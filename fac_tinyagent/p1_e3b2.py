"""[ext 2026-11-12 P1] E3-B2 experiment A (first wave): fixed target identity, change background.

Pre-registered in E3B2_PREREG_20261112_ZH.md section 3.1 (frozen before training):
  * 10 % budget (7,494 input tokens, >= 99 % used), 23 optimizer steps, A scenario,
    E4 midpoint prefix of the seed (hash-verified copy in runs_ext_e3b2/prefixes),
    E3 common_replay_positions (10 fixed positions), Calendar new data identical to E3/E4.
  * T* (one Database target row, byte-identical in every arm of a seed):
      seed 20261108: database-train-target_db_filter_top-000  (dose_db1 and b10_tf25 both contain it)
      seed 20261109 / 20261110: the single target row of that seed's dose_db1 replay_plan.json
      (read from the checkpoint, not guessed).
  * e3b2_A_target_other : T* + ordinary File/Python rows only (no Database row, no File/Python
                          target rows e4_target_file_last_match / target_median_natural).
  * e3b2_A_target_dbbg  : T* + ordinary Database background from the pre-registered list ONLY
                          (db_count, db_average, db_list_tables, db_schema_count, db_group_count;
                          db_top_n, db_filter_count and every ORDER BY+LIMIT / filter+count
                          neighbour excluded) filling the seed's dose_db1 Database block
                          (db_block_budget), rest ordinary File/Python rows.
  * T* is placed last in both arms (same insertion position), backgrounds shuffled before it.
Writes data_ext_e3b2/ (plans + manifest, refuses to overwrite) and runs_ext_e3b2/ only.
"""
from __future__ import annotations

import argparse
import math
import random
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from . import e3_data as D
from .replay_train import _fill_whole_rows, make_replay_plan
from .utils import canonical_json, ensure_dir, read_json, read_jsonl, sha256_file, write_json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data_ext_e3b2"
RUNS = ROOT / "runs_ext_e3b2"
E3D = ROOT / "data_ext_e3"
E3R = ROOT / "runs_ext_e3"
E4D = ROOT / "data_ext_e4"
E4R = ROOT / "runs_ext_e4"
MV2 = ROOT / "data_ext_monitor_v2"
SEEDS = [20261108, 20261109, 20261110]
ARMS = ["e3b2_A_target_other", "e3b2_A_target_dbbg"]
DB_BG_TEMPLATES = ["db_count", "db_average", "db_list_tables", "db_schema_count", "db_group_count"]
DB_EXCLUDED = ["db_top_n", "db_filter_count", "target_db_filter_top"]
FP_EXCLUDED = ["e4_target_file_last_match", "target_median_natural"]
SEED08_TARGET = "database-train-target_db_filter_top-000"
STEPS_EXPECTED = 23


def locked_target(seed: int) -> str:
    plan = read_json(E3R / "branches" / ("A_seed%d_dose_db1" % seed) / "checkpoint" / "replay_plan.json")
    ids = plan["e3_plan"]["db_target_ids"]
    if len(ids) != 1:
        raise SystemExit("dose_db1 of seed %d has %d DB targets" % (seed, len(ids)))
    if seed == 20261108 and ids[0] != SEED08_TARGET:
        raise SystemExit("seed 08 dose_db1 target is %s, pre-registered %s" % (ids[0], SEED08_TARGET))
    return ids[0]


def _templates() -> Dict[str, str]:
    out = {}
    for f in D.OLD:
        for r in read_jsonl(E4D / "pool" / (f + ".jsonl")):
            out[r["episode_id"]] = r["template_id"]
    return out


