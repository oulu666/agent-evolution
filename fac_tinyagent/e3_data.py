"""[ext 2026-11-11] E3 data / plan builder (CPU only, no model weights loaded).

E3 = budget sweep (5% / 20% x tf00/tf25/tf50; 10% and none reused from E4),
     Database dose at 10% (k = 0/1/2/3/4/6 distinct Database target rows),
     compute-matched Calendar-only control (10% extra Calendar micro-steps, no replay).

Writes data_ext_e3/ only (refuses to overwrite an existing manifest):
  manifest.json          design, arm table, job order, hashes of every input it depends on
                         (E4 pools/target ids, final v2, Calendar v3, Calendar train, probes,
                         start adapters, E4 midpoint prefixes) and the prefix-metadata match.
  plans/A_seed<s>_<arm>.json   frozen replay plans for the dose and control arms
                         (episode ids + token counts; the trainer recomputes the plan and
                         refuses to train if it differs).
  checks.json            unit / leakage / prefix checks (also run by scripts/test_e3_data.py).

Design revised 2026-11-11 20:05 after the advisor review of Calendar v3:
E3-A (main): budget 5/10/20% x tf25/tf50, uniform tf00 at 5/20%, none (reused), and a
  compute-matched Calendar-only control at EACH budget (ctrl_cal05/10/20).  10% tf* and none
  are the E4 checkpoints (reused, not retrained).
E3-B (mechanism): Database dose at fixed 10% budget, k = 0/1/2/3/4/6 distinct Database
  target rows (optional second nested draw dose2_db*, not in the default job list).

Database dose unit: 1 unit = 1 distinct Database *target-type* episode (E4 target_ids
  ["database"], template target_db_filter_top, 11 rows), executed exactly once in the second
  half.  Doses are nested (k=1 subset of k=2 ...) via a fixed per-seed permutation.
  Per seed, the File and Python blocks are IDENTICAL for every k (tf25-style allocation of the
  10% budget: targeted part = budget - int(0.75*budget), File/Python each 1/3 of it; uniform
  part 0.75*budget, File/Python each 1/3 of it, non-target rows).  The Database block keeps the
  remaining budget (~1/3) constant: k target rows + ordinary (non-target) Database rows filling
  the rest.  So the total replay budget, the other tools' allocation and the Database replay
  tokens are (nearly) constant, and only the number of distinct Database target rows varies.
Control: the replay slots are filled with Calendar training rows (same 80-row train set,
  with replacement) at the same budget; the number of rows is chosen so that the optimizer
  update count equals the matched tf25 arm (ceil((160+n)/8)) and n >= 10 so the insertion
  positions are the same 10 positions as every replay arm; total tokens within 1% of budget.
"""
from __future__ import annotations

import argparse
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .replay_train import _fill_whole_rows, fixed_new_order, make_replay_plan
from .research_data import task_signature
from .utils import canonical_json, read_json, read_jsonl, sha256_file, write_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_ext_e3"
E4D = ROOT / "data_ext_e4"
CV3 = ROOT / "data_ext_cal_v3"
MV2 = ROOT / "data_ext_monitor_v2"
E4R = ROOT / "runs_ext_e4"
NEW_TRAIN = ROOT / "data_phase2" / "calendar" / "train.jsonl"
OLD = ["file", "database", "python"]
SEEDS = [20261108, 20261109, 20261110]
DOSES = [0, 1, 2, 3, 4, 6]
TF25 = 0.25
FINAL_V2_HASH = "5dcc7d786fd60556e97d4e2ebefe143fdd9e96e9aa9052877a1317758b15a8f6"
CALV3_HASH = "2b203ab5123620b99fb64c06afb1e89a388596eade154012e331bb4a27b3633a"
DOSE_PERM_OFFSET = 7
PLAN_SEED_OFFSET = 104729  # = replay_train: plans use config seed + 104729

# ----------------------------------------------------------------- arms
DOSE_PERM_OFFSET2 = 17  # optional second nested draw
ARMS: Dict[str, Dict[str, Any]] = {}
for _b in (5, 20):
    for _tf in (0, 25, 50):
        ARMS["b%02d_tf%02d" % (_b, _tf)] = {"kind": "sweep", "group": "E3-A", "ratio": _b / 100.0, "tf": _tf / 100.0}
