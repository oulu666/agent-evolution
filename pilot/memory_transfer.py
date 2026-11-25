"""Frozen Qwen memory distilled from GPT-6 demonstrations, evaluated on new tasks."""
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import random
import re

import astra_qwen as base
from plan_once import coordinates, parse_plan
from push import choices
from run import board

OUT = base.HERE / "astra_qwen_memory_transfer"
GROUPS = ("no_memory", "short_memory")
TEST_SEEDS = (20261107, 20261108)


def render(case):
    return board(set(map(tuple, case["floors"])),
                 (tuple(case["player"]), tuple(case["box"])), tuple(case["goal"]))


def prepare():
    training = base.make_cases(base.SEED)
    tests = []
    seen = {render(c) for c in training}
    for seed in TEST_SEEDS:
        for case in base.make_cases(seed):
            signature = render(case)
            assert signature not in seen, "train/test overlap or duplicate test"
            seen.add(signature)
            tests.append({**case, "id": len(tests)+1, "generation_seed": seed})
    demonstrations = []
    teacher_tokens = 0
    for case in training:
        source = base.HERE / "astra_qwen_plan_once" / f"{case['id']:02d}-plan_once.json"
        teacher = json.loads(source.read_text())["calls"][0]
        floors = set(map(tuple, case["floors"]))
        start = tuple(case["player"]), tuple(case["box"])
        state = start
        plan = parse_plan(teacher["output"])
        trace = []
        for entry in plan:
            action = entry["action"]
            state = start if action == "RESET" else choices(floors, state)[action]
            actual = coordinates(state)
            assert actual == {k: entry[k] for k in ("player", "box")}
            trace.append({"action": action, **actual})
        assert state[1] == tuple(case["goal"])
        demonstrations.append({"id": case["id"], "initial_board": render(case),
                               "successful_steps": trace})
        teacher_tokens += teacher["total_tokens"]
    base.save(OUT / "demonstrations.json", demonstrations)
    base.save(OUT / "test_boards.json", tests)
    return tests, demonstrations, teacher_tokens


def distill(demonstrations):
    path = OUT / "memory_generation.json"
    if path.exists():
        return json.loads(path.read_text())
    prompt = (base.RULES + "\nBelow are 12 successful teacher demonstrations. Each includes "
              "the initial board and the verified positions after each push, in 1-based "
              "[row,column] coordinates including walls.\n" +
              json.dumps(demonstrations) +
              "\nLearn from these demonstrations. Write 3 to 5 short general rules to help "
              "yourself solve NEW boards. Use at most 120 English words total. "
              "Describe reusable decision procedures or common traps, without referring to "
              "example numbers, fixed coordinates, or memorized action sequences. "
              "Output only the rules.")
    data = base.post("http://127.0.0.1:18946/v1/chat/completions", dict(
        model=base.STUDENT, messages=[{"role": "user", "content": prompt}],
        temperature=0, seed=base.SEED, max_tokens=256))
    choice = data["choices"][0]
    assert choice["finish_reason"] == "stop"
    memory = choice["message"]["content"].strip()
    assert memory and len(memory.split()) <= 120
    assert data["model"] == base.STUDENT
    record = dict(model=data["model"], prompt=prompt, output=memory, usage=data["usage"],
                  word_count=len(memory.split()),
                  sha256=hashlib.sha256(memory.encode()).hexdigest())
    base.save(path, record)
    (OUT / "memory.txt").write_text(memory+"\n", encoding="utf-8")
    return record


def run(case, group, memory):
    path = OUT / f"{case['id']:02d}-{group}.json"
    row = json.loads(path.read_text()) if path.exists() else dict(
        id=case["id"], group=group, calls=[], actions=[], done=False,
        memory_sha256=hashlib.sha256(memory.encode()).hexdigest() if group=="short_memory" else None)
    if row["done"]:
        return row
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    state = start
    for action in row["actions"]:
        state = start if action=="RESET" else choices(floors,state).get(action,state)
    header = (base.RULES + "\nInitial board:\n" + render(case) +
              f"\nInitial history: attempted to walk {case['blocked']} twice, both blocked.")
    note = "\nYour reusable rules from earlier training tasks:\n"+memory if group=="short_memory" else ""
    while len(row["actions"]) < 8 and state[1] != goal:
        options = choices(floors,state)
        prompt = (header+note+"\nActions taken: "+" ".join(row["actions"]) +
                  "\nCurrent board:\n"+board(floors,state,goal)+"\nAvailable actions: "+
                  " ".join([*options,"RESET"])+"\nChoose one available action. Reply with just its label.")
        move = base.call(base.STUDENT,prompt)
        match = re.fullmatch(r"(RESET|[UDLR])",move["output"].upper())
        action = match[1] if match else "INVALID"
        if action=="RESET":
            state=start
        elif action in options:
            state=options[action]
        else:
            action="INVALID("+move["output"]+")"
        row["actions"].append(action)
        row["calls"].append(move)
        base.save(path,row)
    row.update(done=True,solved=state[1]==goal,tokens=sum(c["total_tokens"] for c in row["calls"]))
    base.save(path,row)
    print(case["id"],group,row["solved"],row["tokens"],flush=True)
    return row


def summarize(rows, memory, teacher_tokens):
    assert len(rows)==48
    summary={"teacher_demonstration_tokens":teacher_tokens,
             "memory_generation_tokens":memory["usage"]["total_tokens"],
             "memory_word_count":memory["word_count"]}
    preparation=teacher_tokens+memory["usage"]["total_tokens"]
    for group in GROUPS:
        selected=[r for r in rows if r["group"]==group]
        total=sum(r["tokens"] for r in selected)
        summary[group]=dict(wins=sorted(r["id"] for r in selected if r["solved"]),
            evaluation_tokens=total,total_tokens_with_preparation=total+(preparation if group=="short_memory" else 0),
            action_calls=sum(len(r["actions"]) for r in selected))
    a=set(summary["no_memory"]["wins"]);b=set(summary["short_memory"]["wins"])
    summary["rescued"]=sorted(b-a)
    summary["lost"]=sorted(a-b)
    rng=random.Random(17)
    orders=[rng.sample(range(1,25),24) for _ in range(1000)]
    for group in GROUPS:
        lookup={r["id"]:r for r in rows if r["group"]==group}
        for charge in (False,True):
            successes=0
            for order in orders:
                left=20000-(preparation if charge and group=="short_memory" else 0)
                for i in order:
                    left-=lookup[i]["tokens"]
                    if left<0:break
                    successes+=int(lookup[i]["solved"])
            key="replay_successes_20000_with_preparation" if charge else "replay_successes_20000_online_only"
            summary[group][key]=successes/len(orders)
    base.save(OUT/"summary.json",summary)
    with (OUT/"cases.csv").open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["id","group","success","tokens","actions"])
        for r in sorted(rows,key=lambda r:(r["id"],r["group"])):
            w.writerow([r["id"],r["group"],r["solved"],r["tokens"]," ".join(r["actions"])])
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    OUT.mkdir(exist_ok=True)
    cases,demos,teacher_tokens=prepare()
    memory=distill(demos)
    print("FROZEN MEMORY",memory["output"],flush=True)
    jobs=[(c,g) for c in cases for g in GROUPS]
    random.Random(42).shuffle(jobs)
    with ThreadPoolExecutor(2) as pool:
        rows=list(pool.map(lambda job:run(*job,memory["output"]),jobs))
    summarize(rows,memory,teacher_tokens)
