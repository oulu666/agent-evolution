"""Compile literal examples and a small, explicitly bounded vocabulary of relations."""
import ast
import json
import re
from sample import OUT, save


def extract(s):
    lines=(OUT/(s["id"]+".txt")).read_text(encoding="utf8").splitlines()
    rows=[]
    def add(kind, arg, kw, want, ref, evidence, other=None):
        rows.append(dict(kind=kind,arg=arg,kw=kw,want=want,lines=sorted(set(ref)),evidence=evidence,other=other))
    value=call=None
    for i,line in enumerate(lines):
        txt=line.strip()
        if txt.startswith("txt = "):
            value=(ast.literal_eval(txt.split("=",1)[1].strip()), i+1)
        elif txt.startswith("r = slugify(") and value is not None:
            node=ast.parse(txt).body[0].value
            assert len(node.args)==1 and node.args[0].id=="txt"
            call=(value[0],{k.arg:ast.literal_eval(k.value) for k in node.keywords},[value[1],i+1])
        elif txt.startswith("self.assertEqual(r,") and call:
            want=ast.literal_eval(ast.parse(txt).body[0].value.args[1])
            add("exact",call[0],call[1],want,call[2]+[i+1],"literal")
            call=None
        elif txt.startswith(">>> num2words("):
            node=ast.parse(txt[4:],mode="eval").body
            add("exact",ast.literal_eval(node.args[0]),{k.arg:ast.literal_eval(k.value) for k in node.keywords},
                lines[i+1].strip(),[i+1,i+2],"literal")
    literal=list(rows)
    for i,line in enumerate(lines):
        if "unsupported language" in line and "NotImplementedError" in line:
            for n in (1,8,42):
                add("raises",n,{"lang":"zz_ZZ"},"NotImplementedError",[i+1],"explicit")
        if "English, default" in line:
            for n in (1,8,42):
                add("equiv",n,{},None,[i+1],"explicit",{"lang":"en"})
        if "fr_FR" in line and "correctly interpreted" in " ".join(lines[i:i+2]):
            for n in (1,8,42):
                add("equiv",n,{"lang":"fr_FR"},None,[i+1,i+2],"locale_inference",{"lang":"fr"})
    # Learn delimiter substitution only from a documented contrast with all other settings equal.
    sep=[]
    for a in literal:
        for b in literal:
            if a["arg"]!=b["arg"] or a is b or "separator" not in a["kw"] or "separator" not in b["kw"]:
                continue
            opts=lambda r:{k:v for k,v in r["kw"].items() if k!="separator"}
            x,y=a["kw"]["separator"],b["kw"]["separator"]
            if x==y or not x or not y or x not in a["want"] or opts(a)!=opts(b):
                continue
            if a["want"].split(x)==b["want"].split(y):
                sep.append((a,b,opts(a)))
    if sep:
        a,b,opts=sep[0]
        for new in ("_","~","|"):
            kw=dict(opts,separator=new)
            add("exact_new",a["arg"],kw,new.join(a["want"].split(a["kw"]["separator"])),
                a["lines"]+b["lines"],"contrast_inference")
    for kind,flag in (("bound","max_length"),("absent","stopwords")):
        support=[r for r in literal if flag in r["kw"] and len(r["kw"].get("separator","-"))==1]
        if kind=="bound":
            support=[r for r in support if 0<r["kw"][flag] and len(r["want"])<=r["kw"][flag]]
        else:
            support=[r for r in support if not set(map(str.lower,r["kw"][flag])) & set(r["want"].lower().split("-"))]
        if len(support)>=2:
            src=support[0]["lines"]+support[1]["lines"]
            for arg in ("green oak red","a quick blue fox","new old paper"):
                for opt in ((4,8) if kind=="bound" else ([arg.split()[0]], [arg.split()[-1]])):
                    add(kind,arg,{flag:opt},None,src,"example_inference")
    return rows


TASKS={
 "num2words":[(0,{},"zero"),(7,{},"seven"),(19,{},"nineteen"),(81,{},"eighty-one"),
     (42,{},"forty-two"),(100,{},"one hundred"),(1001,{},"one thousand and one"),(-7,{},"minus seven"),
     (1,{"ordinal":True},"first"),(12,{"ordinal":True},"twelfth"),(21,{"ordinal":True},"twenty-first"),
     (7,{"lang":"fr_FR"},"sept")],
 "python-slugify":[("Green Oak",{},"green-oak"),("oak -- elm",{},"oak-elm"),("café noir",{},"cafe-noir"),
     ("oak &amp; elm",{},"oak-elm"),("This is a test ---",{},"this-is-a-test"),
     ("blue river",{"separator":"_"},"blue_river"),("green oak red",{"max_length":5},"green"),
     ("oak elm ash",{"max_length":7},"oak-elm"),("go to school",{"stopwords":["to"]},"go-school"),
     ("Red and BLUE",{"stopwords":["and"]},"red-blue"),("oak elm",{"max_length":3,"word_boundary":True},"oak"),
     ("a blue fox",{"separator":"."},"a.blue.fox")]}


if __name__=="__main__":
    samples=json.loads((OUT/"sample.json").read_text())
    save("checks.json",{s["id"]:extract(s) for s in samples})
    save("tasks.json",TASKS)
