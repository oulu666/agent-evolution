"""CPU-only message audit and preregistration; no heldout cases or weights are loaded."""
from common import *
import ast,copy,collections,importlib.metadata
from fac_tinyagent.sft.train import load_tokenizer
from fac_tinyagent.sft.dataset import conversation_text
from fac_tinyagent.replay_study import config_for
from core import parse_syntax,strict_score

def main():
 assert not (HERE/'FREEZE_MANIFEST.json').exists()
 checks=[]
 def check(label,condition):
  assert condition,label
  checks.append(label)
 old=read(ROOT/'acod_v2_eval_20261122/PROTOCOL_LOCK.json')
 protected=dict(old['protected_hashes'])
 for name,h in protected.items():check('legacy_hash:'+name,sha(ROOT/name)==h)
 for dirname in ['acod_round1_20261121','acod_v2_freeze_20261121','acod_v2_eval_20261122']:
  for p in (ROOT/dirname).rglob('*'):
   if p.is_file():protected[str(p.relative_to(ROOT))]=sha(p)
 for name in ['fac_tinyagent/sft/evaluate.py','fac_tinyagent/sft/dataset.py','fac_tinyagent/sft/train.py','fac_tinyagent/replay_study.py','fac_tinyagent/p10_devdiagnosis_20261117.py']:
  protected[name]=sha(ROOT/name)
 oldstop=ROOT/'acod_v2_eval_20261122/results/logs/STOP';stop=read(oldstop)
 check('known_STOP_exact_owner_reason',stop['owner']=='acod_v2_eval_20261122' and stop['reason']=={'deadline_seconds':1500} and stop['time']=='2026-11-22 00:38:09 +0800' and stop['auto_clear'] is False)
 source=(ROOT/'acod_v2_freeze_20261121/interfaces.py').read_text()
 constants=[n.value for n in ast.walk(ast.parse(source)) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith('You are answering a controlled read-only')]
 check('unique_original_v2_system',len(constants)==1);system=constants[0]
 tasks=read(ROOT/'acod_round1_20261121/tasks.json');chosen=['historical_0_first','historical_1_last'];configs=['A_historical_reference','B_v2_style','C_v2_system_legacy_stage']
 tok=load_tokenizer(config_for('A',20261108,batch_size=1));tok.padding_side='left'
 tokenizer_sha=hashlib.sha256(tok.backend_tokenizer.to_str().encode()).hexdigest()
 prior_events=rows(ROOT/'acod_v2_eval_20261122/results/events.jsonl')
 prior_tok={x['tokenizer_sha256'] for x in prior_events if x['event']=='MODEL_LOADED'}
 check('tokenizer_matches_both_previous_models',prior_tok=={tokenizer_sha})
 plan_cases=[];scorer=[];audit_cases=[];(HERE/'prompts').mkdir()
 prior_responses=rows(ROOT/'acod_round1_20261121/results/responses.jsonl')
 for ident in chosen:
  t=next(t for t in tasks if t['id']==ident);check(ident+':historical_dev',t['family']=='historical_dev')
  a=copy.deepcopy(t['views']['original']['messages']);check(ident+':legacy_roles',[x['role'] for x in a]==['system','user','assistant','user'])
  c=copy.deepcopy(a);c[0]['content']=system
  b=[{'role':'system','content':system},{'role':'user','content':a[1]['content']+'\n'+a[3]['content']}]
  mm=dict(zip(configs,[a,b,c]));check(ident+':A_C_only_system',a[1:]==c[1:]);check(ident+':B_C_same_system',b[0]==c[0])
  check(ident+':B_C_exact_question_payload',b[1]['content']==c[1]['content']+'\n'+c[3]['content'])
  check(ident+':original_payload',a[3]['content'].startswith('TOOL RESULT:\n') and json.loads(a[3]['content'].split('\n',1)[1])=={'ok':True,'result':t['views']['original']['rows']})
  counts={};details=[]
  for config,messages in mm.items():
   text=conversation_text(tok,messages,generation=True)
   direct=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
   check(ident+':'+config+':single_template_equal',text==direct)
   encoded=tok(text,add_special_tokens=False)['input_ids']
   ids=tok.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,enable_thinking=False)
   if hasattr(ids,'keys'):ids=ids['input_ids']
   check(ident+':'+config+':no_double_special_tokens',encoded==ids)
   check(ident+':'+config+':no_pretemplated_tokens',not any('<|im_start|>' in m['content'] for m in messages))
   check(ident+':'+config+':assistant_generation_suffix',text.rsplit('<|im_start|>',1)[1].startswith('assistant\n'))
   check(ident+':'+config+':role_header_count',text.count('<|im_start|>')==len(messages)+1)
   check(ident+':'+config+':within_input_limit',len(encoded)+128<32768)
   counts[config]=len(encoded)
   (HERE/f'prompts/{ident}__{config}.txt').open('x',encoding='utf-8').write(text)
   details.append({'configuration':config,'roles':[m['role'] for m in messages],'input_tokens':len(encoded),'render_suffix':text[-100:],'render_sha256':hashlib.sha256(text.encode()).hexdigest(),'template_applications':1,'input_truncation':False})
  plan_cases.append({'case_id':ident,'messages':mm,'input_tokens':counts})
  scorer.append({'case_id':ident,'gold':t['views']['original']['gold'],'schema':{'allowed_types':['string','null']}})
  audit_cases.append({'case_id':ident,'details':details,'prior_exposed_raw':[{'seed':x['seed'],'raw':x['raw']} for x in prior_responses if x['task']==ident and x['view']=='original']})
 # Parser regressions: format compatibility and task correctness remain separate.
 for raw,envelope,schema in [('9',False,False),('"9"',False,False),('{"answer":9}',True,False),('{"answer":"9"}',True,True),('{"answer":"line 9"}',True,True),('{"answer":null}',True,True),('{"record_key":"r0","start_line":9}',False,False),('{"answer":"x","answer":"y"}',False,False),('```json\n{"answer":"x"}\n```',False,False),('{"answer":"x","extra":1}',False,False),('{"answer":"x"}',True,True)]:
  s=strict_score(raw,{'allowed_types':['string','null']},'x');check('parser:'+raw,s['syntax_valid']==envelope and s['output_schema_valid']==schema)
 check('integer_not_string_gold',not strict_score('{"answer":9}',{'allowed_types':['string','null']},'9')['strict_correct'])
 text=(ROOT/'fac_tinyagent/sft/evaluate.py').read_text();tree=ast.parse(text);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='generate_with_usage')
 calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call)]
 check('one_conversation_template_call',sum(isinstance(n.func,ast.Name) and n.func.id=='conversation_text' for n in calls)==1)
 check('tokenize_no_input_truncation',not any(k.arg in ['max_length','truncation'] for n in calls for k in n.keywords))
 check('one_model_generate',sum(isinstance(n.func,ast.Attribute) and n.func.attr=='generate' for n in calls)==1)
 gen=next(n for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='generate')
 check('greedy_fixed_false',next(k.value.value for k in gen.keywords if k.arg=='do_sample') is False)
 receipts=rows(ROOT/'acod_v2_eval_20261122/results/model_receipts.jsonl');models=[]
 for m in old['models']:
  ident=copy.deepcopy(m);r=next(x for x in receipts if x['seed']==m['seed']);ident['expected_parameter_digest']=r['parameter_digest_after'];models.append(ident)
  ac=read(Path(m['adapter'])/'adapter_config.json');check('adapter_identity:'+str(m['seed']),sha(Path(m['adapter'])/'adapter_model.safetensors')==m['adapter_sha256'])
  check('base_pairing:'+str(m['seed']),Path(ac['base_model_name_or_path']).name==Path(m['model_name_or_path']).name)
 plan={'created':now(),'scope':'Existing historical development only; two fixed original cases, no reserved/heldout or new cases','models':models,'configurations':configs,'cases':plan_cases,'tokenizer_backend_sha256':tokenizer_sha,'decode':{'batch_size':1,'greedy':True,'use_cache':False,'max_new_tokens':128},'maximum_calls':12,'technical_retries':0,'walltime_seconds':600,'single_call_timeout_seconds':60}
 save(HERE/'PLAN_PUBLIC.json',plan);save(HERE/'SCORER_ONLY.json',scorer)
 audit={'created':now(),'checks':checks,'PASS':len(checks),'FAIL':0,'cases':audit_cases,'tokenizer_backend_sha256':tokenizer_sha,'tokenizer_name':tok.name_or_path,'tokenizer_model_max_length':tok.model_max_length,'padding_side':'left','truncation_side':tok.truncation_side,'input_truncation_applied':False,'stack_bug_found':False,'observed_interface_difference':'Historical S/U/A(toolcall)/U(TOOL RESULT envelope) vs v2 S/U(question + TOOL RESULT observation), plus changed system and observation structures','causal_status':'Difference confirmed; impact not yet tested. B is exact v2 two-role construction transplanted onto historical payload, not reproduction of original heldout failure rate.'}
 save(HERE/'CPU_AUDIT.json',audit)
 prereg='''# 兼容性有界预注册（所有新响应前锁定）
仅 historical_0_first / historical_1_last 两个既有历史开发题，均用original；不读入v2保留16题，不用reserved，无新数据。选择ID在查看本次输出前固定。旧raw已知，因此是开发兼容性检查，不是盲验证。
A：逐字重放round1四轮消息及原历史system；B：把同一个问题/TOOL RESULT观测按v2原system及两轮构造包装；C：保持B的system、原问题和同一观测，恢复历史四轮工具后回答阶段包装。B不是重跑v2复杂保留题，不能宣称复现了原失败率。
A与C只差system；B与C只差阶段包装。阶段包装包含提供既有assistant tool-call与将TOOL RESULT移至独立末轮user，不能进一步分辨这两个组成部分的各自作用。观测envelope/字段/行号/text字节和问题语义全程不变；不加字段提醒，不根据结果搜索prompt。
两份原checkpoint，各2题×3配置×1次B1 greedy，共12次；技术失败重试0；单次60秒、监督墙钟600秒，未完成就停，不自动恢复。不训练，不改旧文件。use_cache=False、max_new_tokens128，使用原generate_with_usage，无模板/解析修补。
主终点：完整单键answer JSON且value为string/null的schema计数。单键envelope、严格typed答案正确另列；整数9与string9不混同；不从record_key/start_line等对象提取答案。正确率只是描述，schema合格不代表理解正确。
判读：若B失败而A/C成功，只支持这两道历史开发题上阶段包装影响输出契约；若B/C均失败而A成功，支持system/阶段适配不足但不得再追调；若B也成功，说明历史简单payload未复现故障，原v2复杂任务的观测结构/语义变化仍未被本对照隔离。任何结果都不证明ACOD/MDCS有效或无效。
旧eval STOP经owner/time/reason及SHA核对，仅对该不可变历史超时artifact做作用域隔离，不删除/移动/改写；任意未知、修改后的或新STOP、游戏、其他GPU/项目进程均停止。本次有独立STOP，不清用户停止命令。
结束即释放GPU。原v2/round1/权重/.venv均不改；CPU检查不等于零CPU成本。不推断隐藏根因，不以2题淘汰研究方向。
'''
 (HERE/'PREREG_COMPAT_ZH.md').open('x',encoding='utf-8').write(prereg)
 sources={str(p.relative_to(HERE)):sha(p) for p in HERE.rglob('*') if p.is_file()}
 manifest={'created':now(),'protected_sha256':protected,'protected_file_count':len(protected),'new_source_sha256':sources,'plan_sha256':sha(HERE/'PLAN_PUBLIC.json'),'isolated_historical_STOP':{'path':str(oldstop.relative_to(ROOT)),'sha256':sha(oldstop),'contents':stop},'installed_package_versions':{n:importlib.metadata.version(n) for n in ['torch','transformers','peft','bitsandbytes']},'max_generation_calls':12,'technical_retries':0,'walltime_seconds':600}
 save(HERE/'FREEZE_MANIFEST.json',manifest);verify()
 from compat_runner import safety
 s=safety({os.getpid(),os.getppid()});save(HERE/'CPU_PREFLIGHT.json',s)
 print(canonical({'PASS':len(checks),'FAIL':0,'protected_files':len(protected),'plan_sha256':manifest['plan_sha256'],'freeze_manifest_sha256':sha(HERE/'FREEZE_MANIFEST.json'),'preflight':s,'new_inference':0}))
if __name__=='__main__':main()