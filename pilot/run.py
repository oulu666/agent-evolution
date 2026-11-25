"""Paired, deterministic Sokoban pilot. Run with Python 3.11 or newer."""
import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import random
import re
import time
import urllib.error
import urllib.request


HERE = Path(__file__).resolve().parent
STUDENT = "doubao-seed-2-0-mini-260428"
TEACHER = "doubao-seed-2-0-pro-260215"
DIR = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
GROUPS = ("continue", "self", "teacher")
ROUNDS = 4
BUDGETS = (800, 1500, 2200)
RULES = (
    "Solve a single-crate Sokoban board. # wall, . floor, P player, B crate, G goal. "
    "U/D/L/R move one square. Walking into the crate pushes it if the next square "
    "is free. You cannot pull. The crate must land on G. Rows are shown top to bottom."
)


def step(floors, state, direction):
    (x, y), box = state
    dx, dy = DIR[direction]
    dest = x + dx, y + dy
    if dest not in floors:
        return None
    if dest != box:
        return dest, box
    pushed = dest[0] + dx, dest[1] + dy
    return (dest, pushed) if pushed in floors else None


def distance(floors, start, goal):
    queue = deque([(start, 0)])
    seen = {start}
    while queue:
        state, n = queue.popleft()
        if state[1] == goal:
            return n
        for direction in DIR:
            nxt = step(floors, state, direction)
            if nxt and nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, n + 1))


def board(floors, state, goal):
    # The player may stand on the goal; preserve both facts in that case.
    player, box = state
    tiles = {goal: "G", box: "B", player: "+" if player == goal else "P"}
    return "\n".join("".join(tiles.get((x, y), "." if (x, y) in floors else "#")
                             for x in range(7)) for y in range(7))


def make_cases(seed=20261105):
    rng = random.Random(seed)
    cases = []
    while len(cases) < 12:
        floors = [(x, y) for x in range(1, 6) for y in range(1, 6) if rng.random() > 0.18]
        if len(floors) < 3:
            continue
        player, box, goal = rng.sample(floors, 3)
        floor_set = set(floors)
        invalid = [d for d in DIR if step(floor_set, (player, box), d) is None]
        if not invalid:
            continue
        shortest = distance(floor_set, (player, box), goal)
        low, high = (4, 7) if len(cases) < 6 else (8, 12)
        if shortest is not None and low <= shortest <= high:
            cases.append(dict(id=len(cases)+1, floors=floors, player=player, box=box,
                              goal=goal, blocked=invalid[0], optimal_steps=shortest))
    return cases


def call(model, prompt, max_tokens):
    payload = dict(model=model, messages=[dict(role="user", content=prompt)],
                   temperature=0, max_tokens=max_tokens, thinking=dict(type="disabled"))
    req = urllib.request.Request(os.environ["OPENAI_BASE_URL"].rstrip("/")+"/chat/completions",
                                 data=json.dumps(payload).encode(), headers={
                                     "Content-Type": "application/json",
                                     "Authorization": "Bearer "+os.environ["OPENAI_API_KEY"]})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=75) as res:
                data = json.load(res)
            break
        except urllib.error.HTTPError as err:
            if attempt == 2 or err.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(2**attempt)
    choice = data["choices"][0]
    return dict(model=model, prompt=prompt, output=choice["message"]["content"].strip(),
                usage=data["usage"], finish_reason=choice["finish_reason"])


def run_branch(case, group):
    path = HERE/"runs"/f"{case['id']:02d}-{group}.json"
    if path.exists():
        return json.loads(path.read_text())
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    state = start
    history = [f"Initial attempts: {case['blocked']} was blocked twice. Board unchanged."]
    header = RULES+" + means player on goal.\nInitial board:\n"+board(floors, start, goal)
    calls = []
    hint = ""
    if group != "continue":
        model = STUDENT if group == "self" else TEACHER
        prompt = header+"\n"+history[0]+"\nGive one short strategic hint for this board. " \
                 "Point out a specific intermediate position or push direction. Do not give a full move sequence."
        advice = call(model, prompt, 64)
        calls.append(advice)
        hint = "\nOne-time advice: "+advice["output"]
    for _ in range(ROUNDS):
        prompt = (header+hint+"\nHistory:\n"+"\n".join(history)+"\nCurrent board:\n"+
                  board(floors, state, goal)+"\nReturn only a sequence of UDLR moves (max 24), "
                  "optionally prefixed by RESET to restart from the initial board. "
                  "Try to solve the entire board. Execution stops on the first illegal move.")
        action = call(STUDENT, prompt, 64)
        calls.append(action)
        match = re.fullmatch(r"(RESET\s*)?([UDLR]{1,24})", action["output"].upper().strip())
        if not match:
            history.append("Invalid move syntax: "+action["output"])
            continue
        if match[1]:
            state = start
        outcome = "all executed"
        for index, direction in enumerate(match[2], 1):
            nxt = step(floors, state, direction)
            if nxt is None:
                outcome = f"blocked at move {index}"
                break
            state = nxt
            if state[1] == goal:
                break
        history.append(action["output"]+" -> "+outcome)
        if state[1] == goal:
            break
    result = dict(id=case["id"], group=group, solved=state[1] == goal, history=history,
                  tokens=sum(c["usage"]["total_tokens"] for c in calls), calls=calls)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(result, indent=2))
    temp.replace(path)
    return result


def report(rows):
    for group in GROUPS:
        selected = sorted((r for r in rows if r["group"] == group), key=lambda r:r["id"])
        tokens = sum(r["tokens"] for r in selected)
        wins = [r["id"] for r in selected if r["solved"]]
        capped = {b: sum(r["solved"] and r["tokens"] <= b for r in selected) for b in BUDGETS}
        print(group, "wins:", wins, "token sum:", tokens, "budget wins:", capped)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    cases = make_cases()
    (HERE/"runs").mkdir(exist_ok=True)
    (HERE/"cases.json").write_text(json.dumps(cases, indent=2))
    jobs = [(c, g) for c in cases for g in GROUPS]
    random.Random(42).shuffle(jobs)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(lambda job: run_branch(*job), jobs))
    report(rows)
