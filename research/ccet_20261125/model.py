"""Estimate diagnosticity from development releases; convert probe colours to target risk."""
from datetime import date
import math

EPS=.05
PROBE_COST=.06
FALLBACK_COST=.25
MODES=("pooled","category","contract","ccet")


def signature(tool,x):
    if tool=="week":
        d=date.fromisoformat(x)
        bound=(d.month==1 and d.day<=3) or (d.month==12 and d.day>=28)
        return (int(bound),d.month,date(d.year-(d.month==1),1,1).weekday())
    return (int(x>31),int(x>=60),float(x).is_integer())


def pairs(worlds):
    for world in worlds:
        n=len(world)
        for i,(target,bad) in enumerate(world):
            for j,(source,failed) in enumerate(world):
                if i!=j:
                    yield target,source,bad,failed,1/(n*(n-1))


def relation(target,source):
    return tuple(a==b for a,b in zip(target,source))


class Transfer:
    def __init__(self,fit,cal):
        self.fit=fit
        self.rows=list(pairs(fit))
        self.buckets={}
        self.prior_by_scope={}
        for scope in (0,1):
            rates=[sum(b for s,b in w if s[0]==scope)/sum(s[0]==scope for s,b in w)
                   for w in fit if any(s[0]==scope for s,b in w)]
            self.prior_by_scope[scope]=EPS+(1-2*EPS)*sum(rates)/len(rates)
        # Calibration examples use separate tools from both fitting and release evaluation.
        self.alpha={}
        calibration=list(pairs(cal))
        for mode in MODES:
            candidates=(0,.25,.5,.75,1.)
            losses=[]
            for a in candidates:
                loss=0
                for x,p,b,f,weight in calibration:
                    l=self.likelihood(mode,x,p,a)
                    pred=self.update(self.prior_by_scope[x[0]],l,f)
                    loss+=weight*(pred-b)**2
                losses.append(loss)
            self.alpha[mode]=candidates[min(range(len(losses)),key=losses.__getitem__)]

    def stats(self,mode,x,p):
        match=relation(x,p)
        key=mode,match
        if key in self.buckets:
            return self.buckets[key]
        samples={False:[],True:[]}
        # One conditional rate per release, so overlapping input pairs do not inflate precision.
        for w in self.fit:
            rr=list(pairs([w]))
            for bad in samples:
                sel=[f for a,b,y,f,_ in rr if y==bad and (mode!="ccet" or relation(a,b)==match)]
                if sel:
                    samples[bad].append(sum(sel)/len(sel))
        means=[]
        variances=[]
        for rates in samples.values():
            a=.5+sum(rates)
            b=.5+len(rates)-sum(rates)
            means.append(a/(a+b))
            variances.append(a*b/((a+b)**2*(a+b+1)))
        delta=max(0,means[1]-means[0])
        noise=math.sqrt(sum(variances)) if mode=="ccet" else 0
        transfer=max(0,delta-noise)
        if (mode=="category" and not match[0]) or (mode=="contract" and not all(match)):
            transfer=0.
        mid=sum(means)/2
        self.buckets[key]=(mid,transfer)
        return mid,transfer

    def likelihood(self,mode,x,p,alpha=None):
        mid,t=self.stats(mode,x,p)
        scale=self.alpha[mode] if alpha is None else alpha
        return (mid-scale*t/2,mid+scale*t/2)

    @staticmethod
    def update(prior,likelihood,failed):
        ok,bad=likelihood
        if not failed:
            ok,bad=1-ok,1-bad
        return prior*bad/((1-prior)*ok+prior*bad)


def terminal(risk,severity,allowed,confidence):
    opts={"primary":(1-confidence*(1-risk))*severity,"defer":1.}
    if allowed:
        opts["fallback"]=FALLBACK_COST+severity*(1-confidence)
    action=min(opts,key=opts.get)
    return opts[action],action


def plan(model,mode,x,probes,first,choices,observe,allowed,severity,forced,confidence):
    # observe memoizes exact probe identity; index rather than colour identifies the request.
    initial=observe(first)
    prior=model.prior_by_scope[x[0]]
    like=model.likelihood(mode,x,probes[first])
    risk=model.update(prior,like,initial)
    best,act=terminal(risk,severity,allowed,confidence)
    if forced:
        best=float("inf")
    selected=None
    for j in choices:
        s=probes[j]
        if j==first: continue
        l=model.likelihood(mode,x,s)
        pf=(1-risk)*l[0]+risk*l[1]
        value=PROBE_COST+sum(prob*terminal(model.update(risk,l,failed),severity,allowed,confidence)[0]
                             for failed,prob in ((True,pf),(False,1-pf)))
        if value<best:
            selected,best=j,value
    if selected is not None:
        risk=model.update(risk,model.likelihood(mode,x,probes[selected]),observe(selected))
        act=terminal(risk,severity,allowed,confidence)[1]
    return act,risk

