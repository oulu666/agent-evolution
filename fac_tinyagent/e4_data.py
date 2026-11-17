"""[ext 2026-11-11] E4 data: clean File replay pool + frozen natural final v2.

Writes data_ext_e4/ only (refuses to overwrite):
  pool/file.jsonl      data_round2 pool File rows minus the 16 mislabeled
                       last-match targets, plus 16 new last-match targets whose
                       gold is the executed *last* matching line, built on new
                       files/paths (e4_replay/...) disjoint from every eval set.
  pool/database.jsonl, pool/python.jsonl   byte-identical copies of data_round2.
  manifest.json        target_ids (File replaced; Database/Python unchanged).
  final_v2/{file,database,python,calendar}.jsonl + FROZEN.json
                       natural final v2: Database/Python = data_round2 final
                       (unchanged rows), File = the same 30 round2_final
                       instances relabeled to the last matching line, Calendar =
                       30 new natural-language tasks (6 trained skills x 5).
  checks.json          unit checks (executed gold, semantic label checks) and
                       leakage checks.
Nothing here loads a model.  final_v2 is evaluation-only and is never passed to
any training API (e4_run enforces this before training).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .data.generate import _observation
from .research_data import call_signature, task_signature
from .round2_data import _make_row, _system
from .utils import canonical_json, read_json, read_jsonl, sha256_file, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_ext_e4"
R2 = ROOT / "data_round2"
MV2 = ROOT / "data_ext_monitor_v2"
FIX = ROOT / "data_phase2" / "fixtures"
DB_PATH = FIX / "toolbench.db"
CAL_PATH = FIX / "calendar.json"
OLD = ("file", "database", "python")
FINAL_FAMILIES = ("file", "database", "python", "calendar")
VERSION = "natural_final_v2"
N_FILE_TARGETS = 16
POOL_SEED = 20261121
CAL_SEED = 20261122
FILE_SCORING = ("file: joint (tool, arguments, execution) AND final answer equals the last "
                "matching line; strict = exact string; official v2 = ext_rescore lenient rule "
                "(exact line text, or body after 'line N: ', or {line,text} with matching line).")


# ------------------------------------------------------------------ helpers
def _sources() -> List[Path]:
    """Every pre-existing dataset file (train/val/test/pool/monitor/final/probe)."""
    out = []
    for root in ("data_phase2", "data_replay_study", "data_round2", "data_ext_monitor_v2"):
        base = ROOT / root
        out += sorted(base.glob("*.jsonl")) + sorted(base.glob("*/*.jsonl"))
    return [p for p in out if p.exists()]


def _eval_sources() -> List[Path]:
    """Every evaluation/monitor set a replay row must never coincide with."""
    out = [ROOT / "data_phase2" / f / s for f in FINAL_FAMILIES for s in ("test.jsonl", "val.jsonl")]
    out += sorted((ROOT / "data_replay_study").glob("*/*.jsonl"))
    out += sorted((R2 / "monitor").glob("*.jsonl")) + sorted((R2 / "final").glob("*.jsonl"))
    out += sorted(MV2.glob("*.jsonl"))
    return [p for p in out if p.exists()]


def _files_of(row: Dict[str, Any]) -> Dict[str, str]:
    return ((row.get("environment") or {}).get("files") or {})


def _paths_of(row: Dict[str, Any]) -> Set[str]:
    paths = set(_files_of(row))
    args = row.get("expected_arguments") or {}
    for key in ("path", "directory"):
        if isinstance(args.get(key), str):
            paths.add(args[key])
    return paths


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _answers_equal(a, b) -> bool:
    from .metrics import answers_equal
    return answers_equal(a, b)


# ------------------------------------------------------- semantic File gold
def file_semantic_gold(row: Dict[str, Any]) -> Tuple[bool, Any, str]:
    """Independent gold from the prompt's intent and a fresh tool execution.

    Returns (ok, gold, rule).  Does not use answer_spec / project_answer.
    """
    obs = json.loads(_observation("file", row["expected_tool"], row["expected_arguments"],
                                  row.get("environment", {}), str(DB_PATH), str(CAL_PATH)))
    if not obs.get("ok"):
        return False, None, "execution_failed"
    result = obs["result"]
    p = row["prompt"].lower()
    tool = row["expected_tool"]
    if tool == "file_search":
        if re.search(r"\blast\b|\blatest\b|final line|bottom-most", p):
            return True, (result[-1]["text"] if result else ""), "last_match"
        if re.search(r"\bfirst\b|\bearliest\b", p):
            return True, (result[0]["text"] if result else ""), "first_match"
        if p.startswith("how many lines in"):
            return True, len(result), "match_count"
    if tool == "file_read":
        if "exact contents" in p:
            return True, result, "contents"
        if p.startswith("how many lines are in"):
            return True, len(result.splitlines()), "line_count"
        if "whitespace-separated words" in p:
            return True, len(result.split()), "word_count"
    if tool == "file_list" and "how many .txt files" in p:
        return True, sum(x.endswith(".txt") for x in result), "txt_count"
    if tool == "file_write" and "character" in p:
        return True, result["characters"], "characters"
    return False, None, "unknown_intent"


def check_file_rows(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Execution + semantic label check for File rows.  Lists every failure."""
    rows = list(rows)
    bad, rules = [], Counter()
    for r in rows:
        obs = _observation("file", r["expected_tool"], r["expected_arguments"],
                           r.get("environment", {}), str(DB_PATH), str(CAL_PATH))
        if not _answers_equal(json.loads(obs), json.loads(r["expected_observation"])):
            bad.append({"episode_id": r["episode_id"], "why": "observation_mismatch"})
            continue
        ok, gold, rule = file_semantic_gold(r)
        rules[rule] += 1
        if not ok:
            bad.append({"episode_id": r["episode_id"], "why": rule})
        elif not _answers_equal(gold, r["expected_final_answer"]):
            bad.append({"episode_id": r["episode_id"], "why": "label_mismatch_" + rule})
        elif not _answers_equal(json.loads(r["messages"][4]["content"])["answer"], gold):
            bad.append({"episode_id": r["episode_id"], "why": "message_answer_mismatch"})
    return {"n": len(rows), "n_bad": len(bad), "bad": bad, "rules": dict(rules)}


