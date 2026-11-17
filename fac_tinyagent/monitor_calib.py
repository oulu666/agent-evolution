"""[ext 2026-11-11] Offline calibration of Monitor v2 (CPU only, read-only).

Units = the 15 offline units of runs_ext_monitor (scenario x seed x old family; A: 9, C: 6).
Features come from the v2 probe set (File re-scored with corrected_joint):
  p0 = probe score at stage start, p1 = at the midpoint (decision time),
  pref = probe score at the family's own reference checkpoint (right after it was trained;
         = p0 for the family trained just before the new stage).
Gold (from monitor_eval.json, independent natural final at end of the no-replay arm):
  G_need (end < 0.80), G_cum (end <= ref - 0.10).
Models (few parameters on purpose, n = 15): ridge-logistic on p1; on (p1, p0-p1); on (p1, pref-p1);
isotonic (monotone decreasing) on p1.  Validation: leave-one-seed-out (3 folds) and
leave-one-scenario-out (2 folds), out-of-fold probabilities pooled.  Baselines: rule2 (as used
by v2: DEGRADED or DEFICIENT -> flag) and a fixed threshold p1 < 0.8.
External replicate: E4 + E2 `none` runs (A, Database/Python only; training-time probe scores are raw
joint, identical to corrected for these families), model fitted on all 15 units.
Output: runs_ext_monitor_calib/{calibration.json, report.md}.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .monitor_v2 import FLAGGED, wilson
from .monitor_v2_offline import SCEN, _eval_dir, _kn
from .utils import ensure_dir, read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs_ext_monitor_calib"
GOLDS = ["G_need", "G_cum"]


def _logit(p: float) -> float:
    p = min(max(p, 0.02), 0.98)
    return math.log(p / (1 - p))


def units() -> List[Dict[str, Any]]:
    m = read_json(ROOT / "runs_ext_monitor" / "monitor_eval.json")
    out = []
    for u in m["units"]:
        s, seed, fam = u["scenario"], u["seed"], u["family"]
        d = u["detectors"]["V2probes+rule2_pooled"]
        ref_name, _ = SCEN[s]["refs"][fam]
        if ref_name == SCEN[s]["start"][0]:
            pref = d["p0"]
        else:
            kn = _kn(_eval_dir(s, seed, "ref_" + ref_name, "monitor_v2", fam) / "results.jsonl", True)
            pref = kn[0] / kn[1] if kn else None
        out.append({"scenario": s, "seed": seed, "family": fam, "p0": d["p0"], "p1": d["p1"], "n1": d["n1"],
                    "pref": pref, "rule2_status": d["status"],
                    "rule2_subsetmax_status": u["detectors"]["V2probes+rule2_subsetmax"]["status"],
                    "gold": u["gold"], "gold_scores": u["gold_scores_fixed"]})
    return out


def feats(u: Dict[str, Any], kind: str) -> List[float]:
    if kind == "p1":
        return [_logit(u["p1"])]
    if kind == "p1+drop":
        return [_logit(u["p1"]), u["p0"] - u["p1"]]
    if kind == "p1+refdrop":
        return [_logit(u["p1"]), u["pref"] - u["p1"]]
    raise ValueError(kind)


def fit_logistic(X: np.ndarray, y: np.ndarray, lam: float = 1.0) -> Callable[[np.ndarray], np.ndarray]:
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
    w = np.zeros(Z.shape[1])
    R = np.eye(Z.shape[1]) * lam
    R[0, 0] = 1e-4  # (almost) unpenalised intercept
    for _ in range(100):
        p = 1 / (1 + np.exp(-Z @ w))
        g = Z.T @ (p - y) + R @ w
        H = Z.T @ (Z * (p * (1 - p))[:, None]) + R
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break

    def pred(Xn: np.ndarray) -> np.ndarray:
        Zn = np.hstack([np.ones((len(Xn), 1)), (Xn - mu) / sd])
        return 1 / (1 + np.exp(-Zn @ w))
    return pred


def fit_isotonic_decreasing(x: np.ndarray, y: np.ndarray) -> Callable[[np.ndarray], np.ndarray]:
    """P(need) non-increasing in probe score; pool-adjacent-violators on -x; Laplace-smoothed blocks."""
    order = np.argsort(-x)
    xs, ys = -x[order], y[order].astype(float)
    blocks = [[xs[i], xs[i], ys[i], 1.0] for i in range(len(xs))]  # lo, hi, sum, n
    i = 0
    while i < len(blocks) - 1:
        a, b = blocks[i], blocks[i + 1]
        if a[2] / a[3] > b[2] / b[3]:
            blocks[i] = [a[0], b[1], a[2] + b[2], a[3] + b[3]]
            del blocks[i + 1]
            i = max(i - 1, 0)
        else:
            i += 1
    pts = [((bl[0] + bl[1]) / 2, (bl[2] + 0.5) / (bl[3] + 1.0)) for bl in blocks]

    def pred(xn: np.ndarray) -> np.ndarray:
        q = -np.asarray(xn, float)
        cx = np.array([p[0] for p in pts]); cy = np.array([p[1] for p in pts])
        return np.interp(q, cx, cy)
    return pred


MODELS = ["logit(p1)", "logit(p1, p0-p1)", "logit(p1, pref-p1)", "isotonic(p1)"]


def model_fit(name: str, train: List[Dict[str, Any]], gold: str):
    y = np.array([int(u["gold"][gold]) for u in train])
    if len(set(y.tolist())) < 2:
        c = float(y.mean())
        return lambda us: np.full(len(us), (y.sum() + 0.5) / (len(y) + 1.0))
    if name == "isotonic(p1)":
        f = fit_isotonic_decreasing(np.array([u["p1"] for u in train]), y)
        return lambda us: f(np.array([u["p1"] for u in us]))
    kind = {"logit(p1)": "p1", "logit(p1, p0-p1)": "p1+drop", "logit(p1, pref-p1)": "p1+refdrop"}[name]
    f = fit_logistic(np.array([feats(u, kind) for u in train]), y)
    return lambda us: f(np.array([feats(u, kind) for u in us]))


def metrics(probs: List[float], ys: List[int], thr: float = 0.5) -> Dict[str, Any]:
    p, y = np.array(probs, float), np.array(ys, int)
    flag = p >= thr
    tp = int(((flag == 1) & (y == 1)).sum()); fn = int(((flag == 0) & (y == 1)).sum())
    fp = int(((flag == 1) & (y == 0)).sum()); tn = int(((flag == 0) & (y == 0)).sum())
    bins = np.linspace(0, 1, 6)
    ece = 0.0
    for i in range(5):
        m = (p >= bins[i]) & ((p < bins[i + 1]) if i < 4 else (p <= 1))
        if m.any():
            ece += m.mean() * abs(p[m].mean() - y[m].mean())
    pos, neg = y.sum(), (1 - y).sum()
    auc = None
    if pos and neg:
        pp, nn = p[y == 1], p[y == 0]
        auc = float(np.mean([(a > b) + 0.5 * (a == b) for a in pp for b in nn]))
    return {"n": len(y), "pos": int(pos), "tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "recall": tp / pos if pos else None, "fpr": fp / neg if neg else None,
            "brier": float(np.mean((p - y) ** 2)), "ece5": float(ece), "auc": auc}


def cross_val(U: List[Dict[str, Any]], name: str, gold: str, key: str) -> List[float]:
    probs = [None] * len(U)
    for g in sorted({u[key] for u in U}):
        tr = [u for u in U if u[key] != g]
        te_idx = [i for i, u in enumerate(U) if u[key] == g]
        f = model_fit(name, tr, gold)
        out = f([U[i] for i in te_idx])
        for i, v in zip(te_idx, out):
            probs[i] = float(v)
    return probs


def external_units(U: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    res = read_json(ROOT / "runs_ext_e4" / "results.json")
    byk = {(u["seed"], u["family"]): u for u in U if u["scenario"] == "A"}
    out = []
    for r in res["rows"]:
        if r["arm"] != "none":
            continue
        for fam in ("database", "python"):
            base = byk[(r["seed"], fam)]
            end = r["nat_" + fam]
            ref = base["gold_scores"]["ref"]
            p0, p1 = r["probe_start"][fam], r["probe_mid"][fam]
            out.append({"scenario": "A", "round": r["round"], "seed": r["seed"], "family": fam,
                        "p0": p0, "p1": p1, "n1": 32,
                        "pref": p0 if fam == "python" else base["pref"],
                        "gold": {"G_need": end < 0.8, "G_cum": end <= ref - 0.1 + 1e-9},
                        "gold_scores": {"end_none": end, "ref": ref}})
    return out


def run() -> Dict[str, Any]:
    U = units()
    res: Dict[str, Any] = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "units": U, "results": {}}
    for gold in GOLDS:
        ys = [int(u["gold"][gold]) for u in U]
        R = {}
        R["baseline rule2 (v2 pooled)"] = {"in_sample": metrics([1.0 if u["rule2_status"] in FLAGGED else 0.0 for u in U], ys)}
        R["baseline rule2 subset-max"] = {"in_sample": metrics([1.0 if u["rule2_subsetmax_status"] in FLAGGED else 0.0 for u in U], ys)}
        R["baseline fixed p1<0.8"] = {"in_sample": metrics([1.0 if u["p1"] < 0.8 else 0.0 for u in U], ys)}
        R["baseline Wilson-upper(p1)<0.8"] = {"in_sample": metrics([1.0 if wilson(round(u["p1"] * u["n1"]), u["n1"])[1] < 0.8 else 0.0 for u in U], ys)}
        R["baseline prevalence (constant)"] = {"in_sample": metrics([mean(ys)] * len(U), ys)}
        for name in MODELS:
            loso = cross_val(U, name, gold, "seed")
            losc = cross_val(U, name, gold, "scenario")
            ins = model_fit(name, U, gold)(U)
            R[name] = {"LOSO_seed": metrics(loso, ys), "LOSO_scenario": metrics(losc, ys),
                       "in_sample_optimistic": metrics([float(x) for x in ins], ys),
                       "oof_probs_seed": [round(x, 3) for x in loso]}
        res["results"][gold] = R
    ext = external_units(U)
    res["external"] = {"units": ext, "results": {}}
    for gold in GOLDS:
        ys = [int(u["gold"][gold]) for u in ext]
        R = {"baseline fixed p1<0.8": metrics([1.0 if u["p1"] < 0.8 else 0.0 for u in ext], ys),
             "baseline Wilson-upper(p1)<0.8": metrics([1.0 if wilson(round(u["p1"] * 32), 32)[1] < 0.8 else 0.0 for u in ext], ys)}
        for name in MODELS:
            R[name] = metrics([float(x) for x in model_fit(name, U, gold)(ext)], ys)
        res["external"]["results"][gold] = R
    # scale drift
    drift = []
    for u in U:
        drift.append({"unit": "%s/%d/%s" % (u["scenario"], u["seed"], u["family"]), "p0_probe": u["p0"],
                      "start_natural": u["gold_scores"]["start"], "p1_probe": u["p1"],
                      "end_natural_none": u["gold_scores"]["end_none"], "pref_probe": u["pref"],
                      "ref_natural": u["gold_scores"]["ref"],
                      "wilson_upper_p1": wilson(round(u["p1"] * u["n1"]), u["n1"])[1]})
    res["scale_drift"] = {
        "units": drift,
        "max_probe_p1": max(u["p1"] for u in U),
        "mean_start_gap_natural_minus_probe": mean(d["start_natural"] - d["p0_probe"] for d in drift),
        "mean_ref_gap_natural_minus_probe": mean(d["ref_natural"] - d["pref_probe"] for d in drift if d["pref_probe"] is not None),
        "p1_needed_for_wilson_upper_ge_0.8_at_n32": min(k / 32 for k in range(33) if wilson(k, 32)[1] >= 0.8),
    }
    return res


def _fmt(v, nd=2):
    return "-" if v is None else "%.*f" % (nd, v)


def report() -> Path:
    res = run()
    ensure_dir(OUT)
    write_json(OUT / "calibration.json", res)
    sd = res["scale_drift"]
    L = ["# Monitor v2 离线校准（CPU，只读）", "",
         "生成于 %s（Asia/Shanghai）。15 个离线单元（A 9 + C 6），特征只用 v2 探针（File 用修正判分）。"
         "金标准来自独立自然语言期末（无复习臂末端）。n=15，所有数字只作描述；概率阈值固定 0.5，未在验证折上调。" % res["generated"], "",
         "## 1. 为什么 τ=0.8 把所有单元判成不足（刻度漂移）", "",
         "- 15 个单元在决策时刻的 v2 探针分数最高只有 **%.3f**；n=32 时 Wilson 90%% 上界要 ≥0.8，探针分至少要 %.3f。"
         "所以 rule2 的“上界 < τ → DEFICIENT”对每个单元都成立。" % (sd["max_probe_p1"], sd["p1_needed_for_wilson_upper_ge_0.8_at_n32"]),
         "- 同一个 checkpoint 上，自然语言期末比 v2 探针平均高 %.3f（起点）/ %.3f（各工具刚学完时）。"
         "v2 探针含改写/自然表述子集，比期末难，分数被整体压低：τ=0.8 是按期末刻度定的，却用在探针刻度上。" % (
             sd["mean_start_gap_natural_minus_probe"], sd["mean_ref_gap_natural_minus_probe"]),
         "- 例：A/20261109/python 期末起点 1.000、末端 1.000（完全没忘），探针只有 0.625 → 仍被判 DEFICIENT。", "",
         "| 单元 | 探针 p0 | 期末起点 | 探针 p1(决策) | 期末末端(none) | 探针 ref | 期末 ref | Wilson 上界(p1) |",
         "|---|---|---|---|---|---|---|---|"]
    for d in sd["units"]:
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (d["unit"], _fmt(d["p0_probe"], 3), _fmt(d["start_natural"], 3),
                                                             _fmt(d["p1_probe"], 3), _fmt(d["end_natural_none"], 3),
                                                             _fmt(d["pref_probe"], 3), _fmt(d["ref_natural"], 3),
                                                             _fmt(d["wilson_upper_p1"], 3)))
    for gold in GOLDS:
        R = res["results"][gold]
        pos = R["baseline prevalence (constant)"]["in_sample"]["pos"]
        L += ["", "## 2. 预测 %s（阳性 %d/15）" % (gold, pos), "",
              "| 方法 | 验证 | recall | FPR | TP/FN/FP/TN | Brier | ECE(5 箱) | AUC |", "|---|---|---|---|---|---|---|---|"]
        for name, d in R.items():
            for split, m in d.items():
                if split.startswith("oof"):
                    continue
                L.append("| %s | %s | %s | %s | %d/%d/%d/%d | %.3f | %.3f | %s |" % (
                    name, split, _fmt(m["recall"]), _fmt(m["fpr"]), m["tp"], m["fn"], m["fp"], m["tn"],
                    m["brier"], m["ece5"], _fmt(m["auc"])))
    L += ["", "## 3. 外部复现单元（E4 + E2 的 none 臂，A 场景，Database/Python，模型用全部 15 单元拟合）", "",
          "注意：与离线单元同起点、同种子，只是重新训练的中点与末端，不是独立种子。", ""]
    for gold in GOLDS:
        ext = res["external"]["results"][gold]
        L += ["%s：" % gold, "", "| 方法 | recall | FPR | TP/FN/FP/TN | Brier | ECE | AUC |", "|---|---|---|---|---|---|---|"]
        for name, m in ext.items():
            L.append("| %s | %s | %s | %d/%d/%d/%d | %.3f | %.3f | %s |" % (name, _fmt(m["recall"]), _fmt(m["fpr"]), m["tp"], m["fn"],
                                                                     m["fp"], m["tn"], m["brier"], m["ece5"], _fmt(m["auc"])))
        L.append("")
    L += ["外部单元明细：", ""]
    for u in res["external"]["units"]:
        L.append("- %s seed%d %s: p0=%.3f p1=%.3f pref=%.3f end=%.3f ref=%.3f gold=%s" % (
            u["round"], u["seed"], u["family"], u["p0"], u["p1"], u["pref"], u["gold_scores"]["end_none"],
            u["gold_scores"]["ref"], u["gold"]))
    path = OUT / "report.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(report())