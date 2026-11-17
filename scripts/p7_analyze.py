"""CPU-only analysis of frozen P7 and archived P6 outputs."""
import collections, json, math, re, sqlite3, statistics, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fac_tinyagent.utils import read_json,read_jsonl,write_json
from fac_tinyagent.p7_response import RUN,DATA,SEEDS,SKILLS

def sql_audit():
    from fac_tinyagent.sft.evaluate import _evaluate_tool_prediction
    gold={r['episode_id']:r for r in read_jsonl(ROOT/'data_ext_p6_devplan/holdout/rows.jsonl')}
    details=[];counts=collections.Counter();arm_scores=collections.defaultdict(list)
    for path in sorted((ROOT/'runs_ext_p6_devplan_attempt2/evaluation').glob('*/p6_*/results.jsonl')):
        branch=path.parts[-3]
        for r in read_jsonl(path):
            rerun=_evaluate_tool_prediction(gold[r['episode_id']],r['tool_call_raw'],str(ROOT/'data_ext_p6_devplan/fixtures/holdout.sqlite'),str(ROOT/'data_phase2/fixtures/calendar.json'))
            for key in ['tool_correct','arguments_correct','execution_success']:
                assert rerun[key]==r[key],(path,r['episode_id'],key)
            arm_scores[branch].append({'strict':int(r['joint_success']),'execution_final':int(r['tool_correct'] and r['execution_success'] and r['final_correct'])})
            if 'db.filter_cmp_top' not in r['episode_id']:continue
            g=gold[r['episode_id']];expected=g['expected_arguments']['sql'];pred=r['predicted_arguments'].get('sql','')
            tab=re.search(r'FROM\s+(\w+)',expected,re.I).group(1)
            threshold=float(re.search(r'score > (\d+)',expected).group(1))
            probes={
                'none_qualify':[(i,f'below_{i}',threshold-i) for i in range(1,7)],
                'few_qualify':[(i,f'few_{i}',threshold+1 if i==1 else threshold-i) for i in range(1,7)],
                'ties':[(i,f'tie_{i}',threshold+10) for i in [6,5,4,3,2,1]],
            }
            outcomes={}
            for kind,rows in probes.items():
                with sqlite3.connect(':memory:') as c:
                    # Match source schema, including INTEGER PRIMARY KEY semantics.
                    for name in ['p6h_people','p6h_stock','p6h_rates']:
                        c.execute(f'CREATE TABLE {name}(id INTEGER PRIMARY KEY,name TEXT,score REAL)')
                        c.executemany(f'INSERT INTO {name} VALUES (?,?,?)',rows)
                    c.execute('PRAGMA query_only=ON')
                    try:
                        want=c.execute(expected).fetchall();got=c.execute(pred).fetchall()
                        outcomes[kind]={'same':want==got,'expected':want,'predicted':got}
                    except sqlite3.Error as e:outcomes[kind]={'same':False,'error':str(e)}
            item={'branch':branch,'id':r['episode_id'],'original_execution_correct':r['execution_success'],'arguments_exact':r['arguments_correct'],'expected_sql':expected,'predicted_sql':pred,'has_where':bool(re.search(r'\bWHERE\b',pred,re.I)),'has_id_tie':bool(re.search(r'\bid\s+ASC\b',pred,re.I)),'probes':outcomes}
            details.append(item);counts['n']+=1
            counts['exact']+=int(r['arguments_correct']);counts['original_execution_correct']+=int(r['execution_success'])
            if r['execution_success'] and not r['arguments_correct']:
                counts['execution_right_args_wrong']+=1
                counts['coincidental_result_counterexample']+=int(not all(o['same'] for o in outcomes.values()))
                counts['missing_where']+=int(not item['has_where'])
                counts['missing_tie']+=int(not item['has_id_tie'])
    out={'analysis_type':'Post-hoc CPU diagnostic, not a replacement P6 endpoint','predicted_calls_reexecuted':sum(map(len,arm_scores.values())),'counts':counts,'details':details,'branch_sensitivity':{k:{m:statistics.mean(r[m] for r in v) for m in ['strict','execution_final']} for k,v in arm_scores.items()}}
    write_json(RUN/'sql_counterfactual.json',out);print(json.dumps(out['counts']))

def avg(rows,field='nll',skill=None):return statistics.mean(r[field] for r in rows if skill is None or r['skill']==skill)
def ranks(values):return [1+sum(v<x for v in values)+(sum(v==x for v in values)-1)/2 for x in values]
def corr(x,y):
    if len(set(x))<2 or len(set(y))<2:return None
    return statistics.correlation(ranks(x),ranks(y))

