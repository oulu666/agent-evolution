"""Full teacher planning and per-action feedback on the existing 12 held-out boards."""
from concurrent.futures import ThreadPoolExecutor
import json
import re

import astra_qwen as base
from push import choices
from run import board

OUT = base.HERE / "astra_qwen_full_guidance"


def run(case):
    path = OUT / f"{case['id']:02d}-full_guidance.json"
    row = json.loads(path.read_text()) if path.exists() else dict(
        id=case["id"], group="full_guidance", calls=[], actions=[], done=False)
    if row["done"]:
        return row
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    state = start
    header = (base.RULES + "\nInitial board:\n" + board(floors, start, goal) +
              f"\nInitial history: attempted to walk {case['blocked']} twice, both blocked.")
    for action in row["actions"]:
        state = start if action == "RESET" else choices(floors, state).get(action, state)
    while len(row["actions"]) < 8 and state[1] != goal:
        opts = choices(floors, state)
        observation = ("\nCurrent board:\n" + board(floors, state, goal) +
                       "\nAvailable actions: " + " ".join([*opts, "RESET"]))
        if len(row["calls"]) == 2 * len(row["actions"]):
            previous = ""
            if row["calls"]:
                previous = "\nYour previous instruction:\n" + row["calls"][-2]["output"]
            prompt = (header + "\nStudent actions taken: " + " ".join(row["actions"]) +
                      observation + previous +
                      "\nYou supervise a smaller model that executes one action at a time. "
                      "Solve the whole remaining task and give a complete ordered action plan. "
                      "Explicitly state the ONE action the student must execute now. "
                      "Check whether the previous instruction was followed and correct mistakes. "
                      "Include a brief expected state after the next action. Be concise.")
            advice = base.call(base.TEACHER, prompt)
            advice["kind"] = "full_guidance"
            row["calls"].append(advice)
            base.save(path, row)
        prompt = (header + "\nActions taken: " + " ".join(row["actions"]) + observation +
                  "\nTeacher instructions:\n" + row["calls"][-1]["output"] +
                  "\nExecute the teacher's requested next action. Reply with just one label "
                  "from the available actions.")
        move = base.call(base.STUDENT, prompt)
        match = re.fullmatch(r"(RESET|[UDLR])", move["output"].upper())
        action = match[1] if match else "INVALID"
        if action == "RESET":
            state = start
        elif action in opts:
            state = opts[action]
        else:
            action = "INVALID(" + move["output"] + ")"
        row["calls"].append(move)
        row["actions"].append(action)
        base.save(path, row)
    row.update(done=True, solved=state[1] == goal,
               tokens=sum(c["total_tokens"] for c in row["calls"]))
    base.save(path, row)
    print(row["id"], row["solved"], row["tokens"], " ".join(row["actions"]), flush=True)
    return row


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    cases = base.make_cases(base.SEED)
    base.save(OUT / "boards.json", cases)
    with ThreadPoolExecutor(3) as pool:
        results = list(pool.map(run, cases))
    previous = [json.loads(p.read_text()) for p in base.OUT.glob("[0-9][0-9]-*.json")]
    base.GROUPS = (*base.GROUPS, "full_guidance")
    base.OUT = OUT
    base.summarize(previous + results)
