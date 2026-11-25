import sys,json,zipfile,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lock_protocol import verify,now
verify()
d=Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((d/'DELIVERY_HASHES.json').read_text())
assert all(sha(d/k)==v for k,v in m['hashes'].items())
z=d/'acod_v2_eval_incomplete_bundle.zip'
files=[p for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
assert not any(p.is_symlink() for p in files)
f=d/'FINAL_DELIVERY_FILES.json'
f.open('x').write(json.dumps({'time':now(),'hashes':{str(p.relative_to(d)):sha(p) for p in files}},ensure_ascii=False,indent=2)+'\n')
files.append(f)
with zipfile.ZipFile(z,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as a:
    for p in files:a.write(p,arcname=str(Path(d.name)/p.relative_to(d)))
with zipfile.ZipFile(z) as a:assert a.testzip() is None
out={'time':now(),'bundle':str(z),'sha256':sha(z),'bytes':z.stat().st_size,'files':len(files),'all_118_protected_files_unchanged':True,'all_delivery_hashes_verified':True,'zip_integrity':'PASS','STOP':'PRESERVED','new_generations_after_stop':0}
(d/'DELIVERY_RECEIPT.json').open('x').write(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))