"""Execute locked ordinary and boundary probes against pinned public source revisions."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile
from issre_independent_collect import HERE,OUT
from issre_independent_cases import EXPECTED


def version(repo,sha,pr):
    short=repo.split('/')[1]
    module=short.replace('-','_')
    cache=Path(tempfile.gettempdir())
    db=cache/('issre20261124-'+short+'.git')
    if not db.exists():
        subprocess.run(['git','clone','--quiet','--bare','--single-branch','--no-tags',
                        f'https://github.com/{repo}.git',str(db)],check=True)
    git=['git','--git-dir='+str(db)]
    files=subprocess.check_output(git+['ls-tree','--name-only',sha]).decode().splitlines()
    pkg=('src/' if 'src' in files and short in ('humanize','prettytable') else '')+module
    data=subprocess.check_output(git+['archive','--format=zip',sha,pkg])
    with tempfile.TemporaryDirectory() as temp:
        base=Path(temp)
        with ZipFile(BytesIO(data)) as z:
            z.extractall(base)
        dest=base/pkg
        if short in ('humanize','prettytable') and not (dest/'_version.py').exists():
            (dest/'_version.py').write_text(f"__version__ = '0+git.{sha[:12]}'\n",encoding='utf8')
        if pr in (273,216):
            sys.path.insert(0,str(cache/'issre20261124-deps'))
            from babel.messages.pofile import read_po
            from babel.messages.mofile import write_mo
            locale='fr_FR' if pr==273 else 'pt_BR'
            pot=dest/'locale'/locale/'LC_MESSAGES'/'humanize.po'
            with pot.open('rb') as f, pot.with_suffix('.mo').open('wb') as out:
                write_mo(out,read_po(f,locale=locale))
        proc=subprocess.run([sys.executable,'-I',str(HERE/'issre_independent_cases.py'),str(pr),temp,module],
                            capture_output=True,encoding='utf8',errors='replace',timeout=30)
        if proc.returncode:
            raise RuntimeError(proc.stderr[-600:])
        return json.loads(proc.stdout)


def passed(r,projection):
    a,e=r['actual'],r['expected']
    return a['ok'] and (projection=='status' or a[projection]==e[projection])


def main():
    frame=json.loads((OUT/'frame.json').read_text(encoding='utf8'))
    commits={r['pr']:r for r in json.loads((OUT/'commits.json').read_text(encoding='utf8'))}
    # PR IDs in this captured frame are unique across projects.
    assert len(commits)==sum(len(p['records']) for p in frame['projects'])
    outcomes=[]
    confirmed=set()
    for index in range(10):
        for p in frame['projects']:
            pr=p['records'][index]['number']
            if pr not in EXPECTED or len(confirmed)>=12:
                continue
            c=commits[pr]
            entry=dict(pr=pr,repo=c['repo'],parent=c['parent'],fixed=c['fixed'])
            try:
                for key in ('parent','fixed'):
                    entry[key+'_rows']=version(c['repo'],c[key],pr)
                verified=all(passed(r,'fine') and passed(r,'coarse') for r in entry['fixed_rows'])
                control=passed(entry['parent_rows'][0],'fine') and passed(entry['parent_rows'][0],'coarse')
                found=any(not passed(r,'fine') for r in entry['parent_rows'])
                entry['confirmed']=verified and control and found
                if entry['confirmed']:
                    confirmed.add(250 if pr==240 else pr)
            except (OSError,RuntimeError,subprocess.SubprocessError) as e:
                entry.update(confirmed=False,setup_error=str(e))
            outcomes.append(entry)
            print(pr,entry['confirmed'],entry.get('setup_error','')[:100],flush=True)
    result=dict(probes_sha256=hashlib.sha256((HERE/'issre_independent_cases.py').read_bytes()).hexdigest(),
                independent_count=len(confirmed),outcomes=outcomes)
    (OUT/'replay.json').write_text(json.dumps(result,indent=1,ensure_ascii=False),encoding='utf8')


if __name__=='__main__':
    main()
