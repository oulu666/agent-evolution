"""Fixed descriptive report, no inference and no answer normalization."""
from common import *
import collections,subprocess,zipfile,ast
from core import strict_score

def main():
 m=verify();run=HERE/'results';responses=rows(run/'responses.jsonl');attempts=rows(run/'calls_started.jsonl');gold={x['case_id']:x for x in read(HERE/'SCORER_ONLY.json')};plan=read(HERE/'PLAN_PUBLIC.json')
 end=read(run/'supervisor_end.json');start=read(run/'supervisor_start.json');cpu=read(HERE/'CPU_AUDIT.json')
 assert end['rc']==0 and (run/'COMPLETE.json').exists() and len(responses)==12 and len(attempts)==12
 detailed=[]
 for r in responses:
  g=gold[r['case_id']];score=strict_score(r['raw'],g['schema'],g['gold'])
  detailed.append(dict(r,**score,gold=g['gold'],at_output_limit=r['usage']['output_tokens']==128))
 save(run/'scorer_only_layered.json',detailed)
 aggregates=[]
 for config in plan['configurations']:
  rr=[x for x in detailed if x['configuration']==config]
  aggregates.append({'configuration':config,'n':len(rr),'exact_answer_envelope':sum(x['syntax_valid'] for x in rr),'strict_schema':sum(x['output_schema_valid'] for x in rr),'strict_correct':sum(x['strict_correct'] for x in rr),'at128':sum(x['at_output_limit'] for x in rr)})
 lookup={(x['seed'],x['case_id'],x['configuration']):x for x in detailed};contrasts=[];matches=0
 for seed in [x['seed'] for x in plan['models']]:
  for case in plan['cases']:
   a,b,c=[lookup[seed,case['case_id'],k] for k in plan['configurations']]
   contrasts.append({'seed':seed,'case_id':case['case_id'],'A_schema':a['output_schema_valid'],'B_schema':b['output_schema_valid'],'C_schema':c['output_schema_valid'],'stage_rescue_B_to_C':not b['output_schema_valid'] and c['output_schema_valid'],'system_rescue_C_to_A':not c['output_schema_valid'] and a['output_schema_valid']})
   prior=next(x for q in cpu['cases'] if q['case_id']==case['case_id'] for x in q['prior_exposed_raw'] if x['seed']==seed)
   matches+=a['raw']==prior['raw']
 usage={k:sum(r['usage'][k] for r in responses) for k in ['input_tokens','output_tokens','total_tokens','generation_seconds']}
 guards=rows(run/'logs/guard.jsonl')+rows(run/'logs/worker_guard.jsonl');receipts=rows(run/'model_receipts.jsonl');events=rows(run/'model_events.jsonl')
 gpu=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],timeout=20).decode().strip()
 runtime={}
 for pid in [start['pid'],read(run/'worker_identity.json')['pid']]:
  p=Path('/proc')/str(pid)/'cmdline'
  try:args=[x.decode(errors='replace') for x in p.read_bytes().split(b'\0') if x]
  except FileNotFoundError:args=[]
  runtime[str(pid)]=args
 assert not any('compat_runner.py' in arg for args in runtime.values() for arg in args)
 # Read-only source audit of inherited generation config preparation. This is CPU provenance, not new inference.
 import transformers
 gp=Path(transformers.__file__).parent/'generation/utils.py';source=gp.read_text();tree=ast.parse(source);targets=[]
 for node in ast.walk(tree):
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name=='_prepare_generation_config':targets.append(ast.get_source_segment(source,node))
 (HERE/'INHERITED_GENERATION_CONFIG_SOURCE.txt').open('x',encoding='utf-8').write('\n\n'.join(targets))
 summary={'time':now(),'completed':True,'cases':2,'models':2,'configurations':3,'attempts':len(attempts),'responses':len(responses),'technical_retries':0,'strict_aggregates':aggregates,'paired_schema_contrasts':contrasts,'A_raw_reproduces_previous':matches,'usage':usage,'supervisor':end,'CPU_PASS':cpu['PASS'],'CPU_FAIL':cpu['FAIL'],'protected_files_unchanged':m['protected_file_count'],'parameter_receipts':receipts,'guard_checks':len(guards),'sampled_power_W_range':[min(float(s['gpu_actual'][1]) for s in guards),max(float(s['gpu_actual'][1]) for s in guards)],'sampled_max_temperature_C':max(float(s['gpu_actual'][3]) for s in guards),'old_STOP_hash_unchanged':sha(ROOT/m['isolated_historical_STOP']['path'])==m['isolated_historical_STOP']['sha256'],'former_run_pids_current_argv':runtime,'final_gpu_compute_apps':gpu,'no_auto_followup':True,'model_generation_config_use_cache_values':[e['generation_config'].get('use_cache') for e in events],'model_config_use_cache_values':[e['model_use_cache'] for e in events]}
 save(run/'summary.json',summary)
 a,b,c=aggregates
 if b['strict_schema']==4:
  conclusion='B的两轮v2式包装在全部4个历史开发配对上仍产生严格schema合格answer。这里没有复现原v2格式崩溃，因此不能把“两轮包装/缺少历史工具前缀”直接判为207条失败的原因。'
  nextstep='唯一建议：先对已暴露v2开发输入做CPU语义契约审查，明确其复杂观测结构/问句相对旧file_search新增了什么；只有得到可独立验证的同语义表示，才另行预注册表示兼容对照。不是改保留集prompt再刷分。'
 elif c['strict_schema']>b['strict_schema']:
  conclusion='在这些固定历史开发输入上，恢复工具后回答阶段包装后，schema合格计数高于v2式两轮包装。这是阶段包装影响的直接配对证据，不足以证明原v2复杂输入全由同一原因失败。'
  nextstep='唯一建议：把阶段包装作为待验证适配器，先在已暴露v2开发题上进行语义/输出契约CPU审查并预注册独立兼容性验收；不要重跑原保留矩阵。'
 else:
  conclusion='本次有限对照未取得阶段包装能够稳定修复schema的证据；不能把假说写成已确证原因，也不继续搜索prompt。'
  nextstep='唯一建议：CPU审查已暴露v2开发任务与旧file_search观测/问句的语义契约差异，先明确可比较的接口适配定义，再决定是否需要另行有界验证。'
 text=['# ACOD有界兼容性检查：真实完成12次，非v2重跑',f'报告时间：{now()}（Asia/Shanghai）。',f"执行：{start['time']}—{end['time']}，墙钟{end['wall_seconds']:.3f}秒；12次尝试/12条原始输出，0技术失败/重试。",'', '## 范围与预锁','仅既有historical_0_first、historical_1_last两道已暴露开发题的original；不是v2保留16题，不用reserved，不新造题。两份旧P9 ordinary Qwen3-0.6B checkpoint（seed20261108/20261109），没有训练或新增规则。','每题观测JSON及问题逐字相同；A为原round1四轮消息/旧system，B为原v2 system/两轮消息构造移植到历史payload，C保持B system并恢复A四轮阶段包装。B不是v2复杂保留集失败率的复现。','A↔C仅system不同；B↔C为阶段包装差别，包含既有assistant tool-call和独立末轮TOOL RESULT两个组成，不能进一步分别归因。','', '## CPU审计',f"{cpu['PASS']} PASS、{cpu['FAIL']} FAIL，其中118项为此前保护哈希断言；其余包含消息等价/模板/类型/模型身份等检查。",'实际模板仅应用一次，tokenize=False后add_special_tokens=False的IDs与直接chat-template tokenize一致；消息内容无预套模板；所有渲染均有闭合消息和新assistant生成头，未停在未闭合tool JSON。输入不截断，六个prompt仅151—335 tokens；128是输出上限，不是输入上限。tokenizer backend SHA与前次两checkpoint记录一致，基座/adapter身份及全部参数digest另外核验。','观察到旧历史工具结果为ok/result封装与line/text列表；v2保留复杂观测曾是record_key/fragment等结构，且system/阶段/问句均改变。本对照故意不同时改观测表示，因此没有隔离复杂结构或问句新增语义的作用。','', '## 三配置真实数值','|配置|次数|单answer envelope|严格schema|string/null严格答案正确|达到128上限|','|---|---:|---:|---:|---:|---:|']
 for x in aggregates:text.append(f"|{x['configuration']}|{x['n']}|{x['exact_answer_envelope']}|{x['strict_schema']}|{x['strict_correct']}|{x['at128']}|")
 text += ['', 'schema合格只是输出格式/类型契约，不等于正确理解任务。integer9、string9、line9仍严格区分；没有从record_key/start_line提取答案。所有raw完整保存在results/responses.jsonl。',f'原历史A raw与旧记录逐字复现：{matches}/4；两个题/两个checkpoint不能当大量独立样本作显著性或因果根因结论。','', '## 逐条原输出','|seed|题|配置|raw|严格正确|','|---|---|---|---|---:|']
 for r in detailed:text.append(f"|{r['seed']}|{r['case_id']}|{r['configuration']}|`{r['raw'].replace('|',' / ')}`|{int(r['strict_correct'])}|")
 text += ['', '## 判断与唯一下一步',conclusion,nextstep,'本检查不证明ACOD/MDCS有效，无条件切换或隐藏根因gold；不因这两个开发题淘汰任何研究方向。本次到此停止，不自动实施下一步。','', '## 成本、冻结与停止',f"输入{usage['input_tokens']}、输出{usage['output_tokens']}、合计{usage['total_tokens']} tokens；原generate_with_usage计时合计{usage['generation_seconds']:.3f}秒，墙钟含两次加载与监护，不能把0训练说成0推理/CPU成本。",f"{len(guards)}次guard；采样功耗{summary['sampled_power_W_range']}W、最高温度{summary['sampled_max_temperature_C']}℃；未调整风扇/功耗。两模型全参数digest前后一致，并与原v2模型digest相同。",f"{m['protected_file_count']}个历史文件SHA不变，原STOP仍在原路径且SHA不变；没有删除、移动或清除。最终GPU计算进程：{gpu or '无'}；原worker/监督器身份已不存在，无自动恢复。",'新目录仅acod_compat_20261122。FREEZE_MANIFEST.json/PLAN_PUBLIC.json/PREREG_COMPAT_ZH.md/六个渲染prompt均在响应前锁定。旧round1/v2freeze/v2eval/.venv/权重不改，无push/外发/付费API。','', '## 继承生成配置的透明记录',f"沿用原generate_with_usage与model.config.use_cache=False；加载时generation_config.use_cache记录为{summary['model_generation_config_use_cache_values']}。模型配置与生成配置若不同，不能仅凭前者声称底层强制关闭cache；附INHERITED_GENERATION_CONFIG_SOURCE.txt保留所用库准备逻辑，未为此额外生成或修改原pipeline。所有A/B/C共享同一继承设置，不是B32提速对照。"]
 (HERE/'REPORT_COMPAT_ZH.md').open('x',encoding='utf-8').write('\n'.join(text)+'\n')
 handover=['# 兼容性检查交接',conclusion,nextstep,'全部12次已结束；不得自动跑v2/MDCS或继续prompt search。旧STOP不可清除。','主报告REPORT_COMPAT_ZH.md；数据results/responses.jsonl；预锁FREEZE_MANIFEST.json；分层评分results/scorer_only_layered.json；摘要results/summary.json。','若未来研究接口适配，本检查只是历史开发证据，不是独立新测试，不能复用原v2保留集宣称独立验证。']
 (HERE/'HANDOVER_COMPAT_ZH.md').open('x',encoding='utf-8').write('\n'.join(handover)+'\n')
 verify();files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
 save(HERE/'DELIVERY_HASHES.json',{'time':now(),'protected_files_verified':m['protected_file_count'],'hashes':{str(p.relative_to(HERE)):sha(p) for p in files}})
 print(canonical(summary))
if __name__=='__main__':main()