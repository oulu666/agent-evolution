"""Passive observation inventory and type-guided ranking on real functional tools."""
import argparse,decimal,hashlib,inspect,io,itertools,json,random,re
from collections import Counter
from pathlib import Path
from PIL import Image, PngImagePlugin
D=decimal.Decimal
CASES=('loss','rounded','density','tag')
MISSING='∅'
TYPE={'loss':'bool','rounded':'bool','density':'tuple','tag':'str'}
TASK={
 'loss':'nonzero numeric digits were discarded, send for review',
 'rounded':'decimal representation digits were removed, even if zero',
 'density':'print resolution dots per inch exceeds threshold',
 'tag':'workflow status annotation marks draft for review'}
EXPERT={'loss':'flags.Inexact','rounded':'flags.Rounded',
        'density':'info.dpi','tag':'info.workflow'}
MODES=('endpoint','lexical','generic','shape','all_scan','expert')
CAP=3

def native(kind,i,label,cal):
    nuisance=label if cal else ((i+label)//2)%2
    if kind in ('loss','rounded'):
        ctx=decimal.Context(prec=9+int(nuisance))
        v=i%8+1
        if kind=='loss':raw=f'{v}.20{1 if label else 0}'
        else:raw=f'{v}.200' if label else f'{v}.20'
        end=ctx.quantize(D(raw),D('.01'))
        return ctx,format(end,'f')
    buf=io.BytesIO(); image=Image.new('RGB',(8+i%4,7+i%3),(i%250,60,100))
    pix=hashlib.sha256(image.tobytes()).hexdigest()
    p=PngImagePlugin.PngInfo()
    if kind=='tag':
        p.add_text('workflow','draft' if label else 'ready')
        dpi=(300 if nuisance else 72)
    else:
        p.add_text('workflow','draft' if nuisance else 'ready')
        dpi=(300 if label else 72)
    p.add_text('project','red' if nuisance else 'blue')
    image.save(buf,format='PNG',pnginfo=p,dpi=(dpi,dpi))
    buf.seek(0)
    with Image.open(buf) as new:
        new.load()
        assert pix==hashlib.sha256(new.tobytes()).hexdigest()
        return new.copy(),pix

def scalar(z):
    return type(z) in (bool,int,float,str) or (isinstance(z,tuple) and len(z)<=4 and all(type(x) in (int,float,str,bool) for x in z))
def inventory(obj):
    d={}
    try: ctor=set(inspect.signature(type(obj)).parameters)
    except (TypeError,ValueError):ctor=set()
    for name in sorted(set(dir(obj))|ctor):
        if name.startswith('_'):continue
        one=inspect.getattr_static(obj,name,None)
        # Limit runtime reads to public concrete data, native stored
        # members, and the Pillow stored metadata dictionary.
        if callable(one):continue
        if isinstance(one,property) and type(obj).__module__!='decimal':continue
        val=getattr(obj,name,None)
        if scalar(val): d[name]=val
        elif isinstance(val,dict) or (isinstance(obj,decimal.Context) and hasattr(val,'keys')):
            for k in val.keys():
                z=val[k]
                if scalar(z):d[f'{name}.{k if isinstance(k,str) else k.__name__}']=z
    return d

def kindof(v):return type(v).__name__
def fit(vals,ys):
    mp={}
    for v,y in zip(vals,ys):
        if v in mp and mp[v]!=y:return None
        mp[v]=y
    return mp if len(mp)>=2 else None

def run(out):
 p=Path(out);p.mkdir(parents=True,exist_ok=True);summary={}
 for case in CASES:
    train=[];audit=[];rows=[]
    for i in range(6):
     for y in (0,1):
      o,ep=native(case,1+i,y,True);train.append((inventory(o),ep,y))
    for i in range(30,54):
     pair=[]
     for y in (0,1):
      o,ep=native(case,i,y,False);pair.append(ep);audit.append((inventory(o),ep,y))
     assert pair[0]==pair[1],(case,i)
    # Inventory shape is from unlabeled training objects, no gold port.
    col={}
    for signals,_,_ in train:
      for k,v in signals.items():col.setdefault(k,kindof(v))
    vocab=set(re.findall(r'[a-z]+',TASK[case].lower()))
    def lex(k):
        words=set(re.findall(r'[a-z]+',re.sub(r'([a-z])([A-Z])',r'\1 \2',k).lower()))
        return -len(words&vocab),k
    ys=[x[2] for x in train]
    s={}
    for m in MODES:
      if m=='endpoint':
         keys=['endpoint']
      elif m=='lexical':keys=sorted(col,key=lex)[:CAP]
      elif m=='generic':keys=sorted(col)[:CAP]
      elif m=='shape':keys=sorted(col,key=lambda k:(col[k]!=TYPE[case],lex(k)))[:CAP]
      elif m=='all_scan':keys=sorted(col)
      else:keys=[EXPERT[case]]
      def extract(row,k):return row[1] if k=='endpoint' else row[0].get(k,MISSING)
      trained=[]
      for k in keys:
         h=fit([extract(q,k) for q in train],ys)
         if h is not None:trained.append((k,h))
      stats=Counter(ok=0,wrong=0,defer=0)
      for row in audit:
         if not trained:stats['defer']+=1;continue
         if m=='all_scan':
            guesses=[h[extract(row,k)] for k,h in trained if extract(row,k) in h]
            d=guesses[0] if len(set(guesses))==1 else None
         else:
            k,h=trained[0]; d=h.get(extract(row,k))
         stats['defer' if d is None else 'ok' if d==row[2] else 'wrong']+=1
      s[m]=dict(stats,ports_learned=len(trained),reads_for_calibration=len(keys)*len(train),
             selected=trained[0][0] if trained else None, candidate_reads=len(keys), n=len(audit))
    oracle_k=EXPERT[case]
    assert oracle_k in col and s['expert']['ok']==48,s['expert']
    summary[case]={'observer_count':len(col),'methods':s}
 (p/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps(summary,indent=2))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--out',required=True);run(a.parse_args().out)
