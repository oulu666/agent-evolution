import random,json,sys
from collections import Counter
import numpy as np
from PIL import Image, ImageOps, __version__ as PILLOW
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.neighbors import KNeighborsClassifier
import sklearn
T=Image.Transpose
SIZE=9
A=((0,0),(1,6),(7,2),(2,3),(4,4),(6,7),(8,0),(0,8),(8,8))
G=[None,T.FLIP_LEFT_RIGHT,T.FLIP_TOP_BOTTOM,T.ROTATE_90,T.ROTATE_180,T.ROTATE_270,T.TRANSPOSE,T.TRANSVERSE]
INV=(0,1,2,5,4,3,6,7)
P=[(0,1,2),(1,2,0),(2,0,1)]
def cycle(im,k):
    channels=im.split()
    return Image.merge('RGB',[channels[i] for i in P[k]])
def apply(im,a):
    if a==0:return im
    if a<8:return im.transpose(G[a])
    if a==8:return ImageOps.invert(im)
    return cycle(im,a-8)
def make(seed,profile):
    r=random.Random(seed); pix=[]
    if profile=='color':
        pix=[tuple(r.randrange(256) for y in range(3)) for _ in range(SIZE**2)]
    if profile=='impulse':
        val=r.randrange(256);pix=[(val,)*3]*(SIZE**2)
        for i in r.sample(range(SIZE**2),r.randint(2,10)):
            pix[i]=tuple(r.randrange(256) for _ in range(3))
    if profile=='gray_sym':
        for y in range(SIZE):
            row=[(r.randrange(256),)*3 for _ in range(5)]
            pix+=row+row[-2::-1]
        if r.random()<.3:
            pix[r.randrange(SIZE**2)]=tuple(r.randrange(256) for _ in range(3))
    im=Image.new('RGB',(SIZE,SIZE));im.putdata(pix);return im
def exact(x,y):
    return x.mode==y.mode and x.size==y.size and x.tobytes()==y.tobytes()
def target_samples(target):
    return np.array([target.getpixel(a) for a in A],dtype=np.int16)
def geom_coord(g,x,y):
    m=SIZE-1
    return ((x,y),(m-x,y),(x,m-y),(m-y,x),(m-x,m-y),(y,m-x),(y,x),(m-y,m-x))[g]
# Verify coordinate indexing without depending on any fixture image.
def verify_geom():
    im=Image.new('RGB',(SIZE,SIZE));im.putdata([(i,0,0) for i in range(SIZE**2)])
    for g in range(8):
        out=apply(im,g)
        for x in range(SIZE):
          for y in range(SIZE):
            assert out.getpixel((x,y))==im.getpixel(geom_coord(g,x,y))
def sorted_signature(a):
    return np.sort(a,axis=-1)
def observe(im,target):
    # From the full source, nine sampled positions per geometry; no full-image trial.
    v=np.array([[im.getpixel(geom_coord(g,*a)) for a in A] for g in range(8)],dtype=np.int16)
    geo=[]
    for g in range(8):
        s=sorted_signature(v[g])
        t=sorted_signature(target)
        geo.append(min(np.sum(np.abs(s-t)),np.sum(np.abs(255-s[:,::-1]-t))))
    direct=np.array([np.sum(np.abs(v[g][:, P[k]]*(1-2*f)+255*f-target))
                     for g in range(8) for f in range(2) for k in range(3)],dtype=np.int16)
    sparse=direct[[0,6,12,18,24,30,36,42,3,1,2]]
    feature=np.concatenate([np.asarray(geo),sparse,sparse/(1+np.max(sparse))])
    return feature,direct,sparse
def corrupt(im,combo):
    g,i,p=combo
    return apply(apply(apply(im,g),8 if i else 0),8+p if p else 0)
TRAIN_COMBOS=[(g,i,p) for g in range(8) for i in range(2) for p in range(3) if 0<(bool(g)+bool(i)+bool(p))<=2]
TEST_COMBOS=[(g,1,p) for g in range(1,8) for p in (1,2)]
def training():
    xs,ys=[],[]
    rr=random.Random(871)
    for j in range(800):
        g,i,p=combo=rr.choice(TRAIN_COMBOS)
        y=make(18000+j,'color'); x=corrupt(y,combo)
        seen=target_samples(y)
        for a in (INV[g],8 if i else 0, 11-p if p else 0,0):
            nx=apply(x,a)
            if a and exact(x,nx): continue
            if a or exact(x,y):
                xs.append(observe(x,seen)[0]);ys.append(a)
            x=nx
        assert exact(x,y)
    return np.array(xs),np.array(ys)
def native(direct):
    q=int(np.argmin(direct))
    g,rem=divmod(q,6);i,p=divmod(rem,3)
    return g or (8 if i else 0) or (8+p if p else 0)
def run():
    verify_geom()
    F,Y=training()
    balanced='--balanced' in sys.argv
    assert set(Y)==set(range(11))
    kw=dict(n_estimators=56,max_depth=12,min_samples_leaf=3,n_jobs=1,random_state=314)
    shuffled=np.random.default_rng(883).permutation(Y)
    model=ExtraTreesClassifier(**kw).fit(F,Y)
    permuted=ExtraTreesClassifier(**kw).fit(F,shuffled)
    knn=KNeighborsClassifier(n_neighbors=1).fit(F,Y)
    metrics={}
    methods=('candidate','native','greedy','retrieval','shuffled')
    for idx,p in enumerate(('color','impulse','gray_sym')):
        r=random.Random(8327+idx)
        out={m:[] for m in methods}
        evidence={m:Counter() for m in methods}
        calls=Counter()
        combos=TEST_COMBOS*20 if balanced else [r.choice(TEST_COMBOS) for _ in range(320)]
        if balanced: r.shuffle(combos)
        for j,combo in enumerate(combos):
            y=make(88000+idx*1000+j+5000*balanced,p)
            source=corrupt(y,combo)
            seen=target_samples(y)
            for m in methods:
                state=source
                for _ in range(3):
                    f,d,s=observe(state,seen)
                    if m=='native':a=native(d)
                    elif m=='greedy':a=int(np.argmin(s))
                    else:a=int(dict(candidate=model,retrieval=knn,shuffled=permuted)[m].predict([f])[0])
                    evidence[m][str(a)]+=1
                    if a==0:break
                    calls[m]+=1; state=apply(state,a)
                out[m].append(exact(state,y))
        metrics[p]={m:dict(success=sum(out[m]),total=len(out[m]),calls=calls[m],emitted=dict(evidence[m]),
             candidate_only=sum(c and not o for c,o in zip(out['candidate'],out[m])),comparator_only=sum(o and not c for c,o in zip(out['candidate'],out[m])))
             for m in methods}
    print(json.dumps(dict(pillow=PILLOW,sklearn=sklearn.__version__,balanced=balanced,training_labeled_states=len(Y),train_combinations=len(TRAIN_COMBOS),test_combinations=len(TEST_COMBOS),result=metrics),indent=2))
if __name__=='__main__': run()
