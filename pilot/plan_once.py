"""Teacher plans once. Deterministic state checks trigger subsequent replanning."""
from concurrent.futures import ThreadPoolExecutor
import json
import re

import astra_qwen as base
from push import choices
from run import board

OUT = base.HERE / "astra_qwen_plan_once"
MAX_ACTIONS = 8
MAX_PLANS = 8


def parse_plan(text):
    clean = re.sub(r"^\x60\x60\x60(?:json)?\s*|\s*\x60\x60\x60$", "", text.strip())
    plan = json.loads(clean)["steps"]
    if not isinstance(plan, list) or not 1 <= len(plan) <= MAX_ACTIONS:
        raise ValueError("steps must contain 1 to 8 actions")
    for step in plan:
        if step["action"] not in ("U", "D", "L", "R", "RESET"):
            raise ValueError("unknown action")
        for name in ("box", "player"):
            coords = step[name]
            if (not isinstance(coords, list) or len(coords) != 2 or
                    any(type(n) is not int or not 1 <= n <= 7 for n in coords)):
                raise ValueError("coordinates must be [row, column], each 1 to 7")
    return plan


def coordinates(state):
    player, box = state
    return {"player": [player[1]+1, player[0]+1], "box": [box[1]+1, box[0]+1]}


def run(case):
    path = OUT / f"{case['id']:02d}-plan_once.json"
    row = json.loads(path.read_text()) if path.exists() else dict(
        id=case["id"], group="plan_once", calls=[], actions=[], checks=[],
        plan=[], cursor=0, plans=0, trigger="Initial planning.", done=False)
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
    while len(row["actions"]) < MAX_ACTIONS and state[1] != goal:
        opts = choices(floors, state)
        observation = ("\nCurrent board:\n" + board(floors, state, goal) +
                       "\nCurrent coordinates: " + json.dumps(coordinates(state)) +
                       "\nAvailable actions: " + " ".join([*opts, "RESET"]))
        if row["cursor"] >= len(row["plan"]):
            if row["plans"] >= MAX_PLANS:
                break
            prompt = (header + observation +
                      "\nActions taken: " + " ".join(row["actions"]) +
                      "\nReason for request: " + row["trigger"] +
                      "\nGive a complete plan from the CURRENT state to the goal. "
                      "Return JSON only, with steps containing action, box, and player. "
                      "box and player are EXPECTED positions AFTER that action, each [row,column], "
                      "1-based including the outer walls. After a push the player occupies "
                      "the box's previous square. Example schema: "
                      '{"steps":[{"action":"R","box":[2,4],"player":[2,3]}]}. '
                      "Use at most " + str(MAX_ACTIONS-len(row["actions"])) +
                      " actions. The student will execute without further supervision unless "
                      "the observed state diverges. Include RESET if recovery requires it.")
            advice = base.call(base.TEACHER, prompt)
            advice["kind"] = "plan"
            row["calls"].append(advice)
            row["plans"] += 1
            try:
                row["plan"] = parse_plan(advice["output"])
                row["cursor"] = 0
                row["trigger"] = ""
            except (ValueError, TypeError, KeyError) as exc:
                row["plan"] = []
                row["cursor"] = 0
                row["trigger"] = "Previous plan could not be parsed: " + str(exc)
            base.save(path, row)
            if not row["plan"]:
                continue
        expected = row["plan"][row["cursor"]]
        prompt = (header + observation + "\nActions taken: " + " ".join(row["actions"]) +
                  "\nRemaining teacher plan:\n" + json.dumps(row["plan"][row["cursor"]:]) +
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
        matched = all(actual[name] == expected[name] for name in ("player", "box"))
        row["calls"].append(move)
        row["actions"].append(action)
        row["checks"].append(dict(expected=expected, actual=actual, matched=matched))
        row["cursor"] += 1
        if not matched:
            row["trigger"] = ("State diverged after student action " + action +
                              ". Expected " + json.dumps(expected) +
                              "; observed " + json.dumps(actual))
            row["plan"] = []
            row["cursor"] = 0
        elif row["cursor"] == len(row["plan"]) and state[1] != goal:
            row["trigger"] = "Plan exhausted but the box has not reached the goal."
        base.save(path, row)
    row.update(done=True, solved=state[1] == goal,
               tokens=sum(c["total_tokens"] for c in row["calls"]))
    base.save(path, row)
    print(row["id"], row["solved"], row["tokens"], "plans", row["plans"],
          "actions", " ".join(row["actions"]), flush=True)
    return row


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    cases = base.make_cases(base.SEED)
    base.save(OUT / "boards.json", cases)
    with ThreadPoolExecutor(3) as pool:
        results = list(pool.map(run, cases))
    previous = [json.loads(p.read_text()) for p in base.OUT.glob("[0-9][0-9]-*.json")]
    full = [json.loads(p.read_text()) for p in
            (base.HERE / "astra_qwen_full_guidance").glob("[0-9][0-9]-full_guidance.json")]
    base.GROUPS = (*base.GROUPS, "full_guidance", "plan_once")
    base.OUT = OUT
    base.summarize(previous + full + results)
