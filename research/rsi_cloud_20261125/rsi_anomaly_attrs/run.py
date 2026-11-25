from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys

VERS=('25.3.0','25.4.0')
POOL=[*range(200,264),100]


def worker(root, ver):
    sys.path.insert(0, root)
    import attrs
    assert version('attrs')==ver and Path(attrs.__file__).is_relative_to(root)
    def record(x):
        received=[]
        @attrs.define
        class Parcel:
            estimate:int=100
            def __attrs_pre_init__(self, estimate):
                received.append(estimate)
        p=Parcel(x)
        assert len(received)==1
        return (p.estimate, received[0])
    print(json.dumps([record(x) for x in POOL]))


def main(root):
    old,new=[json.loads(subprocess.check_output([sys.executable,'-IB',__file__,'worker',
         str((root/f'attrs-{v}').resolve()),v],text=True)) for v in VERS]
    assert old[0]==[200,100] and new[0]==[200,200]
    assert old[-1]==new[-1]==[100,100]
    assert all(x==b[0]==b[1] and a[0]==x for x,a,b in zip(POOL,old,new,strict=True))
    report={}
    for k in (1,8,64):
        tasks=list(zip(POOL[:k],old[:k],new[:k],strict=True))
        report[k]=dict(version_pair_calls=k,endpoint_exact=sum(a[0]!=x for x,a,b in tasks),
            callback_exact=sum(a[1]!=x for x,a,b in tasks),
            callback_sign_only=sum((a[1]>0)!=(x>0) for x,a,b in tasks),
            native_direct=sum(a[1]!=b[1] for x,a,b in tasks),
            fixed_errors=sum(b[1]!=x for x,a,b in tasks))
    print(json.dumps(dict(versions=VERS,positive_pool=len(POOL)-1,control_false_alarms=0,
        paired_executions=65, results=report),indent=2,sort_keys=True))


if __name__=='__main__':
    if sys.argv[1]=='worker': worker(*sys.argv[2:])
    else: main(Path(sys.argv[1]))
