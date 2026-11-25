"""Counterexample projection search in a controlled, benign export adapter."""
import argparse,csv,io,itertools,json,math,sqlite3,time
from pathlib import Path
import numpy as np
import openpyxl,xlsxwriter

N=5
A=np.array(list(itertools.product(range(3),repeat=N)),dtype=int)
S=np.vstack([np.zeros(N,int)]+[np.eye(N,dtype=int)[j]*k for j in range(N) for k in (1,2)])
W=np.array([np.where(np.all(A==x,axis=1))[0][0] for x in S])
T=np.count_nonzero(A,axis=1)
VAL=(("0007","0011","0042"),(123,340,505),("2027-01-03","2027-02-09","2028-02-29"),("East, 2","West\n3",'Quoted "bay"'),(-7,0,13))
F=("csv","json","sqlite","xlsx")
MODES=("random","local","aggregate_pair","scope_static","scope_optimistic","cpr")
ANCHOR=11; LIMIT=16
KINDS=("independent","coupled","dense","missing_edge","infeasible")

def codec(kind,cols):
    rows=list(zip(*cols))
    if kind=="csv":
        f=io.StringIO(newline="")
        csv.writer(f).writerows(rows); f.seek(0)
        return list(csv.reader(f))
    if kind=="json": return json.loads(json.dumps(rows,ensure_ascii=False))
    if kind=="sqlite":
        with sqlite3.connect(":memory:") as db:
            db.execute("create table artifact(a,b,c,d,e)")
            db.executemany("insert into artifact values(?,?,?,?,?)",rows)
            return db.execute("select * from artifact order by rowid").fetchall()
    if kind=="xlsx":
        stream=io.BytesIO()
        with xlsxwriter.Workbook(stream,{"in_memory":True}) as book:
            sh=book.add_worksheet()
            for i,row in enumerate(rows):
                for j,v in enumerate(row): sh.write(i,j,v)
        book=openpyxl.load_workbook(stream,read_only=True,data_only=True)
        try: return list(book.active.values)
        finally: book.close()
    raise ValueError(kind)

class World:
    def __init__(self,domain,seed,kind):
        self.domain,self.seed,self.kind=domain,seed,kind
        g=np.random.default_rng(seed)
        order=g.permutation(N)
        self.scope=[(j,) for j in range(N)]
        if kind!="independent":
            for i,j in enumerate(order):
                if kind in ("coupled","missing_edge","infeasible") and i%3==2: continue
                self.scope[j]=(j,int(order[(i+1)%N]))
        self.real=list(self.scope)
        if kind=="missing_edge":
            j=int(order[0])
            self.real[j]+= (int(order[2]),)
        planted=g.integers(0,3,N)
        self.lut=[]
        for j,s in enumerate(self.real):
            # Distinct adapter settings alter the outgoing field, not the checker.
            k=len(s)-1
            table=g.integers(0,3,3**k)
            if k==0: table[0]=planted[j]
            else:
                h=sum(int(planted[p])*3**i for i,p in enumerate(s[1:]))
                table[h]=planted[j]
                if (j+seed)%3==0: table[0]=planted[j]
            if kind=="infeasible" and j==order[0]: table[:]=-1
            self.lut.append(table)
        self.cache={}
    def check(self,i):
        if i not in self.cache:
            a=A[i]; cols=[]
            for j,s in enumerate(self.real):
                k=sum(int(a[p])*3**i for i,p in enumerate(s[1:]))
                vals=VAL[j]
                if a[j]!=self.lut[j][k]:
                    if j==0: vals=tuple(str(int(v)) for v in vals)
                    elif j==1: vals=tuple(v/100 for v in vals)
                    elif j==2: vals=tuple(v.replace("-","/") for v in vals)
                    elif j==3: vals=tuple(v.replace("\n"," ").replace(",",";") for v in vals)
                    else: vals=tuple(abs(v) for v in vals)
                cols.append(vals)
            obs=codec(self.domain,cols)
            exp=list(zip(*VAL))
            if self.domain=="csv": exp=[tuple(map(str,r)) for r in exp]
            self.cache[i]=np.array([all(type(r[j]) is type(e[j]) and r[j]==e[j] for r,e in zip(obs,exp)) for j in range(N)],int)
        return self.cache[i]

def project(scope):
    return np.stack([sum(A[:,p]*3**i for i,p in enumerate(s)) for s in scope],axis=1)

