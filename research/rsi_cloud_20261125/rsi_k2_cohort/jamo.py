"""Primary wcwidth case after ordered screening."""
from collections import Counter
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
from unicodedata import normalize

V=('0.2.9','0.2.14')

def cases():
    return [(normalize('NFD',x),2) for x in "가각간갇갈감값강낙났뭉힣"]+[(x,2) for x in '깜꼼']+[('a',1),('x',1)]

def worker(ver,root):
    sys.path.insert(0,root)
    import wcwidth as w
    assert version('wcwidth')==ver and Path(w.__file__).is_relative_to(root)
    c=cases()
    print(json.dumps(dict(raw=[w.wcswidth(s) for s,_ in c],
                          normalized=[w.wcswidth(normalize('NFC',s)) for s,_ in c])))

def main(root):
    runs=[]
    for ver in V:
        where=Path(root,f'wcwidth-{ver}').resolve()
        x=subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),
                          'worker',ver,str(where)],text=True,check=True,capture_output=True)
        runs.append(json.loads(x.stdout))
    old,new=runs
    summary={}
    for name,t in [('old',old['raw']),('native_adapter',old['normalized']),('new',new['raw'])]:
        hits=Counter()
        for i,(observed,(_,expected)) in enumerate(zip(t,cases(),strict=True)):
            block='first_six' if i<6 else 'later_six' if i<12 else 'no_change_control'
            hits[block+'_total']+=1
            hits[block+'_correct']+=observed==expected
        summary[name]=hits
    print(json.dumps(dict(versions=V,results=summary,
                          sample=dict(expected=2,old=old['raw'][0],adapter=old['normalized'][0],new=new['raw'][0])),
                     indent=2,sort_keys=True))

if __name__=='__main__':
    if sys.argv[1]=='worker':worker(*sys.argv[2:])
    else:main(sys.argv[1])
