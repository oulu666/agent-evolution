"""Pillow public API removals in a benign ICC label export."""
import argparse,collections,io,json,os,subprocess,sys,warnings
from pathlib import Path

MODES=('legacy','cms_only','draw_only','documented','guarded','eager_fallback')
CASES=24
def child():
    import PIL
    from PIL import Image,ImageCms,ImageDraw
    warnings.simplefilter('ignore', DeprecationWarning)
    rows=[]
    for n in range(CASES):
      w,h=25+n%4,15+n%3
      base=(34+n,70+n%12,134+n%7); red=(200+n%25,85,94)
      for method in MODES:
       stages=[];success=False;profile_ok=False;pixels_ok=False
       try:
        stages.append('cms_enter')
        if method in ('cms_only','documented'):flag=ImageCms.Flags.NOCACHE
        elif method=='guarded':flag=ImageCms.Flags.NOCACHE if hasattr(ImageCms,'Flags') else ImageCms.FLAGS['NOTCACHE']
        elif method=='eager_fallback':flag=getattr(ImageCms.Flags,'NOCACHE',ImageCms.FLAGS['NOTCACHE'])
        else:flag=ImageCms.FLAGS['NOTCACHE']
        im=Image.new('RGB',(w,h),base)
        p=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
        im=ImageCms.profileToProfile(im,p,p,flags=flag,outputMode='RGB')
        stages.append('cms_exit')
        stages.append('draw_enter')
        if method in ('draw_only','documented','guarded','eager_fallback'):d, factory=ImageDraw.getdraw(im)
        else:d,factory=ImageDraw.getdraw(im,hints=None)
        d.rectangle((3,3,8,8),factory.Brush("#%02x%02x%02x" % red))
        stages.append('draw_exit')
        b=io.BytesIO();im.save(b,format='PNG',icc_profile=im.info['icc_profile'])
        with Image.open(io.BytesIO(b.getvalue())) as verify:
            profile_ok=bool(verify.info.get('icc_profile')) and verify.info['icc_profile']==p.tobytes()
            pixels_ok=verify.mode=='RGB' and verify.size==(w,h) and verify.getpixel((4,4))==red and verify.getpixel((w-2,h-2))==base
        success=profile_ok and pixels_ok
        exception=None
       except (AttributeError,TypeError) as e: exception=type(e).__name__
       rows.append(dict(version=PIL.__version__,case=n,method=method,stages=stages,success=success,icc_ok=profile_ok,pixels_ok=pixels_ok,exception=exception))
    print(json.dumps(rows))

def parent(roots,target):
    rows=[]
    for name in ('10.4.0','12.0.0'):
        loc=str(Path(roots,name).resolve())
        e={**os.environ,'PYTHONPATH':loc}
        raw=subprocess.check_output([sys.executable,'-S',__file__,'--child'],env=e,text=True)
        d=json.loads(raw);assert all(r['version']==name for r in d);rows+=d
    m={}
    for r in rows:
       y=m.setdefault(r['version'],{}).setdefault(r['method'],dict(n=0,correct=0,fail_cms=0,fail_draw=0,failed_verify=0))
       y['n']+=1;y['correct']+=r['success']
       if r['exception']:y['fail_draw' if 'draw_enter'in r['stages'] else 'fail_cms']+=1
       elif not r['success']:y['failed_verify']+=1
    # Symptom inferred from full stage intervention rather than replacing only
    # the first visible failure, by swapping each change separately.
    p=Path(target);p.mkdir(parents=True,exist_ok=True)
    (p/'summary.json').write_text(json.dumps(m,indent=2)+'\n')
    print(json.dumps(m))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--child',action='store_true');p.add_argument('--roots');p.add_argument('--out'); a=p.parse_args()
 if a.child:child()
 else:parent(a.roots,a.out)
