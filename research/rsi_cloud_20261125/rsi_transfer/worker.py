"""Benign task adapters: call the selected real package, then serialize the artifact."""
import json,re,sys,unicodedata,datetime
from importlib.metadata import version

kind=sys.argv[1]
print(json.dumps({'release':version({'width':'wcwidth','requirement':'packaging','calendar':'python-dateutil'}[kind])}),flush=True)
if kind=='width':
 from wcwidth import wcwidth,wcswidth
 def actual(x,items):
    n,m,s,u=x
    out=[]
    for p,t in enumerate(items):
      if n:t=unicodedata.normalize(('none','NFC','NFKC')[n],t)
      if s:t=t.replace('\u00ad',('','', '-')[s])
      ver=('auto','14.0.0','15.0.0')[u]
      if m==1: y=sum(wcwidth(ch,unicode_version=ver) for ch in t)
      else:
       y=wcswidth(t,unicode_version=ver)
       if m==2: y=max(y,2) if '\ufe0f' in t and len(t)==2 else y
      out.append(y)
    return out
elif kind=='requirement':
 from packaging.requirements import Requirement
 from packaging.markers import Marker
 from packaging.utils import canonicalize_name
 def norm(t):
    a=re.match(r'[\w.-]+',t)
    return canonicalize_name(a.group(0))+t[a.end():] if a else t
 def actual(x,items):
    n,m,g,u=x; a,b,bad,valid,url=items
    def prep(t):return (t,norm(t),t.lower())[n]
    a,b=Requirement(prep(a)),Requirement(prep(b))
    if m==0:same=a==b
    elif m==1:same=(canonicalize_name(a.name),a.extras,a.specifier,a.url,a.marker)==(canonicalize_name(b.name),b.extras,b.specifier,b.url,b.marker)
    else:same=str(a)==str(b)
    def accept(k):
     if g==1 and not re.fullmatch(r'(python_version|sys_platform)\s*(?:[=!<>]=?|~=)\s*"[^"]+"', k):return False
     if g==2:k=k.strip().removesuffix(')').strip()
     try: Marker(k);return True
     except ValueError:return False
    c=Requirement(prep(url))
    got=(c.url,c.url.lower(),str(c).split('@')[-1].strip())[u]
    return [same,accept(bad),accept(valid),got,canonicalize_name(c.name)]
else:
 from dateutil.parser import isoparse,parse
 def actual(x,items):
    g,e,z,k=x; out=[]
    for s in items:
      if g==1 and not re.fullmatch(r'\d{4}-\d\d-\d\dT(?:\d\d:\d\d(?::\d\d(?:[.,]\d+)?)?|\d{4}(?:\d\d(?:[.,]\d+)?)?)(?:Z|[+-]\d\d:\d\d)?',s):
       out.append(None);continue
      if g==2:s=s.replace(':','')
      if z==1:s=s.replace(',', '.')
      if z==2:s=s.removesuffix('Z')
      try:
       y=(isoparse,datetime.datetime.fromisoformat,parse)[e](s)
       out.append((y.isoformat(),y.replace(tzinfo=None).isoformat(),y.date().isoformat())[k])
      except (ValueError,OverflowError):out.append(None)
    return out
for line in sys.stdin:
    x,items=json.loads(line)
    try: print(json.dumps(actual(x,items),ensure_ascii=True),flush=True)
    except Exception as e: print(json.dumps({'error':type(e).__name__}),flush=True)
