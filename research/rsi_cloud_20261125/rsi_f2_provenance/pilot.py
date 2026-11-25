"""Benign actual XLSX → fixed-schema CSV; test provenance needed for rehydration."""
import argparse,collections,csv,io,itertools,json
from pathlib import Path
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Font
from openpyxl.comments import Comment

FIELDS=('format','bold','title','comment')
METHODS=('csv_only','full_sidecar','required_fields','required_delta','search_minimal','native_xlsx')
MODES=('csv_only_interface','sidecar_allowed')
GOALS={'rows':(), 'money':('format',), 'accessibility':('bold','title'), 'archive':FIELDS}
N=12

def create(seed):
    w=Workbook();s=w.active;s.title='Report' if seed%3 else 'Period_'+str(seed)
    s.append(['item_id','cents']);s.append([f'{seed+8:04d}',12300+seed]);v=s['B2']
    if seed%4:v.number_format='"USD "0.00'
    if seed%2:v.font=Font(bold=True)
    if not seed%3:v.comment=Comment('Reviewed item '+str(seed),'Finance')
    return pack(w)

def pack(w):
    f=io.BytesIO();w.save(f);w.close();return f.getvalue()

def read(data):
    w=load_workbook(io.BytesIO(data))
    try:
        s=w.active;v=s['B2']
        return ([list(row) for row in s.values],
           {'format':v.number_format,'bold':bool(v.font.bold),'title':s.title,
            'comment':(v.comment.text,v.comment.author) if v.comment else None})
    finally:w.close()

def emit(data):
    rows,_=read(data);f=io.StringIO(newline='');csv.writer(f).writerows(rows)
    return f.getvalue().encode()

def restore(raw,side):
    rows=list(csv.reader(io.StringIO(raw.decode(),newline='')))
    w=Workbook();s=w.active;s.title='Report'
    for j,row in enumerate(rows):s.append(row if j==0 else [row[0],int(row[1])])
    fields=json.loads(side) if side else {};v=s['B2']
    if 'format' in fields:v.number_format=fields['format']
    if 'bold' in fields:v.font=Font(bold=fields['bold'])
    if 'title' in fields:s.title=fields['title']
    if fields.get('comment') is not None:v.comment=Comment(*fields['comment'])
    return pack(w)
def encode(x):return json.dumps(x,separators=(',',':'),sort_keys=True,ensure_ascii=False).encode() if x else b''

def run(out):
    sums=collections.defaultdict(lambda:dict(n=0,correct=0,wrong=0,defer=0,bytes=0,rehydrations=0))
    for seed in range(N):
      src=create(seed);csv_bytes=emit(src);rows,got=read(src)
      default_blob=restore(csv_bytes,b'');fallback=read(default_blob)[1]
      for key,require in GOALS.items():
        def ok(candidate):
            r,meta=read(candidate)
            return r==rows and all(meta[f]==got[f] for f in require)
        methods={'csv_only':b'','full_sidecar':encode(got),
                 'required_fields':encode({f:got[f] for f in require}),
                 'required_delta':encode({f:got[f] for f in require if got[f]!=fallback[f]})}
        options=sorted((encode({f:got[f] for f in q}) for k in range(len(FIELDS)+1)
                 for q in itertools.combinations(FIELDS,k)),key=lambda b:(len(b),b))
        n=0
        for side in options:
            n+=1
            if ok(restore(csv_bytes,side)):methods['search_minimal']=side;break
        assert methods['search_minimal']==methods['required_delta']
        for mode in MODES+('native_allowed_reference',):
          for m in METHODS:
            if mode=='native_allowed_reference' and m!='native_xlsx':continue
            result='defer';nbytes=ncalls=0
            if m=='native_xlsx':
                 if mode=='native_allowed_reference':result='correct' if ok(src) else 'wrong';nbytes=len(src);ncalls=1
            else:
                 side=methods[m]
                 if not side or mode=='sidecar_allowed':
                    result='correct' if ok(restore(csv_bytes,side)) else 'wrong'
                    nbytes=len(csv_bytes)+len(side);ncalls=n+1 if m=='search_minimal' else 1
            q=sums[(mode,key,m)]
            q['n']+=1;q[result]+=1;q['bytes']+=nbytes;q['rehydrations']+=ncalls
    result={}
    for (mode,key,m),row in sums.items():
       result.setdefault(mode,{}).setdefault(key,{})[m]=row
       whole=result[mode].setdefault('all',{}).setdefault(m,{k:0 for k in row})
       for k,n in row.items():whole[k]+=n
    p=Path(out);p.mkdir(parents=True,exist_ok=True)
    (p/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    for mode,r in result.items():print(mode,json.dumps(r['all']))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);run(p.parse_args().out)
