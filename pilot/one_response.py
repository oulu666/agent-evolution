"""One teacher plan, then one Qwen response containing the complete action sequence."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import random
import re

import astra_qwen as base
from plan_once import OUT as PLANS, coordinates, parse_plan
from push import choices
from run import board

OUT = base.HERE / "astra_qwen_one_response"
GROUPS = ("one_response_alone", "one_response_taught")


def parse_actions(text):
    clean = re.sub(r"^\x60\x60\x60(?:json)?\s*|\s*\x60\x60\x60$", "", text.strip())
    actions = json.loads(clean)
    if not isinstance(actions, list) or not 1 <= len(actions) <= 8:
        raise ValueError("expected an array of 1 to 8 actions")
    if any(a not in ("U", "D", "L", "R", "RESET") for a in actions):
        raise ValueError("invalid action")
    return actions


def run(case, group):
    path = OUT / f"{case['id']:02d}-{group}.json"
    if path.exists():
        row = json.loads(path.read_text())
        if row["done"]:
            return row
    else:
        row = dict(id=case["id"], group=group, calls=[], actions=[], done=False)
        if group == "one_response_taught":
            source = json.loads((PLANS / f"{case['id']:02d}-plan_once.json").read_text())
            teacher = deepcopy(source["calls"][0])
            parse_plan(teacher["output"])
            row["calls"].append(teacher)
            row["reused_teacher_call"] = True
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    state = start
    prompt = (base.RULES + "\nInitial board:\n" + board(floors, start, goal) +
              f"\nInitial history: attempted to walk {case['blocked']} twice, both blocked." +
              "\nCurrent coordinates: " + json.dumps(coordinates(state)) +
              "\nAvailable initial actions: " + " ".join([*choices(floors, state), "RESET"]))
    if group == "one_response_taught":
        prompt += "\nTeacher's complete action plan and expected states:\n" + row["calls"][0]["output"]
    prompt += ('\nProvide the entire action sequence to solve this board in ONE response. '
               'The environment will execute the sequence without further model calls. '
               'Reply only with a JSON array of at most 8 action labels, for example ["R","U"].')
    if not row["calls"] or row["calls"][-1]["model"] != base.STUDENT:
        move = base.call(base.STUDENT, prompt, hint=True)
        move["kind"] = "complete_sequence"
        row["calls"].append(move)
        base.save(path, row)
    try:
        proposed = parse_actions(row["calls"][-1]["output"])
        row["proposed_actions"] = proposed
        row["stop_reason"] = "sequence_exhausted"
    except (ValueError, TypeError):
        proposed = []
        row["stop_reason"] = "invalid_response_format"
    row["actions"] = []
    for action in proposed:
        options = choices(floors, state)
        if action == "RESET":
            state = start
        elif action in options:
            state = options[action]
        else:
            row["actions"].append("INVALID(" + action + ")")
            row["stop_reason"] = "illegal_action"
            break
        row["actions"].append(action)
        if state[1] == goal:
            row["stop_reason"] = "goal"
            break
    row.update(done=True, solved=state[1] == goal,
               tokens=sum(c["total_tokens"] for c in row["calls"]))
    base.save(path, row)
    print(row["id"], group, row["solved"], row["tokens"], row["calls"][-1]["output"], flush=True)
    return row


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    cases = base.make_cases(base.SEED)
    base.save(OUT / "boards.json", cases)
    jobs = [(case, group) for case in cases for group in GROUPS]
    random.Random(42).shuffle(jobs)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda job: run(*job), jobs))
    previous = [json.loads(p.read_text()) for p in base.OUT.glob("[0-9][0-9]-*.json")]
    for folder, group in [
        ("astra_qwen_full_guidance", "full_guidance"),
        ("astra_qwen_plan_once", "plan_once"),
        ("astra_qwen_no_correction", "no_correction"),
    ]:
        previous.extend(json.loads(p.read_text()) for p in
                        (base.HERE / folder).glob(f"[0-9][0-9]-{group}.json"))
    base.GROUPS = (*base.GROUPS, "full_guidance", "plan_once", "no_correction", *GROUPS)
    base.OUT = OUT
    base.summarize(previous + results)
