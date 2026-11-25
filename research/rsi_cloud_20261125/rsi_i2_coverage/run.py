from PIL import Image, ImageOps, ImageFilter, __version__ as PILLOW
from collections import Counter
from math import log2
import hashlib, random, json
S=8
T=Image.Transpose
BASE=8
def permute(im,ind):
    b=im.split();return Image.merge('RGB',[b[i] for i in ind])
M=[lambda x:x,ImageOps.mirror,ImageOps.flip,*[lambda x,t=t:x.transpose(t) for t in (T.ROTATE_90,T.ROTATE_180,T.ROTATE_270)],lambda x:ImageOps.grayscale(x).convert('RGB'),ImageOps.invert,
   *[lambda x,k=k:permute(x,k) for k in [(1,0,2),(1,2,0),(2,1,0)]],
   lambda x:x.point(lambda n:min(n+48,255)),lambda x:x.point(lambda n:255*(n>=128)),lambda x:ImageOps.posterize(x,4),ImageOps.solarize]
def fixtures(domain):
    r=random.Random(22061+domain)
    for nominal in range(3):
      for ix in range(80):
        im=Image.new('RGB',(S,S))
        if domain==0: source=[tuple(r.randrange(256) for _ in range(3)) for _ in range(S*S)]
        elif domain==1:
            raw=[r.randrange(256) for _ in range(S*4)]
            source=[(q,)*3 for j in range(S) for q in (raw[4*j:4*j+4]+raw[4*j:4*j+4][::-1])]
            if ix%4==0: source[r.randrange(S*S)]=(0,37,150)
        else:
            bg=r.choice([(0,0,0),(255,255,255),(128,128,128),(90,90,90)])
            source=[bg]*(S*S)
            for z in range(1+ix%4):source[r.randrange(S*S)]=tuple(r.randrange(256) for _ in range(3))
        im.putdata(source)
        predictions=[tuple(a(im).tobytes()) for a in M]
        if nominal==0: target=M[r.randrange(1,BASE)](im)
        elif nominal==1: target=M[r.randrange(BASE,len(M))](im)
        elif ix%3==0: target=im.filter(ImageFilter.GaussianBlur(.6))
        elif ix%3==1: target=ImageOps.colorize(ImageOps.grayscale(im),(4,12,55),(223,201,193))
        else:
            target=M[r.randrange(len(M))](im).copy()
            x,y=r.randrange(S),r.randrange(S)
            q=target.getpixel((x,y));target.putpixel((x,y),(q[0]^1,q[1],q[2]))
        target=tuple(target.tobytes())
        cat='base' if target in predictions[:BASE] else 'extension' if target in predictions else 'impossible'
        yield [list(dict.fromkeys(predictions[:BASE])),list(dict.fromkeys(p for p in predictions[BASE:] if p not in predictions[:BASE]))],target,cat,(target in predictions[:BASE] and target!=predictions[0])
def value(p,j):
    return p[3*j:3*j+3]
def entropy(counts):
    n=sum(counts)
    return -sum(k/n*log2(k/n) for k in counts if k)
def scores(groups,j):
    counts=[Counter(value(p,j) for p in g) for g in groups]
    allcounts=counts[0]+counts[1]
    h=entropy(allcounts.values())
    # MI for a uniformly distributed catalog hypothesis, not a calibrated posterior.
    n=sum(allcounts.values())
    mi=entropy([len(g) for g in groups])-sum((k/n)*entropy([c[v] for c in counts]) for v,k in allcounts.items()) if n else 0
    return h,mi
def observe(groups,target,seed,method,budget):
    r=random.Random(seed)
    positions=r.sample(range(S*S),S*S)
    for _ in range(budget):
        if method in ('random','random_rank'):
            j=positions[0]
        else:
            def priority(j):
                h,mi=scores(groups,j)
                return (mi,h) if method=='candidate' else (h,)
            j=max(positions,key=priority)
        seen=value(target,j);positions.remove(j)
        groups=[[p for p in g if value(p,j)==seen] for g in groups]
    hit=int(bool(groups[1]))
    score=0 if method=='random' else hit*(2-int(bool(groups[0])))
    return score,r.random(),tuple(map(len,groups))
def main():
    ans={}
    for d in range(3):
      fixtures_d=list(fixtures(d))
      results={}
      for b in (1,2):
        profile={}
        for m in ('random','random_rank','entropy','candidate'):
            looking=[]
            for j,(g,t,c,e) in enumerate(fixtures_d):
                s,k,n=observe(g,t,47931+j,m,b)
                looking.append((s,k,c,e,n))
            chosen=sorted(looking,reverse=True)[:72]
            n=Counter(e[2] for e in chosen)
            count=Counter(e[2] for e in looking)
            profile[m]=dict(precision=n['extension']/72,recall=n['extension']/count['extension'],escalated={k:n[k] for k in ('base','extension','impossible')},
               nongap_wrong_identity_escalations=sum(e[3] for e in chosen),base_or_extension_false_eliminations=sum((e[2]=='base' and not e[4][0]) or (e[2]=='extension' and not e[4][1]) for e in looking), unmatched_impossible=sum(e[2]=='impossible' and e[4]==(0,0) for e in looking), target_labels=dict(count), base_selection_errors=sum(e[3] for e in looking))
        results[str(b)]=profile
      ans[('color','symmetric','sparse')[d]]=results
    print(json.dumps(dict(pillow=PILLOW,result=ans),indent=2))
if __name__=='__main__': main()