# --------------------------------------------------------- Calendar gold
def _cal_events() -> List[Dict[str, Any]]:
    return read_json(CAL_PATH)["events"]


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def calendar_semantic_gold(row: Dict[str, Any]) -> Any:
    """Gold recomputed directly from the fixture JSON (no tool code)."""
    ev = _cal_events()
    a = row["expected_arguments"]
    kind = row["target_type"]
    if kind == "cal_nl_count_date":
        return sum(e["date"] == a["date"] for e in ev)
    if kind == "cal_nl_count_month":
        return sum(e["date"][:7] == a["month"] for e in ev)
    if kind == "cal_nl_list_titles":
        return sorted(e["title"] for e in ev if e["date"] == a["date"])
    if kind == "cal_nl_search_dates":
        return sorted(e["date"] for e in ev if a["title"].casefold() in e["title"].casefold())
    if kind == "cal_nl_attendees":
        return next(list(e["attendees"]) for e in ev if e["id"] == a["event_id"])
    if kind == "cal_nl_free_first":
        busy = sorted((_hm(e["start"]), _hm(e["end"])) for e in ev if e["date"] == a["date"])
        t, gaps = 9 * 60, []
        for s, e in busy:
            if s - t >= a["duration_minutes"]:
                gaps.append((t, s))
            t = max(t, e)
        if 17 * 60 - t >= a["duration_minutes"]:
            gaps.append((t, 17 * 60))
        if not gaps:
            return None
        s, e = gaps[0]
        return {"start": "%02d:%02d" % divmod(s, 60), "end": "%02d:%02d" % divmod(e, 60)}
    raise ValueError("unknown calendar target type %s" % kind)


