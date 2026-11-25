"""Documentation-only tasks and expected observables. No fix information is imported."""
from dataclasses import dataclass
from io import StringIO
import json
import re
from time import perf_counter_ns as tick
from xml.etree import ElementTree as ET


@dataclass
class Task:
    name: str
    clauses: tuple
    calls: int
    expected: dict
    relevant: dict


def task(name,clauses,calls,expected,links):
    return Task(name,tuple(clauses.split()),calls,{'status':'ok',**expected},
                {'status':['completion'],**{k:v.split() for k,v in links.items()}})


def tasks(p):
    if p=='click':
        specs=[
            ('default','default',{'num':2},'num=2'),
            ('given','explicit',{'num':7},'num=7'),
            ('repeat','collection order',{'val':['a','b']},'val=a,b'),
            ('count','count combined',{'val':3},'val=3'),
            ('env','environment',{'num':4},'num=4'),
            ('override','explicit precedence environment',{'num':7},'num=7'),
            ('off','boolean disable',{'val':False},'val=False'),
            ('args','collection order variadic',{'val':['a','b']},'val=a,b'),
            ('help','help default formatting',{},'documents default and option'),
            ('invalid','invalid choice diagnostic',{},'explains allowed choices')]
        return [task(n,c,2,dict(exit=2 if n=='invalid' else 0,payload=v,text=t),
                     dict(exit='error_code' if n=='invalid' else 'success_code',
                          payload=c if n not in ('help','invalid') else 'no_callback',
                          text=c+' display')) for n,c,v,t in specs]
    if p=='markdown':
        specs=[
            ('basic','paragraph',2,['hello'],['p'],[]),
            ('em','emphasis',2,['hello'],['p','em'],[]),
            ('head','heading anchor',2,['Alpha'],['h1'],['alpha']),
            ('twins','duplicate anchor order',2,['Alpha','Alpha'],['h1','h1'],['alpha','alpha_1']),
            ('reuse','reset anchor duplicate',4,['Alpha'],['h1'],['alpha']),
            ('table','table header cells',2,['A','B','x','y'],['table','tr','th','th','tr','td','td'],[]),
            ('fence','code literal language',2,['<tag>'],['pre','code'],['language-html']),
            ('link','link target',2,['title'],['p','a'],['/guide']),
            ('list','list order items',2,['x','y'],['ul','li','li'],[]),
            ('refreset','reference reset',4,['[title][id]'],['p'],[])]
        return [task(n,c,k,dict(text=v,structure=t,attrs=a),
              dict(text=c.split()[0]+' content',structure=c.split()[0]+' tree',attrs=c if a or k==4 else 'no_attributes'))
                for n,c,k,v,t,a in specs]
    specs=[
        ('empty','initial total',[],0,5,'job'),
        ('one','advance', [('update',1)],1,5,'job'),
        ('initial','initial advance',[('update',2)],4,5,'job'),
        ('many','advance cumulative',[('update',1),('update',2)],3,5,'job'),
        ('reset','reset total',[('update',2),('reset',8)],0,8,'job'),
        ('resume','reset total advance',[('update',2),('reset',8),('update',3)],3,8,'job'),
        ('rename','description',[('desc','next')],0,5,'next'),
        ('finish','advance complete',[('update',5)],5,5,'job'),
        ('reset_same','reset retained',[('update',3),('reset',None)],0,5,'job'),
        ('fraction','advance fractional',[('update',0.5)],0.5,5,'job')]
    return [task(n,c,3+len(ops),dict(counter=count,total=total,text=f'{label}|{count}/{total}'),
                 dict(counter=c+' count',total='total '+('reset' if 'reset' in c else 'initial'),text=c+' render'))
            for n,c,ops,count,total,label in specs]


