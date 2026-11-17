"""[ext 2026-11-11] Read-only re-evaluation with Calendar natural final v3.

Targets (adapters are only READ):
  E4  runs_ext_e4/branches/A_seed<s>_<tf00|tf25|tf50|none>/checkpoint      (12)
  E2  runs_ext_tf/branches/A_seed<s>_<tf00|tf25|tf50|tf75|none>/checkpoint (15)
  start  runs_phase2/A_seed<s>/checkpoints/stage_03_python  (pre-Calendar reference, 3)
  p2cal  runs_phase2/A_seed<s>/checkpoints/stage_04_calendar (original sequential Calendar, no replay, 3)
Outputs: runs_ext_calv3/evaluation/<round>_A_seed<s>_<arm>/calendar_v3/ (pilot: runs_ext_calv3_pilot/).
"""
from __future__ import annotations

import argparse
import json
import random
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Optional

from .replay_study import config_for
from .utils import ensure_dir, read_json, read_jsonl, sha256_file, write_json

ROOT = Path(__file__).resolve().parents[1]
CV3 = ROOT / "data_ext_cal_v3"
OUT = ROOT / "runs_ext_calv3"
PILOT = ROOT / "runs_ext_calv3_pilot"
DB_PATH = ROOT / "data_phase2" / "fixtures" / "toolbench.db"
FIXTURE = CV3 / "fixtures" / "calendar_v3.json"
SEEDS = [20261108, 20261109, 20261110]
ARMS = {"E4": ["tf00", "tf25", "tf50", "none"], "E2": ["tf00", "tf25", "tf50", "tf75", "none"],
        "REF": ["start", "p2cal"]}
TYPES = ["free_latest", "locations", "attendee_count", "search_count", "last_end"]


def adapter(round_: str, seed: int, arm: str) -> Path:
    if round_ == "E4":
        return ROOT / "runs_ext_e4" / "branches" / ("A_seed%d_%s" % (seed, arm)) / "checkpoint"
    if round_ == "E2":
        return ROOT / "runs_ext_tf" / "branches" / ("A_seed%d_%s" % (seed, arm)) / "checkpoint"
    stage = "stage_03_python" if arm == "start" else "stage_04_calendar"
    return ROOT / "runs_phase2" / ("A_seed%d" % seed) / "checkpoints" / stage


def targets() -> List[Dict[str, Any]]:
    out = []
    for seed in SEEDS:
        for rnd in ("REF", "E4", "E2"):
            for arm in ARMS[rnd]:
                out.append({"round": rnd, "seed": seed, "arm": arm})
    return out


def frozen_rows() -> List[Dict[str, Any]]:
    fz = read_json(CV3 / "final_v3" / "FROZEN.json")
    if sha256_file(CV3 / fz["files"]["calendar_v3"]["path"]) != fz["files"]["calendar_v3"]["sha256"]:
        raise SystemExit("calendar_v3 rows hash changed; refusing")
    if sha256_file(FIXTURE) != fz["fixture"]["sha256"]:
        raise SystemExit("calendar_v3 fixture hash changed; refusing")
    return read_jsonl(CV3 / "final_v3" / "calendar_v3.jsonl")


def run_dir(base: Path, t: Dict[str, Any]) -> Path:
    return base / "evaluation" / ("%s_A_seed%d_%s" % (t["round"], t["seed"], t["arm"])) / "calendar_v3"


