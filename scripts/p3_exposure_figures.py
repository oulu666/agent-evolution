#!/usr/bin/env python3
"""[ext 2026-11-14] 用「暴露量」重画 E3 剂量图与预算图（只读，CPU）。
输入：runs_ext_e3b2_timing/analysis/timing_audit.json（scripts/p2_timing_audit.py 的输出）；
      可选 runs_ext_p3_count_timing/summary.json（P3 完成后叠加 P3 三个新臂，空心星号）。
输出：runs_ext_p3_count_timing/analysis/figures/*.png（新文件）。B1 与 B32 分图，不混画。
依赖 matplotlib（项目 .venv 里没有，也不往 .venv 装）；用任意带 matplotlib 的 Python 运行：
  python scripts/p3_exposure_figures.py --root <项目根目录>
"""
import argparse, json, statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

for f in ("Noto Sans CJK SC", "Microsoft YaHei", "SimHei", "WenQuanYi Zen Hei"):
    if any(f == x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [f]
        break
plt.rcParams["axes.unicode_minus"] = False

DOSE = ["dose_db0", "dose_db1", "dose_db2", "dose_db3", "dose_db4", "dose_db6"]
ONE = ["dose_db1_pos143", "target_other_pos143", "tf25", "e3b2_A_target_other", "e3b2_A_target_dbbg"]
P3 = ["dose_db1_pos127", "dose_db4_late", "dose_db1_pos95"]
MARK = {"dose_db1_pos143": "^", "target_other_pos143": "v", "tf25": "D", "e3b2_A_target_other": "x", "e3b2_A_target_dbbg": "+"}
CMAP = plt.get_cmap("viridis")


def ncol(n, nmax=8):
    return CMAP(min(n, nmax) / nmax)


def jitter(seed):
    return {20261108: -0.12, 20261109: 0.0, 20261110: 0.12}.get(seed, 0.0)


def dose_figure(rows, p3, out, xkey, xlabel, fname, title):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), sharey=True)
    # 左：旧横轴 n；右：新横轴（Σafter 或 mom）
    for ax, key, lab in ((axes[0], "n_target", "target 条数 n（旧横轴）"), (axes[1], xkey, xlabel)):
        span = 1.0 if key != "mom" else 0.03
        for arm in DOSE:
            rs = [r for r in rows if r["arm"] == arm]
            if not rs:
                continue
            xs = [r[key] + jitter(r["seed"]) * span for r in rs]
            ax.scatter(xs, [r["b1"] for r in rs], s=46, color=ncol(rs[0]["n_target"]), edgecolor="k", lw=0.5, zorder=3)
            mx = statistics.mean(r[key] for r in rs); my = statistics.mean(r["b1"] for r in rs)
            ax.scatter([mx], [my], s=170, marker="o", facecolor="none", edgecolor=ncol(rs[0]["n_target"]), lw=2, zorder=4)
            ax.annotate(arm.replace("dose_", ""), (mx, my), textcoords="offset points", xytext=(6, -12), fontsize=8)
        for arm in ONE:
            rs = [r for r in rows if r["arm"] == arm]
            if rs:
                ax.scatter([r[key] + jitter(r["seed"]) * span for r in rs], [r["b1"] for r in rs], s=46, marker=MARK[arm],
                           color=ncol(1), edgecolor="k" if MARK[arm] not in "x+" else None, lw=0.5, zorder=3, label=arm)
        for arm in P3:
            rs = [r for r in p3 if r["arm"] == arm and r.get("main") is not None]
            if rs:
                ax.scatter([r[key] + jitter(r["seed"]) * span for r in rs], [r["main"] for r in rs], s=120, marker="*",
                           facecolor="none", edgecolor=ncol(rs[0]["n_target"]), lw=1.4, zorder=5, label="P3 " + arm)
        ax.set_xlabel(lab)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("B1 nat v2 db.filter_cmp_top Joint Success（30 题）")
    axes[0].set_ylim(-0.04, 1.04)
    h, l = axes[1].get_legend_handles_labels()
    axes[1].legend(h, l, fontsize=7.5, loc="lower right")
    sm = plt.cm.ScalarMappable(cmap=CMAP, norm=plt.Normalize(0, 8)); sm.set_array([])
    fig.colorbar(sm, ax=axes, label="target 条数 n（颜色）", fraction=0.025, pad=0.01)
    fig.suptitle(title, fontsize=11)
    fig.savefig(out / fname, dpi=160, bbox_inches="tight")
    plt.close(fig)


