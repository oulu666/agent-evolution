"""Same QLoRA model/AdamW as v2; deterministic backend fixed before first model load."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',PYTHONDONTWRITEBYTECODE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
from common import *

def make(seed,guard):
 import torch,numpy as np
 from fac_tinyagent.sft.train import load_base_model,load_tokenizer,_attach_adapter
 torch.use_deterministic_algorithms(True);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 torch.manual_seed(seed);torch.cuda.manual_seed_all(seed);np.random.seed(seed);random.seed(seed)
 config=copy.deepcopy(CONFIG);config['seed']=seed;guard.check()
 tok=load_tokenizer(config);m,dtype=load_base_model(config);m=_attach_adapter(m,config,None)
 expected=read(OLD_RUN/'budget_ledger.json')['lora_trainable_parameters_structure_estimate']
 assert sum(p.numel() for p in m.parameters() if p.requires_grad)==expected
 opt=torch.optim.AdamW([p for p in m.parameters() if p.requires_grad],lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=0)
 scaler=torch.cuda.amp.GradScaler(enabled=True)
 return m,tok,opt,scaler
