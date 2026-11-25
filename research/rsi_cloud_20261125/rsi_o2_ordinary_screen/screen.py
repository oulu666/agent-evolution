import argparse,hashlib,json,os,signal,sqlite3,sys,warnings
from pathlib import Path
def h(b):return hashlib.sha256(b).hexdigest()
def log(f,d):
    b=json.dumps(d,sort_keys=True,separators=(',',':'))
    f.write(json.dumps(dict(d,row_sha256=h(b.encode())),sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
def pandas_run(args,out):
    if args.localsite:sys.path.insert(0,str(Path(args.localsite).resolve()))
    import pandas as pd
    import numpy as np
    assert pd.__version__==args.version
    if args.localsite:assert Path(pd.__file__).is_relative_to(Path(args.localsite).resolve())
    rows=[]
    for variant, values in enumerate(((1500000,9000000000),(-1500000,0,1000001))):
        orig=pd.Series(np.array(values,dtype='timedelta64[us]'),name='duration')
        original_dtype=str(orig.dtype)
        for route in ('default','native_ns'):
            key=dict(issue=71941,version=pd.__version__,variant=variant,route=route)
            log(out,dict(key,event='start'))
            src=orig.to_frame()
            if route=='native_ns':src=src.assign(duration=src.duration.dt.as_unit('ns'))
            with sqlite3.connect(':memory:') as db,warnings.catch_warnings(record=True) as ws:
                warnings.simplefilter('always')
                src.to_sql('durations',db,index=False)
                act=db.execute('SELECT duration, typeof(duration) FROM durations ORDER BY rowid').fetchall()
            oracle=[(v*1000,'integer') for v in values]
            intact=(str(orig.dtype)==original_dtype and np.array_equal(
                        orig.to_numpy().astype('timedelta64[us]').astype(np.int64),values))
            row=dict(key,event='end',passed=act==oracle and bool(intact),actual=act,oracle=oracle,source_unchanged=bool(intact),
                warned_ns=any('ns frequency' in str(w.message) for w in ws),source_dtype=original_dtype,
                written_dtype=str(src.duration.dtype),actions=2+int(route=='native_ns'))
            log(out,row);rows.append(row)
    return rows
def scipy_run(a,out):
    import scipy
    import numpy as np
    from scipy.optimize import root
    assert scipy.__version__==a.version
    def fun(v):
        x,y=v; term=((x-y)**3)/2
        return [x+term-1,y-term]
    rows=[]
    for meth in ('hybr','lm'):
        for variant,start in enumerate(([0.,0.],[1.,.25])):
            for route in ('default','native_count'):
                key=dict(issue=24767,version=scipy.__version__,variant=variant,route=route,solver=meth)
                log(out,dict(key,event='start'))
                observed=[]
                public_counter=0
                def derivative(v):
                    if len(observed)>=16:raise RuntimeError('jacobian cap')
                    observed.append([float(q) for q in v])
                    q=1.5*(v[0]-v[1])**2
                    return [[1+q,-q],[-q,1+q]]
                def counted(v):
                    nonlocal public_counter
                    public_counter+=1
                    return derivative(v)
                sol=root(fun,start,jac=counted if route=='native_count' else derivative,method=meth)
                loss=max(abs(t) for t in fun(sol.x))
                delivered=int(sol.njev) if route=='default' else public_counter
                row=dict(key,event='end',passed=bool(sol.success and loss<=1e-9 and len(observed)==delivered),
                    reported=int(sol.njev),delivered=delivered,observed=len(observed),residual=float(loss),
                    solution=sol.x.tolist(),actions=2+len(observed),actual_callback_entries=observed)
                log(out,row);rows.append(row)
    return rows
def main():
    p=argparse.ArgumentParser()
    p.add_argument('library',choices=['pandas','scipy']);p.add_argument('version')
    p.add_argument('log',type=Path);p.add_argument('--localsite')
    a=p.parse_args()
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('screen wall cap')))
    signal.alarm(240)
    with a.log.open('x') as out:
        try:
            rows=(pandas_run if a.library=='pandas' else scipy_run)(a,out)
        except BaseException as e:
            log(out,dict(event='runtime_error',error=repr(e)))
            raise
    signal.alarm(0)
    print(json.dumps({r:dict(pass_count=sum(x['passed'] for x in rows if x['route']==r),
        total=sum(x['route']==r for x in rows),actions=sum(x['actions'] for x in rows if x['route']==r))
        for r in sorted({x['route'] for x in rows})},sort_keys=True))
if __name__=='__main__':main()
