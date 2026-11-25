"""Actual openpyxl artifact replay; policy-identification finite experiment."""
import argparse,collections,io,json
from pathlib import Path
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Font

COST=.35
DEFER=.35
N=16
ACTIONS=("accept","rollback","verify")

def artifact(amount,correct):
    w=Workbook()
    w.active['A1']=amount
    w.active['A1'].number_format='"USD "0.00' if correct else '0.00'
    w.active['A1'].font=Font(bold=True)
    f=io.BytesIO();w.save(f);w.close();return f.getvalue()

def observe(raw):
    w=load_workbook(io.BytesIO(raw))
    try:
        a=w.active['A1']
        return (a.value,a.font.bold)
    finally:w.close()

def audit(raw,target):
    w=load_workbook(io.BytesIO(raw))
    try:
        a=w.active['A1']
        return (a.value,a.font.bold,a.number_format)==(target,True,'"USD "0.00')
    finally:w.close()

def make(world,j,seed):
    # Outcome coupling is controlled; actual workbook validity is measured.
    target=1000+seed*32+j//4
    a=(j%4 in (0,3))
    r=a if world=="redundant" else not a
    incumbent=artifact(target,r); edited=artifact(target,a)
    unchanged_observation=(observe(incumbent),observe(edited))
    validity=(int(audit(edited,target)),int(audit(incumbent,target)))
    return unchanged_observation,validity

def costs(a,r):
    return (float(not a),float(not r),COST+DEFER*int(not (a or r)))

def best(x):
    return min(range(3),key=lambda j:(x[j],j))

def run(out):
    worlds={}
    for name in ("redundant","complementary"):
        train=[make(name,j,0) for j in range(N)]
        test=[make(name,j,1) for j in range(N)]
        # Train types: accept-only; a counterbalanced overlap design observes
        # one action per instance and exactly matches marginals; paired gets both.
        # Observer features cannot distinguish the two instances within a logged arm.
        passive=[(o,'accept',a) for o,(a,r) in train]
        overlap=[(o,('accept','rollback')[j%2],(a,r)[j%2]) for j,(o,(a,r)) in enumerate(train)]
        obs=tuple(o for o,_ in train)
        worlds[name]=dict(train=train,test=test,passive=passive,
                          overlap=sorted(overlap),obs=obs)
    assert worlds["redundant"]["passive"]==worlds["complementary"]["passive"]
    assert worlds["redundant"]["overlap"]==worlds["complementary"]["overlap"]
    result={}
    for world,d in worlds.items():
        ac=list((a,r) for _,(a,r) in d['train'])
        p=sum(a for a,r in ac)/N;q=sum(r for a,r in ac)/N
        expected=[sum(costs(a,r)[k] for a,r in ac)/N for k in range(3)]
        # Strong matched-data comparators: exact marginal Bayesian model
        # assuming independence, and sharp worst-case Fréchet bound.
        bayes=[1-p,1-q,COST+DEFER*(1-p)*(1-q)]
        worst_joint_failure=1-max(p,q)
        robust=[1-p,1-q,COST+DEFER*worst_joint_failure]
        selections={"always_accept":0,"always_rollback":1,"always_verify":2,
                     "overlap_independence":best(bayes),
                     "overlap_minimax":best(robust),"paired_joint":best(expected)}
        true=[sum(costs(a,r)[k] for _,(a,r) in d['test'])/N for k in range(3)]
        result[world]={"n":N,"marginal":[p,q],"action_cost":{k:round(c,6) for k,c in zip(ACTIONS,true)},
                       "selectors":{k:{"action":ACTIONS[i],"cost":round(true[i],6),
                                        "regret":round(true[i]-min(true),6)} for k,i in selections.items()}}
    p=Path(out);p.mkdir(parents=True,exist_ok=True)
    (p/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);run(p.parse_args().out)