def run_click(n):
    import click
    from click.testing import CliRunner
    payload={}
    def command(**values):
        for k,v in values.items():
            payload[k]=list(v) if isinstance(v,tuple) else v
            click.echo(k+'='+(','.join(v) if isinstance(v,tuple) else str(v)))
    args=[]
    if n in ('default','given','override','env','help'):
        command=click.option('--num',type=int,default=2,show_default=True,envvar='BLIND_NUM')(command)
        args={'given':['--num','7'],'override':['--num','7'],'help':['--help']}.get(n,[])
    elif n=='repeat':
        command=click.option('-v','val',multiple=True)(command)
        args=['-v','a','-v','b']
    elif n=='count':
        command=click.option('-v','val',count=True)(command)
        args=['-vvv']
    elif n=='off':
        command=click.option('--on/--off','val',default=True)(command)
        args=['--off']
    elif n=='args':
        command=click.argument('val',nargs=-1)(command)
        args=['a','b']
    else:
        command=click.option('--color',type=click.Choice(['red','blue']))(command)
        args=['--color','green']
    t=tick()
    runner=CliRunner()
    cmd=click.command()(command)
    fresh=tick()-t
    t=tick()
    result=runner.invoke(cmd,args,env={'BLIND_NUM':'4' if n in ('env','override') else None},
                         color=False,terminal_width=80)
    return dict(result=result,payload=payload,phase_ns={'runner_setup':fresh,'invoke_and_capture':tick()-t})


def run_markdown(n):
    import markdown
    from markdown.extensions.toc import TocExtension
    from markdown.extensions.tables import TableExtension
    from markdown.extensions.fenced_code import FencedCodeExtension
    t=tick()
    md=markdown.Markdown(extensions=[TocExtension(),TableExtension(),FencedCodeExtension()])
    phases={'fresh_converter':tick()-t}
    inputs=dict(basic='hello',em='*hello*',head='# Alpha',twins='# Alpha\n\n# Alpha',reuse='# Alpha',
                table='A | B\n--- | ---\nx | y',fence='```html\n<tag>\n```',link='[title](/guide)',
                list='- x\n- y',refreset='[title][id]')
    if n in ('reuse','refreset'):
        md.convert('# Alpha' if n=='reuse' else '[title][id]\n\n[id]: /previous')
        t=tick()
        md.reset()
        phases['explicit_reset']=tick()-t
    t=tick()
    html=md.convert(inputs[n])
    phases['final_render']=tick()-t
    return dict(html=html,phase_ns=phases)


def run_tqdm(n):
    from tqdm import tqdm
    s=StringIO()
    # Deterministic transcript: no clocks, rates, terminal negotiation, or worker threads.
    t=tick()
    bar=tqdm(total=5,initial=2 if n=='initial' else 0,desc='job',file=s,ascii=True,
             disable=False,mininterval=999,bar_format='{desc}|{n}/{total}')
    phases={'fresh_bar':tick()-t}
    ops=dict(empty=[],one=[1],initial=[2],many=[1,2],reset=[2,'reset8'],resume=[2,'reset8',3],
             rename=['rename'],finish=[5],reset_same=[3,'reset'],fraction=[0.5])
    try:
        for x in ops[n]:
            if x=='rename': bar.set_description_str('next')
            elif x in ('reset','reset8'):
                t=tick()
                bar.reset(total=8 if x=='reset8' else None)
                phases['explicit_reset']=tick()-t
            else: bar.update(x)
        t=tick()
        bar.refresh()
        phases['final_refresh']=tick()-t
        data=dict(counter=bar.n,total=bar.total)
    finally:
        t=tick()
        bar.close()
        phases['close']=tick()-t
    data['render']=s.getvalue()
    data['phase_ns']=phases
    return data


RUN=dict(click=run_click,markdown=run_markdown,tqdm=run_tqdm)


def observe(p,n,a,field):
    if field=='status': return a.get('error','ok')
    if 'error' in a: return {'error':a['error']}
    if p=='click':
        if field=='exit': return a['result'].exit_code
        if field=='payload': return a['payload']
        text=a['result'].output.strip()
        if n=='help' and '--num' in text and re.search(r'default:\s*2\b',text,re.I):
            return 'documents default and option'
        if n=='invalid' and all(q in text for q in ('red','blue','green')):
            return 'explains allowed choices'
        return text
    if p=='markdown':
        if 'tree' not in a:
            a['tree']=ET.fromstring('<root>'+a['html']+'</root>')
        tree=a['tree']
        if field=='text':return [t.strip() for t in tree.itertext() if t.strip()]
        if field=='structure':return [e.tag for e in tree.iter() if e.tag not in ('root','thead','tbody')]
        return [v for e in tree.iter() for k,v in e.attrib.items() if k in ('href','class','id')]
    if field=='text':return a['render'].strip().split('\r')[-1].strip()
    return a[field]


def raw_channel(p,a):
    if 'error' in a:return a['error']
    if p=='markdown':return a['html']
    if p=='click':return a['result'].output
    return a['render']
