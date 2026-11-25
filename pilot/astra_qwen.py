"""GPT-6 Astra / Qwen paired pilot. Standard library, Python 3.11.

Serve the verified Qwen3-4B-Instruct-2507 Q4_K_M weights on localhost:18946
with llama-server --alias qwen3-4b-instruct-2507-q4_k_m --ctx-size 4096.
Set ASTRA_API_KEY for this process. The teacher always calls api.openai.com.
"""
from concurrent.futures import ThreadPoolExecutor
import csv
import json
import os
import random
import re
import time
import urllib.error
import urllib.request

from push import choices
from run import HERE, board, make_cases

TEACHER = "gpt-6-astra"
STUDENT = "qwen3-4b-instruct-2507-q4_k_m"
OUT = HERE / "astra_qwen_20261106"
GROUPS = ("student", "self_hint", "teacher_solo", "guided")
SEED = 20261106
RULES = ("Push B onto G. # wall, . floor, P player, + player on goal. U/D/L/R push the box "
         "one square up/down/left/right; the player walks behind it automatically if reachable. "
         "You cannot pull. RESET restores the initial board. Rows run top to bottom.")


def post(url, payload, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=150) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if attempt == 2 or exc.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(2**attempt)


def call(model, prompt, hint=False):
    if model == TEACHER:
        data = post("https://api.openai.com/v1/responses", dict(
            model=model, reasoning={"effort": "medium"}, input=prompt, store=False,
            max_output_tokens=2048), os.environ["ASTRA_API_KEY"])
        if data["status"] != "completed":
            raise RuntimeError(f"Teacher response incomplete: {data.get('incomplete_details')}")
        answer = "".join(c["text"] for item in data["output"] if item["type"] == "message"
                         for c in item["content"] if c["type"] == "output_text").strip()
        u = data["usage"]
        counts = [u["input_tokens"], u["output_tokens"],
                  u["output_tokens_details"]["reasoning_tokens"]]
    else:
        data = post("http://127.0.0.1:18946/v1/chat/completions", dict(
            model=model, messages=[{"role": "user", "content": prompt}],
            temperature=0, seed=SEED, max_tokens=64 if hint else 16))
        answer = data["choices"][0]["message"]["content"].strip()
        u = data["usage"]
        counts = [u["prompt_tokens"], u["completion_tokens"], 0]
    if data["model"] != model or sum(counts[:2]) != u["total_tokens"] or not answer:
        raise ValueError(f"Inconsistent model, usage or empty output from {model}")
    return dict(model=model, kind="hint" if hint else "action", prompt=prompt, output=answer,
                input_tokens=counts[0], output_tokens=counts[1], reasoning_tokens=counts[2],
                total_tokens=u["total_tokens"])


def save(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    for attempt in range(6):
        try:
            tmp.replace(path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.2*(attempt+1))


def run(case, group):
    path = OUT / f"{case['id']:02d}-{group}.json"
    row = json.loads(path.read_text()) if path.exists() else dict(
        id=case["id"], group=group, calls=[], actions=[], done=False)
    if row["done"]:
        return row
    floors = set(map(tuple, case["floors"]))
    start = tuple(case["player"]), tuple(case["box"])
    goal = tuple(case["goal"])
    state = start
    header = (RULES+"\nInitial board:\n"+board(floors, start, goal)+
              f"\nInitial history: attempted to walk {case['blocked']} twice, both blocked.")
    for label in row["actions"]:
        state = start if label == "RESET" else choices(floors, state).get(label, state)
    with_hint = group in ("self_hint", "guided")
    if with_hint and not row["calls"]:
        prompt = (header+"\nAvailable pushes: "+" ".join(choices(floors, start))+
                  "\nGive the student one short hint (at most 24 words) about a useful "
                  "intermediate target or trap. Do not provide the full solution.")
        advisor = TEACHER if group == "guided" else STUDENT
        row["calls"].append(call(advisor, prompt, hint=True))
        save(path, row)
    hint = "\nHint: "+row["calls"][0]["output"] if with_hint else ""
    actor = TEACHER if group == "teacher_solo" else STUDENT
    while len(row["actions"]) < 8 and state[1] != goal:
        opts = choices(floors, state)
        prompt = (header+hint+"\nActions taken: "+" ".join(row["actions"])+
                  "\nCurrent board:\n"+board(floors, state, goal)+"\nAvailable actions: "+
                  " ".join([*opts, "RESET"])+"\nChoose one available action. Reply with just its label.")
        move = call(actor, prompt)
        match = re.fullmatch(r"(RESET|[UDLR])", move["output"].upper())
        label = match[1] if match else "INVALID"
        if label == "RESET":
            state = start
        elif label in opts:
            state = opts[label]
        else:
            label = "INVALID("+move["output"]+")"
        row["actions"].append(label)
        row["calls"].append(move)
        save(path, row)
    row.update(done=True, solved=state[1] == goal, tokens=sum(c["total_tokens"] for c in row["calls"]))
    save(path, row)
    print(case["id"], group, row["solved"], row["tokens"], flush=True)
    return row


def summarize(rows):
    cases = {c["id"]: c for c in make_cases(SEED)}
    assert {(r["id"], r["group"]) for r in rows} == {
        (i, group) for i in cases for group in GROUPS}
    assert len(rows) == len(cases)*len(GROUPS)
    for row in rows:
        c = cases[row["id"]]
        floors = set(map(tuple, c["floors"]))
        start = tuple(c["player"]), tuple(c["box"])
        state = start
        for action in row["actions"]:
            if action == "RESET":
                state = start
            elif not action.startswith("INVALID("):
                state = choices(floors, state)[action]
        assert row["done"] and row["solved"] == (state[1] == tuple(c["goal"]))
        assert row["tokens"] == sum(call["total_tokens"] for call in row["calls"])
    summary = {}
    orders = []
    rng = random.Random(17)
    for _ in range(1000):
        orders.append(rng.sample(range(1, 13), 12))
    for group in GROUPS:
        items = {r["id"]: r for r in rows if r["group"] == group}
        wins = sorted(i for i,r in items.items() if r["solved"])
        calls = [c for r in items.values() for c in r["calls"]]
        completions = 0
        for order in orders:
            budget = 8000
            for i in order:
                budget -= items[i]["tokens"]
                if budget < 0:
                    break
                completions += int(items[i]["solved"])
        summary[group] = dict(wins=wins, total=sum(c["total_tokens"] for c in calls),
            student_tokens=sum(c["total_tokens"] for c in calls if c["model"] == STUDENT),
            teacher_tokens=sum(c["total_tokens"] for c in calls if c["model"] == TEACHER),
            reasoning_tokens=sum(c["reasoning_tokens"] for c in calls),
            wins_under_1500=sum(r["solved"] and r["tokens"] <= 1500 for r in items.values()),
            replay_wins_per_8000=completions/len(orders))
    save(OUT/"summary.json", summary)
    with (OUT/"cases.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["case","group","success","tokens","actions"])
        for r in sorted(rows, key=lambda x:(x["id"], x["group"])):
            writer.writerow([r["id"],r["group"],r["solved"],r["tokens"]," ".join(r["actions"])])
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    cases = make_cases(SEED)
    save(OUT/"boards.json", cases)
    jobs = [(c,g) for c in cases for g in GROUPS]
    random.Random(42).shuffle(jobs)
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda job: run(*job), jobs))
    summarize(results)
