#!/usr/bin/env python3
"""[ext 2026-11-13] 插入时机审计（只读，CPU）：把插入位置单变量对照的 6 个新点并入已有各臂，
看 Database 主指标（B1 nat v2 db.filter_cmp_top，30 题）与 (a) target 条数、(b) target 之后的更新次数 的关系，
评估 Database 剂量 S 曲线与「覆盖比预算更重要」在扣除插入时机后还剩多少。
计数口径与 scripts/p2_target_timing_check.py / fac_tinyagent/p2_timing.py 相同：
  之后更新次数 = 训练结束时 optimizer_steps − 该条目所在累积窗口序号 + 1（累积 8 步，含所在窗口那次）。
输入（只读）：各 checkpoint 的 training_log.jsonl / train_summary.json；runs_ext_p1_b1、runs_ext_e3b2_timing/evaluation 的 B1 逐题结果；
              历史 B32 逐题结果（只用于 b05 / b20_tf00 / b20_tf25，单列，不和 B1 混算）。
输出（新文件）：runs_ext_e3b2_timing/analysis/timing_audit.json、timing_audit_ZH.md
用法（项目根目录）：.venv/bin/python scripts/p2_timing_audit.py
"""
import json, math, statistics, sys, time
from pathlib import Path

import numpy as np

ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))
from fac_tinyagent import p1_run as P  # noqa: E402
from fac_tinyagent.utils import read_jsonl  # noqa: E402

TIM = ROOT / "runs_ext_e3b2_timing"
OUT = TIM / "analysis"
SEEDS = [20261108, 20261109, 20261110]
ACC, BETA1 = 8, 0.9
NEW = ["target_other_pos143", "dose_db1_pos143"]
DOSE = ["dose_db0", "dose_db1", "dose_db2", "dose_db3", "dose_db4", "dose_db6"]
B1_ARMS = DOSE + ["tf00", "tf25", "tf50", "b20_tf50", "ctrl_cal10", "ctrl_cal20",
                  "e3b2_A_target_other", "e3b2_A_target_dbbg"] + NEW
B32_GRID = {"b05_tf00": "b05_tf00", "b05_tf25": "b05_tf25", "b05_tf50": "b05_tf50", "b10_tf00": "tf00", "b10_tf25": "tf25",
            "b10_tf50": "tf50", "b20_tf00": "b20_tf00", "b20_tf25": "b20_tf25", "b20_tf50": "b20_tf50"}


def ck_of(s, a):
    return TIM / "branches" / ("A_seed%d_%s" % (s, a)) / "checkpoint" if a in NEW else P.ckpt_path(s, a)


def res_of(s, a, suite="natv2_database"):
    return TIM / "evaluation" / ("A_seed%d_%s" % (s, a)) / suite / "results.jsonl" if a in NEW else P.results_path(s, a, suite)


def score(path):
    if path is None or not Path(path).exists():
        return None
    r = read_jsonl(path)
    return sum(bool(x["joint_success"]) for x in r) / 30 if len(r) == 30 else None


def timing(ck):
    L = read_jsonl(ck / "training_log.jsonl")
    total = json.load(open(ck / "train_summary.json", encoding="utf-8"))["optimizer_steps"]
    tg = []
    for x in L:
        if "target_db_filter_top" in x["episode_id"]:
            win = (x["microstep"] - 1) // ACC + 1
            tg.append({"t": x["episode_id"].rsplit("-", 1)[1], "pos": x["new_position"], "microstep": x["microstep"], "after": total - win + 1})
    af = [t["after"] for t in tg]
    return {"total_steps": total, "targets": tg, "n_target": len(tg), "sum_after": sum(af),
            "first_after": max(af, default=0), "last_after": min(af, default=0),
            "mom": sum(1 - BETA1 ** a for a in af)}


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def pearson(a, b):
    ma, mb = statistics.mean(a), statistics.mean(b)
    va, vb = sum((x - ma) ** 2 for x in a), sum((x - mb) ** 2 for x in b)
    return None if not va or not vb else sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def spearman(a, b):
    return pearson(rank(a), rank(b))


def resid(y, x):
    ry, rx = rank(y), rank(x)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    vx = sum((a - mx) ** 2 for a in rx)
    b = sum((a - mx) * (c - my) for a, c in zip(rx, ry)) / vx if vx else 0.0
    return [c - my - b * (a - mx) for a, c in zip(rx, ry)]


