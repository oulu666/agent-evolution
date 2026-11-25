"""Probe three retained derivations on alternate real paths of a public state machine."""
from datetime import datetime, timezone
from functools import partial
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from issre_order_frame import git,digest,read,write
from issre_order_run import contents
from issre_order_fixtures import GOLD

OUT=HERE.parent/"runs_path_intervention_20261124"
PRIOR=HERE.parent/"runs_order_contract_20261124"/"presentation_audit.json"
TAGS=("0.9.0","0.9.2")
HANDLER="machine.on_exception"
FINAL="machine.finalize_event"
# (condition, callback that raises, expected final state). Each uses one public event.
DESIGN={"success":(True,None,"b"),"guard_declines":(False,None,"a"),
        "early_raise":(True,"transition.before","a"),
        "transition_after_raise":(True,"transition.after","b"),
        "machine_after_raise":(True,"machine.after_state_change","b")}


def chains():
    audit=read(PRIOR)["transitions"]
    doc=audit["normalized_records"]["README.md"]
    edges={(d["scope"],tuple(d["lines"])):(d["left"],d["right"]) for d in doc["direct"]}
    selected={tuple(p) for p in audit["normalized"]["unsupported_agreements"]}
    result=[]
    for proof in doc["derived"]:
        if (proof["left"],proof["right"]) not in selected:
            continue
        steps=[edges[proof["scope"],tuple(s)] for s in proof["spans"]]
        assert all(a[1]==b[0] for a,b in zip(steps,steps[1:]))
        result.append({"nodes":[steps[0][0]]+[s[1] for s in steps],"source_lines":proof["spans"]})
    assert len(result)==3
    return result


def run_path(name):
    from transitions import Machine
    guard,raises,expected_state=DESIGN[name]
    class CallbackError(Exception):
        pass
    sentinel=CallbackError("fixture callback")
    events=[]
    def callback(label,event):
        events.append({"event":label,"phase":"entry","state":event.model.state})
        if label==raises:
            events.append({"event":label,"phase":"raise","state":event.model.state})
            raise sentinel
        if label==HANDLER and event.error is not sentinel:
            raise RuntimeError("handler received unexpected exception")
        answer=guard if label=="transition.conditions" else (False if label=="transition.unless" else None)
        events.append({"event":label,"phase":"return","state":event.model.state})
        return answer
    hooks={k:partial(callback,k) for k in [*GOLD["transitions"],HANDLER]}
    m=Machine(states=[dict(name="a",on_exit=hooks["state.on_exit"]),dict(name="b",on_enter=hooks["state.on_enter"])],
              initial="a",auto_transitions=False,send_event=True,prepare_event=hooks["machine.prepare_event"],
              before_state_change=hooks["machine.before_state_change"],after_state_change=hooks["machine.after_state_change"],
              on_exception=hooks[HANDLER],finalize_event=hooks[FINAL])
    m.add_transition("advance","a","b",prepare=hooks["transition.prepare"],conditions=hooks["transition.conditions"],
                     unless=hooks["transition.unless"],before=hooks["transition.before"],after=hooks["transition.after"])
    events.clear()
    result=m.advance()
    entered=[e["event"] for e in events if e["phase"]=="entry"]
    checks={"expected_state":m.state==expected_state,"handler_count":entered.count(HANDLER)==int(raises is not None),
            "finalization":entered.count(FINAL)==1 and entered[-1]==FINAL,
            "intended_raise":[e["event"] for e in events if e["phase"]=="raise"]==([raises] if raises else [])}
    return dict(path=name,trigger_result=result,end=m.state,events=events,setup_checks=checks)


def score(run,proof):
    nodes=proof["nodes"]
    entries=[e["event"] for e in run["events"] if e["phase"]=="entry"]
    assert len(entries)==len(set(entries))
    endpoints=all(k in entries for k in [nodes[0],nodes[-1]])
    if not endpoints:
        outcome="outside_endpoint_scope"
    elif entries.index(nodes[0])>=entries.index(nodes[-1]):
        outcome="endpoint_contradiction"
    elif all(k in entries for k in nodes) and sorted(nodes,key=entries.index)==nodes:
        outcome="ordered_chain_observed"
    else:
        outcome="agreement_without_chain"
    return dict(source=nodes[0],target=nodes[-1],outcome=outcome,handler_observed=HANDLER in entries,
                absent_nodes=[k for k in nodes if k not in entries])


def freeze():
    OUT.mkdir(exist_ok=True)
    assert not (OUT/"lock.json").exists()
    write(OUT/"lock.json",{"time":datetime.now(timezone.utc).isoformat(),"runner":digest(Path(__file__)),
            "audit":digest(PRIOR),"fixtures":digest(HERE/"issre_order_fixtures.py"),"design":DESIGN,
            "revisions":{tag:git("transitions","rev-parse",tag+"^{commit}").decode().strip() for tag in TAGS},
            "chains":chains()})
    print("protocol",digest(OUT/"lock.json"))


def run():
    lock=read(OUT/"lock.json")
    assert lock["runner"]==digest(Path(__file__)) and lock["audit"]==digest(PRIOR)
    assert lock["fixtures"]==digest(HERE/"issre_order_fixtures.py") and chains()==lock["chains"]
    output={}
    for tag,rev in lock["revisions"].items():
        assert git("transitions","rev-parse",tag+"^{commit}").decode().strip()==rev
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for n,blob in contents("transitions",tag):
                path=root/n
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(blob)
            proc=subprocess.run([sys.executable,"-I",__file__,"worker",tmp],capture_output=True,text=True,check=True,timeout=60)
            output[tag]=json.loads(proc.stdout)
        for row in output[tag]:
            row["proofs"]=[score(row,proof) for proof in lock["chains"]]
    write(OUT/"observations.json",output)
    for tag,rows in output.items():
        print(tag,[(r["path"],[p["outcome"] for p in r["proofs"]],all(r["setup_checks"].values())) for r in rows])


if __name__=="__main__":
    if sys.argv[1]=="freeze": freeze()
    elif sys.argv[1]=="run": run()
    else:
        root=Path(sys.argv[2])
        sys.path[:0]=[str(root/"src"),str(root)]
        import transitions
        assert Path(transitions.__file__).resolve().is_relative_to(root)
        print(json.dumps([run_path(name) for name in DESIGN]))

