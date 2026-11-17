"""Finalize P5 Chinese report/handover from frozen plans and actual result files; CPU only."""
import json,statistics,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fac_tinyagent import p5_file_timing as P

def main():
 P.verify(); P.summarize()
 summary=json.loads((P.RUNS/'summary.json').read_text());rows=summary['rows']
 complete=all(all(r[n] is not None for n in P.SUITES) for r in rows)
 now=time.strftime('%F %T %z')
 report=['# P5 实验报告：File固定经验集合的时机验证','',f'更新时间：{now}（北京时间）。状态：'+('9分支训练与B1评测齐全。' if complete else '尚未全部完成；不得把占位汇总当实验结论。'),'',
 '## 设计与证据边界','3臂×3种子；同种子同22条replay经验、同约7494 input token、同step80前缀及23总optimizer steps。只比较四条相同File target的调度。early/uniform/late不是自动技能分类器，也不是对广度或数量独立因果的检验。',
 'P4的数量推断和三类别解释作假说，不当作已经证实的规则；重新激活需用历史响应识别，不能只凭前后成绩预判。',
 '## 逐种子结果','|种子|臂|nat File joint|tool|args|final|Calendar joint|','|---|---|---|---|---|---|---|']
 for r in rows:
  v=r['natv2_file']; c=r['v3fix'];fmt=lambda v:'—' if v is None else f'{v:.3f}'
  report.append('|%s|%s|%s|%s|%s|%s|%s|'%(r['seed'],r['arm'],*[fmt(v[k] if v else None) for k in ['joint_success','tool_correct','arguments_correct','final_correct']],fmt(c['joint_success'] if c else None)))
 report+=['','## 配对主指标']
 for k,d in summary['paired_primary'].items():
  ds=d['per_seed']; valid=all(x is not None for x in ds)
  report.append('- '+k+'：'+(f'各种子{ds}；均值{statistics.mean(ds):+.3f}；样本SD {statistics.stdev(ds):.3f}；'+('方向一致。' if all(x>0 for x in ds) else '未达到三种子同正。') if valid else '未完成。'))
 if complete:
  mainpairs=[summary['paired_primary'][k] for k in ['early-uniform','early-late']]
  support=all(all(x>0 for x in d['per_seed']) and d['mean']>=.10 for d in mainpairs)
  report+=['','## 预注册判定', '支持本轮固定早插的可用优势。' if support else '没有完整达到“early同时优于uniform和late、三种子同正且均值各>=0.10”的预注册标准。不得泛化为自适应策略成功。']
  report+=['','## 副作用与代价']
  for s in P.SEEDS:
   early=next(r for r in rows if r['seed']==s and r['arm']=='early');uniform=next(r for r in rows if r['seed']==s and r['arm']=='uniform')
   for n in ['file_nontarget','natv2_database','natv2_python','v3fix']:
    delta=early[n]['joint_success']-uniform[n]['joint_success'];report.append(f'- {s} early−uniform {n}: {delta:+.3f}'+('，下降超过0.10。' if delta<-.10-1e-9 else '。'))
 report+=['','## 产物与范围','预注册：P5_PREREG_20261115_file_timing_ZH.md；冻结：data_ext_p5_file_timing/manifest.json；详细summary：runs_ext_p5_file_timing/summary.json / summary_tables_ZH.md。',
 '不做显著性主张；不自动启动下一轮，不根据测试反馈改这轮计划。']
 (ROOT/'EXT_REPORT_20261115_p5_ZH.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
 hand=['# P5 交接手册',f'更新时间：{now}（北京时间）。',f'状态：complete={complete}；未完成时请看logs，不要据此报告实验胜负。',
 '## 已冻结设计','见P5_PREREG_20261115_file_timing_ZH.md、P5_PLAN_READY_20261115_ZH.md及data_ext_p5_file_timing/manifest.json。',
 '## 启动（WSL项目根）','```bash','bash scripts/launch_p5_20261115.sh','```','启动前launcher调用监督器，检查r5apex、其它GPU进程、功耗>=60W。STOP粘性，检测游戏后只能经用户明确批准再恢复，不得自动删STOP。',
 '## 监测与停止','runs_ext_p5_file_timing/logs/status.log、queue.log、runner.pid、gpu_child.pid；CPU dry_run.json、preflight.json。写runs_ext_p5_file_timing/logs/STOP可以终止本轮，监督器10秒内处理。',
 '## CPU收尾','```bash','PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B scripts/finalize_p5_20261115.py','```','这会重算本轮summary并生成本报告与交接；不启动模型/GPU。',
 '## 资产边界','只新增P5文件；前缀直接只读复用runs_ext_e4/prefixes，加载路径已核对为只读。旧data/runs/冻结卷/环境一律不改。新模型adapter和训练日志在runs_ext_p5_file_timing/branches，新B1结果在evaluation。',
 '## 未自动做','未给GPT发送材料；没有teacher/RL/多智能体；没有更大模型；完成后不启动P6。']
 (ROOT/'EXT_HANDOVER_20261115_p5_ZH.md').write_text('\n'.join(hand)+'\n',encoding='utf-8')
 print('FINALIZE complete='+str(complete))
if __name__=='__main__':main()