def budget_figure(grid, b1rows, out):
    budget = lambda c: int(c[1:3])
    tf = lambda c: c.split("_")[1]
    tfm = {"tf00": "o", "tf25": "s", "tf50": "^"}
    bcol = {5: "#1b9e77", 10: "#d95f02", 20: "#7570b3"}
    # B32：预算（旧横轴） / Σafter / mom
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    for ax, key, lab in ((axes[0], "budget", "复习预算 %（旧横轴）"), (axes[1], "sum_after", "Σafter（target 更新暴露）"),
                         (axes[2], "mom", "mom = Σ(1−0.9^after)（敏感性）")):
        for c in sorted(set(r["cell"] for r in grid)):
            rs = [r for r in grid if r["cell"] == c and r.get("b32") is not None]
            if not rs:
                continue
            x = [(budget(c) + 0.6 * jitter(r["seed"]) * 5 + {"tf00": -0.8, "tf25": 0, "tf50": 0.8}[tf(c)]) if key == "budget" else r[key] for r in rs]
            ax.scatter(x, [r["b32"] for r in rs], s=52, marker=tfm[tf(c)], color=bcol[budget(c)], edgecolor="k", lw=0.5,
                       label=c if ax is axes[1] else None, zorder=3)
        ax.set_xlabel(lab); ax.grid(alpha=0.3)
    axes[0].set_xticks([5, 10, 20])
    axes[0].set_ylabel("B32 nat v2 db.filter_cmp_top Joint Success（30 题）")
    axes[0].set_ylim(-0.04, 1.04)
    axes[1].legend(fontsize=7.5, ncol=3, loc="lower right")
    fig.suptitle("预算 × target 比例（只用 B32，27 点；颜色 = 预算，形状 = tf）：横轴从预算换成暴露量", fontsize=11)
    fig.savefig(out / "fig_budget_B32_exposure.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    # B1：只有 b10 三格与 b20_tf50 有 B1
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True)
    cells = {"tf00": "b10_tf00", "tf25": "b10_tf25", "tf50": "b10_tf50", "b20_tf50": "b20_tf50"}
    for ax, key, lab in ((axes[0], "sum_after", "Σafter"), (axes[1], "mom", "mom（敏感性）")):
        for arm, c in cells.items():
            rs = [r for r in b1rows if r["arm"] == arm]
            if rs:
                ax.scatter([r[key] for r in rs], [r["b1"] for r in rs], s=52, marker=tfm[tf(c)], color=bcol[budget(c)],
                           edgecolor="k", lw=0.5, label=c, zorder=3)
        ax.set_xlabel(lab); ax.grid(alpha=0.3)
    axes[0].set_ylabel("B1 nat v2 db.filter_cmp_top Joint Success（30 题）")
    axes[0].set_ylim(-0.04, 1.04)
    axes[0].legend(fontsize=8, loc="lower right")
    fig.suptitle("预算格子中有 B1 的点（b10 三格 + b20_tf50，12 点）：成绩 vs 暴露量", fontsize=11)
    fig.savefig(out / "fig_budget_B1_exposure.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root)
    d = json.loads((root / "runs_ext_e3b2_timing" / "analysis" / "timing_audit.json").read_text(encoding="utf-8"))
    p3p = root / "runs_ext_p3_count_timing" / "summary.json"
    p3 = json.loads(p3p.read_text(encoding="utf-8"))["rows"] if p3p.exists() else []
    out = root / "runs_ext_p3_count_timing" / "analysis" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    rows = [r for r in d["rows"] if r.get("b1") is not None]
    dose_figure(rows, p3, out, "sum_after", "Σafter（target 更新暴露，新横轴）", "fig_dose_B1_exposure.png",
                "Database 剂量曲线（B1）：横轴从 target 条数换成 Σafter；实心点 = 单种子，空心圈 = 剂量臂三种子均值")
    dose_figure(rows, p3, out, "mom", "mom = Σ(1−0.9^after)（AdamW 启发的动量加权暴露代理，敏感性）", "fig_dose_B1_mom.png",
                "Database 剂量曲线（B1）：横轴换成 mom（敏感性指标）")
    budget_figure(d["grid_rows"], d["rows"], out)
    print("figures ->", out, sorted(p.name for p in out.glob("*.png")), "P3 rows overlaid:", len(p3))


if __name__ == "__main__":
    main()
