"""Decision study over actual versioned wcwidth libraries. No external package installation."""
import itertools as it
import json
from collections import Counter
from importlib.metadata import version
from pathlib import Path
import subprocess
import sys

OLD,NEW='0.2.14','0.3.0'
AMB='·Ω¡'
GOAL=16

def fixture(i,group):
    a,b=AMB[i%len(AMB)],AMB[(i+1)%len(AMB)]
    text=[f'job{i}:{a}',f'log{i}:{b}']
    profiles={
        'new_only':(1,1),'fallback_only':(2,2),'both':(2,1),'neither':(1,2),
    }[group]
    if group=='both':text=[f'job{i}:x',f'log{i}:y']
    return text,profiles

def run_worker(v,root):
    sys.path.insert(0,root)
    import wcwidth
    assert version('wcwidth')==v and Path(wcwidth.__file__).is_relative_to(root)
    for text,profile in json.load(sys.stdin):
        if v==OLD:
            out=[wcwidth.wcswidth(s)+sum(c in AMB for c in s) for s in text]
            print(json.dumps({'B':out}))
        else:
            out=[wcwidth.wcswidth(s) for s in text]
            native=[wcwidth.wcswidth(s,ambiguous_width=p) for s,p in zip(text,profile,strict=True)]
            print(json.dumps({'A':out,'N':native}))

def oracle(text,profile):
    return [sum(p if ch in AMB else 1 for ch in s) for s,p in zip(text,profile,strict=True)]

def route(text,profile):
    active={p for s,p in zip(text,profile,strict=True) if any(c in AMB for c in s)}
    if not active or active=={1}:return 'A'
    if active=={2}:return 'B'
    return None

def run_policy(policy,plain,good):
    audited=[]
    if policy=='audit_bundle':
        audited=['A','B']
        a=next((x for x in audited if good[x]),None)
    elif policy=='audit_short':
        audited=['A']
        if not good['A']:audited.append('B')
        a=next((x for x in audited if good[x]),None)
    elif policy=='native_A_B_routing':a=route(*plain)
    else:a=policy
    correct=a is not None and good[a]
    wrong=a is not None and not good[a]
    abstain=a is None
    return dict(audit_report_execs=len(audited),deploy_report_execs=int(a is not None and a not in audited),
                correct=int(correct),wrong=int(wrong),abstain=int(abstain),
                milli_cost=175*len(audited)+1000*int(wrong)+350*int(abstain))

def main(root):
    families=dict(disjoint=('new_only','fallback_only'),overlap=('both','neither'))
    design=[(group,i) for group in it.chain.from_iterable(families.values()) for i in range(12)]
    items=[fixture(i,k) for k,i in design]
    result={}
    for v in (OLD,NEW):
        subprocess_result=subprocess.run([
            sys.executable,'-I',str(Path(__file__).resolve()),'worker',v,str((root/f'wcwidth-{v}').resolve())
        ],input=json.dumps(items),text=True,capture_output=True,check=True)
        res=[json.loads(s) for s in subprocess_result.stdout.splitlines()]
        assert len(res)==len(items)
        for q,r in zip(design,res,strict=True):
            result.setdefault(q,{}).update(r)
    summary={}
    for family,groups in families.items():
        counts=Counter()
        field_hits=Counter()
        totals={m:Counter() for m in ('A','B','N','audit_bundle','audit_short','native_A_B_routing')}
        sample={}
        for k,i in design:
            if k not in groups:continue
            text,prof=fixture(i,k)
            intended=oracle(text,prof)
            observed=result[k,i]
            good={}
            for track,width in observed.items():
                produced=[s+' '*(GOAL-w) for s,w in zip(text,width,strict=True)]
                wanted=[s+' '*(GOAL-w) for s,w in zip(text,intended,strict=True)]
                good[track]=produced==wanted
                field_hits[track]+=sum(a==b for a,b in zip(produced,wanted,strict=True))
            counts[f"{int(good['A'])}{int(good['B'])}"]+=1
            if i==0:sample[k]=dict(text=text,declared=prof,expected=intended,observed=observed)
            for m,t in totals.items():t.update(run_policy(m,(text,prof),good))
        n=sum(counts.values())
        means={k:round(v['milli_cost']/n/1000,6) for k,v in totals.items()}
        summary[family]=dict(reports=n,joint=dict(counts),success_marginals=dict(
            A=(counts['10']+counts['11'])/n,B=(counts['01']+counts['11'])/n),
            field_hits=dict(field_hits),outcomes=totals,mean_cost=means,samples=sample,
            best_fixed_or_bundle=min(('A','B','audit_bundle'),key=means.get),
            best_fixed_or_short=min(('A','B','audit_short'),key=means.get))
    print(json.dumps(dict(versions=[OLD,NEW],panels=summary),indent=2,sort_keys=True))

if __name__=='__main__':
    if sys.argv[1]=='worker':run_worker(*sys.argv[2:])
    else:main(Path(sys.argv[1]))
