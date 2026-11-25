"""Boundary holdout for correlation between individually insufficient public observations."""
import itertools as it
import json
import sqlite3
import xml.etree.ElementTree as ET

OPS = ('outgoing_handle','before_data','key','incoming_handle','after_data','revision')
TYPES = dict(zip(OPS, ('handle','blob','str','handle','blob','str'),strict=True))

def other(a, a0,a1):
    return a1 if a==a0 else a0

def sql(sku,a,b,start,finish):
    con=sqlite3.connect(':memory:')
    try:
        con.execute('CREATE TABLE rowstore (sku TEXT UNIQUE, value TEXT NOT NULL)')
        # NOT the INTEGER PRIMARY KEY schema; allocate a separate row identity.
        con.execute('INSERT INTO rowstore(rowid,sku,value) VALUES(?,?,?)',(a,sku,start))
        before_h,before_v=con.execute('SELECT rowid, value FROM rowstore WHERE sku=?',(sku,)).fetchone()
        if b==a:
            con.execute('UPDATE rowstore SET value=? WHERE sku=?',(finish,sku))
        else:
            con.execute('INSERT OR REPLACE INTO rowstore(rowid,sku,value) VALUES(?,?,?)',(b,sku,finish))
        after_h,after_v=con.execute('SELECT rowid, value FROM rowstore WHERE sku=?',(sku,)).fetchone()
        return before_h,before_v,after_h,after_v
    finally:
        con.close()

def xml(sku,a,b,start,finish):
    root=ET.Element('catalog')
    first=ET.SubElement(root,'item',{'sku':sku})
    first.text=start
    # A live recipient maps owned object references to opaque application handles.
    handles={first:a}
    before_h,before_v=handles[first],ET.tostring(first,encoding='unicode')
    if b==a:first.text=finish
    else:
        root.remove(first)
        new=ET.SubElement(root,'item',{'sku':sku})
        new.text=finish
        handles[new]=b
    check=root.find('item')
    return before_h,before_v,handles[check],ET.tostring(check,encoding='unicode')

def examples(domain,offset):
    run={'sqlite':sql,'elementtree':xml}[domain]
    rows=[]
    for j in range(offset,offset+12):
        a,b=2*j+78,2*j+79
        key,start,finish,revision=f'sku-{j}',f'v{j}',f'v{j+1}',f'cycle-{j%3}'
        block=[]
        for h,preserve in it.product((a,b),(False,True)):
            nxt=h if preserve else other(h,a,b)
            prev_h,prev_v,next_h,next_v=run(key,h,nxt,start,finish)
            block.append((dict(zip(OPS,(next_h,prev_v,key,prev_h,next_v,revision),strict=True)),preserve))
        assert len({obs['after_data'] for obs,_ in block})==1
        for op in OPS:
            assert sorted(r[op] for r,y in block if y)==sorted(r[op] for r,y in block if not y)
        rows.extend(block)
    return rows

def train_rule(columns,rows):
    if len(columns)<2:
        count={}
        def key(row):return tuple(row[c] for c in columns)
        for r,y in rows:
            n=count.setdefault(key(r),[0,0])
            n[y]+=1
        return lambda r: (lambda n:n[1]>n[0])(count.get(key(r),[0,0]))
    if len(columns)==2 and TYPES[columns[0]]==TYPES[columns[1]]:
        x,z=columns
        polarity=max((False,True),key=lambda sign:sum(((r[x]==r[z])==sign)==y for r,y in rows))
        return lambda r:(r[x]==r[z])==polarity
    return None

def accuracy(rule,rows):
    return sum(rule(r)==y for r,y in rows)

def identify(train,solver):
    checked=0
    best=()
    best_n=0
    for n in (0,1,2):
        if solver=='balance_pruning' and n==1:
            # Input-free constant is kept; none of the singleton finite-table rules
            # can improve it when conditional label marginals are identical.
            if all(all(sum(y for r,y in train if r[c]==v)*2==sum(r[c]==v for r,y in train)
                       for v in {r[c] for r,y in train}) for c in OPS):continue
        for columns in it.combinations(OPS,n):
            rule=train_rule(columns,train)
            if rule is None:continue
            checked+=1
            hits=accuracy(rule,train)
            if hits>best_n:best,best_n=columns,hits
            if hits==len(train):return best,best_n,checked
    return best,best_n,checked

def main():
    result={}
    for domain in ('sqlite','elementtree'):
        train=examples(domain,0); sealed=examples(domain,24)
        metrics={}
        for solver in ('balance_pruning','shortest_exact'):
            cols,nhit,checked=identify(train,solver)
            rule=train_rule(cols,train)
            metrics[solver]=dict(columns=cols,train_correct=nhit,test_correct=accuracy(rule,sealed),
                                 test_positive_call_cost=len(cols)*len(sealed),trained_rules=checked)
        metrics['best_single_development']=max(accuracy(train_rule((c,),train),train) for c in OPS)
        metrics['best_single_holdout_retro']=max(accuracy(train_rule((c,),sealed),sealed) for c in OPS)
        metrics['blocks_each']=12
        metrics['cases_each']=len(sealed)
        result[domain]=metrics
    print(json.dumps(dict(sqlite=sqlite3.sqlite_version,results=result),indent=2,sort_keys=True))

if __name__=='__main__':main()
