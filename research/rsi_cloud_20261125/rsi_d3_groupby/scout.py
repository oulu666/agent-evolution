from collections import Counter
from itertools import product
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import warnings


def fixtures():
    for k, order, req, fill in product((3,5,7), range(4), ('sparse','complete','subset'), ('partial','all')):
        labels=[f'category-{i+order*k}' for i in range(k)]
        seen=labels if fill=='all' else labels[::2]
        rows=[(g,(i+1)*(order+2)) for i,g in enumerate(seen)]
        rows+= [(seen[-1],11)]
        if order % 2: rows.reverse()
        roster=labels[1::2]
        yield k,order,req,fill,labels,rows,roster


def expected(s):
    _,_,req,_,labels,rows,roster=s
    sums=Counter()
    for g,value in rows:
        sums[g]+=value
    keys={'sparse':list(sums),'complete':labels,'subset':roster}[req]
    return [list(t) for t in sorted((g,sums[g]) for g in keys)]


def work():
    import pandas as pd
    warnings.filterwarnings('ignore', category=FutureWarning)
    fixtures_list=list(fixtures())
    calls=0
    def action(i,native):
        nonlocal calls
        calls+=1
        _,_,req,_,labels,rows,roster=fixtures_list[i]
        df=pd.DataFrame({'g':pd.Categorical([g for g,v in rows], categories=labels),
                         'v':[v for g,v in rows]})
        opts={'observed':req!='complete'} if native else {}
        res=df.groupby('g',**opts)['v'].sum()
        if native and req=='subset':
            res=res.reindex(roster,fill_value=0)
        return [list(t) for t in sorted((str(key),int(val)) for key,val in res.items())]
    for line in sys.stdin:
        items=json.loads(line)
        print(json.dumps({'version':pd.__version__,'outputs':[action(*item) for item in items],
                          'total_calls':calls}),flush=True)


class Backend:
    def __init__(self, path, version):
        env=os.environ.copy()
        if path: env['PYTHONPATH']=str(Path(path).resolve())
        self.version=version
        self.p=subprocess.Popen([sys.executable,'-B',__file__,'--work'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=env)
        self.calls=0
    def call(self,ix,native=False):
        if not ix: return []
        self.p.stdin.write(json.dumps([(i,native) for i in ix])+'\n')
        self.p.stdin.flush()
        out=json.loads(self.p.stdout.readline())
        self.calls+=len(ix)
        assert (out['version'],out['total_calls'])==(self.version,self.calls)
        return out['outputs']
    def close(self):
        self.p.stdin.close()
        assert self.p.wait(timeout=10)==0


def main(new):
    old=Backend(None,'2.2.3')
    fresh=Backend(new,'3.0.0')
    cases=list(fixtures()); ix=list(range(len(cases))); y=list(map(expected,cases))
    try:
        def exec_action(backend,indices,native=False):
            return {i:out==y[i] for i,out in zip(indices,backend.call(indices,native),strict=True)}
        a=exec_action(fresh,ix); r=exec_action(old,ix); n=exec_action(fresh,ix,True)
        an=exec_action(old,ix,True)
        summary={}
        for req in ('sparse','complete','subset','overall'):
            keys=[i for i in ix if req in (cases[i][2],'overall')]
            joint=Counter(f'{int(a[i])}{int(r[i])}' for i in keys)
            costs={'new':sum(not a[i] for i in keys),'old':sum(not r[i] for i in keys),
                   'verify':round(.35*(len(keys)+joint['00']),6)}
            summary[req]={'n':len(keys),'new':sum(a[i] for i in keys),'old':sum(r[i] for i in keys),
                          'native_new':sum(n[i] for i in keys),'native_old':sum(an[i] for i in keys),
                          'union':sum(a[i] or r[i] for i in keys),
                          'joint':dict(sorted(joint.items())),'diagnostic_deployment_cost':costs}
        for tag,first,second in [('new_first',fresh,old),('old_first',old,fresh)]:
            before=old.calls+fresh.calls
            x=exec_action(first,ix)
            z=exec_action(second,[i for i in ix if not x[i]])
            skipped=[i for i in ix if x[i]]
            assert all((not x[i] and not z[i])==(not a[i] and not r[i]) for i in ix)
            summary[tag]={'executed_checks':old.calls+fresh.calls-before,
                          'second_checks_skipped':len(skipped)}
        summary['full_pairs']={'executed_checks':2*len(ix)}
        print(json.dumps(summary,indent=2,sort_keys=True))
    finally:
        old.close(); fresh.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--work',action='store_true'); p.add_argument('--new')
    args=p.parse_args()
    if args.work: work()
    else:
        assert args.new
        main(args.new)