for _b in (5, 10, 20):
    ARMS["ctrl_cal%02d" % _b] = {"kind": "control", "group": "E3-A", "ratio": _b / 100.0}
for _k in DOSES:
    ARMS["dose_db%d" % _k] = {"kind": "dose", "group": "E3-B", "ratio": 0.10, "k": _k, "draw": 1}
for _k in DOSES[1:]:
    ARMS["dose2_db%d" % _k] = {"kind": "dose", "group": "E3-B2(optional)", "ratio": 0.10, "k": _k, "draw": 2}
# reused from E4 (not retrained): 10% tf00/tf25/tf50 and none
REUSED = {"b10_tf00": "tf00", "b10_tf25": "tf25", "b10_tf50": "tf50", "none": "none"}
# per-seed order inside each group: most informative first
JOB_ORDER_A = ["b05_tf25", "b20_tf25", "b05_tf50", "b20_tf50", "ctrl_cal10", "ctrl_cal05", "ctrl_cal20",
               "b05_tf00", "b20_tf00"]
JOB_ORDER_B = ["dose_db0", "dose_db6", "dose_db2", "dose_db4", "dose_db1", "dose_db3"]
JOB_ORDER_B2 = ["dose2_db6", "dose2_db2", "dose2_db4", "dose2_db1", "dose2_db3"]
JOB_ORDER = JOB_ORDER_A + JOB_ORDER_B
assert sorted(JOB_ORDER + JOB_ORDER_B2) == sorted(ARMS)
N_POSITIONS = 10  # common_replay_positions: min(count, 79, (160-80)//8) -> 10 when every plan has >= 10 rows


# ---------------------------------------------------------- plan builders
def _key(r):
    return (r["family"], r["row_index"], r["episode_id"])


def _strip(r):
    return {k: v for k, v in r.items() if k != "features"}


def _finish(items, budget, extra) -> Dict[str, Any]:
    fams = sorted({i["family"] for i in items} | set(extra.get("families", [])))
    tgt = [i for i in items if i.get("target")]
    plan = {
        "items": items, "budget_input_tokens": budget,
        "actual_input_tokens": sum(i["input_tokens"] for i in items),
        "actual_supervised_tokens": sum(i["supervised_tokens"] for i in items),
        "weights": extra.get("weights", {}), "target_family_weights": extra.get("target_family_weights", {}),
        "target_fraction": extra.get("target_fraction", 0.0),
        "actual_target_fraction": sum(i["input_tokens"] for i in tgt) / max(1, sum(i["input_tokens"] for i in items)),
        "uniform_actual_input_tokens": sum(i["input_tokens"] for i in items if not i.get("target")),
        "target_actual_input_tokens": sum(i["input_tokens"] for i in tgt),
        "actual_tokens_by_family": {f: sum(i["input_tokens"] for i in items if i["family"] == f) for f in fams},
        "target_samples_by_family": {f: sum(1 for i in tgt if i["family"] == f) for f in fams},
        "quota_error_tokens_by_family": {f: 0 for f in fams},
        "samples_by_family": {f: sum(i["family"] == f for i in items) for f in fams},
    }
    plan["unused_input_tokens"] = budget - plan["actual_input_tokens"]
    plan["unused_fraction"] = plan["unused_input_tokens"] / budget if budget else 0.0
    plan["within_one_percent_of_budget"] = plan["unused_input_tokens"] <= budget * 0.01
    plan["e3_plan"] = extra["e3_plan"]
    if plan["unused_input_tokens"] < 0:
        raise ValueError("E3 plan exceeds budget")
    return plan


def _dedup(items, seen):
    out = []
    for it in items:
        if _key(it) not in seen:
            seen.add(_key(it))
            out.append(dict(it))
    return out


