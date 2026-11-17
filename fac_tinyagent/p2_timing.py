"""[ext 2026-11-13] target 插入位置单变量对照（E3B2_PREREG_AMEND_20261113_timing_ZH.md）。

臂：target_other_pos143（源：data_ext_e3b2 的 e3b2_A_target_other 冻结计划）、
    dose_db1_pos143（源：data_ext_e3 的 dose_db1 冻结计划）。
改动：把 Database 的 T*（target_db_filter_top）与「第 143 位那一段的最后一个条目」交换位置，其它不变。
训练：与 p1_e3b2.train 相同的 train_replay_stage_e3 参数，plan_override 返回本目录冻结的计划。
评测：Protocol-B1，与实验 A 相同的 9 套考试（复用 p1_run.suite_rows / sft.evaluate.evaluate_family）。
只写 data_ext_e3b2_timing/ 与 runs_ext_e3b2_timing/。
用法：python -m fac_tinyagent.p2_timing --phase build|queue|summarize
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
DATA = ROOT / "data_ext_e3b2_timing"
RUNS = ROOT / "runs_ext_e3b2_timing"
EVAL = RUNS / "evaluation"
STOP = ROOT / "logs_ext" / "timing_20261113.stop"
SEEDS = [20261108, 20261109, 20261110]
ARMS = {"target_other_pos143": ROOT / "data_ext_e3b2" / "plans" / "A_seed{seed}_e3b2_A_target_other.json",
        "dose_db1_pos143": ROOT / "data_ext_e3" / "plans" / "A_seed{seed}_dose_db1.json"}
PAIRS = {"target_other_pos143": "e3b2_A_target_other", "dose_db1_pos143": "dose_db1"}
POSITIONS = [87, 95, 103, 111, 119, 127, 135, 143, 151, 159]
SEG = 7            # 第 143 位 = 第 8 段（下标 7）
STEPS_EXPECTED = 23
FULL = ["natv2_database", "natv2_file", "natv2_python", "db_nontarget", "v3fix", "calendar_v3",
        "p2_file", "p2_python", "p2_database"]


def log(m: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), m, flush=True)


def label(seed: int, arm: str) -> str:
    return "A_seed%d_%s" % (seed, arm)


def ckpt(seed: int, arm: str) -> Path:
    return RUNS / "branches" / label(seed, arm) / "checkpoint"


# ------------------------------------------------------------------ plans
def segment_of(index: int, n: int) -> int:
    for i in range(len(POSITIONS)):
        if i * n // len(POSITIONS) <= index < (i + 1) * n // len(POSITIONS):
            return i
    raise ValueError


def make_plan(seed: int, arm: str) -> Dict[str, Any]:
    src = Path(str(ARMS[arm]).format(seed=seed))
    p = read_json(src)
    items = p["items"]
    n = len(items)
    t_idx = [i for i, it in enumerate(items) if "target_db_filter_top" in it["episode_id"]]
    if len(t_idx) != 1:
        raise SystemExit("%s %d: %d DB targets" % (arm, seed, len(t_idx)))
    ti = t_idx[0]
    if segment_of(ti, n) != len(POSITIONS) - 1:
        raise SystemExit("%s %d: source T* not in the 159 segment" % (arm, seed))
    si = (SEG + 1) * n // len(POSITIONS) - 1          # 第 143 位那一段的最后一个条目
    if segment_of(si, n) != SEG or "target_db_filter_top" in items[si]["episode_id"]:
        raise SystemExit("bad swap index")
    q = copy.deepcopy(p)
    q["items"][ti], q["items"][si] = q["items"][si], q["items"][ti]
    q["timing_amend"] = {"arm": arm, "source_plan": str(src.relative_to(ROOT)), "source_sha256": sha256_file(src),
                         "target_id": items[ti]["episode_id"], "target_index_from": ti, "target_index_to": si,
                         "swapped_item": items[si]["episode_id"], "n_items": n,
                         "target_position_from": POSITIONS[segment_of(ti, n)], "target_position_to": POSITIONS[SEG],
                         "prereg": "E3B2_PREREG_AMEND_20261113_timing_ZH.md"}
    # 不变量
    assert sorted(i["episode_id"] for i in q["items"]) == sorted(i["episode_id"] for i in items)
    assert sum(i["input_tokens"] for i in q["items"]) == p["actual_input_tokens"]
    return q


def build() -> None:
    if (DATA / "manifest.json").exists():
        raise SystemExit("data_ext_e3b2_timing/manifest.json exists; refusing to overwrite")
    ensure_dir(DATA / "plans")
    summ = {}
    for s in SEEDS:
        for arm in ARMS:
            q = make_plan(s, arm)
            if json.dumps(make_plan(s, arm), sort_keys=True) != json.dumps(q, sort_keys=True):
                raise SystemExit("not deterministic")
            write_json(DATA / "plans" / ("A_seed%d_%s.json" % (s, arm)), q)
            summ["%d %s" % (s, arm)] = q["timing_amend"]
    write_json(DATA / "manifest.json", {
        "created_by": "fac_tinyagent/p2_timing.py", "created": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "prereg": "E3B2_PREREG_AMEND_20261113_timing_ZH.md (written before training)",
        "arms": list(ARMS), "seeds": SEEDS, "summary": summ,
        "plan_files": {p.name: sha256_file(p) for p in sorted((DATA / "plans").glob("*.json"))}})
    log("timing plans frozen: %s" % json.dumps(summ))


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
            raise SystemExit("timing prefix copy differs for %d" % seed)
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


def train(seed: int, arm: str) -> Dict[str, Any]:
    from . import e3_data as D
    from .e3_run import guards, v3_leakage_guard
    from .e3_train import train_replay_stage_e3
    from .e4_run import CALENDAR_PATH, DB_PATH, OLD, leakage_guard, start_adapter
    from .replay_study import config_for
    man = read_json(DATA / "manifest.json")
    for name, h in man["plan_files"].items():
        if sha256_file(DATA / "plans" / name) != h:
            raise SystemExit("timing plan changed: %s" % name)
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
                raise RuntimeError("frozen timing item does not match runtime pool: %s" % it["episode_id"])
        log("timing plan %s items %d target %s -> index %d" % (arm, len(frozen["items"]),
            frozen["timing_amend"]["target_id"], frozen["timing_amend"]["target_index_to"]))
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
    # 核对插入位置
    rp = read_json(ckpt(seed, arm) / "replay_plan.json")
    pos = [int(k) for k, v in rp["insertion_schedule"].items() for i in v if "target_db_filter_top" in i["episode_id"]]
    if pos != [143]:
        raise SystemExit("T* inserted at %s, expected [143]" % pos)
    write_json(run / "timing_meta.json", {"arm": arm, "seed": seed,
                                          "plan_sha256": sha256_file(DATA / "plans" / ("A_seed%d_%s.json" % (seed, arm))),
                                          "prefix_state_sha256": s.get("shared_prefix_state_sha256"),
                                          "optimizer_steps": s.get("optimizer_steps"), "target_position": pos,
                                          "finished": time.strftime("%Y-%m-%d %H:%M:%S %z")})
    log("TRAIN done %s steps=%s replay_tokens=%s" % (run.name, s.get("optimizer_steps"), s.get("replay_input_tokens")))
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
    stage = {"name": "TIMING_B1_" + label(seed, arm), "index": 4, "adapter": str(ck)}
    try:
        for s in todo:
            check_safe()
            rows, db, cal, h = suite_rows(s)
            t0 = time.time()
            rep = evaluate_family(model, tok, rows, config, stage, out / s, db, cal)
            if rep["evaluation_protocol"]["batch_size"] != 1:
                raise SystemExit("protocol is not B1")
            write_json(out / s / "timing_meta.json", {"suite": s, "rows_sha256": h, "n": len(rows), "checkpoint": str(ck),
                                                     "adapter_sha256": sha256_file(ck / "adapter_model.safetensors"),
                                                     "protocol": "Protocol-B1", "seconds": round(time.time() - t0, 1),
                                                     "finished": time.strftime("%Y-%m-%d %H:%M:%S %z")})
            log("  done %s %s n=%d %.1fs" % (label(seed, arm), s, len(rows), time.time() - t0))
    finally:
        free_model(model)
    log("EVAL done %s in %.1fs" % (label(seed, arm), time.time() - t_all))


def queue() -> None:
    for s in SEEDS:
        for arm in ARMS:
            check_safe()
            train(s, arm)
            evaluate(s, arm)
            try:
                summarize()
            except Exception as exc:
                log("WARN summarize failed: %r" % exc)
    log("QUEUE COMPLETE")


# ------------------------------------------------------------------ summary (CPU)
def _res(path: Path, suite: str):
    from .p1_run import suite_rows
    if not path.exists():
        return None
    res = read_jsonl(path)
    rows, _, _, _ = suite_rows(suite)
    return res if len(res) == len(rows) else None


def _steps_after(ck: Path) -> List[int]:
    L = read_jsonl(ck / "training_log.jsonl")
    total = read_json(ck / "train_summary.json")["optimizer_steps"]
    return [total - ((x["microstep"] - 1) // 8 + 1) + 1 for x in L if "target_db_filter_top" in x["episode_id"]]


def summarize() -> None:
    from . import p1_run as P
    rows = []
    for s in SEEDS:
        for arm in list(ARMS) + ["e3b2_A_target_other", "dose_db1", "tf25", "e3b2_A_target_dbbg"]:
            if arm in ARMS:
                ck, ev = ckpt(s, arm), EVAL / label(s, arm)
                rp = lambda su: ev / su / "results.jsonl"
            else:
                ck = P.ckpt_path(s, arm)
                rp = lambda su, a=arm: P.results_path(s, a, su)
            if not (ck / "train_summary.json").exists():
                continue
            r = {"seed": s, "arm": arm, "steps_after_target": _steps_after(ck)}
            res = _res(rp("natv2_database"), "natv2_database")
            if res:
                n = len(res)
                r.update({"main": sum(bool(x["joint_success"]) for x in res) / n,
                          "tool": sum(bool(x["tool_correct"]) for x in res) / n,
                          "arguments": sum(bool(x["arguments_correct"]) for x in res) / n,
                          "final": sum(bool(x["final_correct"]) for x in res) / n,
                          "correct_ids": sorted(x["episode_id"].rsplit("-", 1)[1] for x in res if x["joint_success"])})
            for su in ("db_nontarget", "natv2_python", "natv2_file", "calendar_v3", "v3fix", "p2_database", "p2_python", "p2_file"):
                rr = _res(rp(su), su)
                if rr:
                    if su == "natv2_file":
                        r[su] = sum(P._ok(x, su) for x in rr) / len(rr)
                    else:
                        r[su] = sum(bool(x["joint_success"]) for x in rr) / len(rr)
            rows.append(r)
    get = {(r["seed"], r["arm"]): r for r in rows}
    pairs = {}
    for a, b in PAIRS.items():
        d = []
        for s in SEEDS:
            x, y = get.get((s, a), {}).get("main"), get.get((s, b), {}).get("main")
            d.append(None if x is None or y is None else x - y)
        done = [v for v in d if v is not None]
        pairs["%s − %s" % (a, b)] = {"per_seed": d, "mean": statistics.mean(done) if done else None,
                                     "n_pos": sum(v > 1e-9 for v in done), "n_zero": sum(abs(v) <= 1e-9 for v in done),
                                     "n_neg": sum(v < -1e-9 for v in done), "n_seeds": len(done)}
    verdict = None
    if all(v["n_seeds"] == 3 for v in pairs.values()):
        full = [v["n_pos"] == 3 for v in pairs.values()]
        verdict = "支持" if all(full) else ("部分支持" if any(full) else "不支持")
    out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S %z"), "rows": rows, "pairs": pairs, "h_timing_verdict": verdict}
    ensure_dir(RUNS)
    write_json(RUNS / "summary.json", out)
    f3 = lambda x: "—" if x is None else "%.3f" % x
    md = ["# 插入位置单变量对照：汇总（Protocol-B1）", "", "生成：%s。脚本 `python -m fac_tinyagent.p2_timing --phase summarize`。" % out["generated"], "",
          "## 主指标：nat v2 `db.filter_cmp_top` Joint Success（30 题）", "",
          "| 种子 | 臂 | target 之后更新次数 | 主指标 | tool / args / final | 非 target 40 | nat Python | nat File | Calendar v3 | v3fix | p2 DB / Py / File |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    order = ["e3b2_A_target_other", "target_other_pos143", "dose_db1", "dose_db1_pos143", "e3b2_A_target_dbbg", "tf25"]
    for s in SEEDS:
        for a in order:
            r = get.get((s, a))
            if not r:
                continue
            md.append("| %s | %s | %s | %s | %s / %s / %s | %s | %s | %s | %s | %s | %s / %s / %s |" % (
                str(s)[-2:], a, ",".join(map(str, r["steps_after_target"])), f3(r.get("main")), f3(r.get("tool")), f3(r.get("arguments")),
                f3(r.get("final")), f3(r.get("db_nontarget")), f3(r.get("natv2_python")), f3(r.get("natv2_file")), f3(r.get("calendar_v3")),
                f3(r.get("v3fix")), f3(r.get("p2_database")), f3(r.get("p2_python")), f3(r.get("p2_file"))))
    md += ["", "## 配对差（正/零/负 = 种子数）", "", "| 对比 | 08 | 09 | 10 | 均值 | 正/零/负 |", "|---|---|---|---|---|---|"]
    for k, v in pairs.items():
        md.append("| %s | %s | %s | %d/%d/%d |" % (k, " | ".join("—" if x is None else "%+.3f" % x for x in v["per_seed"]), "—" if v["mean"] is None else "%+.3f" % v["mean"],
                                                 v["n_pos"], v["n_zero"], v["n_neg"]))
    md += ["", "H-timing 判定（预注册修订 §1）：%s" % (verdict or "尚未完成三种子"), "", "## 答对的题", ""]
    for s in SEEDS:
        for a in order:
            r = get.get((s, a))
            if r and "correct_ids" in r:
                md.append("- %s %s：%s" % (str(s)[-2:], a, r["correct_ids"] or "—"))
    (RUNS / "summary_tables_ZH.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log("summary written")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["build", "queue", "summarize", "show"], required=True)
    a = ap.parse_args()
    if a.phase == "build":
        build()
    elif a.phase == "queue":
        queue()
    elif a.phase == "summarize":
        summarize()
    else:
        for s in SEEDS:
            for arm in ARMS:
                print(s, arm, make_plan(s, arm)["timing_amend"])


if __name__ == "__main__":
    main()
