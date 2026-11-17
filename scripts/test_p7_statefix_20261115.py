from pathlib import Path
import sys,json,random,tempfile
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import torch,numpy as np
from fac_tinyagent import p7_fullstate_20261115 as F
torch.manual_seed(84);random.seed(84);np.random.seed(84)
m=torch.nn.Sequential(torch.nn.Linear(4,4),torch.nn.Dropout(.3),torch.nn.Linear(4,1));o=torch.optim.AdamW(m.parameters(),lr=1e-4);sc=torch.amp.GradScaler('cpu',enabled=False);x=torch.ones(2,4)
def step():
 m.train();o.zero_grad(set_to_none=True);m(x).square().mean().backward();o.step();o.zero_grad(set_to_none=True)
step();a=F.capture(m,o,sc);step();b=F.capture(m,o,sc);F.restore(a,m,o,sc);step();assert F.digest(F.capture(m,o,sc))==F.digest(b)
out=R/'runs_ext_p7_statefix_20261115/cpu_contract';out.mkdir()
receipt=F.save(b,out/'state.pt');loaded=F.load(out/'state.pt',receipt);m.eval();random.random();np.random.rand();torch.rand(4);F.restore(loaded,m,o,sc);assert F.digest(F.capture(m,o,sc))==F.digest(b)
(out/'acceptance.json').write_text(json.dumps({'status':'PASS','cpu_only':True,'identical_update_replay_with_dropout':True,'exact_disk_roundtrip_parameters_optimizer_scaler_rng_modes':True,'no_GPU_training':True,'digest':F.digest(b)}));print('CPU FULL STATE CONTRACT PASS')
