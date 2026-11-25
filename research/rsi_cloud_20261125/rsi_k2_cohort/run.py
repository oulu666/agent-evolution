"""Three documented, ordinary functional changes in isolated actual public wheels."""
from collections import Counter
import io
import json
from pathlib import Path
import subprocess
import sys
from importlib.metadata import version
from unicodedata import normalize

PINS={'pillow':('10.4.0','12.0.0'),'click':('8.3.3','8.4.0'),'wcwidth':('0.2.9','0.2.14')}

def pillow_case(i,compat):
    from PIL import Image
    w,h=3+i%4,2+i%3
    rb=(20+i,130-i,40+i)
    rf=(90+i,9*i%255,150-i)
    pal=[0,0,0,*rb,*rf]+[0]*759
    b=Image.new('P',(w,h));f=Image.new('P',(w,h))
    for image in (b,f):image.putpalette(pal);image.info['transparency']=0
    overlay=[2 if i>=12 or ((j+i)%3==0) else 0 for j in range(w*h)]
    b.putdata([1]*(w*h));f.putdata(overlay)
    if compat:b,f=(x.convert('RGBA') for x in (b,f))
    out=io.BytesIO()
    b.save(out,format='PNG',save_all=True,append_images=[f],duration=[100,120],blend=[0,1],disposal=[0,0])
    out.seek(0)
    im=Image.open(out);im.seek(1)
    return list(im.convert('RGBA').tobytes())

def click_case(i,compat):
    from click import HelpFormatter
    prog=f'report{i}-{i%5}'; args='' if i<12 else '[FILES]'
    f=HelpFormatter(width=80,max_width=80)
    if compat and not args:f.write(f'Usage: {prog}\n')
    else:f.write_usage(prog,args)
    return f.getvalue()

def text_case(i):
    return f'view{i}:中'+('\u00ad'*(1+i%3) if i<12 else '-')+'end'

def wc_case(i,compat):
    from wcwidth import wcwidth,wcswidth
    s=text_case(i)
    return sum(1 if ch=='\u00ad' else wcwidth(ch) for ch in s) if compat else wcswidth(s)

def reference(family,i):
    if family=='pillow':
        w,h=3+i%4,2+i%3
        back=(20+i,130-i,40+i,255); front=(90+i,9*i%255,150-i,255)
        # Independent two-layer model: a fully transparent foreground maintains each independently chosen background color.
        standin=[front if i>=12 or ((j+i)%3==0) else back for j in range(w*h)]
        return [c for pixel in standin for c in pixel]
    if family=='click':return f'report{i}-{i%5}'.join(('Usage: ', '\n' if i<12 else ' [FILES]\n'))
    return sum(2 if ch=='中' else 1 for ch in text_case(i))

def jamo_probe():
    from wcwidth import wcswidth
    sample="가각간갇갈감값강낙났뭉힣"
    return [wcswidth(normalize('NFD',x)) for x in sample]

def worker(name,ver,root):
    sys.path.insert(0,root)
    mod=__import__('PIL' if name=='pillow' else name)
    assert version(name)==ver and Path(mod.__file__).is_relative_to(root),mod.__file__
    fn={'pillow':pillow_case,'click':click_case,'wcwidth':wc_case}[name]
    out={'raw':[fn(i,False) for i in range(16)],'adapter':[fn(i,True) for i in range(16)]}
    if name=='wcwidth':out['jamo']=jamo_probe()
    print(json.dumps(out))

def main(root):
    panel={}
    for name,versions in PINS.items():
        raw={}
        for v in versions:
            cmd=[sys.executable,'-I',str(Path(__file__).resolve()),'worker',name,v,str((root/f'{name}-{v}').resolve())]
            p=subprocess.run(cmd,text=True,capture_output=True,check=True)
            raw[v]=json.loads(p.stdout)
        old,new=(raw[v] for v in versions)
        results={}
        for method,outputs in [('old',old['raw']),('native_adapter',old['adapter']),('new',new['raw'])]:
            hits=Counter()
            for i,o in enumerate(outputs):
                block='first_six' if i<6 else 'later_six' if i<12 else 'no_change_control'
                hits.update(total=1,correct=int(o==reference(name,i)))
                hits[block+'_total']+=1
                hits[block+'_correct']+=o==reference(name,i)
            results[method]=hits
        entry=dict(versions=versions,results=results,example=dict(
            expected=reference(name,0),actual_old=old['raw'][0],new=new['raw'][0],adapter=old['adapter'][0]))
        if name=='wcwidth':entry['screened_jamo_no_difference']=old['jamo']==new['jamo']==[2]*12
        panel[name]=entry
    print(json.dumps(dict(panel=panel),sort_keys=True,indent=2))

if __name__=='__main__':
    if sys.argv[1]=='worker':worker(*sys.argv[2:])
    else:main(Path(sys.argv[1]))