CAL_SPECS = {
    # target_type: (tool, skill_labels, answer_spec, prompts)
    "cal_nl_count_date": ("calendar_list", ["calendar_date", "calendar_count"], {"kind": "length"}, [
        "My day on {d} looks packed. How many meetings are booked for that date? Answer with a single number.",
        "Tell me how many calendar events take place on {d}, as a number.",
        "On {d}, how many things are on my agenda in total? Reply with just the count.",
    ]),
    "cal_nl_count_month": ("calendar_count", ["calendar_month", "calendar_count"], {"kind": "identity"}, [
        "Across the whole of {m}, how many meetings do I have in total? Answer with a number.",
        "What is the total number of entries on my calendar during {m}?",
        "Over the month {m}, how many events were scheduled altogether? Reply with just the number.",
    ]),
    "cal_nl_list_titles": ("calendar_list", ["calendar_list", "calendar_date"], {"kind": "pluck", "field": "title"}, [
        "Which meetings do I have on {d}? Give me just their names, alphabetized, as a JSON list.",
        "What are the names of the events on my calendar for {d}? Return them as an alphabetically sorted JSON list.",
        "I want the titles of everything scheduled on {d}, in A-to-Z order, as a JSON list.",
    ]),
    "cal_nl_search_dates": ("calendar_search", ["calendar_search", "calendar_date"], {"kind": "pluck", "field": "date"}, [
        "On which days do I have a meeting with '{f}' in its name? Return the dates as a sorted JSON list.",
        "I need every date on which an event whose title mentions '{f}' happens, earliest first, as a JSON list.",
        "When are the '{f}' meetings? List their dates in ascending order as a JSON list.",
    ]),
    "cal_nl_attendees": ("calendar_attendees", ["calendar_attendees", "calendar_event"], {"kind": "identity"}, [
        "Who is attending meeting {e}? Return the attendee names as a JSON list, in the order the calendar gives them.",
        "Give me the guest list for event {e} as a JSON list, exactly as it is stored.",
        "Which people are invited to {e}? Answer with a JSON list of their names in the stored order.",
    ]),
    "cal_nl_free_first": ("calendar_free_slots", ["calendar_time", "calendar_free"], {"kind": "item", "index": 0}, [
        "I need a {n}-minute gap on {d} during working hours. What is the earliest open interval? Return an object with start and end.",
        "On {d}, when does my first free block of at least {n} minutes (workday 09:00-17:00) start and end? Answer as an object with start and end.",
        "Find me the earliest stretch of free time on {d} that can fit a {n}-minute meeting within 09:00-17:00; give it as an object with start and end.",
    ]),
}
CAL_PER_TYPE = 5


def _cal_args(kind: str, rng: random.Random) -> List[Dict[str, Any]]:
    ev = _cal_events()
    dates = sorted({e["date"] for e in ev})
    months = sorted({e["date"][:7] for e in ev})
    frags = sorted({w for e in ev for w in e["title"].split() if len(w) > 3} |
                   {e["title"] for e in ev})
    ids = [e["id"] for e in ev]
    if kind in ("cal_nl_count_date", "cal_nl_list_titles"):
        return [{"date": d} for d in dates]
    if kind == "cal_nl_count_month":
        return [{"month": m} for m in months]
    if kind == "cal_nl_search_dates":
        return [{"title": f} for f in frags]
    if kind == "cal_nl_attendees":
        return [{"event_id": i} for i in ids]
    if kind == "cal_nl_free_first":
        return [{"date": d, "duration_minutes": n} for d in dates for n in (30, 60)]
    raise ValueError(kind)


