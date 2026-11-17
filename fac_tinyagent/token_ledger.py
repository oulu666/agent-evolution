"""[ext 2026-11-11] Real replay token ledger for E4 (runs_ext_e4) and E2 (runs_ext_tf). CPU, read-only.

Sources per run (all logged by replay_train): checkpoint/replay_plan.json (selected items with
input/supervised tokens and the targeted-quota flag), checkpoint/train_summary.json (totals), and
checkpoint/training_log.jsonl (every executed micro-step of the second half, kind=new|replay).
Two views of "target":
  quota view   = items the sampler placed through the targeted quota (plan flag `target`);
  content view = executed replay rows whose id is a target-type row (manifest target_ids),
                 including target rows drawn by the uniform part (so tf00 is not zero).
Output: runs_ext_e4/token_ledger.json + token_ledger.md (new files only).
"""
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict

from .utils import read_json, read_jsonl, write_json

ROOT = Path(__file__).resolve().parents[1]
SEEDS = [20261108, 20261109, 20261110]
ROUNDS = {"E4": (ROOT / "runs_ext_e4", ["tf00", "tf25", "tf50", "none"], ROOT / "data_ext_e4"),
          "E2": (ROOT / "runs_ext_tf", ["tf00", "tf25", "tf50", "tf75", "none"], ROOT / "data_round2")}
OLD = ["file", "database", "python"]


def run_ledger(rnd: str, seed: int, arm: str) -> Dict[str, Any]:
    base, _, data = ROUNDS[rnd]
    ck = base / "branches" / ("A_seed%d_%s" % (seed, arm)) / "checkpoint"
    s = read_json(ck / "train_summary.json")
    plan = read_json(ck / "replay_plan.json") if (ck / "replay_plan.json").exists() else {"items": []}
    log = read_jsonl(ck / "training_log.jsonl")
    target_ids = read_json(data / "manifest.json")["target_ids"]
    tid = {i for f in OLD for i in target_ids.get(f, [])}
    fam_of = {}
    for f in OLD:
        for r in read_jsonl(data / "pool" / (f + ".jsonl")):
            fam_of[r["episode_id"]] = f
    rep = [x for x in log if x["kind"] == "replay"]
    new = [x for x in log if x["kind"] == "new"]
    exposures = Counter(x["episode_id"] for x in rep)
    items = plan.get("items", [])
    tot = sum(x["input_tokens"] for x in rep)
    sup = sum(x["supervised_tokens"] for x in rep)
    quota_on = arm not in ("tf00", "none")  # tf00: the targeted quota is 0; flagged rows there are uniform draws
    tgt = sum(i["input_tokens"] for i in items if i.get("target")) if quota_on else 0
    tgt_sup = sum(i["supervised_tokens"] for i in items if i.get("target")) if quota_on else 0
    ctgt = sum(x["input_tokens"] for x in rep if x["episode_id"] in tid)
    fam = {}
    for f in OLD:
        rf = [x for x in rep if fam_of.get(x["episode_id"]) == f]
        cf = [x for x in rf if x["episode_id"] in tid]
        qf = [i for i in items if i.get("target") and i["family"] == f] if quota_on else []
        fam[f] = {"samples": len(rf), "unique": len({x["episode_id"] for x in rf}),
                  "input_tokens": sum(x["input_tokens"] for x in rf),
                  "target_samples": len(qf), "target_input_tokens": sum(i["input_tokens"] for i in qf),
                  "uniform_input_tokens": sum(x["input_tokens"] for x in rf) - sum(i["input_tokens"] for i in qf),
                  "content_target_samples": len(cf), "content_target_unique": len({x["episode_id"] for x in cf}),
                  "content_target_input_tokens": sum(x["input_tokens"] for x in cf),
                  "content_target_ids": sorted({x["episode_id"] for x in cf}),
                  "quota_target_ids": sorted({i["episode_id"] for i in qf})}
    checks = {
        "log_replay_tokens_eq_summary": tot == (s.get("replay_input_tokens") or 0),
        "log_replay_tokens_eq_plan": tot == (plan.get("actual_input_tokens") or 0) if items else tot == 0,
        "plan_items_eq_log_multiset": Counter(i["episode_id"] for i in items) == exposures,
        "plan_target_flag_eq_target_id": all(bool(i.get("target")) == (i["episode_id"] in tid) for i in items),
        "quota_target_tokens_eq_plan_and_summary": tgt == (plan.get("target_actual_input_tokens") or 0)
        == (s.get("target_actual_input_tokens") or 0),
        "summary_train_tokens_eq_new_plus_replay": s.get("train_tokens") == (s.get("new_input_tokens") or 0) + tot,
    }
    positions = sorted({x["new_position"] for x in rep})
    return {
        "round": rnd, "seed": seed, "arm": arm, "mode": s.get("mode"),
        "nominal_target_fraction": None if arm == "none" else int(arm[2:]) / 100,
        "budget_input_tokens": s.get("budget_input_tokens"),
        "replay_input_tokens": tot, "target_input_tokens": tgt, "uniform_input_tokens": tot - tgt,
        "actual_target_fraction_input": (tgt / tot) if tot else None,
        "replay_supervised_tokens": sup, "target_supervised_tokens": tgt_sup,
        "actual_target_fraction_supervised": (tgt_sup / sup) if sup else None,
        "content_target_input_tokens": ctgt, "content_target_fraction_input": (ctgt / tot) if tot else None,
        "replay_samples": len(rep), "replay_unique": len(exposures),
        "max_exposures_per_sample": max(exposures.values()) if exposures else 0,
        "repeated_samples": {k: v for k, v in exposures.items() if v > 1},
        "replay_new_positions": [positions[0], positions[-1]] if positions else None,
        "replay_in_second_epoch_only": all(p > s["train_samples"] for p in positions) if positions else None,
        "new_input_tokens": s.get("new_input_tokens"), "new_logged_second_half_tokens": sum(x["input_tokens"] for x in new),
        "train_tokens_total": s.get("train_tokens"),
        "by_family": fam, "exposures": dict(exposures), "checks": checks,
    }


