"""Execute real library releases; planner sees only charged target observation vectors."""
import argparse,csv,itertools,json,os,subprocess,sys
from pathlib import Path
from collections import defaultdict
import numpy as np

HERE=Path(__file__).parent; A=list(itertools.product(range(3),repeat=4)); AR=np.array(A)
N=len(A); W=5; B=6
VERS={'width':('wcwidth-0.2.9','wcwidth-0.2.14'),'requirement':('packaging-23.1','packaging-23.2'),'calendar':('python_dateutil-2.8.1','python_dateutil-2.8.2')}
MODES=('reuse','manual_recipe','cold_scope','absolute_transfer','clause_reset','delta_cells','delta_scopes')
SUBS=[c for k in (0,1,2,3,4) for c in itertools.combinations(range(4),k)]
P=np.asarray([sum((3**i*AR[:,j] for i,j in enumerate(c)),start=np.zeros(N,int)) for c in SUBS])
LEN=np.asarray(list(map(len,SUBS)))
CMP=(AR!=0).sum(1); COST=CMP*.0001
RECIPES={'width':(0,2,2,0),'requirement':(1,0,1,0),'calendar':(1,0,0,0)}

def tasks(k,i,hidden=False):
 # Fixed functional requirements and separate sentinel variants; names/dates
 # are repeated scenarios, not additional independently repaired bugs.
 b=i&1;c=bool(i&2);q=i//4
 if k=='width':
  return [(['♥','✈'][q%2]+('\ufe0f' if b else '')),('\u00ad' if c else 'a'),('o\u0308' if not hidden else 'a\u0308'),('Ａ' if q%2==0 else 'Ｋ'),('漢' if not hidden else '字')],[2 if b else 1,1,1,2,2]
 if k=='requirement':
  n=('My-Project','Alpha-Pkg','Pi-Pkg','Beta-Tools')[q]
  a=n+'[fast]>=1'; bb=(n.lower().replace('-','_') if b else n)+'[fast]>=1'
  extra=((' unexpected' if not hidden else ')') if c else '')
  m='python_version >= "3.8"'
  url='https://example.invalid/'+('Alpha' if not hidden else 'DataZ')+str(i)+'.whl'
  return [a,bb,m+extra,m,n+' @ '+url],[True,not c,True,url,n.lower()]
 hour=(10+q if not hidden else 16+q)
 day=6+b if not hidden else 11+b
 date=f'2024-05-{day:02}'
 bad=(f'{hour}:3456' if not hidden else f'{hour}34:56') if c else f'{hour}:34:56'
 return [date+'T'+bad,date+f'T{hour}:34:56',date+f'T{hour}:34:56,5Z',date+'T24:00',date+f'T{hour}3456'],[None if c else date+f'T{hour}:34:56',date+f'T{hour}:34:56',date+f'T{hour}:34:56.500000+00:00',f'2024-05-{day+1:02}T00:00:00',date+f'T{hour}:34:56']

