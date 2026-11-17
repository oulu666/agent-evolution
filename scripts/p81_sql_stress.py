"""Post-hoc CPU semantic stress test of generated SQL, no new model calls.

Names in the original probes encode id. Remove that correlation, vary scores,
and include threshold boundaries to distinguish correct execution from a rule.
Original P81 metrics remain unchanged.
"""
import json,sqlite3,tempfile,sys,collections,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent.utils import read_jsonl,write_json
from fac_tinyagent.p81_semantics import semantic_sql_result
DATA=ROOT/'data_ext_p81_diagnosis_20261116';RUN=ROOT/'runs_ext_p81_diagnosis_20261116'
gold={r['episode_id']:r for r in read_jsonl(DATA/'sql.jsonl')}
details=[]
with tempfile.TemporaryDirectory(prefix='p81_sql_stress_') as temp:
    dbs=[]
    for variant in range(3):
        p=Path(temp)/f'{variant}.sqlite';dbs.append(p)
        with sqlite3.connect(p) as c:
            for ti,tab in enumerate(['p81_zero','p81_few','p81_ties']):
                c.execute(f'CREATE TABLE {tab}(id INTEGER PRIMARY KEY,name TEXT,score REAL)')
                names=['zeta','beta','omega','alpha','theta','delta']
                scores=([20+i if ti==0 else 80 if ti==2 or i in [2,5] else 20+i for i in range(1,7)] if variant==0 else [72,34,88,49,65,51] if variant==1 else [50,51,49,50,90,90])
                c.executemany(f'INSERT INTO {tab} VALUES (?,?,?)',[(i,f'{names[i-1]}_{ti}',scores[i-1]) for i in range(1,7)])
                c.execute(f'CREATE INDEX idx_{tab} ON {tab}(score DESC,id DESC)')
    for path in sorted(RUN.glob('seed*_decision.jsonl')):
        for r in read_jsonl(path):
            if r['kind']!='sql':continue
            expected=gold[r['episode_id']];q=r['predicted_arguments'].get('sql','');passes=[]
            for db in dbs:
                with sqlite3.connect(db) as c:
                    c.execute('PRAGMA query_only=ON')
                    try:
                        cur=c.execute(q);obj={'ok':True,'result':{'columns':[d[0] for d in cur.description],'rows':[list(x) for x in cur.fetchall()]}}
                    except (sqlite3.Error,TypeError):obj={'ok':False}
                passes.append(semantic_sql_result(expected,obj,db))
            details.append({'seed':r['seed'],'id':r['episode_id'],'wording':r['meta']['wording'],'operation':r['meta']['operation'],'original_semantic':r['semantic_execution'],'variants':passes,'robust':r['tool_correct'] and r['semantic_execution'] and all(passes),'sql':q})
cells={}
for seed in [20261108,20261109,20261110]:
    for wording in ['natural','structured']:
        for operation in ['sort','filter','filter_sort','filter_sort_tie']:
            rs=[r for r in details if r['seed']==seed and r['wording']==wording and r['operation']==operation]
            cells[f'{seed}/{wording}/{operation}']={'n':len(rs),'robust_rate':statistics.mean(r['robust'] for r in rs) if rs else None}
write_json(RUN/'sql_stress.json',{'posthoc':True,'changes_original_metrics':False,'model_calls':0,'variants_per_query':3,'n_queries':len(details),'cells':cells,'details':details})
print(json.dumps(cells,indent=2))
