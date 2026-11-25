import hashlib,json
from importlib.metadata import distribution
items=[('icon-left-arrow-64px.png',[3,1,1]),('icon-right-arrow-64px.png',[1,1,2]),
       ('icon-copy-64px.png',[6,1,1]),('icon-goto-bookmark-64px.png',[2,1,2]),('icon-find-64px.png',[5,1,1])]
d=distribution('ezdxf')
print(json.dumps(dict(ezdxf=d.version,pillow=distribution('pillow').version,items=[
    dict(name=n,combo=c,sha256=hashlib.sha256(d.locate_file('ezdxf/resources/'+n).read_bytes()).hexdigest())
    for n,c in items]),indent=2))
