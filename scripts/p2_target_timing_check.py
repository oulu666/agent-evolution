#!/usr/bin/env python3
"""target 插入位置 / 之后的 optimizer 步数（只读 CPU；不训练、不用 GPU）。

动机：v2 梯度打分解释不了 tf25 > 实验 A 两臂。检查已有训练日志里 filter_cmp_top 条目落在哪个累积窗口、
之后还有几次 optimizer 更新（AdamW 动量会把一条梯度带到之后的更新里）。
输入（只读）：各 checkpoint 的 training_log.jsonl、train_summary.json、P1 B1 逐题结果。
输出（新文件）：runs_ext_p2_grad_pilot/v2/target_timing.json、target_timing_ZH.md
用法（项目根目录）：.venv/bin/python scripts/p2_target_timing_check.py
"""
import json, statistics, sys
from pathlib import Path

ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from fac_tinyagent import p1_run as P  # noqa: E402
import p2_grad_utility_pilot as V1  # noqa: E402

OUT = ROOT / "runs_ext_p2_grad_pilot" / "v2"
ACC = 8          # gradient_accumulation_steps（各臂 stage_config 相同）
BETA1 = 0.9      # PagedAdamW8bit 默认 betas[0]（训练代码未改）


def main():
    rows = []
    for s in V1.SEEDS:
        for a in V1.ARMS:
            if a == "none":
                continue
            d = P.ckpt_path(s, a)
            lp = d / "training_log.jsonl"
            if not lp.exists():
                continue
            acc_full = V1.b1_acc(s, a)
            if acc_full is None:
                continue
            L = V1.rj(lp)
            total = json.load(open(d / "train_summary.json", encoding="utf-8"))["optimizer_steps"]
            tg = []
            for x in L:
                if "target_db_filter_top" in x["episode_id"]:
                    win = (x["microstep"] - 1) // ACC + 1
                    n_after = total - win + 1          # 含它所在窗口的那次更新
                    tg.append({"episode": x["episode_id"].rsplit("-", 1)[1], "new_position": x["new_position"],
                               "microstep": x["microstep"], "steps_incl_own": n_after})
            rows.append({"seed": s, "arm": a, "acc_full": acc_full, "n_target": len(tg),
                         "momentum_weighted_target": sum(1 - BETA1 ** t["steps_incl_own"] for t in tg),
                         "sum_steps_after": sum(t["steps_incl_own"] for t in tg),
                         "total_optimizer_steps": total, "total_microsteps": L[-1]["microstep"], "targets": tg})
    for r in rows:
        pass
    y = [r["acc_full"] for r in rows]
    nt = [r["n_target"] for r in rows]
    res = {"n_points": len(rows), "spearman_n_target": V1.spearman(nt, y),
           "spearman_momentum_weighted": V1.spearman([r["momentum_weighted_target"] for r in rows], y),
           "spearman_sum_steps_after": V1.spearman([r["sum_steps_after"] for r in rows], y)}
    sys.path.insert(0, str(ROOT / "scripts"))
    import p2_grad_utility_pilot_v2 as V2
    res["partial_momentum_given_n_target"] = V2.partial_spearman(y, [r["momentum_weighted_target"] for r in rows], nt)
    res["partial_sum_steps_given_n_target"] = V2.partial_spearman(y, [r["sum_steps_after"] for r in rows], nt)
    one = [r for r in rows if r["n_target"] == 1]
    res["one_target_spearman_steps"] = V1.spearman([r["sum_steps_after"] for r in one], [r["acc_full"] for r in one])
    res["rows"] = rows
    json.dump(res, open(OUT / "target_timing.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    f3 = lambda x: "—" if x is None else "%.3f" % x
    md = ["# filter_cmp_top 条目的插入位置与之后的 optimizer 更新次数（只读训练日志）", "",
          "生成脚本：`scripts/p2_target_timing_check.py`。「之后更新次数」= 训练结束时 optimizer_steps − 该条目所在累积窗口序号 + 1"
          "（含它自己所在窗口那次；累积 %d 步；最后不足 %d 步的窗口按代码会补一次更新）。动量加权 = Σ(1 − 0.9^更新次数)，"
          "是 AdamW 一阶动量把一条梯度带入后续更新的粗略系数（忽略二阶矩归一化），只作描述。" % (ACC, ACC), "",
          "| 预测量（%d 个臂×种子点，结果 = B1 nat v2 Database 全 30 题） | Spearman | 偏 Spearman｜n_target |" % res["n_points"], "|---|---|---|",
          "| n_target | %s | — |" % f3(res["spearman_n_target"]),
          "| 动量加权 target | %s | %s |" % (f3(res["spearman_momentum_weighted"]), f3(res["partial_momentum_given_n_target"])),
          "| target 之后更新次数之和 | %s | %s |" % (f3(res["spearman_sum_steps_after"]), f3(res["partial_sum_steps_given_n_target"])),
          "", "只含 1 条 target 的 %d 个点：之后更新次数 vs 成绩 Spearman = %s。" % (len(one), f3(res["one_target_spearman_steps"])), "",
          "| 种子 | 臂 | 实测 | target 条数 | 各条 target（条目 / 新样本位置 / 之后更新次数） | 动量加权 | 总更新次数 |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append("| %s | %s | %s | %d | %s | %s | %d |" % (str(r["seed"])[-2:], r["arm"], f3(r["acc_full"]), r["n_target"],
                  "；".join("T-%s / %d / %d" % (t["episode"], t["new_position"], t["steps_incl_own"]) for t in r["targets"]) or "—",
                  f3(r["momentum_weighted_target"]), r["total_optimizer_steps"]))
    open(OUT / "target_timing_ZH.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    print({k: v for k, v in res.items() if k != "rows"})


if __name__ == "__main__":
    main()
