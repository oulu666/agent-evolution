import json,sys,subprocess
from pathlib import Path
from importlib.metadata import version
X=[100,80,99,100,101,125,149,150,151,200,250,100]
VERS=('25.3.0','25.4.0')
TH=150
def worker(root, v):
    sys.path.insert(0,root)
    import attrs
    assert version('attrs')==v and Path(attrs.__file__).is_relative_to(root)
    out=[]
    for x in X:
        seen=[]
        @attrs.define
        class Parcel:
            estimate:int=100
            def __attrs_pre_init__(self, estimate):seen.append(('pre',estimate))
            def __attrs_post_init__(self):seen.append(('post',self.estimate))
        p=Parcel(x)
        assert [n for n,_ in seen]==['pre','post']
        out.append({'asked':x,'stored':p.estimate,'pre':seen[0][1],'post':seen[1][1],'hook':True})
    print(json.dumps(out))
def eq(k):
    return lambda r:r[k]!=r['asked']
def differing(keys,l,r):
    return any(l[k]!=r[k] for k in keys)
def threshold(r):
    return (r['pre']>=TH)!=(r['asked']>=TH)
def sign(r):
    return (r['pre']>0)!=(r['asked']>0)
def audit(rows,decision,truth):
    return dict(correct_reject=sum(decision(r) and truth(r) for r in rows),
                invalid_release=sum(not decision(r) and truth(r) for r in rows),
                unnecessary_reject=sum(decision(r) and not truth(r) for r in rows),
                correct_accept=sum(not decision(r) and not truth(r) for r in rows))
def main(root):
    old,new=[json.loads(subprocess.check_output([sys.executable,'-IB',__file__,'worker',str((root/f'attrs-{v}').resolve()),v],text=True)) for v in VERS]
    pairs=list(zip(old,new,strict=True))
    exact=eq('pre')
    assert all(r['stored']==r['post']==r['asked'] for r in old+new)
    assert all(r['pre']==r['asked'] for r in new)
    inp1={k:dict(endpoint_hits=sum(differing(('stored',),*p) for p in pairs[:k]),
                 separate_callback_control=sum(differing(('pre',),*p) for p in pairs[:k])) for k in (1,4,12)}
    plans={'plain':(0,1,2,3),'diverse':(1,5,7,10),'boundary':(2,4,6,8)}
    inp2={name:dict(calls=len(selected),endpoint_hits=sum(differing(('stored',),*pairs[j]) for j in selected),
                    nondefault_requested=sum(X[j]!=100 for j in selected)) for name,selected in plans.items()}
    obs1={name:dict(hits=sum(differing(keys,*p) for p in pairs),false_alarms=sum(differing(keys,*p) for p in pairs if p[0]['asked']==100))
          for name,keys in [('post_plus_endpoint',('stored','post')),('pre_plus_endpoint',('stored','pre'))]}
    obs2={name:sum(differing(keys,*p) for p in pairs)
          for name,keys in [('full',('pre','post','hook','stored')),('ablate_pre_value',('post','hook','stored'))]}
    r1={name:audit(old,f,exact) for name,f in [('exact',exact),('terminal',eq('stored')),('same_sign',sign)]}
    r2={sem:{name:audit(old,f,oracle) for name,f in [('exact',exact),('threshold',threshold),('endpoint',eq('stored'))]}
        for sem,oracle in [('exact',exact),('threshold',threshold)]}
    print(json.dumps(dict(versions=VERS,paired_executions=len(pairs),raw_states_published=False,
        I1=inp1,I2=inp2,O1=obs1,O2=obs2,R1=r1,R2=r2,controls=dict(fixed_exact_bad=sum(exact(r) for r in new),
        fixed_threshold_bad=sum(threshold(r) for r in new), default_old_bad=sum(exact(r) for r in old if r['asked']==100),
        rule_disagreements=sum(exact(r)!=threshold(r) for r in old))), indent=2,sort_keys=True))
if __name__=='__main__':
    if sys.argv[1]=='worker':worker(*sys.argv[2:])
    else:main(Path(sys.argv[1]))
