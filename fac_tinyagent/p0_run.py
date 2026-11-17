"""[ext 2026-11-12] P0 runner: batched-eval consistency, Database non-target
curve, Calendar title-count v3fix short validation.

Read-only on existing checkpoints and frozen exams. Writes only to
data_ext_p0_* and runs_ext_p0_*. Does not change evaluate.py defaults;
every call sets evaluation.batch_size explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .replay_study import config_for
from .utils import ensure_dir, read_json, read_jsonl, sha256_file, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
DATA_BATCH = ROOT / "data_ext_p0_batched"
DATA_DB = ROOT / "data_ext_p0_db_nontarget"
DATA_CAL = ROOT / "data_ext_p0_cal_titlecount"
RUN_BATCH = ROOT / "runs_ext_p0_batched"
RUN_DB = ROOT / "runs_ext_p0_db_nontarget"
RUN_CAL = ROOT / "runs_ext_p0_cal_titlecount"
FIX_PHASE2 = ROOT / "data_phase2" / "fixtures"
FIX_CV3 = ROOT / "data_ext_cal_v3" / "fixtures" / "calendar_v3.json"
DB_PATH = FIX_PHASE2 / "toolbench.db"
CAL_PATH = FIX_PHASE2 / "calendar.json"

SEEDS = (20261108, 20261109, 20261110)
DOSE_ARMS = ("dose_db0", "dose_db1", "dose_db2", "dose_db3", "dose_db4", "dose_db6")
BATCH_SIZES = (1, 2, 4, 32)


def log(msg: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def _decode_cmd_output(raw: Optional[bytes]) -> str:
    """Decode tasklist bytes. Try UTF-8, then common Windows code pages, then replace."""
    if not raw:
        return ""
    for enc in ("utf-8", "gbk", "cp936", "mbcs", "cp1252"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def game_running() -> Optional[bool]:
    """Return whether r5apex is running.

    True: the game process was found.
    False: tasklist succeeded and the game is not running.
    None: the check itself failed (nonzero exit, timeout, decode/OS error).
          Callers must treat None as unsafe and must not start GPU work.
    """
    try:
        import subprocess
        r = subprocess.run(
            ["/mnt/c/Windows/System32/tasklist.exe"],
            capture_output=True, text=False, timeout=30)
        if r.returncode != 0:
            err = _decode_cmd_output(r.stderr)
            log("ERROR tasklist failed rc=%s err=%s" % (r.returncode, (err or "")[:300]))
            return None
        text = _decode_cmd_output(r.stdout)
        return "r5apex" in text.lower()
    except Exception as exc:
        log("ERROR tasklist failed: %s" % exc)
        return None


def refuse_if_game() -> None:
    status = game_running()
    if status is True:
        raise SystemExit("r5apex is running; stopping all GPU work")
    if status is None:
        raise SystemExit("tasklist check failed; refusing to start GPU work")


def build_probe() -> None:
    """Freeze a 44-item consistency probe: nat v2 old tools + Calendar v3."""
    if (DATA_BATCH / "FROZEN.json").exists():
        log("probe already frozen; skip build")
        return
    ensure_dir(DATA_BATCH)
    groups = []
    # nat v2: 8 per family, stride 4 over 30
    for family in ("file", "database", "python"):
        src = ROOT / "data_ext_e4" / "final_v2" / (family + ".jsonl")
        rows = read_jsonl(src)
        picked = [rows[i] for i in range(0, 30, 4)[:8]]
        if len(picked) != 8:
            picked = rows[:8]
        for r in picked:
            r = dict(r)
            r["p0_probe_source"] = "natural_final_v2/%s" % family
            r["p0_fixture"] = "phase2"
            groups.append(r)
    # calendar v3: 4 per sub-skill, stride 8 over 30
    cv3 = read_jsonl(ROOT / "data_ext_cal_v3" / "final_v3" / "calendar_v3.jsonl")
    by = defaultdict(list)
    for r in cv3:
        kind = r["episode_id"].split("-")[2]
        by[kind].append(r)
    for kind in ("free_latest", "locations", "attendee_count", "search_count", "last_end"):
        rows = by[kind]
        picked = [rows[i] for i in (0, 8, 16, 24) if i < len(rows)]
        for r in picked:
            r = dict(r)
            r["p0_probe_source"] = "calendar_v3/%s" % kind
            r["p0_fixture"] = "calendar_v3"
            groups.append(r)
    write_jsonl(DATA_BATCH / "probe.jsonl", groups)
    h = sha256_file(DATA_BATCH / "probe.jsonl")
    write_json(DATA_BATCH / "FROZEN.json", {
        "version": "p0_batched_probe_v1",
        "count": len(groups),
        "sha256": h,
        "by_source": {k: sum(1 for r in groups if r["p0_probe_source"] == k)
                      for k in sorted({r["p0_probe_source"] for r in groups})},
        "note": "Read-only copies of already frozen exam items, for batch-size consistency only.",
    })
    log("wrote probe n=%d sha256=%s" % (len(groups), h))


def _suites_from_probe(rows: List[Dict[str, Any]]) -> List[Tuple[str, List[Dict[str, Any]], str, str]]:
    """Group probe rows by fixture so evaluate_family gets a consistent calendar/db."""
    out = []
    phase2 = [r for r in rows if r.get("p0_fixture") == "phase2"]
    by_fam = defaultdict(list)
    for r in phase2:
        by_fam[r["tool_family"]].append(r)
    for fam, items in by_fam.items():
        out.append(("natv2_" + fam, items, str(DB_PATH), str(CAL_PATH)))
    cv3 = [r for r in rows if r.get("p0_fixture") == "calendar_v3"]
    if cv3:
        out.append(("calendar_v3", cv3, str(DB_PATH), str(FIX_CV3)))
    return out


def _eval_one(ckpt: Path, seed: int, batch_size: int, suites, out_root: Path,
              tag: str) -> Dict[str, Any]:
    from .sft.evaluate import evaluate_family, free_model, load_eval_model
    refuse_if_game()
    config = config_for("A", seed, batch_size=1)
    config["evaluation"]["batch_size"] = int(batch_size)
    started = time.time()
    model, tok = load_eval_model(config, str(ckpt))
    stage = {"name": tag, "index": 4, "adapter": str(ckpt)}
    reports = {}
    try:
        for name, rows, db, cal in suites:
            dest = out_root / name
            if (dest / "stage_report.json").exists():
                log("skip existing %s" % dest)
                reports[name] = read_json(dest / "stage_report.json")
                continue
            reports[name] = evaluate_family(model, tok, rows, config, stage, dest, db, cal)
    finally:
        free_model(model)
    return {"duration_seconds": round(time.time() - started, 2),
            "batch_size": batch_size, "reports": {k: {
                "duration_seconds": v.get("duration_seconds"),
                "peak_gpu_gb": v.get("peak_gpu_gb"),
                "evaluation_protocol": v.get("evaluation_protocol"),
                "metrics": v.get("metrics"),
            } for k, v in reports.items()}}


def _load_results(out_root: Path) -> Dict[str, Dict[str, Any]]:
    items = {}
    for path in out_root.glob("*/results.jsonl"):
        for r in read_jsonl(path):
            items[r["episode_id"]] = r
    return items


def _compare(ref: Dict[str, Dict[str, Any]], other: Dict[str, Dict[str, Any]],
             label: str) -> Dict[str, Any]:
    ids = sorted(ref)
    missing = [i for i in ids if i not in other]
    extra = [i for i in other if i not in ref]
    fields = ("tool_call_raw", "answer_raw", "joint_success", "tool_correct",
              "arguments_correct", "execution_success", "final_correct",
              "predicted_tool", "predicted_answer")
    mismatches = []
    text_mismatch = 0
    score_mismatch = 0
    for eid in ids:
        if eid not in other:
            continue
        a, b = ref[eid], other[eid]
        diff = {f: {"ref": a.get(f), "other": b.get(f)} for f in fields if a.get(f) != b.get(f)}
        if not diff:
            continue
        rec = {"episode_id": eid, "diff_fields": sorted(diff), "diff": diff,
               "source": a.get("p0_probe_source") or a.get("template_id") or a.get("skill_labels")}
        mismatches.append(rec)
        if any(f in diff for f in ("tool_call_raw", "answer_raw")):
            text_mismatch += 1
        if any(f in diff for f in ("joint_success", "tool_correct", "arguments_correct",
                                   "execution_success", "final_correct")):
            score_mismatch += 1
    n = len(ids)
    return {
        "label": label, "n": n, "missing": missing, "extra": extra,
        "n_mismatch_any": len(mismatches),
        "n_text_mismatch": text_mismatch,
        "n_score_mismatch": score_mismatch,
        "text_agree": (n - text_mismatch) / n if n else None,
        "score_agree": (n - score_mismatch) / n if n else None,
        "exact_agree": (n - len(mismatches)) / n if n else None,
        "examples": mismatches[:8],
        "mismatch_ids": [m["episode_id"] for m in mismatches],
    }


def run_batched(force: bool = False) -> Path:
    build_probe()
    rows = read_jsonl(DATA_BATCH / "probe.jsonl")
    suites = _suites_from_probe(rows)
    ckpt = ROOT / "runs_ext_e4" / "branches" / "A_seed20261108_tf50" / "checkpoint"
    if not (ckpt / "train_summary.json").exists() and not any(ckpt.glob("*.safetensors")) and not (ckpt / "adapter_config.json").exists():
        raise SystemExit("missing checkpoint: %s" % ckpt)
    seed = 20261108
    meta = {"checkpoint": str(ckpt), "seed": seed, "n_items": len(rows),
            "batch_sizes": list(BATCH_SIZES), "started": time.strftime("%Y-%m-%d %H:%M:%S %z")}
    runs_meta = {}
    for bs in BATCH_SIZES:
        out = RUN_BATCH / ("bs%d" % bs)
        if (out / "EVAL_DONE").exists() and not force:
            log("skip batched bs=%d (EVAL_DONE)" % bs)
            runs_meta[str(bs)] = {"skipped": True, "out": str(out)}
            continue
        log("batched eval bs=%d n=%d ckpt=%s" % (bs, len(rows), ckpt))
        refuse_if_game()
        info = _eval_one(ckpt, seed, bs, suites, out, "P0_batched_bs%d" % bs)
        (out / "EVAL_DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
        write_json(out / "run_meta.json", info)
        runs_meta[str(bs)] = info
        log("done bs=%d duration=%.1fs" % (bs, info["duration_seconds"]))
    ref = _load_results(RUN_BATCH / "bs1")
    # attach probe source for nicer diffs
    src = {r["episode_id"]: r.get("p0_probe_source") for r in rows}
    for item in ref.values():
        item["p0_probe_source"] = src.get(item["episode_id"])
    comparisons = []
    for bs in BATCH_SIZES:
        if bs == 1:
            continue
        other = _load_results(RUN_BATCH / ("bs%d" % bs))
        for item in other.values():
            item["p0_probe_source"] = src.get(item["episode_id"])
        comparisons.append(_compare(ref, other, "bs%d_vs_bs1" % bs))
    # also compare bs32 against historical E4 results for overlapping items
    hist = {}
    ev = ROOT / "runs_ext_e4" / "evaluation" / "A_seed20261108_tf50"
    for fam in ("file", "database", "python"):
        p = ev / "natural_final_v2" / fam / "results.jsonl"
        if p.exists():
            for r in read_jsonl(p):
                hist[r["episode_id"]] = r
    cv = ROOT / "runs_ext_calv3" / "evaluation" / "E4_A_seed20261108_tf50" / "calendar_v3" / "results.jsonl"
    if cv.exists():
        for r in read_jsonl(cv):
            hist[r["episode_id"]] = r
    overlap_ref = {k: v for k, v in ref.items() if k in hist}
    overlap_hist = {k: hist[k] for k in overlap_ref}
    comparisons.append(_compare(overlap_hist, overlap_ref, "bs1_vs_historical_e4_tf50"))
    bs32 = _load_results(RUN_BATCH / "bs32")
    overlap_32 = {k: v for k, v in bs32.items() if k in hist}
    comparisons.append(_compare(overlap_hist, overlap_32, "bs32_vs_historical_e4_tf50"))
    summary = {"meta": meta, "runs": runs_meta, "comparisons": comparisons,
               "finished": time.strftime("%Y-%m-%d %H:%M:%S %z")}
    write_json(RUN_BATCH / "comparison.json", summary)
    log("batched comparison written")
    for c in comparisons:
        log("  %s exact=%.3f text=%.3f score=%.3f mismatches=%d" % (
            c["label"], c["exact_agree"] or -1, c["text_agree"] or -1,
            c["score_agree"] or -1, c["n_mismatch_any"]))
    return RUN_BATCH / "comparison.json"


def _db_rows() -> List[Dict[str, Any]]:
    path = DATA_DB / "final" / "database_nontarget.jsonl"
    frozen = read_json(DATA_DB / "final" / "FROZEN.json")
    if sha256_file(path) != frozen["files"]["database_nontarget"]["sha256"]:
        raise SystemExit("DB nontarget hash mismatch")
    return read_jsonl(path)


def _cal_rows() -> List[Dict[str, Any]]:
    path = DATA_CAL / "final" / "title_count_v3fix.jsonl"
    frozen = read_json(DATA_CAL / "final" / "FROZEN.json")
    if sha256_file(path) != frozen["files"]["title_count_v3fix"]["sha256"]:
        raise SystemExit("title-count v3fix hash mismatch")
    return read_jsonl(path)


def _ckpt_e3(seed: int, arm: str) -> Path:
    return ROOT / "runs_ext_e3" / "branches" / ("A_seed%d_%s" % (seed, arm)) / "checkpoint"


def _ckpt_e4(seed: int, arm: str) -> Path:
    return ROOT / "runs_ext_e4" / "branches" / ("A_seed%d_%s" % (seed, arm)) / "checkpoint"


def recommended_batch_size() -> int:
    """Use 32 iff comparison says bs32 matches bs1 exactly; else 1."""
    path = RUN_BATCH / "comparison.json"
    if not path.exists():
        return 1
    data = read_json(path)
    for c in data.get("comparisons", []):
        if c["label"] == "bs32_vs_bs1" and c.get("n_mismatch_any") == 0:
            return 32
    return 1


def run_db(seeds: Tuple[int, ...] = SEEDS, batch_size: Optional[int] = None) -> Path:
    rows = _db_rows()
    bs = int(batch_size or recommended_batch_size())
    suites = [("database_nontarget", rows, str(DB_PATH), str(CAL_PATH))]
    jobs = []
    for seed in seeds:
        jobs.append((seed, "none", _ckpt_e4(seed, "none")))
        for arm in DOSE_ARMS:
            jobs.append((seed, arm, _ckpt_e3(seed, arm)))
    results = []
    for seed, arm, ckpt in jobs:
        out = RUN_DB / "evaluation" / ("A_seed%d_%s" % (seed, arm))
        if (out / "EVAL_DONE").exists():
            log("skip db eval %s %s" % (seed, arm))
        else:
            if not (ckpt / "adapter_config.json").exists():
                raise SystemExit("missing ckpt %s" % ckpt)
            log("DB nontarget eval seed=%d arm=%s bs=%d n=%d" % (seed, arm, bs, len(rows)))
            refuse_if_game()
            info = _eval_one(ckpt, seed, bs, suites, out, "P0_db_s%d_%s" % (seed, arm))
            write_json(out / "run_meta.json", info)
            (out / "EVAL_DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
            log("done %s %s in %.1fs" % (seed, arm, info["duration_seconds"]))
        items = read_jsonl(out / "database_nontarget" / "results.jsonl")
        by_band = defaultdict(list)
        for r in items:
            band = r["episode_id"].split("-")[2]
            by_band[band].append(int(bool(r.get("joint_success"))))
        rec = {
            "seed": seed, "arm": arm,
            "overall": sum(int(bool(r.get("joint_success"))) for r in items) / len(items),
            "n": len(items),
            "bands": {b: sum(v) / len(v) for b, v in sorted(by_band.items())},
            "batch_size": bs,
        }
        results.append(rec)
        log("  score %s %s overall=%.3f bands=%s" % (seed, arm, rec["overall"], rec["bands"]))
    write_json(RUN_DB / "summary.json", {"results": results, "batch_size": bs,
                                         "finished": time.strftime("%Y-%m-%d %H:%M:%S %z")})
    return RUN_DB / "summary.json"


def run_cal(batch_size: Optional[int] = None) -> Path:
    rows = _cal_rows()
    bs = int(batch_size or recommended_batch_size())
    suites = [("title_count_v3fix", rows, str(DB_PATH), str(FIX_CV3))]
    jobs = [
        (20261108, "start", ROOT / "runs_phase2" / "A_seed20261108" / "checkpoints" / "stage_03_python"),
        (20261108, "none", _ckpt_e4(20261108, "none")),
        (20261108, "ctrl_cal20", _ckpt_e3(20261108, "ctrl_cal20")),
    ]
    results = []
    for seed, arm, ckpt in jobs:
        out = RUN_CAL / "evaluation" / ("A_seed%d_%s" % (seed, arm))
        if (out / "EVAL_DONE").exists():
            log("skip cal v3fix eval %s" % arm)
        else:
            if not (ckpt / "adapter_config.json").exists():
                raise SystemExit("missing ckpt %s" % ckpt)
            log("title-count v3fix eval arm=%s bs=%d n=%d" % (arm, bs, len(rows)))
            refuse_if_game()
            info = _eval_one(ckpt, seed, bs, suites, out, "P0_calfix_s%d_%s" % (seed, arm))
            write_json(out / "run_meta.json", info)
            (out / "EVAL_DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
            log("done %s in %.1fs" % (arm, info["duration_seconds"]))
        items = read_jsonl(out / "title_count_v3fix" / "results.jsonl")
        by = defaultdict(list)
        for r in items:
            band = "day_count" if "day_count" in r["episode_id"] else "global_count"
            by[band].append(int(bool(r.get("joint_success"))))
            by["tool"].append(int(bool(r.get("tool_correct"))))
            by["final"].append(int(bool(r.get("final_correct"))))
        def _rate(key):
            xs = by.get(key) or []
            return (sum(xs) / len(xs)) if xs else None
        rec = {
            "seed": seed, "arm": arm,
            "overall": sum(int(bool(r.get("joint_success"))) for r in items) / len(items),
            "n": len(items),
            "global_count": _rate("global_count"),
            "day_count": _rate("day_count"),
            "tool": _rate("tool"),
            "final": _rate("final"),
            "batch_size": bs,
        }
        results.append(rec)
        def _fmt(value: Optional[float]) -> float:
            return -1 if value is None else value
        log("  score %s overall=%.3f day=%.3f tool=%.3f" % (
            arm, rec["overall"], _fmt(rec["day_count"]), _fmt(rec["tool"])))
    write_json(RUN_CAL / "summary.json", {"results": results, "batch_size": bs,
                                          "finished": time.strftime("%Y-%m-%d %H:%M:%S %z")})
    return RUN_CAL / "summary.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["build-probe", "batched", "db", "cal", "all-gpu"],
                    required=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--batch-size", type=int, default=None)
    ap.add_argument("--seeds", default="20261108,20261109,20261110")
    a = ap.parse_args()
    if a.phase == "build-probe":
        build_probe()
        return
    if a.phase == "batched":
        run_batched(force=a.force)
        return
    if a.phase == "db":
        seeds = tuple(int(x) for x in a.seeds.split(",") if x)
        run_db(seeds=seeds, batch_size=a.batch_size)
        return
    if a.phase == "cal":
        run_cal(batch_size=a.batch_size)
        return
    if a.phase == "all-gpu":
        run_batched(force=a.force)
        run_cal(batch_size=a.batch_size)
        seeds = tuple(int(x) for x in a.seeds.split(",") if x)
        run_db(seeds=seeds, batch_size=a.batch_size)


if __name__ == "__main__":
    main()
