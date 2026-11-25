"""Paired ablation: share initial plan and rollout through the first divergence."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import re

import astra_qwen as base
from plan_once import OUT as SOURCE, coordinates, parse_plan
from push import choices
from run import board

OUT = base.HERE / "astra_qwen_no_correction"


def run(case):
    path = OUT / f"{case['id']:02d}-no_correction.json"
    original = json.loads((SOURCE / f"{case['id']:02d}-plan_once.json").read_text())
    plan = parse_plan(original["calls"][0]["output"])
    if path.exists():
        row = json.loads(path.read_text())
    else:
        shared_actions = next((i+1 for i,c in enumerate(original["checks"]) if not c["matched"]),
                              len(original["actions"]))
        shared_calls = deepcopy(original["calls"][:shared_actions+1])
        assert shared_calls[0]["model"] == base.TEACHER
        assert all(c["model"] == base.STUDENT for c in shared_calls[1:])
        row = dict(id=case["id"], group="no_correction", calls=shared_calls,
                   actions=deepcopy(original["actions"][:shared_actions]),
                   checks=deepcopy(original["checks"][:shared_actions]),
                   shared_prefix_actions=shared_actions, reused_calls=len(shared_calls),
                   plan=plan, done=False)
        base.save(path, row)
    if row["done"]:
        return row
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    state = start
    for action in row["actions"]:
        state = start if action == "RESET" else choices(floors, state).get(action, state)
    header = (base.RULES + "\nInitial board:\n" + board(floors, start, goal) +
              f"\nInitial history: attempted to walk {case['blocked']} twice, both blocked.")
    while len(row["actions"]) < len(plan) and state[1] != goal:
        opts = choices(floors, state)
        cursor = len(row["actions"])
        expected = plan[cursor]
        observation = ("\nCurrent board:\n" + board(floors, state, goal) +
                       "\nCurrent coordinates: " + json.dumps(coordinates(state)) +
                       "\nAvailable actions: " + " ".join([*opts, "RESET"]))
        prompt = (header + observation + "\nActions taken: " + " ".join(row["actions"]) +
                  "\nRemaining teacher plan:\n" + json.dumps(plan[cursor:]) +
                  "\nExecute the FIRST action of this remaining plan. Reply with exactly "
                  "one action label from the available actions.")
        move = base.call(base.STUDENT, prompt)
        match = re.fullmatch(r"(RESET|[UDLR])", move["output"].upper())
        action = match[1] if match else "INVALID"
        if action == "RESET":
            state = start
        elif action in opts:
            state = opts[action]
        else:
            action = "INVALID(" + move["output"] + ")"
        actual = coordinates(state)
        row["calls"].append(move)
        row["actions"].append(action)
        row["checks"].append(dict(expected=expected, actual=actual,
                                 matched=all(actual[k] == expected[k] for k in actual)))
        base.save(path, row)
    row.update(done=True, solved=state[1] == goal,
               stop_reason="goal" if state[1] == goal else "original_plan_exhausted",
               tokens=sum(c["total_tokens"] for c in row["calls"]))
    base.save(path, row)
    print(row["id"], row["solved"], row["tokens"], " ".join(row["actions"]), flush=True)
    return row


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    cases = base.make_cases(base.SEED)
    base.save(OUT / "boards.json", cases)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(run, cases))
    previous = [json.loads(p.read_text()) for p in base.OUT.glob("[0-9][0-9]-*.json")]
    for folder, pattern in [
        (base.HERE / "astra_qwen_full_guidance", "[0-9][0-9]-full_guidance.json"),
        (SOURCE, "[0-9][0-9]-plan_once.json"),
    ]:
        previous.extend(json.loads(p.read_text()) for p in folder.glob(pattern))
    base.GROUPS = (*base.GROUPS, "full_guidance", "plan_once", "no_correction")
    base.OUT = OUT
    base.summarize(previous + results)
