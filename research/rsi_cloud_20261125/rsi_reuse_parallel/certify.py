from fractions import Fraction
from pilot import REGIMES, N, discover, oracle, render
cases=m=overlap=0
for reg in REGIMES:
 for seed in range(N):
  src,test=discover(seed,reg); keys={row[:5] for row in src}
  for row in test:overlap+=row[:5] in keys
  for x,k,f,_c,_t,_i in src+test:
   candidates=set()
   for i in range(7):
    actual=Fraction(render(x,k,i,f)); want=oracle(x,k,i)
    assert actual==want,(x,k,i,actual,want)
    m+=1;candidates.add(actual)
   assert len(candidates)<=2
   cases+=1
print(f'{cases} observations, {m} independent rounding/readback checks, {overlap} exact cache key hits; at most two distinct outputs per observation.')