def evaluate(t: Dict[str, Any], pilot: bool, limit: Optional[int] = None) -> None:
    from .sft.evaluate import evaluate_family, free_model, load_eval_model
    rows = read_jsonl(CV3 / "candidate" / "calendar_v3.jsonl") if pilot else frozen_rows()
    if limit:
        by = defaultdict(list)
        for r in rows:
            by[r["target_type"]].append(r)
        rows = [r for k in by for r in by[k][:limit]]
    out = run_dir(PILOT if pilot else OUT, t)
    if (out / "stage_report.json").exists():
        print("skip", out, flush=True)
        return
    ad = adapter(t["round"], t["seed"], t["arm"])
    if t["round"] in ("E4", "E2") and not (ad / "train_summary.json").exists():
        raise FileNotFoundError("no finished checkpoint %s" % ad)
    if not (ad / "adapter_config.json").exists():
        raise FileNotFoundError("no adapter %s" % ad)
    config = config_for("A", t["seed"], batch_size=32)
    model, tok = load_eval_model(config, str(ad))
    try:
        evaluate_family(model, tok, rows, config,
                        {"name": "CALV3_%s_A_seed%d_%s" % (t["round"], t["seed"], t["arm"]), "index": 4,
                         "adapter": str(ad)}, out, str(DB_PATH), str(FIXTURE))
    finally:
        free_model(model)


# ------------------------------------------------------------------ scoring
def _kind(eid: str) -> str:
    return eid.split("-")[2]


def items(base: Path, t: Dict[str, Any]) -> Optional[Dict[str, Dict[str, int]]]:
    p = run_dir(base, t) / "results.jsonl"
    if not (run_dir(base, t) / "stage_report.json").exists():
        return None
    d = defaultdict(dict)
    for r in read_jsonl(p):
        d[_kind(r["episode_id"])][r["episode_id"]] = int(bool(r.get("joint_success")))
    return d