def build_seed(seed: int) -> Dict[str, Dict[str, Any]]:
    config, pools, extra, total_new, _ = D.prepared(seed)
    ps = int(config["seed"]) + D.PLAN_SEED_OFFSET
    budget = int(math.floor(total_new * 0.10))
    tmpl = _templates()
    tid = locked_target(seed)
    T = [r for r in pools["database"] if r["episode_id"] == tid]
    if len(T) != 1 or not T[0]["target"]:
        raise SystemExit("target %s not found exactly once as a target row" % tid)
    T = dict(T[0])
    dose1 = read_json(E3D / "plans" / ("A_seed%d_dose_db1.json" % seed))
    if dose1["e3_plan"]["db_target_ids"] != [tid]:
        raise SystemExit("frozen dose_db1 plan target differs from checkpoint plan")
    db_block = int(dose1["e3_plan"]["db_block_budget"])
    fp = {f: [dict(r) for r in pools[f] if not r["target"] and tmpl[r["episode_id"]] not in FP_EXCLUDED]
          for f in ("file", "python")}
    dbbg = [dict(r) for r in pools["database"] if not r["target"] and tmpl[r["episode_id"]] in DB_BG_TEMPLATES]

    def fill(pool_map, weights, amount, s):
        p = make_replay_plan(pool_map, weights, amount, s)
        items = [dict(i) for i in p["items"]]
        rem = amount - sum(i["input_tokens"] for i in items)
        if rem > 0:
            items += _fill_whole_rows([r for v in pool_map.values() for r in v], rem, random.Random(s + 3))
        return items

    plans = {}
    # target_other
    other = fill({"file": fp["file"], "python": fp["python"]}, {"file": 0.5, "python": 0.5},
                 budget - T["input_tokens"], ps)
    random.Random(ps + 6).shuffle(other)
    plans["e3b2_A_target_other"] = (other + [dict(T, target=True)], {"db_block_budget": 0})
    # target_dbbg
    dbi = fill({"database": dbbg}, {"database": 1.0}, db_block - T["input_tokens"], ps + 2)
    db_tok = sum(i["input_tokens"] for i in dbi) + T["input_tokens"]
    fpi = fill({"file": fp["file"], "python": fp["python"]}, {"file": 0.5, "python": 0.5}, budget - db_tok, ps)
    bg = dbi + fpi
    random.Random(ps + 6).shuffle(bg)
    plans["e3b2_A_target_dbbg"] = (bg + [dict(T, target=True)], {"db_block_budget": db_block})
    out = {}
    for arm, (items, ex) in plans.items():
        for i in items:
            i["target"] = i["episode_id"] == tid
            i["template_id"] = tmpl[i["episode_id"]]
        fam_tok = Counter()
        for i in items:
            fam_tok[i["family"]] += i["input_tokens"]
        plan = D._finish([{k: v for k, v in i.items() if k != "template_id"} for i in items], budget, {
            "families": D.OLD, "weights": {f: 1.0 / 3 for f in D.OLD},
            "target_family_weights": {"database": "fixed_single_target"}, "target_fraction": 0.0,
            "e3_plan": {"kind": "e3b2_A", "arm": arm, "target_id": tid,
                        "target_sha256": sha256_text(canonical_json(_raw_row(tid))),
                        "target_input_tokens": T["input_tokens"],
                        "target_repeats": sum(i["episode_id"] == tid for i in items),
                        "target_position": "last item (last insertion position)",
                        "db_block_budget": ex["db_block_budget"],
                        "db_background_templates": DB_BG_TEMPLATES if arm.endswith("dbbg") else [],
                        "db_excluded_templates": DB_EXCLUDED, "fp_excluded_templates": FP_EXCLUDED,
                        "tokens": {"target": T["input_tokens"],
                                   "ordinary_database": sum(i["input_tokens"] for i in items
                                                            if i["family"] == "database" and not i["target"]),
                                   "other_tools": fam_tok["file"] + fam_tok["python"],
                                   "total": sum(i["input_tokens"] for i in items)},
                        "template_counts": dict(Counter(i["template_id"] for i in items)),
                        "optimizer_steps_expected": D.steps_for(len(items)),
                        "plan_seed": ps}})
        out[arm] = plan
    return out


