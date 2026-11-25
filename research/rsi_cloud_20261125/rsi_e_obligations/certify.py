from itertools import combinations
from pilot import W,STABLE,SHIFT,UNKNOWN,audit
for which,reg in [('stable',STABLE),('prior_shift',SHIFT),('new_shape',UNKNOWN)]:
  missed=0
  for scope,mutations in reg.items():
    mat=[{w for w in W if not audit(w,op,j+100)} for op,n in mutations.items() for j in range(n)]
    assert all(mat)
    missed+=min(sum(not (set(ws)&row) for row in mat) for ws in combinations(W,2))
  print(which,'test-distribution oracle minimum wrong adopts with two checks:',missed)
