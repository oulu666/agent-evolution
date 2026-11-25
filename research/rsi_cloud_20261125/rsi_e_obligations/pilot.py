"""Reuse historical diagnostic inputs as live regressions on benign lxml exports."""
import argparse,collections,itertools,json
from pathlib import Path
from lxml import etree

# Each witness is an executable input + independent equality obligation.
W=('word','unicode','ident','spaced','namespaced','tail','two_children','comment')
PUBLIC_SCOPES=('text','tree')
B=2
SOURCE={'text':{'strip':36,'ascii':3,'int':1,'upper':15},'tree':{'order':36,'tail':3,'namespace':1,'comment':15}}
STABLE={'text':{'strip':18,'ascii':2,'int':1,'upper':8},'tree':{'order':18,'tail':2,'namespace':1,'comment':8}}
SHIFT={'text':{'strip':2,'ascii':14,'int':13,'upper':0},'tree':{'order':2,'tail':14,'namespace':13,'comment':0}}
UNKNOWN={'text':{'strip':5,'ascii':5,'int':5,'upper':7,'collapse':7},'tree':{'order':5,'tail':5,'namespace':5,'comment':7,'drop_attrs':7}}
METHODS=('none','exact_historical_cache','diagnostic_recency','expected_cover','obligation_basis','full_regression')

def fixture(kind,s):
    r=etree.Element('item',id=str(1000+s))
    if kind=='word':r.text='Invoice '+str(s)
    if kind=='unicode':r.text='Café '+str(s)
    if kind=='ident':r.text='00'+str(10+s)
    if kind=='spaced':r.text=' keep   spaces '+str(s)+' '
    if kind=='namespaced':etree.SubElement(r,'{urn:catal}key').text=str(s)
    if kind=='tail':
        c=etree.SubElement(r,'em');c.text='ship';c.tail=' via rail '+str(s)
    if kind=='two_children':
        etree.SubElement(r,'b').text=str(s);etree.SubElement(r,'a').text='keep order'
    if kind=='comment':r.append(etree.Comment('approved '+str(s)))
    return etree.tostring(r)

def export(v,patch):
    r=etree.fromstring(v)
    if patch=='strip' and r.text:r.text=r.text.strip()
    if patch=='ascii' and r.text:r.text=r.text.encode('ascii','ignore').decode()
    if patch=='int' and r.text and r.text.isdigit():r.text=str(int(r.text))
    if patch=='upper' and r.text:r.text=r.text.upper()
    if patch=='collapse' and r.text:r.text=' '.join(r.text.split())
    if patch=='order' and len(r)>=2:r[:]=sorted(r,key=lambda child:str(child.tag))
    if patch=='tail':
        for child in r:child.tail=None
    if patch=='namespace':
        for child in r:
            if isinstance(child.tag,str) and child.tag.startswith('{'):child.tag=etree.QName(child).localname
    if patch=='comment':
        for child in r:
            if isinstance(child,etree._Comment):r.remove(child)
    if patch=='drop_attrs':r.attrib.clear()
    # All candidate policies meet the new requirement. Regressions concern
    # only previously established obligations for customer records.
    etree.SubElement(r,'summary').text='verified'
    return etree.tostring(r)

def signature(raw):
    r=etree.fromstring(raw)
    return (r.tag,tuple(sorted(r.attrib.items())),r.text,
        tuple((str(c.tag) if isinstance(c.tag,str) else '#comment',c.text,c.tail) for c in r))

def audit(kind,patch,seed):
    old=fixture(kind,seed);out=export(old,patch)
    r=etree.fromstring(out);p=r.find('summary')
    assert p is not None and p.text=='verified'; r.remove(p)
    return signature(old)==signature(etree.tostring(r))

def learn():
    hist={}
    for scope,d in SOURCE.items():
      h={}
      for op,freq in d.items():
        # Retained concrete failing inputs per diagnosed source revision.
        fail={w for w in W if not audit(w,op,0)}
        h[op]=(fail,freq)
      hist[scope]=h
    return hist

def strategy(name,h):
    if name in ('none','exact_historical_cache'):return ()
    if name=='full_regression':return W
    if name=='diagnostic_recency':return tuple(dict.fromkeys(w for op in reversed(h) for w in W if w in h[op][0]))[:B]
    def score(q):
        grouped={body:bool(set(q)&body) for body in {frozenset(a) for a,n in h.values()}}
        mass=sum(n for a,n in h.values() if set(q)&a)
        # Treat repeated counterexamples with the same executable signature
        # as one obligation shape; frequency breaks ties only.
        return (sum(grouped.values()),mass) if name=='obligation_basis' else (mass,)
    return max(itertools.combinations(W,B),key=score)

def main(out):
    h=learn(); result={}
    for regime,dist in (('stable',STABLE),('prior_shift',SHIFT),('new_patch_shape',UNKNOWN)):
      tr={}
      for scope,ops in dist.items():
       for op,n in dict(ops, safe=12).items():
        for j in range(n):
         seed=100+j
         broken={w for w in W if not audit(w,op,seed)}
         for m in METHODS:
          witnesses=strategy(m,h[scope]); failed=False;cost=0
          for w in witnesses:
            cost+=1
            if not audit(w,op,seed):failed=True;break
          q=tr.setdefault(m,dict(n=0,harmful=0,wrong_adopt=0,detected=0,safe_reject=0,calls=0))
          q['n']+=1;q['calls']+=cost;q['harmful']+=bool(broken)
          q['wrong_adopt']+=bool(broken and not failed)
          q['detected']+=bool(broken and failed)
          q['safe_reject']+=bool(not broken and failed)
      result[regime]=tr
    result['selected_witnesses']={m:{scope:strategy(m,h[scope]) for scope in SOURCE} for m in METHODS}
    p=Path(out);p.mkdir(parents=True,exist_ok=True)
    (p/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
