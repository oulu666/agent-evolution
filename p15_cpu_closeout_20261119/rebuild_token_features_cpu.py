"""Reconstruct omitted deterministic derived token cache using local tokenizer only, never model weights.
Default checks bytes against old frozen manifest without writing. --write creates ONLY a missing cache.
"""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
import sys,pathlib,argparse,gzip,json,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'p15_stageaware_20261119'))
from core import *

def main(write_missing=False):
 from transformers import AutoTokenizer
 ident=read(RUN/'tokenizer_identity.json');base=Path(CONFIG['model_name_or_path'])
 for name,d in ident['files'].items():assert h((base/name).read_bytes())==d
 tok=AutoTokenizer.from_pretrained(str(base),trust_remote_code=False,local_files_only=True)
 if tok.pad_token is None:tok.pad_token=tok.eos_token
 tok.padding_side='right'
 rr=[r for split in ('train','dev','test') for r in rows(split)];features=encode_all(tok,rr)
 payload=gzip.compress(cj(features).encode(),mtime=0);p=RUN/'token_features.json.gz'
 expected=read(RUN/'runtime_manifest.json')['files'][str(p.relative_to(ROOT))];assert h(payload)==expected
 if p.exists():assert p.read_bytes()==payload
 elif write_missing:p.write_bytes(payload)
 import torch
 assert not torch.cuda.is_initialized()
 result={'CPU_only':True,'model_loaded':False,'tokenizer_identity_checked':True,'rows':len(rr),'cache_sha256':expected,'cache_bytes':len(payload),
  'write_requested':write_missing,'existing_cache_unchanged':p.exists() and p.read_bytes()==payload}
 out=ROOT/'runs_ext_p15_cpu_closeout_20261119';out.mkdir(exist_ok=True);(out/'token_cache_rebuild_check.json').write_text(cj(result)+'\n');print(cj(result))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');main(p.parse_args().write)
