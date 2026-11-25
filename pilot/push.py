"""Second pilot interface. Environment walks to the push position automatically."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import json
import random
import re

from run import DIR, GROUPS, HERE, STUDENT, TEACHER, board, call, make_cases, report, step


def choices(floors, state):
    player, box = state
    reachable = {player}
    queue = deque([player])
    while queue:
        position = queue.popleft()
        for d in DIR:
            nxt = step(floors, (position, box), d)
            if nxt and nxt[1] == box and nxt[0] not in reachable:
                reachable.add(nxt[0])
                queue.append(nxt[0])
    options = {}
    for d, (dx, dy) in DIR.items():
        behind = box[0]-dx, box[1]-dy
        ahead = box[0]+dx, box[1]+dy
        if behind in reachable and ahead in floors:
            options[d] = (box, ahead)
    return options


def run_branch(case, group):
    path = HERE/"push_runs"/f"{case['id']:02d}-{group}.json"
    if path.exists():
        return json.loads(path.read_text())
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    state = start
    goal = tuple(case["goal"])
    header = ("Push the crate B onto G. # wall, . floor, P player, + player on goal. "
              "U/D/L/R push the crate one square up/down/left/right. The player automatically "
              "walks behind it when reachable. No pulling. Avoid stranding the crate. "
              "RESET restores the initial board. Initial board:\n"+board(floors, start, goal)+
              f"\nBefore this snapshot, walking {case['blocked']} hit a wall or blocked crate twice.")
    calls = []
    history = []
    advice = ""
    if group != "continue":
        prompt = (header+"\nAvailable initial pushes: "+" ".join(choices(floors, start))+
                  "\nGive one short strategic hint for this board, e.g. an intermediate square "
                  "or push direction. Do not give a full move sequence.")
        hint = call(STUDENT if group == "self" else TEACHER, prompt, 64)
        calls.append(hint)
        advice = "\nAdvice: "+hint["output"]
    for _ in range(8):
        options = choices(floors, state)
        prompt = (header+advice+"\nActions taken: "+" ".join(history)+"\nCurrent board:\n"+
                  board(floors, state, goal)+"\nAvailable actions: "+" ".join([*options, "RESET"])+
                  "\nChoose one available action. Reply with just its label.")
        move = call(STUDENT, prompt, 16)
        calls.append(move)
        label = re.match(r"^(RESET|[UDLR])\b", move["output"].upper())
        action = label[1] if label else ""
        if action == "RESET":
            state = start
        elif action in options:
            state = options[action]
        else:
            action = "INVALID("+move["output"]+")"
        history.append(action)
        if state[1] == goal:
            break
    result = dict(id=case["id"], group=group, solved=state[1] == goal, history=history,
                  tokens=sum(c["usage"]["total_tokens"] for c in calls), calls=calls)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, indent=2))
    tmp.replace(path)
    return result


if __name__ == "__main__":
    (HERE/"push_runs").mkdir(exist_ok=True)
    jobs = [(case, group) for case in make_cases() for group in GROUPS]
    random.Random(42).shuffle(jobs)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda job: run_branch(*job), jobs))
    report(results)
