#!/usr/bin/env python3
"""[ext 2026-11-14] 饱和暴露模型拟合（只读，CPU）。
输入：runs_ext_e3b2_timing/analysis/timing_audit.json（48 点）+ runs_ext_p3_count_timing/summary.json（P3 三臂 9 点）。
主指标：B1 nat v2 db.filter_cmp_top Joint Success（30 题）。每点 = 每条 target 的「之后更新次数」列表 after_i。
覆盖特征 x 经二项 logistic 映射到 JS：JS = cap · σ(b0 + b1·x)，cap=1（标准）或网格（带上限）。不用种子固定效应（留一种子要能外推）。
评估：全数据偏差、Spearman(x, JS)、留一种子（按 08/09/10 留一；τ/K 在训练种子上内层重选）MAE / RMSE / 偏差。
输出：runs_ext_p3_count_timing/analysis/saturation_fit.json；图 fig_saturation_coverage_vs_JS.png（需要 matplotlib）。
用法：python scripts/p3_saturation_fit.py --root <项目根>
"""
import argparse, json, math
from pathlib import Path
import numpy as np
np.seterr(all="ignore")

N = 30
SEEDS = [20261108, 20261109, 20261110]
P3ARMS = ["dose_db1_pos127", "dose_db4_late", "dose_db1_pos95"]
TAUS = [round(x, 2) for x in np.arange(0.5, 20.01, 0.25)]
KS = list(range(1, 16))
CAPS = [round(x, 2) for x in np.arange(0.80, 1.001, 0.02)]


def load(root):
    a = json.loads((root / "runs_ext_e3b2_timing/analysis/timing_audit.json").read_text(encoding="utf-8"))
    s = json.loads((root / "runs_ext_p3_count_timing/summary.json").read_text(encoding="utf-8"))
    pts = [dict(src="timing_audit", seed=r["seed"], arm=r["arm"], y=r["b1"], afters=[t["after"] for t in r["targets"]],
                tids=[t["t"] for t in r["targets"]]) for r in a["rows"] if r.get("b1") is not None]
    pts += [dict(src="p3", seed=r["seed"], arm=r["arm"], y=r["main"], afters=[int(t.split("/")[-1]) for t in r["targets"]],
                 tids=[t.split("@")[0].split("-")[1] for t in r["targets"]]) for r in s["rows"] if r["arm"] in P3ARMS]
    return pts


# target 条目所查的表（data_ext_e4/pool/database.jsonl 的 SQL）：products = T-000/001/009，其余 employees
TABLE = {"000": "products", "001": "products", "009": "products"}


def feature(kind, par, afters, tids=None):
    A = afters
    if kind in ("tab_exp", "tab_cap"):
        per = {}
        for a_, t_ in zip(A, tids):
            per.setdefault(TABLE.get(t_, "employees"), []).append(a_)
        if kind == "tab_exp": return sum(1 - math.exp(-sum(v) / par) for v in per.values())
        return sum(min(1.0, sum(min(x, par) for x in v) / par) for v in per.values())
    if kind == "n": return float(len(A))
    if kind == "sum_after": return float(sum(A))
    if kind == "mom": return sum(1 - 0.9 ** x for x in A)
    if kind == "exp": return sum(1 - math.exp(-x / par) for x in A)          # C_tau
    if kind == "cap": return sum(min(x, par) / par for x in A)               # 每条硬上限 K
    raise KeyError(kind)


