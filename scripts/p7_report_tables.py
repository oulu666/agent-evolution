"""Make auditable report tables only after all bounded P7 work completes."""
import collections,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent.utils import read_json,read_jsonl,write_json,sha256_file
from fac_tinyagent.p7_response import RUN,DATA,SKILLS,SEEDS,verify

def main():
    a=read_json(RUN/'analysis.json');assert a['complete'];verify()
    lines=['# P7 实验数字明细','', '所有 NLL 增益为正表示优于同更新数背景控制；Joint 是严格端到端成功。每技能仅2道新响应题，因此同一种子宏Joint每题影响12.5个百分点。','',
           '## 0 / 2 次更新的响应验证集 Joint','', '|种子|起点|背景|list_tables|filter_cmp_top|search_last|median|','|---|---|---|---|---|---|---|']
    macro=lambda scores:statistics.mean(v['joint_success'] for v in scores.values())
    for s,sd in a['seeds'].items():
        vals=[macro(sd['baseline']),macro(sd['background_scores'])]+[macro(sd['actions'][f'{k}_2']['scores']) for k in SKILLS]
        lines.append('|'+s+'|'+'|'.join(f'{v:.1%}' for v in vals)+'|')
    lines += ['', '## 两次更新：逐种子真实收益与线性预测','', '|种子|动作|Replay tokens|dev宏NLL收益vs背景|check宏NLL收益vs背景|check每千token收益|起点→动作dev实际下降|实际Adam位移一阶预测下降|','|---|---|---|---|---|---|---|---|']
    for s,sd in a['seeds'].items():
        for k in SKILLS:
            r=sd['actions'][f'{k}_2'];v=[r['dev']['nll']['gain_vs_background'],r['check']['nll']['gain_vs_background'],r['check_gain_per_1k_tokens'],r['dev']['nll']['absolute_drop'],r['receipt']['linear_predicted_dev_drop']]
            lines.append(f'|{s}|{k}|{r["receipt"]["replay_input_tokens"]}|'+ '|'.join(f'{x:+.6f}' for x in v)+'|')
    lines += ['', '## 预注册两种剂量的选择排序','', '|种子|更新数|P6 B/token选择|实测dev收益/token选择|check事后最优|P6→check Spearman|实测dev→check Spearman|梯度范数→check Spearman|','|---|---|---|---|---|---|---|---|']
    for s,sd in a['seeds'].items():
        for dose,c in sd['choices'].items():
            lines.append(f'|{s}|{dose}|{c["p6_proxy"]}|{c["measured_dev"]}|{c["check_oracle"]}|{c["spearman_proxy_to_check"]}|{c["spearman_dev_to_check"]}|{c["spearman_norm_to_check"]}|')
    lines += ['', '## 两次更新的跨技能响应矩阵（3种子均值）','', '单元格：check目标技能NLL相对背景的减少量。负数表示该技能受损。','', '|复习动作|'+'|'.join(SKILLS)+'|','|---|'+'---|'*4]
    matrix={}
    for k in SKILLS:
        matrix[k]={j:statistics.mean(sd['actions'][f'{k}_2']['check']['nll']['by_skill_gain_vs_background'][j] for sd in a['seeds'].values()) for j in SKILLS}
        lines.append('|'+k+'|'+'|'.join(f'{v:+.6f}' for v in matrix[k].values())+'|')
    lines += ['', '## 分阶段损失响应（3种子均值，两次更新）','', '|动作|dev tool|dev final|check tool|check final|','|---|---|---|---|---|']
    for k in SKILLS:
        vals=[statistics.mean(sd['actions'][f'{k}_2'][split][field]['gain_vs_background'] for sd in a['seeds'].values()) for split in ['dev','check'] for field in ['tool_nll','final_nll']]
        lines.append('|'+k+'|'+'|'.join(f'{x:+.6f}' for x in vals)+'|')
    costs=collections.Counter();seconds=0
    for sd in a['seeds'].values():costs.update(sd['cost']['costs']);seconds+=sd['cost']['seconds']
    assert costs['optimizer_steps']==30 and costs['generation_episodes']==144 and costs['training_backward']==240 and costs['nll_forward']==792
    generations=[r for p in RUN.glob('seed*/*/*/results.jsonl') for r in read_jsonl(p)]
    assert len(generations)==144
    gold={r['episode_id']:r for r in read_jsonl(DATA/'check.jsonl')}
    symptoms={k:collections.Counter() for k in SKILLS}
    from fac_tinyagent.metrics import answers_equal,joint_success
    from fac_tinyagent.sft.evaluate import parse_final_answer
    for r in generations:
        k=r['skill_labels'][0];c=symptoms[k];c['n']+=1
        parsed,pred=parse_final_answer(r['answer_raw'])
        assert bool(parsed and answers_equal(gold[r['episode_id']]['expected_final_answer'],pred))==r['final_correct']
        assert joint_success(r)==r['joint_success']
        for key in ['tool_correct','arguments_correct','execution_success','final_correct','joint_success']:c[key]+=int(r[key])
        c['predicted_tool:'+str(r['predicted_tool'])]+=1
        if k==SKILLS[0]:c['extraneous_arguments']+=int(bool(r['predicted_arguments']))
        if k==SKILLS[2]:c['answers_first_match']+=int(pred==json.loads(gold[r['episode_id']]['expected_observation'])['result'][0]['text'])
    write_json(RUN/'generation_audit.json',symptoms)
    costs['generation_calls']=sum(r['inference_calls'] for r in generations)
    costs['generation_input_tokens']=sum(r['input_tokens'] for r in generations)
    costs['generation_output_tokens']=sum(r['output_tokens'] for r in generations)
    costs['generation_seconds']=sum(r['generation_seconds'] for r in generations)
    costs['recorded_seed_seconds']=seconds
    costs['total_optimizer_steps_including_reconstruction']=costs['optimizer_steps']+costs.get('reconstruction_optimizer_steps',0)
    costs['total_training_backward_including_reconstruction']=costs['training_backward']+costs.get('reconstruction_training_backward',0)
    costs['total_training_input_tokens_including_reconstruction']=costs['training_input_tokens']+costs.get('reconstruction_input_tokens',0)
    write_json(RUN/'costs.json',costs)
    write_json(RUN/'cross_skill_response.json',matrix)
    lines+=['','## 成本','', '```json',json.dumps(costs,ensure_ascii=False,indent=2),'```','', 'optimizer_steps为实验逻辑更新数，reconstruction_optimizer_steps是游戏中断后的额外确定性重建，两者相加才是实际更新计算。recorded_seed_seconds不包括第二种子中断前耗时、模型加载和游戏等待，不可当总墙钟。被中断且未写出的生成token未能完整计量，不计作零。','', '全部原始数据在 runs_ext_p7_response/seed*/；算法选择记录在 dev_selection_1/2.json。']
    (RUN/'TABLES_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Final input/output inventory for repeatable CPU analysis; no new training.
    files=[p for p in RUN.rglob('*') if p.is_file() and p.suffix in ['.json','.jsonl','.md'] and p.name!='final_manifest.json']
    files += [ROOT/'scripts/p7_analyze.py',ROOT/'scripts/p7_report_tables.py',ROOT/'fac_tinyagent/p7_allocator.py',ROOT/'scripts/test_p7_allocator.py',ROOT/'scripts/run_p7_response_20261115.py']
    files += [p for p in [ROOT/'fac_tinyagent/p7_resume.py',ROOT/'scripts/p7_prepare_resume.py',ROOT/'scripts/run_p7_resume_20261115.py',ROOT/'scripts/launch_p7_authorized_resume.py'] if p.exists()]
    write_json(RUN/'final_manifest.json',{'complete':True,'frozen_inputs_verified':True,'files':{str(p.relative_to(ROOT)):sha256_file(p) for p in files}})
    print('\n'.join(lines))

if __name__=='__main__':main()