def dose_plan(pools: Mapping[str, Sequence[Dict[str, Any]]], budget: int, seed: int, k: int,
              draw: int = 1) -> Dict[str, Any]:
    """Database dose plan at a fixed total budget (see module docstring)."""
    if set(pools) != set(OLD):
        raise ValueError("dose plan needs exactly the three old pools")
    tgt = {f: [_strip(r) for r in pools[f] if r.get("target")] for f in OLD}
    non = {f: [_strip(r) for r in pools[f] if not r.get("target")] for f in OLD}
    target_budget = budget - int(budget * (1.0 - TF25))
    uniform_budget = budget - target_budget
    seen: set = set()
    # File / Python blocks: identical for every k (depend only on budget and seed)
    fp_t = make_replay_plan({"file": tgt["file"], "python": tgt["python"]}, {"file": 0.5, "python": 0.5},
                            int(round(target_budget * 2.0 / 3.0)), seed + 1)
    fp_t_items = _dedup(fp_t["items"], seen)
    fp_u = make_replay_plan({"file": non["file"], "python": non["python"]}, {"file": 0.5, "python": 0.5},
                            int(round(uniform_budget * 2.0 / 3.0)), seed)
    fp_u_items = [dict(i) for i in fp_u["items"]]  # ordinary replay: repeats allowed (as in E4 tf arms), recorded in the ledger
    seen.update(_key(i) for i in fp_u_items)
    fp_tokens = sum(i["input_tokens"] for i in fp_t_items + fp_u_items)
    db_budget = budget - fp_tokens
    db_sorted = sorted(tgt["database"], key=lambda r: r["episode_id"])
    if k > len(db_sorted):
        raise ValueError("dose k=%d exceeds %d Database targets" % (k, len(db_sorted)))
    perm = list(range(len(db_sorted)))
    random.Random(seed + (DOSE_PERM_OFFSET if draw == 1 else DOSE_PERM_OFFSET2)).shuffle(perm)
    db_t_items = _dedup([db_sorted[i] for i in perm[:k]], seen)
    db_t_tokens = sum(i["input_tokens"] for i in db_t_items)
    if db_t_tokens > db_budget:
        raise ValueError("Database targets (%d) exceed the Database block (%d)" % (db_t_tokens, db_budget))
    db_u = make_replay_plan({"database": non["database"]}, {"database": 1.0}, db_budget - db_t_tokens, seed + 2)
    db_u_items = [dict(i) for i in db_u["items"]]
    seen.update(_key(i) for i in db_u_items)
    rem = db_budget - db_t_tokens - sum(i["input_tokens"] for i in db_u_items)
    if rem > 0:
        db_u_items += _fill_whole_rows(non["database"], rem, random.Random(seed + 3))
    target_items = fp_t_items + db_t_items
    random.Random(seed + 5).shuffle(target_items)
    uniform_items = fp_u_items + db_u_items
    random.Random(seed + 6).shuffle(uniform_items)
    items = uniform_items + target_items  # same layout as make_hybrid_plan: uniform first, targeted after
    db_all = [i for i in items if i["family"] == "database"]
    return _finish(items, budget, {
        "families": OLD, "weights": {f: 1.0 / len(OLD) for f in OLD},
        "target_family_weights": {"file": 1 / 3, "python": 1 / 3, "database": "fixed_count"},
        "target_fraction": TF25,
        "e3_plan": {"kind": "db_dose", "k": k, "draw": draw,
                    "db_target_ids": [r["episode_id"] for r in db_t_items], "db_target_tokens": db_t_tokens,
                    "db_unique_samples": len({i["episode_id"] for i in db_all}),
                    "db_replay_tokens": sum(i["input_tokens"] for i in db_all), "db_block_budget": db_budget,
                    "fp_target_ids": sorted(i["episode_id"] for i in fp_t_items),
                    "fp_uniform_ids": sorted(i["episode_id"] for i in fp_u_items),
                    "fp_target_tokens": sum(i["input_tokens"] for i in fp_t_items),
                    "fp_tokens": fp_tokens, "target_budget_tf25": target_budget}})


def steps_for(n_replay: int, n_new: int = 160, acc: int = 8) -> int:
    return int(math.ceil((n_new + n_replay) / acc))


