"""Frozen 0.6B two-stage memory pilot. Run from the project WSL environment."""
import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from p15_stageaware_20261119.core import BoundCalendar, DATA
from fac_tinyagent.metrics import answers_equal, observations_equal
from fac_tinyagent.sft.dataset import conversation_text
from fac_tinyagent.sft.evaluate import parse_tool_call, parse_final_answer
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

ROUTED = '--routed' in sys.argv
CALIBRATED = '--calibrated' in sys.argv or ROUTED
ORIGINAL = ROOT / 'runs_rsi_pilot_20261122'
OUT = ROOT / 'runs_rsi_calibrated_20261122' if CALIBRATED else ORIGINAL
PRIOR = ROOT / 'runs_rsi_calibrated_20261122'
if ROUTED:
    OUT = ROOT / 'runs_rsi_routed_20261122'
if CALIBRATED:
    diagnosis = json.loads((ORIGINAL/'training_protocol_check.json').read_text())
    aligned = [r['p11_instructions'] for r in diagnosis]
    assert sum(r['core'] for r in aligned)>=6 and any(r['joint'] and r['skill']=='cal.count_date' for r in aligned), 'insufficient working baseline'
OUT.mkdir(exist_ok=True)
BASE = '/home/egret/models/Qwen3-0.6B'
ADAPTER = ROOT / 'runs_ext_p11_eaar_v1/branches/A_seed20261108_eaar_v1/checkpoint'
LOC, TITLE, COUNT = 'cal.list_locations', 'cal.extract_title_sorted', 'cal.count_date'
SKILLS = [LOC, TITLE, COUNT]
def dump(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2))

def select():
    groups = {'train': {}, 'gate': {}, 'blind': {}}
    for split in ('train', 'dev'):
        rows = [json.loads(s) for s in (DATA/split/'rows.jsonl').read_text().splitlines()]
        for skill in SKILLS:
            pool = [r for r in rows if r['skill'] == skill]
            random.Random('20261122/'+split+'/'+skill).shuffle(pool)
            if split == 'train':
                groups['train'][skill] = pool[:6]
            else:
                assert len(pool) >= 12
                groups['gate'][skill], groups['blind'][skill] = pool[:4], pool[4:12]
    return groups

rows = select()
if CALIBRATED:
    # Compare the same optimizer on a shared, checkpoint-compatible interface.
    # P14 training-bank rows here were never used to train the P11 checkpoint.
    reserved_dates = {r['target_date'] for rr in rows['train'].values() for r in rr}
    pool = [json.loads(s) for s in (DATA/'train/rows.jsonl').read_text().splitlines()]
    if ROUTED:
        previous = json.loads((PRIOR/'design.json').read_text())
        used = {episode for group in previous['ids'].values() for rr in group.values() for episode in rr}
        reserved_dates.update(r['target_date'] for r in pool if r['episode_id'] in used)
    for skill in SKILLS:
        available = [r for r in pool if r['skill']==skill and r['target_date'] not in reserved_dates]
        blind_seed = 'stage-routing-20261122/' if ROUTED else 'protocol-transfer-20261122/'
        random.Random(blind_seed+skill).shuffle(available)
        assert len(available)>=8
        rows['blind'][skill] = available[:8]
        reserved_dates.update(r['target_date'] for r in available[:8])
    system_prompt = json.loads((ROOT/'data_ext_p11_eaar_v1/train/rows.jsonl').read_text().splitlines()[0])['system']
    for group in rows.values():
        for rr in group.values():
            for row in rr:
                row['messages'][0]['content'] = system_prompt
save('design.json', {'checkpoint': str(ADAPTER.relative_to(ROOT)), 'precision':'fp16 merged adapter',
     'first':LOC,'transfer':TITLE,'old':COUNT,'proposals_per_round':2,'proposal_token_cap':96,
     'call_cap':96,'answer_cap':128,'proposal_context_cap':2048,'accept':'target net gains > 0, zero old Joint losses',
     'ids':{k:{s:[r['episode_id'] for r in rr] for s,rr in v.items()} for k,v in rows.items()}})
last_check = 0
def game_guard():
    global last_check
    if time.monotonic()-last_check < 12:
        return
    processes = subprocess.check_output(['tasklist.exe','/FO','CSV','/NH'])
    if b'r5apex' in processes.lower():
        raise SystemExit(75)
    last_check = time.monotonic()

