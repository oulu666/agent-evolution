"""Validate authored tests on the 2021 documentation tags, lock schedules, then release the envelope."""
from collections import defaultdict
from datetime import datetime,timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import random
from statistics import median
import subprocess
import sys
import tempfile
from time import perf_counter_ns
from zipfile import ZipFile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from issre_blind_frame import OUT,PROJECTS,git,persist
from issre_blind_tasks import tasks,RUN,observe,raw_channel
from issre_blind_schedule import key,subsets,schedule,METHODS

DOCS={'click':['docs/options.rst','docs/arguments.rst','docs/documentation.rst','docs/commands.rst'],
      'markdown':['docs/reference.md','docs/extensions/tables.md','docs/extensions/fenced_code_blocks.md',
                  'docs/extensions/toc.md','docs/extensions/footnotes.md'],'tqdm':['README.rst']}
FILES=['issre_blind_frame.py','issre_blind_tasks.py','issre_blind_schedule.py','issre_blind_run.py','ISSRE_BLIND_PROTOCOL_20261124.md']


def digest(path): return sha256(path.read_bytes()).hexdigest()


def worker(p,directory):
    sys.path[:0]=[str(directory/'src'),str(directory)]
    module=__import__(p)
    assert Path(module.__file__).resolve().is_relative_to(directory)
    out={}
    for t in tasks(p):
        def execute():
            try: return RUN[p](t.name)
            except Exception as exc:return {'error':type(exc).__name__}
        execute()  # exclude lazy imports; fresh state on each measured trial
        runs=[]
        phases=defaultdict(list)
        obs_times=defaultdict(list)
        actual={}
        orders=subsets(t)
        rng=random.Random(614+t.calls)
        for rep in range(11):
            a0=perf_counter_ns()
            artifact=execute()
            runs.append(perf_counter_ns()-a0)
            for phase,val in artifact.get('phase_ns',{}).items(): phases[phase].append(val)
            rng.shuffle(orders)
            for fields in orders:
                a=dict(artifact)
                start=perf_counter_ns()
                vals={}
                for f in fields:
                    try: vals[f]=observe(p,t.name,a,f)
                    except Exception as exc: vals[f]={'observer_error':type(exc).__name__}
                verdict=all(vals[f]==t.expected[f] for f in fields)
                obs_times[key(fields)].append(perf_counter_ns()-start)
                if len(fields)==len(t.expected):
                    if actual and actual!=vals: raise ValueError('unstable observer '+t.name)
                    actual=vals
        out[t.name]=dict(values=actual,expected=t.expected,calls=t.calls,raw=raw_channel(p,artifact),
            run=median(runs),phases={k:median(v) for k,v in phases.items()},
            obs={k:median(v) for k,v in obs_times.items()})
    return out


def replay(p,revision):
    pkg='src/click' if p=='click' else p
    raw=git(p,'archive','--format=zip',revision,pkg)
    with tempfile.TemporaryDirectory() as tmp:
        with ZipFile(BytesIO(raw)) as z:z.extractall(tmp)
        proc=subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'worker',p,tmp],
                   capture_output=True,text=True,encoding='utf8',timeout=120)
        if proc.returncode:raise RuntimeError(proc.stderr[-900:])
        return json.loads(proc.stdout)


def freeze():
    assert not (OUT/'freeze.json').exists(),'use the preserved frozen schedules'
    data={}
    plans={}
    for p,(_,tag,_) in PROJECTS.items():
        data[p]=replay(p,tag)
        errors=[(n,row['values'],row['expected']) for n,row in data[p].items() if row['values']!=row['expected']]
        if errors:raise ValueError((p,errors))
        plans[p]={}
        for regime in ('calls','time_and_calls'):
            group={}
            for method in METHODS:
                sel,cap=schedule(p,tasks(p),data[p],method,regime)
                group[method]=dict(inputs=sel,cap_ns=None if cap==float('inf') else cap)
            plans[p][regime]=group
    persist(OUT/'development_timings.json',data)
    persist(OUT/'schedules.json',plans)
    paths=[HERE/n for n in FILES]+[OUT/n for n in ('sealed_frame.json','development_timings.json','schedules.json')]
    persist(OUT/'freeze.json',dict(time_utc=datetime.now(timezone.utc).isoformat(),
         files={q.name:digest(q) for q in paths},docs={p:{n:sha256(git(p,'show',f'{PROJECTS[p][1]}:{n}')).hexdigest()
         for n in DOCS[p]} for p in PROJECTS}))
    print('locked',digest(OUT/'freeze.json'))


def run():
    lock=json.loads((OUT/'freeze.json').read_text(encoding='utf8'))
    for name,h in lock['files'].items():
        assert digest((HERE if name in FILES else OUT)/name)==h
    sealed=json.loads((OUT/'sealed_frame.json').read_text(encoding='utf8'))
    out=[]
    for p,group in sealed.items():
        for i,c in enumerate(group['selected'],1):
            row=dict(project=p,id=i,commit=c['commit'],parent=c['parent'])
            for which in ('parent','commit'):
                try:row[which+'_rows']=replay(p,c[which])
                except (subprocess.SubprocessError,RuntimeError) as exc:row[which+'_error']=str(exc)
            out.append(row)
    persist(OUT/'paired.json',out)
    print('completed pairs',len(out))


if __name__=='__main__':
    if sys.argv[1]=='worker': print(json.dumps(worker(sys.argv[2],Path(sys.argv[3]))))
    elif sys.argv[1]=='freeze': freeze()
    elif sys.argv[1]=='run': run()
