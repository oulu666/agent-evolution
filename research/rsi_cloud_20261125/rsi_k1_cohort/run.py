import os,sys,json,subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime,timedelta
D={'pandas':['3.1.0','3.1.1'],'packaging':['26.3','26.4']}
def check(oracle,f):
    try:return 'pass' if f()==oracle else 'wrong'
    except Exception as e:return type(e).__name__
def pandas_cases():
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    try:
        from py.path import local as path_object
        adapter='py.path.local'
    except ImportError:
        class path_object(os.PathLike):
            def __init__(self,path): self.path=Path(path)
            def __fspath__(self): return str(self.path)
            def write(self,data): return self.path.write_text(data,encoding='utf-8')
            def read(self): return self.path.read_text(encoding='utf-8')
        adapter='standalone PathLike with read and write convenience methods'
    res={}
    for m in ('default','native'):
      res[m]={}
      for c in ('71743','71567','71769'):
        res[m][c]=[]
        for i in range(6):
            ts=datetime(2022+i,2,3,4,5)
            unit=('us','ms','ns')[i//2]
            if c=='71743':
                other=ts+timedelta(days=2) if i%3==0 else None
                oracle=((ts,other),(ts,other))
                def fn():
                    x=pd.DataFrame(dict(d=np.array([ts,other],dtype=f'datetime64[{unit}]')))
                    y=(x.copy(deep=True) if m=='native' else x).convert_dtypes(dtype_backend='pyarrow')
                    return tuple(tuple(None if pd.isna(t) else t for t in a['d']) for a in (x,y))
            elif c=='71567':
                change=lambda x:x.replace(year=2031)
                end=ts.replace(year=2034)
                step=timedelta(minutes=20)
                oracle=((change(ts),change(ts+step),end),(ts,ts+step,ts+2*step))
                def fn():
                    x=pd.Series(pd.date_range(ts,periods=3,freq='20min').as_unit(unit))
                    y=x.transform(change) if m=='native' else x.map(change)
                    y.iloc[2]=end
                    return tuple(y),tuple(x)
            else:
                oracle=(f'name,qty\nred,{i}\nblue,{i+2}\n',(('red',i),('blue',i+2)))
                def fn():
                    with TemporaryDirectory() as tmp:
                        p=Path(tmp)/'report.csv'
                        x=p if i in (0,5) else path_object(str(p))
                        if m=='native':x=os.fspath(x)
                        pd.DataFrame({'name':['red','blue'],'qty':[i,i+2]}).to_csv(x,index=False)
                        return p.read_text(),tuple(pd.read_csv(x).itertuples(index=False,name=None))
            res[m][c].append(check(oracle,fn))
    return dict(version=pd.__version__,arrow=pa.__version__,numpy=np.__version__,adapter=adapter,result=res)
def packaging_cases():
    import packaging
    from packaging.specifiers import SpecifierSet
    result={}
    for m in ('default','native'):
        outcomes=[]
        for b in (4,8,14):
          for major in (b+2,b):
            named,unnamed,ordinary=f'{major}.5a1',f'{major}.5a01',f'{b}.6'
            seq=(named,unnamed,ordinary,f'{b-1}.9')
            def fn():
                a=SpecifierSet(f'>={b}.0,<{b+1}.0').to_range()
                n=SpecifierSet(f'==={named}').to_range()
                if m=='native':
                    keep=set(a.filter(seq))|set(n.filter(seq))
                    return tuple(s for s in seq if s in keep)
                return tuple((a|n).filter(seq))
            outcomes.append(check((named,ordinary),fn))
        result[m]={'1511':outcomes}
    return dict(version=packaging.__version__,result=result)
if __name__=='__main__':
    if sys.argv[1]=='--child':
        print(json.dumps((pandas_cases if sys.argv[2]=='pandas' else packaging_cases)()))
    else:
        root=Path(sys.argv[1]).resolve()
        out={}
        for pkg,vs in D.items():
            for v in vs:
                dirs=[root/f'{pkg}-{v}']+([root/'pyarrow-22.0.0'] if pkg=='pandas' else [])
                assert all(x.exists() for x in dirs),dirs
                e=dict(os.environ,PYTHONPATH=os.pathsep.join(map(str,dirs)),PYTHONNOUSERSITE='1')
                row=json.loads(subprocess.check_output([sys.executable,str(Path(__file__).resolve()),'--child',pkg],env=e,text=True))
                assert row['version']==v
                out[f'{pkg}-{v}']=row
        print(json.dumps(out,indent=2))
