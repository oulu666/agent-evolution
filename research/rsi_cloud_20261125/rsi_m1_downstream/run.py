from pathlib import Path
import os,sys,subprocess,json
from collections import Counter
VERS=('2.4.6','2.5.0','2.5.2')
REV='e946411c6a347e6ec1e5be0d2bef95706ac965e0'
def count(f):
    try:
        return 'pass' if f() else 'wrong'
    except Exception as e:
        return 'exception:'+type(e).__name__
def report(mode, repo):
    import numpy as np
    import quaternion as nq
    import quatica.optiQ as opt
    assert Path(opt.__file__).resolve()==(Path(repo)/'quatica/optiQ.py').resolve()
    assert nq.__version__=='2024.0.12'
    assert Path(opt.__file__).read_text().count('return A.conjugate().T')>=1
    if mode=='native':
        from quatica.utils import quat_hermitian
        opt.qadj=quat_hermitian
    def adj(n,m):
        rows=[[[(i+1)*2,(j+1)*3,1-i-j,(-1)**j] for j in range(m)] for i in range(n)]
        a=nq.as_quat_array(rows)
        expected=[[[rows[i][j][0]]+[-x for x in rows[i][j][1:]] for i in range(n)] for j in range(m)]
        r=opt.qadj(a)
        return r.shape==(m,n) and r.dtype==a.dtype and nq.as_float_array(r).tolist()==expected and nq.as_float_array(a).tolist()==rows
    def gram(n,seed):
        basis,*_=opt.build_singleton_feasible_canonical(n=n,m=None,seed=seed)
        g=np.array([[opt.inner_real(x,y) for y in basis] for x in basis])
        return np.allclose(g,np.eye(len(basis)),atol=1e-8,rtol=0)
    return dict(numpy=np.__version__,quaternion=nq.__version__,result={
        'adjoint':dict(Counter(count(lambda:adj(n,m)) for n,m in ((1,1),(2,3),(3,2)))),
        'canonical_gram':dict(Counter(count(lambda:gram(n,s)) for n,s in ((3,0),(5,1)))),
    })
def main():
    if sys.argv[1]=='--child':
        print(json.dumps(report(*sys.argv[2:])))
    else:
        envroot,repo,prior=map(lambda s:Path(s).resolve(),sys.argv[1:4])
        assert repo.is_dir() and prior.is_dir()
        res={}
        for v in VERS:
            res[v]={}
            wheel=prior if v=='2.4.6' else envroot/f'numpy-{v}'
            for m in ('default','native'):
                env=dict(os.environ,PYTHONPATH=os.pathsep.join(map(str,(wheel,envroot/'quaternion',repo))),PYTHONNOUSERSITE='1', MPLCONFIGDIR=str(envroot/'matplotlib'),OPENBLAS_NUM_THREADS='1')
                row=json.loads(subprocess.check_output([sys.executable,str(Path(__file__).resolve()),'--child',m,str(repo)],env=env,text=True))
                assert row['numpy']==v
                res[v][m]=row['result']
        print(json.dumps(dict(independent_repo_revision=REV,result=res),indent=2))
if __name__=='__main__':
    main()
