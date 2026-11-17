#!/usr/bin/env python3
"""实验 A（E3-B2）三种子汇总（只读，CPU）。

输入（只读）：runs_ext_p1_b1/summary.json、各 label 的 B1 results.jsonl、各 checkpoint 的 replay_plan.json。
输出（新文件）：runs_ext_p1_b1/analysis/e3b2_three_seed.json、e3b2_three_seed_ZH.md
用法（项目根目录）：.venv/bin/python scripts/p2_e3b2_three_seed.py
"""
import json, statistics, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
sys.path.insert(0, str(ROOT))
from fac_tinyagent import p1_run as P  # noqa: E402
from fac_tinyagent.coverage_patterns import classify_item  # noqa: E402

SEEDS = [20261108, 20261109, 20261110]
ARMS = ["e3b2_A_target_other", "e3b2_A_target_dbbg", "ctrl_cal10", "dose_db0", "dose_db1", "tf25", "none"]
OUT = ROOT / "runs_ext_p1_b1" / "analysis"
NEAR = ("db.top_n", "db.filter_eq_count", "db.filter_eq_top")


def lab(s, a):
    return "A_seed%d_%s" % (s, a)


def load_res(s, a, su):
    p = P.results_path(s, a, su)
    if not p.exists():
        return None
    res = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    rows, _, _, _ = P.suite_rows(su)
    return res if len(res) == len(rows) else None


_RAW = None


def raw_pool():
    global _RAW
    if _RAW is None:
        _RAW = {}
        for f in ("file", "database", "python"):
            for l in open(ROOT / "data_ext_e4" / "pool" / (f + ".jsonl"), encoding="utf-8"):
                if l.strip():
                    r = json.loads(l); _RAW[r["episode_id"]] = r
        for l in open(ROOT / "data_phase2" / "calendar" / "train.jsonl", encoding="utf-8"):
            if l.strip():
                r = json.loads(l); _RAW[r["episode_id"]] = r
    return _RAW


def plan_info(s, a):
    pp = P.ckpt_path(s, a) / "replay_plan.json"
    if not pp.exists():
        return None
    plan = json.load(open(pp, encoding="utf-8"))
    raw = raw_pool()
    db_tok, tgt, near, fam = 0, [], {k: 0 for k in NEAR}, {}
    for it in plan.get("items", []):
        row = raw.get(it["episode_id"])
        pat = classify_item(row).pattern if row else "?"
        fam[it["family"]] = fam.get(it["family"], 0) + 1
        if it["family"] == "database":
            db_tok += int(it.get("input_tokens", 0))
        if pat == "db.filter_cmp_top":
            tgt.append(it["episode_id"])
        if pat in near:
            near[pat] += 1
    return {"plan": str(pp.relative_to(ROOT)), "slots": len(plan.get("items", [])), "db_input_tokens": db_tok,
            "target_ids": tgt, "near_slots": near, "family_slots": fam}


