#!/usr/bin/env python3
"""[ext 2026-11-13] 已有臂的 target 插入位置分布与「之后更新次数」（只读日志，CPU）。

评估插入时机对两个已有结论的影响：(1) Database 剂量 S 曲线（dose_db0–6，B1）；
(2) 「覆盖比预算更重要」（b05/b10/b20 × tf00/25/50；b10 = E4 的 tf00/tf25/tf50；B1 只有 b10 三臂与 b20_tf50，
其余用历史 B32，分协议列出，不混算）。
输入（只读）：各 checkpoint 的 training_log.jsonl / train_summary.json；runs_ext_p1_b1 与历史 B32 的 natv2_database 逐题结果。
输出（新文件）：runs_ext_e3b2_timing/analysis/existing_timing.json、existing_timing_ZH.md
用法（项目根目录）：.venv/bin/python scripts/p2_timing_existing.py
"""
import json, statistics, sys
from collections import Counter
from pathlib import Path

ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))
from fac_tinyagent import p1_run as P  # noqa: E402
from fac_tinyagent.utils import read_jsonl  # noqa: E402

OUT = ROOT / "runs_ext_e3b2_timing" / "analysis"
SEEDS = [20261108, 20261109, 20261110]
ACC, BETA1 = 8, 0.9
DOSE = ["dose_db0", "dose_db1", "dose_db2", "dose_db3", "dose_db4", "dose_db6"]
GRID = {("b05", "tf00"): "b05_tf00", ("b05", "tf25"): "b05_tf25", ("b05", "tf50"): "b05_tf50",
        ("b10", "tf00"): "tf00", ("b10", "tf25"): "tf25", ("b10", "tf50"): "tf50",
        ("b20", "tf00"): "b20_tf00", ("b20", "tf25"): "b20_tf25", ("b20", "tf50"): "b20_tf50"}


def score(path):
    if path is None or not Path(path).exists():
        return None
    r = read_jsonl(path)
    if len(r) != 30:
        return None
    return sum(bool(x["joint_success"]) for x in r) / 30


