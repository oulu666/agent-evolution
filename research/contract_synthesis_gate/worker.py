"""Run only the selected public formatter; README text is never evaluated."""
import importlib
import json
import re
import sys
from time import perf_counter_ns
from hypothesis import given, settings, strategies as st


def run(fn, proj, checks, tasks):
    calls=0
    def invoke(x,kw):
        nonlocal calls
        calls+=1
        try:
            out=fn(x,**kw)
            return ("ok",out) if isinstance(out,str) else ("type",type(out).__name__)
        except Exception as exc:
            return ("error",type(exc).__name__)

    def check(r, got=None):
        x,kw,k=r["arg"],r["kw"],r["kind"]
        v=invoke(x,kw) if got is None else got
        if k=="raises":
            return v==("error",r["want"])
        if v[0]!="ok":
            return False
        if k in ("exact","exact_new"):
            return v[1]==r["want"]
        if k=="equiv":
            return v==invoke(x,r["other"])
        if k=="bound":
            return len(v[1])<=kw["max_length"]
        if k=="absent":
            return not set(map(str.lower,kw["stopwords"])) & set(v[1].lower().split("-"))
        raise ValueError(k)

    literals=[r for r in checks if r["kind"]=="exact"]
    verdicts=[]
    for i,r in enumerate(checks):
        n=calls
        verdicts.append(dict(i=i, passed=check(r),calls=calls-n))
    assert calls<=72

    def prop(arg,kw,result):
        if result[0]!="ok" or not result[1].strip():
            return False
        if proj=="num2words":
            return not any(c.isdecimal() for c in result[1])
        if kw or not arg.isascii():
            return True
        return invoke(result[1],{})==result
    props=[]
    domain=(st.integers(0,99999) if proj=="num2words" else
            st.text(alphabet="abcdef ABCDEF-0123456789",min_size=2,max_size=20).filter(lambda t:any(c.isalnum() for c in t)))
    @settings(max_examples=24,derandomize=True,database=None,deadline=None)
    @given(domain)
    def generated(x):
        n=calls
        v=invoke(x,{})
        props.append(dict(x=x,passed=prop(x,{},v),calls=calls-n))
    generated()
    def literal_verdict(x,kw,v):
        same=next((r for r in literals if r["arg"]==x and r["kw"]==kw),None)
        if same:
            return check(same,v)
        nearest=min(literals,key=lambda r:len(set(r["kw"])^set(kw)))
        return check(nearest)
    def policy(method,x,kw):
        v=invoke(x,kw)
        if v[0]!="ok" or method=="type":
            return v,v[0]=="ok"
        if method=="property":
            return v,prop(x,kw,v)
        if method=="synthesis":
            exact=next((r for r in checks if r["kind"] in ("exact","exact_new") and r["arg"]==x and r["kw"]==kw),None)
            if exact:
                return v,check(exact,v)
            for r in checks:
                k=r["kind"]
                if k=="equiv" and r["kw"]==kw:
                    return v,v==invoke(x,r["other"])
                if k=="bound" and set(kw)<= {"max_length","word_boundary"} and kw.get("max_length",0)>0 and x.isascii():
                    return v,len(v[1])<=kw["max_length"]
                if k=="absent" and set(kw)=={"stopwords"} and x.isascii():
                    return v, not set(map(str.lower,kw["stopwords"])) & set(v[1].lower().split("-"))
        return v,literal_verdict(x,kw,v)
    deliveries=[]
    for i,(x,kw) in enumerate(tasks):
        for m in ("type","property","examples","synthesis"):
            n=calls
            start=perf_counter_ns()
            v,deliver=policy(m,x,kw)
            elapsed=perf_counter_ns()-start
            assert calls-n<=2
            deliveries.append(dict(i=i,method=m,v=v,deliver=deliver,calls=calls-n,ns=elapsed))
    return dict(assertions=verdicts,properties=props,deliveries=deliveries)


if __name__=="__main__":
    inp=json.load(sys.stdin)
    sys.path.insert(0,sys.argv[1])
    proj=inp["project"]
    modname="num2words" if proj=="num2words" else "slugify"
    try:
        mod=importlib.import_module(modname)
        from pathlib import Path
        assert Path(mod.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())
        fn=getattr(mod,modname)
    except Exception as exc:
        print(json.dumps(dict(import_error=type(exc).__name__+": "+str(exc))))
    else:
        print(json.dumps(run(fn,proj,inp["checks"],inp["tasks"])))
