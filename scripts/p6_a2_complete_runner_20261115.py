from pathlib import Path
R=Path(__file__).resolve().parents[1];p=R/'fac_tinyagent/p6_attempt2.py'
src=(R/'fac_tinyagent/p6_trainqueue.py').read_text();tail=src[src.index('def rows_for('):src.index('\ndef queue():')]
# Skip old train implementation; append only rows/evaluate/score/finalize helpers.
a=tail.index('\ndef train(');b=tail.index('\ndef evaluate(');tail=tail[:a]+tail[b:]
tail=tail.replace('def evaluate(seed,arm):','def evaluate(seed,arm,only=None):').replace("todo=[x for x in SUITES if not (out/x/'stage_report.json').exists()]","todo=[x for x in (only or SUITES) if not (out/x/'stage_report.json').exists()]")
tail=tail.replace('def finalize():','def finalize(*,allow_cpu_mock=False):')
tail=tail.replace("rep=read_json(out/name/'stage_report.json');assert rep['evaluation_protocol']['batch_size']==1;suites+=1", "rep=read_json(out/name/'stage_report.json');assert rep['evaluation_protocol']['batch_size']==1\n     if rep.get('synthetic_cpu_contract'):assert allow_cpu_mock and 'cpu_contract_tests' in str(P.RUNS)\n     suites+=1")
tail=tail.replace("(P.ROOT/'EXT_REPORT_20261115_p6_ZH.md')",'REPORT').replace("(P.ROOT/'EXT_HANDOVER_20261115_p6_ZH.md')",'HANDOVER')
tail=tail.replace('P6实验报告：','P6 attempt2实验报告：').replace('P6交接手册','P6 attempt2交接手册')
tail=tail.replace('bash scripts/launch_p6_queue_20261115.sh','bash scripts/launch_p6_attempt2_20261115.sh').replace('-m fac_tinyagent.p6_trainqueue --phase finalize','-m fac_tinyagent.p6_attempt2 --phase finalize').replace('runs_ext_p6_devplan/','runs_ext_p6_devplan_attempt2/')
tail=tail.replace('旧训练实现只在内存重绑定输出目录以复用，未改P5代码或文件；兼容训练审计文件叫p5_meta.json但位于P6 branches内。','新增带实际optimizer.step调用凭据的训练副本；旧失败现场不改。旧microstep日志最后22不含尾部flush，新attempt用13次实际调用证明10+13=23，不能凭空添加训练。')
tail=tail.replace("md+=['','## 配对判定'", "md+=['','## 修复与公平性','旧attempt缺摘要必需quota字段而失败；新attempt只补接口诊断元数据，计划items/分配/7494 tokens/超参/holdout全部不变。校准hash核验后复用，不重复GPU校准。实际optimizer事件13次加prefix10次为23；日志最后microstep182的22是尾部6条flush之前，不是漏一步。失败adapter不复用。','','## 配对判定'")
footer='''

def queue():
 runtime_guard();safe()
 assert read_json(RUNS/'cpu_contract_tests'/'acceptance.json')['status']=='PASS'
 first=(SEEDS[0],ARMS[0]);train(*first);evaluate(*first,only=['p6_database'])
 ev=RUNS/'evaluation'/D.label(*first)/'p6_database'
 assert read_json(ev/'stage_report.json')['evaluation_protocol']['batch_size']==1
 assert len(read_jsonl(ev/'results.jsonl'))==24
 write_json(RUNS/'e2e_gate.json',{'status':'PASS','first':D.label(*first),'train_actual_steps':23,'tokens':7494,'first_B1_suite':'p6_database','n':24,'time':time.strftime('%F %T %z'),'scores_not_used_to_gate':True})
 log('E2E GATE PASS: first train summary + actual steps + first B1 suite; remaining 8 arms released')
 evaluate(*first);finalize()
 for arm in ARMS:
  for seed in SEEDS:
   if (seed,arm)==first:continue
   safe();train(seed,arm);evaluate(seed,arm);finalize()
 log('QUEUE COMPLETE')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--phase',required=True,choices=['initialize','verify','queue','finalize']);a=p.parse_args()
 if a.phase=='verify':runtime_guard()
 else:globals()[a.phase]()
'''
p.write_text(p.read_text()+'\n'+tail+footer)
print('attempt2 runner complete: direct contract, fresh roots, first-suite gate')
