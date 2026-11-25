from collections import Counter
from pathlib import Path
import json, math, warnings, subprocess, sys, os
CASES={
 '33155':('2.5.3','2.5.4','2.5.5'),
 '33179':('2.5.3','2.5.4','2.5.5'),
 '31453':('2.4.4','2.4.5','2.4.6'),
}
def quantile(xs,q):
    xs=sorted(x for x in xs if not math.isnan(x))
    if not xs:return float('nan')
    p=q*(len(xs)-1); j=int(p)
    return xs[j]+(xs[min(j+1,len(xs)-1)]-xs[j])*(p-j)
def test(np,case,method):
    results=Counter()
    with warnings.catch_warnings():
     warnings.simplefilter('ignore',RuntimeWarning)
     if case=='33155':
      for h in (2,5,9):
       for first_missing in (True,False):
        for q in (.31,.73):
         rows=[[h+h*k for k in range(4)],[float('nan')]*4]
         if first_missing: rows=rows[::-1]
         a=np.array(rows,dtype=np.float32)
         expected=[[quantile(xs,q) for xs in rows]]
         try:
            out=np.nanquantile(a if method=='default' else a.astype(np.float64),[q],axis=1)
            correct=out.shape==(1,2) and out.dtype==np.dtype('float64') and np.allclose(out,expected,rtol=1e-14,atol=0,equal_nan=True)
            results['pass' if correct else 'wrong']+=1
         except Exception as e:results['exception:'+type(e).__name__]+=1
     elif case=='33179':
      for typ in (np.complex64,np.complex128):
       for frac in (.75,.98,.01):
        for sign in (-1,1):
         mx=np.finfo(np.float32 if typ==np.complex64 else np.float64).max
         r=complex(0,sign*float(mx)*frac)
         a=np.array([r],dtype=typ)
         target_mag=math.sqrt(abs(complex(a[0]).imag)/2)
         try:
            b=np.sqrt(a) if method=='default' else np.sqrt(a/4)*2
            tol=3e-7 if typ==np.complex64 else 3e-14
            val=complex(b.item())
            ok=b.shape==(1,) and b.dtype==typ and math.isclose(val.real,target_mag,rel_tol=tol) and math.isclose(val.imag,sign*target_mag,rel_tol=tol)
            results['pass' if ok else 'wrong']+=1
         except Exception as e:results['exception:'+type(e).__name__]+=1
     elif case=='31453':
      for vals in ([True,False,True,False],[False]*4,[True]*4):
       for layout in ('array','matrix','reverse','slice'):
        a=np.array(vals,dtype=bool)
        if layout=='matrix': a=a.reshape(2,2)
        if layout=='reverse': a=a[::-1]
        if layout=='slice': a=a[::2]
        orig=a.tolist()
        try:
            b=a.conj() if method=='default' else a.copy()
            ok=b.shape==a.shape and b.dtype==np.dtype('bool') and b.tolist()==orig and a.tolist()==orig
            results['pass' if ok else 'wrong']+=1
        except Exception as e: results['exception:'+type(e).__name__]+=1
    assert sum(results.values())==12
    return dict(sorted(results.items()))
def main():
    if sys.argv[1]=='--child':
        import numpy as np
        case=sys.argv[2]
        print(json.dumps(dict(version=np.__version__,results={m:test(np,case,m) for m in ('default','native')})))
        return
    root=Path(sys.argv[1]).resolve()
    output={}
    for case,versions in CASES.items():
        out={}
        for v in versions:
            install=root/v
            if not install.exists():
                out[v]={'unavailable':True}
                continue
            env=dict(os.environ,PYTHONPATH=str(install),PYTHONNOUSERSITE='1')
            row=json.loads(subprocess.check_output([sys.executable,str(Path(__file__).resolve()),'--child',case],env=env,text=True))
            assert row['version']==v
            out[v]=row['results']
        output[case]=out
    print(json.dumps(output,indent=2))
if __name__=='__main__':main()
