"""Read-only verification. No model execution or scientific metric recomputation."""
import os,json
from build_data import HERE,sha,read,unchanged
os.environ['CUDA_VISIBLE_DEVICES']=''
m=read(HERE/'manifest.json');expected=(HERE/'manifest.sha256').read_text().split()[0]
assert sha(HERE/'manifest.json')==expected
for name,h in m['hashes'].items():assert sha(HERE/name)==h,name
n=unchanged()
print(json.dumps({'verified':True,'frozen_files':len(m['hashes']),'manifest_sha256':expected,'legacy_files_unchanged':n,'new_generations':0},ensure_ascii=False))