def fit_logit(x, k, cap=1.0, iters=200):
    """k/N ~ cap·σ(b0+b1 x)；cap<1 时用简单牛顿+阻尼（数值梯度）。返回 b, 预测 p。"""
    X = np.column_stack([np.ones(len(x)), x])
    b = np.zeros(2)
    def nll(bb):
        p = np.clip(cap / (1 + np.exp(-np.clip(X @ bb, -30, 30))), 1e-9, 1 - 1e-9)
        return -np.sum(k * np.log(p) + (N - k) * np.log(1 - p))
    if cap >= 0.9999:
        for _ in range(iters):
            p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30))); W = N * p * (1 - p) + 1e-9
            H = X.T @ (W[:, None] * X) + 1e-8 * np.eye(2); g = X.T @ (k - N * p)
            st = np.linalg.solve(H, g); b += st
            if np.abs(st).max() < 1e-10: break
    else:
        b = fit_logit(x, np.minimum(k, N * cap - 1e-6) , 1.0)[0]
        for _ in range(iters):
            f0 = nll(b); g = np.zeros(2); H = np.zeros((2, 2)); e = 1e-4
            for i in range(2):
                d = np.zeros(2); d[i] = e; g[i] = (nll(b + d) - nll(b - d)) / (2 * e)
                for j in range(2):
                    d2 = np.zeros(2); d2[j] = e
                    H[i, j] = (nll(b + d + d2) - nll(b + d - d2) - nll(b - d + d2) + nll(b - d - d2)) / (4 * e * e)
            try: st = -np.linalg.solve(H + 1e-6 * np.eye(2), g)
            except np.linalg.LinAlgError: break
            t = 1.0
            while nll(b + t * st) > f0 and t > 1e-4: t /= 2
            b = b + t * st
            if np.abs(t * st).max() < 1e-8: break
    p = cap / (1 + np.exp(-np.clip(X @ b, -30, 30)))
    return b, p


