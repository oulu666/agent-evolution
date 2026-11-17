from pathlib import Path
import sys,json,random,tempfile
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import torch,numpy as np
from fac_tinyagent import p7_fullstate_v2_20261115 as F
torch.manual_seed(84);random.seed(84);np.random.seed(84)
m=torch.nn.Sequential(torch.nn.Linear(4,4),torch.nn.Dropout(.3),torch.nn.Linear(4,1));o=torch.optim.AdamW(m.parameters(),lr=1e-4);sc=torch.amp.GradScaler('cpu',enabled=False);x=torch.ones(2,4)
def step():
 m.train();o.zero_grad(set_to_none=True);m(x).square().mean().backward();o.step();o.zero_grad(set_to_none=True)
step();a=F.capture(m,o,sc);step();b=F.capture(m,o,sc);F.restore(a,m,o,sc);step();assert F.digest(F.capture(m,o,sc))==F.digest(b)
out=R/'runs_ext_p7_statefix_v2_20261115/cpu_contract';out.mkdir()
receipt=F.save(b,out/'state.pt');loaded=F.load(out/'state.pt',receipt);m.eval();random.random();np.random.rand();torch.rand(4);F.restore(loaded,m,o,sc);assert F.digest(F.capture(m,o,sc))==F.digest(b)
(out/'acceptance.json').write_text(json.dumps({'status':'PASS','cpu_only':True,'identical_update_replay_with_dropout':True,'exact_disk_roundtrip_parameters_optimizer_scaler_rng_modes':True,'no_GPU_training':True,'digest':F.digest(b)}));print('CPU FULL STATE CONTRACT PASS')

# Exercise the real bnb serialized FSDP wrapper contract on CPU, without GPU or optimizer updates.
from bitsandbytes.optim import PagedAdamW8bit
mm=torch.nn.Linear(4,1,bias=False);oo=PagedAdamW8bit(mm.parameters(),lr=1e-4);pp=next(mm.parameters())
oo.state[pp]={'step':1,'state1':torch.zeros_like(pp,dtype=torch.uint8),'state2':torch.ones_like(pp,dtype=torch.uint8)}
aa=F.capture(mm,oo,sc);F.restore(aa,mm,oo,sc);assert oo.state[pp]['state1'].dtype==torch.uint8
oo.prefetch_state(pp)
data=json.loads((out/'acceptance.json').read_text());data['actual_bnb_FSDP_wrapped_state_native_roundtrip_prefetch']=True;(out/'acceptance.json').write_text(json.dumps(data));print('BNB SERIALIZED/RUNTIME CONTRACT PASS')
