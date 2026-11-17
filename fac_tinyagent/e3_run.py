"""[ext 2026-11-11] E3: budget sweep + Database dose + compute-matched Calendar-only control.

Same setting as E4 (A order stage 3 -> 4, Calendar new, File/Database/Python old, batch 1,
grad-acc 8, 2 epochs, lr 1e-4, replay in the second half, monitor-v2 probes, clean E4 pools).
Every E3 branch starts from the *E4 shared midpoint prefix* of its seed (copied read-only
into runs_ext_e3/prefixes/ and hash-verified), so E3 arms are paired with the E4 10% arms
and E4 none at the exact same midpoint weights / optimizer state.
  sweep   b05_* / b20_*: replay_train.train_replay_stage unchanged, replay_ratio 0.05 / 0.20
  dose    dose_db<k>:   e3_train hook, frozen plan data_ext_e3/plans (see e3_data)
  control ctrl_cal10:   e3_train hook, 10% extra Calendar-only micro-steps, no old-tool replay
Evaluation per trained model (one model load): historical tests (4 tools) + natural final
v2 (4 tools, frozen 5dcc7d78...) + Calendar v3 (frozen 2b203ab5...).
Reused (read-only): runs_ext_e4 (b10_tf00/b10_tf25/b10_tf50/none) + runs_ext_calv3 E4_* evals.
Outputs: runs_ext_e3/ (smoke: runs_ext_e3_smoke/).
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple

from . import e3_data as D
from .e4_run import (CALENDAR_PATH, DB_PATH, FAMILIES, OLD, frozen_check, item_scores, leakage_guard,
                     start_adapter, suites)
from .calv3_run import FIXTURE as CV3_FIXTURE, TYPES as CV3_TYPES, _kind as cv3_kind, frozen_rows as cv3_rows
from .replay_study import config_for
from .research_data import task_signature
from .utils import canonical_json, ensure_dir, read_json, read_jsonl, sha256_file, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
E4D = ROOT / "data_ext_e4"
E3D = ROOT / "data_ext_e3"
E4R = ROOT / "runs_ext_e4"
CV3R = ROOT / "runs_ext_calv3"
MV2 = ROOT / "data_ext_monitor_v2"
SEEDS = D.SEEDS
SMOKE_RATIO = 0.30  # smoke only: 16 new rows give a tiny budget, so use 30% to exercise every plan part


def out_root(smoke: bool) -> Path:
    import os
    return ROOT / (os.environ.get("E3_SMOKE_DIR", "runs_ext_e3_smoke") if smoke else "runs_ext_e3")


def branch_dir(seed: int, arm: str, smoke: bool) -> Path:
    return out_root(smoke) / "branches" / ("A_seed%d_%s" % (seed, arm))


def eval_dir(seed: int, arm: str, smoke: bool) -> Path:
    return out_root(smoke) / "evaluation" / ("A_seed%d_%s" % (seed, arm))


def prefix_dir(seed: int, smoke: bool) -> Path:
    return out_root(smoke) / "prefixes" / ("A_seed%d" % seed)


# ---------------------------------------------------------------- guards
def guards() -> None:
    frozen_check()  # final v2 + E4 pools
    fz2 = read_json(E4D / "final_v2" / "FROZEN.json")["combined_sha256"]
    if fz2 != D.FINAL_V2_HASH:
        raise SystemExit("final_v2 combined hash mismatch")
    cv3_rows()  # Calendar v3 rows + fixture hashes
    if read_json(D.CV3 / "final_v3" / "FROZEN.json")["combined_sha256"] != D.CALV3_HASH:
        raise SystemExit("calendar v3 combined hash mismatch")
    man = read_json(E3D / "manifest.json")
    for name, h in man["plan_files"].items():
        if sha256_file(E3D / "plans" / name) != h:
            raise SystemExit("data_ext_e3 plan changed: %s" % name)


def v3_leakage_guard(rows: List[Dict[str, Any]]) -> None:
    v3 = cv3_rows()
    sig = {task_signature(r) for r in v3}
    msg = {canonical_json(r["messages"]) for r in v3}
    bad = [r["episode_id"] for r in rows if task_signature(r) in sig or canonical_json(r["messages"]) in msg]
    if bad:
        raise SystemExit("calendar v3 leaks into training inputs: %s" % bad[:5])


# ---------------------------------------------------------------- prep
def prep() -> None:
    """Copy E4 midpoint prefixes (read-only source) into runs_ext_e3/prefixes and verify."""
    for s in SEEDS:
        src, dst = E4R / "prefixes" / ("A_seed%d" % s), prefix_dir(s, False)
        m = read_json(src / "manifest.json")
        if (dst / "manifest.json").exists():
            ok = sha256_file(dst / "training_state.pt") == m["state_sha256"] and read_json(dst / "manifest.json") == m
            print("prefix", s, "present, verified" if ok else "PRESENT BUT DIFFERENT", flush=True)
            if not ok:
                raise SystemExit(2)
            continue
        if sha256_file(src / "training_state.pt") != m["state_sha256"]:
            raise SystemExit("E4 prefix %d hash mismatch" % s)
        ensure_dir(dst)
        tmp = dst / "training_state.pt.tmp"
        shutil.copyfile(src / "training_state.pt", tmp)
        if sha256_file(tmp) != m["state_sha256"]:
            raise SystemExit("copy hash mismatch %d" % s)
        tmp.rename(dst / "training_state.pt")
        shutil.copyfile(src / "manifest.json", dst / "manifest.json")
        print("prefix", s, "copied + verified", m["state_sha256"][:12], flush=True)


# ---------------------------------------------------------------- train
def _smoke_inputs() -> Dict[str, str]:
    base = ensure_dir(out_root(True) / "inputs")
    new = base / "calendar_train16.jsonl"
    if not new.exists():
        write_jsonl(new, read_jsonl(ROOT / "data_phase2" / "calendar" / "train.jsonl")[:16])
    res = {"new": str(new)}
    for f in OLD:
        p = base / ("probe_%s.jsonl" % f)
        if not p.exists():
            write_jsonl(p, read_jsonl(MV2 / (f + ".jsonl"))[::8])
        res["probe_" + f] = str(p)
    return res


def _override(seed: int, arm: str, spec: Dict[str, Any], smoke: bool):
    frozen = None if smoke else read_json(E3D / "plans" / ("A_seed%d_%s.json" % (seed, arm)))

    def fn(pools, extra_pools, budget, seed):  # noqa: shadow: seed = config seed + 104729
        if spec["kind"] == "dose":
            plan = D.dose_plan(pools, budget, seed, spec["k"] if not smoke else min(spec["k"], 2), spec["draw"])
        else:
            plan = D.control_plan(extra_pools, budget, seed,
                                  n_target=None if smoke else frozen["e3_plan"]["n_target"], ratio=spec["ratio"])
        if frozen is not None and D.plan_signature(plan) != D.plan_signature(frozen):
            raise RuntimeError("runtime E3 plan differs from frozen data_ext_e3 plan (%s)" % arm)
        print("E3 plan", arm, plan["e3_plan"].get("kind"), "tokens", plan["actual_input_tokens"], "/", budget,
              "targets", plan["target_samples_by_family"], flush=True)
        return plan
    return fn


def train(seed: int, arm: str, smoke: bool) -> Dict[str, Any]:
    from .replay_train import train_replay_stage
    from .e3_train import train_replay_stage_e3
    spec = D.ARMS[arm]
    guards()
    target_ids = read_json(E4D / "manifest.json")["target_ids"]
    config = config_for("A", seed, batch_size=32)
    stage = dict(config["stages"][4], index=4)
    new_path = str(ROOT / "data_phase2" / "calendar" / "train.jsonl")
    probes = {f: str(MV2 / (f + ".jsonl")) for f in OLD}
    ratio = spec["ratio"]
    if smoke:
        config["training"]["num_epochs"] = 1
        inp = _smoke_inputs()
        new_path = inp["new"]
        probes = {f: inp["probe_" + f] for f in OLD}
        ratio = SMOKE_RATIO
    pools = {f: str(E4D / "pool" / (f + ".jsonl")) for f in OLD}
    rows = read_jsonl(new_path) + [r for p in pools.values() for r in read_jsonl(p)] \
        + [r for p in probes.values() for r in read_jsonl(p)]
    leakage_guard(rows)
    v3_leakage_guard(rows)
    pdir = prefix_dir(seed, smoke)
    if not smoke and not (pdir / "manifest.json").exists():
        raise SystemExit("missing E3 prefix copy %s; run --phase prep" % pdir)
    run = branch_dir(seed, arm, smoke)
    ckpt = run / "checkpoint"
    if (ckpt / "train_summary.json").exists():
        print("skip train", run.name, flush=True)
        return read_json(ckpt / "train_summary.json")
    if run.exists():
        aside = run.parent / (run.name + "_partial_%d" % int(time.time()))
        print("moving partial run aside:", aside, flush=True)
        shutil.move(str(run), str(aside))
    print("train", run.name, spec, "ratio", ratio, flush=True)
    common = dict(config=config, stage=stage, train_path=new_path, old_train_paths=pools, probe_paths=probes,
                  previous_adapter=str(start_adapter(seed)), output_dir=str(ckpt), db_path=str(DB_PATH),
                  calendar_path=str(CALENDAR_PATH), mode="targeted", replay_ratio=ratio, uniform_floor=0.2,
                  prefix_dir=str(pdir), target_ids=target_ids,
                  target_family_weights={f: 1.0 / len(OLD) for f in OLD})
    if spec["kind"] == "sweep":
        s = train_replay_stage(target_fraction=spec["tf"], **common)
    else:
        s = train_replay_stage_e3(target_fraction=D.TF25 if spec["kind"] == "dose" else 0.0,
                                  plan_override=_override(seed, arm, spec, smoke),
                                  extra_replay_family="calendar" if spec["kind"] == "control" else None,
                                  require_prefix_reuse=not smoke, **common)
    write_json(run / "e3_meta.json", {"arm": arm, "spec": spec, "ratio_used": ratio, "smoke": smoke,
                                      "prefix_reused": s.get("prefix_reused"),
                                      "prefix_state_sha256": s.get("shared_prefix_state_sha256"),
                                      "finished": time.strftime("%Y-%m-%d %H:%M:%S")})
    return s


# ----------------------------------------------------------------- eval
def evaluate(seed: int, arm: str, smoke: bool) -> None:
    from .sft.evaluate import evaluate_family, free_model, load_eval_model
    guards()
    ckpt = branch_dir(seed, arm, smoke) / "checkpoint"
    if not (ckpt / "train_summary.json").exists():
        raise FileNotFoundError("no finished checkpoint: %s" % ckpt)
    ev = eval_dir(seed, arm, smoke)
    todo = []
    fix = ROOT / "data_phase2" / "fixtures"
    for spec in suites():
        for f in spec["families"]:
            out = ev / spec["name"] / f
            if not (out / "stage_report.json").exists():
                rows = read_jsonl(spec["path"](f))
                todo.append((rows[:3] if smoke else rows, out, str(fix / "toolbench.db"), str(fix / "calendar.json")))
    out = ev / "calendar_v3"
    if not (out / "stage_report.json").exists():
        rows = cv3_rows()
        if smoke:
            by = defaultdict(list)
            for r in rows:
                by[r["target_type"]].append(r)
            rows = [x for k in by for x in by[k][:1]]
        todo.append((rows, out, str(DB_PATH), str(CV3_FIXTURE)))
    if todo:
        config = config_for("A", seed, batch_size=32)
        model, tok = load_eval_model(config, str(ckpt))
        stage = {"name": "E3_A_seed%d_%s" % (seed, arm), "index": 4, "adapter": str(ckpt)}
        try:
            for rows, o, db, cal in todo:
                evaluate_family(model, tok, rows, config, stage, o, db, cal)
        finally:
            free_model(model)
    else:
        print("skip eval", arm, flush=True)
    (ev / "EVAL_DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")


# -------------------------------------------------------------- scoring
def _load(p: Path):
    return read_jsonl(p) if p.exists() else None


def _paths(seed: int, arm: str, smoke: bool) -> Tuple[Path, Path, Path]:
    """(checkpoint, eval dir for hist/v2, calendar_v3 dir) for E3 or reused-E4 arms."""
    if arm in D.REUSED:
        a = D.REUSED[arm]
        return (E4R / "branches" / ("A_seed%d_%s" % (seed, a)) / "checkpoint",
                E4R / "evaluation" / ("A_seed%d_%s" % (seed, a)),
                CV3R / "evaluation" / ("E4_A_seed%d_%s" % (seed, a)) / "calendar_v3")
    return branch_dir(seed, arm, smoke) / "checkpoint", eval_dir(seed, arm, smoke), eval_dir(seed, arm, smoke) / "calendar_v3"


def run_items(seed: int, arm: str, smoke: bool) -> Optional[Dict[str, Dict[str, Dict[str, int]]]]:
    ck, ev, cv = _paths(seed, arm, smoke)
    if not (ck / "train_summary.json").exists():
        return None
    m: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(dict)
    nat = {f: _load(ev / "natural_final_v2" / f / "results.jsonl") for f in FAMILIES}
    hist = {f: _load(ev / "historical" / f / "results.jsonl") for f in FAMILIES}
    if nat["file"] is not None:
        m["nat_file"]["file"] = item_scores(nat["file"], "file", "file_v2")
        m["nat_file_strict"]["file"] = item_scores(nat["file"], "file", "file_strict")
    for f in ("database", "python", "calendar"):
        if nat.get(f) is not None:
            m["nat_" + f][f] = item_scores(nat[f], f, "joint")
    for f in FAMILIES:
        if hist.get(f) is not None:
            m["hist_" + f][f] = item_scores(hist[f], f, "joint")
    if (cv / "stage_report.json").exists():
        for r in read_jsonl(cv / "results.jsonl"):
            m["cv3_" + cv3_kind(r["episode_id"])].setdefault("calendar", {})[r["episode_id"]] = int(bool(r.get("joint_success")))
    return m


METRICS = {
    "nat_old_macro": [("nat_file", "file"), ("nat_database", "database"), ("nat_python", "python")],
    "nat_file": [("nat_file", "file")], "nat_database": [("nat_database", "database")],
    "nat_python": [("nat_python", "python")], "nat_calendar_v2": [("nat_calendar", "calendar")],
    "cv3_overall": [("cv3_" + k, "calendar") for k in CV3_TYPES],
    "cv3_free_latest": [("cv3_free_latest", "calendar")], "cv3_locations": [("cv3_locations", "calendar")],
    "hist_calendar": [("hist_calendar", "calendar")],
    "hist_old_macro": [("hist_file", "file"), ("hist_database", "database"), ("hist_python", "python")],
}


def metric_value(items, metric: str) -> Optional[float]:
    vals = []
    for key, fam in METRICS[metric]:
        d = items.get(key, {}).get(fam)
        if not d:
            return None
        vals.append(mean(d.values()))
    return mean(vals)


def paired_bootstrap(A: Dict[int, Any], B: Dict[int, Any], metric: str, n_boot: int = 2000,
                     seed: int = 20261111) -> Optional[Dict[str, Any]]:
    """Same algorithm as e4_run.paired_bootstrap: paired by seed and item; macro metrics are
    resampled per part (stratified). hier = seeds and items resampled; item = seeds fixed."""
    parts = METRICS[metric]
    data = {}
    for s in sorted(set(A) & set(B)):
        per = []
        for key, fam in parts:
            a, b = A[s].get(key, {}).get(fam), B[s].get(key, {}).get(fam)
            if not a or not b:
                break
            ids = sorted(set(a) & set(b))
            if not ids:
                break
            per.append([a[i] - b[i] for i in ids])
        else:
            data[s] = per
    seeds = sorted(data)
    if not seeds:
        return None
    per_seed = [mean(mean(d) for d in data[s]) for s in seeds]
    rng = random.Random(seed)
    hier, item = [], []
    for _ in range(n_boot):
        for tgt, pick in ((hier, [rng.choice(seeds) for _ in seeds]), (item, seeds)):
            tgt.append(mean(mean(sum(d[rng.randrange(len(d))] for _ in d) / len(d) for d in data[s]) for s in pick))

    def ci(v):
        v = sorted(v)
        return [v[int(0.025 * len(v))], v[min(len(v) - 1, int(0.975 * len(v)))]]
    npos, nneg = sum(x > 0 for x in per_seed), sum(x < 0 for x in per_seed)
    n = len(seeds)
    return {"n_seeds": n, "mean_diff": mean(per_seed), "sd_diff": stdev(per_seed) if n > 1 else 0.0,
            "per_seed": dict(zip([str(s) for s in seeds], per_seed)),
            "n_positive_seeds": npos, "n_negative_seeds": nneg,
            "direction": "方向一致(+)" if npos == n and n > 1 else ("方向一致(−)" if nneg == n and n > 1 else "不一致"),
            "ci95_hier": ci(hier), "ci95_item": ci(item)}


ALL_ARMS = ["none", "b05_tf25", "b10_tf25", "b20_tf25", "b05_tf50", "b10_tf50", "b20_tf50",
            "b05_tf00", "b10_tf00", "b20_tf00", "ctrl_cal05", "ctrl_cal10", "ctrl_cal20"] \
    + ["dose_db%d" % k for k in D.DOSES] + ["dose2_db%d" % k for k in D.DOSES[1:]]
NI_MARGIN = -0.05  # pre-registered (EXT_PLAN_20261111_e3_ZH.md): Calendar v3 overall, hier CI lower bound > -5 pp


def comparison_pairs() -> List[Tuple[str, str, str]]:
    """(group, a, b): a - b.  NI = pre-registered non-inferiority test on cv3_overall."""
    P = []
    for b in ("b05", "b10", "b20"):
        c = "ctrl_cal" + b[1:]
        for tf in ("tf25", "tf50", "tf00"):
            P += [("E3-A NI", "%s_%s" % (b, tf), "none"), ("E3-A NI", "%s_%s" % (b, tf), c)]
        P += [("E3-A", c, "none"), ("E3-A", b + "_tf50", b + "_tf25"), ("E3-A", b + "_tf25", b + "_tf00"),
              ("E3-A", b + "_tf50", b + "_tf00")]
    for tf in ("tf25", "tf50", "tf00"):
        P += [("E3-A budget", "b05_" + tf, "b10_" + tf), ("E3-A budget", "b20_" + tf, "b10_" + tf),
              ("E3-A budget", "b20_" + tf, "b05_" + tf)]
    P += [("E3-A budget", "ctrl_cal20", "ctrl_cal05"), ("E3-A budget", "ctrl_cal10", "ctrl_cal05")]
    ks = D.DOSES
    for pre in ("dose_db", "dose2_db"):
        P += [("E3-B", pre + str(k), "dose_db0") for k in ks[1:]]
        P += [("E3-B", pre + str(ks[i + 1]), pre + str(ks[i])) for i in range(1, len(ks) - 1)]
    P += [("E3-B", "dose_db1", "b10_tf25"), ("E3-B", "dose_db0", "none"), ("E3-B NI", "dose_db6", "none")]
    return P


# ---------------------------------------------------------------- ledger
def ledger(seed: int, arm: str, smoke: bool) -> Optional[Dict[str, Any]]:
    ck, _, _ = _paths(seed, arm, smoke)
    if not (ck / "train_summary.json").exists():
        return None
    s = read_json(ck / "train_summary.json")
    plan = read_json(ck / "replay_plan.json") if (ck / "replay_plan.json").exists() else {"items": []}
    log = read_jsonl(ck / "training_log.jsonl")
    tid = {i for f in OLD for i in read_json(E4D / "manifest.json")["target_ids"].get(f, [])}
    items = plan.get("items", [])
    fam_of = {i["episode_id"]: i["family"] for i in items}
    rep = [x for x in log if x["kind"] == "replay"]
    exp = Counter(x["episode_id"] for x in rep)
    spec = D.ARMS.get(arm, {"kind": "e4", "tf": None})
    quota_on = (spec["kind"] == "dose") or (spec["kind"] == "sweep" and spec["tf"] > 0) \
        or (arm in ("b10_tf25", "b10_tf50"))
    fam = {}
    for f in OLD + ["calendar"]:
        rf = [x for x in rep if fam_of.get(x["episode_id"]) == f]
        qf = [i for i in items if i["family"] == f and i.get("target")] if quota_on else []
        cf = [x for x in rf if x["episode_id"] in tid]
        fam[f] = {"samples": len(rf), "unique": len({x["episode_id"] for x in rf}),
                  "input_tokens": sum(x["input_tokens"] for x in rf),
                  "supervised_tokens": sum(x["supervised_tokens"] for x in rf),
                  "mean_input_tokens_per_sample": (sum(x["input_tokens"] for x in rf) / len(rf)) if rf else None,
                  "quota_target_samples": len(qf), "quota_target_input_tokens": sum(i["input_tokens"] for i in qf),
                  "content_target_samples": len(cf), "content_target_input_tokens": sum(x["input_tokens"] for x in cf),
                  "repeats": len(rf) - len({x["episode_id"] for x in rf}),
                  "quota_target_unique": len({i["episode_id"] for i in qf}),
                  "quota_target_ids": sorted(i["episode_id"] for i in qf)}
    tot = sum(x["input_tokens"] for x in rep)
    tgt = sum(fam[f]["quota_target_input_tokens"] for f in OLD)
    checks = {
        "log_replay_tokens_eq_summary": tot == (s.get("replay_input_tokens") or 0),
        "log_replay_tokens_eq_plan": tot == (plan.get("actual_input_tokens") or 0) if items else tot == 0,
        "plan_items_eq_log_multiset": Counter(i["episode_id"] for i in items) == exp,
        "summary_train_tokens_eq_new_plus_replay": s.get("train_tokens") == (s.get("new_input_tokens") or 0) + tot,
        "plan_target_flag_eq_target_id": all(bool(i.get("target")) == (i["episode_id"] in tid) for i in items
                                             if i["family"] in OLD),
    }
    pos = sorted({x["new_position"] for x in rep})
    return {"seed": seed, "arm": arm, "kind": spec["kind"], "mode": s.get("mode"),
            "replay_ratio": s.get("replay_ratio_requested"), "budget_input_tokens": s.get("budget_input_tokens"),
            "replay_input_tokens": tot, "replay_supervised_tokens": sum(x["supervised_tokens"] for x in rep),
            "quota_target_input_tokens": tgt, "actual_target_fraction_input": (tgt / tot) if tot else None,
            "replay_samples": len(rep), "replay_unique": len(exp),
            "max_exposures_per_sample": max(exp.values()) if exp else 0,
            "repeated_samples": {k: v for k, v in exp.items() if v > 1},
            "replay_new_positions": [pos[0], pos[-1]] if pos else None, "n_insertion_positions": len(pos),
            "insertion_positions": pos, "group": spec.get("group", "E4"),
            "new_input_tokens": s.get("new_input_tokens"), "train_tokens_total": s.get("train_tokens"),
            "optimizer_steps": s.get("optimizer_steps"), "microsteps": s.get("steps"),
            "train_elapsed_seconds": s.get("actual_elapsed_seconds"), "peak_gpu_gb": s.get("peak_gpu_gb"),
            "prefix_state_sha256": s.get("shared_prefix_state_sha256"),
            "db_dose": (plan.get("e3_plan") or {}).get("k"), "by_family": fam, "checks": checks}


# ---------------------------------------------------------------- report
def collect(smoke: bool) -> Dict[str, Any]:
    arms = ALL_ARMS if not smoke else [a for a in D.JOB_ORDER]
    seeds = SEEDS if not smoke else SEEDS[:1]
    items, runs, ledgers = defaultdict(dict), [], []
    for arm in arms:
        for s in seeds:
            it = run_items(s, arm, smoke)
            if it is None:
                continue
            items[arm][s] = it
            row = {"seed": s, "arm": arm, "source": "E4(reused)" if arm in D.REUSED else "E3"}
            row.update({m: metric_value(it, m) for m in METRICS})
            row.update({"cv3_" + k: metric_value(it, "cv3_" + k) if ("cv3_" + k) in METRICS else
                        (mean(it["cv3_" + k]["calendar"].values()) if it.get("cv3_" + k) else None) for k in CV3_TYPES})
            runs.append(row)
            lg = ledger(s, arm, smoke)
            if lg:
                ledgers.append(lg)
    agg = []
    keys = list(METRICS) + ["cv3_" + k for k in CV3_TYPES]
    for arm in arms:
        part = [r for r in runs if r["arm"] == arm]
        if not part:
            continue
        e = {"arm": arm, "n_seeds": len(part)}
        for k in keys:
            v = [r[k] for r in part if r.get(k) is not None]
            e[k] = {"mean": mean(v) if v else None, "std": (stdev(v) if len(v) > 1 else 0.0) if v else None,
                    "per_seed": [r.get(k) for r in part]}
        lg = [l for l in ledgers if l["arm"] == arm]
        for k in ("replay_input_tokens", "quota_target_input_tokens", "actual_target_fraction_input", "replay_samples",
                  "replay_unique", "train_tokens_total", "train_elapsed_seconds"):
            v = [l[k] for l in lg if l.get(k) is not None]
            e["ledger_" + k] = {"mean": mean(v) if v else None, "std": (stdev(v) if len(v) > 1 else 0.0) if v else None}
        for f in OLD + ["calendar"]:
            e["ledger_samples_" + f] = [l["by_family"][f]["samples"] for l in lg]
            e["ledger_quota_target_samples_" + f] = [l["by_family"][f]["quota_target_samples"] for l in lg]
            e["ledger_quota_target_tokens_" + f] = [l["by_family"][f]["quota_target_input_tokens"] for l in lg]
        agg.append(e)
    comps = {}
    for group, a, b in comparison_pairs():
        for m in METRICS:
            r = paired_bootstrap(items.get(a, {}), items.get(b, {}), m)
            if r and group.endswith("NI") and m == "cv3_overall":
                r["noninferior_5pp"] = r["ci95_hier"][0] > NI_MARGIN
            if r:
                comps["%s | %s - %s | %s" % (group, a, b, m)] = r
    failed = ["seed%d %s: %s" % (l["seed"], l["arm"], [k for k, v in l["checks"].items() if not v])
              for l in ledgers if not all(l["checks"].values())]
    # invariants across arms of a seed (documented deviations: none has no replay -> 20 steps / 74,944 tokens)
    dev = []
    for s in seeds:
        ls = {l["arm"]: l for l in ledgers if l["seed"] == s and l["replay_samples"] > 0}
        ref_pos = ls.get("b10_tf25", {}).get("insertion_positions")
        for arm, l in ls.items():
            if ref_pos and l["insertion_positions"] != ref_pos:
                dev.append("seed%d %s: insertion positions differ from b10_tf25" % (s, arm))
            b = {0.05: "b05", 0.1: "b10", 0.2: "b20"}.get(round(l["replay_ratio"] or 0, 2))
            ref = ls.get("%s_tf25" % b) if b else None
            if ref and l["optimizer_steps"] != ref["optimizer_steps"]:
                dev.append("seed%d %s: optimizer steps %s vs %s_tf25 %s" % (s, arm, l["optimizer_steps"], b, ref["optimizer_steps"]))
            if ref and abs(l["train_tokens_total"] - ref["train_tokens_total"]) > 0.01 * ref["replay_input_tokens"]:
                dev.append("seed%d %s: train tokens %s vs %s_tf25 %s" % (s, arm, l["train_tokens_total"], b, ref["train_tokens_total"]))
    return {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "smoke": smoke,
            "final_v2": D.FINAL_V2_HASH, "calendar_v3": D.CALV3_HASH,
            "runs": runs, "aggregates": agg, "comparisons": comps, "ledgers": ledgers,
            "ledger_all_checks_ok": not failed, "ledger_failed": failed, "invariant_deviations": dev}


def _f(d, nd=3):
    if not d or d.get("mean") is None:
        return "-"
    return ("%.*f±%.*f" % (nd, d["mean"], nd, d["std"])) if d.get("std") else "%.*f" % (nd, d["mean"])


CV3_ZH = {"free_latest": "最晚空档", "locations": "地点去重", "attendee_count": "参会人数",
          "search_count": "标题计数", "last_end": "末场结束"}


def report(smoke: bool = False) -> Path:
    res = collect(smoke)
    root = ensure_dir(out_root(smoke))
    write_json(root / "results.json", res)
    write_json(root / "token_ledger.json", {"generated": res["generated"], "runs": res["ledgers"],
                                            "all_checks_ok": res["ledger_all_checks_ok"], "failed": res["ledger_failed"],
                                            "invariant_deviations": res["invariant_deviations"]})
    grp = {a: D.ARMS.get(a, {}).get("group", "E4复用") for a in ALL_ARMS}
    A = res["aggregates"]
    L = ["# E3 自动汇总：E3-A 预算 × 定向比例 + Calendar-only 对照；E3-B Database 剂量（A 场景）", "",
         "生成于 %s（Asia/Shanghai）。自然语言期末 v2 合并哈希 `%s…`，Calendar v3 `%s…`。%s" % (
             res["generated"], D.FINAL_V2_HASH[:16], D.CALV3_HASH[:16], "**smoke**" if smoke else ""),
         "b10_* 与 none 复用 E4（只读），所有 E3 分支从 E4 同种子共享中点前缀出发。均值±样本标准差，n=种子数（筛选阶段 3 个）。"
         "汇报顺序按预注册：①旧工具自然语言期末（主）②Calendar v3（新工具保持，主，分子技能）③Calendar v2 与历史测试（分别列出，不合并）。", "",
         "## ① 旧工具自然语言期末 v2（主指标）", "",
         "| 组 | 臂 | n | nat old（宏平均） | File | Database | Python | 历史模板 old（辅助） |", "|---|---|---|---|---|---|---|---|"]
    for a in A:
        L.append("| %s | %s | %d | %s | %s | %s | %s | %s |" % (grp.get(a["arm"], ""), a["arm"], a["n_seeds"],
                 _f(a["nat_old_macro"]), _f(a["nat_file"]), _f(a["nat_database"]), _f(a["nat_python"]), _f(a["hist_old_macro"])))
    L += ["", "## ② Calendar v3（未训练子技能，新工具保持主指标）", "",
          "| 组 | 臂 | n | overall | " + " | ".join(CV3_ZH[k] for k in CV3_TYPES) + " |", "|---|---|---|---|" + "---|" * len(CV3_TYPES)]
    for a in A:
        L.append("| %s | %s | %d | %s | %s |" % (grp.get(a["arm"], ""), a["arm"], a["n_seeds"], _f(a["cv3_overall"]),
                 " | ".join(_f(a["cv3_" + k]) for k in CV3_TYPES)))
    L += ["", "## ③ Calendar v2（已训练技能换说法）与 Calendar 历史模板测试（分别报告，不合并）", "",
          "| 臂 | n | Calendar nat v2 | Calendar hist |", "|---|---|---|---|"]
    for a in A:
        L.append("| %s | %d | %s | %s |" % (a["arm"], a["n_seeds"], _f(a["nat_calendar_v2"]), _f(a["hist_calendar"])))
    L += ["", "## ④ 预注册非劣效检验：Calendar v3 overall，层级 bootstrap 95% CI 下界 > −5pp", "",
          "| 比较 | 均值差 | 95% CI (hier，主) | 非劣(−5pp) | 方向 | 95% CI (item，次) |", "|---|---|---|---|---|---|"]
    for k, v in res["comparisons"].items():
        g, pair, m = k.split(" | ")
        if g.endswith("NI") and m == "cv3_overall":
            L.append("| %s | %+.3f | [%+.3f, %+.3f] | %s | %s | [%+.3f, %+.3f] |" % (
                pair, v["mean_diff"], v["ci95_hier"][0], v["ci95_hier"][1], "是" if v.get("noninferior_5pp") else "未达",
                v["direction"], v["ci95_item"][0], v["ci95_item"][1]))
    L += ["", "## ⑤ E3-B Database 剂量（10% 固定预算；条数 = 独立 Database target 样本）", "",
          "| 臂 | n | DB nat v2 | nat old | v3 overall | DB 独立样本（按种子） | DB 复习 token | DB target token | DB 重复 |", "|---|---|---|---|---|---|---|---|---|"]
    for a in A:
        if not a["arm"].startswith("dose") and a["arm"] not in ("b10_tf25", "b10_tf50", "none"):
            continue
        lg = [l for l in res["ledgers"] if l["arm"] == a["arm"]]
        L.append("| %s | %d | %s | %s | %s | %s | %s | %s | %s |" % (
            a["arm"], a["n_seeds"], _f(a["nat_database"]), _f(a["nat_old_macro"]), _f(a["cv3_overall"]),
            [l["by_family"]["database"]["quota_target_unique"] for l in lg],
            [l["by_family"]["database"]["input_tokens"] for l in lg],
            [l["by_family"]["database"]["quota_target_input_tokens"] for l in lg],
            [l["by_family"]["database"]["repeats"] for l in lg]))
    L += ["", "## ⑥ 配对比较（同种子同题配对；主 = 层级 bootstrap，次 = 种子固定只抽题目）", "",
          "2000 次重抽。n=3 种子只作筛选：三个种子同号记“方向一致”，否则“不一致”；不作显著性结论。", "",
          "| 组 | 比较 | 指标 | 均值差 | 种子差 sd | +/− 种子 | 方向 | 95% CI (hier，主) | 95% CI (item，次) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, v in res["comparisons"].items():
        g, pair, m = k.split(" | ")
        L.append("| %s | %s | %s | %+.3f | %.3f | %d/%d | %s | [%+.3f, %+.3f] | [%+.3f, %+.3f] |" % (
            g, pair, m, v["mean_diff"], v["sd_diff"], v["n_positive_seeds"], v["n_negative_seeds"], v["direction"],
            v["ci95_hier"][0], v["ci95_hier"][1], v["ci95_item"][0], v["ci95_item"][1]))
    LG = ["## 真实 token 账本（逐 run，来自 training_log.jsonl，与 replay_plan / train_summary 交叉核对）", "",
          "核对全部通过：**%s**%s" % (res["ledger_all_checks_ok"], ("（失败：%s）" % res["ledger_failed"]) if res["ledger_failed"] else ""),
          "跨臂不变量偏差（插入位置 / 优化步数 / 总 token 相对同预算 tf25）：%s" % ("无" if not res["invariant_deviations"] else "; ".join(res["invariant_deviations"])), "",
          "| 种子 | 臂 | 预算 | 复习 token | 定向 token | 条数/独立 | 最大重复 | F/DB/Py/Cal 条数 | F/DB/Py 定向条数 | DB 独立 | DB token | DB 平均长度 | 插入位置数 | 训练总 token | 优化步 | 训练秒 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for l in res["ledgers"]:
        bf = l["by_family"]
        LG.append("| %d | %s | %s | %d | %d | %d/%d | %d | %s | %s | %d | %d | %s | %d | %s | %s | %s |" % (
            l["seed"], l["arm"], l["budget_input_tokens"], l["replay_input_tokens"], l["quota_target_input_tokens"],
            l["replay_samples"], l["replay_unique"], l["max_exposures_per_sample"],
            "/".join(str(bf[f]["samples"]) for f in OLD + ["calendar"]),
            "/".join(str(bf[f]["quota_target_samples"]) for f in OLD),
            bf["database"]["unique"], bf["database"]["input_tokens"],
            "-" if not bf["database"]["mean_input_tokens_per_sample"] else "%.0f" % bf["database"]["mean_input_tokens_per_sample"],
            l["n_insertion_positions"], l["train_tokens_total"], l["optimizer_steps"], l["train_elapsed_seconds"]))
    L += [""] + LG + ["", "## 逐 run 分数", ""]
    for r in res["runs"]:
        L.append("- seed%d %s (%s): %s" % (r["seed"], r["arm"], r["source"], json.dumps(
            {k: round(v, 3) for k, v in r.items() if isinstance(v, float)}, ensure_ascii=False)))
    path = root / "report.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    (root / "token_ledger.md").write_text("\n".join(["# E3 真实 token 账本", ""] + LG[1:]) + "\n", encoding="utf-8")
    return path


def check_smoke(seed: int) -> None:
    bad = []
    for arm in ("dose_db2", "ctrl_cal10"):
        ck = branch_dir(seed, arm, True) / "checkpoint"
        if not (ck / "train_summary.json").exists():
            bad.append(arm + ": no summary")
            continue
        s, plan = read_json(ck / "train_summary.json"), read_json(ck / "replay_plan.json")
        if not s.get("completed") or s["replay_input_tokens"] <= 0:
            bad.append(arm + ": no replay")
        if arm == "dose_db2" and plan["target_samples_by_family"].get("database") != 2:
            bad.append("dose: database targets %s" % plan["target_samples_by_family"])
        if arm == "ctrl_cal10" and any(i["family"] != "calendar" for i in plan["items"]):
            bad.append("control: non-Calendar replay item")
        lg = ledger(seed, arm, True)
        if not all(lg["checks"].values()):
            bad.append("%s ledger checks %s" % (arm, lg["checks"]))
        ev = eval_dir(seed, arm, True)
        need = [ev / sp / f / "stage_report.json" for sp in ("historical", "natural_final_v2") for f in FAMILIES]
        need.append(ev / "calendar_v3" / "stage_report.json")
        bad += ["%s missing %s" % (arm, p.relative_to(ev)) for p in need if not p.exists()]
        print(arm, "replay", s["replay_input_tokens"], "/", s["budget_input_tokens"], "targets",
              plan.get("target_samples_by_family"), "by_family", plan.get("actual_tokens_by_family"),
              "train_s", s.get("actual_elapsed_seconds"), flush=True)
    if bad:
        print("SMOKE_FAIL", bad, flush=True)
        raise SystemExit(2)
    print("SMOKE_OK", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["prep", "train", "eval", "report", "check-smoke", "list"], required=True)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--arm", choices=sorted(D.ARMS))
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if a.phase == "list":
        for s in SEEDS:
            for arm in D.JOB_ORDER:
                print(s, arm)
        return
    if a.phase == "prep":
        prep()
        print("PREP_OK", flush=True)
        return
    if a.phase == "train":
        s = train(a.seed, a.arm, a.smoke)
        print("TRAIN_OK", a.seed, a.arm, s.get("actual_elapsed_seconds"), flush=True)
        return
    if a.phase == "eval":
        evaluate(a.seed, a.arm, a.smoke)
        print("EVAL_OK", a.seed, a.arm, flush=True)
        return
    if a.phase == "check-smoke":
        check_smoke(a.seed)
    print("report:", report(a.smoke), flush=True)


if __name__ == "__main__":
    main()