def build_calendar_final(used_sigs: Set[str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    from .data.generate import _schemas, build_system_prompt
    system = build_system_prompt("calendar", _schemas("calendar", str(DB_PATH), str(CAL_PATH)))
    cal_train = read_jsonl(ROOT / "data_phase2" / "calendar" / "train.jsonl")
    cal_other = (read_jsonl(ROOT / "data_phase2" / "calendar" / "val.jsonl") +
                 read_jsonl(ROOT / "data_phase2" / "calendar" / "test.jsonl"))
    train_calls = {call_signature(r) for r in cal_train}
    other_calls = {call_signature(r) for r in cal_other}
    rows, stats = [], {}
    for t_index, (kind, (tool, skills, spec, prompts)) in enumerate(CAL_SPECS.items()):
        rng = random.Random("%d|%s" % (CAL_SEED, kind))
        cands = _cal_args(kind, rng)
        rng.shuffle(cands)
        # Prefer calls never seen in Calendar training, then not in val/test.
        cands.sort(key=lambda a: (call_signature({"expected_tool": tool, "expected_arguments": a}) in train_calls,
                                  call_signature({"expected_tool": tool, "expected_arguments": a}) in other_calls))
        chosen, seen_calls, seen_answers = [], set(), set()
        i = 0
        while len(chosen) < CAL_PER_TYPE:
            if i < len(cands):
                args = cands[i]
            else:  # fewer distinct calls than slots (e.g. 3 months): reuse with another wording
                args = cands[i % len(cands)]
            i += 1
            prompt = prompts[len(chosen) % len(prompts)].format(
                d=args.get("date"), m=args.get("month"), f=args.get("title"),
                e=args.get("event_id"), n=args.get("duration_minutes"))
            cand = {"prompt": prompt, "expected_tool": tool, "expected_arguments": args}
            if task_signature(cand) in used_sigs:
                continue
            if i <= len(cands) and kind in ("cal_nl_search_dates", "cal_nl_attendees"):
                obs = json.loads(_observation("calendar", tool, args, {}, str(DB_PATH), str(CAL_PATH)))
                if not obs.get("ok") or not obs["result"]:
                    continue
                # keep items informative: no two search items with the same date set
                key = canonical_json(sorted(e["date"] for e in obs["result"])) if kind == "cal_nl_search_dates" else None
                if key is not None and key in seen_answers:
                    continue
                seen_answers.add(key)
            index = len(chosen)
            row = _make_row("calendar", "calnl2-final-%s-%03d" % (kind[7:], index), "nf2_" + kind,
                            "final", prompt, tool, args, skills, {}, spec, kind)
            row["system"] = system
            row["messages"][0]["content"] = system
            row["final_version"] = VERSION
            used_sigs.add(task_signature(row))
            chosen.append(row)
            seen_calls.add(call_signature(row))
        rows += chosen
        stats[kind] = {"n": len(chosen),
                       "calls_also_in_calendar_train": sum(call_signature(r) in train_calls for r in chosen),
                       "calls_also_in_calendar_val_test": sum(call_signature(r) in other_calls for r in chosen),
                       "distinct_calls": len({call_signature(r) for r in chosen})}
    return rows, stats


# ------------------------------------------------------------- File pool
FILL = ["alpha", "bravo", "delta", "echo"]
WORDS = ["juliet", "lima", "hotel", "india", "delta", "charlie", "kilo"]


def build_file_targets(forbidden_paths: Set[str], forbidden_contents: Set[str],
                       used_sigs: Set[str]) -> List[Dict[str, Any]]:
    """Same generator as round2_data._file_last_rows (6 lines, 2-3 matches) but
    new seed, new root e4_replay/, new file stem, and the executed last line as gold."""
    rng = random.Random(POOL_SEED)
    rows, index = [], 0
    while len(rows) < N_FILE_TARGETS:
        path = "e4_replay/log_%03d.txt" % index
        index += 1
        word = rng.choice(WORDS)
        lines = ["line %d: %s value %d" % (i + 1, rng.choice(FILL), rng.randint(10, 99)) for i in range(6)]
        for pos in sorted(rng.sample(range(6), rng.choice([2, 3]))):
            lines[pos] = "line %d: %s appears in this line" % (pos + 1, word)
        content = "\n".join(lines) + "\n"
        if path in forbidden_paths or content in forbidden_contents:
            continue
        row = _make_row("file", "file-train-e4_last_match-%03d" % len(rows), "e4_target_file_last_match",
                        "train", "Return the last line in %s that contains the word '%s'." % (path, word),
                        "file_search", {"path": path, "pattern": word}, ["file_search", "line_index"],
                        {"files": {path: content}}, {"kind": "match", "index": -1}, "file_last_match")
        if task_signature(row) in used_sigs:
            continue
        used_sigs.add(task_signature(row))
        forbidden_contents.add(content)
        rows.append(row)
    return rows


def relabel_file_final(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        obs = json.loads(r["expected_observation"])["result"]
        new = json.loads(json.dumps(r))
        new["source_episode_id"] = r["episode_id"]
        new["episode_id"] = "nf2-" + r["episode_id"]
        new["answer_spec"] = {"kind": "match", "index": -1}
        new["expected_final_answer"] = obs[-1]["text"]
        new["messages"][4]["content"] = json.dumps({"answer": obs[-1]["text"]})
        new["final_version"] = VERSION
        new["scoring"] = "file_last_line_v2"
        out.append(new)
    return out


# ----------------------------------------------------------------- build
def build() -> None:
    if OUT.exists():
        raise FileExistsError("Refusing to replace existing %s" % OUT)
    r2_manifest = read_json(R2 / "manifest.json")
    old_file_target_ids = set(r2_manifest["target_ids"]["file"])
    used_sigs = set()
    for p in _sources():
        for r in read_jsonl(p):
            if "prompt" in r and "expected_tool" in r:
                used_sigs.add(task_signature(r))
    eval_paths, eval_contents = set(), set()
    for p in _eval_sources():
        for r in read_jsonl(p):
            if r.get("tool_family") == "file":
                eval_paths |= _paths_of(r)
                eval_contents |= set(_files_of(r).values())
    # every pre-existing File path (train included) is forbidden for the new targets
    all_paths = set(eval_paths)
    for p in _sources():
        for r in read_jsonl(p):
            if r.get("tool_family") == "file":
                all_paths |= _paths_of(r)
    tmp = OUT.parent / (OUT.name + ".tmp_build")
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "pool").mkdir(parents=True)
    # pool
    file_pool = [r for r in read_jsonl(R2 / "pool" / "file.jsonl") if r["episode_id"] not in old_file_target_ids]
    removed = len(read_jsonl(R2 / "pool" / "file.jsonl")) - len(file_pool)
    new_targets = build_file_targets(all_paths, set(eval_contents), used_sigs)
    write_jsonl(tmp / "pool" / "file.jsonl", file_pool + new_targets)
    for f in ("database", "python"):
        shutil.copyfile(str(R2 / "pool" / (f + ".jsonl")), str(tmp / "pool" / (f + ".jsonl")))
    target_ids = {"file": [r["episode_id"] for r in new_targets],
                  "database": list(r2_manifest["target_ids"]["database"]),
                  "python": list(r2_manifest["target_ids"]["python"])}
    # final v2
    fin = tmp / "final_v2"
    fin.mkdir()
    write_jsonl(fin / "file.jsonl", relabel_file_final(read_jsonl(R2 / "final" / "file.jsonl")))
    for f in ("database", "python"):
        shutil.copyfile(str(R2 / "final" / (f + ".jsonl")), str(fin / (f + ".jsonl")))
    for r in read_jsonl(tmp / "pool" / "file.jsonl"):
        used_sigs.add(task_signature(r))
    cal_rows, cal_stats = build_calendar_final(used_sigs)
    write_jsonl(fin / "calendar.jsonl", cal_rows)
    files = {f: {"path": "final_v2/%s.jsonl" % f, "count": len(read_jsonl(fin / (f + ".jsonl"))),
                 "sha256": sha256_file(fin / (f + ".jsonl"))} for f in FINAL_FAMILIES}
    combined = _sha(canonical_json({f: files[f]["sha256"] for f in FINAL_FAMILIES}))
    frozen = {
        "version": VERSION, "frozen_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S %z"),
        "combined_sha256": combined, "files": files,
        "provenance": {
            "database": "byte-identical copy of data_round2/final/database.jsonl (sha256 %s)" % sha256_file(R2 / "final" / "database.jsonl"),
            "python": "byte-identical copy of data_round2/final/python.jsonl (sha256 %s)" % sha256_file(R2 / "final" / "python.jsonl"),
            "file": "same 30 instances as data_round2/final/file.jsonl (sha256 %s); gold relabeled to the executed last matching line; episode_id prefixed nf2-" % sha256_file(R2 / "final" / "file.jsonl"),
            "calendar": "new: 6 trained Calendar skills x %d, natural wording (3 paraphrases per skill), seed %d, gold by execution and re-derived from the fixture JSON" % (CAL_PER_TYPE, CAL_SEED),
        },
        "scoring": {"default": "joint success (tool, arguments, execution, exact answer via metrics.answers_equal)",
                    "file": FILE_SCORING},
        "fixtures": {"toolbench.db": sha256_file(DB_PATH), "calendar.json": sha256_file(CAL_PATH)},
        "calendar_call_overlap": cal_stats,
        "rules": ["Evaluation only: never a training, replay, probe or selection input.",
                  "Methods/thresholds are not chosen on final_v2; it is scored once per finished run.",
                  "Any change requires a new version string and new hashes."],
    }
    write_json(fin / "FROZEN.json", frozen)
    manifest = {
        "created_by": "fac_tinyagent.e4_data", "pool_seed": POOL_SEED,
        "pool": {f: {"count": len(read_jsonl(tmp / "pool" / (f + ".jsonl"))),
                     "target_count": len(target_ids[f]),
                     "sha256": sha256_file(tmp / "pool" / (f + ".jsonl"))} for f in OLD},
        "pool_unchanged_vs_round2": {f: sha256_file(tmp / "pool" / (f + ".jsonl")) == sha256_file(R2 / "pool" / (f + ".jsonl")) for f in OLD},
        "file_pool_change": {"removed_round2_targets": removed, "added_targets": len(new_targets),
                             "removed_ids": sorted(old_file_target_ids)},
        "target_ids": target_ids,
        "target_types": {"file": ["file_last_match"], "database": ["db_filter_top"], "python": ["median_natural"]},
        "final_v2": {"version": VERSION, "combined_sha256": combined},
    }
    write_json(tmp / "manifest.json", manifest)
    tmp.rename(OUT)
    checks = verify()
    print(json.dumps({"manifest": manifest["pool"], "final_v2": combined, "checks_ok": checks["ok"]}, indent=1))


# ---------------------------------------------------------------- verify
def verify() -> Dict[str, Any]:
    manifest = read_json(OUT / "manifest.json")
    frozen = read_json(OUT / "final_v2" / "FROZEN.json")
    problems = []
    res: Dict[str, Any] = {}
    # hashes
    for f in OLD:
        if sha256_file(OUT / "pool" / (f + ".jsonl")) != manifest["pool"][f]["sha256"]:
            problems.append("pool hash changed: " + f)
    for f, rec in frozen["files"].items():
        if sha256_file(OUT / rec["path"]) != rec["sha256"]:
            problems.append("final_v2 hash changed: " + f)
    if _sha(canonical_json({f: frozen["files"][f]["sha256"] for f in FINAL_FAMILIES})) != frozen["combined_sha256"]:
        problems.append("combined hash mismatch")
    for f in ("database", "python"):
        if sha256_file(OUT / "pool" / (f + ".jsonl")) != sha256_file(R2 / "pool" / (f + ".jsonl")):
            problems.append("pool %s differs from data_round2" % f)
        if sha256_file(OUT / "final_v2" / (f + ".jsonl")) != sha256_file(R2 / "final" / (f + ".jsonl")):
            problems.append("final_v2 %s differs from data_round2" % f)
    pool = {f: read_jsonl(OUT / "pool" / (f + ".jsonl")) for f in OLD}
    final = {f: read_jsonl(OUT / "final_v2" / (f + ".jsonl")) for f in FINAL_FAMILIES}
    # 1. File label unit checks: whole new pool + final_v2 File
    res["file_pool_label_check"] = check_file_rows(pool["file"])
    res["file_final_v2_label_check"] = check_file_rows(final["file"])
    res["round2_pool_label_check_reference"] = {k: v for k, v in check_file_rows(read_jsonl(R2 / "pool" / "file.jsonl")).items() if k != "bad"}
    for key in ("file_pool_label_check", "file_final_v2_label_check"):
        if res[key]["n_bad"]:
            problems.append("%s: %d bad" % (key, res[key]["n_bad"]))
    # executed gold for every row of every final_v2 family + pool targets
    exec_bad = []
    for f, rows in list(final.items()) + [(f, pool[f]) for f in OLD]:
        for r in rows:
            obs = _observation(f, r["expected_tool"], r["expected_arguments"], r.get("environment", {}),
                               str(DB_PATH), str(CAL_PATH))
            if not json.loads(obs).get("ok") or not _answers_equal(json.loads(obs), json.loads(r["expected_observation"])):
                exec_bad.append(r["episode_id"])
    res["executed_gold_mismatch"] = exec_bad
    if exec_bad:
        problems.append("executed gold mismatch: %d" % len(exec_bad))
    # Calendar semantic gold from fixture JSON
    cal_bad = [r["episode_id"] for r in final["calendar"]
               if not _answers_equal(calendar_semantic_gold(r), r["expected_final_answer"])
               or not _answers_equal(json.loads(r["messages"][4]["content"])["answer"], r["expected_final_answer"])]
    res["calendar_semantic_check"] = {"n": len(final["calendar"]), "n_bad": len(cal_bad), "bad": cal_bad,
                                      "types": dict(Counter(r["target_type"] for r in final["calendar"]))}
    if cal_bad:
        problems.append("calendar gold mismatch %d" % len(cal_bad))
    # target ids exist and are flagged
    for f in OLD:
        ids = {r["episode_id"] for r in pool[f]}
        missing = [i for i in manifest["target_ids"][f] if i not in ids]
        if missing:
            problems.append("missing target ids in %s: %s" % (f, missing[:3]))
    old_ids = set(read_json(R2 / "manifest.json")["target_ids"]["file"])
    if old_ids & {r["episode_id"] for r in pool["file"]}:
        problems.append("old mislabeled File targets still in pool")
    # 2. leakage: pool vs final_v2 (and every other eval/monitor set)
    final_rows = [r for rows in final.values() for r in rows]
    eval_rows = final_rows + [r for p in _eval_sources() for r in read_jsonl(p)]
    pool_rows = [r for rows in pool.values() for r in rows]
    new_cal = read_jsonl(ROOT / "data_phase2" / "calendar" / "train.jsonl")
    train_rows = pool_rows + new_cal
    leak = {}
    sig_eval = {task_signature(r) for r in eval_rows}
    msg_eval = {canonical_json(r["messages"]) for r in eval_rows if "messages" in r}
    leak["task_signature_overlap_train_vs_eval"] = sum(task_signature(r) in sig_eval for r in train_rows)
    leak["message_overlap_train_vs_eval"] = sum(canonical_json(r["messages"]) in msg_eval for r in train_rows)
    fin_file = final["file"]
    fin_paths = set().union(*[_paths_of(r) for r in fin_file])
    fin_contents = {c for r in fin_file for c in _files_of(r).values()}
    fin_pairs = {(r["expected_arguments"]["pattern"], c) for r in fin_file for c in _files_of(r).values()}
    all_eval_file = [r for r in eval_rows if r.get("tool_family") == "file"]
    eval_paths = set().union(*[_paths_of(r) for r in all_eval_file])
    eval_contents = {c for r in all_eval_file for c in _files_of(r).values()}
    pf = pool["file"]
    leak["file_path_overlap_pool_vs_final_v2"] = sorted(set().union(*[_paths_of(r) for r in pf]) & fin_paths)
    leak["file_path_overlap_pool_vs_any_eval"] = sorted(set().union(*[_paths_of(r) for r in pf]) & eval_paths)
    leak["file_content_overlap_pool_vs_final_v2"] = sum(c in fin_contents for r in pf for c in _files_of(r).values())
    leak["file_content_overlap_pool_vs_any_eval"] = sum(c in eval_contents for r in pf for c in _files_of(r).values())
    leak["file_pattern_content_overlap_pool_vs_final_v2"] = sum((r["expected_arguments"].get("pattern"), c) in fin_pairs
                                                                for r in pf for c in _files_of(r).values())
    fin_dirs = {p.split("/")[0] for p in fin_paths}
    new_t = [r for r in pf if r["episode_id"] in set(manifest["target_ids"]["file"])]
    leak["new_target_root_dirs"] = sorted({p.split("/")[0] for r in new_t for p in _paths_of(r)})
    leak["final_v2_file_root_dirs"] = sorted(fin_dirs)
    # line-level overlap of new target files vs final files (informative: template lines recur by design)
    fin_lines = {l for c in fin_contents for l in c.splitlines()}
    t_lines = [l for r in new_t for c in _files_of(r).values() for l in c.splitlines()]
    leak["new_target_lines_also_in_final_files"] = {"lines": len(t_lines), "shared": sum(l in fin_lines for l in t_lines),
                                                    "note": "line template 'line N: <word> appears in this line' recurs by design; whole files never repeat"}
    for key in ("task_signature_overlap_train_vs_eval", "message_overlap_train_vs_eval",
                "file_content_overlap_pool_vs_final_v2", "file_pattern_content_overlap_pool_vs_final_v2"):
        if leak[key]:
            problems.append("leak %s=%s" % (key, leak[key]))
    for key in ("file_path_overlap_pool_vs_final_v2", "file_path_overlap_pool_vs_any_eval"):
        if leak[key]:
            problems.append("leak %s=%s" % (key, leak[key][:3]))
    # probes vs final_v2 (monitor must not see the final)
    probe_rows = [r for p in sorted(MV2.glob("*.jsonl")) for r in read_jsonl(p)]
    leak["probe_vs_final_v2_signature_overlap"] = sum(task_signature(r) in {task_signature(x) for x in final_rows} for r in probe_rows)
    leak["final_v2_internal_duplicates"] = len(final_rows) - len({task_signature(r) for r in final_rows})
    if leak["probe_vs_final_v2_signature_overlap"] or leak["final_v2_internal_duplicates"]:
        problems.append("probe/final overlap or duplicates")
    res["leakage"] = leak
    res["counts"] = {"pool": {f: len(pool[f]) for f in OLD},
                     "pool_targets": {f: len(manifest["target_ids"][f]) for f in OLD},
                     "final_v2": {f: len(final[f]) for f in FINAL_FAMILIES}}
    res["final_v2_version"] = frozen["version"]
    res["final_v2_combined_sha256"] = frozen["combined_sha256"]
    res["problems"] = problems
    res["ok"] = not problems
    write_json(OUT / "checks.json", res)
    if problems:
        raise SystemExit("E4 DATA CHECK FAILED: %s" % problems)
    print("E4_DATA_OK", json.dumps(res["counts"]), "final_v2", frozen["combined_sha256"][:16])
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-only", action="store_true")
    a = ap.parse_args()
    if a.verify_only:
        verify()
    else:
        build()


if __name__ == "__main__":
    main()
