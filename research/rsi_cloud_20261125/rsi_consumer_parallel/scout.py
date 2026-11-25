"""Consumer continuations over public attrs and decimal interfaces."""
from collections import Counter
from dataclasses import dataclass
from decimal import Context, Decimal, Inexact
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys

OLD, NEW = '25.3.0', '25.4.0'
PORTS = {'attrs': ('result','post_init','pre_init'),
         'decimal': ('result','after_arithmetic','inexact_flag')}
EVIDENCE = {'result':'final', 'post_init':'final', 'after_arithmetic':'final',
            'pre_init':'constructor request', 'inexact_flag':'arithmetic loss'}

@dataclass(frozen=True)
class Case:
    base: int
    supplied: int
    threshold: int
    control: bool

CASES = [Case(i+100,2*i+200,3*i//2+150,False) for i in range(16)]
CASES += [Case(i+100,i+100,i+100,True) for i in range(8)]

def decide(estimate,threshold):
    return 'reserve' if estimate>threshold else 'hold'

def attrs_run(item,port):
    import attrs
    base,supplied,threshold,control=item
    output=[]
    @attrs.define
    class Parcel:
        estimate: int = base
        def __attrs_pre_init__(self,estimate):
            if port=='pre_init':
                output.append(decide(estimate,threshold))
        def __attrs_post_init__(self):
            if port=='post_init':
                output.append(decide(self.estimate,threshold))
    ob=Parcel(supplied)
    if port=='result':output.append(decide(ob.estimate,threshold))
    assert len(output)==1
    return [attrs.asdict(ob),output[0]]

def attrs_worker(root, expect):
    sys.path.insert(0,root)
    import attrs
    p=Path(attrs.__file__).resolve()
    assert p.is_relative_to(root) and version('attrs')==expect,p
    for item,port in json.load(sys.stdin):
        print(json.dumps(attrs_run(item,port)))

def decimal_run(i,control,kind,port):
    ctx=Context(prec=16)
    ctx.clear_flags()
    # Contract: rounding source values ending in .001 to cents drops a nonzero digit.
    raw=Decimal(f'{i+100}.200' if control else f'{i+100}.201')
    cent=Decimal(f'{i+100}.20')
    value=ctx.quantize(raw,Decimal('.01')) if kind=='reference' else cent
    if port=='after_arithmetic':
        converted = ctx.add(value,Decimal('0.00'))
        assert converted.as_tuple()==value.as_tuple()
    if port=='inexact_flag':
        decision='review' if ctx.flags[Inexact] else 'release'
    else:
        decision='release'
    return [value.as_tuple(), decision]

def main(root):
    req = [(tuple(vars(c).values()),p) for c in CASES for p in PORTS['attrs']]
    obs={}
    for v in (OLD,NEW):
        p=subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'worker',
                          str((root/f'attrs-{v}').resolve()),v],
                         input=json.dumps(req),text=True,check=True,capture_output=True)
        obs[v]=[json.loads(line) for line in p.stdout.splitlines()]
        assert len(obs[v])==len(req)
    reports={}
    for family,need in [('attrs','constructor request'),('decimal','arithmetic loss')]:
        tbl={}
        ports=PORTS[family]
        for i,c in enumerate(CASES):
            for j,p in enumerate(ports):
                if family=='attrs':
                    left,right=[obs[v][len(ports)*i+j] for v in (OLD,NEW)]
                    expected=decide(c.supplied,c.threshold)
                else:
                    left=decimal_run(i,c.control,'fast_path',p)
                    right=decimal_run(i,c.control,'reference',p)
                    expected='release' if c.control else 'review'
                assert left[0]==right[0], (family,left,right,i,p)
                tbl[i,p]=dict(witness=left[1]!=right[1] and right[1]==expected,
                              actual=left[1], reference=right[1], expected=expected,
                              endpoint=left[0])
        matching=tuple(p for p in ports if EVIDENCE[p]==need)
        assert len(matching)==1
        full={}
        for name,menu in {'endpoint_only':ports[:2], 'typed':matching,
                          'native':(ports[-1],), 'exhaustive':ports}.items():
            stats=Counter(positive=0, control_false=0, pairs=0)
            for i,c in enumerate(CASES):
                hit=False
                for p in menu:
                    stats['pairs']+=1
                    hit |= tbl[i,p]['witness']
                    if hit and name!='exhaustive': break
                stats['control_false' if c.control else 'positive']+=hit
            full[name]=stats
        reports[family]=dict(pair_count=len(CASES), by_solver=full,
                             sample=tbl[0,matching[0]], null_sample=tbl[-1+len(CASES),matching[0]],
                             endpoints_matched=24)
    print(json.dumps(dict(attrs_versions=[OLD,NEW],cases=reports,python=sys.version.split()[0]),
                     sort_keys=True,indent=2))

if __name__=='__main__':
    if sys.argv[1]=='worker': attrs_worker(*sys.argv[2:])
    else:main(Path(sys.argv[1]))
