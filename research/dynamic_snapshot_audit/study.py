"""Replay real first-parent commits into private WAL databases; never touch project databases."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import platform
import random
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "runs_dynamic_snapshot_20261125"
REPOS = {"pluggy": ("issre-boundary-pluggy.git","a0e47471d7f5147e72d82fc434c97596df20e642"),
         "click": ("issre-docblind-click.git","08b803cf32ceb2ae6a772c62d5da42757a897d44")}
START = int(datetime(2025,1,1,tzinfo=timezone.utc).timestamp())
STOP = int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp())
QUERY = {"total":"SELECT count(*) FROM commits",
         "authors":"SELECT count(*) FROM (SELECT author FROM commits GROUP BY author)",
         "top3":"SELECT author,count(*) AS n FROM commits GROUP BY author ORDER BY n DESC,author LIMIT 3"}
FAST = {"total":"SELECT n FROM totals","authors":"SELECT count(*) FROM frequency",
        "top3":"SELECT author,n FROM frequency ORDER BY n DESC,author LIMIT 3"}
POLICIES = ("primary","backup","newest","live","summary","head_gate","fused_gate","lazy_gate","publish_memo")
HEAD = "SELECT max(id) FROM commits"


def save(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=True,separators=(",",":")),encoding="utf8")


def load(name):
    return json.loads((OUT/name).read_text(encoding="utf8"))


def hashfile(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def hashes():
    return {p.name:hashfile(p) for p in (HERE/"study.py", HERE/"analyze.py",HERE/"protocol.md",OUT/"streams.json")}


def freeze():
    OUT.mkdir(exist_ok=True)
    if (OUT/"lock.json").exists():
        assert load("lock.json")["hashes"]==hashes()
        return
    streams={}
    for name,(repo,rev) in REPOS.items():
        path=Path(tempfile.gettempdir())/repo
        cmd=["git","--git-dir",str(path),"log","--first-parent","--format=%H%x09%ct%x09%ae",rev]
        records=[]
        for line in subprocess.check_output(cmd).splitlines():
            sha,when,email=line.split(b"\t",2)
            if int(when)<STOP:
                author=hashlib.sha256(email.strip().lower()).hexdigest()[:20]
                records.append([int(when),sha.decode(),author])
        streams[name]=sorted(records)
    save("streams.json",streams)
    save("lock.json",dict(utc=datetime.now(timezone.utc).isoformat(),hashes=hashes(),heads=REPOS,
                          python=platform.python_version(),sqlite=sqlite3.sqlite_version,host=platform.platform()))


def connect(path):
    return sqlite3.connect(path,isolation_level=None,cached_statements=128)


def setup(path,summary):
    db=connect(path)
    assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0]=="wal"
    db.execute("PRAGMA synchronous=FULL")
    db.executescript("CREATE TABLE commits(id INTEGER PRIMARY KEY, author TEXT NOT NULL); CREATE INDEX authors ON commits(author);")
    if summary:
        db.executescript("""
            CREATE TABLE totals(n INTEGER NOT NULL);
            INSERT INTO totals VALUES(0);
            CREATE TABLE frequency(author TEXT PRIMARY KEY,n INTEGER NOT NULL);
            CREATE INDEX ranked ON frequency(n DESC, author);
            CREATE TRIGGER counts AFTER INSERT ON commits BEGIN
              UPDATE totals SET n=n+1;
              INSERT INTO frequency VALUES(new.author,1)
                ON CONFLICT(author) DO UPDATE SET n=n+1;
            END;
        """)
    return db


def query(db,query_text):
    return db.execute(query_text).fetchall()


def measured(fn,*args):
    start=time.perf_counter_ns()
    value=fn(*args)
    return value,time.perf_counter_ns()-start


def seed(db,items):
    db.execute("BEGIN")
    db.executemany("INSERT INTO commits VALUES(?,?)",items)
    db.commit()


def snapshot(db):
    db.execute("BEGIN")
    try:
        head=db.execute(HEAD).fetchone()[0]
        pages={k:query(db,q) for k,q in QUERY.items()}
        return head,pages
    finally:
        db.commit()


def run(name,source,tmp):
    rng=random.Random("wal-audit/"+name)
    basepath=tmp/(name+"-base.sqlite")
    fastpath=tmp/(name+"-maintained.sqlite")
    writers=[setup(basepath,False),setup(fastpath,True)]
    cache_reads=[connect(basepath),connect(basepath)]
    live=connect(basepath)
    maintained=connect(fastpath)
    conns=[*writers,*cache_reads,live,maintained]
    before=[s for s in source if s[0]<START]
    arrivals=[s for s in source if START<=s[0]<STOP]
    initial=[(i+1,s[2]) for i,s in enumerate(before)]
    assert initial and arrivals
    seed_times=[measured(seed,w,initial)[1] for w in writers]
    counts=Counter(s[2] for s in before)
    head=len(before)
    def gold():
        return {"total":[(head,)],"authors":[(len(counts),)],
                "top3":sorted(counts.items(),key=lambda kv:(-kv[1],kv[0]))[:3]}
    latest=gold()
    caches={}
    refreshes=[]
    def refresh(slot,day):
        caches[slot],ns=measured(snapshot,cache_reads[slot])
        assert caches[slot]==(head,latest)
        refreshes.append(dict(day=day,slot=slot,ns=ns))
    refresh(0,-1)
    refresh(1,-1)
    rows=[]
    pairs=[]
    writes=[]
    published=[head]
    memo={p:{} for p in ("lazy_gate","publish_memo")}
    j=0
    def current_head():
        return live.execute(HEAD).fetchone()[0]
    def paired_view():
        observed=current_head()
        assert observed==head
        i=int(caches[1][0]>caches[0][0])
        return {"response":observed,"fresh":observed==caches[i][0],
                "correct":{key:caches[i][1][key]==latest[key] for key in QUERY}}

    def advance(t):
        nonlocal j,head,latest
        while j<len(arrivals) and arrivals[j][0]<=t:
            when,sha,author=arrivals[j]
            state0=paired_view()
            ids=[0,1]
            rng.shuffle(ids)
            timing=[0,0]
            for k in ids:
                _,timing[k]=measured(writers[k].execute,"INSERT INTO commits VALUES(?,?)",(head+1,author))
            tick=time.perf_counter_ns()
            published[0]=head+1
            notification=time.perf_counter_ns()-tick
            writes.append(dict(when=when,ns=timing,notification_ns=notification))
            head+=1
            counts[author]+=1
            latest=gold()
            state1=paired_view()
            pairs.append(dict(commit=sha,when=when,cache_heads=[caches[s][0] for s in (0,1)],
                              before=state0,after=state1))
            j+=1
    try:
        for day in range(365):
            midnight=START+day*86400
            advance(midnight)
            refresh(day%2,day)
            for hour in (12,23):
                advance(midnight+hour*3600)
                for task in QUERY:
                    previous={p:cache.copy() for p,cache in memo.items()}
                    hits={p:task in cache and cache[task][0]==head for p,cache in previous.items()}
                    def deliver(policy):
                        if policy=="primary": return caches[0][1][task]
                        if policy=="backup": return caches[1][1][task]
                        if policy=="live": return query(live,QUERY[task])
                        if policy=="summary": return query(maintained,FAST[task])
                        if policy in memo:
                            epoch=published[0] if policy=="publish_memo" else current_head()
                            if task=="total": return [(epoch,)]
                            old=memo[policy].get(task)
                            if old is not None and old[0]==epoch: return old[1]
                            value=query(live,QUERY[task])
                            memo[policy][task]=(epoch,value)
                            return value
                        k=int(caches[1][0]>caches[0][0])
                        if policy=="newest": return caches[k][1][task]
                        value=current_head()
                        if policy=="fused_gate" and task=="total": return [(value,)]
                        if value==caches[k][0]: return caches[k][1][task]
                        return query(live,QUERY[task])
                    samples={p:[] for p in POLICIES}
                    answers={}
                    for rep in range(6):
                        methods=list(POLICIES)
                        rng.shuffle(methods)
                        for policy in methods:
                            if policy in memo: memo[policy]=previous[policy].copy()
                            result,ns=measured(deliver,policy)
                            if rep: samples[policy].append(ns)
                            if policy in answers: assert answers[policy]==result
                            answers[policy]=result
                    assert all(answers[k]==latest[task] for k in ("live","summary","head_gate","fused_gate",*memo))
                    rows.append(dict(day=day,hour=hour,task=task,public_heads=[caches[s][0] for s in (0,1)],
                        probe=current_head(),gold=latest[task],out=answers,memo_hits=hits,ns={k:statistics.median(v) for k,v in samples.items()}))
        advance(STOP-1)
        assert j==len(arrivals)
    finally:
        for c in conns:c.close()
    return dict(initial=len(initial),seed_ns=seed_times,commits=len(arrivals),refresh=refreshes,write=writes,
                requests=rows,paired=pairs)


if __name__=="__main__":
    if sys.argv[1]=="freeze": freeze()
    else:
        assert hashes()==load("lock.json")["hashes"]
        with tempfile.TemporaryDirectory() as folder:
            for name,source in load("streams.json").items():
                save(name+".json",run(name,source,Path(folder)))