def control_plan(extra_pools: Mapping[str, Sequence[Dict[str, Any]]], budget: int, seed: int,
                 n_target: Optional[int] = None, ratio: float = 0.10) -> Dict[str, Any]:
    """Calendar-only rows; if n_target is given, exactly n_target rows with total tokens in
    [0.99*budget, budget] (randomized local search, deterministic for a seed)."""
    cal = [_strip(r) for r in extra_pools["calendar"]]
    if n_target is None:
        p = make_replay_plan({"calendar": cal}, {"calendar": 1.0}, budget, seed)
        items = [dict(i, target=False) for i in p["items"]]
    else:
        rng = random.Random(seed)
        lo = int(math.ceil(0.99 * budget))
        L = sorted(cal, key=lambda r: (r["input_tokens"], r["episode_id"]))
        if sum(r["input_tokens"] for r in L[:n_target]) > budget or sum(r["input_tokens"] for r in L[-n_target:]) < lo:
            raise ValueError("no %d Calendar rows fit budget %d" % (n_target, budget))
        pick = [rng.choice(cal) for _ in range(n_target)]
        for _ in range(200000):
            tot = sum(r["input_tokens"] for r in pick)
            if lo <= tot <= budget:
                break
            i = rng.randrange(n_target)
            want = (lo + budget) / 2.0 - (tot - pick[i]["input_tokens"])
            cands = sorted(cal, key=lambda r: abs(r["input_tokens"] - want))[:5]
            pick[i] = rng.choice(cands)
        else:
            raise ValueError("control plan search failed")
        rng.shuffle(pick)
        items = [dict(r, target=False) for r in pick]
    return _finish(items, budget, {
        "families": ["calendar"], "weights": {"calendar": 1.0}, "target_fraction": 0.0,
        "e3_plan": {"kind": "calendar_only_control", "ratio": ratio, "n_target": n_target,
                    "optimizer_steps_expected": steps_for(len(items)),
                    "note": "replay slots filled with Calendar training rows; no old-tool replay"}})


def plan_signature(plan: Dict[str, Any]) -> List[List[Any]]:
    return [[i["family"], i["row_index"], i["episode_id"], i["input_tokens"], i["supervised_tokens"],
             bool(i.get("target"))] for i in plan["items"]]


# ------------------------------------------------------------ CPU pools
def _config(seed: int) -> Dict[str, Any]:
    from .replay_study import config_for
    return config_for("A", seed, batch_size=32)


def prepared(seed: int, new_path: Path = NEW_TRAIN, smoke_rows: Optional[int] = None):
    """Exactly the pools / new data replay_train builds (tokenizer only, CPU)."""
    from .replay_train import _prepare_rows
    from .sft.train import load_tokenizer
    config = _config(seed)
    tok = load_tokenizer(config)
    ml = int(config["training"]["max_seq_length"])
    tid = read_json(E4D / "manifest.json")["target_ids"]
    pools = {}
    for f in OLD:
        rows, _ = _prepare_rows(read_jsonl(E4D / "pool" / (f + ".jsonl")), tok, ml, f, complete_only=True)
        pools[f] = [dict(_strip(r), target=r["episode_id"] in set(tid.get(f, []))) for r in rows]
    new_rows = read_jsonl(new_path)
    if smoke_rows:
        new_rows = new_rows[:smoke_rows]
    new, _ = _prepare_rows(new_rows, tok, ml, "calendar")
    epochs = int(config["training"]["num_epochs"])
    order = fixed_new_order(len(new_rows), epochs, int(config["seed"]))
    total_new = sum(new[i]["input_tokens"] for i in order)
    return config, pools, {"calendar": [dict(_strip(r), target=False) for r in new]}, total_new, order