def partial(y, x, z):
    return pearson(resid(y, z), resid(x, z))


def logit_fit(X, k, n=30):
    """二项 logistic（每点 30 题）IRLS；返回系数与偏差。只作描述。"""
    X = np.column_stack([np.ones(len(k))] + [np.asarray(c, float) for c in X])
    k = np.asarray(k, float); b = np.zeros(X.shape[1])
    for _ in range(100):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30))); W = n * p * (1 - p) + 1e-9
        H = X.T @ (W[:, None] * X) + 1e-6 * np.eye(X.shape[1]); g = X.T @ (k - n * p)
        step = np.linalg.solve(H, g); b += step
        if np.abs(step).max() < 1e-10:
            break
    p = np.clip(1 / (1 + np.exp(-X @ b)), 1e-12, 1 - 1e-12)
    ll = np.sum(k * np.log(p) + (n - k) * np.log(1 - p))
    ps = np.clip(k / n, 1e-12, 1 - 1e-12); lls = np.sum(k * np.log(ps) + (n - k) * np.log(1 - ps))
    return {"coef": b.tolist(), "deviance": float(2 * (lls - ll)), "k_params": int(X.shape[1]), "pred": (p).tolist()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for s in SEEDS:
        for a in B1_ARMS:
            ck = ck_of(s, a)
            if not (ck / "training_log.jsonl").exists():
                continue
            b1 = score(res_of(s, a))
            if b1 is None:
                continue
            rows.append({"seed": s, "arm": a, "b1": b1, **timing(ck)})
    get = {(r["seed"], r["arm"]): r for r in rows}
    f3 = lambda x: "—" if x is None else "%.3f" % x
    mean = lambda v: statistics.mean(v) if v else None
    y = [r["b1"] for r in rows]
    feats = ["n_target", "sum_after", "mom", "first_after", "last_after"]
    corr_all = {f: spearman([r[f] for r in rows], y) for f in feats}
    pos = [r for r in rows if r["n_target"] >= 1]
    yp = [r["b1"] for r in pos]
    corr_pos = {f: spearman([r[f] for r in pos], yp) for f in feats}
    part = {}
    for nm, sub, yy in (("all", rows, y), ("n_target>=1", pos, yp)):
        g = lambda f: [r[f] for r in sub]
        part[nm] = {"n_target|sum_after": partial(yy, g("n_target"), g("sum_after")),
                    "sum_after|n_target": partial(yy, g("sum_after"), g("n_target")),
                    "n_target|mom": partial(yy, g("n_target"), g("mom")),
                    "mom|n_target": partial(yy, g("mom"), g("n_target")),
                    "last_after|n_target": partial(yy, g("last_after"), g("n_target")),
                    "n_target|last_after": partial(yy, g("n_target"), g("last_after"))}
    one = [r for r in rows if r["n_target"] == 1]
    corr_one = spearman([r["last_after"] for r in one], [r["b1"] for r in one])
    # ---- logistic（描述性，n_target>=1 的点；种子作固定效应）
    k = [round(r["b1"] * 30) for r in pos]
    sd = [[1.0 if r["seed"] == s else 0.0 for r in pos] for s in SEEDS[1:]]
    nt = [r["n_target"] for r in pos]; mo = [r["mom"] for r in pos]; sa = [r["sum_after"] for r in pos]
    fits = {"seed_only": logit_fit(sd, k), "n_target+seed": logit_fit([nt] + sd, k), "mom+seed": logit_fit([mo] + sd, k),
            "sum_after+seed": logit_fit([sa] + sd, k), "n_target+mom+seed": logit_fit([nt, mo] + sd, k)}
    # 用 mom+seed 模型给每个剂量做「只靠时机暴露」的预测，与实测对比
    pred_mom = fits["mom+seed"]["pred"]; pred_nt = fits["n_target+seed"]["pred"]
    for r, pm, pn in zip(pos, pred_mom, pred_nt):
        r["pred_mom_seed"], r["pred_ntarget_seed"] = pm, pn
    # ---- 曝露分箱
    def bin_of(v):
        return "0" if v == 0 else "1" if v == 1 else "2–4" if v <= 4 else "5–8" if v <= 8 else "9–15" if v <= 15 else "≥16"
    bins = {}
    for r in rows:
        bins.setdefault(bin_of(r["sum_after"]), []).append(r)
    # ---- 关键配对：同曝露、不同条数
    matched = []
    for s in SEEDS:
        m = {a: get.get((s, a)) for a in ["dose_db1", "dose_db1_pos143", "target_other_pos143", "tf25", "dose_db2", "dose_db3"]}
        matched.append({"seed": s, **{a: (None if v is None else {"b1": v["b1"], "n": v["n_target"], "sum_after": v["sum_after"],
                                                                     "mom": round(v["mom"], 3)}) for a, v in m.items()}})
    dose = {}
    for a in DOSE + ["dose_db1_pos143"]:
        rs = [get[(s, a)] for s in SEEDS if (s, a) in get]
        dose[a] = {"b1_mean": mean([r["b1"] for r in rs]), "n_target": mean([r["n_target"] for r in rs]),
                   "sum_after_mean": mean([r["sum_after"] for r in rs]), "mom_mean": mean([r["mom"] for r in rs]),
                   "pred_mom_seed_mean": mean([r.get("pred_mom_seed") for r in rs if "pred_mom_seed" in r]),
                   "pred_ntarget_seed_mean": mean([r.get("pred_ntarget_seed") for r in rs if "pred_ntarget_seed" in r])}
    # ---- 预算格子（B32 单列；含 b10/b20_tf50 的 B32 方便同协议比较）
    grid = []
    for g, a in B32_GRID.items():
        for s in SEEDS:
            ck = P.ckpt_path(s, a)
            if not (ck / "training_log.jsonl").exists():
                continue
            t = timing(ck)
            grid.append({"cell": g, "arm": a, "seed": s, "b32": score(P.historical_b32(s, a, "natv2_database")),
                         "b1": score(P.results_path(s, a, "natv2_database")), **t})
    gp = [r for r in grid if r["b32"] is not None]
    gy = [r["b32"] for r in gp]
    grid_corr = {"n_points": len(gp), "spearman_n_target": spearman([r["n_target"] for r in gp], gy),
                 "spearman_sum_after": spearman([r["sum_after"] for r in gp], gy),
                 "spearman_mom": spearman([r["mom"] for r in gp], gy),
                 "spearman_budget": spearman([{"b05": 5, "b10": 10, "b20": 20}[r["cell"][:3]] for r in gp], gy),
                 "partial_budget|mom": partial(gy, [{"b05": 5, "b10": 10, "b20": 20}[r["cell"][:3]] for r in gp], [r["mom"] for r in gp]),
                 "partial_n_target|mom": partial(gy, [r["n_target"] for r in gp], [r["mom"] for r in gp]),
                 "partial_mom|n_target": partial(gy, [r["mom"] for r in gp], [r["n_target"] for r in gp])}
    cells = {}
    for r in grid:
        c = cells.setdefault(r["cell"], {"b32": [], "b1": [], "n_target": [], "sum_after": [], "mom": [], "earliest": [], "total_steps": set()})
        if r["b32"] is not None: c["b32"].append(r["b32"])
        if r["b1"] is not None: c["b1"].append(r["b1"])
        c["n_target"].append(r["n_target"]); c["sum_after"].append(r["sum_after"]); c["mom"].append(r["mom"])
        c["earliest"].append(min([t["pos"] for t in r["targets"]], default=None)); c["total_steps"].add(r["total_steps"])
    cells = {g: {"b32_mean": mean(v["b32"]), "b1_mean": mean(v["b1"]), "n_target_mean": mean(v["n_target"]), "sum_after_mean": mean(v["sum_after"]),
                 "mom_mean": mean(v["mom"]), "earliest": v["earliest"], "total_steps": sorted(v["total_steps"])} for g, v in cells.items()}
    out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S %z"), "metric": "B1 nat v2 db.filter_cmp_top Joint Success (30)",
           "n_points_b1": len(rows), "n_points_b1_with_target": len(pos),
           "spearman_all": corr_all, "spearman_n_target_ge1": corr_pos, "partial_spearman": part,
           "one_target": {"n_points": len(one), "spearman_last_after": corr_one},
           "logistic_descriptive": {k2: {kk: vv for kk, vv in v.items() if kk != "pred"} for k2, v in fits.items()},
           "exposure_bins": {b: {"n": len(v), "b1_mean": mean([r["b1"] for r in v]),
                                 "by_n_target": {str(n): mean([r["b1"] for r in v if r["n_target"] == n])
                                                 for n in sorted({r["n_target"] for r in v})}} for b, v in bins.items()},
           "matched": matched, "dose": dose, "grid_rows": grid, "grid_cells": cells, "grid_corr_b32": grid_corr, "rows": rows}
    json.dump(out, open(OUT / "timing_audit.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_md(out)
    print(json.dumps({k2: out[k2] for k2 in ("spearman_all", "spearman_n_target_ge1", "partial_spearman", "one_target", "grid_corr_b32")},
                     ensure_ascii=False, indent=1))


def write_md(o):
    f3 = lambda x: "—" if x is None else "%.3f" % x
    sg = lambda x: "—" if x is None else "%+.3f" % x
    sd = lambda s: str(s)[-2:]
    get = {(r["seed"], r["arm"]): r for r in o["rows"]}
    L = ["# 插入时机审计：target 条数 vs target 之后的更新次数（只读，CPU）", "",
         "生成：%s。脚本 `.venv/bin/python scripts/p2_timing_audit.py`。主指标 = B1 nat v2 `db.filter_cmp_top` Joint Success（30 题；"
         "T0 就是 0，属于能力缺口及其恢复）。计数口径与 `scripts/p2_target_timing_check.py`、`fac_tinyagent/p2_timing.py` 相同："
         "之后更新次数 = 训练结束时 optimizer_steps − 该条目所在累积窗口序号 + 1（累积 8 步，含所在窗口那次）。"
         "动量加权 = Σ(1 − 0.9^之后更新次数)。只做描述，不做显著性陈述。" % o["generated"], "",
         "符号：n = target 条数；Σafter = 各条 target 之后更新次数之和（总 target 更新暴露）；first = 最早一条之后的更新次数；"
         "last = 最后一条之后的更新次数；mom = 动量加权。", ""]
    # 1. per-seed table
    L += ["## 1. 逐臂逐种子（B1，%d 个点；含本轮 6 个 pos143 新点）" % o["n_points_b1"], "",
          "| 臂 | 种子 | B1 | n | 各条 target（T / 位置 / 之后更新） | Σafter | first | last | mom | 总更新 |", "|---|---|---|---|---|---|---|---|---|---|"]
    order = ["dose_db0", "dose_db1", "dose_db1_pos143", "dose_db2", "dose_db3", "dose_db4", "dose_db6", "e3b2_A_target_other",
             "e3b2_A_target_dbbg", "target_other_pos143", "tf00", "tf25", "tf50", "b20_tf50", "ctrl_cal10", "ctrl_cal20"]
    for a in order:
        for s in SEEDS:
            r = get.get((s, a))
            if not r:
                continue
            L.append("| %s | %s | %s | %d | %s | %d | %d | %d | %s | %d |" % (a, sd(s), f3(r["b1"]), r["n_target"],
                     "；".join("T-%s/%d/%d" % (t["t"], t["pos"], t["after"]) for t in r["targets"]) or "—",
                     r["sum_after"], r["first_after"], r["last_after"], f3(r["mom"]), r["total_steps"]))
    # 2. correlations
    sa, sp, pa = o["spearman_all"], o["spearman_n_target_ge1"], o["partial_spearman"]
    L += ["", "## 2. 秩相关与偏秩相关（B1）", "",
          "| 预测量 | Spearman（全部 %d 点） | Spearman（n≥1，%d 点） |" % (o["n_points_b1"], o["n_points_b1_with_target"]), "|---|---|---|"]
    for k, nm in (("n_target", "n（target 条数）"), ("sum_after", "Σafter"), ("mom", "mom"), ("first_after", "first"), ("last_after", "last")):
        L.append("| %s | %s | %s |" % (nm, f3(sa[k]), f3(sp[k])))
    L += ["", "| 偏 Spearman | 全部点 | n≥1 |", "|---|---|---|"]
    for k, nm in (("n_target|sum_after", "n ｜ 控制 Σafter"), ("sum_after|n_target", "Σafter ｜ 控制 n"), ("n_target|mom", "n ｜ 控制 mom"),
                  ("mom|n_target", "mom ｜ 控制 n"), ("last_after|n_target", "last ｜ 控制 n"), ("n_target|last_after", "n ｜ 控制 last")):
        L.append("| %s | %s | %s |" % (nm, f3(pa["all"][k]), f3(pa["n_target>=1"][k])))
    L += ["", "只含 1 条 target 的 %d 个点（dose_db1、两个 e3b2 A 臂、tf25、两个 pos143 臂）：last vs B1 的 Spearman = %s。" % (
        o["one_target"]["n_points"], f3(o["one_target"]["spearman_last_after"])), ""]
    lg = o["logistic_descriptive"]
    L += ["### 2.1 描述性二项 logistic（n≥1 的 %d 点，每点 30 题，种子作固定效应）" % o["n_points_b1_with_target"], "",
          "| 模型 | 偏差（越小越贴合） | 关键系数 |", "|---|---|---|",
          "| 只有种子 | %.1f | — |" % lg["seed_only"]["deviance"],
          "| n + 种子 | %.1f | n：%+.3f |" % (lg["n_target+seed"]["deviance"], lg["n_target+seed"]["coef"][1]),
          "| Σafter + 种子 | %.1f | Σafter：%+.3f |" % (lg["sum_after+seed"]["deviance"], lg["sum_after+seed"]["coef"][1]),
          "| mom + 种子 | %.1f | mom：%+.3f |" % (lg["mom+seed"]["deviance"], lg["mom+seed"]["coef"][1]),
          "| n + mom + 种子 | %.1f | n：%+.3f；mom：%+.3f |" % (lg["n_target+mom+seed"]["deviance"], lg["n_target+mom+seed"]["coef"][1], lg["n_target+mom+seed"]["coef"][2]), ""]
    # 3. bins
    L += ["## 3. 按 Σafter 分箱：同暴露下 target 条数还起不起作用", "", "| Σafter | 点数 | B1 均值 | 按 n 分（n：B1 均值） |", "|---|---|---|---|"]
    for b in ["0", "1", "2–4", "5–8", "9–15", "≥16"]:
        v = o["exposure_bins"].get(b)
        if v:
            L.append("| %s | %d | %s | %s |" % (b, v["n"], f3(v["b1_mean"]), "；".join("%s：%s" % (k, f3(x)) for k, x in v["by_n_target"].items())))
    L += ["", "同种子、同暴露量级的直接比较（B1 / n / Σafter）：", "",
          "| 种子 | dose_db1 | dose_db1_pos143 | target_other_pos143 | tf25 | dose_db2 | dose_db3 |", "|---|---|---|---|---|---|---|"]
    for m in o["matched"]:
        L.append("| %s | %s |" % (sd(m["seed"]), " | ".join("—" if m[a] is None else "%s / %d / %d" % (f3(m[a]["b1"]), m[a]["n"], m[a]["sum_after"])
                                                           for a in ["dose_db1", "dose_db1_pos143", "target_other_pos143", "tf25", "dose_db2", "dose_db3"])))
    # 4. dose
    L += ["", "## 4. 剂量 S 曲线：实测 vs「只看暴露」预测", "",
          "预测值来自 §2.1 的两个单变量模型（各自 + 种子），三种子平均。", "",
          "| 臂 | n | Σafter 均值 | mom 均值 | B1 实测均值 | 预测：mom + 种子 | 预测：n + 种子 |", "|---|---|---|---|---|---|---|"]
    for a, v in o["dose"].items():
        L.append("| %s | %s | %s | %s | %s | %s | %s |" % (a, f3(v["n_target"]) if a != "dose_db0" else "0", f3(v["sum_after_mean"]), f3(v["mom_mean"]),
                                                       f3(v["b1_mean"]), f3(v["pred_mom_seed_mean"]), f3(v["pred_ntarget_seed_mean"])))
    # 5. grid
    gc = o["grid_corr_b32"]
    L += ["", "## 5. 预算 × target 比例（覆盖 vs 预算）", "",
          "b05 与 b20_tf00 / b20_tf25 只有历史 B32，所以本节相关统一用 B32（%d 点），B1 均值另列，两种协议不混算。" % gc["n_points"], "",
          "| 格子 | B32 均值 | B1 均值 | n 均值 | Σafter 均值 | mom 均值 | 最早插入位置（08/09/10） | 总更新 |", "|---|---|---|---|---|---|---|---|"]
    for g, v in o["grid_cells"].items():
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (g, f3(v["b32_mean"]), f3(v["b1_mean"]), f3(v["n_target_mean"]), f3(v["sum_after_mean"]),
                                                          f3(v["mom_mean"]), "/".join("—" if e is None else str(e) for e in v["earliest"]),
                                                          ",".join(map(str, v["total_steps"]))))
    L += ["", "| B32，%d 点 | 值 |" % gc["n_points"], "|---|---|",
          "| Spearman：预算（5/10/20） | %s |" % f3(gc["spearman_budget"]), "| Spearman：n | %s |" % f3(gc["spearman_n_target"]),
          "| Spearman：Σafter | %s |" % f3(gc["spearman_sum_after"]), "| Spearman：mom | %s |" % f3(gc["spearman_mom"]),
          "| 偏 Spearman：预算 ｜ 控制 mom | %s |" % f3(gc["partial_budget|mom"]), "| 偏 Spearman：n ｜ 控制 mom | %s |" % f3(gc["partial_n_target|mom"]),
          "| 偏 Spearman：mom ｜ 控制 n | %s |" % f3(gc["partial_mom|n_target"]), ""]
    L += INTERP
    (OUT / "timing_audit_ZH.md").write_text("\n".join(L) + "\n", encoding="utf-8")


INTERP = [
    "## 6. 解读",
    "",
    "**(1) 剂量 S 曲线。** 在 n≥1 的 36 个 B1 点上，Σafter（0.936）和 mom（0.928）的秩相关都高于 n（0.811）；控制 Σafter 后 n 的偏秩相关是 −0.086，"
    "控制 mom 后是 −0.199；反过来控制 n 后 Σafter 仍有 0.799。描述性 logistic 里 mom + 种子的偏差 65.3，n + 种子 124.0；"
    "在 mom 之上再加 n，系数为 −0.095，偏差只降到 64.9。同暴露分箱里看得最清楚：Σafter 2–4 这一档，1 条 target 均值 0.430、2 条 0.400、3 条 0.267，"
    "条数多并没有更好。",
    "",
    "因此，原来「S 曲线由独立 target 条数决定，1 条几乎无效，4–6 条基本恢复」的说法要改。1 条插在第 159 位只有 1 次更新，所以接近无效（0.100）；"
    "同一条挪到第 143 位就有 0.389–0.467。剂量 1→2 原来的 +0.300（0.100→0.400），几乎全部可以由暴露解释："
    "dose_db1_pos143（1 条，Σafter 3.3）0.389，dose_db2（2 条，Σafter 3.3）0.400。剂量 2→6 那一段的上升与 Σafter 从 3.3 升到 15.7 完全同步，"
    "现有臂里条数和暴露高度共线，没有「多条但都很晚」或「少条但很早」的点，分不开。另外，只看「最后一条之后的更新次数」不够（n≥1 时 Spearman 0.075，控制它后 n 仍有 0.892），起作用的是所有 target 的总暴露。能留下来的结论是：**恢复量随 target 模式获得的更新暴露单调上升，"
    "曲线形状仍是 S 形，但横轴应写成暴露量（条数 × 之后更新次数），不是条数。** 在 B1 的剂量和位置点上，看不到「独立条数」在暴露之外还有额外作用。但 §5 的 B32 格子里两者分不开（控制 mom 后 n 0.330，控制 n 后 mom 0.105），所以「只有暴露、条数无关」目前只是 B1 剂量点上的描述，要靠一组直接把两者拆开的实验来定。",
    "",
    "**(2) 「覆盖比预算更重要」。** 定性部分保留，而且更清楚了：没有 target 模式的复习（ctrl_cal、b05_tf00/tf25、b10_tf00）不管预算多大都在 0 附近；"
    "B32 格子里预算本身与成绩的秩相关 0.685，控制 mom 后降到 −0.033，预算只是通过「带进来多少 target 暴露」起作用。"
    "例如 b20_tf00 没有定向比例，却因为随机抽到的 target 插在第 95 / 103 位（之后 12–14 次更新）得到 B32 0.722；"
    "它的 mom 0.776 与 dose_db4（mom 0.815，B1 0.800）接近（b10 三格 B1 与 B32 相差不超过 0.02，可作粗略参照）。需要改的是「覆盖」的定义：只数「有没有 / 有几条」不够，要把插入时机算进去。"
    "论文里建议写成「复习什么、在何时复习，比复习多少更重要」，并把覆盖度量换成 target 模式的更新暴露。Calendar v3 在 20% 预算下的代价是另一件事，不受本审计影响。",
    "",
    "**(3) 与 v2 梯度 pilot、近邻假设的关系。** tf25 高于实验 A 两臂，本轮单变量对照已经由插入位置解释（H-timing 支持）；"
    "不需要再用「近邻经验」或 target 条目身份（T-005 / T-008 vs T-001）去解释这 0.3 的差距。",
]


if __name__ == "__main__":
    main()
