"""Independent semantic oracle for P81 SQL tasks, including unspecified ties."""
import json,re,sqlite3

def semantic_sql_result(row,observation,db_path):
    obj=json.loads(observation) if isinstance(observation,str) else observation
    result=obj.get('result')
    if not obj.get('ok') or not isinstance(result,dict) or result.get('columns')!=['name']:return False
    returned=result.get('rows',[])
    if not isinstance(returned,list) or any(not isinstance(x,list) or len(x)!=1 for x in returned):return False
    names=[x[0] for x in returned]
    if len(names)!=len(set(names)):return False
    table=re.search(r'FROM\s+(\w+)',row['expected_arguments']['sql'],re.I).group(1)
    with sqlite3.connect('file:'+str(db_path)+'?mode=ro',uri=True) as c:
        records=c.execute(f'SELECT id,name,score FROM {table}').fetchall()
    op=row['operation'];eligible=[x for x in records if op=='sort' or x[2]>50]
    lookup={x[1]:x for x in eligible}
    if any(n not in lookup for n in names):return False
    if op=='filter':return set(names)==set(lookup)
    if len(names)!=min(4,len(eligible)):return False
    if op=='filter_sort_tie':return names==[x[1] for x in sorted(eligible,key=lambda x:(-x[2],x[0]))[:4]]
    # With no tie rule, any subset/order at equal boundary score is legal.
    return [lookup[n][2] for n in names]==sorted([x[2] for x in eligible],reverse=True)[:4]
