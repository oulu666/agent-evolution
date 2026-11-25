"""Offline decomposition of autonomous Sokoban traces into planning vs recovery.

For every action, compute the minimum number of pushes still needed to reach the
goal.  An action is optimal when it lowers that number by one, lateral when it
keeps it, and worse when it raises it or makes the board unsolvable.  A trace's
first worsening separates the planning phase (before it) from recovery (after it).

Run from this directory: python diagnose.py
"""
from collections import Counter, deque
import csv
import glob
import json
from pathlib import Path

from push import choices

HERE = Path(__file__).resolve().parent
RUNS = HERE / "astra_qwen_20261106"
OUT = HERE / "diagnose_20261107"
GROUPS = ("student", "self_hint", "guided", "teacher_solo")


def make_distance(floors, goal):
    cache = {}

    def distance(state):
        if state in cache:
            return cache[state]
        queue = deque([(state, 0)])
        seen = {state}
        while queue:
            current, depth = queue.popleft()
            if current[1] == goal:
                cache[state] = depth
                return depth
            for nxt in choices(floors, current).values():
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, depth + 1))
        cache[state] = None
        return None

    return distance


def analyze(case, group, row):
    floors = set(map(tuple, case["floors"]))
    start = (tuple(case["player"]), tuple(case["box"]))
    goal = tuple(case["goal"])
    distance = make_distance(floors, goal)
    state = start
    current = distance(start)
    records = []
    first_worsening = None
    dead = False
    for index, action in enumerate(row["actions"]):
        if action == "RESET":
            records.append(dict(index=index, action=action, kind="reset",
                                before=current, after=current))
            state, current = start, distance(start)
            continue
        if action.startswith("INVALID("):
            records.append(dict(index=index, action=action, kind="invalid",
                                before=current, after=current))
            continue
        options = choices(floors, state)
        if action not in options:
            records.append(dict(index=index, action=action, kind="illegal",
                                before=current, after=current))
            continue
        nxt = options[action]
        after = distance(nxt)
        if current is None:
            kind = "dead"
        elif after is None or after > current:
            kind = "worse"
        elif after == current - 1:
            kind = "optimal"
        else:
            kind = "lateral"
        records.append(dict(index=index, action=action, kind=kind,
                            before=current, after=after))
        if kind in ("worse", "dead") and first_worsening is None:
            first_worsening = index
        dead = dead or after is None
        state, current = nxt, after
    target = records[first_worsening]["before"] if first_worsening is not None else None
    reset_index = next((record["index"] for record in records
                        if first_worsening is not None
                        and record["index"] > first_worsening
                        and record["kind"] == "reset"), None)
    attempt_end = reset_index if reset_index is not None else len(records)
    post = [record for record in records
            if first_worsening is not None
            and first_worsening < record["index"] < attempt_end]
    post_classified = [record for record in post
                       if record["kind"] in ("optimal", "lateral", "worse")]
    pre = [record for record in records
           if (first_worsening is None or record["index"] < first_worsening)
           and record["kind"] in ("optimal", "lateral", "worse")]
    classified = [record for record in records
                  if record["kind"] in ("optimal", "lateral", "worse")]
    recovered = (target is not None and
                 any(record["after"] is not None and record["after"] <= target
                     for record in post))
    return dict(group=group, id=case["id"], solved=row["solved"],
                d0=distance(start), actions=" ".join(row["actions"]),
                first_kind=classified[0]["kind"] if classified else None,
                first_worsening=first_worsening, target=target,
                recovered=recovered if first_worsening is not None else None,
                reset_after=reset_index is not None,
                optimal=sum(record["kind"] == "optimal" for record in classified),
                lateral=sum(record["kind"] == "lateral" for record in classified),
                classified=len(classified),
                pre_optimal=sum(record["kind"] == "optimal" for record in pre),
                pre_classified=len(pre),
                post_optimal=sum(record["kind"] == "optimal" for record in post_classified),
                post_classified=len(post_classified),
                resets=sum(record["kind"] == "reset" for record in records),
                invalids=sum(record["kind"] in ("invalid", "illegal") for record in records),
                dead=dead,
                path=" ".join(f"{record['kind']}:{record['before']}>{record['after']}"
                              for record in records))


