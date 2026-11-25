"""Capture the predeclared consecutive GitHub PR sampling frame."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen

HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'runs_independent_20261124'
PROJECTS=['python-humanize/humanize','prettytable/prettytable','more-itertools/more-itertools','Textualize/rich']


def fetch(url):
    req=Request(url,headers={'User-Agent':'independent-functional-reliability-study'})
    with urlopen(req,timeout=40) as r:
        return json.load(r)


def capture(repo):
    query=f'repo:{repo} is:pr is:merged merged:2022-01-01..2025-12-31 fix in:title'
    url='https://api.github.com/search/issues?'+urlencode(dict(q=query,sort='created',order='desc',per_page=11))
    obj=fetch(url)
    assert not obj['incomplete_results']
    items=sorted(obj['items'],key=lambda r:(r['created_at'],r['number']),reverse=True)
    return dict(repo=repo,url=url,total=obj['total_count'],records=[{k:r[k] for k in
        ('number','title','html_url','created_at','body')} for r in items[:10]])


if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    if (OUT/'frame.json').exists():
        print('Frozen frame already exists; use its recorded PRs and commit IDs.')
        raise SystemExit(0)
    with ThreadPoolExecutor(2) as pool:
        data=list(pool.map(capture,PROJECTS))
    result=dict(protocol_sha256=hashlib.sha256((HERE/'ISSRE_INDEPENDENT_PROTOCOL_20261124.md').read_bytes()).hexdigest(),projects=data)
    (OUT/'frame.json').write_text(json.dumps(result,indent=1,ensure_ascii=False),encoding='utf8')
    for p in data:
        print(p['repo'],p['total'])
        for r in p['records']:
            print(r['number'],r['title'].encode('ascii','replace').decode())
