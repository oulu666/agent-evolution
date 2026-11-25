"""Test a compatibility adapter after witness discovery, separate from frozen scout."""
from pathlib import Path
import json, re, subprocess, sys

VALUES = [
 ('1 61', (1,61)), (' -3 7 ', (-3,7)), ('0\t4', (0,4)),
 ('+2 -5', (2,-5)), ('001 09', (1,9)), ('8\n11', (8,11)),
 ('99 0', (99,0)), ('-1 -2', (-1,-2)),
 ('3',None), ('3 4 5',None), ('3 x',None), ('',None),
 ([-2,4],(-2,4)), ([3],None), ([],None), ([7,9],(7,9)),
]
def synth(spec):
    size, token_type=spec
    def convert(value):
        parts=value.split() if isinstance(value,str) else value
        if len(parts)!=size:raise ValueError('wrong arity')
        return tuple(token_type(p) for p in parts)
    return convert
def direct(value):
    a,b=value.split() if isinstance(value,str) else value
    return int(a),int(b)
def worker(releases,v):
    sys.path.insert(0,str(Path(releases,'click-'+v).resolve()))
    from importlib.metadata import version
    assert version('click')==v
    import click
    from click.testing import CliRunner
    opt=click.Option(['--point'],nargs=2,type=int)
    cmd=click.Command('report',params=[opt],callback=lambda point:click.echo(json.dumps(point)))
    score={}
    for strategy,fn in [('native',None),('declared_tuple',synth((opt.nargs,int))),('direct_rule',direct)]:
        correct=0
        for value,gold in VALUES:
            try:
                val=value if fn is None else fn(value)
            except (ValueError,TypeError):
                got=None
            else:
                r=CliRunner().invoke(cmd,[],default_map={'point':val})
                got=tuple(json.loads(r.output)) if r.exit_code==0 else None
            correct+=got==gold
        score[strategy]=correct
    return score
if __name__=='__main__':
    if len(sys.argv)==4: print(json.dumps(worker(sys.argv[3],sys.argv[2])))
    else:
        assert len(sys.argv)==2
        print(json.dumps({v:json.loads(subprocess.check_output([sys.executable,'-I',__file__,'--worker',v,sys.argv[1]]))
               for v in ('8.3.3','8.4.0')},indent=2))
