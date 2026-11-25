"""Follow-up: compare sufficient paired and singleton data at 16 action audits."""
from pilot import make,N,costs,best,COST,DEFER,ACTIONS
samples={}
for world in ('redundant','complementary'):
    primary=[make(world,i,0) for i in range(N)]
    batches=[primary[:N//2],primary[N//2:]]
    sides=[(o,i%2,ar[i%2]) for i,(o,ar) in enumerate(primary)]
    samples[world]=sorted(sides)
    print(world,'single outcome audits',len(sides))
    for p in batches:
        expected=[sum(costs(*ar)[i] for _,ar in p)/len(p) for i in range(3)]
        print('paired audits',2*len(p),'selected',ACTIONS[best(expected)])
assert samples["redundant"]==samples["complementary"]
