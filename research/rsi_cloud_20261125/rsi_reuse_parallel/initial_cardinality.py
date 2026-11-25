"""Benign cross-task counterexample transfer over actual Decimal exports."""
import argparse, collections, csv, io, json, random
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_HALF_DOWN, ROUND_DOWN, ROUND_UP, ROUND_FLOOR, ROUND_CEILING
from fractions import Fraction
from pathlib import Path

MODES=(ROUND_HALF_EVEN,ROUND_HALF_UP,ROUND_HALF_DOWN,ROUND_DOWN,ROUND_UP,ROUND_FLOOR,ROUND_CEILING)
METHODS=('default','exact','recent','source_vote','ctx_version_space','signature_reuse')
REGIMES=('stable','tagged_shift','untagged_shift','mixed')
N=48
TEST=10

def render(x,k,mode,family):
    v=Decimal(x).quantize(Decimal(1).scaleb(-k),rounding=MODES[mode])
    t=format(v,'f')
    if family=='csv':
        f=io.StringIO();csv.writer(f).writerow([t]);t=next(csv.reader(io.StringIO(f.getvalue())))[0]
    elif family=='json':
        t=json.loads(json.dumps({'total':t}))['total']
    return t

def oracle(x,k,i):
    z=Fraction(x)*(10**k);n=z.numerator//z.denominator;s=z-n
    if not s:j=n
    elif i==0:j=n+int(s>Fraction(1,2) or (s==Fraction(1,2) and n%2!=0))
    elif i==1:j=n+int(s>Fraction(1,2) or (s==Fraction(1,2) and z>0))
    elif i==2:j=n+int(s>Fraction(1,2) or (s==Fraction(1,2) and z<0))
    elif i==3:j=n+int(z<0)
    elif i==4:j=n+int(z>0)
    elif i==5:j=n
    else:j=n+1
    return Fraction(j,10**k)

def discover(seed,regime):
    r=random.Random(seed); a=r.randrange(7); b=(a+r.randrange(1,7))%7
    def item(i,source=False):
        k=r.randrange(1,4)
        v=r.randrange(1000,9900)*10+r.choice((0,1,4,5,5,6,9));x=format(Decimal(r.choice((-1,1))*v).scaleb(-k-1),'f')
        if source:f='csv' if i%2 else 'json'
        else:f=('plain','json')[i%2]
        ctx='a' if i%2 else 'b'
        # Tags identify known deployment changes, but not the new mode.
        tag='2' if not source and regime=='tagged_shift' else '1'
        truth=(a if ctx=='a' else b) if regime=='mixed' else (b if not source and regime in ('tagged_shift','untagged_shift') else a)
        return x,k,f,ctx,tag,truth
    return [item(i,True) for i in range(8)],[item(i) for i in range(TEST)]

def signature(x,k):
    # Rank-normalized equivalence classes, with no target readback. The
    # method derives these from Decimal's documented rounding predicates.
    z=Fraction(x)*(10**k)
    n=z.numerator//z.denominator; s=z-n
    return (s==0,s<Fraction(1,2),s==Fraction(1,2),z<0,n%2)
def equivalence(x,k):
    vals=[oracle(x,k,i) for i in range(7)]
    return [{j for j in range(7) if vals[j]==v} for v in vals]

def bank(source,seed):
    r=random.Random(seed+123)
    out=[]
    for x,k,f,c,t,truth in source:
        choice=r.randrange(7)
        success=Fraction(render(x,k,choice,f))==oracle(x,k,truth)
        out.append((x,k,f,c,t,choice,success))
    return out

def choose(method,history,x,k,f,c,t,active,tried):
    if method=='default':prior=[0]*7
    elif method=='exact':
        hits=[(j,ok) for xx,kk,ff,cc,tt,j,ok in history if (xx,kk,ff,cc,tt)==(x,k,f,c,t)]
        prior=[sum((1 if ok else -1) for j,ok in hits if j==i) for i in range(7)]
    elif method=='recent':
        hits=[j for _x,_k,_f,cc,tt,j,ok in history if (cc,tt)==(c,t) and ok]
        prior=[int(bool(hits) and i==hits[-1]) for i in range(7)]
    elif method=='source_vote':
        hits=[(j,ok) for _x,_k,_f,_cc,tt,j,ok in history if tt==t]
        prior=[sum((1 if ok else -1) for j,ok in hits if j==i) for i in range(7)]
    else:
        # Same representation for strong context-only comparator. Transfer
        # hypothesis differs only in when a signature is admitted.
        used=[row for row in history if row[4]==t and
              (row[3]==c or (method=='signature_reuse' and signature(row[0],row[1])==signature(x,k)))]
        prior=[0]*7
        for xx,kk,_f,_c,_t,j,ok in used:
            eq=equivalence(xx,kk)[j]
            for i in range(7): prior[i]+=1 if ((i in eq)==ok) else -2
    cand=[i for i in range(7) if i not in tried]
    # Matched within-task equivalence elimination. Use the best remaining
    # individual mode as tie break for unknown/contradictory logs.
    pool=[i for i in cand if i in active] or cand
    eq=equivalence(x,k)
    return max(pool,key=lambda i:(sum(prior[j]+100 for j in (eq[i]&set(pool))),prior[i],-i)) if method.startswith(('ctx_','signature')) else max(pool,key=lambda i:(prior[i],-i))

def run(out):
    by=collections.defaultdict(lambda:[0,0,0]); rows=[]
    for reg in REGIMES:
      for seed in range(N):
        s,targets=discover(seed,reg); init=bank(s,seed)
        for m in METHODS:
          for x,k,f,c,t,truth in targets:
            active=set(range(7)); eq=equivalence(x,k); tried=[]; win=0
            for j in (1,2):
                i=choose(m,init,x,k,f,c,t,active,tried);tried.append(i)
                if Fraction(render(x,k,i,f))==oracle(x,k,truth): win=j;break
                active-=eq[i]
            row=(reg,m,win,len(tried),f);rows.append(row)
            for key in ((reg,m),('whole',m)):
                b=by[key];b[0]+=int(win==1);b[1]+=int(win>0);b[2]+=len(tried)
    p=Path(out);p.mkdir(parents=True,exist_ok=True)
    d={}
    for (g,m),v in by.items():
        d.setdefault(g,{})[m]=dict(first=v[0],two=v[1],calls=v[2],n=N*TEST*(4 if g=='whole' else 1))
    (p/'summary.json').write_text(json.dumps(d,indent=2)+'\n')
    print(json.dumps(d))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True)
    run(p.parse_args().out)
