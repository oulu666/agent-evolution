"""Post-disclosure presentation-only diagnostic. Never modify primary documents or locks."""
from itertools import combinations
import re
from issre_order_run import OUT,PROJECTS,GOLD,contents,extract,read,write
from issre_order_extract import IDENT,ORDER


def normalize(text):
    lines = []
    n = 0
    in_order_list = False
    for line in text.splitlines():
        if ORDER.search(line):
            in_order_list=True
            n=0
        elif line.strip() and not re.match(r"^\s*[-*+]\s+",line):
            in_order_list=False
        if in_order_list and re.match(r"^\s*[-*+]\s+",line):
            n+=1
            line=re.sub(r"^(\s*)[-*+]\s+",lambda m:f"{m[1]}{n}. ",line)
        if "|" in line:
            line=re.sub(r"\x60'("+IDENT+r")'\x60",lambda m:chr(96)+m[1]+chr(96),line)
        lines.append(line)
    return "\n".join(lines)


def metrics(project, docs, trace):
    all_facts=[(d,k,e) for d,v in docs.items() for k in ("direct","derived") for e in v[k]]
    expected=set(combinations(GOLD[project],2))
    result={}
    for k in ("direct","derived"):
        facts=[(d,e) for d,kind,e in all_facts if kind==k]
        pairs={(e["left"],e["right"]) for d,e in facts}
        result[k]={"unique":len(pairs),"correct":len(pairs & expected),
                   "unbound":sorted([list(t) for t in pairs if any(x not in GOLD[project] for x in t)]),
                   "reversed":sorted([list(t) for t in pairs if tuple(reversed(t)) in expected])}
    edges={(e["left"],e["right"]) for d,k,e in all_facts if all(x in GOLD[project] for x in [e["left"],e["right"]])}
    adjacent=set(zip(trace,trace[1:]))
    # A numerically correct order can have an inapplicable intermediate proof step.
    # Recompute closure separately per document and scope, excluding absent events first.
    scoped={}
    for d,kind,e in all_facts:
        if kind=="direct" and e["left"] in trace and e["right"] in trace:
            scoped.setdefault((d,e["scope"]),set()).add((e["left"],e["right"]))
    supported=set()
    for scope_edges in scoped.values():
        closure=set(scope_edges)
        while True:
            extension={(a,d) for a,b in closure for c,d in closure if b==c}
            if extension<=closure: break
            closure.update(extension)
        supported.update(closure)
    masked=[]
    for i in range(len(trace)-1):
        alt=trace[:]
        alt[i:i+2]=reversed(alt[i:i+2])
        failed=any(alt.index(a)>=alt.index(b) for a,b in edges)
        if failed:masked.append([trace[i],trace[i+1]])
    result.update(identified=len(edges&expected),total=len(expected),adjacent=len(edges&adjacent),
                  adjacent_total=len(adjacent),offline_swaps_detected=len(masked),swapped_pairs=masked,
                  in_path_supported=len(supported&expected),supported_adjacent=len(supported&adjacent),
                  unsupported_agreements=sorted([list(pair) for pair in (edges&expected)-supported]))
    return result


def main():
    preds=read(OUT/"predictions.json")
    refs=read(OUT/"reference_traces.json")
    out={}
    for p,(_,rev) in PROJECTS.items():
        normalized={}
        for n,blob in contents(p,rev,True):
            text=blob.decode("utf8")
            tested=normalize(text)
            normalized[n]=extract(tested)
        out[p]={"primary":metrics(p,preds[p],refs[p]["trace"]),"normalized":metrics(p,normalized,refs[p]["trace"]),
                "normalized_records":normalized}
    write(OUT/"presentation_audit.json",out)


if __name__=="__main__": main()

