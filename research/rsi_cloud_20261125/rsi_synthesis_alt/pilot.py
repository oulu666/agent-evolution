"""CSV contract-recovery pilot: one real probe, one real target parse per policy."""
import argparse, collections, csv, io, itertools, json
from pathlib import Path

DELS=",;|\t"
QUOTES="\"'~"
STATES=list(itertools.product(DELS,QUOTES,(False,True)))
PROBES={
    "ordinary": [["code","total"]],
    "comma": [["labels, amount","284"]],
    "semicolon": [["labels; amount","284"]],
    "double_quote": [['after"before','284']],
    "single_quote": [["after'before","284"]],
    "line": [["north\nsouth","284"]],
    "comprehensive": [["a,b;c|d\te", "quoted\"'~value", "two\nlines", "end\\"]],
}
TASKS={
    "ordinary":[["names","cents"],["ore", "47"],["dense", "901"]],
    "delimiters":[["north,west","47"],["north;west","901"],["north|west\tsouth","10"]],
    "quotes":[["label","n"],["joined\"'~plot","17"],["joined\nline","53"]],
    "combined":[["x,y;z|w\tt","81"],["hyphen\"'~selector","802"],["row\nrow\\","42"]],
}
REGIMES={"restricted":tuple(q for q in PROBES if q!="comprehensive"),"unrestricted":tuple(PROBES)}
# Plausible prior groups announced before seeing outcomes: charset conventions
# are stable within a producer here, but deployments may mix producer types.
GROUPS=[tuple(i for i,s in enumerate(STATES) if s[0]==d) for d in DELS]
HIST=tuple((.70,.15,.10,.05)[DELS.index(s[0])]/6 for s in STATES)
MIXTURES={"historical":(.70,.15,.10,.05),"balanced":(.25,.25,.25,.25),
          "shift":(.05,.15,.25,.55)}

def encode(rows,state):
    d,q,double=state; f=io.StringIO(newline="")
    csv.writer(f,delimiter=d,quotechar=q,doublequote=double,
               escapechar=None if double else "\\",lineterminator="\r\n").writerows(rows)
    return f.getvalue()

def decode(data,state):
    d,q,double=state
    try:
        return list(csv.reader(io.StringIO(data,newline=""), delimiter=d,quotechar=q,
                               doublequote=double,escapechar=None if double else "\\",strict=True))
    except csv.Error:
        return None

def bits(v):
    return [i for i in range(len(STATES)) if (v>>i)&1]

def dominates(a,b):
    return all(x>=y for x,y in zip(a,b))

def prior(v,p):
    return sum(p[i] for i in bits(v))

def cover(v):
    return tuple(sum((v>>i)&1 for i in g) for g in GROUPS)

def ent(clusters):
    from math import log
    return -sum(p*log(p) for c in clusters.values() if (p:=prior(c,HIST)))

def policy(q,clusters,success,objective):
    options={}
    for out,worlds in clusters[q].items():
        acts={worlds&passed: a for a,passed in reversed(list(enumerate(success)))}
        options[out]=acts
    if objective=="bayes":
        return {out:max(acts.items(),key=lambda v:(prior(v[0],HIST),-v[1]))[1]
                for out,acts in options.items()}
    # Exact skyline over all feasible conditional deployment policies.
    # Every group's latent members carry equal weight within that group.
    frontier={(0,0,0,0):(0,{})}
    for out,acts in options.items():
        new={}
        for vv,sel in frontier.values():
            for v,a in acts.items():
                z=vv|v;k=cover(z)
                if k not in new:
                    new[k]=(z,dict(sel,**{out:a}))
        frontier={k:new[k] for k in new if not any(h!=k and dominates(h,k) for h in new)}
    return max(frontier.values(),key=lambda p:(min(cover(p[0])),prior(p[0],HIST)))[1]

def run(out):
    summary={}; rows=[]
    for regime,qs in REGIMES.items():
        clusters={}
        for q in qs:
            c=collections.defaultdict(int)
            for i,s in enumerate(STATES): c[encode(PROBES[q],s)]|=1<<i
            clusters[q]=c
        for name,task in TASKS.items():
            success=[sum((decode(encode(task,s),a)==task)<<i for i,s in enumerate(STATES)) for a in STATES]
            def score(q,p):
                # Reexecute the selected target parse in every latent world.
                return sum(int(decode(encode(task,s),STATES[p[encode(PROBES[q],s)]])==task)<<i
                           for i,s in enumerate(STATES))
            policies={}
            for m in ("bayes","robust","entropy"):
                opts=[]
                for q in qs:
                    p=policy(q,clusters,success,"robust" if m=="robust" else "bayes")
                    a=score(q,p)
                    obj=(min(cover(a)),prior(a,HIST)) if m=="robust" else (prior(a,HIST),) if m=="bayes" else (ent(clusters[q]),)
                    opts.append((obj,q,a))
                _,q,a=max(opts,key=lambda x:x[0]);policies[m]=(q,a)
            for m,(q,a) in policies.items():
                counts=cover(a)
                rows.append(dict(regime=regime,task=name,method=m,probe=q,n=24,
                                 correct=a.bit_count(),wrong=24-a.bit_count(),
                                 worst_group_numerator=min(counts), group_count=counts,
                                 scenarios={n: round(sum(p*x/6 for p,x in zip(ps,counts)),6)
                                            for n,ps in MIXTURES.items()}))
    p=Path(out);p.mkdir(parents=True,exist_ok=True)
    (p/"summary.json").write_text(json.dumps(rows,indent=2)+"\n")
    for x in rows: print(x)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True)
    run(p.parse_args().out)
