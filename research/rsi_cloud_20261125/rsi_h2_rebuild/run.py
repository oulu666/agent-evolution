import sqlite3, random, csv, io, gzip, hashlib, time, json, statistics, sys
R,N,T=16,640,36
SCHEMA="""CREATE TABLE sales(id INTEGER PRIMARY KEY, region INTEGER, sku INTEGER, cents INTEGER, qty INTEGER, published INTEGER,note TEXT);
CREATE INDEX region_sales ON sales(region, published, sku);
CREATE TABLE journal(id,or_,os,oc,oq,op,nr,ns,nc,nq,np);
CREATE TRIGGER changes AFTER UPDATE ON sales BEGIN INSERT INTO journal VALUES(old.id, old.region,old.sku,old.cents,old.qty,old.published,new.region,new.sku,new.cents,new.qty,new.published); END;"""
def batches(kind, seed):
    rng=random.Random(seed)
    rows=[(i, i%R, rng.randrange(32), rng.randrange(100, 3000),rng.randrange(1,6),rng.randrange(10)!=0,'') for i in range(N)]
    hist=[]
    live=rows.copy()
    for t in range(T):
        ops=[]
        for i in rng.sample(range(N), 320 if kind=='dense' else 12):
            old=live[i]
            edit=list(old)
            if kind=='metadata' or (kind in ('sparse','dense') and rng.random()<.20):
                edit[6]=f"{t}:{i}"
            elif kind=='roundtrip':
                edit[3]+=25
            else:
                j=rng.choice([1,2,3,4,5])
                edit[j]={1:rng.randrange(R),2:rng.randrange(32),3:old[3]+17,4:old[4]+1,5:1-old[5]}[j]
            ops.append(tuple(edit));live[i]=tuple(edit)
            if kind=='roundtrip' and rng.random()<.9:
                ops.append(old);live[i]=old
        hist.append(ops)
    return rows,hist

def projection(db,r):
    return tuple(db.execute("SELECT sku,sum(cents*qty),sum(qty) FROM sales WHERE region=? AND published=1 GROUP BY sku ORDER BY sku",(r,)))
def exported(proj):
    f=io.StringIO(newline='')
    w=csv.writer(f,lineterminator='\n')
    w.writerow(('sku','sales_cents','quantity'))
    w.writerows(proj)
    return gzip.compress(f.getvalue().encode(),mtime=0)
def digest(x):
    return hashlib.blake2b(repr(x).encode(),digest_size=24).digest()
def contribution(x):
    return (x[0],x[1],x[2]*x[3],x[3]) if x[4] else None
def order(db,kind,seed,mode):
    rows,hist=batches(kind,seed)
    db.executescript(SCHEMA)
    db.executemany("INSERT INTO sales VALUES(?,?,?,?,?,?,?)",rows)
    projs=[projection(db,r) for r in range(R)]
    hashes=list(map(digest,projs)); files=list(map(exported,projs)); root=digest(rows)
    projection_n=build_n=stale=app_rows=app_eval=cn=0
    ns=app_ns=0
    for ops in hist:
        start=time.perf_counter_ns()
        db.execute("DELETE FROM journal")
        db.executemany("UPDATE sales SET region=?,sku=?,cents=?,qty=?,published=?,note=? WHERE id=?",
                       [x[1:]+x[:1] for x in ops])
        if mode=='dag':
            current=digest(tuple(db.execute("SELECT * FROM sales ORDER BY id")))
            dirty=range(R) if current!=root else ()
            root=current
        elif mode=='full_projection':
            dirty=range(R)
        elif mode=='journal_sql':
            a=time.perf_counter_ns()
            cond="(or_,os,oc,oq,op) != (nr,ns,nc,nq,np)"
            dirty=[x[0] for x in db.execute(f"SELECT or_ FROM journal WHERE op=1 AND {cond} UNION SELECT nr FROM journal WHERE np=1 AND {cond}")]
            app_ns+=time.perf_counter_ns()-a
        elif mode=='endpoint_sql':
            a=time.perf_counter_ns()
            dirty=[x[0] for x in db.execute("""
            WITH bounds AS (SELECT min(rowid) f, max(rowid) l FROM journal GROUP BY id),
            x AS (SELECT jf.or_ a, jf.os b,jf.oc*jf.oq c,jf.oq d,jf.op e,
                         jl.nr v,jl.ns w,jl.nc*jl.nq x,jl.nq y,jl.np z
                  FROM bounds JOIN journal jf ON jf.rowid=bounds.f JOIN journal jl ON jl.rowid=bounds.l)
            SELECT a FROM x WHERE e=1 AND (z=0 OR (a,b,c,d)!=(v,w,x,y))
            UNION
            SELECT v FROM x WHERE z=1 AND (e=0 OR (a,b,c,d)!=(v,w,x,y))""")]
            app_ns+=time.perf_counter_ns()-a
        elif mode=='candidate':
            a=time.perf_counter_ns()
            ends={}
            for jid,*j in db.execute("SELECT * FROM journal ORDER BY rowid"):
                app_rows+=1
                if jid not in ends:
                    ends[jid]=(j[:5],j[5:])
                else:
                    ends[jid]=(ends[jid][0],j[5:])
            dirty=set(); cn+=len(ends)
            for before,after in ends.values():
                if before==after:
                    continue
                x,y=contribution(before),contribution(after);app_eval+=2
                if x!=y:
                    for c in (x,y):
                        if c is not None:dirty.add(c[0])
            app_ns+=time.perf_counter_ns()-a
        for r in sorted(dirty):
            p=projection(db,r); projection_n+=1
            h=digest(p)
            if h!=hashes[r]:
                files[r]=exported(p);hashes[r]=h;build_n+=1
        ns+=time.perf_counter_ns()-start
        for r in range(R):
            stale+=files[r]!=exported(projection(db,r))
    return dict(projections=projection_n,gzip_builds=build_n,stale_regional_outputs=stale,ms=ns/1e6,applicability_ms=app_ns/1e6,applicability_rows=app_rows,applicability_unique_rows=cn,applicability_contributions=app_eval)
def main():
    result={}
    for idx,k in enumerate(('metadata','roundtrip','sparse','dense')):
        out={m:[] for m in (('journal_sql','candidate','endpoint_sql') if '--endpoint' in sys.argv else ('full_projection','candidate','journal_sql') if '--confirm' in sys.argv else ('dag','full_projection','candidate'))}
        for s in range(6):
            modes=list(out)
            random.Random(101+s).shuffle(modes)
            for m in modes:
                with sqlite3.connect(':memory:') as db:
                    out[m].append(order(db,k,31280+s+idx*10+1000*('--confirm' in sys.argv)+2000*('--endpoint' in sys.argv),m))
        result[k]={"aggregate":{m:{a:sum(x[a] for x in rr) if a=='stale_regional_outputs' else round(statistics.median(x[a] for x in rr),3) for a in rr[0]} for m,rr in out.items()},"seeds":out}
    print(json.dumps({"sqlite":sqlite3.sqlite_version,"python":sys.version,"result":result},indent=2))
if __name__=='__main__': main()
