"""Read-only Windows Git blob/working-byte verification; --staged before commit or --ref HEAD after.
No credential reads, network, model import, GPU, index write, or history modification.
"""
import pathlib,json,subprocess,hashlib,argparse
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'runs_ext_p15_cpu_closeout_20261119'

def main(ref=None):
 git='/mnt/c/Program Files/Git/bin/git.exe';winroot=subprocess.check_output(['wslpath','-w',str(ROOT)],text=True).strip()
 def command(args,data=None):return subprocess.check_output([git,'-C',winroot]+args,input=data)
 inv=json.loads((OUT/'candidate_inventory.json').read_text());expected=sorted(list(inv['files'])+inv['metadata_files_excluded_from_own_hash_index'])
 assert len(expected)==len(set(expected))
 if ref is None:
  staged=command(['diff','--cached','--name-only','-z']).decode().split('\0');assert sorted(p for p in staged if p)==expected,'staged scope mismatch'
  changes=command(['diff','--cached','--name-status']).decode().splitlines();assert all(s.startswith('A\t') for s in changes),'Only additions allowed in this delivery'
 specs=[f'{ref}:{p}' if ref else ':'+p for p in expected]
 output=command(['cat-file','--batch'],(''.join(s+'\n' for s in specs)).encode());offset=0;total=0
 for path in expected:
  end=output.index(b'\n',offset);header=output[offset:end].split();assert len(header)==3 and header[1]==b'blob',(path,header)
  n=int(header[2]);offset=end+1;blob=output[offset:offset+n];assert output[offset+n:offset+n+1]==b'\n';offset+=n+1
  local=(ROOT/path).read_bytes();digest=hashlib.sha256(blob).hexdigest();assert blob==local,('Git blob changed working bytes',path)
  if path in inv['files']:assert digest==inv['files'][path]['sha256'] and n==inv['files'][path]['bytes']
  total+=n
 assert offset==len(output)
 print(json.dumps({'pass':True,'mode':'ref:'+ref if ref else 'staged','files':len(expected),'bytes':total,'all_git_blob_bytes_equal_working_files':True,'inventory_hashes_checked':True},sort_keys=True))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--ref');main(p.parse_args().ref)
