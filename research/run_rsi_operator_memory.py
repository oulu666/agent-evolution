"""Two frozen 0.6B choices, before/after measured execution feedback."""
import json
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fac_tinyagent.metrics import answers_equal, observations_equal
from fac_tinyagent.sft.dataset import conversation_text
from fac_tinyagent.sft.evaluate import parse_tool_call, parse_final_answer
from fac_tinyagent.tools.calendar_tools import build_calendar_registry
from rsi_operator_memory import OPERATIONS, apply_operation, in_scope
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

OUT = ROOT / 'runs_rsi_operations_20261122'
ADAPTER = ROOT / 'runs_ext_p11_eaar_v1/branches/A_seed20261108_eaar_v1/checkpoint'
BASE = '/home/egret/models/Qwen3-0.6B'
LABELS = dict(zip('ABC',random.Random(1122).sample(list(OPERATIONS),3)))
PATTERNS = [(1,0,1,2),(2,1,0,0),(0,0,1,2),(2,0,3,1),(3,2,1,0),(0,1,2,3)]
TRAIN = ['Alto','Bloom','Cedar','Delta']
HELD = ['Amber','Birch','Coral','Dune','Elm','Fern','Grove','Haze',
        'Iris','Jade','Kite','Lime','Maple','Navy','Opal','Pearl',
        'Quartz','Reed','Slate','Thyme','Umber','Vale','Willow','Zinc']


def save(name, value):
    path = OUT / name
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2))
    tmp.replace(path)


def make_bank(split):
    rng = random.Random('operator-pilot-'+split)
    words = TRAIN if split=='train' else HELD
    count = 6 if split=='train' else 12
    events, rows = [], []
    for i in range(count):
        date = f"{2071 if split=='train' else 2073}-03-{i+1:02d}"
        names = sorted(rng.sample(words,4))
        titles = [names[j] for j in PATTERNS[i%6]]
        rooms = ['Room B','Room A','Room B','Room C']
        for j,(title,loc) in enumerate(zip(titles,rooms)):
            events.append(dict(id=f"EV{date}-{j}",date=date,start=f"{9+j:02d}:00",
                end=f"{10+j:02d}:00",title=title,location=loc,attendees=['Lee']))
        title_prompts = (
            f"Collect every event title on {date}. Return a JSON array in ascending order, keeping duplicates.",
            f"For {date}, list all event titles alphabetically in a JSON array. Keep repeated titles.",
            f"Return the titles of all events on {date} in A to Z order as a JSON array, including repeats.")
        prompt = title_prompts[0 if split=='train' else 1+i%2]
        rows.append(dict(id=f'{split}-title-{i}',day=date,skill='title',prompt=prompt,gold=sorted(titles),source=titles))
        if split=='holdout' and i<8:
            rows.append(dict(id=f'hold-location-{i}',day=date,skill='location',
                prompt=f'List the distinct locations on {date}, sorted alphabetically, as a JSON array.',gold=sorted(set(rooms))))
            rows.append(dict(id=f'hold-count-{i}',day=date,skill='count',
                prompt=f'How many events occur on {date}? Return a single integer.',gold=len(titles)))
    save(split+'_fixture.json',dict(events=events))
    return rows