def timing(seed, arm):
    d = P.ckpt_path(seed, arm)
    L = read_jsonl(d / "training_log.jsonl")
    total = json.load(open(d / "train_summary.json", encoding="utf-8"))["optimizer_steps"]
    tg = []
    for x in L:
        if "target_db_filter_top" in x["episode_id"]:
            win = (x["microstep"] - 1) // ACC + 1
            tg.append({"t": x["episode_id"].rsplit("-", 1)[1], "pos": x["new_position"], "after": total - win + 1})
    return {"total_steps": total, "total_microsteps": L[-1]["microstep"], "targets": tg, "n_target": len(tg),
            "sum_after": sum(t["after"] for t in tg), "mom": sum(1 - BETA1 ** t["after"] for t in tg),
            "n_at_159": sum(t["pos"] == 159 for t in tg), "earliest": min([t["pos"] for t in tg], default=None)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for s in SEEDS:
        for a in DOSE + list(GRID.values()) + ["e3b2_A_target_other", "e3b2_A_target_dbbg"]:
            if not (P.ckpt_path(s, a) / "training_log.jsonl").exists():
                continue
            r = {"seed": s, "arm": a, **timing(s, a)}
            r["b1"] = score(P.results_path(s, a, "natv2_database"))
            r["b32"] = score(P.historical_b32(s, a, "natv2_database"))
            rows.append(r)
    get = {(r["seed"], r["arm"]): r for r in rows}
    f3 = lambda x: "—" if x is None else "%.3f" % x
    mean = lambda v: statistics.mean(v) if v else None
    md = ["# 已有臂的 target 插入位置与「之后更新次数」（只读日志，CPU）", "",
          "脚本 `scripts/p2_timing_existing.py`。「之后更新次数」= 训练结束时 optimizer_steps − 该条目所在累积窗口序号 + 1（含所在窗口那次）。"
          "动量加权 = Σ(1 − 0.9^之后更新次数)，只是 AdamW 一阶动量的粗略系数，作描述用。主指标 = nat v2 Database 30 题 Joint Success。", ""]
    # ---- (1) dose
    md += ["## 1. 剂量曲线（B1）", "", "| 剂量 | 种子 | B1 | 各条 target（新样本位置 / 之后更新次数） | 之后更新次数之和 | 在第 159 位的条数 | 动量加权 |", "|---|---|---|---|---|---|---|"]
    agg = {}
    for a in DOSE:
        for s in SEEDS:
            r = get.get((s, a))
            if not r:
                continue
            md.append("| %s | %s | %s | %s | %d | %d/%d | %s |" % (a, str(s)[-2:], f3(r["b1"]), "；".join("%d/%d" % (t["pos"], t["after"]) for t in r["targets"]) or "—",
                                                       r["sum_after"], r["n_at_159"], r["n_target"], f3(r["mom"])))
        rs = [get[(s, a)] for s in SEEDS if (s, a) in get]
        agg[a] = {"b1_mean": mean([r["b1"] for r in rs if r["b1"] is not None]), "sum_after_mean": mean([r["sum_after"] for r in rs]),
                  "after_per_target_mean": mean([t["after"] for r in rs for t in r["targets"]]),
                  "share_at_159": (sum(r["n_at_159"] for r in rs) / max(1, sum(r["n_target"] for r in rs))) if any(r["n_target"] for r in rs) else None,
                  "mom_mean": mean([r["mom"] for r in rs])}
    md += ["", "| 剂量 | B1 三种子均值 | 每条 target 平均之后更新次数 | 之后更新次数之和（均值） | 在第 159 位的比例 | 动量加权（均值） |", "|---|---|---|---|---|---|"]
    for a, v in agg.items():
        md.append("| %s | %s | %s | %s | %s | %s |" % (a, f3(v["b1_mean"]), f3(v["after_per_target_mean"]), f3(v["sum_after_mean"]),
                                                f3(v["share_at_159"]), f3(v["mom_mean"])))
    # 同「之后更新次数之和」的比较：tf25（1 条，3–4 次） vs dose_db2（2 条）
    cmp = []
    for s in SEEDS:
        a, b = get.get((s, "tf25")), get.get((s, "dose_db2"))
        if a and b:
            cmp.append({"seed": s, "tf25": [a["b1"], a["sum_after"]], "dose_db2": [b["b1"], b["sum_after"]]})
    md += ["", "同样「之后更新次数之和」、不同条数：", "", "| 种子 | tf25：B1 / 之后更新次数之和（1 条） | dose_db2：B1 / 之后更新次数之和（2 条） |", "|---|---|---|"]
    for c in cmp:
        md.append("| %s | %s / %d | %s / %d |" % (str(c["seed"])[-2:], f3(c["tf25"][0]), c["tf25"][1], f3(c["dose_db2"][0]), c["dose_db2"][1]))
    # ---- (2) grid
    md += ["", "## 2. 预算 × target 比例（覆盖 vs 预算）", "",
           "b10 三臂和 b20_tf50 有 B1；b05 和 b20_tf00/tf25 只有历史 B32。两种协议分列，不混算。", "",
           "| 预算 | tf | 种子 | B1 | B32 | target 条数 | 各条 target（位置 / 之后更新次数） | 之后更新次数之和 | 总更新次数 |", "|---|---|---|---|---|---|---|---|---|"]
    grid = {}
    for (b, tf), a in GRID.items():
        for s in SEEDS:
            r = get.get((s, a))
            if not r:
                continue
            md.append("| %s | %s | %s | %s | %s | %d | %s | %d | %d |" % (b, tf, str(s)[-2:], f3(r["b1"]), f3(r["b32"]), r["n_target"],
                      "；".join("%d/%d" % (t["pos"], t["after"]) for t in r["targets"]) or "—", r["sum_after"], r["total_steps"]))
        rs = [get[(s, a)] for s in SEEDS if (s, a) in get]
        grid["%s_%s" % (b, tf)] = {"arm": a, "n": len(rs), "b1_mean": mean([r["b1"] for r in rs if r["b1"] is not None]),
                                   "b32_mean": mean([r["b32"] for r in rs if r["b32"] is not None]),
                                   "n_target_mean": mean([r["n_target"] for r in rs]), "sum_after_mean": mean([r["sum_after"] for r in rs]),
                                   "earliest": [r["earliest"] for r in rs], "total_steps": sorted({r["total_steps"] for r in rs})}
    md += ["", "| 预算_tf | B1 均值 | B32 均值 | target 条数均值 | 之后更新次数之和均值 | 最早插入位置（08/09/10） | 总更新次数 |", "|---|---|---|---|---|---|---|"]
    for k, v in grid.items():
        md.append("| %s | %s | %s | %s | %s | %s | %s |" % (k, f3(v["b1_mean"]), f3(v["b32_mean"]), f3(v["n_target_mean"]), f3(v["sum_after_mean"]),
                                                     "/".join("—" if e is None else str(e) for e in v["earliest"]), v["total_steps"]))
    json.dump({"rows": rows, "dose_agg": agg, "same_sum_after_cmp": cmp, "grid": grid}, open(OUT / "existing_timing.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    (OUT / "existing_timing_ZH.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"dose_agg": agg, "grid": grid, "cmp": cmp}, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    main()
