"""[ext 2026-11-12] Database non-target exam for the E3-B dose curve.

Scientific question: the E3-B S-curve (k=0/1/2/3/4/6 -> DB nat v2
0.00/0.10/0.34/0.61/0.82/1.00) is measured on target_db_filter_top, the same
template that was dosed. If a non-target exam does not rise with k, that curve
is template coverage, not Database-skill transfer.

Design:
  Same fixture as training / nat v2 (data_phase2/fixtures/toolbench.db), so a
  flat curve cannot be written off as 'unknown tables'. Items are NOT close
  rewrites of filter_top (no ORDER BY + LIMIT + 'list the name values').

  Bands:
    filter_count         COUNT(*) with a numeric 'col > threshold' filter.
                         Near a trained skill (db_filter_count uses string
                         equality), far from filter_top's ranked list.
    filter_mean          AVG(col) with a numeric filter. Related to db_average
                         / db_filter_average, not to filter_top.
    group_count_filter   GROUP BY after a numeric filter (composition).
    min_max              MIN/MAX, with or without a numeric filter. Farther:
                         this aggregate never appears in the target template
                         and is not a training template.
    multi_filter_count   COUNT with a string-equality AND a numeric comparison.
                         Farther query structure.

Writes data_ext_p0_db_nontarget/ only; refuses to overwrite a freeze.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from .data.generate import _observation, _schemas, build_system_prompt
from .data.templates import DB_GROUPS, DB_NUMERIC, DB_STRINGS
from .research_data import call_signature, project_answer, task_signature
from .round2_data import _messages
from .tools import build_db_registry
from .utils import canonical_json, read_jsonl, sha256_file, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_ext_p0_db_nontarget"
DB_PATH = ROOT / "data_phase2" / "fixtures" / "toolbench.db"
VERSION = "database_nontarget_v1"
TASK_SEED = 20261143
PER_BAND = 8
BANDS = ("filter_count", "filter_mean", "group_count_filter", "min_max", "multi_filter_count")


def _system() -> str:
    return build_system_prompt("database", _schemas("database", str(DB_PATH),
                                                    str(ROOT / "data_phase2" / "fixtures" / "calendar.json")))


def _existing_jsonl() -> List[Path]:
    out = []
    for d in sorted(ROOT.glob("data*")):
        if d.is_dir() and d.name != OUT.name:
            out += sorted(d.rglob("*.jsonl"))
    return out


def _forbidden() -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
    prompts, sigs, calls, sqls = set(), set(), set(), set()
    for path in _existing_jsonl():
        for row in read_jsonl(path):
            if "prompt" in row and "expected_tool" in row:
                prompts.add(row["prompt"])
                sigs.add(task_signature(row))
                calls.add(call_signature(row))
                args = row.get("expected_arguments") or {}
                if isinstance(args, dict) and "sql" in args:
                    sqls.add(str(args["sql"]).strip())
    return prompts, sigs, calls, sqls


def _lit(value: Any) -> str:
    if isinstance(value, str):
        return "'%s'" % value.replace("'", "''")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _thresholds(registry, table: str, column: str) -> List[Any]:
    result = registry.execute("db_query", {
        "sql": "SELECT DISTINCT %s FROM %s ORDER BY %s" % (column, table, column)})
    if not result.get("ok"):
        raise ValueError(result)
    values = [row[0] for row in result["result"]["rows"]]
    return values[:-1]  # keep at least one row


def _string_values() -> List[Tuple[str, str, str]]:
    out = []
    for table, cols in DB_STRINGS.items():
        for col, vals in cols.items():
            for v in vals:
                out.append((table, col, v))
    return out


def _row(index: int, band: str, prompt: str, sql: str, skills: List[str],
         spec: Dict[str, Any], system: str) -> Dict[str, Any]:
    tool, args = "db_query", {"sql": sql}
    obs = _observation("database", tool, args, {}, str(DB_PATH),
                       str(ROOT / "data_phase2" / "fixtures" / "calendar.json"))
    parsed = json.loads(obs)
    if not parsed.get("ok"):
        raise ValueError("bad sql %s: %s" % (sql, obs))
    answer = project_answer(parsed["result"], spec)
    if answer in (None, [], {}):
        raise ValueError("empty answer for %s" % sql)
    eid = "db-nontarget-%s-%03d" % (band, index)
    row = {
        "episode_id": eid, "tool_family": "database", "split": "final",
        "template_id": "nontarget_" + band, "target_type": "nontarget_" + band,
        "target": False, "prompt": prompt, "system": system, "environment": {},
        "expected_tool": tool, "expected_arguments": args,
        "skill_labels": skills, "answer_spec": spec,
        "expected_observation": obs, "expected_final_answer": answer,
        "evaluation_only": True, "selection_allowed": False,
        "final_version": VERSION,
    }
    row["messages"] = _messages(system, prompt, tool, args, obs, answer)
    row["data_signature"] = task_signature(row)
    return row


def _candidates(registry) -> Dict[str, List[Dict[str, Any]]]:
    banks = {b: [] for b in BANDS}
    numerics = [(table, col) for table, cols in DB_NUMERIC.items() for col in cols]
    for table, col in numerics:
        for thresh in _thresholds(registry, table, col):
            cond = "%s > %s" % (col, _lit(thresh))
            banks["filter_count"].append({
                "sql": "SELECT COUNT(*) AS n FROM %s WHERE %s" % (table, cond),
                "spec": {"kind": "scalar"},
                "skills": ["sql_filter", "sql_count"],
                "prompts": [
                    "How many records remain in %s after keeping only rows with %s strictly above %s? Answer with a number."
                    % (table, col, _lit(thresh)),
                    "In the %s table, count the rows satisfying %s strictly greater than %s. Reply with a single number."
                    % (table, col, _lit(thresh)),
                ],
            })
            for measured in DB_NUMERIC[table]:
                banks["filter_mean"].append({
                    "sql": "SELECT AVG(%s) AS v FROM %s WHERE %s" % (measured, table, cond),
                    "spec": {"kind": "scalar"},
                    "skills": ["sql_filter", "sql_aggregation"],
                    "prompts": [
                        "Among rows of %s whose %s is strictly above %s, what is the average %s? Return the numeric average."
                        % (table, col, _lit(thresh), measured),
                        "Filter %s to %s strictly greater than %s, then report the mean %s as a number."
                        % (table, col, _lit(thresh), measured),
                    ],
                })
            group = DB_GROUPS[table]
            banks["group_count_filter"].append({
                "sql": ("SELECT %s, COUNT(*) AS n FROM %s WHERE %s GROUP BY %s ORDER BY %s"
                        % (group, table, cond, group, group)),
                "spec": {"kind": "rows_mapping"},
                "skills": ["sql_filter", "sql_group", "sql_count"],
                "prompts": [
                    "After restricting %s to rows with %s strictly above %s, return a JSON object mapping each %s to its remaining row count."
                    % (table, col, _lit(thresh), group),
                    "For %s rows whose %s is greater than %s, give each %s's count as a JSON object."
                    % (table, col, _lit(thresh), group),
                ],
            })
            for fn, word in (("MIN", "smallest"), ("MAX", "largest")):
                banks["min_max"].append({
                    "sql": "SELECT %s(%s) AS v FROM %s WHERE %s" % (fn, col, table, cond),
                    "spec": {"kind": "scalar"},
                    "skills": ["sql_filter", "sql_aggregation"],
                    "prompts": [
                        "What is the %s %s among %s rows with %s strictly above %s? Answer with a number."
                        % (word, col, table, col, _lit(thresh)),
                        "On the subset of %s where %s > %s, return the %s value of %s."
                        % (table, col, _lit(thresh), word, col),
                    ],
                })
        # unfiltered min/max (even farther from filter_top)
        for fn, word in (("MIN", "minimum"), ("MAX", "maximum")):
            banks["min_max"].append({
                "sql": "SELECT %s(%s) AS v FROM %s" % (fn, col, table),
                "spec": {"kind": "scalar"},
                "skills": ["sql_aggregation"],
                "prompts": [
                    "What is the %s %s in the entire %s table? Answer with a number."
                    % (word, col, table),
                    "Return the %s of column %s over all rows of %s."
                    % (word, col, table),
                ],
            })
    for table, scol, sval in _string_values():
        for ncol in DB_NUMERIC[table]:
            for thresh in _thresholds(registry, table, ncol)[:4]:
                cond = "%s = %s AND %s > %s" % (scol, _lit(sval), ncol, _lit(thresh))
                banks["multi_filter_count"].append({
                    "sql": "SELECT COUNT(*) AS n FROM %s WHERE %s" % (table, cond),
                    "spec": {"kind": "scalar"},
                    "skills": ["sql_filter", "sql_count"],
                    "prompts": [
                        "How many %s rows have %s equal to %s and %s strictly above %s? Answer with a number."
                        % (table, scol, _lit(sval), ncol, _lit(thresh)),
                        "Count the records in %s that simultaneously satisfy %s = %s and %s > %s. Reply with a number."
                        % (table, scol, _lit(sval), ncol, _lit(thresh)),
                    ],
                })
    return banks


def build_tasks(per_band: int = PER_BAND) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    registry = build_db_registry(str(DB_PATH))
    system = _system()
    prompts_used, sigs, calls, sqls = _forbidden()
    banks = _candidates(registry)
    stats: Dict[str, Any] = {"existing_files": len(_existing_jsonl()), "raw": {b: len(banks[b]) for b in BANDS}}
    rows: List[Dict[str, Any]] = []
    for band in BANDS:
        rng = random.Random("%d|%s" % (TASK_SEED, band))
        raw = list(banks[band])
        rng.shuffle(raw)
        chosen = []
        for cand in raw:
            if len(chosen) >= per_band:
                break
            if cand["sql"].strip() in sqls:
                continue
            # try prompts in shuffled order
            prompt_list = list(cand["prompts"])
            rng.shuffle(prompt_list)
            for prompt in prompt_list:
                if prompt in prompts_used:
                    continue
                try:
                    trial = _row(len(chosen), band, prompt, cand["sql"], cand["skills"], cand["spec"], system)
                except ValueError:
                    continue
                if task_signature(trial) in sigs or call_signature(trial) in calls:
                    continue
                if any(call_signature(r) == call_signature(trial) for r in chosen + rows):
                    continue
                # reject answers that are literally identical for too many items later; keep for now
                chosen.append(trial)
                sqls.add(cand["sql"].strip())
                prompts_used.add(prompt)
                calls.add(call_signature(trial))
                break
        if len(chosen) < per_band:
            raise ValueError("not enough unused items for %s: got %d / %d (raw %d)" % (
                band, len(chosen), per_band, len(raw)))
        rows += chosen
        stats[band] = {
            "n": len(chosen),
            "answer_preview": [canonical_json(r["expected_final_answer"])[:80] for r in chosen],
            "sql": [r["expected_arguments"]["sql"] for r in chosen],
        }
    return rows, stats


def check(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    prompts, sigs, calls, sqls = _forbidden()
    bad_exec, bad_proj, bad_msg = [], [], []
    for r in rows:
        obs = _observation("database", r["expected_tool"], r["expected_arguments"],
                           {}, str(DB_PATH), str(ROOT / "data_phase2" / "fixtures" / "calendar.json"))
        if json.loads(obs) != json.loads(r["expected_observation"]):
            bad_exec.append(r["episode_id"])
        got = project_answer(json.loads(obs)["result"], r["answer_spec"])
        if got != r["expected_final_answer"]:
            bad_proj.append(r["episode_id"])
        if json.loads(r["messages"][4]["content"])["answer"] != r["expected_final_answer"]:
            bad_msg.append(r["episode_id"])
    res: Dict[str, Any] = {
        "gold_reexec_mismatch": bad_exec,
        "gold_project_mismatch": bad_proj,
        "message_answer_mismatch": bad_msg,
        "n_existing_files_scanned": len(_existing_jsonl()),
        "overlap_task_signature": [r["episode_id"] for r in rows if task_signature(r) in sigs],
        "overlap_prompt": [r["episode_id"] for r in rows if r["prompt"] in prompts],
        "overlap_call": [r["episode_id"] for r in rows if call_signature(r) in calls],
        "overlap_sql": [r["episode_id"] for r in rows
                        if str(r["expected_arguments"]["sql"]).strip() in sqls],
        "n_rows": len(rows),
        "types": dict(Counter(r["target_type"] for r in rows)),
        "internal_call_dups": len(rows) - len({call_signature(r) for r in rows}),
        "internal_sql_dups": len(rows) - len({r["expected_arguments"]["sql"] for r in rows}),
        "filter_top_sql_markers": [r["episode_id"] for r in rows
                                   if "ORDER BY" in r["expected_arguments"]["sql"].upper()
                                   and "LIMIT" in r["expected_arguments"]["sql"].upper()],
        "db_sha256": sha256_file(DB_PATH),
    }
    res["ok"] = not (bad_exec or bad_proj or bad_msg
                     or res["overlap_task_signature"] or res["overlap_prompt"]
                     or res["overlap_call"] or res["overlap_sql"]
                     or res["internal_call_dups"] or res["internal_sql_dups"]
                     or res["filter_top_sql_markers"]) and len(rows) == PER_BAND * len(BANDS)
    return res


def build() -> None:
    if (OUT / "final" / "FROZEN.json").exists():
        raise SystemExit("already frozen; refusing to rebuild")
    OUT.mkdir(parents=True, exist_ok=True)
    rows, stats = build_tasks()
    write_jsonl(OUT / "candidate" / "database_nontarget.jsonl", rows)
    chk = check(rows)
    chk["task_stats"] = stats
    write_json(OUT / "checks.json", chk)
    print(json.dumps({k: chk[k] for k in ("ok", "n_rows", "types") if k in chk}, indent=1))
    if not chk["ok"]:
        slim = {k: chk[k] for k in chk if k != "task_stats"}
        raise SystemExit("checks failed: %s" % json.dumps(slim)[:3000])


def freeze(note: str) -> None:
    fin = OUT / "final"
    if (fin / "FROZEN.json").exists():
        raise SystemExit("already frozen")
    rows = read_jsonl(OUT / "candidate" / "database_nontarget.jsonl")
    chk = check(rows)
    if not chk["ok"]:
        raise SystemExit("checks failed; not freezing")
    fin.mkdir(parents=True, exist_ok=True)
    write_jsonl(fin / "database_nontarget.jsonl", rows)
    h_rows, h_db = sha256_file(fin / "database_nontarget.jsonl"), sha256_file(DB_PATH)
    import hashlib
    write_json(fin / "FROZEN.json", {
        "version": VERSION, "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "files": {"database_nontarget": {"path": "final/database_nontarget.jsonl",
                                         "count": len(rows), "sha256": h_rows}},
        "fixture": {"path": "data_phase2/fixtures/toolbench.db", "sha256": h_db,
                    "note": "same Database fixture as training and nat v2; read-only"},
        "combined_sha256": hashlib.sha256((h_rows + h_db).encode()).hexdigest(),
        "types": chk["types"], "seeds": {"tasks": TASK_SEED},
        "scoring": "joint success (tool, exact SQL arguments, execution on toolbench.db, exact answer via project_answer / answers_equal); report overall and per band",
        "rationale": "Non-target Database exam for E3-B: if scores do not rise with independent target_db_filter_top count k, downgrade the S-curve to template coverage.",
        "bands": list(BANDS),
        "pilot_note": note,
        "rules": ["Evaluation only; never a training, replay, probe or selection input.",
                  "Not a rewrite of target_db_filter_top; no ORDER BY+LIMIT name lists.",
                  "Any change requires a new version string and hashes."],
    })
    write_json(OUT / "checks_frozen.json", chk)
    print("FROZEN", h_rows, "combined", hashlib.sha256((h_rows + h_db).encode()).hexdigest())


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