def results(root):
    rs=[r for f in ['database','file','python'] for r in read_jsonl(root/f/'results.jsonl')]
    return {k:{m:statistics.mean(float(r[m]) for r in rs if k in r['skill_labels']) for m in ['joint_success','tool_correct','arguments_correct','execution_success','final_correct']} for k in SKILLS}

def analyze():
    from fac_tinyagent.p7_allocator import select_action
    output={'seeds':{},'complete':all((RUN/f'seed{s}/complete.json').exists() for s in SEEDS)}
    for s in SEEDS:
        root=RUN/f'seed{s}'
        if not (root/'complete.json').exists():continue
        base=read_json(root/'baseline/nll.json');base_scores=results(root/'baseline')
        old=read_json(ROOT/f'runs_ext_p6_devplan/calibration/A_seed{s}.json')
        meta=read_json(root/'action_meta.json');sd={'baseline':base_scores,'actions':{},'cost':read_json(root/'complete.json')}
        for dose in [1,2]:
            control=read_json(root/f'background_{dose}/nll.json')
            for k in SKILLS:
                path=root/f'{k}_{dose}';nll=read_json(path/'nll.json');receipt=read_json(path/'receipt.json')
                row={'dose':dose,'receipt':receipt,'p6_B':old['benefit'][k],'p6_norm':old['candidate_gradient_norm'][k],'actual_candidate':meta[k]}
                for split in ['dev','check']:
                    row[split]={field:{'absolute_drop':avg(base[split],field)-avg(nll[split],field),'gain_vs_background':avg(control[split],field)-avg(nll[split],field),'own_skill_gain_vs_background':avg(control[split],field,k)-avg(nll[split],field,k),'by_skill_gain_vs_background':{j:avg(control[split],field,j)-avg(nll[split],field,j) for j in SKILLS}} for field in ['nll','tool_nll','final_nll']}
                row['dev_gain_per_1k_tokens']=1000*row['dev']['nll']['gain_vs_background']/receipt['replay_input_tokens']
                row['check_gain_per_1k_tokens']=1000*row['check']['nll']['gain_vs_background']/receipt['replay_input_tokens']
                if dose==2:row['scores']=results(path)
                sd['actions'][f'{k}_{dose}']=row
        choices={}
        for dose in [1,2]:
            rows=[sd['actions'][f'{k}_{dose}'] for k in SKILLS]
            proxy=[old['benefit'][k]/sum(meta[k]['input_tokens'][:dose]) for k in SKILLS]
            devgain=[r['dev_gain_per_1k_tokens'] for r in rows];checkgain=[r['check_gain_per_1k_tokens'] for r in rows]
            choice={name:SKILLS[max(range(4),key=lambda i:vals[i])] for name,vals in [('p6_proxy',proxy),('measured_dev',devgain),('check_oracle',checkgain)]}
            choice.update({'spearman_proxy_to_check':corr(proxy,checkgain),'spearman_dev_to_check':corr(devgain,checkgain),'spearman_norm_to_check':corr([old['candidate_gradient_norm'][k] for k in SKILLS],checkgain),'check_gain_per_1k_tokens':dict(zip(SKILLS,checkgain))})
            choice['spearman_single_unit_gradient_to_check']=corr([meta[k]['single_unit_dot']/sum(meta[k]['input_tokens'][:dose]) for k in SKILLS],checkgain)
            choice['spearman_single_raw_gradient_to_check']=corr([meta[k]['single_raw_dot']/sum(meta[k]['input_tokens'][:dose]) for k in SKILLS],checkgain)
            selected=select_action(read_json(root/f'background_{dose}/nll.json')['dev'],{k:read_json(root/f'{k}_{dose}/nll.json')['dev'] for k in SKILLS},{k:sd['actions'][f'{k}_{dose}']['receipt']['replay_input_tokens'] for k in SKILLS})
            assert selected['action']==choice['measured_dev']
            write_json(root/f'dev_selection_{dose}.json',selected)
            choices[str(dose)]=choice
        sd['choices']=choices;sd['background_scores']=results(root/'background_2');output['seeds'][str(s)]=sd
    write_json(RUN/'analysis.json',output)
    print('complete',output['complete'])
    for seed,sd in output['seeds'].items():
        print(seed,json.dumps(sd['choices']))
        for key,r in sd['actions'].items():
            if r['dose']==2:print(key,'dev_gain',round(r['dev']['nll']['gain_vs_background'],5),'check_gain',round(r['check']['nll']['gain_vs_background'],5),'Joint',round(statistics.mean(x['joint_success'] for x in r['scores'].values()),3))

if __name__=='__main__':
    {'sql':sql_audit,'analyze':analyze}[sys.argv[1]]()
