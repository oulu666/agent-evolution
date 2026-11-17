"""[ext 2026-11-14] P3「条数 vs 时机」拆分实验（E3B2_PREREG_AMEND_20261114_p3_count_timing_ZH.md）。

臂（三种子 20261108/09/10，同一 A_seed* Calendar step-80 prefix，同 replay 池、同 token 预算、23 次 optimizer 更新）：
  dose_db1_pos127 ：源 data_ext_e3 dose_db1；唯一 DB target 与「第 127 位那一段的最后一个条目」交换。
  dose_db4_late   ：源 data_ext_e3 dose_db4；4 条 DB target 全部放到第 151 位那一段（2 个槽）+ 第 159 位那一段的最后 2 个槽。
  dose_db1_pos95  ：源 data_ext_e3 dose_db1；唯一 DB target 与「第 95 位那一段的最后一个条目」交换。
移动方式与 p2_timing 相同：与目标槽上的条目交换，其它条目不动。不设 sham 臂。
训练 / 评测 / 开跑前检查与 p2_timing 完全相同（复用 p2_timing 的函数体，只换目录）。
只写 data_ext_p3_count_timing/ 与 runs_ext_p3_count_timing/。
用法：python -m fac_tinyagent.p3_count_timing --phase build|show|dry|queue|summarize
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List

from .utils import ensure_dir, read_json, read_jsonl, sha256_file, write_json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data_ext_p3_count_timing"
RUNS = ROOT / "runs_ext_p3_count_timing"
EVAL = RUNS / "evaluation"
TIM = ROOT / "runs_ext_e3b2_timing"          # dose_db1_pos143（只读）
STOP = ROOT / "logs_ext" / "p3_20261114.stop"
PREREG = "E3B2_PREREG_AMEND_20261114_p3_count_timing_ZH.md"
SEEDS = [20261108, 20261109, 20261110]
SRC = {"dose_db1_pos127": "dose_db1", "dose_db4_late": "dose_db4", "dose_db1_pos95": "dose_db1"}
ARMS = list(SRC)                               # 队列顺序：先拆分核心两臂，再 pos95
POSITIONS = [87, 95, 103, 111, 119, 127, 135, 143, 151, 159]
ACC, BETA1 = 8, 0.9
STEPS_EXPECTED = 23
FULL = ["natv2_database", "natv2_file", "natv2_python", "db_nontarget", "v3fix", "calendar_v3",
        "p2_file", "p2_python", "p2_database"]
TKEY = "target_db_filter_top"


def log(m: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), m, flush=True)


def label(seed: int, arm: str) -> str:
    return "A_seed%d_%s" % (seed, arm)


def ckpt(seed: int, arm: str) -> Path:
    return RUNS / "branches" / label(seed, arm) / "checkpoint"


def src_plan(seed: int, arm: str) -> Path:
    return ROOT / "data_ext_e3" / "plans" / ("A_seed%d_%s.json" % (seed, SRC[arm]))


def seg_bounds(n: int) -> List[range]:
    return [range(i * n // len(POSITIONS), (i + 1) * n // len(POSITIONS)) for i in range(len(POSITIONS))]


def segment_of(index: int, n: int) -> int:
    for i, r in enumerate(seg_bounds(n)):
        if index in r:
            return i
    raise ValueError(index)


def mom(after: List[int]) -> float:
    return sum(1 - BETA1 ** a for a in after)


# ------------------------------------------------------------------ plans
def source_after_by_index(seed: int, arm: str, items: List[Dict[str, Any]]) -> List[int]:
    """源臂实际训练日志：按 microstep 排序的 replay 条目 = 计划顺序；返回每个下标的「之后更新次数」。"""
    from . import p1_run as P
    ck = P.ckpt_path(seed, SRC[arm])
    L = read_jsonl(ck / "training_log.jsonl")
    total = read_json(ck / "train_summary.json")["optimizer_steps"]
    rep = sorted([x for x in L if x["kind"] != "new"], key=lambda x: x["microstep"])
    if [x["episode_id"] for x in rep] != [i["episode_id"] for i in items]:
        raise SystemExit("%s %d: source training order != plan order" % (arm, seed))
    if total != STEPS_EXPECTED:
        raise SystemExit("%s %d: source steps %d" % (arm, seed, total))
    return [total - ((x["microstep"] - 1) // ACC + 1) + 1 for x in rep]


def dest_slots(arm: str, n: int) -> List[int]:
    b = seg_bounds(n)
    if arm == "dose_db1_pos127":
        return [b[POSITIONS.index(127)][-1]]
    if arm == "dose_db1_pos95":
        return [b[POSITIONS.index(95)][-1]]
    if arm == "dose_db4_late":
        s151, s159 = list(b[POSITIONS.index(151)]), list(b[POSITIONS.index(159)])
        if len(s151) != 2 or len(s159) < 2:
            raise SystemExit("unexpected segment sizes %s %s" % (s151, s159))
        return s151 + s159[-2:]
    raise KeyError(arm)


def make_plan(seed: int, arm: str) -> Dict[str, Any]:
    src = src_plan(seed, arm)
    p = read_json(src)
    items = p["items"]
    n = len(items)
    t_idx = [i for i, it in enumerate(items) if TKEY in it["episode_id"]]
    want = {"dose_db1": 1, "dose_db4": 4}[SRC[arm]]
    if len(t_idx) != want:
        raise SystemExit("%s %d: %d DB targets, expected %d" % (arm, seed, len(t_idx), want))
    dest = dest_slots(arm, n)
    move_from = [i for i in t_idx if i not in dest]
    free = [j for j in dest if j not in t_idx]
    if len(move_from) != len(free):
        raise SystemExit("bad slot bookkeeping")
    q = copy.deepcopy(p)
    swaps = []
    for i, j in zip(sorted(move_from), sorted(free)):
        q["items"][i], q["items"][j] = q["items"][j], q["items"][i]
        swaps.append({"target_id": items[i]["episode_id"], "from_index": i, "from_position": POSITIONS[segment_of(i, n)],
                      "to_index": j, "to_position": POSITIONS[segment_of(j, n)], "swapped_item": items[j]["episode_id"]})
    after_idx = source_after_by_index(seed, arm, items)
    t_new = [i for i, it in enumerate(q["items"]) if TKEY in it["episode_id"]]
    if sorted(t_new) != sorted(dest):
        raise SystemExit("targets not in destination slots")
    pred = [{"target": q["items"][i]["episode_id"].rsplit("-", 1)[1], "index": i, "position": POSITIONS[segment_of(i, n)],
             "after": after_idx[i]} for i in t_new]
    src_t = [{"target": items[i]["episode_id"].rsplit("-", 1)[1], "index": i, "position": POSITIONS[segment_of(i, n)],
              "after": after_idx[i]} for i in t_idx]
    q["p3_amend"] = {"arm": arm, "source_arm": SRC[arm], "source_plan": str(src.relative_to(ROOT)),
                     "source_sha256": sha256_file(src), "n_items": n, "swaps": swaps,
                     "targets_source": src_t, "targets_predicted": pred,
                     "sum_after_source": sum(t["after"] for t in src_t), "mom_source": round(mom([t["after"] for t in src_t]), 4),
                     "sum_after_pred": sum(t["after"] for t in pred), "mom_pred": round(mom([t["after"] for t in pred]), 4),
                     "prereg": PREREG}
    # 不变量：条目集合、条目数、各段条目数、token 预算
    assert sorted(i["episode_id"] for i in q["items"]) == sorted(i["episode_id"] for i in items)
    assert sum(i["input_tokens"] for i in q["items"]) == p["actual_input_tokens"]
    assert sum(i["supervised_tokens"] for i in q["items"]) == p["actual_supervised_tokens"]
    assert q["budget_input_tokens"] == p["budget_input_tokens"] and len(q["items"]) == n
    return q


def build() -> None:
    if (DATA / "manifest.json").exists():
        raise SystemExit("data_ext_p3_count_timing/manifest.json exists; refusing to overwrite")
    from . import p1_run as P
    ensure_dir(DATA / "plans")
    summ = {}
    for s in SEEDS:
        for arm in ARMS:
            q = make_plan(s, arm)
            if json.dumps(make_plan(s, arm), sort_keys=True) != json.dumps(q, sort_keys=True):
                raise SystemExit("not deterministic")
            base = read_json(P.ckpt_path(s, SRC[arm]) / "train_summary.json")
            a = q["p3_amend"]
            a["base_optimizer_steps"] = base["optimizer_steps"]
            a["base_replay_input_tokens"] = base.get("replay_input_tokens")
            write_json(DATA / "plans" / ("A_seed%d_%s.json" % (s, arm)), q)
            summ["%d %s" % (s, arm)] = a
    write_json(DATA / "manifest.json", {
        "created_by": "fac_tinyagent/p3_count_timing.py", "created": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "prereg": PREREG + " (written before training)", "arms": ARMS, "seeds": SEEDS, "source_arms": SRC,
        "steps_expected": STEPS_EXPECTED, "summary": summ,
        "plan_files": {p.name: sha256_file(p) for p in sorted((DATA / "plans").glob("*.json"))}})
    log("p3 plans frozen")


def dry() -> None:
    """CPU 检查：清单哈希、计划 vs 源计划的预算 / token / 条目数 / 条目多重集合、源臂步数 = 23。"""
    man = read_json(DATA / "manifest.json")
    for name, h in man["plan_files"].items():
        assert sha256_file(DATA / "plans" / name) == h, name
    for s in SEEDS:
        for arm in ARMS:
            q = read_json(DATA / "plans" / ("A_seed%d_%s.json" % (s, arm)))
            p = read_json(src_plan(s, arm))
            assert q["budget_input_tokens"] == p["budget_input_tokens"]
            assert sum(i["input_tokens"] for i in q["items"]) == p["actual_input_tokens"]
            assert len(q["items"]) == len(p["items"])
            assert q["p3_amend"]["base_optimizer_steps"] == STEPS_EXPECTED
            key = lambda it: json.dumps(it, sort_keys=True)
            assert sorted(map(key, q["items"])) == sorted(map(key, p["items"])), "item multiset differs"
            # 运行期 pool 的逐条核对（family,row_index,episode_id,tokens）在训练时由 plan_override 完成
            diff = [i for i, (a, b) in enumerate(zip(q["items"], p["items"])) if a["episode_id"] != b["episode_id"]]
            a = q["p3_amend"]
            print("%d %-16s n=%d budget=%d tokens=%d changed_idx=%s targets=%s sum_after=%d mom=%.3f (source sum_after=%d mom=%.3f)" % (
                s, arm, len(q["items"]), q["budget_input_tokens"], sum(i["input_tokens"] for i in q["items"]), diff,
                ["T-%s@%d/%d" % (t["target"], t["position"], t["after"]) for t in a["targets_predicted"]],
                a["sum_after_pred"], a["mom_pred"], a["sum_after_source"], a["mom_source"]))
    print("DRY OK")


# ------------------------------------------------------------------ safety
def check_safe() -> None:
    if STOP.exists():
        raise SystemExit("stop flag %s present" % STOP)
    from .p0_run import refuse_if_game
    refuse_if_game()


# ------------------------------------------------------------------ train
def prep_prefix(seed: int) -> Path:
    src, dst = ROOT / "runs_ext_e4" / "prefixes" / ("A_seed%d" % seed), RUNS / "prefixes" / ("A_seed%d" % seed)
    m = read_json(src / "manifest.json")
    if (dst / "manifest.json").exists():
        if sha256_file(dst / "training_state.pt") != m["state_sha256"] or read_json(dst / "manifest.json") != m:
            raise SystemExit("p3 prefix copy differs for %d" % seed)
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


def target_timing(ck: Path) -> Dict[str, Any]:
    L = read_jsonl(ck / "training_log.jsonl")
    total = read_json(ck / "train_summary.json")["optimizer_steps"]
    tg = [{"target": x["episode_id"].rsplit("-", 1)[1], "position": x["new_position"], "microstep": x["microstep"],
           "after": total - ((x["microstep"] - 1) // ACC + 1) + 1} for x in L if TKEY in x["episode_id"]]
    af = [t["after"] for t in tg]
    return {"targets": tg, "n": len(tg), "sum_after": sum(af), "mom": round(mom(af), 4), "total_steps": total}


def train(seed: int, arm: str) -> Dict[str, Any]:
    from . import e3_data as D
    from .e3_run import guards, v3_leakage_guard
    from .e3_train import train_replay_stage_e3
    from .e4_run import CALENDAR_PATH, DB_PATH, OLD, leakage_guard, start_adapter
    from .replay_study import config_for
    man = read_json(DATA / "manifest.json")
    for name, h in man["plan_files"].items():
        if sha256_file(DATA / "plans" / name) != h:
            raise SystemExit("p3 plan changed: %s" % name)
    guards()
    frozen = read_json(DATA / "plans" / ("A_seed%d_%s.json" % (seed, arm)))
    run = ckpt(seed, arm).parent
    if (ckpt(seed, arm) / "train_summary.json").exists():
        log("skip train %s" % run.name)
        return read_json(ckpt(seed, arm) / "train_summary.json")
    if run.exists():
        aside = run.parent / (run.name + "_partial_%d" % int(time.time()))
        log("moving partial run aside: %s" % aside)
        shutil.move(str(run), str(aside))
    pdir = prep_prefix(seed)
    target_ids = read_json(ROOT / "data_ext_e4" / "manifest.json")["target_ids"]
    config = config_for("A", seed, batch_size=32)
    stage = dict(config["stages"][4], index=4)
    new_path = str(ROOT / "data_phase2" / "calendar" / "train.jsonl")
    probes = {f: str(ROOT / "data_ext_monitor_v2" / (f + ".jsonl")) for f in OLD}
    pools = {f: str(ROOT / "data_ext_e4" / "pool" / (f + ".jsonl")) for f in OLD}
    rows = read_jsonl(new_path) + [r for p in pools.values() for r in read_jsonl(p)] \
        + [r for p in probes.values() for r in read_jsonl(p)]
    leakage_guard(rows)
    v3_leakage_guard(rows)

    def override(pools, extra_pools, budget, seed):  # noqa
        if budget != frozen["budget_input_tokens"]:
            raise RuntimeError("runtime budget %d != frozen %d" % (budget, frozen["budget_input_tokens"]))
        idx = {(f, r["row_index"], r["episode_id"]): r for f, rs in pools.items() for r in rs}
        for it in frozen["items"]:
            r = idx.get((it["family"], it["row_index"], it["episode_id"]))
            if r is None or r["input_tokens"] != it["input_tokens"] or r["supervised_tokens"] != it["supervised_tokens"]:
                raise RuntimeError("frozen p3 item does not match runtime pool: %s" % it["episode_id"])
        log("p3 plan %s items %d targets %s" % (arm, len(frozen["items"]),
            [(t["target"], t["position"], t["after"]) for t in frozen["p3_amend"]["targets_predicted"]]))
        return copy.deepcopy(frozen)

    log("TRAIN %s" % run.name)
    s = train_replay_stage_e3(
        config=config, stage=stage, train_path=new_path, old_train_paths=pools, probe_paths=probes,
        previous_adapter=str(start_adapter(seed)), output_dir=str(ckpt(seed, arm)), db_path=str(DB_PATH),
        calendar_path=str(CALENDAR_PATH), mode="targeted", replay_ratio=0.10, uniform_floor=0.2,
        prefix_dir=str(pdir), target_ids=target_ids, target_fraction=D.TF25,
        target_family_weights={f: 1.0 / len(OLD) for f in OLD},
        plan_override=override, extra_replay_family=None, require_prefix_reuse=True)
    if s.get("optimizer_steps") != STEPS_EXPECTED:
        raise SystemExit("optimizer steps %s != %d" % (s.get("optimizer_steps"), STEPS_EXPECTED))
    tt = target_timing(ckpt(seed, arm))
    pred = frozen["p3_amend"]["targets_predicted"]
    if sorted((t["position"], t["after"]) for t in tt["targets"]) != sorted((t["position"], t["after"]) for t in pred):
        raise SystemExit("actual target timing %s != predicted %s" % (tt["targets"], pred))
    write_json(run / "p3_meta.json", {"arm": arm, "seed": seed,
                                      "plan_sha256": sha256_file(DATA / "plans" / ("A_seed%d_%s.json" % (seed, arm))),
                                      "prefix_state_sha256": s.get("shared_prefix_state_sha256"),
                                      "optimizer_steps": s.get("optimizer_steps"), "replay_input_tokens": s.get("replay_input_tokens"),
                                      "target_timing": tt, "finished": time.strftime("%Y-%m-%d %H:%M:%S %z")})
    log("TRAIN done %s steps=%s replay_tokens=%s sum_after=%d mom=%.3f" % (run.name, s.get("optimizer_steps"),
        s.get("replay_input_tokens"), tt["sum_after"], tt["mom"]))
    return s


# ------------------------------------------------------------------ eval
def evaluate(seed: int, arm: str) -> None:
    from .p1_run import suite_rows
    ck = ckpt(seed, arm)
    out = EVAL / label(seed, arm)
    todo = [s for s in FULL if not (out / s / "stage_report.json").exists()]
    if not todo:
        log("skip eval %s" % label(seed, arm))
        return
    check_safe()
    from .replay_study import config_for
    from .sft.evaluate import evaluate_family, free_model, load_eval_model
    config = config_for("A", seed, batch_size=1)
    config["evaluation"]["batch_size"] = 1
    t_all = time.time()
    log("EVAL %s suites=%s" % (label(seed, arm), todo))
    model, tok = load_eval_model(config, str(ck))
    stage = {"name": "P3_B1_" + label(seed, arm), "index": 4, "adapter": str(ck)}
    try:
        for s in todo:
            check_safe()
            rows, db, cal, h = suite_rows(s)
            t0 = time.time()
            rep = evaluate_family(model, tok, rows, config, stage, out / s, db, cal)
            if rep["evaluation_protocol"]["batch_size"] != 1:
                raise SystemExit("protocol is not B1")
            write_json(out / s / "p3_meta.json", {"suite": s, "rows_sha256": h, "n": len(rows), "checkpoint": str(ck),
                                                 "adapter_sha256": sha256_file(ck / "adapter_model.safetensors"),
                                                 "protocol": "Protocol-B1", "seconds": round(time.time() - t0, 1),
                                                 "finished": time.strftime("%Y-%m-%d %H:%M:%S %z")})
            log("  done %s %s n=%d %.1fs" % (label(seed, arm), s, len(rows), time.time() - t0))
    finally:
        free_model(model)
    log("EVAL done %s in %.1fs" % (label(seed, arm), time.time() - t_all))


def queue() -> None:
    for arm in ARMS:                 # 臂优先：先把三种子的 pos127 / db4_late 做完，pos95 最后
        for s in SEEDS:
            check_safe()
            train(s, arm)
            evaluate(s, arm)
            try:
                summarize()
            except Exception as exc:
                log("WARN summarize failed: %r" % exc)
    log("QUEUE COMPLETE")


# ------------------------------------------------------------------ summary (CPU)
REFS = ["dose_db1", "dose_db1_pos143", "dose_db4"]
PAIRS = [("dose_db1_pos127", "dose_db4_late"),      # 核心：同 Σafter≈6，1 条早 vs 4 条晚
         ("dose_db1_pos95", "dose_db1_pos127"),     # 暴露单调 / 饱和 / 被覆盖
         ("dose_db1_pos127", "dose_db1"), ("dose_db1_pos127", "dose_db1_pos143"), ("dose_db1_pos127", "dose_db4"),
         ("dose_db4_late", "dose_db4"), ("dose_db4_late", "dose_db1"), ("dose_db4_late", "dose_db1_pos143"),
         ("dose_db1_pos95", "dose_db1"), ("dose_db1_pos95", "dose_db1_pos143"), ("dose_db1_pos95", "dose_db4")]
SIDE = ["db_nontarget", "natv2_python", "natv2_file", "calendar_v3", "v3fix", "p2_database", "p2_python", "p2_file"]
TIE = 0.10   # 预注册 §3：|均值差| ≤ 0.10（3 题）且方向不一致 → 「≈」


def _res(path: Path, suite: str):
    from .p1_run import suite_rows
    if not path.exists():
        return None
    res = read_jsonl(path)
    rows, _, _, _ = suite_rows(suite)
    return res if len(res) == len(rows) else None


def _paths(s: int, arm: str):
    from . import p1_run as P
    if arm in ARMS:
        ck, ev = ckpt(s, arm), EVAL / label(s, arm)
        return ck, (lambda su: ev / su / "results.jsonl")
    if arm == "dose_db1_pos143":
        ck, ev = TIM / "branches" / label(s, arm) / "checkpoint", TIM / "evaluation" / label(s, arm)
        return ck, (lambda su: ev / su / "results.jsonl")
    return P.ckpt_path(s, arm), (lambda su, a=arm: P.results_path(s, a, su))


def _pair(get, a, b, key):
    d = []
    for s in SEEDS:
        x, y = get.get((s, a), {}).get(key), get.get((s, b), {}).get(key)
        d.append(None if x is None or y is None else x - y)
    done = [v for v in d if v is not None]
    return {"per_seed": d, "mean": statistics.mean(done) if done else None,
            "n_pos": sum(v > 1e-9 for v in done), "n_zero": sum(abs(v) <= 1e-9 for v in done),
            "n_neg": sum(v < -1e-9 for v in done), "n_seeds": len(done)}


def _verdict(pr, kind):
    if pr["n_seeds"] < 3:
        return None
    if kind == "count":       # pos127 − db4_late
        if pr["n_neg"] == 3:
            return "db4_late > pos127（三种子方向一致）：多条不同 target（多样性）在相同 Σafter 下有独立价值"
        if pr["n_pos"] == 3:
            return "pos127 > db4_late（三种子方向一致）：早插入优于多样性"
        if abs(pr["mean"]) <= TIE:
            return "pos127 ≈ db4_late：暴露量（Σafter）是主要驱动"
        return "不一致：方向不一致且 |均值差| > %.2f，需加种子或控制条目身份" % TIE
    else:                     # pos95 − pos127
        if pr["n_pos"] == 3:
            return "pos95 > pos127（三种子方向一致）：暴露继续单调起作用"
        if pr["n_neg"] == 3:
            return "pos95 < pos127（三种子方向一致）：过早插入被后续 Calendar 更新覆盖"
        if abs(pr["mean"]) <= TIE:
            return "pos95 ≈ pos127：在 Σafter≈6 之后饱和"
        return "不一致：方向不一致且 |均值差| > %.2f" % TIE


def summarize() -> None:
    from . import p1_run as P
    rows = []
    for s in SEEDS:
        for arm in ARMS + REFS:
            ck, rp = _paths(s, arm)
            if not (ck / "train_summary.json").exists():
                continue
            tt = target_timing(ck)
            r = {"seed": s, "arm": arm, "n_target": tt["n"], "sum_after": tt["sum_after"], "mom": tt["mom"],
                 "targets": ["T-%s@%s/%d" % (t["target"], t["position"], t["after"]) for t in tt["targets"]],
                 "optimizer_steps": tt["total_steps"]}
            res = _res(rp("natv2_database"), "natv2_database")
            if res:
                n = len(res)
                r.update({"main": sum(bool(x["joint_success"]) for x in res) / n,
                          "tool": sum(bool(x["tool_correct"]) for x in res) / n,
                          "arguments": sum(bool(x["arguments_correct"]) for x in res) / n,
                          "final": sum(bool(x["final_correct"]) for x in res) / n,
                          "correct_ids": sorted(x["episode_id"].rsplit("-", 1)[1] for x in res if x["joint_success"])})
            for su in SIDE:
                rr = _res(rp(su), su)
                if rr:
                    r[su] = sum(P._ok(x, su) for x in rr) / len(rr) if su == "natv2_file" else \
                        sum(bool(x["joint_success"]) for x in rr) / len(rr)
            rows.append(r)
    get = {(r["seed"], r["arm"]): r for r in rows}
    pairs = {}
    for a, b in PAIRS:
        pairs["%s − %s" % (a, b)] = {k: _pair(get, a, b, k) for k in ("main", "tool", "arguments", "final", "db_nontarget")}
    verdicts = {"count_vs_timing": _verdict(pairs["dose_db1_pos127 − dose_db4_late"]["main"], "count"),
                "early_monotonic": _verdict(pairs["dose_db1_pos95 − dose_db1_pos127"]["main"], "early")}
    means = {}
    for arm in ARMS + REFS:
        v = [get[(s, arm)] for s in SEEDS if (s, arm) in get and "main" in get[(s, arm)]]
        if v:
            means[arm] = {"n_seeds": len(v), "main": statistics.mean(x["main"] for x in v),
                          "main_sd": statistics.stdev([x["main"] for x in v]) if len(v) > 1 else None,
                          "sum_after": statistics.mean(x["sum_after"] for x in v), "mom": statistics.mean(x["mom"] for x in v)}
    out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S %z"), "prereg": PREREG, "rows": rows, "means": means,
           "pairs": pairs, "verdicts": verdicts}
    ensure_dir(RUNS)
    write_json(RUNS / "summary.json", out)
    f3 = lambda x: "—" if x is None else "%.3f" % x
    sg = lambda x: "—" if x is None else "%+.3f" % x
    md = ["# P3「条数 vs 时机」：汇总（Protocol-B1）", "",
          "生成：%s。脚本 `python -m fac_tinyagent.p3_count_timing --phase summarize`。预注册：`%s`。" % (out["generated"], PREREG), "",
          "主指标：B1 nat v2 `db.filter_cmp_top` Joint Success（30 题；T0 为 0，属能力缺口及其恢复）。只报方向（「方向一致」= 三种子同号），不做显著性陈述。", "",
          "## 1. 逐种子（主指标 + 副作用）", "",
          "| 种子 | 臂 | n | target（T@位置/之后更新） | Σafter | mom | 主指标 | tool / args / final | 非 target 40 | nat Python | nat File | Calendar v3 | v3fix | p2 DB / Py / File |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    order = ["dose_db1", "dose_db1_pos143", "dose_db1_pos127", "dose_db1_pos95", "dose_db4", "dose_db4_late"]
    for s in SEEDS:
        for a in order:
            r = get.get((s, a))
            if not r:
                continue
            md.append("| %s | %s | %d | %s | %d | %.3f | %s | %s / %s / %s | %s | %s | %s | %s | %s | %s / %s / %s |" % (
                str(s)[-2:], a, r["n_target"], "；".join(r["targets"]) or "—", r["sum_after"], r["mom"], f3(r.get("main")),
                f3(r.get("tool")), f3(r.get("arguments")), f3(r.get("final")), f3(r.get("db_nontarget")), f3(r.get("natv2_python")),
                f3(r.get("natv2_file")), f3(r.get("calendar_v3")), f3(r.get("v3fix")), f3(r.get("p2_database")),
                f3(r.get("p2_python")), f3(r.get("p2_file"))))
    md += ["", "## 2. 三种子均值", "", "| 臂 | 种子数 | Σafter 均值 | mom 均值 | 主指标均值 | 样本标准差 |", "|---|---|---|---|---|---|"]
    for a in order:
        m = means.get(a)
        if m:
            md.append("| %s | %d | %.2f | %.3f | %.3f | %s |" % (a, m["n_seeds"], m["sum_after"], m["mom"], m["main"], f3(m["main_sd"])))
    md += ["", "## 3. 配对差（同种子；正/零/负 = 种子数）", "",
           "| 对比 | 指标 | 08 | 09 | 10 | 均值 | 正/零/负 |", "|---|---|---|---|---|---|---|"]
    for k, v in pairs.items():
        for met in ("main", "tool", "arguments", "final", "db_nontarget"):
            pr = v[met]
            if pr["n_seeds"] == 0:
                continue
            md.append("| %s | %s | %s | %s | %d/%d/%d |" % (k, met, " | ".join(sg(x) for x in pr["per_seed"]), sg(pr["mean"]),
                                                          pr["n_pos"], pr["n_zero"], pr["n_neg"]))
    md += ["", "## 4. 预注册判定（§3）", "",
           "- 条数 vs 时机（dose_db1_pos127 − dose_db4_late）：%s" % (verdicts["count_vs_timing"] or "尚未完成三种子"),
           "- 早插入是否继续有效（dose_db1_pos95 − dose_db1_pos127）：%s" % (verdicts["early_monotonic"] or "尚未完成三种子"),
           "", "## 5. 答对的题（主指标 30 题，题号）", ""]
    for s in SEEDS:
        for a in order:
            r = get.get((s, a))
            if r and "correct_ids" in r:
                md.append("- %s %s（%d 题）：%s" % (str(s)[-2:], a, len(r["correct_ids"]), ", ".join(r["correct_ids"]) or "—"))
    md += ["", "### 5.1 同种子答对集合的交并（pos127 vs db4_late；pos95 vs pos127）", ""]
    for s in SEEDS:
        for a, b in (("dose_db1_pos127", "dose_db4_late"), ("dose_db1_pos95", "dose_db1_pos127")):
            x, y = get.get((s, a), {}).get("correct_ids"), get.get((s, b), {}).get("correct_ids")
            if x is None or y is None:
                continue
            X, Y = set(x), set(y)
            md.append("- %s %s vs %s：共同 %d；只有前者 %s；只有后者 %s" % (str(s)[-2:], a, b, len(X & Y),
                      ", ".join(sorted(X - Y)) or "—", ", ".join(sorted(Y - X)) or "—"))
    (RUNS / "summary_tables_ZH.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log("summary written")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["build", "show", "dry", "queue", "summarize"], required=True)
    a = ap.parse_args()
    if a.phase == "build":
        build()
    elif a.phase == "dry":
        dry()
    elif a.phase == "queue":
        queue()
    elif a.phase == "summarize":
        summarize()
    else:
        for s in SEEDS:
            for arm in ARMS:
                print(s, arm, json.dumps(make_plan(s, arm)["p3_amend"], ensure_ascii=False))


if __name__ == "__main__":
    main()
