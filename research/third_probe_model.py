"""One frozen-model third-test proposal per visible history and permission."""
import json
import time
from third_probe_inputs import OUT,save,model_prompt
from semantic_repair_run import Inference


def main():
    agent=Inference('06')
    agent.file=OUT/'generations.jsonl'
    agent.cache={}
    if agent.file.exists():
        for line in agent.file.read_text().splitlines():
            item=json.loads(line)
            agent.cache[item['hash']]=item
    jobs=[(i,p,model_prompt(i,p)) for i in range(24) for p in ('read','build')]
    results=[]
    start=time.perf_counter()
    for off in range(0,len(jobs),2):
        batch=jobs[off:off+2]
        before=time.perf_counter()
        generated=agent.run([s for _,_,s in batch],96)
        elapsed=time.perf_counter()-before
        for (i,p,s),r in zip(batch,generated):
            results.append(dict(layout=i,permission=p,raw=r['raw'],output_tokens=r['tokens'],
                                input_tokens=len(agent.tok.encode(s)),batch_share_seconds=elapsed/len(batch)))
        save('model.json',results)
    print(len(results),'proposals;',time.perf_counter()-start,'seconds',flush=True)


if __name__=='__main__':
    main()
