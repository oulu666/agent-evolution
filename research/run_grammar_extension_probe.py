"""Constrain only the candidate output grammar; never give the model candidate outcome scores."""
import argparse
import json
import subprocess
import time

import torch
from run_semantic_extensions import assess, prompt, ranked
from semantic_extension_bank import language,tasks
from semantic_repair_run import Inference,conversation_text,save


@torch.inference_mode()
def main(size):
    agent=Inference(size)
    ts=list(tasks())
    rows=[]
    for off in range(0,len(ts),4):
        while b'r5apex' in subprocess.check_output(['tasklist.exe','/FO','CSV','/NH']).lower():
            time.sleep(15)
        batch=ts[off:off+4]
        messages=[conversation_text(agent.tok,[dict(role='user',content=prompt(t,'local'))],True) for t in batch]
        enc=agent.tok(messages,padding=True,add_special_tokens=False,return_tensors='pt').to('cuda')
        prefix=enc.input_ids.shape[1]
        tries=[]
        for t in batch:
            trie={}
            for h in language(t['alias']):
                ids=agent.tok.encode(json.dumps(h,separators=(',',':')),add_special_tokens=False)
                path=[]
                for token in [*ids,agent.tok.eos_token_id]:
                    trie.setdefault(tuple(path),set()).add(token)
                    path.append(token)
            tries.append(trie)
        def allowed(batch_id,current):
            path=tuple(current[prefix:].tolist())
            return sorted(tries[batch_id].get(path,{agent.tok.eos_token_id}))
        decoded=agent.model.generate(**enc,do_sample=False,max_new_tokens=96,num_beams=2,
            num_return_sequences=2,renormalize_logits=True,length_penalty=0.0,
            prefix_allowed_tokens_fn=allowed,pad_token_id=agent.tok.eos_token_id)
        for i,t in enumerate(batch):
            outputs=decoded[i*2:i*2+2,prefix:]
            hs=[tuple(json.loads(agent.tok.decode(out,skip_special_tokens=True))) for out in outputs]
            assert len(set(hs))==2 and all(h in language(t['alias']) for h in hs)
            best=ranked(t)[0]
            for arm,proposals in [('grammar2',hs),('hybrid',[best,next(h for h in hs if h!=best)])]:
                rows.append(dict(id=t['id'],truth=t['truth'],split=t['split'],arm=arm,
                    tokens=sum(sum(k!=agent.tok.eos_token_id for k in out.tolist()) for out in outputs),
                    **assess(t,proposals)))
        save(f'grammar_{size}.json',rows)
    print(size,{arm:sum(r['exact'] for r in rows if r['split']=='final' and r['arm']==arm)
                for arm in ('grammar2','hybrid')},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('size',choices=['06','17'])
    main(p.parse_args().size)
