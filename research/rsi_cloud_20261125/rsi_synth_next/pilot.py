"""Synthesize a benign PNG repair expression, then execute actual Pillow."""
import argparse, collections, io, itertools, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

OPS='CHLMRX'
OLD=((),)+tuple((x,) for x in OPS)+(tuple('LX'),tuple('HM'),tuple('MX'))
GRAMMAR=tuple(x for n in range(5) for x in itertools.product(OPS,repeat=n))
TARGETS={'identity':'','rotate':'L','border_after_fade':'XM','fade_after_border':'MX',
         'complex_order':'LMCX','reflected_frame':'HMXL','outside':'D'}
BUDGET=16
BACKGROUND=(255,255,255)
PAD=(220,28,25,103)

def base(seed):
    r=np.random.default_rng(seed)
    h=6+seed%3; w=9+(seed//3)%4
    x=r.integers(0,256,(h,w,4),dtype=np.uint8)
    x[0,0]=(245,25,15,255)
    x[-1,-1]=(5,182,110,81)
    return x

def expected(x,expr):
    """Independent NumPy semantics; no Pillow transformation."""
    for a in expr:
        if a in 'LR':x=np.rot90(x,1 if a=='L' else 3)
        elif a=='H':x=x[:,::-1]
        elif a=='M':
            h,w,c=x.shape
            y=np.empty((h+2,w+2,c),dtype=np.uint8)
            y[...]=PAD[:c];y[1:-1,1:-1]=x;x=y
        elif a=='C':x=x[1:-1,1:-1]
        elif a=='X' and x.shape[2]==4:
            y=x.astype(np.int32)
            x=((y[...,:3]*y[...,3:]+255*(255-y[...,3:])+127)//255).astype(np.uint8)
        elif a=='D':x=x.repeat(2,axis=0).repeat(2,axis=1)
    return x

def apply(x,expr):
    im=Image.fromarray(x)
    for a in expr:
        if a=='L':im=im.transpose(Image.Transpose.ROTATE_90)
        elif a=='R':im=im.transpose(Image.Transpose.ROTATE_270)
        elif a=='H':im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif a=='M':im=ImageOps.expand(im,border=1,fill=PAD if im.mode=='RGBA' else PAD[:3])
        elif a=='C':
            w,h=im.size
            if w<=2 or h<=2:return None
            im=im.crop((1,1,w-1,h-1))
        elif a=='X' and im.mode=='RGBA':
            white=Image.new('RGB',im.size,BACKGROUND)
            white.paste(im,mask=im.getchannel('A'));im=white
        elif a=='D':im=im.resize((im.width*2,im.height*2),Image.Resampling.NEAREST)
    f=io.BytesIO();im.save(f,format='PNG');f.seek(0)
    with Image.open(f) as im:return np.array(im)

def md(x,expr):
    h,w,c=x.shape
    ds=[]
    for a in expr:
        ds.append((h,w,c))
        if a in 'LR':h,w=w,h
        elif a=='M':h,w=h+2,w+2
        elif a=='C':h,w=h-2,w-2
        elif a=='X':c=3
        if min(h,w)<=0:return None
    return (h,w,c),ds

def project(x,expr,trace,r,c):
    """Trace one output coordinate back through the expression."""
    flatten=False
    for a,(h,w,ch) in zip(expr[::-1],trace[::-1]):
        if a=='L':r,c=c,w-1-r
        elif a=='R':r,c=h-1-c,r
        elif a=='H':c=w-1-c
        elif a=='M':
            r-=1;c-=1
            if not(0<=r<h and 0<=c<w):
                p=PAD[:ch]
                break
        elif a=='C':r+=1;c+=1
        elif a=='X' and ch==4:flatten=True
    else:p=tuple(map(int,x[r,c]))
    if flatten and len(p)==4:p=tuple((y*p[3]+255*(255-p[3])+127)//255 for y in p[:3])
    return p

def run(out):
    rows=[]
    for name,spec in TARGETS.items():
      for seed in range(8):
        x=base(seed); goal=expected(x,spec); hh,ww,_=goal.shape
        points={(0,0),(hh-1,ww-1),(hh//2,ww//2),(0,ww-1),(hh//3,ww//3)}
        wanted={p:tuple(map(int,goal[p])) for p in points}
        def verified(z):return z is not None and z.shape==goal.shape and all(tuple(map(int,z[p]))==v for p,v in wanted.items())
        # Declared common manual solution table, intentionally strong: spec is available to
        # a human. D is still out of declared grammar; no hidden privilege to resize.
        man=spec if set(spec)<=set(OPS) else None
        def choose(mode):
            if mode=='old':iterable=OLD
            elif mode=='manual':iterable=(man,) if man is not None else ()
            else:iterable=GRAMMAR
            n=0;nprobe=0
            for expr in iterable:
                nprobe+=1
                desc=md(x,expr)
                if mode in ('shape_exhaustive','project_synth') and (not desc or desc[0]!=goal.shape):continue
                if mode=='project_synth' and any(project(x,expr,desc[1],*p)!=v for p,v in wanted.items()):continue
                n+=1
                zz=apply(x,expr)
                if verified(zz):return ("correct" if np.array_equal(zz,goal) else "wrong",n,nprobe,''.join(expr))
                if n==BUDGET:break
            return "defer",n,nprobe,None
        for m in ('old','exhaustive','shape_exhaustive','project_synth','manual'):
          v,n,npb,q=choose(m);rows.append(dict(task=name,seed=seed,method=m,outcome=v,executions=n,expressions_examined=npb,expr=q))
    p=Path(out);p.mkdir(parents=True,exist_ok=True)
    agg={}
    for group in ('all',*TARGETS):
       agg[group]={}
       for m in ('old','exhaustive','shape_exhaustive','project_synth','manual'):
          rr=[r for r in rows if r['method']==m and (group=='all' or group==r['task'])]
          agg[group][m]={'n':len(rr),**collections.Counter(r['outcome'] for r in rr),'executions':sum(r['executions'] for r in rr),'expressions_examined':sum(r['expressions_examined'] for r in rr)}
    (p/'summary.json').write_text(json.dumps(agg,ensure_ascii=False,indent=2)+'\n')
    (p/'decisions.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(agg,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True)
    run(p.parse_args().out)