def deviance(k, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(2 * np.sum(np.where(k > 0, k * np.log(np.maximum(k, 1e-12) / (N * p)), 0)
                            + np.where(N - k > 0, (N - k) * np.log(np.maximum(N - k, 1e-12) / (N * (1 - p))), 0)))


def rank(v):
    o = np.argsort(v, kind="mergesort"); r = np.empty(len(v)); i = 0; v = np.asarray(v)
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[o[j + 1]] == v[o[i]]: j += 1
        r[o[i:j + 1]] = (i + j) / 2; i = j + 1
    return r


def spearman(a, b):
    ra, rb = rank(a), rank(b)
    return float(np.corrcoef(ra, rb)[0, 1])


FAMS = {"n": [None], "sum_after": [None], "mom": [None], "exp": TAUS, "cap": KS, "tab_exp": TAUS, "tab_cap": KS}


def best_in_family(kind, pts, k, capgrid):
    best = None
    for par in FAMS[kind]:
        x = np.array([feature(kind, par, p["afters"], p["tids"]) for p in pts])
        for cap in capgrid:
            b, pr = fit_logit(x, k, cap)
            d = deviance(k, pr)
            if best is None or d < best["dev"]:
                best = dict(par=par, cap=cap, b=b, dev=d)
    return best


def predict(kind, par, cap, b, afters, tids=None):
    x = feature(kind, par, afters, tids)
    return float(cap / (1 + math.exp(-(b[0] + b[1] * x))))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default="."); ap.add_argument("--no-fig", action="store_true")
    root = Path(ap.parse_args().root)
    pts = load(root)
    y = np.array([p["y"] for p in pts]); k = np.round(y * N)
    models = {}
    variants = [(kind, capg) for kind in FAMS for capg in (("logit", [1.0]), ("capped_logit", CAPS))]
    keyarms = ["dose_db1", "dose_db1_pos143", "dose_db1_pos127", "dose_db4_late", "dose_db1_pos95", "dose_db2", "dose_db3", "dose_db4", "dose_db6", "tf25"]
    obs = {a: float(np.mean([p["y"] for p in pts if p["arm"] == a])) for a in keyarms}
    for kind, (lname, capgrid) in variants:
        name = "%s|%s" % (kind, lname)
        full = best_in_family(kind, pts, k, capgrid)
        x = np.array([feature(kind, full["par"], p["afters"], p["tids"]) for p in pts])
        pr = np.array([predict(kind, full["par"], full["cap"], full["b"], p["afters"], p["tids"]) for p in pts])
        # 留一种子：训练种子上重选 τ/K/cap
        loso, pl = {}, np.zeros(len(pts))
        for s in SEEDS:
            tr = [p for p in pts if p["seed"] != s]; ktr = np.round(np.array([p["y"] for p in tr]) * N)
            bf = best_in_family(kind, tr, ktr, capgrid)
            idx = [i for i, p in enumerate(pts) if p["seed"] == s]
            for i in idx: pl[i] = predict(kind, bf["par"], bf["cap"], bf["b"], pts[i]["afters"], pts[i]["tids"])
            loso[str(s)[-2:]] = dict(par=bf["par"], cap=bf["cap"], mae=float(np.mean(np.abs(pl[idx] - y[idx]))))
        am = lambda arr, a: float(np.mean([arr[i] for i, p in enumerate(pts) if p["arm"] == a]))
        models[name] = dict(kind=kind, link=lname, par=full["par"], cap=full["cap"], coef=[float(c) for c in full["b"]],
                            deviance=round(full["dev"], 2), spearman=round(spearman(x, y), 3),
                            loso_mae=round(float(np.mean(np.abs(pl - y))), 4), loso_rmse=round(float(np.sqrt(np.mean((pl - y) ** 2))), 4),
                            loso_deviance=round(deviance(k, np.clip(pl, 1e-6, 1 - 1e-6)), 2), loso_by_seed=loso,
                            arm_pred_full={a: round(am(pr, a), 3) for a in keyarms},
                            arm_pred_loso={a: round(am(pl, a), 3) for a in keyarms},
                            checks_full=dict(pos95_minus_db4=round(am(pr, "dose_db1_pos95") - am(pr, "dose_db4"), 3),
                                             pos127_minus_db4late=round(am(pr, "dose_db1_pos127") - am(pr, "dose_db4_late"), 3),
                                             pos95_minus_pos127=round(am(pr, "dose_db1_pos95") - am(pr, "dose_db1_pos127"), 3)),
                            checks_loso=dict(pos95_minus_db4=round(am(pl, "dose_db1_pos95") - am(pl, "dose_db4"), 3),
                                             pos127_minus_db4late=round(am(pl, "dose_db1_pos127") - am(pl, "dose_db4_late"), 3),
                                             pos95_minus_pos127=round(am(pl, "dose_db1_pos95") - am(pl, "dose_db1_pos127"), 3)),
                            _pred=pr.tolist(), _loso=pl.tolist())
    obs_checks = dict(pos95_minus_db4=round(obs["dose_db1_pos95"] - obs["dose_db4"], 3),
                      pos127_minus_db4late=round(obs["dose_db1_pos127"] - obs["dose_db4_late"], 3),
                      pos95_minus_pos127=round(obs["dose_db1_pos95"] - obs["dose_db1_pos127"], 3))
    # τ 剖面（标准 logistic，全数据）
    prof = {}
    for t in TAUS:
        x = np.array([feature("exp", t, p["afters"], p["tids"]) for p in pts]); b, pr = fit_logit(x, k)
        prof[str(t)] = round(deviance(k, pr), 2)
    kprof = {}
    for K in KS:
        x = np.array([feature("cap", K, p["afters"], p["tids"]) for p in pts]); b, pr = fit_logit(x, k)
        kprof[str(K)] = round(deviance(k, pr), 2)
    # 判定：两个关键检查（与预注册阈值 0.10 同口径）
    def passes(c):
        return dict(pos95_below_db4=bool(c["pos95_minus_db4"] <= -0.10),
                    pos127_approx_db4late=bool(abs(c["pos127_minus_db4late"]) <= 0.10))
    for m in models.values():
        m["pass_full"] = passes(m["checks_full"]); m["pass_loso"] = passes(m["checks_loso"])
    ranking = sorted(models, key=lambda n: models[n]["loso_mae"])
    best = ranking[0]
    B = models[best]
    # 新分配方案（只做预测，不构建）：dose_db4 源计划 22 槽 after 映射见 md；db4_early = 127×2 + 135×2；db2_early = 127×2
    # 新分配方案（只做预测，不构建）。槽位 → 之后更新次数（dose_db4 / dose_db2 源计划 22–23 槽，三种子相同）：
    # 87:13/12, 95:11, 103:10, 111:9, 119:8/7/7, 127:6/6, 135:5/5, 143:4/4(3), 151:2/2, 159:1/1/1
    D4 = {20261108: ["009", "004", "001", "000"], 20261109: ["005", "001", "006", "008"], 20261110: ["009", "007", "001", "002"]}
    D2 = {20261108: ["001", "000"], 20261109: ["005", "001"], 20261110: ["009", "001"]}
    BAL = {20261108: ["001", "004"], 20261109: ["005", "001"], 20261110: ["001", "007"]}   # 1 products + 1 employees（取自同种子 dose_db4/db2 的 target）
    plans = {"db4_early(127,127,135,135)": ([6, 6, 5, 5], D4), "db4_early_alt(119,119,127,127)": ([7, 7, 6, 6], D4),
             "db2_early(127,127)|dose_db2 原 target": ([6, 6], D2), "db2_early(127,127)|表平衡 target": ([6, 6], BAL),
             "ref dose_db4": (None, None), "ref db4_late": (None, None), "ref pos127": (None, None), "ref pos95": (None, None)}
    REF = {"ref dose_db4": "dose_db4", "ref db4_late": "dose_db4_late", "ref pos127": "dose_db1_pos127", "ref pos95": "dose_db1_pos95"}
    preds = {}
    show = list(dict.fromkeys(ranking[:3] + ["cap|logit", "exp|logit", "tab_cap|logit", "tab_exp|logit", "mom|logit", "sum_after|logit", "n|logit"]))
    loso_fits = {}
    for mn in show:
        m = models[mn]; loso_fits[mn] = []
        for s in SEEDS:
            tr = [p for p in pts if p["seed"] != s]; ktr = np.round(np.array([p["y"] for p in tr]) * N)
            loso_fits[mn].append(best_in_family(m["kind"], tr, ktr, [m["cap"]] if m["link"] == "logit" else CAPS))
    for pn, (af, tmap) in plans.items():
        row = {}
        for mn in show:
            m = models[mn]
            if pn in REF:
                ps = [p for p in pts if p["arm"] == REF[pn]]
                cfg = [(p["afters"], p["tids"]) for p in ps]
            else:
                cfg = [(af, tmap[s]) for s in SEEDS]
            full = [predict(m["kind"], m["par"], m["cap"], np.array(m["coef"]), a_, t_) for a_, t_ in cfg]
            rng = [predict(m["kind"], bf["par"], bf["cap"], bf["b"], a_, t_) for bf in loso_fits[mn] for a_, t_ in cfg]
            row[mn] = dict(per_seed=[round(v, 3) for v in full], mean=round(float(np.mean(full)), 3),
                           loso_range=[round(min(rng), 3), round(max(rng), 3)])
        if pn in REF:
            row["observed"] = round(obs.get(REF[pn], float(np.mean([p["y"] for p in pts if p["arm"] == REF[pn]]))), 3)
        else:
            row["afters"] = af; row["targets"] = {str(s)[-2:]: tmap[s] for s in SEEDS}
        preds[pn] = row
    out = dict(generated="2026-11-14 (Asia/Shanghai)", metric="B1 nat v2 db.filter_cmp_top Joint Success (30)",
               n_points=len(pts), n_timing_audit=sum(p["src"] == "timing_audit" for p in pts), n_p3=sum(p["src"] == "p3" for p in pts),
               observed_arm_means={a: round(v, 3) for a, v in obs.items()}, observed_checks=obs_checks,
               ranking_by_loso_mae=ranking, best_model=best,
               models={n: {kk: vv for kk, vv in m.items() if not kk.startswith("_")} for n, m in models.items()},
               tau_profile_logit=prof, K_profile_logit=kprof, predictions=preds,
               points=[dict(seed=p["seed"], arm=p["arm"], src=p["src"], y=p["y"], afters=p["afters"],
                            x_best=round(feature(B["kind"], B["par"], p["afters"], p["tids"]), 4), pred_best=round(B["_pred"][i], 4),
                            loso_best=round(B["_loso"][i], 4)) for i, p in enumerate(pts)])
    od = root / "runs_ext_p3_count_timing/analysis"; od.mkdir(parents=True, exist_ok=True)
    (od / "saturation_fit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({n: dict(dev=m["deviance"], sp=m["spearman"], mae=m["loso_mae"], par=m["par"], cap=m["cap"],
                              cf=m["checks_full"], cl=m["checks_loso"]) for n, m in ((n, models[n]) for n in ranking)}, indent=0, ensure_ascii=False))
    print("best", best); print(json.dumps(preds, indent=0))
    print("tau", prof); print("K", kprof)
    if not ap.parse_args().no_fig:
        figure(out, models, pts, od / "figures_p3")