def build() -> Dict[str, Any]:
    runs = []
    for rnd, (base, arms, _) in ROUNDS.items():
        for arm in arms:
            for seed in SEEDS:
                if (base / "branches" / ("A_seed%d_%s" % (seed, arm)) / "checkpoint" / "train_summary.json").exists():
                    runs.append(run_ledger(rnd, seed, arm))
    agg = []
    keys = ["replay_input_tokens", "target_input_tokens", "uniform_input_tokens", "actual_target_fraction_input",
            "actual_target_fraction_supervised", "content_target_input_tokens", "content_target_fraction_input",
            "replay_samples", "replay_unique", "train_tokens_total"]
    for rnd, (base, arms, _) in ROUNDS.items():
        for arm in arms:
            part = [r for r in runs if r["round"] == rnd and r["arm"] == arm]
            if not part:
                continue
            e = {"round": rnd, "arm": arm, "n": len(part)}
            for k in keys:
                v = [r[k] for r in part if r[k] is not None]
                e[k] = {"mean": mean(v) if v else None, "std": (stdev(v) if len(v) > 1 else 0.0) if v else None,
                        "per_seed": [r[k] for r in part]}
            for f in OLD:
                for k in ("target_input_tokens", "target_samples", "samples", "content_target_samples"):
                    e["%s_%s" % (k, f)] = [r["by_family"][f][k] for r in part]
            agg.append(e)
    file_targets = read_json(ROOT / "data_ext_e4" / "manifest.json")["target_ids"]["file"]
    usage = {}
    for t in file_targets:
        used = [(r["seed"], r["arm"], r["exposures"].get(t, 0)) for r in runs if r["round"] == "E4" and t in r["exposures"]]
        usage[t] = {"runs_used": len(used), "max_exposures_in_a_run": max([u[2] for u in used] or [0]),
                    "used_in": ["%d:%s" % (u[0], u[1]) for u in used]}
    by_arm = defaultdict(dict)
    for r in runs:
        if r["round"] == "E4" and r["arm"] != "none":
            by_arm[r["arm"]][str(r["seed"])] = r["by_family"]["file"]["content_target_ids"]
    failed = ["%s seed%d %s: %s" % (r["round"], r["seed"], r["arm"], [k for k, v in r["checks"].items() if not v])
              for r in runs if not all(r["checks"].values())]
    return {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "runs": runs, "aggregates": agg,
            "e4_file_target_usage": usage, "e4_file_target_ids_by_arm_seed": by_arm,
            "all_checks_ok": not failed, "failed_checks": failed}


def _ms(d, nd=0):
    if d["mean"] is None:
        return "-"
    return ("%.*f±%.*f" % (nd, d["mean"], nd, d["std"])) if d["std"] else "%.*f" % (nd, d["mean"])


