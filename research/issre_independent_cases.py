"""Frozen paired probes. Each observation contains a coarse projection and a stronger one."""
from datetime import timedelta
from io import StringIO
import json
from pathlib import Path
import re
import sys
import tempfile
from xml.etree import ElementTree


# Two inputs per PR, ordinary first. Success status is also retained separately.
EXPECTED={
    273:[(1.,'1.0 million'),(1.,'1.0 million')],
    254:[(60,'1 minute'),(60,'1 minute')],
    250:[(1.,'1 Byte'),(1.,'1 Byte')],
    240:[(2,'2 Bytes'),(1,'1 Bytes')],
    218:[('MB','3.0 MB'),('MB','3.0 MB')],
    216:[(1.,'1.0 milhão'),(2.,'2.0 bilhões')],
    1088:[(True,True),(False,False)],
    1082:[(3,3),(3,3)],
    378:[(1,[['X']]),(0,[])],
    356:[(['X','Y'],'+'),(['X','Y'],'├')],
    355:[(['a','z'],['z','a']),(['a','z'],['a','z'])],
    3718:[('title',None),('title','blue')],
    345:[('X','center'),('1','center')],
    206:[('100.0 ZB','100.0 ZB'),('1.0 YB','1.0 YB')],
    344:[('X',True),('X',True)],
    1028:[(3,3),(3,3)],
}
INPUTS={
    273:['fr_FR 1000000','fr_FR 1010000, one fractional digit'],
    254:['60 s, zero fractional digits','59.5 s, zero fractional digits'],
    250:['1 as integer','1 as floating point'],
    240:['2 as integer','1.123456789 as floating point'],
    218:['3000000 as Python integer','3000000 as numpy.int32'],
    216:['pt_BR 1000000','pt_BR 2000000000'],
    1088:['[True], n=1','[True], n=-10'],
    1082:['tuple target and pools','one-pass iterators for target and pools'],
    378:['one populated row','empty row batch'],
    356:['default border, two rows, divider after X','single-line border, same rows and divider'],
    355:['insertion order z,a','request sort on field k at construction'],
    3718:['panel with plain background','panel with blue background, red title'],
    345:['ordinary formatted HTML table','same table, automatic index added'],
    206:['10**23 bytes','10**24 bytes'],
    344:['apply MSWORD_FRIENDLY to fresh table','apply MARKDOWN then MSWORD_FRIENDLY'],
    1028:['list 1,2,3','iterable explicitly without reverse iteration'],
}


def probe(n,edge,call):
    if n in (273,254,250,240,218,216,206):
        import humanize as h
        if n in (273,216):
            call('activate locale',h.activate,'fr_FR' if n==273 else 'pt_BR')
            value=(1010000 if n==273 else 2000000000) if edge else 1000000
            s=call('format magnitude',h.intword,value)
            return float(s.split()[0]),s
        if n==254:
            s=call('format time',h.precisedelta,timedelta(seconds=59.5 if edge else 60),format='%.0f')
            pairs=re.findall(r'([\d.]+) (second|minute|hour)',s)
            return sum(float(v)*{'second':1,'minute':60,'hour':3600}[u] for v,u in pairs),s
        import numpy as np
        v={250:(1,1.0),240:(2,1.123456789),218:(3000000,np.int32(3000000)),206:(10**23,10**24-1)}[n][edge]
        s=call('format bytes',h.naturalsize,v)
        if n==206:
            return s,s
        return (s.split()[-1] if n==218 else int(float(s.split()[0]))),s
    if n in (1088,1082,1028):
        import more_itertools as mi
        if n==1088:
            v=call('exactly_n',mi.exactly_n,[True],-10 if edge else 1)
        elif n==1082:
            f=iter if edge else tuple
            v=call('product_index',mi.product_index,f('by'),f('ab'),f('xy'))
        else:
            class Forward:
                __reversed__=None
                def __iter__(self):
                    return iter([1,2,3])
            v=call('last',mi.last,Forward() if edge else [1,2,3])
        return v,v
    if n==3718:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        c=call('create console',Console,file=StringIO(),width=30,force_terminal=True,
               color_system='truecolor',legacy_windows=False)
        title=call('create title',Text,'title',style='red')
        panel=call('create panel',Panel,'body',title=title,style='on blue' if edge else '')
        segments=call('render',lambda:list(c.render(panel)))
        title_segment=next(s for s in segments if 'title' in s.text)
        bg=title_segment.style.bgcolor if title_segment.style else None
        return title_segment.text.strip(),bg.name if bg else None
    from prettytable import PrettyTable
    if n==355:
        t=call('create table',PrettyTable,['k'],**({'sortby':'k'} if edge else {}))
        call('add rows',t.add_rows,[['z'],['a']])
        s=call('render',t.get_string)
        values=re.findall(r'\|\s*([az])\s*\|',s)
        return sorted(values),values
    t=call('create table',PrettyTable,['k'])
    if n==344:
        from prettytable import TableStyle
        oracle=PrettyTable(['k'])
        oracle.add_row(['X'])
        oracle.set_style(TableStyle.MSWORD_FRIENDLY)
        call('add row',t.add_row,['X'])
        if edge:
            call('set prior style',t.set_style,TableStyle.MARKDOWN)
        call('set final style',t.set_style,TableStyle.MSWORD_FRIENDLY)
        result=call('render',t.get_string)
        return 'X' if 'X' in result else '',result==oracle.get_string()
    if n==378:
        call('add rows',t.add_rows,[] if edge else [['X']])
        vals=call('read rows',lambda:t.rows)
        return len(vals),vals
    if n==356:
        from prettytable import TableStyle
        call('apply style',t.set_style,TableStyle.SINGLE_BORDER if edge else TableStyle.DEFAULT)
        call('add divided row',t.add_row,['X'],divider=True)
        call('add row',t.add_row,['Y'])
        lines=call('render',t.get_string).splitlines()
        k=next(i for i,l in enumerate(lines) if 'X' in l)
        return [v for l in lines for v in ('X','Y') if v in l],lines[k+1][0]
    call('add row',t.add_row,['X'])
    call('enable HTML formatting',setattr,t,'format',True)
    if edge:
        call('add index',t.add_autoindex,'I')
    xml=call('render HTML',t.get_html_string)
    td=ElementTree.fromstring(xml).find('.//td')
    align=re.search(r'text-align:\s*([^;]+)',td.attrib['style'])
    return td.text,align[1] if align else None


def main():
    n=int(sys.argv[1])
    directory=Path(sys.argv[2]).resolve()
    sys.path[:0]=[str(directory/'src'),str(directory),str(Path(tempfile.gettempdir())/'issre20261124-deps')]
    package=sys.argv[3]
    mod=__import__(package)
    assert Path(mod.__file__).resolve().is_relative_to(directory)
    records=[]
    for i,expected in enumerate(EXPECTED[n]):
        steps=[]
        def call(name,fn,*args,**kwargs):
            steps.append(name)
            return fn(*args,**kwargs)
        try:
            result=probe(n,i,call)
            actual=dict(ok=True,coarse=result[0],fine=result[1])
        except Exception as e:
            actual=dict(ok=False,error=type(e).__name__,detail=str(e)[:220])
        records.append(dict(input=INPUTS[n][i],expected=dict(ok=True,coarse=expected[0],fine=expected[1]),
                            actual=actual,steps=steps))
    print(json.dumps(records))


if __name__=='__main__':
    main()
