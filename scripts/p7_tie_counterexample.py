"""Independent counterexample for omitted tie breaking, using saved SQL only."""
import re,sqlite3,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent.utils import read_json,write_json
RUN=ROOT/'runs_ext_p7_response'
rows=[r for r in read_json(RUN/'sql_counterfactual.json')['details'] if r['original_execution_correct'] and not r['arguments_exact']]
results=[]
for r in rows:
    threshold=float(re.search(r'score > (\d+)',r['expected_sql']).group(1))
    with sqlite3.connect(':memory:') as c:
        for tab in ['p6h_people','p6h_stock','p6h_rates']:
            c.execute(f'CREATE TABLE {tab}(id INTEGER PRIMARY KEY,name TEXT,score REAL)')
            c.executemany(f'INSERT INTO {tab} VALUES(?,?,?)',[(i,f'tie_{i}',threshold+10) for i in range(1,7)])
            c.execute(f'CREATE INDEX idx_{tab} ON {tab}(score DESC,id DESC)')
        c.execute('PRAGMA query_only=ON')
        want=c.execute(r['expected_sql']).fetchall();got=c.execute(r['predicted_sql']).fetchall()
    results.append({'branch':r['branch'],'id':r['id'],'expected':want,'predicted':got,'counterexample':want!=got})
out={'tested':len(results),'failed_tie_semantics':sum(r['counterexample'] for r in results),'all_scores_satisfy_where':True,'method':'Equal scores, source INTEGER PRIMARY KEY schema, legal secondary index(score DESC,id DESC). Isolates omission of ORDER BY id ASC from omission of WHERE.','results':results}
write_json(RUN/'sql_tie_counterexample.json',out)
print(json.dumps({k:v for k,v in out.items() if k!='results'}))
