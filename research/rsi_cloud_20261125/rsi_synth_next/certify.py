from pilot import GRAMMAR, TARGETS, apply, base, expected, md, project
import numpy as np

n=m=0
for seed in (0,5):
    x=base(seed)
    for spec in TARGETS.values():
        assert np.array_equal(apply(x,spec),expected(x,spec)),spec
    for expr in GRAMMAR:
        z=apply(x,expr);info=md(x,expr)
        if info is None:
            assert z is None
            continue
        shape,ts=info
        assert z.shape==shape
        h,w,_=shape
        n+=1
        for p in {(0,0),(1 if h>1 else 0,0),(h//2,w//2),(h-1,w-1),(0,w-1)}:
            assert project(x,expr,ts,*p)==tuple(int(k) for k in z[p]),(expr,p)
            m+=1
print(f'Passed {n} full grammar executions, {m} projected pixel checks, and 14 independent target oracle checks.')
