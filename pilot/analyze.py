"""Verify saved trajectory costs and independently replay the scored push actions."""
import json
import random

from push import choices
from run import BUDGETS, GROUPS, HERE, make_cases


def load_runs(directory):
    rows = [json.loads(p.read_text()) for p in sorted((HERE/directory).glob("*.json"))]
    assert len(rows) == len({(r["id"], r["group"]) for r in rows}) == 36
    for r in rows:
        usages = [c["usage"] for c in r["calls"]]
        assert r["tokens"] == sum(u["total_tokens"] for u in usages)
        assert all(u["total_tokens"] == u["prompt_tokens"] + u["completion_tokens"] for u in usages)
    return rows


def verify_push(rows):
    cases = make_cases()
    for r in rows:
        case = cases[r["id"]-1]
        start = tuple(case["player"]), tuple(case["box"])
        floors = set(map(tuple, case["floors"]))
        state = start
        for a in r["history"]:
            if a == "RESET":
                state = start
            elif not a.startswith("INVALID("):
                state = choices(floors, state)[a]
        assert r["solved"] == (state[1] == tuple(case["goal"]))


def summarize(rows):
    rng = random.Random(17)
    orders = [rng.sample(range(1, 13), 12) for _ in range(1000)]
    summary = {}
    for group in GROUPS:
        group_rows = {r["id"]: r for r in rows if r["group"] == group}
        assert set(group_rows) == set(range(1, 13))
        total = sum(r["tokens"] for r in group_rows.values())
        wins = sorted(r["id"] for r in group_rows.values() if r["solved"])
        completions = 0
        for order in orders:
            remaining = 8000
            for case_id in order:
                r = group_rows[case_id]
                remaining -= r["tokens"]
                if remaining < 0:
                    break
                completions += r["solved"]
        summary[group] = dict(wins=wins, total=total, mean=total/12,
                              budget_wins={b:sum(r["tokens"] <= b and r["solved"]
                                                   for r in group_rows.values()) for b in BUDGETS},
                              mean_wins_per_8000=completions/len(orders))
    return summary


if __name__ == "__main__":
    raw = load_runs("runs")
    push = load_runs("push_runs")
    verify_push(push)
    out = dict(raw=summarize(raw), push=summarize(push))
    (HERE/"summary.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