def figure(out, models, pts, od):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for f in ("Noto Sans CJK SC", "Noto Sans CJK JP", "Microsoft YaHei", "SimHei", "WenQuanYi Zen Hei"):
        if any(f == x.name for x in font_manager.fontManager.ttflist):
            plt.rcParams["font.sans-serif"] = [f]; break
    plt.rcParams["axes.unicode_minus"] = False
    od.mkdir(parents=True, exist_ok=True)
    B = models[out["best_model"]]; E = models["exp|logit"]
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.2), sharey=True)
    cmap = plt.get_cmap("viridis")
    special = {"dose_db1_pos127": ("*", "pos127"), "dose_db4_late": ("P", "db4_late"), "dose_db1_pos95": ("X", "pos95"),
               "dose_db4": ("s", "dose_db4"), "dose_db1": ("v", "dose_db1"), "dose_db1_pos143": ("^", "pos143")}
    for ax, (kind, par, lab, m) in zip(axes, [("sum_after", None, "Σafter（不饱和，旧横轴）", models["sum_after|logit"]),
                                               ("exp", E["par"], "C_τ = Σ(1−exp(−after/τ))，τ=%.2f" % E["par"], E),
                                               (B["kind"], B["par"], "最佳（留一种子 MAE）：%s %s" % (out["best_model"], B["par"]), B)]):
        xs = np.array([feature(kind, par, p["afters"], p["tids"]) for p in pts])
        for p, xv in zip(pts, xs):
            mk, _ = special.get(p["arm"], ("o", None))
            ax.scatter(xv, p["y"], s=110 if mk in "*PX" else 40, marker=mk, color=cmap(min(len(p["afters"]), 8) / 8),
                       edgecolor="k", lw=0.5, zorder=3)
        g = np.linspace(0, xs.max() * 1.05, 200)
        ax.plot(g, m["cap"] / (1 + np.exp(-(m["coef"][0] + m["coef"][1] * g))), "r-", lw=1.5, zorder=2,
                label="拟合（全数据，偏差 %.0f，留一种子 MAE %.3f）" % (m["deviance"], m["loso_mae"]))
        for a, (mk, nm) in special.items():
            v = [(xv, p["y"]) for p, xv in zip(pts, xs) if p["arm"] == a]
            if v:
                ax.annotate(nm, (np.mean([t[0] for t in v]), np.mean([t[1] for t in v])), textcoords="offset points", xytext=(6, 6), fontsize=8)
        ax.set_xlabel(lab); ax.grid(alpha=0.3); ax.legend(fontsize=7.5, loc="lower right")
    axes[0].set_ylabel("B1 nat v2 db.filter_cmp_top Joint Success（30 题）"); axes[0].set_ylim(-0.04, 1.04)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 8)); sm.set_array([])
    fig.colorbar(sm, ax=axes, label="target 条数 n（颜色）", fraction=0.02, pad=0.01)
    fig.suptitle("饱和覆盖 vs JS（B1，57 点 = 时机审计 48 + P3 9）：星 pos127，十字 db4_late，X pos95，方块 dose_db4", fontsize=11)
    fig.savefig(od / "fig_saturation_coverage_vs_JS.png", dpi=160, bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    main()