game_guard()
tok = AutoTokenizer.from_pretrained(BASE, local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.float16, device_map={'':'cuda:0'},local_files_only=True)
model = PeftModel.from_pretrained(model, str(ADAPTER)).merge_and_unload().eval()
bounds = {s:BoundCalendar(s) for s in ('train','dev')}
cachefile = OUT/'generations.jsonl'
cache = {v['key']:v for v in map(json.loads,cachefile.read_text().splitlines())} if cachefile.exists() else {}
if CALIBRATED:
    borrowed = {v['key']:v for v in map(json.loads,(ORIGINAL/'generations.jsonl').read_text().splitlines())}
    cache.update(borrowed)
if ROUTED:
    cache.update({v['key']:v for v in map(json.loads,(PRIOR/'generations.jsonl').read_text().splitlines())})
def gen(msgs, cap):
    game_guard()
    prompt = conversation_text(tok,msgs,True)
    key = hashlib.sha256((str(cap)+prompt).encode()).hexdigest()
    if key not in cache:
        enc = tok(prompt,return_tensors='pt',add_special_tokens=False).to('cuda')
        assert enc.input_ids.shape[1] < (2048 if cap==96 and msgs[0]['content'].startswith('You improve') else 4096)
        with torch.inference_mode():
            ids = model.generate(**enc,max_new_tokens=cap,do_sample=False,pad_token_id=tok.eos_token_id)
        new = ids[0,enc.input_ids.shape[1]:]
        rec = dict(key=key, text=tok.decode(new,skip_special_tokens=True).strip(),input_tokens=enc.input_ids.shape[1],output_tokens=len(new))
        with cachefile.open('a') as f:
            f.write(dump(rec)+'\n')
        cache[key]=rec
    return cache[key]['text']

def run(r, rules):
    msgs = [dict(m) for m in r['messages'][:2]]
    def apply(stage):
        ms = [dict(m) for m in msgs]
        additions = [rule for turn,rule in rules if turn==stage]
        if additions:
            ms[0]['content'] += '\n'+'\n'.join(additions)
        return ms
    raw = gen(apply('CALL'),96)
    call = parse_tool_call(raw)
    obs = bounds[r['split']].execute(r,call['tool'],call['arguments']) if call and call['tool'] else {'ok':False,'error':'invalid tool call'}
    msgs.extend([{'role':'assistant','content':raw},{'role':'user','content':'TOOL RESULT:\n'+dump(obs)}])
    out = gen(apply('FINAL'),128)
    valid, answer = parse_final_answer(out)
    core = bool(call and call['tool']==r['expected_tool'] and answers_equal(call['arguments'],r['expected_arguments']) and observations_equal(obs,r['expected_observation']))
    final = valid and answers_equal(answer,r['expected_final_answer'])
    return dict(id=r['episode_id'],skill=r['skill'],joint=bool(core and final),core=core,
                prompt=r['prompt'],expected=r['expected_final_answer'],answer=out,call=raw)

def evaluate(split, skills, rules):
    return [run(r,rules) for s in skills for r in rows[split][s]]

def propose(skill, failures, inherited, history, index, final_only=False):
    examples = [{k:r[k] for k in ('prompt','expected','call','answer','core')} for r in failures[:2]]
    focus = ['Identify the earliest wrong step.','Consider a narrow instruction that preserves other tasks.'][index]
    msg = f"""Improve a calendar assistant for {skill}. {focus}
Inherited instructions: {dump(inherited)}
Past edit history: {dump(history)}
Failed training examples: {dump(examples)}
Write ONE reusable conditional instruction. Start with CALL| for choosing a tool or FINAL| for answering after a tool result. No example values, explanations, or JSON. If no change is warranted write SKIP."""
    if final_only:
        msg=msg.replace('Start with CALL| for choosing a tool or FINAL| for answering after a tool result.',
                        'The tool, arguments and execution are already correct in these failures. The edit will apply only when writing the final answer from the tool result. Start with FINAL|.')
    raw=gen([{'role':'system','content':'You improve instructions from verified examples. Follow the requested output format.'},{'role':'user','content':msg}],96)
    turn,sep,rule=raw.partition('|')
    valid=bool(sep and turn.strip() in ('CALL','FINAL') and rule.strip() and len(rule.strip())<=400)
    return raw, ('FINAL' if final_only else turn.strip(),rule.strip()) if valid else None

