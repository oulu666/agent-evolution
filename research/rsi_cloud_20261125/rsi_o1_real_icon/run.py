import argparse,hashlib,itertools,json,math,os,time,signal
from collections import Counter
from importlib.metadata import distribution
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps
T=Image.Transpose
G=[None,T.FLIP_LEFT_RIGHT,T.FLIP_TOP_BOTTOM,T.ROTATE_90,T.ROTATE_180,T.ROTATE_270,T.TRANSPOSE,T.TRANSVERSE]
P=[(0,1,2),(1,2,0),(2,0,1)]
HH=list(itertools.product(range(8),range(2),range(3)))
A=((0,0),(1,6),(7,2),(2,3),(4,4),(6,7),(8,0),(0,8),(8,8))
METHODS=('native_fixed','native_entropy','class_minimax','batch_cover','source_saliency')
BASE=Path(__file__).resolve().parent
PLAN=json.loads((BASE/'plan.json').read_text())
def sha(x):return hashlib.sha256(x).hexdigest()
def geo(g,x,y,m):
    return ((x,y),(m-x,y),(x,m-y),(m-y,x),(m-x,m-y),(y,m-x),(y,x),(m-y,m-x))[g]
class Log:
    def __init__(self,path):
        self.f=path.open('x',encoding='utf-8');self.n=0;self.chain='0'*64
    def add(self,**d):
        d['previous_sha256']=self.chain
        self.chain=sha(json.dumps(d,sort_keys=True,separators=(',',':')).encode())
        d['sha256']=self.chain
        self.f.write(json.dumps(d,sort_keys=True)+'\n');self.f.flush();os.fsync(self.f.fileno())
    def act(self,key,kind,fn):
        if self.n>=240:raise RuntimeError('total action limit')
        self.n+=1;self.add(event='start',action=kind,key=key,index=self.n)
        try: result=fn()
        except BaseException as e:
            self.add(event='error',action=kind,key=key,index=self.n,error=repr(e));raise
        self.add(event='end',action=kind,key=key,index=self.n,result=result)
        return result
def transform(im,g,i,p,log,key):
    for name,on,op in [('geometry',g,lambda v:v.transpose(G[g])),
                       ('invert',i,ImageOps.invert),
                       ('cycle',p,lambda v:Image.merge('RGB',[v.split()[k] for k in P[p]]))]:
        if on:
            old=im
            def f():
                nonlocal im
                im=op(old);return sha(im.tobytes())
            log.act(key,name,f)
    return im
def source_predictions(im):
    # The complete source is an already available input for every arm; this is
    # algebraic indexing of that input, never a Pillow repair or a reference query.
    n=im.width
    x,y=np.meshgrid(np.arange(n),np.arange(n))
    s=np.asarray(im,dtype=np.uint32)
    data=[]
    for g,i,p in HH:
        xx,yy=geo(g,x,y,n-1)
        a=s[yy,xx][:,:,list(P[p])]
        if i:a=255-a
        vals=(a[:,:,0]<<16)|(a[:,:,1]<<8)|a[:,:,2]
        data.append(vals.reshape(-1))
    arr=np.array(data)
    rep={}
    cls=[rep.setdefault(row.tobytes(),k) for k,row in enumerate(arr)]
    return arr,np.array(cls),n
def group_counts(z):
    return np.unique(z,return_counts=True)[1]
def source_plan(arr,n):
    # Orbit saliency: rank geometry orbits by permutation/inversion-invariant
    # chromatic/background departure, then tile maximum-distance points.
    # No reference or predicted decision classes enter this rule.
    m=n-1; odds=[]; seen=set()
    p=arr[0]
    colors=((p>>16)&255,(p>>8)&255,p&255)
    C=np.array(colors,dtype=np.int32)
    score=(C.max(axis=0)-C.min(axis=0))+np.minimum(C.sum(axis=0),765-C.sum(axis=0))
    for pos in range(n*n):
        if pos in seen:continue
        x,y=pos%n,pos//n
        orbit={b*n+a for g in range(8) for a,b in [geo(g,x,y,m)]}
        seen.update(orbit)
        peak=int(score[list(orbit)].max())
        odds.append((peak,pos))
    return [pos for _,pos in sorted(odds,key=lambda a:(-a[0],a[1]))[:9]]
def batch_plan(arr,cls):
    # A fixed test set: greedily cover undecided pairs of output classes
    # BEFORE any target pixel is read. Use packed-bit masks of separated pairs.
    pairs=list(itertools.combinations(sorted(set(cls.tolist())),2))
    if not pairs:return []
    u,v=np.array(pairs).T
    separated=np.packbits((arr[u]!=arr[v]).T,axis=1,bitorder='little')
    masks=[int.from_bytes(bytes(z),'little') for z in separated]
    unresolved=(1<<len(pairs))-1; chosen=[]
    for _ in range(9):
        best=max(range(len(masks)),key=lambda j:((masks[j]&unresolved).bit_count(),-j))
        if not masks[best]&unresolved:break
        chosen.append(best);unresolved&=~masks[best]
    return chosen
