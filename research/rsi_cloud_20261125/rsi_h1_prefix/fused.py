"""Strong same-information DAG check with a fused guard/projection."""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP, localcontext
from itertools import product
import json
from run import (FAMILIES, PREFS, fixture, checkpoint, load, to_input, output, project,
                 independent_check)

def guarded_projection(state):
    report=[]
    with localcontext() as c:
        c.prec=40
        for section,(n,total,missing) in state:
            if missing:return None
            floor,remainder=divmod(total,10*n)
            if remainder*2==10*n and floor%2==0:return None
            mean=(Decimal(total)/(100*n)).quantize(Decimal('0.1'),rounding=ROUND_HALF_UP)
            report.append((section,n,str(mean)))
    return tuple(report)

def run_fused(rows,answer):
    state=checkpoint(load(to_input(rows)))
    receipt=guarded_projection(state)
    early=output(receipt) if receipt is not None else None
    final=early if early is not None else output(project(state,answer))
    return early,final,dict(pre=3+int(early is not None),post=0 if early is not None else 2,
                            preliminary_projections=int(early is not None))

def main():
    result={}
    for split,ids in [('development',range(8)),('holdout',range(54,64))]:
        report=Counter()
        for f,i,answer in product(FAMILIES,ids,PREFS):
            rows=fixture(i,f)
            early,final,ctr=run_fused(rows,answer)
            safe=early is not None and all(independent_check(early,rows,p) for p in PREFS)
            report.update(ctr)
            report.update(cases=1,safe_early=safe,
                          unsafe_early=(early is not None and not safe),
                          final_correct=independent_check(final,rows,answer))
        report['total']=report['pre']+report['post']
        result[split]=report
    print(json.dumps(dict(fused_guard=result),sort_keys=True,indent=2))

if __name__=='__main__':main()
