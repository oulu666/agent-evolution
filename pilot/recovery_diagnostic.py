"""Six paired boards, two models, four conditions. Cases fixed before inference."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import argparse
import csv
import json
import random
import re

import astra_qwen as base
from push import choices
from run import board, make_cases

OUT = base.HERE / "recovery_diagnostic_20261108"
CONDITIONS = ("clean", "recovery", "error_flag", "oracle_plan")
MODELS = {"qwen": base.STUDENT, "astra": base.TEACHER}
MAX_ACTIONS = 6
RULES = ("Push the box B onto G. # wall, . floor, P player, + player on goal. "
         "U/D/L/R specify the direction the BOX moves, not where the player walks. "
         "The environment automatically walks the player behind the box when possible. "
         "Each action pushes once. No pulling or reset. Only listed actions are legal.")


def shortest(floors, state, goal):
    queue = deque([(state, [])])
    seen = {state}
    while queue:
        current, path = queue.popleft()
        if current[1] == goal:
            return path
        for action, nxt in choices(floors, current).items():
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, path+[action]))
    return None


def prepare():
    path = OUT / "cases.json"
    if path.exists():
        return json.loads(path.read_text())
    # Deterministic eligibility, no selection based on either model's outputs.
    cases = []
    for seed in range(20261120, 20261220):
        for candidate in make_cases(seed):
            floors = set(map(tuple, candidate["floors"]))
            state = tuple(candidate["player"]), tuple(candidate["box"])
            goal = tuple(candidate["goal"])
            plan = shortest(floors, state, goal)
            if plan is None or not 2 <= len(plan) <= 3:
                continue
            for action, nxt in choices(floors, state).items():
                repair = shortest(floors, nxt, goal)
                if repair is not None and len(plan) < len(repair) <= 4:
                    cases.append({**candidate, "id": len(cases)+1, "seed": seed,
                                  "injected_action": action, "error_state": nxt,
                                  "clean_plan": plan, "repair_plan": repair})
                    break
            if len(cases) == 6:
                base.save(path, cases)
                return cases
    raise RuntimeError("Not enough eligible cases")


def run(case, actor, condition):
    path = OUT / f"{case['id']:02d}-{actor}-{condition}.json"
    row = json.loads(path.read_text()) if path.exists() else dict(
        id=case["id"], actor=actor, condition=condition, calls=[], actions=[], done=False)
    if row["done"]:
        return row
    floors = set(map(tuple, case["floors"]))
    initial = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    state = initial if condition == "clean" else tuple(map(tuple, case["error_state"]))
    prefix = RULES
    if condition != "clean":
        prefix += ("\nBoard before the preceding action:\n"+board(floors,initial,goal)+
                   "\nPreceding action: "+case["injected_action"]+".")
    if condition in ("error_flag", "oracle_plan"):
        prefix += ("\nVerified feedback: the preceding action was a mistake. "
                   "It increased the number of pushes still required. The current state "
                   "remains solvable without a reset.")
    if condition == "oracle_plan":
        prefix += "\nVerified complete repair plan from this starting state: "+" ".join(case["repair_plan"])+"."
    for action in row["actions"]:
        state = choices(floors,state).get(action,state)
    while len(row["actions"]) < MAX_ACTIONS and state[1] != goal:
        opts = choices(floors,state)
        if not opts:
            break
        prompt = (prefix+"\nCurrent board:\n"+board(floors,state,goal)+
                  "\nActions since this trial started: "+" ".join(row["actions"])+
                  "\nAvailable actions: "+" ".join(opts)+
                  "\nChoose the next box push to reach G. Reply with exactly one action label.")
        move = base.call(MODELS[actor],prompt)
        match = re.fullmatch(r"[UDLR]",move["output"].upper())
        action = match[0] if match else "INVALID"
        if action in opts:
            state=opts[action]
        else:
            action="INVALID("+move["output"]+")"
        row["calls"].append(move)
        row["actions"].append(action)
        base.save(path,row)
    row.update(done=True,solved=state[1]==goal,
               tokens=sum(c["total_tokens"] for c in row["calls"]))
    base.save(path,row)
    print(case["id"],actor,condition,row["solved"],row["tokens"]," ".join(row["actions"]),flush=True)
    return row


def summarize(cases):
    rows=[json.loads(p.read_text()) for p in OUT.glob("[0-9][0-9]-*.json")]
    expected={(c["id"],a,g) for c in cases for a in MODELS for g in CONDITIONS}
    assert len(rows)==len(expected)==48
    assert {(r["id"],r["actor"],r["condition"]) for r in rows}==expected
    lookup={c["id"]:c for c in cases}
    for row in rows:
        c=lookup[row["id"]]
        floors=set(map(tuple,c["floors"]));goal=tuple(c["goal"])
        start=(tuple(c["player"]),tuple(c["box"])) if row["condition"]=="clean" else tuple(map(tuple,c["error_state"]))
        state=start
        original_plan=shortest(floors,state,goal)
        first_optimal=False
        for i,action in enumerate(row["actions"]):
            if action.startswith("INVALID("):
                continue
            state=choices(floors,state)[action]
            if i==0:
                remaining=shortest(floors,state,goal)
                first_optimal=remaining is not None and len(remaining)==len(original_plan)-1
        assert row["done"] and row["solved"]==(state[1]==goal)
        assert row["tokens"]==sum(c["input_tokens"]+c["output_tokens"] for c in row["calls"])
        row["first_optimal"]=first_optimal
    summary={}
    for actor in MODELS:
        summary[actor]={}
        for condition in CONDITIONS:
            selected=[r for r in rows if r["actor"]==actor and r["condition"]==condition]
            summary[actor][condition]=dict(
                wins=sorted(r["id"] for r in selected if r["solved"]),
                first_optimal=sum(r["first_optimal"] for r in selected),
                calls=sum(len(r["calls"]) for r in selected),
                tokens=sum(r["tokens"] for r in selected))
    base.save(OUT/"summary.json",summary)
    with (OUT/"results.csv").open("w",newline="") as f:
        writer=csv.writer(f)
        writer.writerow(["case","actor","condition","solved","first_optimal","tokens","actions"])
        for r in sorted(rows,key=lambda r:(r["id"],r["actor"],r["condition"])):
            writer.writerow([r["id"],r["actor"],r["condition"],r["solved"],r["first_optimal"],r["tokens"]," ".join(r["actions"])])
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--actor",choices=MODELS)
    parser.add_argument("--prepare",action="store_true")
    args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    cases=prepare()
    print("Selected clean/recovery lengths",[(len(c["clean_plan"]),len(c["repair_plan"])) for c in cases],flush=True)
    if not args.prepare:
        actors=[args.actor] if args.actor else MODELS
        jobs=[(c,a,g) for c in cases for a in actors for g in CONDITIONS]
        random.Random(42).shuffle(jobs)
        with ThreadPoolExecutor(3 if args.actor=="astra" else 2) as pool:
            list(pool.map(lambda job:run(*job),jobs))
        if not args.actor:
            summarize(cases)
