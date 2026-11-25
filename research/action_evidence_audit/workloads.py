"""Versioned public examples and scalar contracts. Corpus selection sees no tool output."""
from collections import defaultdict
from html.parser import HTMLParser
import json
import re

SECTIONS=("ATX headings","Setext headings","Thematic breaks","Paragraphs","Block quotes",
          "List items","Lists","Code spans","Emphasis and strong emphasis")
BLOCK={"p","h1","h2","h3","h4","h5","h6","ul","ol","li","pre","blockquote","hr"}
SCALARS={
    "boolean":[("true",True,True),("yes",True,"yes"),("NO",False,"NO"),("False",False,False),
               ("on",True,"on"),("Off",False,"Off"),("TRUE",True,True),("Yes",True,"Yes"),
               ("ON",True,"ON"),("no",False,"no"),("FALSE",False,False),("off",False,"off")],
    "integer":[("12",12,12),("012",10,12),("0o17","0o17",15),("0b101",5,"0b101"),
               ("0x13",19,19),("021",17,21),("2:15",135,"2:15"),("0o20","0o20",16),
               ("+13",13,13),("030",24,30),("0b11",3,"0b11"),("1:27",87,"1:27")],
    "quoted-or-null":[("null",None,None),("'012'","012","012"),('"yes"',"yes","yes"),("~",None,None),
               ("'no'","no","no"),("Null",None,None),('"0o20"',"0o20","0o20"),("'on'","on","on"),
               ("NULL",None,None),("'1:20'","1:20","1:20"),('"null"',"null","null"),("'~'","~","~")],
}


class Markup(HTMLParser):
    """Keep text, inline whitespace and structure. Ignore inter-block rendering newlines."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens=[]

    def handle_starttag(self,tag,attrs):
        self.tokens.append(("start",tag,tuple(sorted(attrs))))

    def handle_endtag(self,tag):
        self.tokens.append(("end",tag))

    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in ("hr","br","img"): self.handle_endtag(tag)

    def handle_data(self,data):
        self.tokens.append(("text",data))

    def result(self):
        result=[]
        for i,t in enumerate(self.tokens):
            if t[0]=="text" and t[1].strip()=="":
                adjacent=self.tokens[max(0,i-1):i]+self.tokens[i+1:i+2]
                if any(e[0]!="text" and e[1] in BLOCK for e in adjacent) and "\n" in t[1]: continue
            result.append(t)
        return result


def normalized_html(raw):
    p=Markup()
    p.feed(raw)
    p.close()
    return json.dumps(p.result(),ensure_ascii=False)


def role(i):
    return "probe" if i%5==0 else ("development" if i%5==1 else "test")


def corpus(source):
    data=[]
    by=defaultdict(int)
    for ex in source:
        section=ex["section"]
        s=ex["markdown"]
        if section not in SECTIONS or len(s)>240 or any(c in s for c in "<>[]"): continue
        i=by[section]
        by[section]+=1
        data.append(dict(project="Markdown",family=section,id=f"M{ex['example']}",text=s,
                         role=role(i),gold=normalized_html(ex["html"])))
    for version in ("1.1","1.2"):
        for family,items in SCALARS.items():
            for i,(literal,v11,v12) in enumerate(items):
                value=v11 if version=="1.1" else v12
                data.append(dict(project="YAML",family=f"{version}/{family}",id=f"Y{version}-{family}-{i:02}",
                    text=f"%YAML {version}\n---\nitem: {literal}\n",role=role(i),
                    gold=json.dumps({"item":value},sort_keys=True)))
    return data


def nearest(target,bank):
    # Compare only public syntax. Do not use reference or primary outputs.
    def shape(row):
        return set(re.findall(r"[A-Za-z]+|\d+|[^\w\s]",row["text"].casefold()))
    a=shape(target)
    options=[r for r in bank if r["family"]==target["family"] and r["project"]==target["project"]
             and r["text"]!=target["text"]]
    def key(other):
        b=shape(other)
        return (-len(a & b)/max(1,len(a | b)),abs(len(target["text"])-len(other["text"])),other["id"])
    return min(options,key=key)["id"]

