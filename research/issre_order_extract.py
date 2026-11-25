"""Project-independent extraction of precedence from explicit ordered lists and local clauses."""
import re
from collections import defaultdict

IDENT = r"[A-Za-z_][\w.{}<>-]*(?:\(\))?"
CODE = re.compile(r"\x60+("+IDENT+r")\x60+")
ORDER = re.compile(r"(?:order (?:of|in which)|(?:execution|callback|invocation|processing) order|in (?:the |this )?(?:following )?order|(?:in |the )following sequence|sequence of (?:callbacks|actions|events|steps))",re.I)
HEADING = re.compile(r"^#{1,6}\s+(.+)")
CLAUSE = re.compile(r"\x60+("+IDENT+r")\x60+\s+(?:(?:is|are|will be)\s+)?(?:called|run|runs|executed|invoked|occurs?)\s+(before|after)\s+\x60+("+IDENT+r")\x60+",re.I)
GUARD = re.compile(r"\b(if|unless|except when|only when|may|might|optionally)\b",re.I)


def extract(body):
    lines = body.splitlines()
    scope = "document"
    section_start = 0
    marker = -1000
    signal = False
    prev = None
    facts = []
    def add(a,b,kind,line1,line2):
        if a and b and a!=b:
            facts.append(dict(left=a,right=b,kind=kind,scope=scope,lines=[line1,line2]))
    for i,line in enumerate(lines):
        n = i+1
        heading = HEADING.match(line)
        rst = i+1<len(lines) and line.strip() and re.fullmatch(r"[-=~^]{3,}",lines[i+1].strip())
        if heading or rst:
            scope = heading[1].strip() if heading else line.strip()
            section_start = n
            prev = None
            marker = -1000
            signal = bool(ORDER.search(scope))
        if ORDER.search(line):
            marker = n
        if not GUARD.search(line):
            for a,rel,b in CLAUSE.findall(line):
                add(a if rel.lower()=="before" else b,b if rel.lower()=="before" else a,"clause",n,n)
        stripped = line.strip()
        if not stripped:
            continue
        numbered = re.match(r"^(?:\d+[.)]|#\.)\s+(.+)",stripped)
        table = "|" in stripped and not stripped.startswith(("#",".."))
        if not (table or numbered):
            prev = None
            continue
        if not (signal or n-marker<=30):
            prev = None
            continue
        cell = stripped.strip("|").split("|",1)[0].strip() if table else numbered[1]
        if set(cell)<=set(":- "):
            continue
        ids = CODE.findall(cell)
        if not ids and table and re.fullmatch(IDENT,cell) and ("_" in cell or "." in cell):
            ids = [cell]
        if len(ids)!=1:
            prev = None
            continue
        token = ids[0]
        if prev:
            add(prev[0],token,"ordered_rows",prev[1],n)
        prev = (token,n)
    # Same section and direction, distinct source spans only. Keep the shortest witness.
    groups = defaultdict(list)
    for e in facts:
        groups[e["scope"]].append(e)
    derived = []
    for section,edges in groups.items():
        direct = {(e["left"],e["right"]) for e in edges}
        for src in sorted({a for a,_ in direct}):
            queue = [(src,[])]
            seen = {src}
            while queue:
                node,path = queue.pop(0)
                for e in edges:
                    target = e["right"]
                    if e["left"]!=node or target in seen:
                        continue
                    witness = path+[e["lines"]]
                    seen.add(target)
                    queue.append((target,witness))
                    if len(witness)>1 and (src,target) not in direct and len({tuple(s) for s in witness})>1:
                        derived.append(dict(left=src,right=target,scope=section,kind="transitive",spans=witness))
    return {"direct":facts,"derived":derived}