def write() -> None:
    res = build()
    out = ROOT / "runs_ext_e4"
    write_json(out / "token_ledger.json", res)
    L = ["# 真实复习 Token 账本（E4 = runs_ext_e4，E2 = runs_ext_tf）", "",
         "生成于 %s（Asia/Shanghai）。来源：每个 run 的 training_log.jsonl（实际执行的每个 micro-step），"
         "与 replay_plan.json、train_summary.json 交叉核对；核对全部通过：**%s**%s。" % (
             res["generated"], res["all_checks_ok"], ("（失败：%s）" % res["failed_checks"]) if res["failed_checks"] else ""), "",
         "token 指输入 token（prompt+回答）。均值±sd（3 种子）。**定向 token（配额口径）**= 采样器经定向配额放入的样本；"
         "**target 类内容 token（内容口径）**= 实际执行的复习样本里属于 target 类型（manifest target_ids）的全部样本，"
         "包括均匀部分碰巧抽到的 target 行，所以 tf00 也不为 0。", "",
         "| 轮 | 臂 | 复习总 token | 定向 token(配额) | 均匀 token | 实际定向比例(输入) | 实际定向比例(监督) | target 类内容 token | 内容口径比例 | 复习条数 | 独立条数 | 训练总 token |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in res["aggregates"]:
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            a["round"], a["arm"], _ms(a["replay_input_tokens"]), _ms(a["target_input_tokens"]),
            _ms(a["uniform_input_tokens"]), _ms(a["actual_target_fraction_input"], 3),
            _ms(a["actual_target_fraction_supervised"], 3), _ms(a["content_target_input_tokens"]),
            _ms(a["content_target_fraction_input"], 3), _ms(a["replay_samples"], 1),
            _ms(a["replay_unique"], 1), _ms(a["train_tokens_total"])))
    L += ["", "## 分工具（按种子 108/109/110）", "",
          "| 轮 | 臂 | 定向 token File/DB/Py（配额） | 定向条数 File/DB/Py（配额） | target 类内容条数 File/DB/Py | 复习条数 File/DB/Py |",
          "|---|---|---|---|---|---|"]
    for a in res["aggregates"]:
        def trip(k):
            return " / ".join(str(a["%s_%s" % (k, f)]) for f in OLD)
        L.append("| %s | %s | %s | %s | %s | %s |" % (a["round"], a["arm"], trip("target_input_tokens"),
                                                      trip("target_samples"), trip("content_target_samples"), trip("samples")))
    reps = ["%s seed%d %s: %s" % (r["round"], r["seed"], r["arm"], json.dumps(r["repeated_samples"]))
            for r in res["runs"] if r["repeated_samples"]]
    L += ["", "## 重复使用检查", "",
          "- 复习全部插在第二个 epoch（共享前缀之后，new_position > 80）：%s。" % all(
              r["replay_in_second_epoch_only"] for r in res["runs"] if r["replay_in_second_epoch_only"] is not None),
          "- 单个 run 内同一复习样本的最大执行次数：%s。" % sorted({r["max_exposures_per_sample"] for r in res["runs"]}),
          "- run 内重复的样本：" + ("; ".join(reps) if reps else "无"),
          "- E4 的 16 条新 File target 在 12 个 E4 run 中的使用（被几个 run 用到 / 单 run 最多几次）：", ""]
    for t, u in res["e4_file_target_usage"].items():
        L.append("  - `%s`: %d 个 run，单 run 最多 %d 次（%s）" % (t, u["runs_used"], u["max_exposures_in_a_run"], ", ".join(u["used_in"]) or "未使用"))
    L += ["", "- E4 各臂各种子实际执行到的 File target（内容口径）："]
    for arm, d in res["e4_file_target_ids_by_arm_seed"].items():
        for s, ids in d.items():
            L.append("  - %s seed%s: %s" % (arm, s, ", ".join(i.split("-")[-1] for i in ids) or "无"))
    L += ["", "## 说明", "",
          "- none 臂没有复习 token，训练总 token 74,944；复习臂约 82,438（+10%）。复习是加在新数据之上，不是替换，"
          "因此“复习 vs none”的差异混有约 10% 额外训练量——E3 需要计算量匹配对照。"]
    (out / "token_ledger.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("ok", res["all_checks_ok"], res["failed_checks"])


if __name__ == "__main__":
    write()