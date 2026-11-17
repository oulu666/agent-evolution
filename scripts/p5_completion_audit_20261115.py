import json,statistics,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'runs_ext_p5_file_timing'
def j(p):return json.loads(p.read_text())
s=j(O/'summary.json');counts=0;trains=[]
for row in s['rows']:
 label=f'A_seed{row["seed"]}_{row["arm"]}'
 train=j(O/'branches'/label/'checkpoint/train_summary.json');meta=j(O/'branches'/label/'p5_meta.json')
 assert train['optimizer_steps']==meta['optimizer_steps']==23
 assert train['replay_input_tokens']==meta['replay_input_tokens']
 trains.append({'label':label,'steps':23,'tokens':train['replay_input_tokens']})
 for suite in ['natv2_file','p2_file','natv2_database','natv2_python','v3fix']:
  p=O/'evaluation'/label/suite;rep=j(p/'stage_report.json')
  assert rep['evaluation_protocol']['batch_size']==1
  assert j(p/'p5_meta.json')['protocol']=='Protocol-B1'
  rs=[json.loads(x) for x in (p/'results.jsonl').read_text().splitlines() if x]
  assert len(rs)==30
  assert abs(sum(bool(x['joint_success']) for x in rs)/30-row[suite]['joint_success'])<1e-12
  counts+=1
out={'time':time.strftime('%F %T %z'),'complete_suites_B1':counts,'completed_training':len(trains),'training':trains,'arm_scores':{}}
for arm in ['early','uniform','late']:
 rows=sorted([r for r in s['rows'] if r['arm']==arm],key=lambda r:r['seed'])
 out['arm_scores'][arm]={k:{'per_seed':[r[k]['joint_success'] for r in rows],'mean':statistics.mean(r[k]['joint_success'] for r in rows)} for k in ['natv2_file','p2_file','file_nontarget','natv2_database','natv2_python','v3fix']}
 # Separate phase2 target8, not the primary natural language test.
 target=[]
 for row in rows:
  p=O/'evaluation'/f'A_seed{row["seed"]}_{arm}'/'p2_file/results.jsonl'
  rs=[json.loads(x) for x in p.read_text().splitlines() if x]
  rs=[r for r in rs if 'file_last_match' in r['episode_id']];assert len(rs)==8
  target.append(sum(bool(r['joint_success']) for r in rs)/8)
 out['arm_scores'][arm]['phase2_search_last8']={'per_seed':target,'mean':statistics.mean(target)}
(O/'completion_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
