"""Post-hoc menu-position audit on a predetermined stride of layouts; no retuning."""
import json
import random
from third_probe_inputs import OUT,model_prompt,public,parse_request,save
from semantic_repair_run import Inference


def main():
    agent=Inference('06')
    agent.file=OUT/'position_generations.jsonl'
    agent.cache={}
    if agent.file.exists():
        for line in agent.file.read_text().splitlines():
            entry=json.loads(line)
            agent.cache[entry['hash']]=entry
    results=[]
    for i in range(0,24,3):
        for perm in ['read','build']:
            bank=public(i)[2]
            bank=bank[:12] if perm=='read' else bank
            order=list(range(len(bank)))
            random.Random(f'position/{i}/{perm}').shuffle(order)
            raw=agent.run([model_prompt(i,perm,order)],96)[0]['raw']
            q,obj=parse_request(raw,i,perm,[bank[k] for k in order])
            results.append(dict(layout=i,permission=perm,order=order,raw=raw,parsed=obj,
                                physical=q['name'] if q else None))
            save('position_audit.json',results)


if __name__=='__main__':
    main()
