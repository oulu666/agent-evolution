"""Exact checkpoint/data/prompt/generation cache. No parsed-tool-correctness shortcut."""
from common import *
import time

class ExactCache:
 def __init__(self,path,scope,model_binding,data_binding):
  self.path=Path(path);self.scope=scope;self.model=model_binding;self.data=data_binding
 def request(self,prompt,generation,mode,producer):
  binding={'scope':self.scope,'checkpoint':self.model,'data':self.data,
   'prompt_sha256':h(prompt.encode('utf8')),'prompt_bytes':len(prompt.encode('utf8')),'generation':generation}
  key=h(cj(binding).encode());p=self.path/(key+'.json')
  if p.exists():
   rec=read(p);assert rec['binding']==binding and rec['payload_sha256']==h(cj(rec['payload']).encode())
   raw,usage=rec['payload']['raw'],dict(rec['payload']['usage']);usage.update(cache_hit=True,inference_calls=0,wall_seconds=0.,input_tokens=0,output_tokens=0,
    logical_input_tokens=rec['payload']['usage']['input_tokens'],logical_output_tokens=rec['payload']['usage']['output_tokens'],source_mode=rec['mode'])
  else:
   disk_check();raw,usage=producer();usage=dict(usage);payload={'raw':raw,'usage':dict(usage)}
   atomic_json(p,{'binding':binding,'mode':mode,'payload':payload,'payload_sha256':h(cj(payload).encode())})
   usage.update(cache_hit=False,logical_input_tokens=usage['input_tokens'],logical_output_tokens=usage['output_tokens'])
  usage.update(cache_key=key,prompt_sha256=binding['prompt_sha256'],checkpoint_binding_sha256=h(cj(self.model).encode()))
  return raw,usage

def evaluate(model,tok,rr,guard,cache,path=None):
 import torch
 from runner_v2 import generate,preserved_rng
 from fac_tinyagent.sft.evaluate import parse_tool_call,parse_final_answer
 from fac_tinyagent.metrics import answers_equal,observations_equal,joint_success
 assert rr and len({r['split'] for r in rr})==1
 bound=BoundCalendar(rr[0]['split']);was=model.training;result=[];funcs=tokenizer_functions()
 def gen(messages,n,mode):
  text=funcs['conversation_text'](tok,messages,True)
  config={'max_new_tokens':n,'do_sample':False,'use_cache':True,'context_limit':4096,'pad_token_id':tok.pad_token_id,
   'eos_token_ids':sorted({v for v in (tok.eos_token_id,tok.convert_tokens_to_ids('<|im_end|>')) if isinstance(v,int) and v>=0}),
   'tokenizer_identity_sha256':h((OLD_RUN/'tokenizer_identity.json').read_bytes())}
  def produce():
   torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.perf_counter()
   raw,usage=generate(model,tok,messages,n,guard);torch.cuda.synchronize()
   usage.update(wall_seconds=time.perf_counter()-start,peak_allocated_MiB=torch.cuda.max_memory_allocated()/2**20,peak_reserved_MiB=torch.cuda.max_memory_reserved()/2**20)
   return raw,usage
  return cache.request(text,config,mode,produce)
 with preserved_rng(torch):
  model.eval()
  try:
   for r in rr:
    start=time.perf_counter();guard.check();toolraw,ut=gen(r['messages'][:2],128,'tool');call=parse_tool_call(toolraw)
    tool=call['tool'] if call else None;args=call['arguments'] if call else {}
    obs=bound.execute(r,tool,args) if tool else {'ok':False,'error':'model did not return a valid tool call'}
    realmsg=r['messages'][:2]+[{'role':'assistant','content':toolraw},{'role':'user','content':'TOOL RESULT:\n'+cj(obs)}]
    real,ur=gen(realmsg,256,'real_final');gold,ug=gen(r['messages'][:4],256,'gold_final')
    ok,ans=parse_final_answer(real);gok,gans=parse_final_answer(gold)
    rec={'episode_id':r['episode_id'],'split':r['split'],'skill':r['skill'],'continual_group':r['continual_group'],
     'tool_correct':tool==r['expected_tool'],'arguments_correct':answers_equal(args,r['expected_arguments']),
     'execution_success':observations_equal(cj(obs),r['expected_observation']),
     'final_correct':bool(ok and not ur['context_overflow'] and answers_equal(ans,r['expected_final_answer'])),
     'gold_final_correct':bool(gok and not ug['context_overflow'] and answers_equal(gans,r['expected_final_answer'])),
     'predicted_tool':tool,'predicted_arguments':args,'tool_raw':toolraw,'real_final_raw':real,'gold_final_raw':gold,
     'tool_usage':ut,'real_final_usage':ur,'gold_final_usage':ug,'actual_observation_sha256':h(cj(obs).encode()),
     'episode_wall_seconds':time.perf_counter()-start,'real_gold_prompt_bytes_equal':ur['prompt_sha256']==ug['prompt_sha256']}
    rec['tool_args_core']=rec['tool_correct'] and rec['arguments_correct'];rec['joint_success']=joint_success(rec);result.append(rec)
    if path:append(path,rec)
  finally:model.train(was)
 return result
