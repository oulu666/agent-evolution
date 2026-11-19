"""CPU toys execute the SAME branch engine and disk state/cache code; no model weights."""
import os
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
from common import *
from engine_v3 import optimizer_update,branch_coefficients
from state_v3 import Store,capture,semantic,restore,PhysicalBudget
from evaluation_v3 import ExactCache

def main():
 import torch,types
 import runner_v2
 runner_v2.verify() # includes598 protected hashes, v1/v2 freeze and base/tokenizer file hashes; NO model loading
 assert not torch.cuda.is_initialized()
 work=RUN/'cpu_fixtures'/str(time.time_ns());work.mkdir(parents=True)
 class Guard:
  def check(self):pass
 class Scaler:
  def state_dict(self):return {}
  def load_state_dict(self,s):assert s=={}
 class Toy(torch.nn.Module):
  def __init__(self):
   super().__init__();self.w=torch.nn.Parameter(torch.tensor(0.));self.register_buffer('fixed',torch.tensor([1.]));self.config=types.SimpleNamespace(use_cache=False)
  def get_base_model(self):return self
  def forward(self,input_ids,attention_mask,labels):
   target=labels[labels!=-100].float().mean()/10
   return types.SimpleNamespace(loss=(self.w-target)**2)
 f={'n':{'input_ids':[0]*4,'masks':{'both':[1,1,-100,-100]},'supervised_tokens':{'both':2},'input_tokens':4},
  'r':{'input_ids':[0]*4,'masks':{'call':[3,-100,-100,-100],'final':[3,3,3,-100]},'supervised_tokens':{'call':1,'final':3},'input_tokens':4}}
 tests={};vals=[]
 for mode in ('call','final'):
  m=Toy();opt=torch.optim.SGD(m.parameters(),lr=.1);ex=[('n','both','new'),('r',mode,'replay')]
  result=optimizer_update(m,opt,None,f,ex,'cpu',Guard());vals.append(float(m.w.detach()))
  assert result['branch_weights']=={'new':.5,'replay':.5} and abs(result['gradient_norm_before_clip']-.4)<1e-6
 assert vals[0]==vals[1];tests['fixed_branch_weight_mask_invariance']=True
 assert branch_coefficients(f,[('n','both','new')])[1]=={'new':1.,'replay':0.};tests['new_only_weight_one']=True
 m=Toy();opt=torch.optim.AdamW(m.parameters(),lr=.01);scaler=Scaler();store=Store(work/'state');g=Guard();meta={'position':0,'queue':['r'],'rng':random.Random(17).getstate(),'anchors':{'fixture_only':True}}
 store.commit(m,opt,scaler,meta)
 ex=[('n','both','new'),('r','final','replay')]
 optimizer_update(m,opt,None,f,ex,'cpu',g);meta['position']=1;r1=store.commit(m,opt,scaler,meta)
 optimizer_update(m,opt,None,f,ex,'cpu',g);meta['position']=2;a=capture(m,opt,scaler,meta)
 m2=Toy();o2=torch.optim.AdamW(m2.parameters(),lr=.01);s2=Scaler();meta=store.restore(m2,o2,s2,r1)
 optimizer_update(m2,o2,None,f,ex,'cpu',g);meta['position']=2;b=capture(m2,o2,s2,meta)
 assert semantic(a)==semantic(b);tests['atomic_disk_fullstate_next_update_exact_cpu']=True
 oldcurrent=read(work/'state/CURRENT.json');(work/'state/uncommitted_partial.tmp').write_text('interrupted')
 assert read(work/'state/CURRENT.json')==oldcurrent;store.load();tests['uncommitted_partial_not_current']=True
 budget=PhysicalBudget(work/'physical.jsonl',3)
 for i in range(3):budget.before_step()
 try:budget.before_step();raise AssertionError('budget must reject fourth')
 except AssertionError as exc:assert 'limit exhausted' in str(exc)
 tests['physical_step_cap_enforced']=True
 count=[0]
 def producer():count[0]+=1;return 'answer',{'inference_calls':1,'input_tokens':4,'output_tokens':2,'wall_seconds':.1,'context_overflow':False}
 cache=ExactCache(work/'cache',{'trajectory':'t','seed':17},{'model':'a'},{'fixture':'train'})
 _,u=cache.request('exact bytes',{'max_new':256},'real_final',producer)
 _,v=cache.request('exact bytes',{'max_new':256},'gold_final',producer)
 assert count[0]==1 and v['cache_hit'] and v['source_mode']=='real_final'
 cache.request('exact bytes ',{'max_new':256},'gold_final',producer)
 cache.request('exact bytes',{'max_new':128},'gold_final',producer)
 ExactCache(work/'cache',{'trajectory':'t','seed':29},{'model':'a'},{'fixture':'train'}).request('exact bytes',{'max_new':256},'gold_final',producer)
 ExactCache(work/'cache',{'trajectory':'t','seed':17},{'model':'b'},{'fixture':'train'}).request('exact bytes',{'max_new':256},'gold_final',producer)
 ExactCache(work/'cache',{'trajectory':'t','seed':17},{'model':'a'},{'fixture':'dev'}).request('exact bytes',{'max_new':256},'gold_final',producer)
 assert count[0]==6;tests['cache_exact_bytes_model_seed_data_generation_binding']=True
 tests['real_gold_reuse_only_same_prompt_bytes']=True
 try:BoundCalendar('dev',DATA/'fixtures/train.json');raise AssertionError('wrong fixture must fail')
 except ValueError:pass
 tests['wrong_split_fixture_rejected']=True
 plan=read(RUN/'review_budget_v3.json');assert plan['total_logical_generation_requests']==603072 and plan['request_cap_after_update0_exact_cache_if_all_bindings_match']==584064
 assert plan['trajectories']==108 and plan['logical_updates']==41472;tests['revised_eval_matrix_and108_trajectories']=True
 assert not (RUN/'START_APPROVED_V3.json').exists();tests['formal_start_gate_absent']=True
 assert not torch.cuda.is_initialized();tests['CPU_only_no_model_load']=True
 result={'pass':all(tests.values()),'tests':tests,'protected_old_files':598,'source_hashes':{str(p.relative_to(ROOT)):h(p.read_bytes()) for p in sorted(CODE.glob('*.py'))}}
 write(RUN/'cpu_acceptance.json',result);print(cj(result))

if __name__=='__main__':main()
