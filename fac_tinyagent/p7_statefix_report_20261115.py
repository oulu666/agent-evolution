"""Read completed repaired measurements only; never starts GPU."""
from pathlib import Path
import json,statistics,runpy,time
from .p7_statefix_20261115 import ROOT,RUN,SEEDS,SKILLS,verify
from .utils import read_json,read_jsonl,write_json

def finalize():
 verify();assert all((RUN/f'seed{s}/complete.json').exists() for s in SEEDS)
 ns=runpy.run_path(str(ROOT/'scripts/p7_analyze_statefix_20261115.py'));ns['analyze']()
 a=read_json(RUN/'analysis.json');assert a['complete'];mean=statistics.mean
 macro=lambda sc:mean(v['joint_success'] for v in sc.values())
 table={key:{s:macro(sd['baseline'] if key=='baseline' else sd['background_scores'] if key=='background' else sd['actions'][f'{key}_2']['scores']) for s,sd in a['seeds'].items()} for key in ['baseline','background',*SKILLS]}
 gain={k:{split:mean(sd['actions'][f'{k}_2'][split]['nll']['gain_vs_background'] for sd in a['seeds'].values()) for split in ['dev','check']} for k in SKILLS}
 cross={s:{k:r['check']['nll']['by_skill_gain_vs_background'] for k,r in sd['actions'].items() if r['dose']==2} for s,sd in a['seeds'].items()}
 costs={str(s):read_json(RUN/f'seed{s}/complete.json') for s in SEEDS}
 newly=sum(v['costs']['optimizer_steps'] for s,v in costs.items() if int(s)!=20261108)
 assert newly==18
 results=[r for p in RUN.glob('seed*/*_2/*/results.jsonl') for r in read_jsonl(p)]
 baseline=[r for p in RUN.glob('seed*/baseline/*/results.jsonl') for r in read_jsonl(p)]
 assert len(results)==120 and len(baseline)==24
 choices={s:sd['choices'] for s,sd in a['seeds'].items()}
 out={'complete':True,'finished':time.strftime('%F %T %z'),'seeds':3,'paired_actions':15,'logical_optimizer_steps':30,'new_optimizer_steps':18,'reused_logical_steps':12,'known_discarded_or_failed_reconstruction_steps':3,'minimum_physical_optimizer_steps_including_old_work':33,'generation_episodes':144,'joint_macro':table,'mean_joint_macro':{k:mean(v.values()) for k,v in table.items()},'mean_NLL_gain_vs_background':gain,'choices':choices,'cross_skill_check_NLL_gain':cross,'costs':costs,'exact_state_bindings':len(list(RUN.glob('seed*/*/state_binding.json'))),'old_partial_reused':False}
 write_json(RUN/'summary.json',out)
 lines=['# P7精确状态恢复修复版实验报告',f'完成：{out["finished"]}（北京时间）。3/3种子、15/15配对、144题B1完整。','旧中断与重建失败产物只读保留；本版本没有使旧重建hash校验通过，而是重新运行受影响完整配对并精确落盘绑定其状态。','## 严格Joint宏平均（8题，非144独立题）','|状态|08|09|10|均值|','|---|---|---|---|---|']
 for k,v in table.items():lines.append('|'+k+'|'+'|'.join(f'{x:.3%}' for x in [*v.values(),mean(v.values())])+'|')
 lines+=['## 相对背景的NLL收益（正数为改善）',json.dumps(gain,ensure_ascii=False,indent=2),'## 排序检验',json.dumps(choices,ensure_ascii=False,indent=2),'## 逐技能与跨技能','analysis.json包含各动作/剂量的dev/check tool/final NLL及逐技能严格Joint；summary.json保留跨技能check损失收益矩阵。负值是代价，不包装为恢复。','## 原始错误审计来源']
 audit=RUN/'audit.json'
 if audit.exists():
  au=read_json(audit);lines += [f'复用CPU审计：评分重算{au.get("scoring_rows_checked")}条，gold核验{au.get("gold_checks")}题，评分不一致{au.get("scoring_mismatches")}。',json.dumps(au.get('counts'),ensure_ascii=False,indent=2)]
 lines+=['## 成本与方法结论','逻辑30次诊断更新；本次新增18，复用12；另有已知旧中断/失败重建至少3次，累计物理更新至少33。旧中断未输出的生成token不可精确追溯，未记为零。新exact state binding数量：'+str(out['exact_state_bindings'])+'。','仅dev收益/token进入选择，check不进入选择器。NLL响应和严格Joint并非同义，须分别查看；排序相关只作三个种子的描述性诊断，不是长期EAAR已胜出，也不是在线部署。','恢复工程补充：P7_STATEFIX_AMEND_20261115_ZH.md。全部输入沿用原冻结协议，不按check结果改策略，不启动P8。']
 (ROOT/'EXT_REPORT_20261115_p7_statefix_ZH.md').write_text('\n\n'.join(lines)+'\n')
 (ROOT/'EXT_HANDOVER_20261115_p7_statefix_ZH.md').write_text('本轮修复结果目录：runs_ext_p7_statefix_20261115。完成标志P7 STATEFIX QUEUE COMPLETE + CPU REPORT COMPLETE + END queue rc=0；summary.complete=true，3/3、15/15、144题。\n监测logs/status.log、queue.log、STOP。安全STOP不得自动删除或恢复。\nCPU收尾：PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B -m fac_tinyagent.p7_statefix_report_20261115\n本报告替代旧报告的结果汇总用途，但不覆盖旧文件。无下一轮自动执行。\n')
 (ROOT/'P7_STATEFIX_CORE_ALGORITHM_20261115_ZH.md').write_text('状态S=(可训练参数,optimizer,scaler,RNG,模式)。每动作恢复同一前缀，执行d=1/2次[7 Calendar+1 replay]实际更新。保存完整可恢复状态并严格hash往返后，测dev与check；测量后恢复该状态。\nV_k(d)=[L_dev(background_d)-L_dev(action_k_d)]/实际replay输入token；只以dev选择argmax，check仅验证。四技能宏平均包含跨技能损害，另输出矩阵。\n本轮验证短程响应代理，不把NLL收益等同严格Joint，也不声称在线自适应已成功。\n')
 print('P7 STATEFIX CPU REPORT COMPLETE',out['finished'],flush=True)
if __name__=='__main__':finalize()
