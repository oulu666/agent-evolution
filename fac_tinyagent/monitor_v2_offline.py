"""[ext 2026-11-11] Offline validation of monitor v1 vs v2 on existing checkpoints.

Read-only on runs_phase2 / runs_round2 / runs_round2_c; writes runs_ext_monitor/.

Online setting (the one adaptive replay faces): the monitor sees the stage
start and the midpoint and must predict whether a family needs help at the end
of the stage *without replay* (the ``none`` arm).  Gold comes from the
independent natural final set (File rows re-scored, see ext_rescore):
  G_drop : final(end_none) <= final(start) - 0.10   (stage-local forgetting)
  G_need : final(end_none) <  0.80                  (needs replay / deficit)
  G_cum  : final(end_none) <= final(ref) - 0.10, ref = checkpoint right after
           the family's own training stage           (cumulative forgetting)
Phases: --phase gpu (inference, skip-existing), --phase report (CPU only).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

from .ext_rescore import corrected_joint
from .monitor_v2 import DEFAULTS, FLAGGED, combine, decide, v1_flag
from .monitor_v2_data import OUT as MV2, subset_of
from .utils import ensure_dir, read_json, read_jsonl, write_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs_ext_monitor"
SEEDS = [20261108, 20261109, 20261110]
FIX = ROOT / "data_phase2" / "fixtures"
CAL = ROOT / "data_replay_study" / "fixtures" / "calendar.json"
SCEN = {
    "A": {"runs": ROOT / "runs_round2", "old": ["file", "database", "python"],
          "start": ("stage_03_python", 3),
          "refs": {"file": ("stage_01_file", 1), "database": ("stage_02_database", 2),
                   "python": ("stage_03_python", 3)}},
    "C": {"runs": ROOT / "runs_round2_c", "old": ["file", "database"],
          "start": ("stage_02_file", 2),
          "refs": {"database": ("stage_01_database", 1), "file": ("stage_02_file", 2)}},
}
THRESH = {"drop": 0.10, "need": 0.80}


def _ckpt(s: str, seed: int, name: str) -> Path:
    return ROOT / "runs_phase2" / ("%s_seed%d" % (s, seed)) / "checkpoints" / name


def states(s: str, seed: int) -> Dict[str, Dict[str, Any]]:
    sc = SCEN[s]
    start_name, start_idx = sc["start"]
    out = {"start": {"adapter": _ckpt(s, seed, start_name), "index": start_idx},
           "mid": {"adapter": _ckpt(s, seed, start_name), "index": start_idx,
                   "prefix": sc["runs"] / "prefixes" / ("%s_seed%d" % (s, seed))},
           "end_none": {"adapter": sc["runs"] / "branches" / ("%s_seed%d_none" % (s, seed)) / "checkpoint",
                        "index": start_idx + 1}}
    for name, idx in {v for v in sc["refs"].values()}:
        if name != start_name:
            out["ref_" + name] = {"adapter": _ckpt(s, seed, name), "index": idx}
    return out


def _eval_dir(s, seed, state, suite, family) -> Path:
    return OUT / "eval" / ("%s_seed%d_%s" % (s, seed, state)) / suite / family


def _load_midpoint(model, prefix: Path) -> Dict[str, Any]:
    import torch
    state = torch.load(prefix / "training_state.pt", map_location="cpu", weights_only=False)
    params = dict(model.named_parameters())
    missing = [n for n in state["parameters"] if n not in params]
    if missing:
        raise ValueError("prefix parameters not found in eval model: %s" % missing[:3])
    with torch.no_grad():
        for name, value in state["parameters"].items():
            params[name].copy_(value.to(params[name].device, dtype=params[name].dtype))
    digest = hashlib.sha256()
    for name in sorted(state["parameters"]):
        digest.update(name.encode("utf-8"))
        digest.update(params[name].detach().contiguous().view(torch.uint8).cpu().numpy().tobytes())
    return {"n_params": len(state["parameters"]),
            "hash_matches_prefix": digest.hexdigest() == state["parameter_hash"]}


def run_gpu(scenarios: List[str], seeds: List[int]) -> None:
    from .replay_study import config_for
    from .sft.evaluate import evaluate_family, free_model, load_eval_model
    for s in scenarios:
        sc = SCEN[s]
        for seed in seeds:
            for state, info in states(s, seed).items():
                jobs = []
                for family in sc["old"]:
                    jobs.append(("monitor_v2", family, MV2 / (family + ".jsonl")))
                    if state.startswith("ref_"):
                        jobs.append(("natural_final", family, ROOT / "data_round2" / "final" / (family + ".jsonl")))
                todo = [j for j in jobs if not (_eval_dir(s, seed, state, j[0], j[1]) / "stage_report.json").exists()]
                if not todo:
                    print("skip", s, seed, state, flush=True)
                    continue
                config = config_for(s, seed, batch_size=32)
                model, tok = load_eval_model(config, str(info["adapter"]))
                meta = {"adapter": str(info["adapter"])}
                try:
                    if "prefix" in info:
                        meta.update(_load_midpoint(model, info["prefix"]))
                        meta["prefix"] = str(info["prefix"])
                    write_json(OUT / "eval" / ("%s_seed%d_%s" % (s, seed, state)) / "state_meta.json", meta)
                    stage = {"name": "%s_seed%d_%s" % (s, seed, state), "index": info["index"],
                             "adapter": str(info["adapter"])}
                    for suite, family, path in todo:
                        evaluate_family(model, tok, read_jsonl(path), config, stage,
                                        _eval_dir(s, seed, state, suite, family),
                                        str(FIX / "toolbench.db"), str(CAL))
                finally:
                    free_model(model)


# ----------------------------------------------------------------- report ---

def _kn(path: Path, corrected: bool = True, subset: Optional[str] = None) -> Optional[Tuple[int, int]]:
    if not path.exists():
        return None
    rows = read_jsonl(path)
    if subset is not None:
        rows = [r for r in rows if subset_of(r["episode_id"]) == subset]
    if not rows:
        return None
    k = sum(bool(corrected_joint(r)) if corrected else bool(r.get("joint_success")) for r in rows)
    return k, len(rows)


def _cost(path: Path) -> Dict[str, float]:
    if not path.exists():
        return {}
    rows = read_jsonl(path)
    rep = read_json(path.parent / "stage_report.json") if (path.parent / "stage_report.json").exists() else {}
    return {"episodes": len(rows), "input_tokens": sum(r.get("input_tokens", 0) for r in rows),
            "output_tokens": sum(r.get("output_tokens", 0) for r in rows),
            "seconds": rep.get("duration_seconds", 0.0)}


def gold_scores(s: str, seed: int, family: str, corrected: bool = True) -> Dict[str, Optional[float]]:
    runs = SCEN[s]["runs"]
    res = {}
    for key, mode in (("start", "start"), ("end_none", "none")):
        kn = _kn(runs / "evaluation" / ("%s_seed%d_%s" % (s, seed, mode)) / "natural_final" / family / "results.jsonl", corrected)
        res[key] = kn[0] / kn[1] if kn else None
    ref_name, _ = SCEN[s]["refs"][family]
    if ref_name == SCEN[s]["start"][0]:
        res["ref"] = res["start"]
    else:
        kn = _kn(_eval_dir(s, seed, "ref_" + ref_name, "natural_final", family) / "results.jsonl", corrected)
        res["ref"] = kn[0] / kn[1] if kn else None
    return res


def gold_labels(g: Dict[str, Optional[float]]) -> Dict[str, Optional[bool]]:
    end, start, ref = g["end_none"], g["start"], g["ref"]
    return {"G_drop": None if end is None or start is None else end <= start - THRESH["drop"] + 1e-9,
            "G_need": None if end is None else end < THRESH["need"],
            "G_cum": None if end is None or ref is None else end <= ref - THRESH["drop"] + 1e-9}


def v1_probe(s, seed, family, which, corrected):
    base = SCEN[s]["runs"] / "branches" / ("%s_seed%d_none" % (s, seed)) / "checkpoint" / "probes"
    name = {"start": "start", "mid": "midpoint"}[which]
    return _kn(base / name / family / "results.jsonl", corrected)


def v2_probe(s, seed, family, state, subset=None):
    return _kn(_eval_dir(s, seed, state, "monitor_v2", family) / "results.jsonl", True, subset)


def detectors(s, seed, family) -> Dict[str, Dict[str, Any]]:
    out = {}
    for tag, corrected in (("V1_drop>0_rawlabels", False), ("V1_drop>0_fixedlabels", True)):
        a, b = v1_probe(s, seed, family, "start", corrected), v1_probe(s, seed, family, "mid", corrected)
        if a and b:
            out[tag] = {"status": "DEGRADED" if v1_flag(a[0] / a[1], b[0] / b[1]) else "OK",
                        "p0": a[0] / a[1], "p1": b[0] / b[1]}
    a, b = v1_probe(s, seed, family, "start", True), v1_probe(s, seed, family, "mid", True)
    if a and b:
        out["V1probes+rule2"] = decide(a[0], a[1], b[0], b[1])
    a, b = v2_probe(s, seed, family, "start"), v2_probe(s, seed, family, "mid")
    if a and b:
        out["V2probes_drop>0"] = {"status": "DEGRADED" if v1_flag(a[0] / a[1], b[0] / b[1]) else "OK",
                                  "p0": a[0] / a[1], "p1": b[0] / b[1]}
        out["V2probes+rule2_pooled"] = decide(a[0], a[1], b[0], b[1])
        rows = read_jsonl(_eval_dir(s, seed, "start", "monitor_v2", family) / "results.jsonl")
        subs = sorted({subset_of(r["episode_id"]) for r in rows})
        dec = {}
        for sub in subs:
            x, y = v2_probe(s, seed, family, "start", sub), v2_probe(s, seed, family, "mid", sub)
            if x and y:
                dec[sub] = decide(x[0], x[1], y[0], y[1])
        out["V2probes+rule2_subsetmax"] = dict(combine(dec.values()), subsets={k: {kk: v[kk] for kk in ("status", "p0", "p1") if kk in v} for k, v in dec.items()})
    for name in [n for n in out if "rule2" in n]:
        d = out[name]
        out[name + "[DEGRADED-only]"] = dict(d, status=("OK" if d["status"] == "DEFICIENT" else d["status"]))
    return out


def round2_rescore() -> Dict[str, Any]:
    """Round-2 natural-final tables with raw vs label-fixed File scoring."""
    res = {}
    for s, sc in SCEN.items():
        for mode in ("start", "none", "uniform", "targeted", "adaptive"):
            raw, fix, ffix = [], [], []
            for seed in SEEDS:
                vr, vf = [], []
                for fam in sc["old"]:
                    p = sc["runs"] / "evaluation" / ("%s_seed%d_%s" % (s, seed, mode)) / "natural_final" / fam / "results.jsonl"
                    a, b = _kn(p, False), _kn(p, True)
                    if not a:
                        continue
                    vr.append(a[0] / a[1]); vf.append(b[0] / b[1])
                    if fam == "file":
                        ffix.append(b[0] / b[1])
                if vr:
                    raw.append(mean(vr)); fix.append(mean(vf))
            if raw:
                res["%s|%s" % (s, mode)] = {"old_macro_raw": mean(raw), "old_macro_fixed": mean(fix),
                                            "file_fixed": mean(ffix) if ffix else None,
                                            "file_fixed_by_seed": ffix}
    return res


def confusion(units: List[Dict[str, Any]], det: str, gold: str, ie_as_flag: bool) -> Dict[str, Any]:
    tp = fp = fn = tn = ie = 0
    for u in units:
        d = u["detectors"].get(det)
        g = u["gold"].get(gold)
        if d is None or g is None:
            continue
        status = d["status"]
        if status == "INSUFFICIENT_EVIDENCE":
            ie += 1
        flag = status in FLAGGED or (ie_as_flag and status == "INSUFFICIENT_EVIDENCE")
        if g and flag:
            tp += 1
        elif g:
            fn += 1
        elif flag:
            fp += 1
        else:
            tn += 1
    pos, neg = tp + fn, fp + tn
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "ie": ie,
            "recall": tp / pos if pos else None, "fpr": fp / neg if neg else None,
            "n": pos + neg}


def costs() -> Dict[str, Any]:
    v1 = {"episodes": 0, "input_tokens": 0, "output_tokens": 0, "seconds": 0.0, "checks": 0}
    v2 = dict(v1)
    for s in SCEN:
        for seed in SEEDS:
            p = SCEN[s]["runs"] / "branches" / ("%s_seed%d_none" % (s, seed)) / "checkpoint" / "probes"
            for which in ("start", "midpoint"):
                ok = False
                for fam in SCEN[s]["old"]:
                    c = _cost(p / which / fam / "results.jsonl")
                    for k in ("episodes", "input_tokens", "output_tokens", "seconds"):
                        v1[k] += c.get(k, 0)
                    ok = ok or bool(c)
                v1["checks"] += ok
            for st in ("start", "mid"):
                ok = False
                for fam in SCEN[s]["old"]:
                    c = _cost(_eval_dir(s, seed, st, "monitor_v2", fam) / "results.jsonl")
                    for k in ("episodes", "input_tokens", "output_tokens", "seconds"):
                        v2[k] += c.get(k, 0)
                    ok = ok or bool(c)
                v2["checks"] += ok
    for v in (v1, v2):
        n = max(1, v["checks"])
        v["per_check"] = {k: v[k] / n for k in ("episodes", "input_tokens", "output_tokens", "seconds")}
    return {"v1": v1, "v2": v2}


def report() -> Path:
    units = []
    for s, sc in SCEN.items():
        for seed in SEEDS:
            for family in sc["old"]:
                g_fix = gold_scores(s, seed, family, True)
                g_raw = gold_scores(s, seed, family, False)
                units.append({"scenario": s, "seed": seed, "family": family,
                              "gold_scores_fixed": g_fix, "gold_scores_raw": g_raw,
                              "gold": gold_labels(g_fix), "gold_raw": gold_labels(g_raw),
                              "detectors": detectors(s, seed, family)})
    dets = ["V1_drop>0_rawlabels", "V1_drop>0_fixedlabels", "V1probes+rule2",
            "V1probes+rule2[DEGRADED-only]", "V2probes_drop>0", "V2probes+rule2_pooled",
            "V2probes+rule2_pooled[DEGRADED-only]", "V2probes+rule2_subsetmax",
            "V2probes+rule2_subsetmax[DEGRADED-only]"]
    table = {}
    for det in dets:
        for gold in ("G_drop", "G_need", "G_cum"):
            table["%s|%s|IE=neg" % (det, gold)] = confusion(units, det, gold, False)
            table["%s|%s|IE=flag" % (det, gold)] = confusion(units, det, gold, True)
    raw_v1 = {g: confusion([dict(u, gold=u["gold_raw"]) for u in units], "V1_drop>0_rawlabels", g, False)
              for g in ("G_drop", "G_need", "G_cum")}
    result = {"params": DEFAULTS, "thresholds": THRESH, "units": units, "table": table,
              "v1_raw_everything": raw_v1, "costs": costs(), "round2_rescore": round2_rescore()}
    ensure_dir(OUT)
    write_json(OUT / "monitor_eval.json", result)
    lines = ["# Monitor v1 vs v2 offline validation", "",
             "Units: scenario x seed x old family = %d (A: 9, C: 6). Decision at stage midpoint; "
             "gold = independent natural final at end of the no-replay arm (File re-scored)." % len(units), "",
             "| detector | gold | IE policy | recall | FPR | TP/FN/FP/TN | IE |", "|---|---|---|---|---|---|---|"]
    fmt = lambda v: "-" if v is None else "%.2f" % v
    for key, c in table.items():
        det, gold, ie = key.split("|")
        lines.append("| %s | %s | %s | %s | %s | %d/%d/%d/%d | %d |" % (
            det, gold, ie, fmt(c["recall"]), fmt(c["fpr"]), c["tp"], c["fn"], c["fp"], c["tn"], c["ie"]))
    lines += ["", "## V1 with raw labels for both monitor and gold (what Round 2 saw)", "",
              "```", json.dumps(raw_v1, indent=1), "```",
              "", "## Round-2 natural final re-scored (File last-match label fix)", "",
              "```", json.dumps(result["round2_rescore"], indent=1), "```"]
    lines += ["", "## Costs (per monitoring check, all old families)", "",
              "```", json.dumps(result["costs"], indent=1), "```", "", "## Units", ""]
    for u in units:
        lines.append("- %s seed%d %s gold_fixed=%s gold_raw=%s labels=%s | %s" % (
            u["scenario"], u["seed"], u["family"],
            {k: (None if v is None else round(v, 3)) for k, v in u["gold_scores_fixed"].items()},
            {k: (None if v is None else round(v, 3)) for k, v in u["gold_scores_raw"].items()},
            u["gold"], {k: v["status"] for k, v in u["detectors"].items()}))
    path = OUT / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["gpu", "report"], required=True)
    parser.add_argument("--scenarios", nargs="+", default=["A", "C"])
    parser.add_argument("--seeds", nargs="+", type=int, default=SEEDS)
    args = parser.parse_args()
    if args.phase == "gpu":
        run_gpu(args.scenarios, args.seeds)
    print("report:", report(), flush=True)


if __name__ == "__main__":
    main()
