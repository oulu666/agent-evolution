"""Counterfactual validation of candidate observation points on actual lxml reports."""
import argparse, collections, itertools, json, random, re
from pathlib import Path
from lxml import etree
REGIMES=('clean','marginal_trap','no_valid_observer','unannounced_shift')
N=32
MODES=('positive','single_axis','matched_mean','matched_exact','factorial_gate')

def value(s):
    v=re.sub(r'[\s,]', '',s)
    return int(v) if re.fullmatch(r'-?\d+',v) else ' '.join(s.split())

def extract(xml):
    root=etree.fromstring(xml)
    tree=root.getroottree();o={}
    for e in root.iter():
        p=tree.getpath(e)
        if e.text and e.text.strip():o[p+'/#text']=value(e.text)
        for k,v in e.attrib.items():o[p+'/[@'+k+']']=value(v)
    return o

def render(seed,role,signal,x,y,regime,test):
    g=random.Random(seed*19+role*127)
    base=1200+g.randrange(600); charge=11+g.randrange(24)
    total=base+charge*signal
    root=etree.Element('ledger')
    a=etree.SubElement(root,'a_audit')
    # This mirror looks perfect when axes are only assessed individually.
    interaction=x*y if regime!='clean' else x
    a.text=str(total+19*interaction)
    a.set('schema_serial',str(role+10*x+100*y))
    md=etree.SubElement(root,'b_meta')
    md.text=str(base+charge*int(bool(signal or x)))
    md.set('run',str(seed+1000*x+10000*y))
    t=etree.SubElement(root,'z_visible_total')
    if regime=='no_valid_observer':
        t.text=str(total+11*y)
    elif regime=='unannounced_shift' and test:
        # Same shape and name but a benign missing charge after a version swap.
        t.text=str(base if not signal else base)
    else:
        t.text=f'  {total:,}  ' if x else str(total)
    return etree.tostring(root,pretty_print=bool(y)),total

def inspect(task):
    docs={}
    for (s,x,y) in itertools.product(range(2),repeat=3):
        payload,truth=task(s,x,y)
        docs[s,x,y]=(extract(payload),truth)
    paths=sorted(set.intersection(*(set(o) for o,_ in docs.values())))
    pairs=list(itertools.combinations(sorted(docs),2))
    def label(p,q):return docs[p][1]!=docs[q][1]
    def evidence(key,p,q):return docs[p][0][key]!=docs[q][0][key]
    POS=[(p,q) for p,q in pairs if p[1:]==q[1:]]
    CROSS=[(p,q) for p,q in pairs if p[0]==q[0]]
    AXIS=[(p,q) for p,q in CROSS if (sum(a!=b for a,b in zip(p,q))==1 and (p[1:]==(0,0) or q[1:]==(0,0)))]
    return paths,POS,CROSS,AXIS,pairs,label,evidence

def decide(model,method):
    paths,pos,nuis,axis,allpairs,label,diff=model
    count=lambda p,ls:sum(int(diff(p,x,y)!=label(x,y)) for x,y in ls)
    if method=='positive':
        return min(paths,key=lambda p:count(p,pos))
    if method=='single_axis':
        return min(paths,key=lambda p:count(p,pos+axis))
    if method=='matched_mean':
        best=min(paths,key=lambda p:count(p,pos)/len(pos)+count(p,nuis)/len(nuis))
        return best if count(best,pos)<len(pos) else None
    if method=='matched_exact':
        return next((p for p in paths if not count(p,allpairs)),None)
    # Four same-context signal pairs plus two nuisance subcubes.
    return next((p for p in paths if not count(p,pos) and not count(p,nuis)),None)

def run(out):
 rows=[]
 for reg,seed in itertools.product(REGIMES,range(N)):
    train=inspect(lambda s,x,y:render(seed,0,s,x,y,reg,False))
    test=inspect(lambda s,x,y:render(seed+61,1,s,x,y,reg,True))
    for method in MODES:
        path=decide(train,method)
        labels=[(p,q,z) for (p,q),z in [(k,0) for k in test[2]]+[(k,1) for k in test[1]]]
        mistakes=[int(test[-1](path,p,q)!=z) for p,q,z in labels] if path in test[0] else []
        rows.append(dict(regime=reg,seed=seed,method=method,path=path,
                         correct=int(bool(mistakes) and not any(mistakes)),
                         wrong=int(bool(mistakes) and any(mistakes)),defer=int(not mistakes),
                         false_alarms=sum(m for m,(_,_,z) in zip(mistakes,labels) if not z),
                         misses=sum(m for m,(_,_,z) in zip(mistakes,labels) if z)))
 p=Path(out);p.mkdir(parents=True,exist_ok=True)
 agg={}
 for reg in (*REGIMES,'whole'):
    agg[reg]={}
    for method in MODES:
        sub=[r for r in rows if (r['regime']==reg or reg=='whole') and r['method']==method]
        agg[reg][method]={"n":len(sub),**{key:sum(r[key] for r in sub) for key in ('correct','wrong','defer','false_alarms','misses')}}
 (p/'summary.json').write_text(json.dumps(agg,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(agg,ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True)
 run(p.parse_args().out)
