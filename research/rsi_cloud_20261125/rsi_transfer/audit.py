"""Post-freeze audit: reexecute finite tables to characterize actual scope."""
from collections import Counter,defaultdict
import argparse,json,math
from pathlib import Path
import numpy as np
from main import A,AR,MODES,W,Tool,VERS,tasks

def scope(y):
    lookup={a:int(v) for a,v in zip(A,y)}
    return [j+1 for j in range(4) if any(
        any(lookup[a[:j]+(k,)+a[j+1:]]!=v for k in range(3)) for a,v in lookup.items())]

def main(root,results):
    f=Path(results); worlds=json.loads((f/'worlds.json').read_text())
    x=json.loads((f/'runs.json').read_text())
    assert len(worlds)==192 and len(x)==len(worlds)*len(MODES)
    cases={w['id']:w for w in worlds}
    for k,versions in VERS.items():
        t=[Tool(root,k,v) for v in versions]
        try:
            for i in range(16):
                tables=[np.array([v.go(a,i)[0] for a in range(len(A))]) for v in t]
                for s,d in ((0,0),(1,1),(0,1),(1,0)):
                    rec=cases[f'{k}:{i}:{s}>{d}']
                    old,new=tables[s],tables[d]
                    rec['checks_changed']=int(np.any(old!=new,axis=0).sum())
                    src=[scope(old[:,j]) for j in range(W)]
                    tgt=[scope(new[:,j]) for j in range(W)]
                    ds=[scope(old[:,j]^new[:,j]) for j in range(W)]
                    rec.update(src_scopes=src,target_scopes=tgt,delta_scopes=ds,scope_changed=src!=tgt,
                               delta_smaller=any(len(ds[j])<len(tgt[j]) for j in range(W) if np.any(old[:,j]!=new[:,j])))
                    if rec['visible_headroom']:
                        act=t[d].go(0,i,False)
                        rec.update(input=tasks(k,i)[0],native_source=t[s].go(0,i,False)[1],native_target=act[1])
        finally:
            for p in t:p.close()
    d={}
    for r in x:
        a=r['actions'];v=r['checks'];i=r['attempted'];h=r['hidden_ok']
        assert len(set(a))==len(a)==len(v)
        assert i==next((j+1 for j,c in enumerate(v) if all(c)),0)
        assert (i>0)==(h is not None)
        d[r['id'],r['mode']]=r
    ans={}
    for s,gs in [('all',worlds),('transitions',[w for w in worlds if w['switch']]),
        ('headroom',[w for w in worlds if w['visible_headroom']]),
        ('headroom_scope_changed',[w for w in worlds if w['visible_headroom'] and w['scope_changed']]),
        *[(k,[w for w in worlds if w['tool']==k]) for k in VERS]]:
       ans[s]={}
       for m in MODES:
        r=[d[w['id'],m] for w in gs]
        ans[s][m]={}
        for b in range(1,7):
            a=[p for p in r if 0<p['attempted']<=b]
            ok=sum(q['hidden_ok'] for q in a)
            ans[s][m][str(b)]=dict(correct=ok,wrong=len(a)-ok,deferred=len(gs)-len(a),charged=sum(min(len(q['actions']),b) for q in r))
    (f/'verified.json').write_text(json.dumps(ans,indent=1)+'\n')
    (f/'scope_audit.json').write_text(json.dumps(worlds,indent=1)+'\n')
    print('coverage',Counter((q['switch'],q['delta'],q['scope_changed'],q['visible_headroom'],q['delta_smaller']) for q in worlds))
    for b in (2,3):
        print('budget',b,{m:n[str(b)] for m,n in ans['all'].items()})
    for k in VERS:
        rec=next(q for q in worlds if q['tool']==k and q['visible_headroom'])
        print(rec)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--roots',required=True);p.add_argument('--results',required=True);a=p.parse_args();main(a.roots,a.results)
