"""Independent verification of saved decisions from verdict strings, standard library only."""
import collections,csv,ast,math,json
from pathlib import Path
base=Path(__file__).resolve().parent
def read(name):
    cases=collections.defaultdict(dict)
    with (base/name/'traces.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            key=tuple(row[k] for k in ('format','kind','seed'))
            m=row['method']; assert m not in cases[key]
            idx=ast.literal_eval(row['indices']); out=ast.literal_eval(row['verdicts'])
            calls=int(row.get('calls',row.get('queries'))); res=int(row['found'])
            assert len(set(idx))==len(idx)==len(out)==calls
            assert all(0<=i<243 for i in idx)
            assert all(len(x)==5 and set(x)<=set('01') for x in out)
            first=next((i+1 for i,x in enumerate(out) if x=='11111'),0)
            assert first==res and (not res or res==calls)
            if row.get('success') is not None: assert int(row['success'])==bool(res)
            cases[key][m]=(res,calls)
    assert len({tuple(sorted(m)) for m in cases.values()})==1
    return cases
def pairs(cases,left,right,budget):
    both=[(0<r[left][0]<=budget,0<r[right][0]<=budget) for r in cases.values()]
    a=sum(x and not y for x,y in both); b=sum(y and not x for x,y in both)
    n=len(both)
    p=min(1.,2*sum(math.comb(a+b,i) for i in range(min(a,b)+1))/2**(a+b))
    # Standard paired normal summary, not a claim about real-world tasks.
    d=[int(x)-int(y) for x,y in both]; mean=(a-b)/n
    se=(sum((x-mean)**2 for x in d)/(n-1)/n)**.5 if n>1 else 0
    return {'n':n,'left':sum(x for x,_ in both),'right':sum(y for _,y in both),
       'left_only':a,'right_only':b,'mcnemar_exact_unadjusted':p,
       'paired_normal_95pct_diff':[mean-1.96*se,mean+1.96*se]}
v1=read('holdout'); v2={**read('shift_a'),**read('shift_b')}
assert len(v1)==240 and len(v2)==288
d={'v1':{str(b):pairs(v1,'cpr','scope_optimistic',b) for b in (13,16)},'v2':{}}
for left in ('scoper','ensemble_no_bonus'):
 for m in next(iter(v2.values())):
  if m==left: continue
  key=left+'_vs_'+m
  d['v2'][key]={str(b):pairs(v2,left,m,b) for b in (13,16,20)}
d['v2_by_kind']={k:pairs({x:r for x,r in v2.items() if x[1]==k},'scoper','fixed_scope',16) for k in sorted({x[1] for x in v2})}
d['v2_by_batch']={k:pairs(read(k),'scoper','fixed_scope',16) for k in ('shift_a','shift_b')}
(base/'paired_audit.json').write_text(json.dumps(d,indent=2)+'\n')
print(d['v1']['16']);print(d['v2']['scoper_vs_fixed_scope']['16']);print(d['v2']['ensemble_no_bonus_vs_static_cpr'])
