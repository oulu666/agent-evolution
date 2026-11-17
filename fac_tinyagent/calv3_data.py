"""[ext 2026-11-11] Calendar natural final v3: UNTRAINED Calendar sub-skills.

Pilot 1 (13:17-13:22, seed 20261108, REF:start vs E4:tf50; see data_ext_cal_v3/PILOT.md):
locations was at the floor (0.00/0.03) and attendee_count near ceiling already before Calendar
(0.87/0.93), so before freezing: locations restricted to days with 3-5 events (still >=1 duplicate),
attendee lists widened to 2-10 people, 15 days per month.

Writes data_ext_cal_v3/ only (refuses to overwrite a frozen version):
  fixtures/calendar_v3.json   NEW irregular calendar (2026-07..2026-09, ids E301+,
                              new titles / rooms / people, 1-6 meetings per day,
                              irregular start times and durations, no overlaps).
  candidate/calendar_v3.jsonl  tasks (before freezing; used by the pilot)
  final_v3/calendar_v3.jsonl + FROZEN.json   (after `--freeze`)
  checks.json                  unit checks (gold re-exec, fixture re-derivation,
                               overlap with every training / eval jsonl, untrained check)

Sub-skills (none is a Calendar training template; training templates are
count_date, count_month, list_titles, search_dates, attendees, free_slot(first)):
  free_latest      calendar_free_slots -> LAST free slot (first != last enforced)
  locations        calendar_list -> sorted DISTINCT locations (duplicates enforced)
  attendee_count   calendar_attendees -> number of attendees
  search_count     calendar_search -> number of matching events
  last_end         calendar_list -> end time of the last meeting of the day
Nothing here loads a model.  final_v3 is evaluation-only.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .research_data import call_signature, task_signature
from .round2_data import _messages, _system
from .tools import build_calendar_registry
from .utils import canonical_json, read_json, read_jsonl, sha256_file, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_ext_cal_v3"
FIXTURE = OUT / "fixtures" / "calendar_v3.json"
VERSION = "calendar_natural_final_v3"
FIX_SEED = 20261131
TASK_SEED = 20261132
PER_TYPE = 30

TITLES = ["Vendor Sync", "Roadmap Review", "Hiring Panel", "Release Planning", "Security Audit",
          "QA Triage", "Board Prep", "Team Lunch", "Mentoring Session", "Budget Review",
          "Customer Workshop", "Incident Postmortem", "Design Critique", "Data Review", "Ops Sync",
          "Partner Call", "Quarterly Planning", "Tech Talk", "Onboarding", "Sales Huddle"]
TITLE_W = [9, 8, 7, 7, 6, 6, 5, 5, 4, 4, 3, 3, 3, 2, 2, 2, 1, 1, 1, 1]
LOCATIONS = ["Room A", "Room B", "Room D", "Lab 2", "Atrium", "Online"]
PEOPLE = ["Kevin", "Laura", "Mallory", "Nina", "Oscar", "Peggy", "Quinn", "Rupert",
          "Sybil", "Trent", "Uma", "Victor"]
DURS = [30, 45, 60, 60, 90, 120]


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _clock(x: int) -> str:
    return "%02d:%02d" % divmod(x, 60)


# ------------------------------------------------------------------ fixture
def build_fixture() -> Dict[str, Any]:
    rng = random.Random(FIX_SEED)
    days = []
    for month in (7, 8, 9):
        pool = [d for d in range(1, 29)]
        rng.shuffle(pool)
        days += ["2026-%02d-%02d" % (month, d) for d in sorted(pool[:15])]
    events = []
    for date in days:
        n = rng.choice([1, 2, 3, 3, 3, 4, 4, 4, 5, 5, 6, 6])
        placed: List[Tuple[int, int]] = []
        tries = 0
        while len(placed) < n and tries < 400:
            tries += 1
            dur = rng.choice(DURS)
            start = rng.randrange(9 * 60, 17 * 60 - dur + 1, 15)
            end = start + dur
            if any(start < e and s < end for s, e in placed):
                continue
            placed.append((start, end))
        # some days run until 17:00 so the latest free slot is not always 16:xx-17:00
        if rng.random() < 0.25:
            last_end = max(e for _, e in placed)
            if last_end < 17 * 60 - 30:
                s = rng.choice([16 * 60, 16 * 60 + 15, 16 * 60 + 30])
                if all(s >= e for _, e in placed):
                    placed.append((s, 17 * 60))
        for s, e in sorted(placed):
            k = rng.choice([2, 3, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 10])
            events.append({"date": date, "start": _clock(s), "end": _clock(e),
                           "title": rng.choices(TITLES, weights=TITLE_W)[0], "location": rng.choice(LOCATIONS),
                           "attendees": rng.sample(PEOPLE, k)})
    events.sort(key=lambda e: (e["date"], e["start"]))
    out = []
    for i, e in enumerate(events):
        out.append({"id": "E%03d" % (301 + i), "title": e["title"], "date": e["date"], "start": e["start"],
                    "end": e["end"], "location": e["location"], "attendees": e["attendees"]})
    return {"events": out}


# ------------------------------------------------------------ semantic gold
def _free(ev, date, dur):
    busy = sorted((_hm(e["start"]), _hm(e["end"])) for e in ev if e["date"] == date)
    t, gaps = 9 * 60, []
    for s, e in busy:
        if s - t >= dur:
            gaps.append((t, s))
        t = max(t, e)
    if 17 * 60 - t >= dur:
        gaps.append((t, 17 * 60))
    return [{"start": _clock(s), "end": _clock(e)} for s, e in gaps]


def semantic_gold(kind: str, a: Dict[str, Any], ev: List[Dict[str, Any]]) -> Any:
    """Gold recomputed directly from the fixture JSON (no tool code)."""
    if kind == "free_latest":
        g = _free(ev, a["date"], a["duration_minutes"])
        return g[-1] if g else None
    if kind == "locations":
        return sorted({e["location"] for e in ev if e["date"] == a["date"]})
    if kind == "attendee_count":
        return len(next(e["attendees"] for e in ev if e["id"] == a["event_id"]))
    if kind == "search_count":
        return sum(a["title"].casefold() in e["title"].casefold() for e in ev)
    if kind == "last_end":
        ends = [_hm(e["end"]) for e in ev if e["date"] == a["date"]]
        return _clock(max(ends)) if ends else None
    raise ValueError(kind)


def project(kind: str, result: Any) -> Any:
    """Gold from the executed tool observation."""
    if kind == "free_latest":
        return result[-1] if result else None
    if kind == "locations":
        return sorted({e["location"] for e in result})
    if kind in ("attendee_count", "search_count"):
        return len(result)
    if kind == "last_end":
        return result[-1]["end"] if result else None
    raise ValueError(kind)


SPECS = {
    # kind: (tool, skill_labels, prompts)
    "free_latest": ("calendar_free_slots", ["calendar_time", "calendar_free"], [
        "I want to book a {n}-minute meeting as late as possible on {d}. What is the last free interval in the workday (09:00-17:00) that fits it? Return an object with start and end.",
        "On {d}, which free block of at least {n} minutes comes latest in the day? Give it as an object with start and end.",
        "Looking at {d} between 09:00 and 17:00, find the final open gap that can hold {n} minutes. Answer with an object containing start and end.",
        "What is the latest free slot of {n} minutes or more on {d}? Reply with an object with start and end.",
    ]),
    "locations": ("calendar_list", ["calendar_list", "calendar_location"], [
        "Which rooms or places will I be in on {d}? List each location once, alphabetically, as a JSON list.",
        "Give me the distinct meeting locations for {d}, without duplicates, sorted A-Z, as a JSON list.",
        "On {d}, where are my meetings held? Return the unique locations as an alphabetically sorted JSON list.",
        "List every different venue used by events on {d}, each only once, in alphabetical order as a JSON list.",
    ]),
    "attendee_count": ("calendar_attendees", ["calendar_attendees", "calendar_count"], [
        "How many people are invited to meeting {e}? Answer with a single number.",
        "What is the headcount for event {e}? Reply with just the number of attendees.",
        "Count the attendees of {e} and give me the number.",
        "For event {e}, how many participants are on the guest list? Answer as a number.",
    ]),
    "search_count": ("calendar_search", ["calendar_search", "calendar_count"], [
        "How many events on my calendar have '{f}' in their title? Answer with a number.",
        "Count all meetings whose name contains '{f}'. Reply with just the count.",
        "In total, how many '{f}' sessions are scheduled? Give a single number.",
        "How many calendar entries mention '{f}' in the title? Answer as a number.",
    ]),
    "last_end": ("calendar_list", ["calendar_list", "calendar_time"], [
        "When does my last meeting on {d} finish? Answer with the end time as an HH:MM string.",
        "On {d}, at what time am I done with meetings for the day? Give the end time of the final event as HH:MM.",
        "What time does the final event on {d} end? Reply with a string in HH:MM format.",
        "I'd like to know when my schedule on {d} wraps up: the end time of the last meeting, as HH:MM.",
    ]),
}


def _candidates(kind: str, ev: List[Dict[str, Any]], rng: random.Random) -> List[Dict[str, Any]]:
    dates = sorted({e["date"] for e in ev})
    if kind == "free_latest":
        out = []
        for d in dates:
            for n in (30, 45, 60, 90):
                g = _free(ev, d, n)
                if len(g) >= 2 and g[-1] != g[0]:
                    out.append({"date": d, "duration_minutes": n})
        return out
    if kind == "locations":
        out = []
        for d in dates:
            locs = [e["location"] for e in ev if e["date"] == d]
            if 3 <= len(locs) <= 5 and len(set(locs)) < len(locs):
                out.append({"date": d})
        return out
    if kind == "attendee_count":
        return [{"event_id": e["id"]} for e in ev]
    if kind == "search_count":
        frags = sorted({t for t in TITLES} | {w for t in TITLES for w in t.split() if len(w) > 3}
                       | {t.split()[0].lower() for t in TITLES})
        forbidden = set()
        for p in _all_existing_jsonl():
            forbidden |= {x["expected_arguments"].get("title") for x in read_jsonl(p)
                          if x.get("expected_tool") == "calendar_search" and isinstance(x.get("expected_arguments"), dict)}
        out = []
        for f in frags:
            if f in forbidden:
                continue
            c = sum(f.casefold() in e["title"].casefold() for e in ev)
            if 1 <= c <= 12:
                out.append({"title": f})
        return out
    if kind == "last_end":
        return [{"date": d} for d in dates if sum(e["date"] == d for e in ev) >= 2]
    raise ValueError(kind)


def _row(kind: str, index: int, prompt: str, tool: str, args: Dict[str, Any], skills: List[str],
         system: str, registry) -> Dict[str, Any]:
    obs = registry.observation(tool, args)
    parsed = json.loads(obs)
    if not parsed.get("ok"):
        raise ValueError("bad task %s %s" % (kind, obs))
    ans = project(kind, parsed["result"])
    row = {"episode_id": "calv3-final-%s-%03d" % (kind, index), "tool_family": "calendar",
           "split": "final", "template_id": "cv3_" + kind, "target_type": "cv3_" + kind, "target": True,
           "prompt": prompt, "system": system, "environment": {}, "expected_tool": tool,
           "expected_arguments": args, "skill_labels": skills, "answer_spec": {"kind": "cv3_" + kind},
           "expected_observation": obs, "expected_final_answer": ans, "evaluation_only": True,
           "selection_allowed": False, "final_version": VERSION}
    row["messages"] = _messages(system, prompt, tool, args, obs, ans)
    row["data_signature"] = task_signature(row)
    return row


def build_tasks(per_type: int = PER_TYPE) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    ev = read_json(FIXTURE)["events"]
    registry = build_calendar_registry(str(FIXTURE))
    system = _system("calendar")  # tool schemas do not depend on the fixture
    rows, stats = [], {}
    for kind, (tool, skills, prompts) in SPECS.items():
        rng = random.Random("%d|%s" % (TASK_SEED, kind))
        cands = _candidates(kind, ev, rng)
        rng.shuffle(cands)
        if kind in ("attendee_count", "search_count"):  # spread answers over 1..7 instead of following the raw mix
            by = {}
            for a in cands:
                by.setdefault(semantic_gold(kind, a, ev), []).append(a)
            order, i = [], 0
            while len(order) < len(cands):
                for k in sorted(by):
                    if i < len(by[k]):
                        order.append(by[k][i])
                i += 1
            cands = order
        chosen = []
        i = 0
        while len(chosen) < per_type:
            args = cands[i % len(cands)]
            rep = i // len(cands)
            prompt = prompts[(len(chosen) + rep) % len(prompts)].format(
                d=args.get("date"), n=args.get("duration_minutes"), e=args.get("event_id"), f=args.get("title"))
            i += 1
            if any(r["prompt"] == prompt for r in chosen):
                if i > 50 * len(cands):
                    raise ValueError("not enough candidates for %s" % kind)
                continue
            chosen.append(_row(kind, len(chosen), prompt, tool, dict(args), skills, system, registry))
        rows += chosen
        golds = [canonical_json(r["expected_final_answer"]) for r in chosen]
        stats[kind] = {"n": len(chosen), "candidates": len(cands),
                       "distinct_calls": len({call_signature(r) for r in chosen}),
                       "distinct_answers": len(set(golds)),
                       "most_common_answer_share": Counter(golds).most_common(1)[0][1] / len(chosen),
                       "answer_hist": dict(Counter(golds).most_common(8))}
    return rows, stats


# ------------------------------------------------------------------ checks
def _all_existing_jsonl() -> List[Path]:
    out = []
    for d in sorted(ROOT.glob("data*")):
        if d.is_dir() and d.name != "data_ext_cal_v3":
            out += sorted(d.rglob("*.jsonl"))
    return out


def check(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ev = read_json(FIXTURE)["events"]
    reg = build_calendar_registry(str(FIXTURE))
    res: Dict[str, Any] = {}
    bad_exec, bad_sem, bad_msg = [], [], []
    for r in rows:
        kind = r["target_type"][4:]
        obs = reg.observation(r["expected_tool"], r["expected_arguments"])
        if json.loads(obs) != json.loads(r["expected_observation"]) or \
                project(kind, json.loads(obs)["result"]) != r["expected_final_answer"]:
            bad_exec.append(r["episode_id"])
        if semantic_gold(kind, r["expected_arguments"], ev) != r["expected_final_answer"]:
            bad_sem.append(r["episode_id"])
        if json.loads(r["messages"][4]["content"])["answer"] != r["expected_final_answer"]:
            bad_msg.append(r["episode_id"])
    res["gold_reexec_mismatch"] = bad_exec
    res["gold_fixture_semantic_mismatch"] = bad_sem
    res["message_answer_mismatch"] = bad_msg
    # overlap with every pre-existing dataset file (training, pools, probes, val/test, finals v1/v2)
    sigs, msgs, prompts, calls_cal = set(), set(), set(), set()
    files = _all_existing_jsonl()
    for p in files:
        for x in read_jsonl(p):
            if "prompt" in x and "expected_tool" in x:
                sigs.add(task_signature(x))
                prompts.add(x["prompt"])
                if x.get("tool_family") == "calendar":
                    calls_cal.add(call_signature(x))
            if "messages" in x:
                msgs.add(canonical_json(x["messages"]))
    res["n_existing_files_scanned"] = len(files)
    res["overlap_task_signature"] = [r["episode_id"] for r in rows if task_signature(r) in sigs]
    res["overlap_prompt"] = [r["episode_id"] for r in rows if r["prompt"] in prompts]
    res["overlap_messages"] = [r["episode_id"] for r in rows if canonical_json(r["messages"]) in msgs]
    res["overlap_calendar_call"] = [r["episode_id"] for r in rows if call_signature(r) in calls_cal]
    # untrained check: Calendar training templates and the v3 target types
    tr = read_jsonl(ROOT / "data_phase2" / "calendar" / "train.jsonl")
    res["calendar_train_templates"] = sorted({x["template_id"] for x in tr})
    res["v3_types"] = sorted({r["target_type"] for r in rows})
    old_ids = {e["id"] for e in read_json(ROOT / "data_phase2" / "fixtures" / "calendar.json")["events"]}
    res["fixture_id_overlap_with_v1_fixture"] = sorted(old_ids & {e["id"] for e in ev})
    res["fixture_stats"] = {
        "events": len(ev), "days": len({e["date"] for e in ev}),
        "months": sorted({e["date"][:7] for e in ev}),
        "meetings_per_day": dict(sorted(Counter(Counter(e["date"] for e in ev).values()).items())),
        "distinct_start_times": len({e["start"] for e in ev}),
        "attendee_count_hist": dict(sorted(Counter(len(e["attendees"]) for e in ev).items())),
        "locations": dict(Counter(e["location"] for e in ev)),
    }
    res["n_rows"] = len(rows)
    res["types"] = dict(Counter(r["target_type"] for r in rows))
    res["ok"] = not (bad_exec or bad_sem or bad_msg or res["overlap_task_signature"] or res["overlap_prompt"]
                     or res["overlap_messages"] or res["overlap_calendar_call"]
                     or res["fixture_id_overlap_with_v1_fixture"]) and all(
        n >= 25 for n in res["types"].values())
    return res


def build() -> None:
    if (OUT / "final_v3" / "FROZEN.json").exists():
        raise SystemExit("final_v3 already frozen; refusing to rebuild")
    (OUT / "fixtures").mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(build_fixture(), ensure_ascii=False, indent=2), encoding="utf-8")
    rows, stats = build_tasks()
    write_jsonl(OUT / "candidate" / "calendar_v3.jsonl", rows)
    chk = check(rows)
    chk["task_stats"] = stats
    write_json(OUT / "checks.json", chk)
    print(json.dumps({k: chk[k] for k in ("ok", "n_rows", "types", "fixture_stats")}, indent=1))
    print(json.dumps(stats, indent=1))


def freeze(note: str) -> None:
    fin = OUT / "final_v3"
    if (fin / "FROZEN.json").exists():
        raise SystemExit("already frozen")
    rows = read_jsonl(OUT / "candidate" / "calendar_v3.jsonl")
    chk = check(rows)
    if not chk["ok"]:
        raise SystemExit("checks failed; not freezing: %s" % json.dumps(chk)[:2000])
    fin.mkdir(parents=True, exist_ok=True)
    write_jsonl(fin / "calendar_v3.jsonl", rows)
    h_rows, h_fix = sha256_file(fin / "calendar_v3.jsonl"), sha256_file(FIXTURE)
    import hashlib
    write_json(fin / "FROZEN.json", {
        "version": VERSION, "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "files": {"calendar_v3": {"path": "final_v3/calendar_v3.jsonl", "count": len(rows), "sha256": h_rows}},
        "fixture": {"path": "fixtures/calendar_v3.json", "sha256": h_fix},
        "combined_sha256": hashlib.sha256((h_rows + h_fix).encode()).hexdigest(),
        "types": chk["types"], "seeds": {"fixture": FIX_SEED, "tasks": TASK_SEED},
        "untrained_rationale": "Calendar training templates = %s; v3 types are none of these (last free slot, distinct "
                               "locations, attendee count, title-search count, last end time)." % chk["calendar_train_templates"],
        "scoring": "joint success (tool, exact arguments, execution on fixtures/calendar_v3.json, exact answer via metrics.answers_equal); per sub-skill = mean over its items",
        "pilot_note": note,
        "rules": ["Evaluation only: never a training, replay, probe or selection input.",
                  "Scored once per finished checkpoint; any change requires a new version string and hashes."],
    })
    write_json(OUT / "checks_frozen.json", chk)
    print("FROZEN", h_rows, h_fix)


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