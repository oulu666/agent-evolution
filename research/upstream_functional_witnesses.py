"""Paired, public-release replay of three ordinary data-formatting regressions."""
from datetime import date, timedelta
from hashlib import sha256
from io import BytesIO
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import sys
import urllib.request
from xml.etree import ElementTree
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs_upstream_functional_20261124'
CASES = {
    'column': ('XlsxWriter','3.3.0','3.3.1','https://github.com/jmcnamara/XlsxWriter/issues/1219'),
    'duration': ('XlsxWriter','1.3.7','1.3.8','https://github.com/jmcnamara/XlsxWriter/issues/731'),
    'week': ('Babel','2.16.0','2.17.0','https://github.com/python-babel/babel/pull/1179'),
}
NS = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def workbook_result(actions, days=None):
    import xlsxwriter
    stream = BytesIO()
    wb = xlsxwriter.Workbook(stream,{'in_memory':True})
    sheet = wb.add_worksheet()
    for action in actions:
        if action=='width':
            sheet.set_column(0,0,2)
        elif action=='text':
            sheet.write_string(0,0,'hello world')
        elif action=='fit':
            sheet.autofit()
    if days is not None:
        sheet.write_datetime(0,0,timedelta(days=days),wb.add_format({'num_format':'[h]:mm'}))
    wb.close()
    with ZipFile(stream) as archive:
        root = ElementTree.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        if days is not None:
            return float(root.find('.//s:c/s:v',NS).text)
        col = root.find('.//s:col',NS)
        text = ''
        if root.find('.//s:c',NS) is not None:
            sst = ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))
            text = sst.find('.//s:t',NS).text
        return {'visible':col is None or col.get('hidden','0')!='1','cell_text':text}


def observations(key):
    if key=='column':
        return [{'input':list(s),'actual':workbook_result(s),
                 'expected':{'visible':True,'cell_text':'hello world' if 'text' in s else ''}}
                for length in range(4) for s in product(('width','text','fit'),repeat=length)]
    if key=='duration':
        return [{'input':x,'actual':workbook_result([],x),'expected':x} for x in (1, 30, 59, 59.5, 60, 75)]
    from babel.dates import format_date
    rows=[]
    for year in (2003,2004,2005,2008):
        for month,day in ((6,15),(1,1),(12,28),(12,29),(12,31)):
            dt=date(year,month,day)
            iso=dt.isocalendar()
            rows.append({'input':dt.isoformat(),'actual':format_date(dt,"YYYY-'W'ww-e",locale='de_DE'),
                         'expected':f'{iso.year:04}-W{iso.week:02}-{iso.weekday}'})
    return rows


def fetch(url):
    with urllib.request.urlopen(url, timeout=45) as resp:
        return resp.read()


def replay(key,package,version):
    info=json.loads(fetch(f'https://pypi.org/pypi/{package}/{version}/json'))
    wheel=next(x for x in info['urls'] if x['filename'].endswith('.whl') and x['filename'].endswith('none-any.whl'))
    data=fetch(wheel['url'])
    digest=sha256(data).hexdigest()
    assert digest==wheel['digests']['sha256']
    with TemporaryDirectory() as tmp:
        with ZipFile(BytesIO(data)) as archive:
            archive.extractall(tmp)
        proc=subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--worker',
                             key,package,version,tmp],capture_output=True,text=True,check=True)
    return dict(version=version,filename=wheel['filename'],url=wheel['url'],sha256=digest,
                rows=json.loads(proc.stdout))


def main():
    result={}
    for key,(package,old,new,source) in CASES.items():
        before=replay(key,package,old)
        after=replay(key,package,new)
        diffs=[]
        for a,b in zip(before['rows'],after['rows'],strict=True):
            assert a['input']==b['input'] and a['expected']==b['actual']==b['expected']
            if a['expected']!=a['actual']:
                diffs.append(a['input'])
        assert diffs and len(diffs)<len(before['rows'])
        result[key]=dict(source=source,before=before,after=after,detected_inputs=diffs)
    OUT.mkdir(exist_ok=True)
    (OUT/'paired_releases.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print({k:v['detected_inputs'] for k,v in result.items()})


if __name__=='__main__':
    if sys.argv[1:2]==['--worker']:
        _,_,key,pkg,version,path=sys.argv
        sys.path.insert(0,path)
        mod=__import__(pkg.lower())
        assert mod.__version__==version and Path(mod.__file__).is_relative_to(path)
        print(json.dumps(observations(key)))
    else:
        main()
