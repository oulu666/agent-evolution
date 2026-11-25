"""Online regression auditing after drift in a real lxml export workflow."""
import argparse,collections,itertools,json,math,random
from pathlib import Path
from lxml import etree
REG=('steady','tagged_switch','untagged_switch','recurrent_tags')
METHODS=('static','window','discounted','version_window','surprise_reuse','full')
P=6;T=120;SEEDS=16
A=(.32,.30,.07,.05,.03,.03,.20)
B=(.05,.03,.34,.31,.04,.03,.20)
C=(.10,.07,.05,.03,.30,.25,.20)

def mk(witness,i):
    x=etree.Element('item',item=str(i))
    if witness==0:x.text='  protect spaces  '
    if witness==1:x.text='保留 Café'
    if witness==2:x.text=f'{i+1:07d}'
    if witness==3:x.append(etree.Comment('keep'))
    if witness==4:
        c=etree.SubElement(x,'em');c.text='mixed';c.tail=' preserve tail '
    if witness==5:etree.SubElement(x,'{urn:test}code').text='preserve ns'
    return x

def audit(witness,mode,i):
    x=mk(witness,i); goal=etree.tostring(x,with_tail=False)
    if mode==0 and x.text:x.text=x.text.strip()
    elif mode==1 and x.text:x.text=x.text.encode('ascii','ignore').decode()
    elif mode==2 and x.text and x.text.isdigit():x.text=str(int(x.text))
    elif mode==3:
        for c in x:
            if isinstance(c,etree._Comment):x.remove(c)
    elif mode==4:
        for c in x:
            if c.tail:c.tail=None
    elif mode==5:
        for c in x:
            if c.tag.startswith('{'):c.tag=etree.QName(c).localname
    # A proposed update satisfies the new obligation, independent of regression.
    out=etree.SubElement(x,'summary');out.text='updated'
    read=etree.fromstring(etree.tostring(x))
    assert read.find('summary').text=='updated'
    read.remove(read.find('summary'))
    return etree.tostring(read,with_tail=False)!=goal

def setting(reg,t):
    if reg=='steady':return 'v1',A
    if reg=='tagged_switch':return ('v1',A) if t<60 else ('v2',B)
    if reg=='untagged_switch':return 'v1',A if t<60 else B
    return ('v1',A) if t in range(0,30) or t in range(60,90) else ('v2', C)

def choose(method,mem,tag,t):
    if method=='static':return sorted(range(P),key=lambda w:(-A[w],w))[:2]
    if method=='full':return range(P)
    h=mem[0] if method in ('window','discounted') else mem[1][tag]
    s=[]
    for w in range(P):
        if method=='discounted':
            seq=[(.97**(t-u),x) for u,x in h[w]]
        else:
            seq=[(1,x) for u,x in h[w] if t-u<=28 or method=='surprise_reuse']
            if method=='surprise_reuse':
                # Reuse history for observable returning versions, but discard
                # a local span on an unusual run of actual paid responses.
                seq=seq[-40:]
        n=sum(q for q,_ in seq);v=sum(q*x for q,x in seq)
        rank=(v+4*A[w])/(n+4)+.75*math.sqrt(math.log(2+t)/(n+4))
        s.append(rank)
    return sorted(range(P),key=lambda w:(-s[w],w))[:2]

def observe(method,mem,tag,t,w,y):
    mem[0][w].append((t,y)); h=mem[1][tag][w];h.append((t,y))
    if method=='surprise_reuse' and len(h)>=16:
        past=[v for _,v in h[:-7]]
        recent=[v for _,v in h[-7:]]
        avg=(sum(past)+1)/(len(past)+2)
        p=1.
        if sum(recent)==0:p=(1-avg)**7
        if sum(recent)==7:p=avg**7
        if p<.08:del h[:-7]

def sim(out):
  summary={};pair={}
  for reg in REG:
    rr={}
    for k in range(SEEDS):
      r=random.Random(k+8809);stream=[]
      for t in range(T):
        tag,prior=setting(reg,t)
        mode=r.choices(range(7),weights=prior)[0]
        hidden=[audit(w,mode,1000*k+t) for w in range(P)]
        stream.append((tag,mode,hidden))
      for m in METHODS:
        mem=([[] for _ in range(P)],collections.defaultdict(lambda:[[] for _ in range(P)]))
        cnt=rr.setdefault(m,dict(n=0,bad=0,wrong=0,calls=0,wrong_post=0,wrong_reentry=0))
        for t,(tag,mode,hidden) in enumerate(stream):
          # Policy can only read its own paid lxml audits, not offline hidden.
          ws=choose(m,mem,tag,t); discovered=False
          for w in ws:
            y=audit(w,mode,1000*k+t);assert y==hidden[w]
            discovered|=y
            observe(m,mem,tag,t,w,y)
            cnt['calls']+=1
          wrong=any(hidden) and not discovered
          cnt['n']+=1;cnt['bad']+=any(hidden);cnt['wrong']+=wrong
          cnt['wrong_post']+=bool(wrong and t>=60)
          cnt['wrong_reentry']+=bool(wrong and any(z<=t<z+7 for z in (30,60,90)))
    summary[reg]=rr
  p=Path(out);p.mkdir(parents=True,exist_ok=True)
  (p/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
  print(json.dumps(summary))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);sim(p.parse_args().out)
