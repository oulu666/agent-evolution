"""Actually execute fixed, fully identifying pandas batch and its serial control."""
import argparse,itertools,json,random,statistics,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'rsi_pandas_split'))
from pilot import batch, ACT, separate_gold, masks

X=list(itertools.product((0,1),repeat=4))
Q0=(1,1,1,1); Q1=(0,0,1,1);Q2=(0,1,0,1)
def record(q):
    return q[0],q[1],3+q[2],18+(1-q[3])
def run(path,n):
    pairs=sum(len(set(zip(a,b)))==4 for a,b in itertools.combinations(X,2))
    assert pairs==12 and set(zip(Q1,Q2))==set(itertools.product((0,1),repeat=2))
    data=[record(a) for a in (Q0,Q1,Q2)]
    rr={m:[] for m in ('separate','native_batch')}
    r=random.Random(721)
    for _ in range(n):
     ms=list(rr);r.shuffle(ms)
     for m in ms:
       start=time.perf_counter();out={}
       for v in ('old','new'):
          here=path if v=='new' else None
          d={}
          for rows in ([data] if m=='native_batch' else [[a] for a in data]):
             d.update(batch(v,here,rows))
          out[v]={x:sorted(z) for x,z in masks(data,d).items()}
       dt=time.perf_counter()-start
       assert all(len(out['new'][x])==1 for x in data)
       assert tuple(out['new'][data[i]][0] for i in (1,2))==(0,0)
       assert out['old'][(1,1,4,18)]==[0,1]
       rr[m].append(dt)
    print(json.dumps({'diagnostic_pairs':pairs,'first_is_shared':True,'versions':2,'repeats':n,
           'results':{m:dict(median_seconds=statistics.median(v),process_starts=6 if m=='separate' else 2,
                    witness_rows=6,logical_edit_evaluations=12) for m,v in rr.items()}},indent=2))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--new',required=True);a.add_argument('--repeats',type=int,default=5);p=a.parse_args();run(p.new,p.repeats)
