"""Extract testable clause types and slots from public documentation only."""
import ast
from hashlib import sha256
import re
from time import perf_counter_ns
from issre_boundary_frame import PROJECTS, git

MODULES = {"blinker":{"src/blinker/base.py":{"Signal"}},
           "pluggy":{"src/pluggy/_hooks.py":{"HookCaller"},"src/pluggy/_manager.py":{"PluginManager"}}}


def compile_clause(method, doc):
    text = " ".join(doc.split())
    flat = text.replace("*","").replace("\x60","")
    emitted = re.search(r"Emitted after (?:each )?:meth:(\w+)\.",flat)
    args = re.search(r"arguments are passed through: ([\w, ]+)\.",flat)
    if emitted and args and "sender is the signal instance" in flat.lower():
        names = re.findall(r"\w+",args[1].replace(" and "," "))
        return ("notification",emitted[1],method,names)
    if "passing on kwargs" in flat and "pairing receivers with their return" in flat:
        return ("forward",method,"receiver",["sender","kwargs"])
    historic = re.search(r":param (\w+): If provided, will be called for each non-None result",flat)
    if historic and "plugins which will be registered afterwards" in flat:
        return ("deferred",method,historic[1],["result","late_registration"])
    if "additional temporarily participating" in flat and "kwargs as call parameters" in flat:
        return ("temporary",method,"additional_method",["kwargs","membership"])
    watchers = re.findall(r"(before|after)\(([^)]+)\)",flat)
    if len(watchers)==2 and "ahead of all hook calls" in flat and "undo function" in flat:
        return ("monitor",method,"+".join(w[0] for w in watchers),["kwargs","outcome","undo"])
    return None


def extract(p):
    documents = []
    for path, classes in MODULES[p].items():
        blob = git(p,"show",PROJECTS[p][1]+":"+path)
        for cls in ast.parse(blob).body:
            if not isinstance(cls,ast.ClassDef) or cls.name not in classes:
                continue
            for node in cls.body:
                if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) or node.name.startswith("_"):
                    continue
                doc = ast.get_docstring(node)
                if doc:
                    documents.append((path,cls.name,node.name,doc,node.body[0].lineno))
    start = perf_counter_ns()
    records = []
    for path,cls,method,doc,line in documents:
        result = compile_clause(method,doc)
        if result:
            kind,action,observer,fields = result
            records.append(dict(id=cls+"."+method,kind=kind,action=action,observer=observer,fields=fields,
                source=path,line=line,doc_sha256=sha256(doc.encode()).hexdigest()))
    return {"documents_examined":len(documents),"records":records,"match_ns":perf_counter_ns()-start}

