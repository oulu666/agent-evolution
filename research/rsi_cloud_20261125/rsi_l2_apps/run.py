"""Two benign numerical/rendering regressions, fresh pinned workers, aggregate only."""
from collections import Counter
import io
import json
from pathlib import Path
import subprocess
import sys
from importlib.metadata import version

PINS={'scikit_learn':('scikit-learn','sklearn',('1.5.2','1.7.2','1.8.0')),
      'matplotlib':('matplotlib','matplotlib',('3.9.4','3.10.0','3.10.1'))}

def tree_case(i,adapt):
    from sklearn.tree import DecisionTreeClassifier
    near=1e-8*(1+i/20) if i<12 else .015
    y=[(j+i)%2 for j in range(16)]
    # Feature 0 fits training perfectly, but is below the stated instrument noise on witness rows.
    x=[[yj*near,3*(yj if j!=i%16 else 1-yj)+(j%4)*.01] for j,yj in enumerate(y)]
    desired=1 if i<12 else 0
    probes=[[near*z if i>=12 else (1-z)*near,3*z] for z in (0,1,0,1)]
    if adapt:
        mask=[max(row[j] for row in x)-min(row[j] for row in x)<=1e-7 for j in range(2)]
        x,probes=([[0.0 if mask[j] else val for j,val in enumerate(row)] for row in arr] for arr in (x,probes))
    clf=DecisionTreeClassifier(max_depth=1,random_state=i).fit(x,y)
    return (int(clf.tree_.feature[0])==desired and list(clf.predict(probes))==[0,1,0,1])

def plot_case(i,adapt):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    polar=i<12
    fig=Figure(figsize=(6.0+.2*(i%3),4.8+.15*(i%4)),dpi=88+i%5)
    FigureCanvasAgg(fig)
    ax=fig.add_subplot(1,1,1,projection='polar' if polar else None)
    x=[.05,1.0+(i%3)/10];y=[.15,1.0+(i%2)/10]
    p=ax.plot(x,y,color=('blue','red','black')[i%3])[0]
    if adapt and polar:
        fig.subplots_adjust(top=.78)
        ax.set_title(f'Plot measure {i}',y=1.21)
    else:ax.set_title(f'Plot measure {i}')
    buf=io.BytesIO()
    fig.savefig(buf,format='png')
    assert buf.getvalue()[:8]==b'\x89PNG\r\n\x1a\n'
    r=fig.canvas.get_renderer()
    title=ax.title.get_window_extent(r)
    # Compare actual drawn text rectangles, not library's title-placement method or pixels from a known-good release.
    labels=[e.get_window_extent(r) for e in ax.get_xticklabels()
            if e.get_visible() and e.get_text()]
    overlapping=[z for z in labels if z.x0<title.x1 and title.x0<z.x1]
    gap=min((title.y0-z.y1 for z in overlapping),default=1000.)
    intact=list(p.get_xdata())==x and list(p.get_ydata())==y
    return bool((gap>0 and title.y1<=fig.bbox.y1 and intact) if polar else
                (title.y0>ax.bbox.y1 and title.y1<=fig.bbox.y1 and intact))

def worker(name,pin,role,path):
    sys.path.insert(0,path)
    pkg,mod,_=PINS[name]
    module=__import__(mod)
    assert version(pkg)==pin and Path(module.__file__).is_relative_to(path)
    f=tree_case if name=='scikit_learn' else plot_case
    out={'raw':[f(i,False) for i in range(16)]}
    if role=='failed':out['native']=[f(i,True) for i in range(16)]
    print(json.dumps(out))

def main(r):
    result={}
    for name,(_,_,versions) in PINS.items():
        output={}
        for role,pin in zip(('earlier','failed','fixed'),versions,strict=True):
            cmd=[sys.executable,'-I',str(Path(__file__).resolve()),'worker',name,pin,role,
                 str((r/f'{name}-{pin}').resolve())]
            worker_run=subprocess.run(cmd,text=True,capture_output=True,check=True)
            got=json.loads(worker_run.stdout)
            output[role]=got['raw']
            if 'native' in got:output['native_same_version']=got['native']
        tallies={}
        for key,rows in output.items():
            tallies[key]=dict(witness_pass=sum(rows[:12]),witness_total=12,
                              control_pass=sum(rows[12:]),control_total=4)
        strict=[i for i in range(12) if output['earlier'][i] and not output['failed'][i] and output['fixed'][i]]
        result[name]=dict(versions=versions,strategies=tallies,strict_witnesses=len(strict))
    print(json.dumps(dict(result=result),sort_keys=True,indent=2))

if __name__=='__main__':
    if sys.argv[1]=='worker':worker(*sys.argv[2:])
    else:main(Path(sys.argv[1]))
