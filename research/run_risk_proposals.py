"""Frozen P11 proposals, measured tokens and wall time, plus a matched decoding-bias audit."""
import json
import subprocess
import time
import torch
from risk_worlds import OUT,endpoint,layouts,pool,prompt,save,parse
from semantic_repair_run import Inference,conversation_text
from semantic_extension_bank import language
from run_semantic_extensions import prompt as old_prompt


def trie(agent, strings):
    tree={}
    for text in strings:
        path=()
        for tok in agent.tok.encode(text,add_special_tokens=False)+[agent.tok.eos_token_id]:
            tree.setdefault(path,set()).add(tok)
            path=(*path,tok)
    return tree


@torch.inference_mode()
def infer(agent,texts,trees,mode):
    formatted=[conversation_text(agent.tok,[dict(role='user',content=s)],True) for s in texts]
    enc=agent.tok(formatted,padding=True,add_special_tokens=False,return_tensors='pt').to('cuda')
    prefix=enc.input_ids.shape[1]
    def allowed(i,tokens):
        tree=trees[i//2 if mode=='sample' else i]
        return sorted(tree.get(tuple(tokens[prefix:].tolist()),{agent.tok.eos_token_id}))
    options=dict(max_new_tokens=40,pad_token_id=agent.tok.eos_token_id)
    if mode!='free':
        options.update(prefix_allowed_tokens_fn=allowed,renormalize_logits=True,num_return_sequences=2)
    if mode=='beam':
        options.update(num_beams=2,length_penalty=0.0)
    if mode=='sample':
        options.update(temperature=1.0,top_p=1.0,top_k=0)
    while b'r5apex' in subprocess.check_output(['tasklist.exe','/FO','CSV','/NH']).lower():
        time.sleep(15)
    torch.cuda.synchronize()
    start=time.perf_counter()
    result=agent.model.generate(**enc,do_sample=mode=='sample',**options)
    torch.cuda.synchronize()
    elapsed=time.perf_counter()-start
    output=[]
    width=1 if mode=='free' else 2
    for i in range(len(texts)):
        seq=result[i*width:(i+1)*width,prefix:]
        output.append(dict(raw=[agent.tok.decode(v,skip_special_tokens=True).strip() for v in seq],
            input_tokens=int(enc.attention_mask[i].sum()),output_tokens=sum(int((v!=agent.tok.eos_token_id).sum()) for v in seq),
            seconds=elapsed/len(texts)))
    return output


def main():
    agent=Inference('06')
    _,large,slices=pool()
    grammar=trie(agent,[' '.join(h) for h in large+slices])
    jobs=[]
    for idx,alias,raw,rows,bank,held in layouts():
        for kind in ['simple','compound','outside']:
            for i in range(3):
                answer=endpoint(rows,kind,i)
                jobs.append((f'{idx}-{kind}-{i}',prompt(rows,answer)))
    # Identical public histories receive identical proposals; no hidden case identifier enters the prompt.
    texts=list(dict.fromkeys(s for _,s in jobs))
    log=OUT/'proposals.jsonl'
    cache={}
    if log.exists():
        for line in log.read_text().splitlines():
            item=json.loads(line)
            cache[item['text']]=item
    missing=[s for s in texts if s not in cache]
    for off in range(0,len(missing),6):
        part=missing[off:off+6]
        beams=infer(agent,part,[grammar]*len(part),'beam')
        frees=infer(agent,part,None,'free')
        with log.open('a') as f:
            for s,b,g in zip(part,beams,frees):
                item=dict(text=s,beam=b,free=g)
                cache[s]=item
                f.write(json.dumps(item)+'\n')
    save('case_proposals.json',{key:{k:v for k,v in cache[s].items() if k!='text'} for key,s in jobs})
    old=OUT.parent/'runs_semantic_repair_20261123'
    cases=[t for t in json.loads((old/'B_fixtures.json').read_text()) if t['split']=='final']
    audit=[]
    torch.manual_seed(112326)
    for off in range(0,len(cases),4):
        part=cases[off:off+4]
        prompts=[old_prompt(t,'local') for t in part]
        trees=[trie(agent,[json.dumps(h,separators=(',',':')) for h in language(t['alias'])]) for t in part]
        reversed_prompts=[]
        for s in prompts:
            start=s.index('Extension syntax: ')+len('Extension syntax: ')
            end=s.index(' Position is',start)
            options=s[start:end].rstrip('.').split('; ')
            assert len(options)==3
            reversed_prompts.append(s[:start]+'; '.join(reversed(options))+'.'+s[end:])
        rev=infer(agent,reversed_prompts,trees,'beam')
        sample=infer(agent,prompts,trees,'sample')
        audit.extend(dict(id=t['id'],reversed_order=r,sampling=v) for t,r,v in zip(part,rev,sample))
    save('bias.json',audit)
    print('Finished',len(jobs),'cases,',len(texts),'unique public histories.',flush=True)


if __name__=='__main__':
    main()
