"""Permission-bounded third requests and paired black-box services."""
import datetime as dt
import hashlib
import json
import random
from itertools import product
from risk_worlds import pool,run
from third_probe_identifiability import OUT,save

RULES=pool()[1]+pool()[2]
DEV=('size','ties','order')
TEST=('conditional','month','leap','history')


def make(day,span,n,times,owners,seed,name):
    start=dt.date.fromisoformat(day)
    end=start+dt.timedelta(days=span)
    rng=random.Random(seed)
    labels=rng.sample(range(100,990),n)
    if seed%3 and n>3:
        labels[1]=labels[0]
        labels[-1]=labels[2]
    rows=[(str(labels[j]),j%times,'g'+str(j%owners),j%3,(n-j)%9) for j in range(n)]
    rng.shuffle(rows)
    return dict(name=name,start=day,end=end.isoformat(),rows=rows)


def public(layout):
    seed=721902+layout*233
    h=[('uid','page'),('drop1','page'),('rank_down','page')][layout%3]
    # Two distinct, ordinary, non-boundary requests. Make them neutral to the paired challenge mechanisms.
    first=[make(f'2040-04-{2+j*4:02}',1,7+j,20,20,seed+j,'past'+str(j)) for j in range(2)]
    for x in first:
        # The first three slots are ordinary, active events.
        x['rows']=[(i,t,g,0 if t<3 else s,r) for i,t,g,s,r in x['rows']]
    rng=random.Random(seed)
    # Each saved view is a distinct read-only calendar. Its listed events belong to its window.
    # There are no writes or arbitrary subwindows in this finite read-only API.
    dates=['2040-05-11','2040-08-30','2041-12-31','2040-02-28','2042-10-09']
    saved=[]
    for j in range(10):
        d=rng.choice(dates if layout%3 else dates[:2])
        saved.append(make(d,rng.choice([0,1,3]),rng.randint(4,10),rng.randint(2,8),rng.randint(1,6),seed+20+j,'saved'+str(j)))
    # Existing recent windows can legally be requested again in both permission settings.
    catalog=first+saved
    for j in range(18):
        catalog.append(make(rng.choice(dates),rng.choice([0,1,3,7]),rng.choice([3,7,11,15]),rng.choice([1,3,12]),
                            rng.choice([1,2,8]),seed+100+j,'built'+str(j)))
    return h,first,catalog


def evaluate(h,mechanism,req,history):
    rows=req['rows']
    expected=run(rows,h)
    day=dt.date.fromisoformat(req['start'])
    end=dt.date.fromisoformat(req['end'])
    if mechanism=='size' and len(rows)>10:
        return tuple(r[0] for r in sorted(rows,key=lambda r:-r[4])[:3])
    if mechanism=='ties' and len({r[1] for r in rows})<len(rows):
        return run(rows,('id_down','page'))
    if mechanism=='order' and any(r[3]==1 for r in sorted(rows,key=lambda r:r[1])[:3]):
        return run(rows,('page','drop1'))
    if mechanism=='conditional':
        seen=set()
        kept=[]
        for r in sorted(rows,key=lambda v:v[1]):
            if r[3]==2:
                if r[2] in seen:
                    continue
                seen.add(r[2])
            kept.append(r)
        return run(kept,h)
    if mechanism=='month' and (day.year,day.month)!=(end.year,end.month):
        return expected[:-1]
    if mechanism=='leap' and any((day+dt.timedelta(days=j)).month==2 and (day+dt.timedelta(days=j)).day==29
                                 for j in range((end-day).days+1)):
        return expected[1:]
    if mechanism=='history' and history and req['name']==history[-1]['name']:
        return ()
    return expected


def model_prompt(layout,permission,order=None):
    h,history,bank=public(layout)
    bank=bank[:12] if permission=='read' else bank
    order=list(range(len(bank))) if order is None else order
    bank=[bank[i] for i in order]
    menu=[(i,x['start'],x['end'],len(x['rows']),len({r[1] for r in x['rows']}),len({r[2] for r in x['rows']})) for i,x in enumerate(bank)]
    traces=[dict(window=x['name'],rows=x['rows'],result=run(x['rows'],h)) for x in history]
    return ('Act as a tester of a calendar API. A proposed contract sorts by time, then executes '+str(h)+
            '. uid means keep first event per ID; drop1 excludes status 1; rank_down breaks time ties by descending rank; '
            'page takes three. Row fields are ID,time,owner,status,rank. Two successful calls in order: '+json.dumps(traces,separators=(',',':'))+
            '. Choose ONE third test likely to refute a false contract, even when its defect is outside the known rules. '
            'Permitted existing requests [index,start_date,end_date,row_count,distinct_times,distinct_owners]: '+json.dumps(menu,separators=(',',':'))+
            '. Public row arrays in that same order: '+json.dumps([x['rows'] for x in bank],separators=(',',':'))+
            f'. Indices {order.index(0)} and {order.index(1)} repeat the first and second requests. Return '+ 
            '{"index":integer,"reason":"suspected failure condition"}.'+
            (' You may instead construct a new calendar with JSON {"date":"YYYY-MM-DD","span":days_from_start_0_to_31,'
             '"n":row_count_1_to_24,"times":distinct_time_slots_1_to_24,"owners":owner_slots_1_to_24,"reason":"suspected failure condition"}.'
             if permission=='build' else ' You may only query existing calendars.'))


def parse_request(raw,layout,permission,bank):
    decoder=json.JSONDecoder()
    for pos,c in enumerate(raw):
        if c!='{':
            continue
        try:
            obj,_=decoder.raw_decode(raw[pos:])
            if type(obj)!=dict:
                continue
            i=obj.get('index')
            if type(i)==int and 0<=i<len(bank):
                return bank[i],obj
            if permission=='build':
                n,t,o,span=(obj[k] for k in ('n','times','owners','span'))
                if all(type(k)==int and 1<=k<=24 for k in (n,t,o)) and type(span)==int and 0<=span<=31:
                    return make(obj['date'],span,n,t,o,900000+layout,'model'),obj
        except (KeyError,TypeError,ValueError,OverflowError):
            pass
    return None,None