def main():
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S +0800")
    S = json.load(open(ROOT / "runs_ext_p1_b1" / "summary.json", encoding="utf-8"))
    out = {"generated": now, "cells": {}}
    for s in SEEDS:
        for a in ARMS:
            c = {}
            res = load_res(s, a, "natv2_database")
            if res:
                n = len(res)
                c["main"] = sum(bool(r["joint_success"]) for r in res) / n
                c["tool"] = sum(bool(r["tool_correct"]) for r in res) / n
                c["arguments"] = sum(bool(r["arguments_correct"]) for r in res) / n
                c["final"] = sum(bool(r["final_correct"]) for r in res) / n
                c["correct_ids"] = sorted(r["episode_id"].rsplit("-", 1)[1] for r in res if r["joint_success"])
            sc = S["scores"].get(lab(s, a), {})
            for su in ("db_nontarget", "natv2_python", "calendar_v3", "v3fix"):
                if su in sc:
                    c[su] = sc[su].get("score")
                    if su == "db_nontarget":
                        c["db_nontarget_patterns"] = sc[su].get("patterns")
            c["plan"] = plan_info(s, a) if a != "none" else None
            out["cells"][lab(s, a)] = c
    # 三种子主指标与差
    agg = {}
    for a in ARMS:
        v = [out["cells"][lab(s, a)].get("main") for s in SEEDS]
        if None not in v:
            agg[a] = {"per_seed": v, "mean": statistics.mean(v), "sd": statistics.stdev(v)}
    diffs = {}
    for x, y in [("e3b2_A_target_other", "ctrl_cal10"), ("e3b2_A_target_other", "dose_db0"),
                 ("e3b2_A_target_dbbg", "ctrl_cal10"), ("e3b2_A_target_dbbg", "dose_db0"),
                 ("e3b2_A_target_dbbg", "e3b2_A_target_other"), ("e3b2_A_target_other", "dose_db1"),
                 ("e3b2_A_target_dbbg", "dose_db1"), ("tf25", "e3b2_A_target_other"), ("tf25", "e3b2_A_target_dbbg")]:
        d = [out["cells"][lab(s, x)]["main"] - out["cells"][lab(s, y)]["main"] for s in SEEDS]
        diffs["%s − %s" % (x, y)] = {"per_seed": d, "mean": statistics.mean(d),
                                     "n_pos": sum(v > 1e-9 for v in d), "n_zero": sum(abs(v) <= 1e-9 for v in d),
                                     "n_neg": sum(v < -1e-9 for v in d)}
    overlap = {}
    for s in SEEDS:
        o = set(out["cells"][lab(s, "e3b2_A_target_other")]["correct_ids"])
        b = set(out["cells"][lab(s, "e3b2_A_target_dbbg")]["correct_ids"])
        d1 = set(out["cells"][lab(s, "dose_db1")]["correct_ids"])
        t = set(out["cells"][lab(s, "tf25")]["correct_ids"])
        overlap[str(s)] = {"other": sorted(o), "dbbg": sorted(b), "both": sorted(o & b), "dose_db1": sorted(d1),
                           "tf25_n": len(t), "other_in_tf25": len(o & t), "dbbg_in_tf25": len(b & t)}
    out["aggregate"], out["diffs"], out["overlap"] = agg, diffs, overlap
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT / "e3b2_three_seed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    f3 = lambda x: "—" if x is None else "%.3f" % x
    md = ["# 实验 A（E3-B2）三种子结果（Protocol-B1）", "",
          "生成：%s（Asia/Shanghai）。脚本 `scripts/p2_e3b2_three_seed.py`，只读 `summary.json`、B1 逐题结果和 `replay_plan.json`。" % now, "",
          "## 1. 主指标：nat v2 `db.filter_cmp_top` Joint Success（30 题）", "",
          "| 臂 | 08 | 09 | 10 | 均值 | SD |", "|---|---|---|---|---|---|"]
    for a, v in agg.items():
        md.append("| %s | %s | %.3f | %.3f |" % (a, " | ".join(f3(x) for x in v["per_seed"]), v["mean"], v["sd"]))
    md += ["", "## 2. 逐种子差（正/零/负 = 三种子里差 >0 / =0 / <0 的个数）", "", "| 对比 | 08 | 09 | 10 | 均值 | 正/零/负 |", "|---|---|---|---|---|---|"]
    for k, v in diffs.items():
        md.append("| %s | %s | %+.3f | %d/%d/%d |" % (k, " | ".join("%+.3f" % x for x in v["per_seed"]), v["mean"], v["n_pos"], v["n_zero"], v["n_neg"]))
    md += ["", "## 3. 逐环节、复习池与副指标", "",
           "| 种子 | 臂 | 主指标 | tool / args / final | 复习 slots | DB token | target 条目 | 近邻 slots(top_n, filter_eq_count, filter_eq_top) | 非 target 40 | nat Python | Calendar v3 | v3fix |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in SEEDS:
        for a in ARMS:
            c = out["cells"][lab(s, a)]
            pl = c["plan"]
            md.append("| %s | %s | %s | %s / %s / %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                str(s)[-2:], a, f3(c.get("main")), f3(c.get("tool")), f3(c.get("arguments")), f3(c.get("final")),
                pl["slots"] if pl else "0", pl["db_input_tokens"] if pl else "0",
                ", ".join(x.replace("database-train-", "") for x in pl["target_ids"]) if pl and pl["target_ids"] else "—",
                ", ".join(str(pl["near_slots"][k]) for k in NEAR) if pl else "—",
                f3(c.get("db_nontarget")), f3(c.get("natv2_python")), f3(c.get("calendar_v3")), f3(c.get("v3fix"))))
    md += ["", "## 4. 答对的题（题号后缀）", ""]
    for s, v in overlap.items():
        md.append("- 种子 %s：other %s；dbbg %s；两臂共同 %s；dose_db1 %s；tf25 答对 %d 题，其中含 other 的 %d/%d、dbbg 的 %d/%d。" % (
            s[-2:], v["other"] or "—", v["dbbg"] or "—", v["both"] or "—", v["dose_db1"] or "—", v["tf25_n"],
            v["other_in_tf25"], len(v["other"]), v["dbbg_in_tf25"], len(v["dbbg"])))
    md += ["", "## 5. 非 target 五模式（探索记录，不进主结论）", "", "| 种子 | 臂 | 各模式 |", "|---|---|---|"]
    for s in SEEDS:
        for a in ("e3b2_A_target_other", "e3b2_A_target_dbbg", "none"):
            p = out["cells"][lab(s, a)].get("db_nontarget_patterns") or {}
            md.append("| %s | %s | %s |" % (str(s)[-2:], a, "，".join("%s %.3f" % (k, v) for k, v in sorted(p.items()))))
    open(OUT / "e3b2_three_seed_ZH.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("wrote", OUT / "e3b2_three_seed_ZH.md")


if __name__ == "__main__":
    main()