def sha256_text(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


_RAW: Dict[str, Dict[str, Any]] = {}


def _raw_row(eid: str) -> Dict[str, Any]:
    if not _RAW:
        for f in D.OLD:
            for r in read_jsonl(E4D / "pool" / (f + ".jsonl")):
                _RAW[r["episode_id"]] = r
    return _RAW[eid]


def check_plan(seed: int, arm: str, p: Dict[str, Any]) -> List[str]:
    probs = []
    e = p["e3_plan"]
    b = p["budget_input_tokens"]
    if not (math.ceil(0.99 * b) <= p["actual_input_tokens"] <= b):
        probs.append("budget use %d/%d" % (p["actual_input_tokens"], b))
    if e["optimizer_steps_expected"] != STEPS_EXPECTED:
        probs.append("steps %d != %d" % (e["optimizer_steps_expected"], STEPS_EXPECTED))
    if len(p["items"]) < D.N_POSITIONS:
        probs.append("fewer than 10 rows")
    tg = [i for i in p["items"] if i.get("target")]
    if len(tg) != 1 or tg[0]["episode_id"] != e["target_id"]:
        probs.append("target rows %s" % [i["episode_id"] for i in tg])
    if p["items"][-1]["episode_id"] != e["target_id"]:
        probs.append("target not last")
    for t, n in e["template_counts"].items():
        if t in DB_EXCLUDED and t != "target_db_filter_top":
            probs.append("excluded DB template %s" % t)
        if t in FP_EXCLUDED:
            probs.append("excluded File/Python target template %s" % t)
        if t.startswith("db_") and arm.endswith("target_other"):
            probs.append("DB row in target_other")
        if t.startswith("db_") and t not in DB_BG_TEMPLATES:
            probs.append("DB template outside list %s" % t)
    if e["template_counts"].get("target_db_filter_top") != 1:
        probs.append("target_db_filter_top count != 1")
    return probs


def build() -> None:
    if (DATA / "manifest.json").exists():
        raise SystemExit("data_ext_e3b2/manifest.json exists; refusing to overwrite")
    ensure_dir(DATA / "plans")
    allp, problems, summ = {}, [], {}
    for s in SEEDS:
        a = build_seed(s)
        b = build_seed(s)
        for arm in ARMS:
            if D.plan_signature(a[arm]) != D.plan_signature(b[arm]):
                problems.append("%d %s not deterministic" % (s, arm))
            problems += ["%d %s: %s" % (s, arm, x) for x in check_plan(s, arm, a[arm])]
            allp[(s, arm)] = a[arm]
            summ["%d %s" % (s, arm)] = {"items": len(a[arm]["items"]), **a[arm]["e3_plan"]["tokens"],
                                        "target": a[arm]["e3_plan"]["target_id"],
                                        "templates": a[arm]["e3_plan"]["template_counts"]}
        # T* byte-identical across arms of a seed
        t0 = {allp[(s, arm)]["e3_plan"]["target_sha256"] for arm in ARMS}
        if len(t0) != 1:
            problems.append("%d: target hash differs across arms" % s)
    if problems:
        raise SystemExit("E3-B2 plan problems: %s" % problems)
    for (s, arm), p in allp.items():
        write_json(DATA / "plans" / ("A_seed%d_%s.json" % (s, arm)), p)
    write_json(DATA / "manifest.json", {
        "created_by": "fac_tinyagent/p1_e3b2.py", "created": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "prereg": "E3B2_PREREG_20261112_ZH.md section 3.1 (frozen before the first arm)",
        "arms": ARMS, "seeds": SEEDS, "locked_targets": {str(s): locked_target(s) for s in SEEDS},
        "db_background_templates": DB_BG_TEMPLATES, "db_excluded_templates": DB_EXCLUDED,
        "fp_excluded_templates": FP_EXCLUDED, "budget_ratio": 0.10, "optimizer_steps": STEPS_EXPECTED,
        "summary": summ,
        "inputs": {"e4_pool": {f: sha256_file(E4D / "pool" / (f + ".jsonl")) for f in D.OLD},
                   "e3_dose_db1_plans": {str(s): sha256_file(E3D / "plans" / ("A_seed%d_dose_db1.json" % s)) for s in SEEDS},
                   "e4_prefix_state": {str(s): read_json(E4R / "prefixes" / ("A_seed%d" % s) / "manifest.json")["state_sha256"] for s in SEEDS}},
        "plan_files": {p.name: sha256_file(p) for p in sorted((DATA / "plans").glob("*.json"))}})
    print("E3-B2 plans frozen", summ, flush=True)


def prep_prefix(seed: int) -> Path:
    src, dst = E4R / "prefixes" / ("A_seed%d" % seed), RUNS / "prefixes" / ("A_seed%d" % seed)
    m = read_json(src / "manifest.json")
    if (dst / "manifest.json").exists():
        if sha256_file(dst / "training_state.pt") != m["state_sha256"] or read_json(dst / "manifest.json") != m:
            raise SystemExit("e3b2 prefix copy differs for %d" % seed)
        return dst
    if sha256_file(src / "training_state.pt") != m["state_sha256"]:
        raise SystemExit("E4 prefix %d hash mismatch" % seed)
    ensure_dir(dst)
    tmp = dst / "training_state.pt.tmp"
    shutil.copyfile(src / "training_state.pt", tmp)
    if sha256_file(tmp) != m["state_sha256"]:
        raise SystemExit("prefix copy hash mismatch %d" % seed)
    tmp.rename(dst / "training_state.pt")
    shutil.copyfile(src / "manifest.json", dst / "manifest.json")
    return dst


def ckpt(seed: int, arm: str) -> Path:
    return RUNS / "branches" / ("A_seed%d_%s" % (seed, arm)) / "checkpoint"


def train(seed: int, arm: str) -> Dict[str, Any]:
    from .e3_run import guards, v3_leakage_guard
    from .e3_train import train_replay_stage_e3
    from .e4_run import CALENDAR_PATH, DB_PATH, OLD, leakage_guard, start_adapter
    from .replay_study import config_for
    man = read_json(DATA / "manifest.json")
    for name, h in man["plan_files"].items():
        if sha256_file(DATA / "plans" / name) != h:
            raise SystemExit("data_ext_e3b2 plan changed: %s" % name)
    guards()
    frozen = read_json(DATA / "plans" / ("A_seed%d_%s.json" % (seed, arm)))
    run = ckpt(seed, arm).parent
    if (ckpt(seed, arm) / "train_summary.json").exists():
        print("skip train", run.name, flush=True)
        return read_json(ckpt(seed, arm) / "train_summary.json")
    if run.exists():
        aside = run.parent / (run.name + "_partial_%d" % int(time.time()))
        print("moving partial run aside:", aside, flush=True)
        shutil.move(str(run), str(aside))
    pdir = prep_prefix(seed)
    target_ids = read_json(E4D / "manifest.json")["target_ids"]
    config = config_for("A", seed, batch_size=32)
    stage = dict(config["stages"][4], index=4)
    new_path = str(ROOT / "data_phase2" / "calendar" / "train.jsonl")
    probes = {f: str(MV2 / (f + ".jsonl")) for f in OLD}
    pools = {f: str(E4D / "pool" / (f + ".jsonl")) for f in OLD}
    rows = read_jsonl(new_path) + [r for p in pools.values() for r in read_jsonl(p)] \
        + [r for p in probes.values() for r in read_jsonl(p)]
    leakage_guard(rows)
    v3_leakage_guard(rows)

    def override(pools, extra_pools, budget, seed):  # noqa: seed = config seed + 104729
        if budget != frozen["budget_input_tokens"]:
            raise RuntimeError("runtime budget %d != frozen %d" % (budget, frozen["budget_input_tokens"]))
        idx = {(f, r["row_index"], r["episode_id"]): r for f, rs in pools.items() for r in rs}
        for it in frozen["items"]:
            r = idx.get((it["family"], it["row_index"], it["episode_id"]))
            if r is None or r["input_tokens"] != it["input_tokens"] or r["supervised_tokens"] != it["supervised_tokens"]:
                raise RuntimeError("frozen E3-B2 item does not match runtime pool: %s" % it["episode_id"])
        print("E3-B2 plan", arm, "tokens", frozen["actual_input_tokens"], "/", budget,
              "items", len(frozen["items"]), "target", frozen["e3_plan"]["target_id"], flush=True)
        return read_json(DATA / "plans" / ("A_seed%d_%s.json" % (seed - D.PLAN_SEED_OFFSET, arm)))

    print("train", run.name, flush=True)
    s = train_replay_stage_e3(
        config=config, stage=stage, train_path=new_path, old_train_paths=pools, probe_paths=probes,
        previous_adapter=str(start_adapter(seed)), output_dir=str(ckpt(seed, arm)), db_path=str(DB_PATH),
        calendar_path=str(CALENDAR_PATH), mode="targeted", replay_ratio=0.10, uniform_floor=0.2,
        prefix_dir=str(pdir), target_ids=target_ids, target_fraction=D.TF25,
        target_family_weights={f: 1.0 / len(OLD) for f in OLD},
        plan_override=override, extra_replay_family=None, require_prefix_reuse=True)
    if s.get("optimizer_steps") != STEPS_EXPECTED:
        raise SystemExit("optimizer steps %s != %d" % (s.get("optimizer_steps"), STEPS_EXPECTED))
    write_json(run / "e3b2_meta.json", {"arm": arm, "seed": seed, "plan_sha256": sha256_file(DATA / "plans" / ("A_seed%d_%s.json" % (seed, arm))),
                                        "prefix_reused": s.get("prefix_reused"),
                                        "prefix_state_sha256": s.get("shared_prefix_state_sha256"),
                                        "optimizer_steps": s.get("optimizer_steps"),
                                        "finished": time.strftime("%Y-%m-%d %H:%M:%S %z")})
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["build", "show"], required=True)
    a = ap.parse_args()
    if a.phase == "build":
        build()
    else:
        for s in SEEDS:
            print(s, locked_target(s))


if __name__ == "__main__":
    main()
