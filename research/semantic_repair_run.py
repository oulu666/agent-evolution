"""Cached greedy inference and the matched archive-based constraint repair experiment."""
import argparse
import hashlib
import json
import re
import subprocess
import time
from itertools import product

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from run_interface_induction_pilot import interpret, replay
from run_rsi_operator_memory import FrozenAgent, ROOT, conversation_text

OUT = ROOT / 'runs_semantic_repair_20261123'
OUT.mkdir(exist_ok=True)


def save(name, obj):
    path = OUT / name
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf8')
    tmp.replace(path)


def as_json(raw):
    s = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', raw, flags=re.I).strip()
    try:
        return json.loads(s)
    except ValueError:
        return None


class Inference:
    def __init__(self, size):
        self.size = size
        if size == '06':
            a = FrozenAgent()
            self.model, self.tok = a.model, a.tok
        else:
            folder='/home/egret/models/Qwen3-1.7B'
            self.tok=AutoTokenizer.from_pretrained(folder,local_files_only=True)
            self.model=AutoModelForCausalLM.from_pretrained(folder,device_map={'':'cuda:0'},
                dtype=torch.float16,local_files_only=True).eval()
        self.tok.padding_side='left'
        self.file=OUT/f'generations_{size}.jsonl'
        self.cache={}
        if self.file.exists():
            for line in self.file.read_text().splitlines():
                item=json.loads(line)
                self.cache[item['hash']]=item

    @torch.inference_mode()
    def run(self, prompts, limit):
        def key(p):
            return hashlib.sha256(f'{limit}/{p}'.encode()).hexdigest()
        missing=list(dict.fromkeys(p for p in prompts if key(p) not in self.cache))
        for off in range(0,len(missing),4):
            while b'r5apex' in subprocess.check_output(['tasklist.exe','/FO','CSV','/NH']).lower():
                time.sleep(15)
            batch=missing[off:off+4]
            texts=[conversation_text(self.tok,[dict(role='user',content=p)],True) for p in batch]
            enc=self.tok(texts,padding=True,add_special_tokens=False,return_tensors='pt').to('cuda')
            outputs=self.model.generate(**enc,do_sample=False,max_new_tokens=limit,pad_token_id=self.tok.eos_token_id)
            with self.file.open('a') as f:
                for p, seq in zip(batch,outputs[:,enc.input_ids.shape[1]:]):
                    raw=self.tok.decode(seq,skip_special_tokens=True).strip()
                    item=dict(hash=key(p),prompt=p,raw=raw,tokens=sum(t!=self.tok.eos_token_id for t in seq.tolist()))
                    self.cache[key(p)]=item
                    f.write(json.dumps(item)+'\n')
        return [self.cache[key(p)] for p in prompts]


def experiment_a(engine):
    data=json.loads((ROOT/'runs_interface_induction_20261123/results.json').read_text())
    jobs=[]
    for row in data:
        obs=row['calibration']
        keys=list(obs[0]['records'][0])[1:]
        prior=row['stages']['first']
        n=max(len(x['returned']) for x in obs)
        prefix=('Infer an executable contract for calendar.list(): it returns an ordered first page of event IDs. '
                f'Each event has fields id, {keys[0]}, {keys[1]}. The time fields are integers. ')
        full=('Write a single JSON object with exactly these keys: "key" (actual field name used for sorting), '
              '"direction" ("asc" or "desc"), "take" (positive integer maximum page size or null for unlimited). ')
        evidence=('Use the supplied fixture records and actual API returns when available. Give your best hypothesis. '
                  'Return JSON only.\nObservations: '+json.dumps(obs,separators=(',',':'))+
                  '\nPrior proposal to reconsider: '+prior['raw'])
        witness=f"\nObserved {n} records in one response; take = {prior['rule']['take']} is inconsistent."
        prompts=[prefix+full+evidence, prefix+full+evidence+witness,
                 prefix+'Only patch the page size. Return a JSON object with exactly one field "take", a positive integer or null. '+evidence+witness]
        jobs.append((row,prompts))
    arms=[0,1,2] if engine.size!='06' else [1,2]
    generated=iter(engine.run([p[a] for _,p in jobs for a in arms],96))
    records=[]
    for row,p in jobs:
        obs=row['calibration']
        fields=list(obs[0]['records'][0])
        prior=row['stages']['first']['rule']
        n=max(len(x['returned']) for x in obs)
        result={}
        for i in range(4):
            if i==3:
                # All compatible programs are considered. Refuse ambiguity unless A1 is itself compatible.
                feasible=[]
                for key,d,k in product(fields,['asc','desc'],[None,*range(1,len(obs[1]['records'])+1)]):
                    rule=dict(key=key,direction=d,take=k)
                    if all(replay(rule,x['records'])==x['returned'] for x in obs):
                        feasible.append(rule)
                a1=result['A1']['rule']
                rule=a1 if a1 in feasible else feasible[0] if len(feasible)==1 else None
                raw=None
            else:
                raw=row['stages']['revision']['raw'] if i==0 and engine.size=='06' else next(generated)['raw']
                value=as_json(raw)
                if i==2:
                    value={**prior,**value} if isinstance(value,dict) and set(value)=={'take'} else None
                    rule=interpret(json.dumps(value),fields)
                else:
                    rule=interpret(raw,fields)
            result[f'A{i}']=dict(raw=raw,rule=rule,count_ok=rule is not None and (rule['take'] is None or rule['take']>=n),
                correct_take=rule is not None and rule['take']==row['truth']['take'],exact=rule==row['truth'],
                consistent=all(replay(rule,x['records'])==x['returned'] for x in obs),
                held=sum(replay(rule,x)==y for x,y in zip(row['held_inputs'],row['held_returns'])))
        records.append(dict(truth=row['truth'],prior=prior,observed=n,arms=result))
    save(f'A_{engine.size}.json',records)
    print('A',engine.size,{a:sum(r['arms'][a]['count_ok'] for r in records) for a in result},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('size',choices=['06','17'])
    experiment_a(Inference(parser.parse_args().size))
