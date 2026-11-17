"""Further CPU classification of archived P8 outputs; no model generation."""
import json,re,collections,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent.utils import read_jsonl,write_json
from fac_tinyagent import p8_decision_data_20261115 as P8
RUN=ROOT/'runs_ext_p81_diagnosis_20261116';gold={r['episode_id']:r for r in read_jsonl(P8.DATA/'holdout.jsonl')}
counts=collections.defaultdict(collections.Counter);details=[]
for p in sorted((P8.RUN/'evaluation').glob('*/*/results.jsonl')):
    if p.parent.name not in ['file','database']:continue
    arm=p.parts[-3].split('_')[-1]
    for r in read_jsonl(p):
        g=gold[r['episode_id']];skill=g['skill'];key=arm+'/'+skill
        if skill not in ['file.search_last','db.filter_cmp_top']:continue
        c=counts[key];c['n']+=1
        if skill=='file.search_last':
            matches=json.loads(g['expected_observation'])['result'];texts=[m['text'] for m in matches];pred=r['predicted_answer']
            category='first' if pred==texts[0] else 'last' if pred==texts[-1] else 'all_joined' if pred=='\n'.join(texts) else 'all_list' if pred==texts else 'other'
            c[category]+=1;details.append({'model':p.parts[-3],'id':r['episode_id'],'category':category,'predicted':pred})
        else:
            q=r['predicted_arguments'].get('sql','');gq=g['expected_arguments']['sql']
            def part(pattern,s):
                m=re.search(pattern,s,re.I);return m.group(1).strip() if m else None
            table=part(r'\bFROM\s+([\w]+)',q);gt=part(r'\bFROM\s+([\w]+)',gq)
            cols=part(r'\bSELECT\s+(.+?)\s+FROM\b',q)
            limit=part(r'\bLIMIT\s+(\d+)',q);gl=part(r'\bLIMIT\s+(\d+)',gq)
            vals={'wrong_table':table!=gt,'extra_or_wrong_columns':cols is None or cols.lower()!='name','wrong_limit':limit!=gl,'missing_where':not re.search(r'\bWHERE\b',q,re.I),'missing_tie':not re.search(r'\bid\s+ASC\b',q,re.I)}
            for k,v in vals.items():c[k]+=int(v)
            details.append({'model':p.parts[-3],'id':r['episode_id'],'sql':q,**{k:bool(v) for k,v in vals.items()}})
out={'counts':dict(counts),'details':details,'note':'SQL categories are nonexclusive literal indicators for these archived simple queries, not a general semantic SQL parser.'}
write_json(RUN/'p8_detailed_errors.json',out);print(json.dumps(out['counts']))
