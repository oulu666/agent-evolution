"""One counterfactual selector call on archived, verified tool observations."""
import json
from run_rsi_operator_memory import ROOT, FrozenAgent, LABELS, apply_and_grade, apply_operation


def main():
    source=ROOT/'runs_rsi_operations_20261122'
    out=ROOT/'runs_rsi_operator_signal_20261123'
    out.mkdir(exist_ok=True)
    result=out/'result.json'
    if result.exists():
        print(result.read_text())
        return
    read=lambda f:json.loads((source/f).read_text())
    train=read('training_answers.json')
    history=read('memory.json')
    evidence=[]
    for label,operation in LABELS.items():
        outcomes=[]
        for r in train:
            assert r['core'] and r['observation']['ok']
            titles=[event['title'] for event in r['observation']['result']]
            outcomes.append(apply_operation(operation,r['prompt'],titles)==r['gold'])
        evidence.append(dict(action=label,correct=sum(outcomes),total=len(train),per_case=outcomes))
    agent=FrozenAgent()
    decision=agent.choose(evidence)
    (out/'frozen.json').write_text(json.dumps(dict(evidence=evidence,decision=decision),indent=2))
    held=read('holdout_answers.json')
    scores={}
    for label,op in [('raw_feedback',history['after_feedback']['operation']),('tool_feedback',decision['operation'])]:
        scores[label]={s:sum(apply_and_grade(r,op)['joint'] for r in held if r['skill']==s) for s in ['title','location','count']}
    result.write_text(json.dumps(dict(decision=decision,evidence=evidence,previous=history['after_feedback'],
        scores_on_original_model_answers=scores,additional_model_calls=agent.calls),indent=2))
    print(result.read_text(),flush=True)


if __name__=='__main__':
    main()
