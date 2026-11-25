"""Replay two immutable, audited third-party gallery cells without shipping their code or images."""
from collections import Counter
import ast
from hashlib import sha256
import io
from importlib.metadata import version
import json
from pathlib import Path
import re
import subprocess
import sys

PINS=('3.9.4','3.10.0','3.10.1')
ORIG_HASH='197dec934f8e404706cf0f95ca092d4032c483a32a1e5d0fd3f38fdd923785bb'
CALLS={'np.random.seed','np.random.rand','np.linspace','np.arange','plt.cm.winter',
       'plt.figure','plt.subplot','ax.bar','ax.set_title','ax.plot','ax.set_rmax',
       'ax.set_rticks','plt.savefig'}
CAN_PARSE=(ast.Assign,ast.Name,ast.Attribute,ast.Call,ast.keyword,ast.Constant,ast.BinOp,
           ast.Mult,ast.Div,ast.List,ast.Tuple,ast.Load,ast.Store,ast.Expr,ast.Module)

def extracted(path):
    raw=Path(path).read_bytes()
    assert sha256(raw).hexdigest()==ORIG_HASH
    [_,rest]=raw.decode().split('### Polar Axis')
    sub=rest.split('### Twin Axes',1)[0]
    f=chr(96)*3
    snippets=re.findall(f+r'python\s*\n(.*?)'+f,sub,flags=re.S)
    assert len(snippets)==6
    for i,src in enumerate(snippets[:4],1):
        tree=ast.parse(src)
        for k in ast.walk(tree):
            assert isinstance(k,CAN_PARSE),type(k)
            if isinstance(k,ast.Call):assert ast.unparse(k.func) in CALLS,ast.unparse(k.func)
            if isinstance(k,ast.Attribute):assert not k.attr.startswith('_'),k.attr
        yield compile(tree,f'audited_gallery_fence_{i}','exec')

def worker(ver,where,caller,mode):
    sys.path.insert(0,where)
    import matplotlib as mpl
    assert version('matplotlib')==ver and Path(mpl.__file__).is_relative_to(where)
    mpl.use('Agg',force=True)
    mpl.rcdefaults()
    import matplotlib.pyplot as plt
    import numpy as np
    from PIL import Image
    dims=[]
    actual_save=plt.savefig
    ctx={'np':np,'plt':plt,'__builtins__':{}}
    def audited_save(name,**kw):
        fig=plt.gcf()
        ax=plt.gca()
        expected=27+len(dims)
        assert Path(name).stem.endswith(str(expected))
        title=ax.get_title()
        if mode=='native':ax.set_title(title,y=1.09)
        b=io.BytesIO()
        actual_save(b,format='webp',**kw)
        with Image.open(b) as raster:assert raster.format=='WEBP' and min(raster.size)>0
        engine=fig.canvas.get_renderer()
        title_bbox=ax.title.get_window_extent(engine)
        labels=[e.get_window_extent(engine) for e in ax.get_xticklabels() if e.get_visible() and e.get_text()]
        matches=[q for q in labels if q.x0<title_bbox.x1 and q.x1>title_bbox.x0]
        assert matches and ax.name=='polar'
        gap=round(min(title_bbox.y0-q.y1 for q in matches),3)
        if expected==27:
            patches=ax.containers[0]
            intact=title=='Polar Bar Chart' and len(patches)==40 and np.allclose(
                [p.get_height() for p in patches],ctx['radii'],rtol=0,atol=1e-12)
        else:
            line=ax.lines[0]
            intact=title=='Polar Line Chart' and np.array_equal(line.get_xdata(),ctx['theta2']) and np.array_equal(
                line.get_ydata(),ctx['radii2'])
        dims.append((gap,bool(intact)))
        plt.close(fig)
    plt.savefig=audited_save
    for program in extracted(caller):exec(program,ctx,ctx)
    assert len(dims)==2
    print(json.dumps(dims))

def main(root,caller):
    report={}
    for ver in PINS:
        dest=(Path(root)/f'matplotlib-{ver}').resolve()
        for mode in (('original','native') if ver=='3.10.0' else ('original',)):
            cmd=[sys.executable,'-I',str(Path(__file__).resolve()),'worker',ver,str(dest),
                 str(Path(caller).resolve()),mode]
            p=subprocess.run(cmd,text=True,capture_output=True,check=True)
            stats=json.loads(p.stdout)
            report[f'{ver}_{mode}']=dict(
                exports=len(stats),positive_gaps=sum(g>0 for g,_ in stats),value_shape_intact=sum(x for g,x in stats),
                pass_all=sum(g>0 and x for g,x in stats),gap_px_range=[min(g for g,_ in stats),max(g for g,_ in stats)])
    print(json.dumps(dict(downstream_sources=1,caller_cells=2,results=report),indent=2,sort_keys=True))

if __name__=='__main__':
    if sys.argv[1]=='worker':worker(*sys.argv[2:])
    else:main(*sys.argv[1:])
