"""[ext 2026-11-11] E4: clean File replay pool, A scenario, 10% budget.

Identical to ext_tf_sweep (A order stage 3 -> 4, Calendar new, File/Database/
Python old, batch 1, grad-acc 8, 2 epochs, lr 1e-4, replay in the second half,
target family weights 1/3, monitor-v2 probes, replay_ratio 0.1) except:
  * old replay pools / target ids come from data_ext_e4 (File targets rebuilt
    with correct last-line gold on isolated files; Database/Python unchanged),
  * evaluation = historical tests (4 tools) + frozen natural final v2 (4 tools,
    incl. the new Calendar natural final),
  * outputs under runs_ext_e4/ (smoke: runs_ext_e4_smoke/), fresh prefixes.
Phase calnl-old scores Calendar natural final v2 on the finished runs_ext_tf
checkpoints (read-only) plus the stage_03 start adapters.
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

from .ext_rescore import corrected_joint, last_line_correct
from .metrics import answers_equal
from .replay_study import config_for
from .research_data import task_signature
from .utils import canonical_json, ensure_dir, read_json, read_jsonl, sha256_file, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
E4D = ROOT / "data_ext_e4"
R2 = ROOT / "data_round2"
MV2 = ROOT / "data_ext_monitor_v2"
E2 = ROOT / "runs_ext_tf"
OLD = ["file", "database", "python"]
FAMILIES = OLD + ["calendar"]
SEEDS = [20261108, 20261109, 20261110]
E4_ARMS = ["tf00", "tf25", "tf50", "none"]
E2_ARMS = ["tf00", "tf25", "tf50", "tf75", "none"]
FIX = ROOT / "data_phase2" / "fixtures"
DB_PATH = FIX / "toolbench.db"
CALENDAR_PATH = ROOT / "data_replay_study" / "fixtures" / "calendar.json"  # same bytes as data_phase2 (as ext_tf_sweep)


def out_root(smoke: bool) -> Path:
    return ROOT / ("runs_ext_e4_smoke" if smoke else "runs_ext_e4")


def arm_tf(arm: str) -> Optional[float]:
    return None if arm == "none" else int(arm[2:]) / 100.0


def branch_dir(seed: int, arm: str, smoke: bool) -> Path:
    return out_root(smoke) / "branches" / ("A_seed%d_%s" % (seed, arm))


def start_adapter(seed: int) -> Path:
    return ROOT / "runs_phase2" / ("A_seed%d" % seed) / "checkpoints" / "stage_03_python"


# ------------------------------------------------------------- guards
def frozen_check() -> Dict[str, Any]:
    fz = read_json(E4D / "final_v2" / "FROZEN.json")
    for f, rec in fz["files"].items():
        if sha256_file(E4D / rec["path"]) != rec["sha256"]:
            raise SystemExit("final_v2 hash changed for %s; refusing to run" % f)
    man = read_json(E4D / "manifest.json")
    for f in OLD:
        if sha256_file(E4D / "pool" / (f + ".jsonl")) != man["pool"][f]["sha256"]:
            raise SystemExit("data_ext_e4 pool hash changed for %s" % f)
    return fz


def leakage_guard(train_rows: List[Dict[str, Any]]) -> None:
    final = [r for f in FAMILIES for r in read_jsonl(E4D / "final_v2" / (f + ".jsonl"))]
    sig = {task_signature(r) for r in final}
    msg = {canonical_json(r["messages"]) for r in final}
    bad = [r["episode_id"] for r in train_rows
           if task_signature(r) in sig or canonical_json(r["messages"]) in msg]
    if bad:
        raise SystemExit("final_v2 leaks into training/probe inputs: %s" % bad[:5])


# -------------------------------------------------------------- train
def _smoke_inputs() -> Dict[str, str]:
    base = out_root(True) / "inputs"
    ensure_dir(base)
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


def train(seed: int, arm: str, smoke: bool) -> Dict[str, Any]:
    from .replay_train import train_replay_stage
    frozen_check()
    tf = arm_tf(arm)
    target_ids = read_json(E4D / "manifest.json")["target_ids"]
    config = config_for("A", seed, batch_size=32)
    stage = dict(config["stages"][4], index=4)
    new_path = str(ROOT / "data_phase2" / "calendar" / "train.jsonl")
    probes = {f: str(MV2 / (f + ".jsonl")) for f in OLD}
    if smoke:
        config["training"]["num_epochs"] = 1
        inp = _smoke_inputs()
        new_path = inp["new"]
        probes = {f: inp["probe_" + f] for f in OLD}
    pools = {f: str(E4D / "pool" / (f + ".jsonl")) for f in OLD}
    leakage_guard(read_jsonl(new_path) + [r for p in pools.values() for r in read_jsonl(p)]
                  + [r for p in probes.values() for r in read_jsonl(p)])
    run = branch_dir(seed, arm, smoke)
    ckpt = run / "checkpoint"
    if (ckpt / "train_summary.json").exists():
        print("skip train", run.name, flush=True)
        return read_json(ckpt / "train_summary.json")
    if run.exists():
        aside = run.parent / (run.name + "_partial_%d" % int(time.time()))
        print("moving partial run aside:", aside, flush=True)
        shutil.move(str(run), str(aside))
    print("train", run.name, flush=True)
    return train_replay_stage(
        config=config, stage=stage, train_path=new_path, old_train_paths=pools,
        probe_paths=probes, previous_adapter=str(start_adapter(seed)),
        output_dir=str(ckpt), db_path=str(DB_PATH), calendar_path=str(CALENDAR_PATH),
        mode="none" if tf is None else "targeted", replay_ratio=0.1, uniform_floor=0.2,
        prefix_dir=str(out_root(smoke) / "prefixes" / ("A_seed%d" % seed)),
        target_ids=target_ids, target_fraction=0.0 if tf is None else tf,
        target_family_weights={f: 1.0 / len(OLD) for f in OLD})


# --------------------------------------------------------------- eval
def suites() -> List[Dict[str, Any]]:
    return [
        {"name": "historical", "families": FAMILIES,
         "path": lambda f: ROOT / "data_phase2" / f / "test.jsonl", "fix": ROOT / "data_phase2" / "fixtures"},
        {"name": "natural_final_v2", "families": FAMILIES,
         "path": lambda f: E4D / "final_v2" / (f + ".jsonl"), "fix": ROOT / "data_phase2" / "fixtures"},
    ]


def _eval_many(adapter: Path, seed: int, label: str, todo: List[Tuple[List[Dict], Path, Path]]) -> None:
    from .sft.evaluate import evaluate_family, free_model, load_eval_model
    if not todo:
        print("skip eval", label, flush=True)
        return
    config = config_for("A", seed, batch_size=32)
    model, tok = load_eval_model(config, str(adapter))
    stage = {"name": label, "index": 4, "adapter": str(adapter)}
    try:
        for rows, out, fix in todo:
            evaluate_family(model, tok, rows, config, stage, out,
                            str(fix / "toolbench.db"), str(fix / "calendar.json"))
    finally:
        free_model(model)


def evaluate(seed: int, arm: str, smoke: bool) -> None:
    frozen_check()
    ckpt = branch_dir(seed, arm, smoke) / "checkpoint"
    if not (ckpt / "train_summary.json").exists():
        raise FileNotFoundError("no finished checkpoint: %s" % ckpt)
    todo = []
    for spec in suites():
        for f in spec["families"]:
            out = out_root(smoke) / "evaluation" / ("A_seed%d_%s" % (seed, arm)) / spec["name"] / f
            if not (out / "stage_report.json").exists():
                rows = read_jsonl(spec["path"](f))
                todo.append((rows[:3] if smoke else rows, out, spec["fix"]))
    _eval_many(ckpt, seed, "E4_A_seed%d_%s" % (seed, arm), todo)


def calnl_old(seed: int) -> None:
    """Calendar natural final v2 on finished runs_ext_tf checkpoints (read-only) + start adapter."""
    frozen_check()
    rows = read_jsonl(E4D / "final_v2" / "calendar.jsonl")
    for arm in E2_ARMS + ["start"]:
        adapter = start_adapter(seed) if arm == "start" else E2 / "branches" / ("A_seed%d_%s" % (seed, arm)) / "checkpoint"
        if arm != "start" and not (adapter / "train_summary.json").exists():
            print("missing E2 checkpoint", adapter, flush=True)
            continue
        out = ROOT / "runs_ext_e4" / "e2_calnl" / ("A_seed%d_%s" % (seed, arm)) / "natural_final_v2" / "calendar"
        todo = [] if (out / "stage_report.json").exists() else [(rows, out, ROOT / "data_phase2" / "fixtures")]
        _eval_many(adapter, seed, "E2calnl_A_seed%d_%s" % (seed, arm), todo)


# ------------------------------------------------------------- scoring
def _last_text(r):
    try:
        return json.loads(r["expected_observation"])["result"][-1]["text"]
    except Exception:
        return None


def _calls_ok(r):
    return all(r.get(k, False) for k in ("tool_correct", "arguments_correct", "execution_success"))


def item_scores(results: List[Dict[str, Any]], family: str, mode: str) -> Dict[str, int]:
    """mode: 'joint' (evaluator joint_success) | 'file_v2' (official lenient) | 'file_strict'."""
    out = {}
    for r in results:
        eid = r["episode_id"]
        key = eid[4:] if eid.startswith("nf2-") else eid
        if family == "file" and mode == "file_v2":
            ok = _calls_ok(r) and last_line_correct(r, lenient=True)
        elif family == "file" and mode == "file_strict":
            ok = _calls_ok(r) and answers_equal(_last_text(r), r.get("predicted_answer"))
        else:
            ok = bool(r.get("joint_success"))
        out[key] = int(bool(ok))
    return out


def _load(path: Path) -> Optional[List[Dict[str, Any]]]:
    return read_jsonl(path) if path.exists() else None


def _pool_index(pool_dir: Path, target_ids: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
    idx = {}
    for f in OLD:
        tid = set(target_ids.get(f, []))
        for r in read_jsonl(pool_dir / (f + ".jsonl")):
            idx[r["episode_id"]] = {"template": r["template_id"], "target": r["episode_id"] in tid,
                                    "family": f}
    return idx


def audit(ckpt: Path, pool_idx: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    s = read_json(ckpt / "train_summary.json")
    plan = read_json(ckpt / "replay_plan.json") if (ckpt / "replay_plan.json").exists() else {}
    items = plan.get("items", [])
    fam = {}
    for f in OLD:
        it = [i for i in items if i["family"] == f]
        tg = [i for i in it if i.get("target")]
        fam[f] = {"samples": len(it), "unique": len({i["episode_id"] for i in it}),
                  "repeats": len(it) - len({i["episode_id"] for i in it}),
                  "target_samples": len(tg), "target_unique": len({i["episode_id"] for i in tg}),
                  "input_tokens": sum(i["input_tokens"] for i in it),
                  "supervised_tokens": sum(i["supervised_tokens"] for i in it),
                  "target_input_tokens": sum(i["input_tokens"] for i in tg),
                  "target_supervised_tokens": sum(i["supervised_tokens"] for i in tg)}
    by_tpl = defaultdict(lambda: {"samples": 0, "input_tokens": 0, "supervised_tokens": 0})
    for i in items:
        t = pool_idx.get(i["episode_id"], {}).get("template", "?")
        k = "%s/%s" % (i["family"], t)
        by_tpl[k]["samples"] += 1
        by_tpl[k]["input_tokens"] += i["input_tokens"]
        by_tpl[k]["supervised_tokens"] += i["supervised_tokens"]
    tot_in = sum(i["input_tokens"] for i in items)
    tgt_in = sum(i["input_tokens"] for i in items if i.get("target"))
    tot_sup = sum(i["supervised_tokens"] for i in items)
    tgt_sup = sum(i["supervised_tokens"] for i in items if i.get("target"))
    return {
        "nominal_target_fraction": s.get("target_fraction") if s.get("mode") != "none" else None,
        "actual_target_fraction_tokens": (tgt_in / tot_in) if tot_in else None,
        "actual_target_fraction_plan": plan.get("actual_target_fraction"),
        "actual_target_fraction_supervised": (tgt_sup / tot_sup) if tot_sup else None,
        "actual_target_fraction_samples": (sum(1 for i in items if i.get("target")) / len(items)) if items else None,
        "replay_samples": len(items), "replay_unique": len({i["episode_id"] for i in items}),
        "replay_repeats": len(items) - len({i["episode_id"] for i in items}),
        "replay_input_tokens": s.get("replay_input_tokens"), "replay_supervised_tokens": s.get("replay_supervised_tokens"),
        "budget_input_tokens": s.get("budget_input_tokens"),
        "new_input_tokens": s.get("new_input_tokens"), "new_supervised_tokens": s.get("new_supervised_tokens"),
        "target_samples_by_family": {f: fam[f]["target_samples"] for f in OLD},
        "by_family": fam, "exposure_by_template": dict(by_tpl),
        "replay_positions": len(plan.get("common_replay_positions", [])),
        "actual_elapsed_seconds": s.get("actual_elapsed_seconds"), "duration_seconds": s.get("duration_seconds"),
        "prefix_reused": s.get("prefix_reused"),
        "probe_start": (s.get("probes") or {}).get("start", {}).get("scores"),
        "probe_mid": (s.get("probes") or {}).get("midpoint", {}).get("scores"),
    }


def _run_items(round_: str, seed: int, arm: str, smoke: bool) -> Optional[Dict[str, Dict[str, Dict[str, int]]]]:
    """Per-item 0/1 vectors keyed by metric -> family -> item id."""
    m = defaultdict(dict)
    if round_ == "E4":
        ev = out_root(smoke) / "evaluation" / ("A_seed%d_%s" % (seed, arm))
        nat = {f: _load(ev / "natural_final_v2" / f / "results.jsonl") for f in FAMILIES}
        hist = {f: _load(ev / "historical" / f / "results.jsonl") for f in FAMILIES}
        if nat["file"] is not None:
            m["nat_file"]["file"] = item_scores(nat["file"], "file", "file_v2")
            m["nat_file_strict"]["file"] = item_scores(nat["file"], "file", "file_strict")
    else:
        ev = E2 / "evaluation" / ("A_seed%d_%s" % (seed, arm))
        nat = {f: _load(ev / "natural_final" / f / "results.jsonl") for f in OLD}
        nat["calendar"] = _load(ROOT / "runs_ext_e4" / "e2_calnl" / ("A_seed%d_%s" % (seed, arm))
                                / "natural_final_v2" / "calendar" / "results.jsonl")
        hist = {f: _load(ev / "historical" / f / "results.jsonl") for f in FAMILIES}
        if nat["file"] is not None:
            m["nat_file"]["file"] = {r["episode_id"]: int(corrected_joint(r)) for r in nat["file"]}
            m["nat_file_strict"]["file"] = item_scores(nat["file"], "file", "file_strict")
    for f in ("database", "python", "calendar"):
        if nat.get(f) is not None:
            m["nat_" + f][f] = item_scores(nat[f], f, "joint")
    for f in FAMILIES:
        if hist.get(f) is not None:
            m["hist_" + f][f] = item_scores(hist[f], f, "joint")
    return m


def _mean_items(d):
    return mean(d.values()) if d else None


def _row_scores(items) -> Dict[str, Optional[float]]:
    r = {}
    for key in ("nat_file", "nat_file_strict", "nat_database", "nat_python", "nat_calendar",
                "hist_file", "hist_database", "hist_python", "hist_calendar"):
        fam = key.split("_")[1]
        r[key] = _mean_items(items.get(key, {}).get(fam, {})) if items.get(key) else None
    def macro(keys):
        v = [r[k] for k in keys]
        return mean(v) if all(x is not None for x in v) else None
    r["nat_old_macro"] = macro(["nat_file", "nat_database", "nat_python"])
    r["nat_old_macro_strict"] = macro(["nat_file_strict", "nat_database", "nat_python"])
    r["hist_old_macro"] = macro(["hist_file", "hist_database", "hist_python"])
    return r


METRIC_FAMS = {"nat_old_macro": [("nat_file", "file"), ("nat_database", "database"), ("nat_python", "python")],
               "nat_old_macro_strict": [("nat_file_strict", "file"), ("nat_database", "database"), ("nat_python", "python")],
               "nat_file": [("nat_file", "file")], "nat_database": [("nat_database", "database")],
               "nat_python": [("nat_python", "python")], "nat_calendar": [("nat_calendar", "calendar")],
               "hist_calendar": [("hist_calendar", "calendar")],
               "hist_old_macro": [("hist_file", "file"), ("hist_database", "database"), ("hist_python", "python")]}


def paired_bootstrap(a_items: Dict[int, Any], b_items: Dict[int, Any], metric: str,
                     n_boot: int = 2000, seed: int = 20261111) -> Optional[Dict[str, Any]]:
    """a_items/b_items: seed -> items dict (from _run_items).  Paired by seed and item id."""
    parts = METRIC_FAMS[metric]
    seeds = sorted(set(a_items) & set(b_items))
    data = {}
    for s in seeds:
        per = []
        for key, fam in parts:
            A = a_items[s].get(key, {}).get(fam)
            B = b_items[s].get(key, {}).get(fam)
            if not A or not B:
                break
            ids = sorted(set(A) & set(B))
            per.append([A[i] - B[i] for i in ids])
        else:
            data[s] = per
    seeds = sorted(data)
    if not seeds:
        return None
    per_seed = [mean(mean(d) for d in data[s]) for s in seeds]
    rng = random.Random(seed)
    hier, item_only = [], []
    for _ in range(n_boot):
        for target, pick in ((hier, [rng.choice(seeds) for _ in seeds]), (item_only, seeds)):
            vals = []
            for s in pick:
                fam_means = []
                for d in data[s]:
                    n = len(d)
                    fam_means.append(sum(d[rng.randrange(n)] for _ in range(n)) / n)
                vals.append(mean(fam_means))
            target.append(mean(vals))
    def ci(v):
        v = sorted(v)
        return [v[int(0.025 * len(v))], v[min(len(v) - 1, int(0.975 * len(v)))]]
    return {"n_seeds": len(seeds), "mean_diff": mean(per_seed),
            "sd_diff": stdev(per_seed) if len(per_seed) > 1 else 0.0,
            "per_seed": dict(zip([str(s) for s in seeds], per_seed)),
            "n_positive_seeds": sum(x > 0 for x in per_seed),
            "ci95_seed_and_item_bootstrap": ci(hier), "ci95_item_bootstrap_seeds_fixed": ci(item_only)}


def collect(smoke: bool = False) -> Dict[str, Any]:
    e4_idx = _pool_index(E4D / "pool", read_json(E4D / "manifest.json")["target_ids"])
    e2_idx = _pool_index(R2 / "pool", read_json(R2 / "manifest.json")["target_ids"])
    rows, items = [], {"E4": defaultdict(dict), "E2": defaultdict(dict)}
    seeds = SEEDS
    plan = [("E4", a) for a in E4_ARMS] + ([] if smoke else [("E2", a) for a in E2_ARMS])
    for rnd, arm in plan:
        for seed in seeds:
            ck = (branch_dir(seed, arm, smoke) if rnd == "E4" else E2 / "branches" / ("A_seed%d_%s" % (seed, arm))) / "checkpoint"
            if not (ck / "train_summary.json").exists():
                continue
            it = _run_items(rnd, seed, arm, smoke)
            items[rnd][arm][seed] = it
            row = {"round": rnd, "seed": seed, "arm": arm}
            row.update(_row_scores(it))
            row.update(audit(ck, e4_idx if rnd == "E4" else e2_idx))
            rows.append(row)
    # start (pre-Calendar) reference for Calendar natural final
    start = {}
    for seed in seeds:
        p = ROOT / "runs_ext_e4" / "e2_calnl" / ("A_seed%d_start" % seed) / "natural_final_v2" / "calendar" / "results.jsonl"
        if p.exists():
            start[str(seed)] = _mean_items(item_scores(read_jsonl(p), "calendar", "joint"))
    keys = ["nat_old_macro", "nat_old_macro_strict", "nat_file", "nat_file_strict", "nat_database", "nat_python",
            "nat_calendar", "hist_calendar", "hist_old_macro", "actual_target_fraction_tokens",
            "actual_target_fraction_samples", "replay_unique", "replay_repeats", "replay_supervised_tokens",
            "actual_elapsed_seconds"]
    agg = []
    for rnd, arm in plan:
        part = [r for r in rows if r["round"] == rnd and r["arm"] == arm]
        if not part:
            continue
        e = {"round": rnd, "arm": arm, "n_seeds": len(part)}
        for k in keys:
            v = [r[k] for r in part if r.get(k) is not None]
            e[k] = {"mean": mean(v) if v else None, "std": (stdev(v) if len(v) > 1 else 0.0) if v else None}
        e["target_samples_by_family"] = {f: [r["target_samples_by_family"][f] for r in part] for f in OLD}
        agg.append(e)
    comps = {}
    metrics = ["nat_old_macro", "nat_old_macro_strict", "nat_file", "nat_database", "nat_python",
               "nat_calendar", "hist_calendar", "hist_old_macro"]
    pairs = [("tf25", "tf00"), ("tf50", "tf00"), ("tf25", "none"), ("tf50", "none"), ("tf50", "tf25"), ("tf00", "none")]
    for a, b in pairs:
        for m in metrics:
            res = paired_bootstrap(items["E4"].get(a, {}), items["E4"].get(b, {}), m)
            if res:
                comps["E4 %s-%s | %s" % (a, b, m)] = res
    if not smoke:
        for a in E4_ARMS:
            for m in metrics:
                res = paired_bootstrap(items["E4"].get(a, {}), items["E2"].get(a, {}), m)
                if res:
                    comps["E4-E2 %s | %s" % (a, m)] = res
    # Pareto over (old natural macro, Calendar natural) means
    pts = [(e["round"] + ":" + e["arm"], e["nat_old_macro"]["mean"], e["nat_calendar"]["mean"]) for e in agg
           if e["nat_old_macro"]["mean"] is not None and e["nat_calendar"]["mean"] is not None]
    def nd(points):
        return [p[0] for p in points if not any((q[1] >= p[1] and q[2] >= p[2] and (q[1] > p[1] or q[2] > p[2])) for q in points)]
    pareto = {"all": nd(pts), "E4": nd([p for p in pts if p[0].startswith("E4")]),
              "E2": nd([p for p in pts if p[0].startswith("E2")]), "points": pts}
    return {"rows": rows, "aggregates": agg, "comparisons": comps, "pareto": pareto,
            "calendar_nat_start": start,
            "final_v2": read_json(E4D / "final_v2" / "FROZEN.json")["combined_sha256"]}


def _f(d, nd=3):
    if d is None or d.get("mean") is None:
        return "-"
    return ("%.*f±%.*f" % (nd, d["mean"], nd, d["std"])) if d.get("std") else "%.*f" % (nd, d["mean"])


def report(smoke: bool = False) -> Path:
    res = collect(smoke)
    root = out_root(smoke)
    ensure_dir(root)
    write_json(root / "results.json", res)
    L = ["# E4 自动汇总：干净 File 复习池 · A 场景 · 预算 10%", "",
         "自动生成于 %s（Asia/Shanghai）。natural final v2 合并哈希 `%s`。" % (time.strftime("%Y-%m-%d %H:%M:%S"), res["final_v2"][:16]),
         "主口径 nat old = 自然语言期末 v2 旧工具宏平均（File 用 v2 官方宽松判分：最后一行原文 / 去掉 `line N: ` 的正文 / {line,text} 且行号对）；"
         "strict = File 精确字符串。Calendar nat = 新 Calendar 自然语言期末（30 题）；Calendar hist = 历史模板测试。"
         "E2 = 上轮 runs_ext_tf（旧 File 池），Calendar nat 为只读补评。均值±样本标准差，n=种子数。", "",
         "| 轮 | 臂 | n | nat old | nat old strict | File | DB | Py | Calendar nat | Calendar hist | hist old | 实际定向比例(token) | 实际定向比例(样本) | 独立样本 | 重复 | 复习监督 token |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in res["aggregates"]:
        L.append("| %s | %s | %d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            a["round"], a["arm"], a["n_seeds"], _f(a["nat_old_macro"]), _f(a["nat_old_macro_strict"]),
            _f(a["nat_file"]), _f(a["nat_database"]), _f(a["nat_python"]), _f(a["nat_calendar"]),
            _f(a["hist_calendar"]), _f(a["hist_old_macro"]), _f(a["actual_target_fraction_tokens"]),
            _f(a["actual_target_fraction_samples"]), _f(a["replay_unique"], 1), _f(a["replay_repeats"], 1),
            _f(a["replay_supervised_tokens"], 0)))
    if res["calendar_nat_start"]:
        L += ["", "起点（stage_03，未学 Calendar）的 Calendar nat：%s" % json.dumps(
            {k: round(v, 3) for k, v in res["calendar_nat_start"].items()})]
    L += ["", "## 每臂定向样本数（按种子 108/109/110）", ""]
    for a in res["aggregates"]:
        L.append("- %s %s: %s" % (a["round"], a["arm"], json.dumps(a["target_samples_by_family"])))
    L += ["", "## 配对比较（同种子、同题目配对；先按种子求差再平均）", "",
          "CI 为配对 bootstrap 95% 区间（2000 次）：hier = 种子与题目两级重抽；item = 种子固定、只抽题目。"
          "n=3 种子，区间只作描述，不作显著性结论。", "",
          "| 比较 | 指标 | 均值差 | 种子差 sd | 为正的种子数 | 95% CI (hier) | 95% CI (item) |", "|---|---|---|---|---|---|---|"]
    for k, v in res["comparisons"].items():
        name, metric = k.split(" | ")
        L.append("| %s | %s | %+.3f | %.3f | %d/%d | [%+.3f, %+.3f] | [%+.3f, %+.3f] |" % (
            name, metric, v["mean_diff"], v["sd_diff"], v["n_positive_seeds"], v["n_seeds"],
            v["ci95_seed_and_item_bootstrap"][0], v["ci95_seed_and_item_bootstrap"][1],
            v["ci95_item_bootstrap_seeds_fixed"][0], v["ci95_item_bootstrap_seeds_fixed"][1]))
    p = res["pareto"]
    L += ["", "## 均值层面的非支配点（旧工具 nat old × Calendar nat，两者越高越好）", "",
          "- 全部臂（含 none/tf00）：%s" % ", ".join(p["all"]),
          "- 仅 E4：%s" % ", ".join(p["E4"]), "- 仅 E2：%s" % ", ".join(p["E2"]), "",
          "点：" + "; ".join("%s=(%.3f, %.3f)" % t for t in p["points"]), "",
          "## 逐 run 明细", ""]
    for r in res["rows"]:
        slim = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
                if k not in ("exposure_by_template", "by_family", "round", "seed", "arm")}
        L.append("- %s seed%d %s: %s" % (r["round"], r["seed"], r["arm"], json.dumps(slim, ensure_ascii=False)))
        L.append("  - by_family: %s" % json.dumps(r["by_family"]))
        L.append("  - exposure_by_template: %s" % json.dumps(r["exposure_by_template"]))
    path = root / "report.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


def check_smoke(seed: int) -> None:
    bad = []
    old_ids = set(read_json(R2 / "manifest.json")["target_ids"]["file"])
    new_ids = set(read_json(E4D / "manifest.json")["target_ids"]["file"])
    for arm in ("tf00", "tf50"):
        ck = branch_dir(seed, arm, True) / "checkpoint"
        s = read_json(ck / "train_summary.json")
        plan = read_json(ck / "replay_plan.json")
        if not s.get("completed") or s["replay_input_tokens"] <= 0:
            bad.append("%s: no replay" % arm)
        if arm == "tf50" and not plan.get("target_actual_input_tokens"):
            bad.append("tf50: no target tokens")
        if arm == "tf00" and plan.get("target_actual_input_tokens"):
            bad.append("tf00: unexpected target tokens")
        ids = [i["episode_id"] for i in plan.get("items", [])]
        if old_ids & set(ids):
            bad.append("%s: old mislabeled File target in plan" % arm)
        ft = [i for i in ids if i.startswith("file-") and i in new_ids]
        ev = out_root(True) / "evaluation" / ("A_seed%d_%s" % (seed, arm))
        for suite in ("historical", "natural_final_v2"):
            for fam in FAMILIES:
                if not (ev / suite / fam / "stage_report.json").exists():
                    bad.append("%s missing eval %s/%s" % (arm, suite, fam))
        print(arm, "replay", s["replay_input_tokens"], "budget", s["budget_input_tokens"],
              "target_tokens", plan.get("target_actual_input_tokens"), "actual_tf",
              plan.get("actual_target_fraction"), "new_file_targets_in_plan", len(ft), flush=True)
    if bad:
        print("SMOKE_FAIL", bad, flush=True)
        raise SystemExit(2)
    print("SMOKE_OK", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["train", "eval", "calnl-old", "report", "check-smoke"], required=True)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--arm", choices=["tf00", "tf25", "tf50", "tf75", "none"])
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if a.phase == "train":
        s = train(a.seed, a.arm, a.smoke)
        print("TRAIN_OK", a.seed, a.arm, s.get("actual_elapsed_seconds"), flush=True)
    elif a.phase == "eval":
        evaluate(a.seed, a.arm, a.smoke)
        print("EVAL_OK", a.seed, a.arm, flush=True)
    elif a.phase == "calnl-old":
        calnl_old(a.seed)
        print("CALNL_OLD_OK", a.seed, flush=True)
    elif a.phase == "check-smoke":
        check_smoke(a.seed)
    print("report:", report(a.smoke), flush=True)


if __name__ == "__main__":
    main()
