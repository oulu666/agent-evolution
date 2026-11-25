"""Predeclared semantically split migration and matched simple alternatives."""
import argparse,copy,itertools,json,os,subprocess,sys
from collections import defaultdict
from pathlib import Path
R=Path(__file__).resolve().parent
ACT=('series','both')
# 4 observed history bits. Only the first means 'view versus copy'.
# State split cannot rely on library identity or output values.
ENVS={'old':'2.2.3','new':'3.0.0'}

def data(full):
    if not full:return [(a,0,3,0) for a in (0,1)]
    return [(a,s,w,seed) for a,s,w,seed in itertools.product((0,1),range(2),(3,4),range(12,24))]

def batch(tag,path,rows):
    q=[(*x,y) for x in rows for y in ACT]
    env=os.environ.copy()
    if path: env['PYTHONPATH']=str(Path(path).resolve())
    else:env.pop('PYTHONPATH',None)
    r=subprocess.run([sys.executable,str(R/'worker.py')],env=env,input=json.dumps(q),capture_output=True,text=True,check=True)
    obs=[json.loads(line) for line in r.stdout.splitlines()]
    assert len(obs)==len(q) and {x['version'] for x in obs}=={ENVS[tag]}
    return {tuple(k):o for k,o in zip(q,obs)}

def separate_gold(x):
    attached, _, width, seed=x
    orig=[8+seed,9+seed,12+seed]+[19+seed]*(width-3)
    edit=[20+seed,*orig[1:]]
    return [edit if attached else orig,edit]

def key(x):
    a,s,w,n=x
    return (a,bool(s),w==4,n%2==0)

def masks(rows,observed):
    return {x:{j for j,m in enumerate(ACT) if observed[(*x,m)]['after']==separate_gold(x)} for x in rows}

def fit(ex,old_action='series',strategy='local'):
    def get(x,j):return 0 if j<0 else int(key(x)[j])
    possible=[]
    for j in (-1,*range(4)):
        for a in range(len(ACT)):
            for b in (range(len(ACT)) if j>=0 else (a,)):
                if all((a,b)[get(x,j)] in acts for x,acts in ex.items()):
                    # Same grammar and the same counterexamples. Refine by minimizing
                    # changes from the old state; cold prefers low complexity and tuple order.
                    score=( (a!=0)+(b!=0),j>=0,j,a,b) if strategy=='local' else (j>=0,j,a,b)
                    possible.append((score,j,a,b))
    if not possible:return None
    _,j,a,b=min(possible)
    return lambda x:ACT[(a,b)[get(x,j)]]

def run(path,out):
    q=Path(out); q.mkdir(parents=True,exist_ok=True)
    train=data(False);tests=data(True); allrows=train+tests
    obs={k:batch(k,path if k=='new' else None,allrows) for k in ENVS}
    hs={k:masks(allrows,v) for k,v in obs.items()}
    assert set(map(frozenset,(hs['old'][x] for x in train)))=={frozenset((0,)),frozenset((0,1))}
    assert set(map(frozenset,(hs['new'][x] for x in train)))=={frozenset((0,)),frozenset((1,))}
    for x in allrows:
      y=(1-x[0],*x[1:])
      assert all(v[(*x,'series')]['before']==v[(*y,'series')]['before'] for v in obs.values())
    # Positive and negative evidence genuinely keep the same current observation.
    cases={}
    for budget in (1,2):
     for selection,L in [('draft_first',train[:budget]),('attached_first',train[::-1][:budget])]:
      labels={x:hs['new'][x] for x in L}
      methods={'old':lambda x:'series','refine':fit(labels),'cold_stump':fit(labels,strategy='cold'),
               'expert_origin':lambda x:'both' if x[0] else 'series'}
      results={}
      for z,func in methods.items():
       results[z]={}
       for tag,observed in obs.items():
        good=sum(observed[(*x,func(x))]['after']==separate_gold(x) for x in tests)
        results[z][tag]={'correct':good,'wrong':len(tests)-good}
      results['metadata_probe']={}
      for tag,observed in obs.items():
        # Measures a real readable NumPy predicate; this baseline explicitly pays an extra probe.
        good=sum(observed[(*x,'both' if observed[(*x,'series')]['shared'] else 'series')]['after']==separate_gold(x) for x in tests)
        results['metadata_probe'][tag]={'correct':good,'wrong':len(tests)-good,'extra_metadata_probes':len(tests)}
      cases[f'{budget}_{selection}']=results
    proof={f'{k}_{x[0]}':{'actions':[ACT[a] for a in sorted(hs[k][x])],
          'same_before':obs[k][(*x,'series')]['before'],'shares_memory':obs[k][(*x,'series')]['shared']}
          for k in ENVS for x in train}
    d={'n':len(tests),'cases':cases,'cert':proof}
    (q/'summary.json').write_text(json.dumps(d,indent=2)+'\n')
    print(json.dumps(d,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--new',required=True);p.add_argument('--out',required=True);a=p.parse_args();run(a.new,a.out)