def diagnostics(base: Path, t: Dict[str, Any], rows_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    p = run_dir(base, t) / "results.jsonl"
    res = defaultdict(lambda: defaultdict(int))
    for r in read_jsonl(p):
        k = _kind(r["episode_id"])
        c = res[k]
        c["n"] += 1
        c["tool_ok"] += bool(r["tool_correct"])
        c["args_ok"] += bool(r["arguments_correct"])
        c["exec_ok"] += bool(r["execution_success"])
        c["answer_ok"] += bool(r["final_correct"])
        if k == "free_latest" and r["execution_success"] and not r["final_correct"]:
            obs = json.loads(r["observation"])["result"]
            if obs and r.get("predicted_answer") == obs[0]:
                c["answered_first_slot"] += 1
        if k == "locations" and r["execution_success"] and not r["final_correct"]:
            obs = json.loads(r["observation"])["result"]
            pa = r.get("predicted_answer")
            if isinstance(pa, list) and sorted(pa) == sorted(e["location"] for e in obs):
                c["answered_with_duplicates"] += 1
        if k == "last_end" and r["execution_success"] and not r["final_correct"]:
            obs = json.loads(r["observation"])["result"]
            if obs and r.get("predicted_answer") == obs[-1]["start"]:
                c["answered_last_start"] += 1
        if k in ("attendee_count", "search_count") and r["execution_success"] and not r["final_correct"]:
            if isinstance(r.get("predicted_answer"), list):
                c["answered_list_not_count"] += 1
            elif isinstance(r.get("predicted_answer"), (int, float)):
                c["count_off_by"] += abs(int(r["predicted_answer"]) - int(r["expected_final_answer"]))
    return {k: dict(v) for k, v in res.items()}


def score(it: Dict[str, Dict[str, int]]) -> Dict[str, float]:
    s = {k: mean(it[k].values()) for k in TYPES if it.get(k)}
    s["overall"] = mean(s[k] for k in TYPES if k in s)
    return s


def boot(A: Dict[int, Dict[str, Dict[str, int]]], B: Dict[int, Dict[str, Dict[str, int]]], metric: str,
         n_boot: int = 2000, seed: int = 20261111) -> Optional[Dict[str, Any]]:
    """Paired by seed and item; overall = macro over sub-skills (stratified resampling)."""
    kinds = TYPES if metric == "overall" else [metric]
    seeds = sorted(set(A) & set(B))
    data = {}
    for s in seeds:
        per = []
        for k in kinds:
            ids = sorted(set(A[s].get(k, {})) & set(B[s].get(k, {})))
            if not ids:
                break
            per.append([A[s][k][i] - B[s][k][i] for i in ids])
        else:
            data[s] = per
    seeds = sorted(data)
    if not seeds:
        return None
    per_seed = [mean(mean(d) for d in data[s]) for s in seeds]
    rng = random.Random(seed)
    hier, item = [], []
    for _ in range(n_boot):
        for tgt, pick in ((hier, [rng.choice(seeds) for _ in seeds]), (item, seeds)):
            vals = []
            for s in pick:
                vals.append(mean(sum(d[rng.randrange(len(d))] for _ in d) / len(d) for d in data[s]))
            tgt.append(mean(vals))

    def ci(v):
        v = sorted(v)
        return [v[int(0.025 * len(v))], v[min(len(v) - 1, int(0.975 * len(v)))]]
    return {"n_seeds": len(seeds), "mean_diff": mean(per_seed), "sd_diff": stdev(per_seed) if len(per_seed) > 1 else 0.0,
            "per_seed": dict(zip([str(s) for s in seeds], per_seed)), "n_positive_seeds": sum(x > 0 for x in per_seed),
            "n_negative_seeds": sum(x < 0 for x in per_seed),
            "ci95_hier": ci(hier), "ci95_item": ci(item)}


def collect(base: Path) -> Dict[str, Any]:
    rows_by_id = {}
    src = CV3 / ("final_v3/calendar_v3.jsonl" if (CV3 / "final_v3" / "FROZEN.json").exists() and base == OUT
                 else "candidate/calendar_v3.jsonl")
    for r in read_jsonl(src):
        rows_by_id[r["episode_id"]] = r
    runs, its = [], defaultdict(dict)
    for t in targets():
        it = items(base, t)
        if it is None:
            continue
        its[(t["round"], t["arm"])][t["seed"]] = it
        rec = dict(t)
        rec["scores"] = score(it)
        rec["diagnostics"] = diagnostics(base, t, rows_by_id)
        rep = read_json(run_dir(base, t) / "stage_report.json")
        rec["duration_seconds"] = rep.get("duration_seconds")
        runs.append(rec)
    agg = []
    for rnd in ("REF", "E4", "E2"):
        for arm in ARMS[rnd]:
            part = [r for r in runs if r["round"] == rnd and r["arm"] == arm]
            if not part:
                continue
            e = {"round": rnd, "arm": arm, "n_seeds": len(part)}
            for k in TYPES + ["overall"]:
                v = [r["scores"][k] for r in part if k in r["scores"]]
                e[k] = {"mean": mean(v), "std": stdev(v) if len(v) > 1 else 0.0, "per_seed": v}
            agg.append(e)
    comps = {}
    pairs = [("E4", "tf50", "E4", "tf25"), ("E4", "tf50", "E4", "none"), ("E4", "tf25", "E4", "none"),
             ("E4", "tf00", "E4", "none"), ("E4", "tf50", "E4", "tf00"),
             ("E2", "tf75", "E2", "tf50"), ("E2", "tf50", "E2", "tf25"), ("E2", "tf50", "E2", "none"),
             ("E2", "tf25", "E2", "none"), ("E2", "tf75", "E2", "none"),
             ("E4", "tf50", "E2", "tf50"), ("E4", "tf25", "E2", "tf25"), ("E4", "none", "E2", "none"),
             ("E4", "none", "REF", "start"), ("E4", "none", "REF", "p2cal")]
    for ra, a, rb, b in pairs:
        for m in ["overall"] + TYPES:
            res = boot(its.get((ra, a), {}), its.get((rb, b), {}), m)
            if res:
                comps["%s:%s - %s:%s | %s" % (ra, a, rb, b, m)] = res
    out = {"runs": runs, "aggregates": agg, "comparisons": comps,
           "generated": time.strftime("%Y-%m-%d %H:%M:%S")}
    if (CV3 / "final_v3" / "FROZEN.json").exists():
        out["frozen"] = read_json(CV3 / "final_v3" / "FROZEN.json")["combined_sha256"]
    return out


def _f(d):
    return "%.3f±%.3f" % (d["mean"], d["std"]) if d["std"] else "%.3f" % d["mean"]


def report(pilot: bool = False) -> Path:
    base = PILOT if pilot else OUT
    res = collect(base)
    ensure_dir(base)
    write_json(base / "results.json", res)
    e4 = {}
    p = ROOT / "runs_ext_e4" / "results.json"
    if p.exists():
        for a in read_json(p)["aggregates"]:
            e4[(a["round"], a["arm"])] = a
    L = ["# Calendar v3（未训练子技能）只读补评自动汇总", "",
         "生成于 %s（Asia/Shanghai）。%s" % (res["generated"], ("冻结合并哈希 `%s`。" % res.get("frozen", "")[:16]) if not pilot else "**pilot（候选题，未冻结）**"),
         "判分 = joint success（工具、参数完全一致、在 v3 新日历上执行一致、答案精确相等）。overall = 5 个子技能等权宏平均。"
         "均值±样本标准差（n=种子数）。REF:start = stage_03（学 Calendar 前）；REF:p2cal = phase2 原始顺序学习的 stage_04_calendar（无复习）。", "",
         "| 轮 | 臂 | n | overall | 最晚空档 | 地点去重 | 参会人数 | 标题计数 | 末场结束 | Calendar nat v2 | Calendar hist |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in res["aggregates"]:
        ref = e4.get((a["round"], a["arm"]), {})
        v2 = ref.get("nat_calendar", {}).get("mean") if ref else None
        hi = ref.get("hist_calendar", {}).get("mean") if ref else None
        L.append("| %s | %s | %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            a["round"], a["arm"], a["n_seeds"], _f(a["overall"]), *[_f(a[k]) for k in TYPES],
            "-" if v2 is None else "%.3f" % v2, "-" if hi is None else "%.3f" % hi))
    L += ["", "## 配对比较（同种子同题配对；overall 为子技能分层重抽）", "",
          "95% CI：hier = 种子+题目两级 bootstrap；item = 种子固定只抽题目（2000 次）。n=3 种子，只描述方向，"
          "三个种子同号记为“方向一致”，不作显著性结论。", "",
          "| 比较 | 指标 | 均值差 | 种子差 sd | +/− 种子数 | 方向 | 95% CI (hier) | 95% CI (item) |", "|---|---|---|---|---|---|---|---|"]
    for k, v in res["comparisons"].items():
        name, m = k.split(" | ")
        n = v["n_seeds"]
        direction = "方向一致(+)" if v["n_positive_seeds"] == n else ("方向一致(−)" if v["n_negative_seeds"] == n else "不一致")
        L.append("| %s | %s | %+.3f | %.3f | %d/%d | %s | [%+.3f, %+.3f] | [%+.3f, %+.3f] |" % (
            name, m, v["mean_diff"], v["sd_diff"], v["n_positive_seeds"], v["n_negative_seeds"], direction,
            v["ci95_hier"][0], v["ci95_hier"][1], v["ci95_item"][0], v["ci95_item"][1]))
    L += ["", "## 逐 run 明细与错误分解", ""]
    for r in res["runs"]:
        L.append("- %s seed%d %s: %s" % (r["round"], r["seed"], r["arm"],
                                         json.dumps({k: round(v, 3) for k, v in r["scores"].items()})))
        L.append("  - diag: %s" % json.dumps(r["diagnostics"]))
    path = base / "report.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["eval", "pilot", "report", "list"], required=True)
    ap.add_argument("--round", choices=["E4", "E2", "REF"])
    ap.add_argument("--seed", type=int)
    ap.add_argument("--arm")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--pilot-report", action="store_true")
    a = ap.parse_args()
    if a.phase == "list":
        for t in targets():
            print(t["round"], t["seed"], t["arm"])
        return
    if a.phase in ("eval", "pilot"):
        evaluate({"round": a.round, "seed": a.seed, "arm": a.arm}, a.phase == "pilot", a.limit)
        print("EVAL_OK", a.round, a.seed, a.arm, flush=True)
    print("report:", report(a.phase == "pilot" or a.pilot_report), flush=True)


if __name__ == "__main__":
    main()