def pick(mode,h,scope,rng,P,design):
    ids=np.array([k for k in range(len(A)) if k not in h]); yy=np.stack(list(h.values())); ii=np.array(list(h)); penalty=T[ids]*1e-4
    if mode=="random": return int(rng.choice(ids))
    if mode=="local":
        # Best fully evaluated incumbent and nearest unexplored edit.
        best=int(ii[np.argmax(yy.sum(1)-T[ii]*.001)])
        return int(ids[np.argmin(np.count_nonzero(A[ids]!=A[best],axis=1)+rng.random(len(ids))*.01)])
    if mode=="aggregate_pair":
        x=design[ii]; y=yy.sum(1)/N
        inv=np.linalg.inv(x@x.T+.6*np.eye(len(ii)))
        q=design[ids]@x.T
        pred=q@inv@y
        sd=np.maximum(0,(design[ids]**2).sum(1)-((q@inv)*q).sum(1))
        return int(ids[np.argmax(pred+.09*np.sqrt(sd)-penalty)])
    pri=np.full((len(ids),N),.40)
    stat_idx=ii if mode!="scope_static" else ii[:ANCHOR]; stat_yy=yy if mode!="scope_static" else yy[:ANCHOR]
    for j in range(N):
        own=A[stat_idx,j]
        for k in range(3):
            x=stat_yy[own==k,j]
            pri[A[ids,j]==k,j]=(1+sum(x))/(2+len(x)) if len(x) else .50
    state=np.full((len(ids),N),-1)
    for j in range(N):
        for code in np.unique(P[stat_idx,j]):
            v=stat_yy[P[stat_idx,j]==code,j]
            if min(v)==max(v): state[P[ids,j]==code,j]=v[0]
    known=state!=-1
    ev=np.where(known,state,pri)
    if mode=="scope_static": return int(ids[np.argmax(ev.prod(1)-penalty)])
    if mode=="scope_optimistic": return int(ids[np.argmax(ev.prod(1)+.05*(~known).sum(1)-penalty)])
    # CPR: counterexample pruning with soft backoff for a misspecified scope.
    # Update all still-plausible completions after a new clause observation.
    plaus=(state!=0).all(1)
    if not np.any(plaus):
        return int(ids[np.argmax(ev.sum(1)+.02*(~known).sum(1)-penalty)])
    keep=np.where(plaus)[0]; probs=ev.prod(1)
    score=probs.copy()
    for j in range(N):
        for c in np.unique(P[ids[keep],j]):
            mask=(P[ids,j]==c)&(~known[:,j])&plaus
            if mask.any():
                # Expected ruled-out feasible mass, conditional on other clause priors.
                m=np.sum(probs[mask]/np.maximum(pri[mask,j],1e-9))
                score[mask]+=.65*(1-pri[mask,j])*m/len(keep)
    return int(ids[keep[np.argmax((score-penalty)[keep])]])

def run(out,ns,offset):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    design=np.column_stack([np.ones(len(A))]+[(A[:,j]==k).astype(float) for j in range(N) for k in (1,2)]+[( (A[:,j]==k)&(A[:,p]==v)).astype(float) for j,p in itertools.combinations(range(N),2) for k in (1,2) for v in (1,2)])
    rows=[]
    for fi,f in enumerate(F):
        for ti,t in enumerate(KINDS):
            for s in range(ns):
                seed=offset+fi*100000+ti*10000+s
                env=World(f,seed,t); P=project(env.scope)
                for mode in MODES:
                    rng=np.random.default_rng(seed+56790)
                    h={}; delivered=None; inds=[]; outs=[]
                    for q in range(LIMIT):
                        idx=int(W[q]) if q<ANCHOR else pick(mode,h,env.scope,rng,P,design)
                        r=env.check(idx);h[idx]=r;inds.append(idx);outs.append(''.join(str(v) for v in r))
                        if r.all(): delivered=q+1;break
                    rows.append(dict(format=f,kind=t,seed=seed,method=mode,success=int(delivered is not None),queries=len(h),found=delivered or 0,indices=inds,verdicts=outs))
    with (out/"traces.csv").open("w",newline="") as f:
        csvf=csv.DictWriter(f,fieldnames=rows[0]);csvf.writeheader();csvf.writerows(rows)
    from collections import defaultdict
    a=defaultdict(list)
    for row in rows:
        for key in ("all",row["format"],row["kind"]): a[key,row["method"]].append(row)
    ans={}
    for (g,m),rr in a.items():
        ans.setdefault(g,{})[m]=dict(n=len(rr),ok=sum(r["success"] for r in rr),calls=sum(r["queries"] for r in rr),at13=sum(0<r["found"]<=13 for r in rr))
    (out/"summary.json").write_text(json.dumps(ans,indent=2)+"\n")
    print(json.dumps(ans,sort_keys=True))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);p.add_argument("--ns",type=int,default=12);p.add_argument("--offset",type=int,default=500000);a=p.parse_args();run(a.out,a.ns,a.offset)
