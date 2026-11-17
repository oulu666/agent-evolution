"""[ext 2026-11-12 P1] E3-B2 GPU queue, steps 2-5 of E3B2_PREREG_20261112_ZH.md section 7.

Protocol-B1 everywhere (evaluation.batch_size = 1 -> sft.evaluate.generate_with_usage, greedy),
same evaluate_family as P0 (sft/evaluate.py unchanged since 2026-11-09).
Battery per checkpoint (frozen exams, hash-checked):
  natv2_database / natv2_file / natv2_python  (data_ext_e4/final_v2, 30 each)
  db_nontarget  (data_ext_p0_db_nontarget, 40; reused from P0 when P0 already has B1 for the ckpt)
  v3fix         (data_ext_p0_cal_titlecount, 30; reused from P0 for seed 08 start/none/ctrl_cal20)
  calendar_v3   (data_ext_cal_v3 final_v3, 150, frozen)
  p2_file / p2_python / p2_database (data_phase2/<f>/test.jsonl, 30 each; side evidence, prereg 6)
Queue order (resumable, one GPU job at a time, game / stop flag checked before every suite):
  seed 08: step 2 bridge [none tf25 tf50 b20_tf50 dose_db0 dose_db1 dose_db6 ctrl_cal10 ctrl_cal20]
           step 3 [stage_02_database (T0) stage_03_python stage_04_calendar(supplement)]
           extra  dose_db2/3/4 (natv2_database only, experiment B B1 curve), tf00 (natv2 + p2)
           step 5 experiment A seed 08: train e3b2_A_target_other, e3b2_A_target_dbbg -> full battery
  seeds 09, 10: steps 2-4 as above (experiment A for 09/10 is NOT queued: prereg 3.1 decides after 08)
Writes runs_ext_p1_b1/ (and runs_ext_e3b2/ via p1_e3b2) only.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple

from .utils import ensure_dir, read_json, read_jsonl, sha256_file, write_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs_ext_p1_b1"
EVAL = OUT / "evaluation"
STOP = ROOT / "logs_ext" / "p1_20261112.stop"
FIX2 = ROOT / "data_phase2" / "fixtures"
DB_PATH = FIX2 / "toolbench.db"
CAL_PATH = FIX2 / "calendar.json"
CV3_FIX = ROOT / "data_ext_cal_v3" / "fixtures" / "calendar_v3.json"
SEEDS = [20261108, 20261109, 20261110]
FULL = ["natv2_database", "natv2_file", "natv2_python", "db_nontarget", "v3fix", "calendar_v3",
        "p2_file", "p2_python", "p2_database"]
STEP2 = ["none", "tf25", "tf50", "b20_tf50", "dose_db0", "dose_db1", "dose_db6", "ctrl_cal10", "ctrl_cal20"]
STEP3 = ["stage_02_database", "stage_03_python", "stage_04_calendar"]
EXTRA = [("dose_db2", ["natv2_database"]), ("dose_db3", ["natv2_database"]), ("dose_db4", ["natv2_database"]),
         ("tf00", ["natv2_database", "natv2_file", "natv2_python", "p2_file", "p2_python", "p2_database"])]
E3B2_ARMS = ["e3b2_A_target_other", "e3b2_A_target_dbbg"]


def log(msg: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


# ------------------------------------------------------------------ paths
def ckpt_path(seed: int, arm: str) -> Path:
    if arm.startswith("stage_"):
        return ROOT / "runs_phase2" / ("A_seed%d" % seed) / "checkpoints" / arm
    if arm in ("none", "tf00", "tf25", "tf50"):
        return ROOT / "runs_ext_e4" / "branches" / ("A_seed%d_%s" % (seed, arm)) / "checkpoint"
    if arm.startswith("e3b2_"):
        return ROOT / "runs_ext_e3b2" / "branches" / ("A_seed%d_%s" % (seed, arm)) / "checkpoint"
    return ROOT / "runs_ext_e3" / "branches" / ("A_seed%d_%s" % (seed, arm)) / "checkpoint"


def label(seed: int, arm: str) -> str:
    return "A_seed%d_%s" % (seed, arm)


def p0_reference(seed: int, arm: str, suite: str) -> Optional[Path]:
    """B1 results already produced by P0 with the identical evaluator (reused, not rerun)."""
    if suite == "db_nontarget":
        p = ROOT / "runs_ext_p0_db_nontarget" / "evaluation" / label(seed, arm) / "database_nontarget" / "results.jsonl"
        return p if p.exists() else None
    if suite == "v3fix":
        a = "start" if arm == "stage_03_python" else arm
        p = ROOT / "runs_ext_p0_cal_titlecount" / "evaluation" / label(seed, a) / "title_count_v3fix" / "results.jsonl"
        return p if p.exists() else None
    return None


def results_path(seed: int, arm: str, suite: str) -> Path:
    ref = p0_reference(seed, arm, suite)
    if ref is not None:
        return ref
    return EVAL / label(seed, arm) / suite / "results.jsonl"


# ------------------------------------------------------------------ suites
_SUITE_CACHE: Dict[str, Tuple[List[Dict[str, Any]], str, str, str]] = {}


def suite_rows(name: str) -> Tuple[List[Dict[str, Any]], str, str, str]:
    """-> rows, db_path, calendar_path, sha256 of the row file (hash-checked against FROZEN files)."""
    if name in _SUITE_CACHE:
        return _SUITE_CACHE[name]
    if name.startswith("natv2_"):
        f = name[6:]
        fz = read_json(ROOT / "data_ext_e4" / "final_v2" / "FROZEN.json")
        p = ROOT / "data_ext_e4" / fz["files"][f]["path"]
        h = sha256_file(p)
        if h != fz["files"][f]["sha256"]:
            raise SystemExit("final_v2 %s hash changed" % f)
        res = (read_jsonl(p), str(DB_PATH), str(CAL_PATH), h)
    elif name == "calendar_v3":
        from .calv3_run import frozen_rows
        rows = frozen_rows()  # checks rows + fixture hashes
        res = (rows, str(DB_PATH), str(CV3_FIX), sha256_file(ROOT / "data_ext_cal_v3" / "final_v3" / "calendar_v3.jsonl"))
    elif name == "db_nontarget":
        from .p0_run import _db_rows
        rows = _db_rows()
        res = (rows, str(DB_PATH), str(CAL_PATH), sha256_file(ROOT / "data_ext_p0_db_nontarget" / "final" / "database_nontarget.jsonl"))
    elif name == "v3fix":
        from .p0_run import _cal_rows
        rows = _cal_rows()
        res = (rows, str(DB_PATH), str(CV3_FIX), sha256_file(ROOT / "data_ext_p0_cal_titlecount" / "final" / "title_count_v3fix.jsonl"))
    elif name.startswith("p2_"):
        f = name[3:]
        p = ROOT / "data_phase2" / f / "test.jsonl"
        res = (read_jsonl(p), str(DB_PATH), str(CAL_PATH), sha256_file(p))
    else:
        raise ValueError(name)
    _SUITE_CACHE[name] = res
    return res


# ------------------------------------------------------------------ safety
def check_safe() -> None:
    if STOP.exists():
        raise SystemExit("stop flag %s present; stopping" % STOP)
    from .p0_run import refuse_if_game
    refuse_if_game()


# ------------------------------------------------------------------ evaluation
def evaluate_ckpt(seed: int, arm: str, battery: List[str]) -> None:
    ck = ckpt_path(seed, arm)
    out = EVAL / label(seed, arm)
    todo = []
    for s in battery:
        if p0_reference(seed, arm, s) is not None:
            continue
        if (out / s / "stage_report.json").exists():
            continue
        todo.append(s)
    if not todo:
        log("skip eval %s (all suites done or reused from P0)" % label(seed, arm))
        return
    if not (ck / "adapter_config.json").exists():
        raise SystemExit("missing checkpoint %s" % ck)
    check_safe()
    from .replay_study import config_for
    from .sft.evaluate import evaluate_family, free_model, load_eval_model
    config = config_for("A", seed, batch_size=1)
    config["evaluation"]["batch_size"] = 1
    started = time.time()
    log("EVAL %s suites=%s ckpt=%s" % (label(seed, arm), todo, ck))
    model, tok = load_eval_model(config, str(ck))
    stage = {"name": "P1_B1_" + label(seed, arm), "index": 4, "adapter": str(ck)}
    try:
        for s in todo:
            check_safe()
            rows, db, cal, h = suite_rows(s)
            t0 = time.time()
            rep = evaluate_family(model, tok, rows, config, stage, out / s, db, cal)
            if rep["evaluation_protocol"]["batch_size"] != 1:
                raise SystemExit("protocol is not B1")
            write_json(out / s / "p1_meta.json", {"suite": s, "rows_sha256": h, "n": len(rows),
                                                 "checkpoint": str(ck),
                                                 "adapter_sha256": sha256_file(ck / "adapter_model.safetensors"),
                                                 "protocol": "Protocol-B1", "seconds": round(time.time() - t0, 1),
                                                 "finished": time.strftime("%Y-%m-%d %H:%M:%S %z")})
            log("  done %s %s n=%d %.1fs" % (label(seed, arm), s, len(rows), time.time() - t0))
    finally:
        free_model(model)
    log("EVAL done %s in %.1fs" % (label(seed, arm), time.time() - started))


def jobs(extra_e3b2_seeds: Tuple[int, ...] = ()) -> List[Tuple[str, int, str, List[str]]]:
    """(kind, seed, arm, battery) in queue order.

    Experiment A for seeds 09/10 is only appended when explicitly requested
    (--e3b2-seeds 20261109,20261110) after the seed-08 decision (prereg 3.1)."""
    out = []

    def seed_block(s):
        for a in STEP2:
            out.append(("eval", s, a, FULL))
        for a in STEP3:
            out.append(("eval", s, a, FULL))
        for a, b in EXTRA:
            out.append(("eval", s, a, b))

    seed_block(20261108)
    for a in E3B2_ARMS:
        out.append(("train", 20261108, a, []))
        out.append(("eval", 20261108, a, FULL))
    for s in (20261109, 20261110):
        seed_block(s)
    for s in extra_e3b2_seeds:
        for a in E3B2_ARMS:
            out.append(("train", s, a, []))
            out.append(("eval", s, a, FULL))
    return out


def run_queue(only_seed: Optional[int] = None, stop_after_e3b2_08: bool = False,
              extra_e3b2_seeds: Tuple[int, ...] = ()) -> None:
    ensure_dir(OUT)
    J = jobs(extra_e3b2_seeds)
    write_json(OUT / "queue.json", [{"kind": k, "seed": s, "arm": a, "battery": b} for k, s, a, b in J])
    for kind, seed, arm, battery in J:
        if only_seed and seed != only_seed:
            continue
        if kind == "train":
            from .p1_e3b2 import ckpt as e3b2_ckpt, train as e3b2_train
            if (e3b2_ckpt(seed, arm) / "train_summary.json").exists():
                log("skip train %s" % label(seed, arm))
                continue
            check_safe()
            log("TRAIN %s" % label(seed, arm))
            s = e3b2_train(seed, arm)
            log("TRAIN done %s steps=%s replay_tokens=%s seconds=%s" % (
                label(seed, arm), s.get("optimizer_steps"), s.get("replay_input_tokens"), s.get("duration_seconds")))
            continue
        evaluate_ckpt(seed, arm, battery)
        try:
            summarize(quiet=True)
        except Exception as exc:  # summary must never kill the queue
            log("WARN summarize failed: %r" % exc)
        if stop_after_e3b2_08 and arm == E3B2_ARMS[-1] and seed == 20261108:
            log("stop_after_e3b2_08 reached")
            return
    log("QUEUE COMPLETE")


# ------------------------------------------------------------------ scoring
def _pattern(row: Dict[str, Any]) -> str:
    from .coverage_patterns import classify_item
    return classify_item(row).pattern


def _ok(r: Dict[str, Any], suite: str) -> int:
    if suite == "natv2_file":
        from .e4_run import _calls_ok
        from .ext_rescore import last_line_correct
        return int(_calls_ok(r) and last_line_correct(r, lenient=True))  # official v2 lenient rule
    return int(bool(r.get("joint_success")))


def score_suite(seed: int, arm: str, suite: str) -> Optional[Dict[str, Any]]:
    p = results_path(seed, arm, suite)
    if not p.exists():
        return None
    res = read_jsonl(p)
    rows, _, _, _ = suite_rows(suite)
    if len(res) != len(rows):
        return None  # incomplete
    by_id = {r["episode_id"]: r for r in rows}
    pats = defaultdict(list)
    for r in res:
        row = by_id[r["episode_id"]]
        if suite == "calendar_v3":
            k = "cv3." + r["episode_id"].split("-")[2]
        else:
            k = _pattern(row)
        pats[k].append(_ok(r, suite))
    flags = [_ok(r, suite) for r in res]
    out = {"n": len(res), "score": sum(flags) / len(flags),
           "patterns": {k: round(sum(v) / len(v), 4) for k, v in sorted(pats.items())},
           "source": "P0 (reused B1)" if p0_reference(seed, arm, suite) else "P1",
           "results": str(p)}
    if suite == "natv2_file":
        out["strict_joint"] = sum(int(bool(r.get("joint_success"))) for r in res) / len(res)
    if suite == "v3fix":
        tool = [int(bool(r.get("tool_correct"))) for r in res]
        cond = [int(bool(r.get("final_correct"))) for r in res if r.get("tool_correct")]
        out["tool_accuracy"] = sum(tool) / len(tool)
        out["conditional_counting_accuracy"] = (sum(cond) / len(cond)) if cond else None
        out["n_tool_correct"] = len(cond)
        out["joint_success"] = out["score"]
    return out


def historical_b32(seed: int, arm: str, suite: str) -> Optional[Path]:
    fam = {"natv2_database": "database", "natv2_file": "file", "natv2_python": "python",
           "p2_file": "file", "p2_python": "python", "p2_database": "database"}.get(suite)
    grp = "natural_final_v2" if suite.startswith("natv2_") else "historical"
    if arm in ("none", "tf00", "tf25", "tf50"):
        if suite == "calendar_v3":
            p = ROOT / "runs_ext_calv3" / "evaluation" / ("E4_" + label(seed, arm)) / "calendar_v3" / "results.jsonl"
        elif fam:
            p = ROOT / "runs_ext_e4" / "evaluation" / label(seed, arm) / grp / fam / "results.jsonl"
        else:
            return None
    elif arm.startswith("stage_"):
        if suite == "calendar_v3" and arm == "stage_03_python":
            p = ROOT / "runs_ext_calv3" / "evaluation" / ("REF_" + label(seed, "start")) / "calendar_v3" / "results.jsonl"
        else:
            return None
    elif arm.startswith("e3b2_"):
        return None
    else:
        if suite == "calendar_v3":
            p = ROOT / "runs_ext_e3" / "evaluation" / label(seed, arm) / "calendar_v3" / "results.jsonl"
        elif fam:
            p = ROOT / "runs_ext_e3" / "evaluation" / label(seed, arm) / grp / fam / "results.jsonl"
        else:
            return None
    return p if p.exists() else None


def bridge(seed: int, arm: str, suite: str) -> Optional[Dict[str, Any]]:
    hp = historical_b32(seed, arm, suite)
    bp = results_path(seed, arm, suite)
    if hp is None or not bp.exists():
        return None
    h = {r["episode_id"]: _ok(r, suite) for r in read_jsonl(hp)}
    b = {r["episode_id"]: _ok(r, suite) for r in read_jsonl(bp)}
    if set(h) != set(b):
        return {"note": "episode sets differ", "n_hist": len(h), "n_b1": len(b)}
    up = sorted(k for k in b if b[k] and not h[k])
    down = sorted(k for k in b if h[k] and not b[k])
    return {"n": len(b), "b32": sum(h.values()) / len(h), "b1": sum(b.values()) / len(b),
            "b1_minus_b32": (sum(b.values()) - sum(h.values())) / len(b),
            "n_flip_b32_wrong_to_b1_right": len(up), "n_flip_b32_right_to_b1_wrong": len(down),
            "flips_up": up, "flips_down": down, "historical": str(hp)}


# ------------------------------------------------------------------ coverage ledger (CPU)
def coverage_ledger(seed: int, arm: str) -> Optional[Dict[str, Any]]:
    from .coverage_patterns import experience_diversity, pattern_coverage
    ck = ckpt_path(seed, arm)
    pp = ck / "replay_plan.json"
    if arm.startswith("stage_") or not pp.exists():
        return None
    plan = read_json(pp)
    raw = {}
    for f in ("file", "database", "python"):
        for r in read_jsonl(ROOT / "data_ext_e4" / "pool" / (f + ".jsonl")):
            raw[r["episode_id"]] = r
    for r in read_jsonl(ROOT / "data_phase2" / "calendar" / "train.jsonl"):
        raw[r["episode_id"]] = r
    items = plan.get("items", [])
    rows = [raw[i["episode_id"]] for i in items if i["episode_id"] in raw]
    if not rows:
        return {"n_slots": 0}
    cov = pattern_coverage(rows).to_dict()
    div = experience_diversity(rows).to_dict()
    tok = defaultdict(int)
    for i in items:
        tok[i["family"]] += int(i["input_tokens"])
    tgt_ids = sorted({i["episode_id"] for i in items if i.get("target")})
    return {"n_slots": cov["n_slots"], "n_unique": cov["n_unique"],
            "pattern_coverage": cov["coverage"], "n_official_covered": cov["n_official_covered"],
            "covered_patterns": sorted(k for k, v in cov["by_pattern"].items() if v["covered"]),
            "db_filter_cmp_top_slots": cov["by_pattern"].get("db.filter_cmp_top", {}).get("slots"),
            "db_filter_cmp_top_unique": cov["by_pattern"].get("db.filter_cmp_top", {}).get("unique"),
            "db_neighbour_slots": {p: cov["by_pattern"].get(p, {}).get("slots") for p in ("db.top_n", "db.filter_eq_count", "db.filter_eq_top")},
            "uniqueness": div["uniqueness"], "normalized_entropy": div["normalized_entropy"],
            "tokens_by_family": dict(tok), "target_ids": tgt_ids,
            "optimizer_steps": read_json(ck / "train_summary.json").get("optimizer_steps") if (ck / "train_summary.json").exists() else None}


# ------------------------------------------------------------------ summary
def _ms(vals: List[float]) -> Dict[str, Any]:
    v = [x for x in vals if x is not None]
    return {"n": len(v), "mean": round(mean(v), 4) if v else None,
            "sd": round(stdev(v), 4) if len(v) > 1 else None}


def summarize(quiet: bool = False) -> Path:
    from .coverage_patterns import forgetting_and_recovery
    arms = STEP2 + STEP3 + [a for a, _ in EXTRA] + E3B2_ARMS
    suites = FULL
    table: Dict[str, Dict[str, Any]] = {}
    for s in SEEDS:
        for a in arms:
            rec = {}
            for su in suites:
                sc = score_suite(s, a, su)
                if sc is not None:
                    rec[su] = sc
            if rec:
                table[label(s, a)] = rec
    bridges = {}
    for s in SEEDS:
        for a in arms:
            for su in ("natv2_database", "natv2_file", "natv2_python", "calendar_v3", "p2_file", "p2_python", "p2_database"):
                b = bridge(s, a, su)
                if b is not None:
                    bridges.setdefault(label(s, a), {})[su] = b
    # T0 / T1 / T2 per pattern (same exam, same protocol)
    t012 = {}
    for s in SEEDS:
        def pat(a, su, key):
            sc = table.get(label(s, a), {}).get(su)
            if sc is None:
                return None
            return sc["patterns"].get(key) if key else sc["score"]
        keys = [("natv2_database", "db.filter_cmp_top"), ("natv2_file", None), ("natv2_python", None),
                ("db_nontarget", None)]
        rows = {}
        for su, key in keys:
            for t2 in ("tf50", "dose_db6", "tf25"):
                k = "%s:%s|T2=%s" % (su, key or "overall", t2)
                rows[k] = forgetting_and_recovery(pat("stage_02_database", su, key), pat("none", su, key), pat(t2, su, key))
                rows[k]["start_stage_03"] = pat("stage_03_python", su, key)
                rows[k]["stage_04_calendar_supplement"] = pat("stage_04_calendar", su, key)
        t012[str(s)] = rows
    # experiment A (main metric natv2_database B1) and experiment B (dose curve)
    def main_metric(s, a):
        sc = table.get(label(s, a), {}).get("natv2_database")
        return None if sc is None else sc["score"]
    expA = {}
    for a in E3B2_ARMS + ["ctrl_cal10", "dose_db0", "dose_db1", "tf25", "none"]:
        vals = {str(s): main_metric(s, a) for s in SEEDS}
        expA[a] = {"per_seed": vals, **_ms(list(vals.values()))}
    doses = {}
    for k in (0, 1, 2, 3, 4, 6):
        vals = {str(s): main_metric(s, "dose_db%d" % k) for s in SEEDS}
        doses["dose_db%d" % k] = {"per_seed": vals, **_ms(list(vals.values()))}
    ledger = {}
    for s in SEEDS:
        for a in STEP2 + ["dose_db2", "dose_db3", "dose_db4", "tf00"] + E3B2_ARMS:
            try:
                L = coverage_ledger(s, a)
            except Exception as exc:
                L = {"error": repr(exc)}
            if L is not None:
                ledger[label(s, a)] = L
    done = sorted(table)
    summary = {"protocol": "Protocol-B1 (evaluation.batch_size=1, generate_with_usage, greedy)",
               "evaluate_py_sha256": sha256_file(ROOT / "fac_tinyagent" / "sft" / "evaluate.py"),
               "generated": time.strftime("%Y-%m-%d %H:%M:%S %z"),
               "evaluated_labels": done, "scores": table, "bridge_b1_vs_b32": bridges,
               "t0_t1_t2": t012, "experiment_A_main_metric": expA, "experiment_B_dose_curve_b1": doses,
               "coverage_ledger": ledger}
    ensure_dir(OUT)
    write_json(OUT / "summary.json", summary)
    write_tables(summary)
    if not quiet:
        log("summary written: %d labels" % len(done))
    return OUT / "summary.json"


def _f(x, nd=3):
    return "—" if x is None else ("%.*f" % (nd, x))


def write_tables(S: Dict[str, Any]) -> None:
    L = ["# P1 自动汇总表（Protocol-B1）", "", "生成：%s（Asia/Shanghai）。由 `fac_tinyagent/p1_run.py --phase summarize` 自动生成，数字只来自 results.jsonl。" % S["generated"], ""]
    cols = ["natv2_database", "natv2_file", "natv2_python", "db_nontarget", "calendar_v3", "p2_file", "p2_python", "p2_database"]
    L.append("## 1. 各 checkpoint 总分（Joint Success；natv2_file 为官方 v2 宽松规则）")
    L.append("")
    L.append("| checkpoint | " + " | ".join(cols) + " | v3fix 工具/条件计数/联合 |")
    L.append("|---" * (len(cols) + 2) + "|")
    for lab in S["evaluated_labels"]:
        r = S["scores"][lab]
        v = r.get("v3fix")
        vf = "—" if not v else "%s / %s / %s" % (_f(v["tool_accuracy"]), _f(v["conditional_counting_accuracy"]), _f(v["joint_success"]))
        L.append("| %s | " % lab + " | ".join(_f(r[c]["score"]) if c in r else "—" for c in cols) + " | %s |" % vf)
    L.append("")
    L.append("## 2. 非 target 五模式与 Calendar v3 五模式")
    L.append("")
    L.append("| checkpoint | db_nontarget 各模式 | calendar_v3 各类型 |")
    L.append("|---|---|---|")
    for lab in S["evaluated_labels"]:
        r = S["scores"][lab]
        a = r.get("db_nontarget", {}).get("patterns")
        b = r.get("calendar_v3", {}).get("patterns")
        L.append("| %s | %s | %s |" % (lab, ", ".join("%s %s" % (k, _f(v)) for k, v in a.items()) if a else "—",
                                       ", ".join("%s %s" % (k[4:], _f(v)) for k, v in b.items()) if b else "—"))
    L.append("")
    L.append("## 3. 协议桥接：同一 checkpoint、同一题集，B1 − 历史 B32")
    L.append("")
    L.append("| checkpoint | suite | B32 | B1 | 差 | B32错→B1对 | B32对→B1错 |")
    L.append("|---|---|---|---|---|---|---|")
    for lab, d in sorted(S["bridge_b1_vs_b32"].items()):
        for su, b in d.items():
            if "b1" not in b:
                continue
            L.append("| %s | %s | %s | %s | %+.3f | %d | %d |" % (lab, su, _f(b["b32"]), _f(b["b1"]), b["b1_minus_b32"],
                                                         b["n_flip_b32_wrong_to_b1_right"], b["n_flip_b32_right_to_b1_wrong"]))
    L.append("")
    L.append("## 4. 实验 A 主指标（natv2_database B1）与实验 B 剂量曲线（B1）")
    L.append("")
    L.append("| 臂 | 08 | 09 | 10 | 均值 | SD |")
    L.append("|---|---|---|---|---|---|")
    for name, blk in list(S["experiment_A_main_metric"].items()) + list(S["experiment_B_dose_curve_b1"].items()):
        ps = blk["per_seed"]
        L.append("| %s | %s | %s | %s | %s | %s |" % (name, _f(ps.get("20261108")), _f(ps.get("20261109")), _f(ps.get("20261110")),
                                                    _f(blk["mean"]), _f(blk["sd"])))
    L.append("")
    L.append("## 5. T0/T1/T2（同题集 B1）。T0=stage_02_database，T1=E4 none")
    L.append("")
    L.append("| 种子 | 指标 | T0 | stage_03 | T1 | T2 | T0−T1 | T2−T1 | stage_04(参考) |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for s, rows in S["t0_t1_t2"].items():
        for k, v in rows.items():
            L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (s[-2:], k, _f(v["skill_t0"]), _f(v["start_stage_03"]), _f(v["skill_t1"]),
                                                                  _f(v["skill_t2"]), _f(v["drop_t0_t1"]), _f(v["recovery_t1_t2"]),
                                                                  _f(v["stage_04_calendar_supplement"])))
    L.append("")
    L.append("## 6. 复习池 Coverage / Diversity（只读计划，CPU）")
    L.append("")
    L.append("| 臂 | slots | unique | filter_cmp_top slots/unique | 近邻 slots(top_n, filter_eq_count, filter_eq_top) | Pattern Coverage | 唯一率 | 归一熵 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for lab, c in sorted(S["coverage_ledger"].items()):
        if "n_unique" not in c:
            continue
        nb = c.get("db_neighbour_slots", {})
        L.append("| %s | %s | %s | %s/%s | %s | %s | %s | %s |" % (lab, c["n_slots"], c["n_unique"], c.get("db_filter_cmp_top_slots"),
                                                             c.get("db_filter_cmp_top_unique"),
                                                             ", ".join(str(nb.get(p)) for p in ("db.top_n", "db.filter_eq_count", "db.filter_eq_top")),
                                                             _f(c.get("pattern_coverage")), _f(c.get("uniqueness")), _f(c.get("normalized_entropy"))))
    (OUT / "summary_tables_ZH.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["queue", "summarize", "list"], required=True)
    ap.add_argument("--only-seed", type=int, default=None)
    ap.add_argument("--stop-after-e3b2-08", action="store_true")
    ap.add_argument("--e3b2-seeds", default="", help="append experiment A train+eval for these seeds (e.g. 20261109,20261110)")
    a = ap.parse_args()
    extra = tuple(int(x) for x in a.e3b2_seeds.split(",") if x)
    if a.phase == "list":
        for j in jobs(extra):
            print(j[0], j[1], j[2], ",".join(j[3]))
        return
    if a.phase == "summarize":
        summarize()
        return
    run_queue(only_seed=a.only_seed, stop_after_e3b2_08=a.stop_after_e3b2_08, extra_e3b2_seeds=extra)


if __name__ == "__main__":
    main()