def evolve(name, skill, old, inherited, history, final_only=False):
    train=evaluate('train',[skill],inherited)
    errors=[r for r in train if not r['joint']]
    if final_only:
        assert errors and all(r['core'] for r in errors)
    before=evaluate('gate',[skill]+old,inherited)
    log=[]; best=list(inherited); best_gain=0
    for i in range(2):
        raw,rule=propose(skill,errors,inherited,history,i,final_only)
        after=evaluate('gate',[skill]+old,inherited+[rule]) if rule else before
        gains=sum(a['joint']-b['joint'] for a,b in zip(after,before) if a['skill']==skill)
        losses=sum(b['joint'] and not a['joint'] for a,b in zip(after,before) if a['skill'] in old)
        log.append(dict(proposal=raw,valid=bool(rule),target_net=gains,old_lost=losses,after=after))
        if rule and gains>best_gain and losses==0:
            best_gain=gains;best=inherited+[rule]
    save(name+'.json',dict(train=train,before=before,candidates=log,selected=best))
    print(name,'gain',best_gain,'selected',best,flush=True)
    memory=[dict(task=skill,edit=r['proposal'][:300],target_net=r['target_net'],old_lost=r['old_lost'],valid=r['valid']) for r in log]
    return best,memory

if '--protocol-check' in sys.argv:
    reference = json.loads((ROOT/'data_ext_p11_eaar_v1/train/rows.jsonl').read_text().splitlines()[0])['system']
    comparison = []
    for skill in SKILLS:
        for row in rows['train'][skill][:4]:
            alternate = dict(row, messages=[dict(m) for m in row['messages']])
            alternate['messages'][0]['content'] = reference
            comparison.append({'original':run(row,[]),'p11_instructions':run(alternate,[])})
    save('training_protocol_check.json',comparison)
    print('Training-only instruction comparison', [(key,sum(r[key]['core'] for r in comparison),sum(r[key]['joint'] for r in comparison)) for key in comparison[0]],flush=True)
    sys.exit()

if ROUTED:
    save('protocol.json', dict(target=TITLE, comparator='optimizer chooses turn', treatment='verified core correct: final-turn-only repair',
         memory='empty both arms', proposals=2, proposer_cap=96, accept='target net gain > 0 on 4, no old case lost on 8; first passing max gain',
         extra_readout='first free-stage proposal verbatim on fresh title items both at its chosen turn and at FINAL regardless of gate, diagnostic only'))
    a,_=evolve('free',TITLE,[COUNT,LOC],[],[])
    b,_=evolve('routed',TITLE,[COUNT,LOC],[],[],final_only=True)
    raw=json.loads((OUT/'free.json').read_text())['candidates'][0]['proposal']
    turn,body=raw.split('|',1)
    assert turn in ('CALL','FINAL') and body.strip()
    states={'baseline':[],'free':a,'routed':b}
    save('locked_states.json',dict(states=states,fixed_text_readout=[turn,body.strip()]))
    blind={k:evaluate('blind',SKILLS,v) for k,v in states.items()}
    save('blind.json',blind)
    placement={k:evaluate('blind',[TITLE],[(stage,body.strip())]) for k,stage in [('chosen',turn),('final','FINAL')]}
    save('placement.json',placement)
    physical=[json.loads(line) for line in cachefile.read_text().splitlines()]
    scores={k:{s:sum(r['joint'] for r in rr if r['skill']==s) for s in SKILLS} for k,rr in blind.items()}
    save('summary.json',dict(scores=scores,placement={k:sum(r['joint'] for r in rr) for k,rr in placement.items()},
         physical_generations=len(physical),input_tokens=sum(r['input_tokens'] for r in physical),output_tokens=sum(r['output_tokens'] for r in physical)))
    print(scores,flush=True)
    sys.exit()

first,memory=evolve('round1',LOC,[COUNT],[],[])
a,_=evolve('round2_A',TITLE,[COUNT,LOC],first,[])
b,_=evolve('round2_B',TITLE,[COUNT,LOC],first,memory)
states={'baseline':[],'round1':first,'A':a,'B':b}
save('locked_states.json',states)
blind={k:evaluate('blind',SKILLS,v) for k,v in states.items()}
save('blind.json',blind)
scores={k:{s:sum(x['joint'] for x in rr if x['skill']==s) for s in SKILLS} for k,rr in blind.items()}
physical = [json.loads(line) for line in cachefile.read_text().splitlines()]
save('summary.json',dict(scores=scores,physical_generations=len(physical),input_tokens=sum(q['input_tokens'] for q in physical),output_tokens=sum(q['output_tokens'] for q in physical)))
print(scores,flush=True)
