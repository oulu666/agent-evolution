"""Composition admission gate on actual workbook, XML, and YAML operations."""
import argparse,csv,io,itertools,json
from collections import defaultdict,Counter
from pathlib import Path
import openpyxl
from openpyxl.styles import Font,NamedStyle
from lxml import etree
import yaml

ORDER=('base','A','B','AB','BA','merge')
KINDS=('commute','A_reset','B_reset','both_reset')
TOOLS=('xlsx','xml','yaml')
def xlsx(which,n,o):
    w=openpyxl.Workbook(); c=w.active['A1']; c.value=100+n
    fmt='0.'+'0'*(1+n%3)
    def op(a):
        if a=='A':
            if which in ('A_reset','both_reset'):
                c.style=NamedStyle(name='repair_heading',font=Font(bold=True))
            else:c.font=Font(name='Calibri',bold=True)
        else:
            if which in ('B_reset','both_reset'):
                c.style=NamedStyle(name='repair_number',number_format=fmt)
            else:c.number_format=fmt
    if o=='merge':
        # An ordinary adapter that changes only the two schema fields.
        c.font=Font(name='Calibri',bold=True);c.number_format=fmt
    else:
        for a in ('' if o=='base' else o):op(a)
    f=io.BytesIO();w.save(f);w2=openpyxl.load_workbook(f);v=w2.active['A1']
    try:return (bool(v.font.bold),v.number_format==fmt,v.value==100+n)
    finally:w2.close();w.close()

def xml(which,n,o):
    root=etree.Element('row'); root.text='legacy'; root.set('status','old')
    root.set('record',str(n)); root.tail='\n'
    def op(a):
        reset=which in (a+'_reset','both_reset')
        if reset:
            old=root.attrib['record'];root.clear(keep_tail=True);root.set('record',old)
        if a=='A':root.text='标题 '+str(n)
        else:root.set('status','ready')
    if o=='merge': root.text='标题 '+str(n);root.set('status','ready')
    else:
        for a in ('' if o=='base' else o):op(a)
    b=etree.tostring(root,encoding='utf-8')
    got=etree.fromstring(b)
    return (got.text=='标题 '+str(n),got.get('status')=='ready',got.get('record')==str(n) and b.endswith(b'\n'))

def yml(which,n,o):
    expected={'z':n,'a':'货物 '+str(n),'m':[n,1]}
    def dump(flow, sort):
        return yaml.safe_dump(expected,default_flow_style=flow,sort_keys=sort,allow_unicode=True)
    def flags(s):
        y=yaml.compose(s,Loader=yaml.SafeLoader)
        return (not y.flow_style,[k.value for k,v in y.value]==list(expected))
    s=dump(True,True)
    if o=='merge':s=dump(False,False)
    else:
     for a in ('' if o=='base' else o):
        fl,seq=flags(s)
        if a=='A':s=dump(False,True if which in ('A_reset','both_reset') else not seq)
        else:s=dump(True if which in ('B_reset','both_reset') else not fl,False)
    fl,seq=flags(s)
    return (fl,seq,yaml.safe_load(s)==expected)

def run(out):
    p=Path(out);p.mkdir(parents=True,exist_ok=True)
    produce=dict(zip(TOOLS,(xlsx,xml,yml)))
    rows=[]; sums=defaultdict(Counter)
    for t,fn in produce.items():
      for case in KINDS:
       for n in range(8):
        v={o:tuple(map(int,fn(case,n,o))) for o in ORDER}
        assert v['A'][0] and v['B'][1],(t,case,v)
        assert all(x[2] for x in v.values()),(t,case,v)
        possible=[a for a in ('AB','BA') if all(v[a])]
        # These are eight documents per condition, not independent bugs.
        f={'tool':t,'condition':case,'document':n,'order_solutions':len(possible),
           **{a:''.join(map(str,z)) for a,z in v.items()}}
        rows.append(f)
        for k in (t,'all'):
         c=sums[k];c['n']+=1
         c['fixed_AB']+=all(v['AB']);c['fixed_BA']+=all(v['BA'])
         c['order_search_best']+=bool(possible)
         c['both_orders_fail']+=not bool(possible)
         c['at_least_one_order_fails']+=len(possible)<2
         c['patch_two_fields']+=all(v['merge'])
         # Dominance of fixed domain adapter is evaluated separately.
         # Try AB, BA, then field merge on a conflict, scoped to this menu.
         c['order_then_merge_calls']+=1 if all(v['AB']) else 2 if all(v['BA']) else 3
         c['patch_two_fields_calls']+=1
    with (p/'witnesses.csv').open('w',newline='') as file:
      w=csv.DictWriter(file,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (p/'summary.json').write_text(json.dumps(sums,indent=2)+'\n')
    print(json.dumps(sums,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);run(p.parse_args().out)
