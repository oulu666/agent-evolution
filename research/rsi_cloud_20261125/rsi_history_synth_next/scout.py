"""Run real Click versions behind separate interpreters. No third-party dependencies other than versioned workers."""
from collections import Counter
from itertools import permutations
from pathlib import Path
import json
import random
import subprocess
import sys

VERSIONS = ('8.3.3', '8.4.0')
TASKS = ('feature_default', 'config_pair')
BUDGET = 2

def worker(version, root):
    import os
    sys.path.insert(0, root)
    import click
    from importlib.metadata import version as installed
    from click.testing import CliRunner
    assert installed('click') == version and Path(click.__file__).is_relative_to(root), click.__file__
    assert not os.environ.get('RSI_SCOUT_POINT')
    runner = CliRunner()
    for request in json.load(sys.stdin):
        task, i, probe = request
        if task == TASKS[0]:
            keys = [f'compact{i}', f'detail{i}', f'wide{i}']
            rotate, flags = probe
            options = [click.Option([f'--{name}', 'mode'], flag_value=name,
                                    **({'default': True} if k == 0 else {}))
                       for k, name in enumerate(keys)]
            result = runner.invoke(click.Command('report', params=options[rotate:] + options[:rotate],
                                                 callback=lambda mode: click.echo(mode)),
                                   [f'--{keys[k]}' for k in flags])
        else:
            medium, j = probe
            a,b=coords(i,j)
            option = click.Option(['--point'], nargs=2, type=int, envvar='RSI_SCOUT_POINT')
            cmd = click.Command('record', params=[option],
                                callback=lambda point: click.echo(json.dumps(point)))
            args,kw=[],{}
            if medium=='cli': args=['--point',str(a),str(b)]
            if medium=='env': kw['env']={'RSI_SCOUT_POINT':f'{a} {b}'}
            if medium=='map_tuple': kw['default_map']={'point':(a,b)}
            if medium=='map_string': kw['default_map']={'point':f'{a} {b}'}
            if medium=='map_tabs': kw['default_map']={'point':f'\t{a}\t {b}  '}
            result = runner.invoke(cmd,args,**kw)
        print(json.dumps(dict(exit=result.exit_code, output=result.output.strip(),
                              error=type(result.exception).__name__ if result.exception else None)))

def coords(i,j):
    return (2*i+1+j, 61-i+2*j)

def oracle(task, i, probe):
    # App-level expected semantic value, no imports of or comparisons to a "correct" release.
    if task == TASKS[0]:
        _, flags=probe
        return ['compact','detail','wide'][flags[-1] if flags else 0] + str(i)
    return list(coords(i,probe[1]))

def passes(task, expected, actual):
    if actual['exit']!=0:return False
    return (actual['output'] if task==TASKS[0] else json.loads(actual['output']))==expected

def menus(task):
    if task == TASKS[0]:
        cli=[(),(0,),(1,),(2,),*permutations(range(3),2)]
        fixed=[(0,a) for a in cli]
        new=[(rotation,a) for a in cli for rotation in (1,2)]
        expert=[(1,())]
        directed=[(1,()),(2,()),*new,*fixed]
        expand=[fixed[0],(1,(0,)),*new,*fixed]
    else:
        fixed=[(m,k) for k in range(4) for m in ('cli','env','map_tuple')]
        new=[(m,k) for k in range(4) for m in ('map_string','map_tabs')]
        expert=[('map_string',0)]
        directed=[('map_string',0),('map_tabs',0),*new,*fixed]
        # Generic channel-first diversification uses the registered channel order.
        expand=[fixed[0],fixed[1],*new,*fixed]
    return {k:list(dict.fromkeys(v)) for k,v in dict(
        fixed=fixed, expand=expand, equivalent=directed, expert=expert,
        fixed_exhaustive=fixed, grammar_exhaustive=fixed+new).items()}

def main(root):
    cases = [(task,i,p) for task in TASKS for i in range(12)
             for p in menus(task)['grammar_exhaustive']]
    outcomes={}
    for label in ('old_a','new_a','old_b','new_b'):
        version = VERSIONS[label.startswith('new')]
        path=(root/f'click-{version}').resolve()
        cmd=[sys.executable,'-I',str(Path(__file__).resolve()),'--worker',version,str(path)]
        p=subprocess.run(cmd,input=json.dumps(cases),text=True,capture_output=True,check=True)
        rows=[json.loads(s) for s in p.stdout.splitlines()]
        assert len(rows)==len(cases)
        outcomes[label]=dict(zip(cases,rows,strict=True))
    report={}
    for task in TASKS:
        r=report[task]={'fixture_replicates':12}
        candidates = menus(task)
        for key,menu in {**candidates, 'uniform_grammar': candidates['grammar_exhaustive']}.items():
            result=Counter(tested=0,hits=0,old_old=0,new_new=0)
            for i in range(12):
                hit=hit_old_control=hit_new_control=False
                if key=='uniform_grammar':
                    menu=menu.copy()
                    random.Random(7125+i).shuffle(menu)
                for probe in (menu if key.endswith('exhaustive') else menu[:BUDGET]):
                    case=(task,i,probe)
                    expected=oracle(*case)
                    old,new,old_b,new_b=[outcomes[v][case] for v in outcomes]
                    po,pn=passes(task,expected,old),passes(task,expected,new)
                    hit_old_control |= not po and passes(task,expected,old_b)
                    hit_new_control |= not pn and passes(task,expected,new_b)
                    result['tested']+=1
                    if not po and pn:
                        hit=True
                        r.setdefault('example',dict(i=i,probe=probe,expected=expected,old=old,new=new))
                        if not key.endswith('exhaustive'):break
                result['hits']+=hit
                result['old_old']+=hit_old_control
                result['new_new']+=hit_new_control
            result['library_calls']=result['tested']*2
            r[key]=dict(result)
        for version,label in zip(VERSIONS,('old_a','new_a')):
            ds=[c for c in cases if c[0]==task]
            r[f'{version}_oracle_conformant']=sum(passes(task,oracle(*c),outcomes[label][c]) for c in ds)
            r['full_grammar_rows']=len(ds)
    print(json.dumps(dict(versions=VERSIONS,budget=BUDGET,results=report),sort_keys=True,indent=2))

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker': worker(*sys.argv[2:])
    else:main(Path(sys.argv[1]))