class Tool:
 def __init__(self,root,k,v):
    path=str(Path(root,v).resolve())+os.pathsep+str(Path(root,'six-1.17.0').resolve())
    self.k=k;self.p=subprocess.Popen([sys.executable,'-S',str(HERE/'worker.py'),k],env={**os.environ,'PYTHONPATH':path},stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    self.tag=json.loads(self.p.stdout.readline())['release']; assert self.tag==v.split('-',1)[1],(self.tag,v)
 def go(self,a,i,h=False):
    x,t=tasks(self.k,i,h)
    self.p.stdin.write(json.dumps([A[a],x])+'\n');self.p.stdin.flush()
    ans=json.loads(self.p.stdout.readline())
    ok=tuple(int(type(y) is type(z) and y==z) for y,z in zip(ans,t)) if isinstance(ans,list) and len(ans)==W else (0,)*W
    return ok,ans
 def close(self):self.p.stdin.close();assert self.p.wait()==0

def candidate(h,S,mode):
 ids=np.array([i for i in range(N) if i not in h])
 ii=np.array(list(h));Y=np.array(list(h.values())); pp=np.zeros((len(ids),W))
 for j in range(W):
  sy=S[:,j]; y=Y[:,j]; z=y^sy[ii] if mode.startswith('delta') else y
  if mode=='clause_reset' and np.all(y==sy[ii]):
   pp[:,j]=np.where(sy[ids],.97,.03)
   continue
  basis=range(len(SUBS))
  if mode=='delta_cells':basis=(len(SUBS)-1,)
  preds=[]; ws=[]
  for si in basis:
   col=P[si]; vc=col[ii]; vb=col[ids]
   pos=np.bincount(vc,weights=z,minlength=81); total=np.bincount(vc,minlength=81)
   if np.any((pos>0)&(pos<total)):continue
   observed=total[vb]>0
   if mode.startswith('delta'):
    # Separate variation in the version difference from the old check.
    rho=.12
    p=np.where(observed,pos[vb]>0,rho)
    ep=np.where(sy[ids],1-p,p)
    keys=np.flatnonzero(total)
    t=np.sum(pos[keys]>0)
    logw=t*np.log(rho)+(len(keys)-t)*np.log1p(-rho)
   elif mode=='absolute_transfer':
    # Matched strong baseline: learns target scope, using same source
    # table as a soft prior, without factoring the XOR delta.
    avg=np.bincount(col,weights=sy,minlength=81)
    cnt=np.bincount(col,minlength=81)
    prior=(1+4*avg/(cnt+1e-9))/6
    ep=np.where(observed,pos[vb]>0,prior[vb])
    keys=np.flatnonzero(total); sign=pos[keys]>0
    logw=np.log(np.where(sign,prior[keys],1-prior[keys])).sum()
   else:
    ep=np.where(observed,pos[vb]>0,.5)
    logw=-np.count_nonzero(total)*np.log(2)
   preds.append(ep);ws.append(logw+LEN[si]*np.log(.4))
  ws=np.exp(np.array(ws)-max(ws)); pp[:,j]=np.average(np.stack(preds),axis=0,weights=ws)
 pr=pp.prod(1)
 if max(pr)==0:pr=pp.sum(1)
 tie=(S[ids].sum(1)*1e-6 if mode!='cold_scope' else 0)
 return int(ids[np.argmax(pr+tie-COST[ids])])

def run(roots,out):
    out=Path(out);out.mkdir(exist_ok=True,parents=True)
    records=[]; worlds=[]; matrix={}
    for k,vs in VERS.items():
     tt=[Tool(roots,k,v) for v in vs]
     try:
      for i in range(16):
       # Offline histories identical for all methods. The target full
       # replay below is performed only after all planner decisions.
       offline=[np.array([t.go(a,i)[0] for a in range(N)],dtype=int) for t in tt]
       for s,t in ((0,0),(1,1),(0,1),(1,0)):
        src=offline[s];target=tt[t]; hist=[]
        start=int(np.argmax(src.sum(1)-COST))
        profile=f'{k}:{i}:{s}>{t}'
        for m in MODES:
         h={}; actions=[]; traces=[]; attempted=0; hidden=None
         maxcalls=1 if m in ('reuse','manual_recipe') else B
         for l in range(maxcalls):
          a=A.index(RECIPES[k]) if m=='manual_recipe' else start if l==0 else candidate(h,src,m)
          y,ob=target.go(a,i);h[a]=y;actions.append(a);traces.append(y)
          if all(y):
           attempted=l+1; hidden=bool(all(target.go(a,i,True)[0]));break
         records.append({'id':profile,'tool':k,'case':i,'from':tt[s].tag,'to':target.tag,'mode':m,'attempted':attempted,'hidden_ok':hidden,'actions':actions,'checks':traces})
        actual=offline[t]
        # Direct baseline and feasibility diagnostics only used for scoring.
        worlds.append({'id':profile,'tool':k,'switch':s!=t,'delta':bool(np.any(actual!=src)),
         'visible_headroom':not bool(actual[start].all()) and bool(np.any(actual.sum(1)==W)),
         'best_start_ok':bool(actual[start].all()),'direct_ok':bool(actual[0].all()),
         'visible_attainable':bool(np.any(actual.sum(1)==W))})
     finally:
      for t in tt:t.close()
    for n,d in [('runs',records),('worlds',worlds)]:
     (out/(n+'.json')).write_text(json.dumps(d,indent=1)+'\n')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--roots',required=True);p.add_argument('--out',required=True);a=p.parse_args();run(a.roots,a.out)