def summarize(traces):
    summary = {}
    for group in GROUPS:
        rows = [trace for trace in traces if trace["group"] == group]
        mistakes = [trace for trace in rows if trace["first_worsening"] is not None]
        clean = [trace for trace in rows if trace["first_worsening"] is None]
        classified = sum(trace["classified"] for trace in rows)
        pre = sum(trace["pre_classified"] for trace in rows)
        post = sum(trace["post_classified"] for trace in rows)
        first = [trace for trace in rows if trace["first_kind"]]
        summary[group] = dict(
            n=len(rows), solved=sum(trace["solved"] for trace in rows),
            first_optimal_rate=round(
                sum(trace["first_kind"] == "optimal" for trace in first) / len(first), 3)
            if first else None,
            optimal_rate=round(sum(trace["optimal"] for trace in rows) / classified, 3)
            if classified else None,
            pre_optimal_rate=round(sum(trace["pre_optimal"] for trace in rows) / pre, 3)
            if pre else None,
            post_optimal_rate=round(sum(trace["post_optimal"] for trace in rows) / post, 3)
            if post else None,
            worsening_traces=len(mistakes),
            worsening_rate=round(len(mistakes) / len(rows), 3),
            dead_traces=sum(trace["dead"] for trace in rows),
            reset_traces=sum(trace["resets"] > 0 for trace in rows),
            invalid_actions=sum(trace["invalids"] for trace in rows),
            solved_clean=f"{sum(trace['solved'] for trace in clean)}/{len(clean)}",
            solved_dirty=f"{sum(trace['solved'] for trace in mistakes)}/{len(mistakes)}",
            recovered_by_play=sum(bool(trace["recovered"]) for trace in mistakes),
            reset_after_mistake=sum(trace["reset_after"] for trace in mistakes),
            first_worsening_positions=Counter(
                trace["first_worsening"] for trace in mistakes))
    return summary


def print_table(summary):
    print(f"{'group':<14} {'n':>2} {'win':>4} {'first':>6} {'pre':>6} {'post':>6} "
          f"{'worse':>6} {'dead':>5} {'reset':>6} {'clean':>7} {'dirty':>7}")
    for group in GROUPS:
        item = summary[group]
        first = item["first_optimal_rate"]
        pre = item["pre_optimal_rate"]
        post = item["post_optimal_rate"]
        print(f"{group:<14} {item['n']:>2} {item['solved']:>4} "
              f"{'-' if first is None else f'{first:.2f}':>6} "
              f"{'-' if pre is None else f'{pre:.2f}':>6} "
              f"{'-' if post is None else f'{post:.2f}':>6} "
              f"{item['worsening_traces']:>6} {item['dead_traces']:>5} "
              f"{item['reset_traces']:>6} {item['solved_clean']:>7} {item['solved_dirty']:>7}")


if __name__ == "__main__":
    boards = {case["id"]: case for case in json.loads((RUNS / "boards.json").read_text())}
    traces = []
    for group in GROUPS:
        for path in sorted(RUNS.glob(f"*-{group}.json")):
            row = json.loads(path.read_text())
            traces.append(analyze(boards[row["id"]], group, row))
    OUT.mkdir(exist_ok=True)
    summary = summarize(traces)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    fields = ["group", "id", "solved", "d0", "first_kind", "first_worsening", "target",
              "recovered", "reset_after", "optimal", "lateral", "classified",
              "pre_optimal", "pre_classified", "post_optimal", "post_classified",
              "resets", "invalids", "dead", "actions", "path"]
    with (OUT / "traces.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(traces)
    print_table(summary)