def prefix_metadata(seed: int) -> Dict[str, Any]:
    """Re-derive replay_train's prefix metadata for the formal E3 config (must equal E4's)."""
    config = _config(seed)
    rows = read_jsonl(NEW_TRAIN)
    order = fixed_new_order(len(rows), int(config["training"]["num_epochs"]), int(config["seed"]))
    adapter = ROOT / "runs_phase2" / ("A_seed%d" % seed) / "checkpoints" / "stage_03_python"
    return {"seed": int(config["seed"]), "training": config["training"], "lora": config["lora"],
            "quantization": config["quantization"],
            "adapter_sha256": sha256_file(adapter / "adapter_model.safetensors"),
            "new_sha256": sha256_file(NEW_TRAIN),
            "old_sha256": {f: sha256_file(E4D / "pool" / (f + ".jsonl")) for f in OLD},
            "probe_sha256": {f: sha256_file(MV2 / (f + ".jsonl")) for f in OLD},
            "order": order, "midpoint": len(order) // 2}


def _e4_probe_scores(seed: int) -> Tuple[Dict[str, float], Dict[str, float]]:
    p = read_json(E4R / "branches" / ("A_seed%d_tf25" % seed) / "checkpoint" / "replay_plan.json")
    return p["baseline_probe_scores"], p["midpoint_probe_scores"]


def reference_counts(seed: int, pools, budget: int, s: int) -> Dict[str, int]:
    """Replay row counts replay_train will produce at this budget (uniform / tf00 / tf25 / tf50 /
    adaptive): used to match control optimizer steps and to verify the 10 common positions."""
    from .replay_train import allocation_weights, make_hybrid_plan
    w = {f: 1.0 / len(OLD) for f in OLD}
    out = {"uniform": len(make_replay_plan(pools, w, budget, s)["items"])}
    for tf in (0.0, 0.25, 0.50):
        out["tf%02d" % int(tf * 100)] = len(make_hybrid_plan(pools, budget, s, tf, w)["items"])
    base, mid = _e4_probe_scores(seed)
    drops = {f: max(0.0, base[f] - mid[f]) for f in base}
    tf_fams = [f for f in sorted(pools) if any(r.get("target") for r in pools[f])]
    aw = {f: drops.get(f, 0.0) for f in tf_fams if drops.get(f, 0.0) > 0}
    if aw:
        t = sum(aw.values())
        out["adaptive@tf25"] = len(make_hybrid_plan(pools, budget, s, 0.25, {f: v / t for f, v in aw.items()})["items"])
        out["adaptive@tf50"] = len(make_hybrid_plan(pools, budget, s, 0.50, {f: v / t for f, v in aw.items()})["items"])
        out["adaptive@tf00"] = len(make_hybrid_plan(pools, budget, s, 0.0, {f: v / t for f, v in aw.items()})["items"])
    else:
        out["adaptive"] = len(make_replay_plan(pools, allocation_weights("adaptive", base, mid, 0.2), budget, s)["items"])
    return out


def control_n(ref: Dict[str, int], cal_rows, budget: int) -> int:
    """Largest n <= n(tf25) with the same optimizer step count as tf25, n >= N_POSITIONS, feasible."""
    target_steps = steps_for(ref["tf25"])
    lo = int(math.ceil(0.99 * budget))
    L = sorted(r["input_tokens"] for r in cal_rows)
    for n in range(max(ref["tf25"], N_POSITIONS), N_POSITIONS - 1, -1):
        if steps_for(n) != target_steps:
            continue
        if sum(L[:n]) <= budget and sum(L[-n:]) >= lo:
            return n
    raise ValueError("no step-matched Calendar control possible at budget %d" % budget)


def build_plans(seed: int) -> Dict[str, Dict[str, Any]]:
    config, pools, extra, total_new, _ = prepared(seed)
    s = int(config["seed"]) + PLAN_SEED_OFFSET
    out, refs = {}, {}
    for b in (5, 10, 20):
        budget = int(math.floor(total_new * b / 100.0))
        refs[b] = reference_counts(seed, pools, budget, s)
        n = control_n(refs[b], extra["calendar"], budget)
        out["ctrl_cal%02d" % b] = control_plan(extra, budget, s, n_target=n, ratio=b / 100.0)
        out["ctrl_cal%02d" % b]["e3_plan"]["reference_counts"] = refs[b]
    budget = int(math.floor(total_new * 0.10))
    for arm, spec in ARMS.items():
        if spec["kind"] == "dose":
            out[arm] = dose_plan(pools, budget, s, spec["k"], spec["draw"])
            out[arm]["e3_plan"]["reference_counts"] = refs[10]
    for p in out.values():
        p["e3_total_new_input_tokens"] = total_new
    return out


# --------------------------------------------------------------- checks
def leakage() -> Dict[str, Any]:
    v3 = read_jsonl(CV3 / "final_v3" / "calendar_v3.jsonl")
    v2 = [r for f in OLD + ["calendar"] for r in read_jsonl(E4D / "final_v2" / (f + ".jsonl"))]
    train = read_jsonl(NEW_TRAIN) + [r for f in OLD for r in read_jsonl(E4D / "pool" / (f + ".jsonl"))] \
        + [r for f in OLD for r in read_jsonl(MV2 / (f + ".jsonl"))]
    res = {}
    for name, ev in (("calendar_v3", v3), ("final_v2", v2)):
        sig = {task_signature(r) for r in ev}
        msg = {canonical_json(r["messages"]) for r in ev}
        res[name] = {"sig_overlap": sum(task_signature(r) in sig for r in train),
                     "msg_overlap": sum(canonical_json(r["messages"]) in msg for r in train)}
    res["ok"] = all(v["sig_overlap"] == 0 and v["msg_overlap"] == 0 for v in res.values() if isinstance(v, dict))
    return res


def input_hashes() -> Dict[str, Any]:
    fz2 = read_json(E4D / "final_v2" / "FROZEN.json")
    fz3 = read_json(CV3 / "final_v3" / "FROZEN.json")
    return {
        "final_v2_combined": fz2["combined_sha256"],
        "final_v2_files_ok": all(sha256_file(E4D / r["path"]) == r["sha256"] for r in fz2["files"].values()),
        "calendar_v3_combined": fz3["combined_sha256"],
        "calendar_v3_files_ok": sha256_file(CV3 / fz3["files"]["calendar_v3"]["path"]) == fz3["files"]["calendar_v3"]["sha256"]
        and sha256_file(CV3 / fz3["fixture"]["path"]) == fz3["fixture"]["sha256"],
        "e4_pool": {f: sha256_file(E4D / "pool" / (f + ".jsonl")) for f in OLD},
        "e4_manifest": sha256_file(E4D / "manifest.json"),
        "calendar_train": sha256_file(NEW_TRAIN),
        "probes": {f: sha256_file(MV2 / (f + ".jsonl")) for f in OLD},
        "e4_prefix_state": {str(s): read_json(E4R / "prefixes" / ("A_seed%d" % s) / "manifest.json")["state_sha256"]
                            for s in SEEDS},
    }


def verify(write_plans: bool = False) -> Dict[str, Any]:
    checks: Dict[str, Any] = {"hashes": input_hashes()}
    h = checks["hashes"]
    checks["final_v2_hash_ok"] = h["final_v2_combined"] == FINAL_V2_HASH and h["final_v2_files_ok"]
    checks["calendar_v3_hash_ok"] = h["calendar_v3_combined"] == CALV3_HASH and h["calendar_v3_files_ok"]
    checks["leakage"] = leakage()
    pm = {}
    for s in SEEDS:
        e4m = read_json(E4R / "prefixes" / ("A_seed%d" % s) / "manifest.json")
        pm[str(s)] = canonical_json(prefix_metadata(s)) == canonical_json(e4m["metadata"])
    checks["prefix_metadata_equals_e4"] = pm
    plans, summ, problems = {}, {}, []
    for s in SEEDS:
        plans[s] = build_plans(s)
        again = build_plans(s)
        fp_sets = defaultdict(set)
        for arm, p in plans[s].items():
            if plan_signature(p) != plan_signature(again[arm]):
                problems.append("%d %s: plan not deterministic" % (s, arm))
            b = p["budget_input_tokens"]
            if p["actual_input_tokens"] > b or p["unused_input_tokens"] > 0.01 * b:
                problems.append("%d %s: budget use %d/%d" % (s, arm, p["actual_input_tokens"], b))
            ref = p["e3_plan"]["reference_counts"]
            if min(ref.values()) < N_POSITIONS or len(p["items"]) < N_POSITIONS:
                problems.append("%d %s: < %d rows somewhere -> insertion positions would differ (%s, %d)"
                                % (s, arm, N_POSITIONS, ref, len(p["items"])))
            if steps_for(len(p["items"])) != steps_for(ref["tf25"]):
                problems.append("%d %s: optimizer steps %d != tf25 %d" % (s, arm, steps_for(len(p["items"])), steps_for(ref["tf25"])))
            e = p["e3_plan"]
            if e["kind"] == "db_dose":
                if p["target_samples_by_family"].get("database", 0) != e["k"]:
                    problems.append("%d %s: database targets != k" % (s, arm))
                fp_sets[e["draw"]].add((tuple(e["fp_target_ids"]), tuple(e["fp_uniform_ids"])))
                fp_sets[0].add((tuple(e["fp_target_ids"]), tuple(e["fp_uniform_ids"])))
                if any(i.get("target") and i["family"] == "database" and i["episode_id"] not in e["db_target_ids"]
                       for i in p["items"]):
                    problems.append("%d %s: stray DB target" % (s, arm))
            elif any(i["family"] != "calendar" for i in p["items"]):
                problems.append("%d %s: non-Calendar item" % (s, arm))
            summ["%d %s" % (s, arm)] = {
                "budget": b, "actual": p["actual_input_tokens"], "items": len(p["items"]),
                "optimizer_steps_expected": steps_for(len(p["items"])), "tf25_steps": steps_for(ref["tf25"]),
                "reference_counts": ref, "target_samples_by_family": p["target_samples_by_family"],
                "db_target_tokens": e.get("db_target_tokens"), "db_replay_tokens": e.get("db_replay_tokens"),
                "db_unique_samples": e.get("db_unique_samples"), "fp_tokens": e.get("fp_tokens"),
                "tokens_by_family": p["actual_tokens_by_family"]}
        if len(fp_sets[0]) != 1:
            problems.append("%d: File/Python blocks differ across doses/draws" % s)
        for pre in ("dose_db", "dose2_db"):
            dbs = [plans[s][pre + str(k)]["e3_plan"]["db_target_ids"] for k in DOSES if (pre + str(k)) in plans[s]]
            if any(dbs[i] != dbs[i + 1][:len(dbs[i])] for i in range(len(dbs) - 1)):
                problems.append("%d %s*: doses not nested" % (s, pre))
    checks["plans"] = summ
    checks["plan_problems"] = problems
    if write_plans:
        for s in SEEDS:
            for arm, p in plans[s].items():
                write_json(OUT / "plans" / ("A_seed%d_%s.json" % (s, arm)), p)
    else:
        for s in SEEDS:
            for arm, p in plans[s].items():
                f = OUT / "plans" / ("A_seed%d_%s.json" % (s, arm))
                if not f.exists() or plan_signature(read_json(f)) != plan_signature(p):
                    problems.append("%d %s: frozen plan missing or differs" % (s, arm))
    checks["ok"] = (checks["final_v2_hash_ok"] and checks["calendar_v3_hash_ok"] and checks["leakage"]["ok"]
                    and all(pm.values()) and not problems)
    return checks


def build() -> None:
    if (OUT / "manifest.json").exists():
        raise SystemExit("data_ext_e3/manifest.json exists; refusing to overwrite")
    checks = verify(write_plans=True)
    write_json(OUT / "checks.json", checks)
    write_json(OUT / "manifest.json", {
        "created_by": "fac_tinyagent/e3_data.py", "created": __import__("time").strftime("%Y-%m-%d %H:%M:%S %z"),
        "arms": ARMS, "reused_from_e4": REUSED, "job_order_e3a_per_seed": JOB_ORDER_A,
        "job_order_e3b_per_seed": JOB_ORDER_B, "job_order_e3b2_optional_per_seed": JOB_ORDER_B2, "seeds": SEEDS,
        "chain_order": "E3-A seed 08 -> 09 -> 10, then E3-B seed 08 -> 09 -> 10 (E3-B2 only if E3_WITH_DRAW2=1)",
        "doses": DOSES, "dose_unit": "1 distinct Database target-type episode (E4 target_ids['database'], "
                                    "template target_db_filter_top), executed once; nested per seed",
        "inputs": checks["hashes"], "plans_dir": "plans/", "checks_ok": checks["ok"],
        "plan_files": {p.name: sha256_file(p) for p in sorted((OUT / "plans").glob("*.json"))}})
    print("E3 data built, checks ok =", checks["ok"], checks["plan_problems"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.verify:
        c = verify()
        print("ok", c["ok"], c["plan_problems"])
        raise SystemExit(0 if c["ok"] else 1)
    build()


if __name__ == "__main__":
    main()