class FrozenAgent:
    def __init__(self):
        self.last_check=0
        self.check_game()
        self.tok=AutoTokenizer.from_pretrained(BASE,local_files_only=True)
        model=AutoModelForCausalLM.from_pretrained(BASE,dtype=torch.float16,device_map={'':'cuda:0'},local_files_only=True)
        self.model=PeftModel.from_pretrained(model,str(ADAPTER)).merge_and_unload().eval()
        self.system=json.loads((ROOT/'data_ext_p11_eaar_v1/train/rows.jsonl').open().readline())['system']
        self.calls=0

    def check_game(self):
        if time.monotonic()-self.last_check>=10:
            if b'r5apex' in subprocess.check_output(['tasklist.exe','/FO','CSV','/NH']).lower():
                raise SystemExit(75)
            self.last_check=time.monotonic()

    def encode(self,messages):
        self.check_game()
        self.calls+=1
        return self.tok(conversation_text(self.tok,messages,True),return_tensors='pt',add_special_tokens=False).to('cuda')

    @torch.inference_mode()
    def generate(self,messages,limit):
        enc=self.encode(messages)
        seq=self.model.generate(**enc,do_sample=False,max_new_tokens=limit,pad_token_id=self.tok.eos_token_id)
        return self.tok.decode(seq[0,enc.input_ids.shape[1]:],skip_special_tokens=True).strip()

    @torch.inference_mode()
    def choose(self,evidence):
        options='\n'.join(f'{label}. {OPERATIONS[key]}' for label,key in LABELS.items())
        prompt=('Choose one persistent action for the calendar assistant when a user asks for event titles '
                'in ascending order and repeated titles must be retained. The action is applied to its predicted JSON list.\n'
                +options+'\nMeasured training results: '+json.dumps(evidence)+'\nReply with exactly one letter.')
        enc=self.encode([dict(role='user',content=prompt)])
        logits=self.model(**enc,use_cache=False).logits[0,-1].float()
        ids=[self.tok.encode(label,add_special_tokens=False) for label in LABELS]
        assert all(len(a)==1 for a in ids)
        scores=logits[[a[0] for a in ids]].tolist()
        label=list(LABELS)[scores.index(max(scores))]
        return dict(label=label,operation=LABELS[label],label_logits=dict(zip(LABELS,scores)))

    def solve(self,row,registry):
        messages=[dict(role='system',content=self.system),dict(role='user',content=row['prompt'])]
        raw=self.generate(messages,96)
        call=parse_tool_call(raw)
        obs=registry.execute(call['tool'],call['arguments']) if call else dict(ok=False,error='invalid tool call')
        messages.extend([dict(role='assistant',content=raw),dict(role='user',content='TOOL RESULT:\n'+json.dumps(obs,ensure_ascii=False,sort_keys=True,separators=(',',':')))])
        final=self.generate(messages,128)
        valid,answer=parse_final_answer(final)
        args={'date':row['day']}
        core=bool(call and call['tool']=='calendar_list' and answers_equal(call['arguments'],args)
                  and observations_equal(obs,registry.execute('calendar_list',args)))
        return dict(**row,call=raw,observation=obs,raw_final=final,valid=valid,parsed=answer,core=core)


def apply_and_grade(row,operation):
    answer=apply_operation(operation,row['prompt'],row['parsed'])
    return dict(answer=answer,joint=bool(row['core'] and row['valid'] and answers_equal(answer,row['gold'])))


def main():
    OUT.mkdir(exist_ok=True)
    if (OUT/'summary.json').exists():
        print((OUT/'summary.json').read_text())
        return
    banks={split:make_bank(split) for split in ['train','holdout']}
    save('design.json',dict(checkpoint=str(ADAPTER.relative_to(ROOT)),labels=LABELS,patterns=PATTERNS,
        task='calendar_list, then postprocess only parsed list of strings in requested title-sorting scope',
        selector='greedy one-token A/B/C before and after training evidence, fixed label order and policy',
        controls=['unmodified','before_feedback','after_feedback'],banks=banks))
    agent=FrozenAgent()
    pre=agent.choose([])
    train_registry=build_calendar_registry(str(OUT/'train_fixture.json'))
    train=[agent.solve(r,train_registry) for r in banks['train']]
    save('training_answers.json',train)
    feedback=[]
    for label,operation in LABELS.items():
        outcomes=[apply_and_grade(r,operation)['joint'] for r in train]
        feedback.append(dict(action=label,correct=sum(outcomes),total=len(train),per_case=outcomes))
    post=agent.choose(feedback)
    save('memory.json',dict(before_feedback=pre,measured_feedback=feedback,after_feedback=post))
    frozen=json.loads((OUT/'memory.json').read_text())
    policies=dict(unmodified='keep',before_feedback=frozen['before_feedback']['operation'],after_feedback=frozen['after_feedback']['operation'])
    print('Frozen choices',pre['operation'],post['operation'],'training evidence',feedback,flush=True)
    registry=build_calendar_registry(str(OUT/'holdout_fixture.json'))
    results=[]
    for row in banks['holdout']:
        solved=agent.solve(row,registry)
        solved['scope']=in_scope(row['prompt'])
        solved['arms']={name:apply_and_grade(solved,op) for name,op in policies.items()}
        results.append(solved)
        save('holdout_answers.json',results)
    scores={name:{skill:sum(r['arms'][name]['joint'] for r in results if r['skill']==skill)
                  for skill in ('title','location','count')} for name in policies}
    save('summary.json',dict(policies=policies,scores=scores,model_calls=agent.calls,updates=0))
    print(scores,flush=True)


if __name__=='__main__':
    main()
