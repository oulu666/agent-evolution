"""Post-pilot equal-memory engineering comparator; does not modify frozen pilot."""
from itertools import permutations
from pilot import NAMES, prepare, execute
# A single bit records whether a permitted anchor was seen. When no anchor
# is seen, choose the fallback name. This is a true two-state automaton.
for task in ('pairwise_trap','all_nonempty'):
    hist=prepare(task); best=[]
    for anchor,fallback in permutations(NAMES,2):
        rows=[]
        for h in hist:
            flag=False
            for e in h: flag=flag or e==anchor
            a=anchor if flag else fallback
            rows.extend(execute(h,a,100+i,200+i)[1] for i in range(12))
        best.append((sum(rows),anchor,fallback,len(rows)))
    print(task,max(best))