def run_policy(method,src,target,prepared,log,key):
    # The policy sees only reference returns from query(). Full target comparison is after decision.
    arr,cls,n=prepared
    alive=list(range(len(HH))); path=[]; seen=set()
    if method=='native_fixed':
        plan=[round(y*(n-1)/8)*n+round(x*(n-1)/8) for x,y in A]
    elif method=='batch_cover':plan=batch_plan(arr,cls)
    elif method=='source_saliency':plan=source_plan(arr,n)
    else:plan=None
    for step in range(9):
        if method!='native_fixed' and len(set(cls[alive]))==1:break
        if plan is not None:
            if step>=len(plan):break
            pos=plan[step]
        else:
            r=alive if method=='native_entropy' else sorted(set(cls[alive].tolist()))
            # Collapse identical query partitions by value matrix before scanning.
            picked=arr[r]
            rows=np.unique(picked.T,axis=0,return_index=True)[1]
            def score(k):
                h=group_counts(picked[:,k]).tolist()
                if method=='native_entropy':
                    return (-sum(v*math.log2(v) for v in h),-k)
                return (-max(h),-sum(v*v for v in h),-k)
            allowed=[int(k) for k in rows if int(k) not in seen]
            if not allowed:break
            pos=max(allowed,key=score)
        sample=log.act(key,'target_pixel',lambda:list(target.getpixel((pos%n,pos//n))))
        packed=(sample[0]<<16)|(sample[1]<<8)|sample[2]
        alive=[j for j in alive if arr[j,pos]==packed]
        if not alive:raise AssertionError('menu omitted truth')
        seen.add(pos);path.append([pos%n,pos//n,len(alive),len(set(cls[alive]))])
    remain=len(set(cls[alive]))
    if method!='native_fixed' and remain!=1:
        state=None
    else:
        j=min(alive,key=lambda k:(sum(bool(z) for z in HH[k]),k)) if method!='native_fixed' else alive[0]
        state=transform(src,*HH[j],log,key)
        if sha(state.tobytes())!=sha(np.stack(((arr[j]>>16)&255,(arr[j]>>8)&255,arr[j]&255),axis=-1).astype(np.uint8).tobytes()):
            raise AssertionError('planned vs actual Pillow repair mismatch')
    outcome=log.act(key,'oracle_compare',lambda:('defer' if state is None else
                'correct' if state.tobytes()==target.tobytes() else 'wrong'))
    row=dict(key=key,method=method,outcome=outcome,observations=len(path),queries=path,remaining_artifact_classes=remain)
    log.add(event='case_result',**row);return row
def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);o=p.parse_args().output;o.mkdir()
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('1800 seconds')))
    signal.alarm(1800); log=Log(o/'first_events.jsonl')
    results=[];screen=[];eligible=[]; status='done'
    try:
        d=distribution('ezdxf')
        assert d.version==PLAN['ezdxf'] and distribution('pillow').version==PLAN['pillow']
        for z in PLAN['items']:
            name=z['name'];f=d.locate_file('ezdxf/resources/'+name)
            assert sha(f.read_bytes())==z['sha256']
            rgba=Image.open(f).convert('RGBA')
            assert rgba.size==(64,64)
            target=Image.alpha_composite(Image.new('RGBA',rgba.size,'white'),rgba).convert('RGB')
            src=transform(target,*z['combo'],log,name+'/injected')
            prep=source_predictions(src)
            n=run_policy('native_fixed',src,target,prep,log,name+'/native_fixed')
            screen.append(dict(image=name,screen=n,distinct_classes=len(set(prep[1]))))
            if n['outcome']=='wrong' and len(eligible)<3:eligible.append((name,src,target,prep))
        for name,src,target,prep in eligible:
            for m in METHODS[1:]:
                results.append(run_policy(m,src,target,prep,log,name+'/'+m))
    except BaseException as e:
        status='stopped: '+repr(e);log.add(event='stop',status=status)
    finally:
        signal.alarm(0);log.f.close()
    (o/'FIRST_RUN.sha256').write_text(sha((o/'first_events.jsonl').read_bytes())+'  first_events.jsonl\n')
    cases=[e[0] for e in eligible]
    rows=[x['screen'] for x in screen if x['image'] in cases]+results
    stats={m:dict(outcomes=dict(Counter(r['outcome'] for r in rows if r['method']==m)),
                  observations=sum(r['observations'] for r in rows if r['method']==m))
           for m in METHODS}
    doc=dict(status=status,versions={'ezdxf':PLAN['ezdxf'],'pillow':PLAN['pillow'],'numpy':np.__version__},
             charged=log.n,selected=cases,methods=stats)
    (o/'summary.json').write_text(json.dumps(doc,indent=2)+'\n')
    (o/'dev_cases.json').write_text(json.dumps(dict(screen=screen,alternatives=results),indent=2)+'\n')
    print(json.dumps(doc,indent=2))
    if status!='done':raise SystemExit(1)
if __name__=='__main__':main()
