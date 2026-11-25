"""Frozen documentation-clause coverage policies, with measured shared parsing costs."""
from itertools import combinations
from statistics import median

CALL_CAP=12
METHODS=('Input-only','Oracle-only','Sequential','Joint','Full-Oracle')
BASIC={'click':'exit','markdown':'text','tqdm':'counter'}


def subsets(t):
    fields=list(t.expected)[1:]
    return [('status',*v) for n in range(len(fields)+1) for v in combinations(fields,n)]


def key(fs):
    return '+'.join(fs)


def schedule(p,tasks,costs,m,regime):
    byname={t.name:t for t in tasks}
    cap=3*median(costs[t.name]['run']+costs[t.name]['obs'][key(tuple(t.expected))]
                 for t in tasks) if regime=='time_and_calls' else float('inf')
    def price(sel):
        return (sum(byname[n].calls for n in sel),
                sum(costs[n]['run']+costs[n]['obs'][key(fs)] for n,fs in sel.items()))
    def value(sel):
        return len({(f,c) for n,fields in sel.items() for f in fields for c in byname[n].relevant[f]})
    def feasible(sel):
        calls,ns=price(sel)
        return calls<=CALL_CAP and ns<=cap
    def weight(calls,ns):
        return calls/CALL_CAP+(ns/cap if cap!=float('inf') else 0)
    sel={}
    if m in ('Oracle-only','Sequential','Input-only'):
        pool=list(tasks)
        seen=set()
        while pool:
            feasible_inputs=[]
            for t in pool:
                fs=('status',BASIC[p]) if m=='Input-only' else ('status',)
                opt={**sel,t.name:fs}
                if feasible(opt):
                    gain=len(set(t.clauses)-seen)
                    base=price(sel)
                    cost=price(opt)
                    feasible_inputs.append((gain/weight(cost[0]-base[0],cost[1]-base[1]),t,opt))
                elif m=='Oracle-only':
                    break
            if not feasible_inputs: break
            _,choice,sel=feasible_inputs[0] if m=='Oracle-only' else max(feasible_inputs,key=lambda v:v[0])
            seen.update(choice.clauses)
            pool.remove(choice)
        if m=='Input-only': return sel,cap
    allowed=list(sel) if m in ('Oracle-only','Sequential') else list(byname)
    while True:
        best=None
        orig=price(sel)
        for n in allowed:
            t=byname[n]
            for fs in ([tuple(t.expected)] if m=='Full-Oracle' else subsets(t)):
                if n in sel and not set(sel[n])<set(fs):continue
                opt={**sel,n:fs}
                if not feasible(opt):continue
                gain=value(opt)-value(sel)
                if gain<=0:continue
                calls,ns=price(opt)
                marginal=max(1e-9,weight(calls-orig[0],max(ns-orig[1],0)))
                rank=(gain/marginal,gain,-ns)
                if best is None or rank>best[0]:best=(rank,opt)
        if best is None:break
        sel=best[1]
    return sel,cap
