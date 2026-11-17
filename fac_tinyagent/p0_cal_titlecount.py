"""[ext 2026-11-12] Calendar title-count fix exam (v3fix).

Not a replacement for frozen Calendar v3, and not the multi-instance v4.
Version: calendar_title_count_v3fix

Diagnosis of v3 search_count (all E3 arms ~0.389): after Calendar training,
almost every arm gets the exact same items right. Joint success is ~1 for
gold in {1,2}, mixed for {4,5}, and 0 for gold in {6,8,10} even when
calendar_search is called correctly — the model systematically undercounts
long tool results (8–10 full event objects, 1.3–1.8k chars). Ambiguous
prompts ("how many 'Sales' sessions") also divert the tool call. The 0.389
is a seed-level plateau (0.433 / 0.300 / 0.433), not an intervention effect.

This exam keeps the frozen v3 fixture (read-only) and builds NEW items.
Almost every 1–5-hit global title fragment is already used by v3
search_count (only 'Budget Review' remains), so a global calendar_search
band cannot be filled. The exam is therefore 30 day_count items:

  day_count  calendar_list on one day -> count titles containing a
             fragment. Observation is short (3–6 events). Gold is in 1–3
             and is not the day's total event count (at least one
             non-match), so 'just count all meetings that day' fails.

calendar_list+date calls that already appear in v3 (locations / last_end)
are allowed: same short observation, new title-count projection. Calls
used in training / other exams stay forbidden.

Writes data_ext_p0_cal_titlecount/ only; refuses to overwrite a freeze.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from .research_data import call_signature, task_signature
from .round2_data import _messages, _system
from .tools import build_calendar_registry
from .utils import canonical_json, read_json, read_jsonl, sha256_file, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_ext_p0_cal_titlecount"
V3_ROOT = ROOT / "data_ext_cal_v3"
FIXTURE = V3_ROOT / "fixtures" / "calendar_v3.json"
VERSION = "calendar_title_count_v3fix"
TASK_SEED = 20261142
N_ITEMS = 30

GLOBAL_PROMPTS = [
    "How many events on my calendar have a title containing '{f}'? Answer with a single number.",
    "Use title search to count every event whose title contains '{f}'. Reply with just the count.",
    "Across the whole calendar, how many entries mention '{f}' in the title? Give a number.",
    "Count the events whose names contain the text '{f}'. Answer as a number.",
]
DAY_PROMPTS = [
    "On {d}, how many events have a title containing '{f}'? Answer with a single number.",
    "Look at the meetings on {d} and count those whose title contains '{f}'. Reply with just the count.",
    "For the date {d} only, how many calendar entries mention '{f}' in the title? Give a number.",
    "Of the events scheduled on {d}, how many have '{f}' in the title? Answer as a number.",
]


def _existing_jsonl() -> List[Path]:
    out = []
    for d in sorted(ROOT.glob("data*")):
        if d.is_dir() and d.name != OUT.name:
            out += sorted(d.rglob("*.jsonl"))
    return out


def _forbidden() -> Tuple[Set[str], Set[str], Set[Any], Set[str]]:
    prompts, sigs, calls, titles = set(), set(), set(), set()
    for path in _existing_jsonl():
        for row in read_jsonl(path):
            if "prompt" in row and "expected_tool" in row:
                prompts.add(row["prompt"])
                sigs.add(task_signature(row))
                calls.add(call_signature(row))
                args = row.get("expected_arguments") or {}
                if row.get("expected_tool") == "calendar_search" and isinstance(args, dict):
                    if "title" in args:
                        titles.add(str(args["title"]))
    return prompts, sigs, calls, titles


def _global_candidates(events: List[Dict[str, Any]], forbidden_titles: Set[str]) -> List[Dict[str, Any]]:
    titles = sorted({e["title"] for e in events})
    frags = sorted(set(titles) | {w for t in titles for w in t.split() if len(w) >= 3}
                   | {t.split()[0] for t in titles} | {t.split()[-1] for t in titles})
    out = []
    for frag in frags:
        if frag in forbidden_titles:
            continue
        count = sum(frag.casefold() in e["title"].casefold() for e in events)
        if 1 <= count <= 5:
            out.append({"title": frag, "gold": count})
    return out


def _day_candidates(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dates = sorted({e["date"] for e in events})
    titles = sorted({e["title"] for e in events})
    frags = sorted(set(titles) | {w for t in titles for w in t.split() if len(w) >= 3})
    out = []
    for date in dates:
        day = [e for e in events if e["date"] == date]
        if not (3 <= len(day) <= 6):
            continue
        for frag in frags:
            gold = sum(frag.casefold() in e["title"].casefold() for e in day)
            if 1 <= gold <= 4 and gold < len(day):
                out.append({"date": date, "title": frag, "gold": gold, "day_n": len(day)})
    return out


def _row(band: str, index: int, prompt: str, tool: str, args: Dict[str, Any],
         skills: List[str], system: str, registry, gold: Any,
         fragment: str = "") -> Dict[str, Any]:
    obs = registry.observation(tool, args)
    parsed = json.loads(obs)
    if not parsed.get("ok"):
        raise ValueError("bad task %s %s" % (band, obs))
    if band == "global_count":
        got = len(parsed["result"])
    elif band == "day_count":
        needle = fragment.casefold()
        got = sum(needle in e["title"].casefold() for e in parsed["result"])
    else:
        raise ValueError(band)
    if got != gold:
        raise ValueError("gold mismatch %s %s fragment=%s expected %s got %s" % (band, args, fragment, gold, got))
    row = {
        "episode_id": "cal-titlecount-v3fix-%s-%03d" % (band, index),
        "tool_family": "calendar", "split": "final",
        "template_id": "cv3fix_" + band, "target_type": "cv3fix_" + band,
        "target": False, "prompt": prompt, "system": system, "environment": {},
        "expected_tool": tool, "expected_arguments": args,
        "skill_labels": skills, "answer_spec": {"kind": "cv3fix_" + band},
        "expected_observation": obs, "expected_final_answer": gold,
        "evaluation_only": True, "selection_allowed": False,
        "final_version": VERSION,
    }
    row["messages"] = _messages(system, prompt, tool, args, obs, gold)
    row["data_signature"] = task_signature(row)
    return row


def build_tasks(n_items: int = N_ITEMS) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    events = read_json(FIXTURE)["events"]
    registry = build_calendar_registry(str(FIXTURE))
    system = _system("calendar")
    prompts_used, sigs, calls_all, _forbidden_titles = _forbidden()
    # Allow reuse of Calendar v3 calendar_list dates (new projection).
    # Still forbid calls seen in any other dataset.
    v3_calls = set()
    v3_dir = V3_ROOT
    for path in sorted(v3_dir.rglob("*.jsonl")):
        for row in read_jsonl(path):
            if "expected_tool" in row:
                v3_calls.add(call_signature(row))
    calls = set(c for c in calls_all if c not in v3_calls)
    stats: Dict[str, Any] = {
        "existing_files": len(_existing_jsonl()),
        "v3_calls_exempted": len(v3_calls),
        "forbidden_non_v3_calls": len(calls),
    }
    rng = random.Random("%d|day_count" % TASK_SEED)
    raw = _day_candidates(events)
    # one candidate per date, prefer gold 2–3 for spread
    by_date = {}
    for c in raw:
        by_date.setdefault(c["date"], []).append(c)
    per_date = []
    for date, opts in by_date.items():
        opts = sorted(opts, key=lambda c: (0 if c["gold"] in (2, 3) else 1, -c["gold"], c["title"]))
        # shuffle among equally preferred
        best_rank = (0 if opts[0]["gold"] in (2, 3) else 1, -opts[0]["gold"])
        pool = [c for c in opts if (0 if c["gold"] in (2, 3) else 1, -c["gold"]) == best_rank]
        per_date.append(rng.choice(pool))
    by_gold = {}
    for c in per_date:
        by_gold.setdefault(c["gold"], []).append(c)
    for g in by_gold:
        rng.shuffle(by_gold[g])
    # take all gold=3, then 2, then 1
    ordered = []
    for g in (3, 2, 1, 4):
        ordered.extend(by_gold.get(g, []))
    chosen = []
    i = 0
    for c in ordered:
        if len(chosen) >= n_items:
            break
        args = {"date": c["date"]}
        prompt = DAY_PROMPTS[len(chosen) % len(DAY_PROMPTS)].format(d=c["date"], f=c["title"])
        if prompt in prompts_used:
            prompt = DAY_PROMPTS[(len(chosen) + 1) % len(DAY_PROMPTS)].format(d=c["date"], f=c["title"])
            if prompt in prompts_used:
                continue
        trial = _row("day_count", len(chosen), prompt, "calendar_list", args,
                     ["calendar_list", "calendar_count", "calendar_title"], system, registry, c["gold"],
                     fragment=c["title"])
        trial["title_fragment"] = c["title"]
        trial["answer_spec"] = {"kind": "cv3fix_day_count", "title": c["title"]}
        if task_signature(trial) in sigs:
            continue
        if call_signature(trial) in calls:
            continue
        if any(call_signature(r) == call_signature(trial) for r in chosen):
            continue
        chosen.append(trial)
        calls.add(call_signature(trial))
        prompts_used.add(prompt)
    if len(chosen) < n_items:
        raise ValueError("not enough day_count items: %d (dates %d, raw %d)" % (
            len(chosen), len(per_date), len(raw)))
    stats["day_count"] = {
        "n": len(chosen), "date_candidates": len(per_date), "raw": len(raw),
        "answer_hist": dict(Counter(r["expected_final_answer"] for r in chosen)),
        "dates": [r["expected_arguments"]["date"] for r in chosen],
        "fragments": [r["title_fragment"] for r in chosen],
        "day_n": [json.loads(r["expected_observation"])["result"] and
                  len(json.loads(r["expected_observation"])["result"]) for r in chosen],
    }
    return chosen, stats



def semantic_gold(row: Dict[str, Any], events: List[Dict[str, Any]]) -> Any:
    kind = row["target_type"].split("cv3fix_", 1)[-1]
    if kind == "global_count":
        f = row["expected_arguments"]["title"]
        return sum(f.casefold() in e["title"].casefold() for e in events)
    if kind == "day_count":
        f = row.get("title_fragment") or row["answer_spec"]["title"]
        d = row["expected_arguments"]["date"]
        return sum(e["date"] == d and f.casefold() in e["title"].casefold() for e in events)
    raise ValueError(kind)


def check(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    events = read_json(FIXTURE)["events"]
    registry = build_calendar_registry(str(FIXTURE))
    prompts, sigs, calls_all, _titles = _forbidden()
    v3_calls = set()
    for path in sorted(V3_ROOT.rglob("*.jsonl")):
        for row in read_jsonl(path):
            if "expected_tool" in row:
                v3_calls.add(call_signature(row))
    calls = set(c for c in calls_all if c not in v3_calls)
    bad_exec, bad_sem, bad_msg, bad_obs = [], [], [], []
    for r in rows:
        obs = registry.observation(r["expected_tool"], r["expected_arguments"])
        if json.loads(obs) != json.loads(r["expected_observation"]):
            bad_exec.append(r["episode_id"])
        if semantic_gold(r, events) != r["expected_final_answer"]:
            bad_sem.append(r["episode_id"])
        if json.loads(r["messages"][4]["content"])["answer"] != r["expected_final_answer"]:
            bad_msg.append(r["episode_id"])
        n_ev = json.loads(obs)["result"]
        if r["target_type"] == "cv3fix_global_count" and len(n_ev) > 5:
            bad_obs.append(r["episode_id"])
        if len(r["expected_observation"]) > 1800:
            bad_obs.append(r["episode_id"])
    res: Dict[str, Any] = {
        "gold_reexec_mismatch": bad_exec,
        "gold_fixture_semantic_mismatch": bad_sem,
        "message_answer_mismatch": bad_msg,
        "long_observation": bad_obs,
        "n_existing_files_scanned": len(_existing_jsonl()),
        "overlap_task_signature": [r["episode_id"] for r in rows if task_signature(r) in sigs],
        "overlap_prompt": [r["episode_id"] for r in rows if r["prompt"] in prompts],
        "overlap_calendar_call": [r["episode_id"] for r in rows if call_signature(r) in calls],
        "n_rows": len(rows),
        "types": dict(Counter(r["target_type"] for r in rows)),
        "answer_hist": dict(Counter(r["expected_final_answer"] for r in rows)),
        "max_observation_chars": max(len(r["expected_observation"]) for r in rows),
        "v3_fixture_sha256": sha256_file(FIXTURE),
        "internal_call_dups": len(rows) - len({call_signature(r) for r in rows}),
        "internal_prompt_dups": len(rows) - len({r["prompt"] for r in rows}),
    }
    res["ok"] = not (bad_exec or bad_sem or bad_msg or bad_obs
                     or res["overlap_task_signature"] or res["overlap_prompt"]
                     or res["overlap_calendar_call"] or res["internal_call_dups"]
                     or res["internal_prompt_dups"]) and len(rows) == N_ITEMS
    return res


def build() -> None:
    if (OUT / "final" / "FROZEN.json").exists():
        raise SystemExit("already frozen; refusing to rebuild")
    OUT.mkdir(parents=True, exist_ok=True)
    rows, stats = build_tasks()
    write_jsonl(OUT / "candidate" / "title_count_v3fix.jsonl", rows)
    chk = check(rows)
    chk["task_stats"] = stats
    write_json(OUT / "checks.json", chk)
    print(json.dumps({k: chk[k] for k in ("ok", "n_rows", "types", "answer_hist",
                                          "max_observation_chars", "ok") if k in chk}, indent=1))
    print(json.dumps(stats, indent=1, ensure_ascii=False))
    if not chk["ok"]:
        raise SystemExit("checks failed: %s" % json.dumps({k: chk[k] for k in chk if k != "task_stats"})[:3000])


def freeze(note: str) -> None:
    fin = OUT / "final"
    if (fin / "FROZEN.json").exists():
        raise SystemExit("already frozen")
    rows = read_jsonl(OUT / "candidate" / "title_count_v3fix.jsonl")
    chk = check(rows)
    if not chk["ok"]:
        raise SystemExit("checks failed; not freezing: %s" % json.dumps(chk)[:2000])
    fin.mkdir(parents=True, exist_ok=True)
    write_jsonl(fin / "title_count_v3fix.jsonl", rows)
    h_rows, h_fix = sha256_file(fin / "title_count_v3fix.jsonl"), sha256_file(FIXTURE)
    import hashlib
    write_json(fin / "FROZEN.json", {
        "version": VERSION, "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "files": {"title_count_v3fix": {"path": "final/title_count_v3fix.jsonl",
                                        "count": len(rows), "sha256": h_rows}},
        "fixture": {"path": "../data_ext_cal_v3/fixtures/calendar_v3.json",
                    "sha256": h_fix, "note": "read-only reuse of frozen Calendar v3 fixture; not modified"},
        "combined_sha256": hashlib.sha256((h_rows + h_fix).encode()).hexdigest(),
        "types": chk["types"], "seeds": {"tasks": TASK_SEED},
        "scoring": "joint success (tool, exact arguments, execution on calendar_v3.json, exact answer); "
                   "report overall and per band (global_count, day_count)",
        "rationale": "Fixes v3 search_count's zero discrimination by replacing long global "
                     "title searches (gold 6–10, systematically undercounted) with 30 "
                     "short-list day_count items (calendar_list on one day, gold 1–3, "
                     "not equal to the day total). Not Calendar v4 (multi-instance).",
        "pilot_note": note,
        "rules": ["Evaluation only; never a training, replay, probe or selection input.",
                  "Does not replace frozen Calendar v3.",
                  "Any change requires a new version string and hashes."],
    })
    write_json(OUT / "checks_frozen.json", chk)
    print("FROZEN", h_rows, "combined", hashlib.sha256((h_rows + h_fix).encode()).hexdigest())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.freeze:
        freeze(a.note)
    else:
        build()


if __name__ == "__main__":
    main()
