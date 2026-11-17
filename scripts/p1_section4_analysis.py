#!/usr/bin/env python3
"""P1 报告第 4 节的补充分析（只读，CPU）。

输入：runs_ext_p1_b1/summary.json 与 runs_ext_p1_b1/evaluation/*/*/results.jsonl。
输出：runs_ext_p1_b1/analysis/section4_analysis.json、section4_tables_ZH.md。
用法（项目根目录）：.venv/bin/python scripts/p1_section4_analysis.py
不写任何已有文件，不占 GPU。
"""
import json, os, statistics, sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
B1 = os.path.join(ROOT, "runs_ext_p1_b1")
EV = os.path.join(B1, "evaluation")
OUT = os.path.join(B1, "analysis")
SEEDS = ["20261108", "20261109", "20261110"]
S = json.load(open(os.path.join(B1, "summary.json"), encoding="utf-8"))
SC = S["scores"]


def rows(label, suite):
    p = os.path.join(EV, label, suite, "results.jsonl")
    if not os.path.exists(p):
        return None
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def score(label, suite, key="score"):
    v = SC.get(label, {}).get(suite)
    return None if v is None else v.get(key)


def mean_sd(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    return round(statistics.mean(xs), 4), (round(statistics.stdev(xs), 4) if len(xs) > 1 else None)


def f(x):
    return "—" if x is None else f"{x:.3f}"


def decomp(label, suite="natv2_database"):
    r = rows(label, suite)
    if r is None:
        return None
    n = len(r)
    return {
        "n": n,
        "tool": sum(x["tool_correct"] for x in r) / n,
        "arguments": sum(x["arguments_correct"] for x in r) / n,
        "execution": sum(bool(x["execution_success"]) for x in r) / n,
        "final": sum(x["final_correct"] for x in r) / n,
        "joint": sum(x["joint_success"] for x in r) / n,
        "joint_ids": sorted(x["episode_id"] for x in r if x["joint_success"]),
    }


res = {"generated": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S +0800"),
       "source": "runs_ext_p1_b1/summary.json + results.jsonl"}
md = ["# P1 第 4 节补充分析表（Protocol-B1）", "",
      f"生成：{res['generated']}（Asia/Shanghai）。脚本 `scripts/p1_section4_analysis.py`，只读 summary.json 与 results.jsonl。", ""]

# ---- A. 桥接翻转汇总 ----
br = S["bridge_b1_vs_b32"]
agg = defaultdict(lambda: {"ckpts": 0, "items": 0, "down": 0, "up": 0, "zero_flip_ckpts": 0})
for label, suites in br.items():
    seed = label.split("_")[1].replace("seed", "")
    for suite, d in suites.items():
        for key in (seed, "all"):
            a = agg[(key, suite)]
            a["ckpts"] += 1
            a["items"] += d["n"]
            a["down"] += d["n_flip_b32_right_to_b1_wrong"]
            a["up"] += d["n_flip_b32_wrong_to_b1_right"]
            a["zero_flip_ckpts"] += int(d["n_flip_b32_right_to_b1_wrong"] + d["n_flip_b32_wrong_to_b1_right"] == 0)
suites_order = ["natv2_database", "natv2_file", "natv2_python", "calendar_v3", "p2_file", "p2_python", "p2_database"]
res["bridge_aggregate"] = {f"{k[0]}|{k[1]}": v for k, v in agg.items()}
md += ["## A. 协议桥接翻转汇总（B1 对历史 B32，同 checkpoint 同题）", "",
       "「B32对→B1错」= down，「B32错→B1对」= up；翻转率 =(down+up)/题次。", "",
       "| 种子 | suite | checkpoint 数 | 题次 | B32对→B1错 | B32错→B1对 | 净(up−down) | 翻转率 | 零翻转 checkpoint |", "|---|---|---|---|---|---|---|---|---|"]
for key in SEEDS + ["all"]:
    for suite in suites_order:
        a = agg.get((key, suite))
        if not a:
            continue
        md.append(f"| {key[-2:] if key!='all' else '三种子合计'} | {suite} | {a['ckpts']} | {a['items']} | {a['down']} | {a['up']} | {a['up']-a['down']:+d} | {(a['down']+a['up'])/a['items']:.3f} | {a['zero_flip_ckpts']} |")
tot = {"items": 0, "down": 0, "up": 0}
for (k, s), a in agg.items():
    if k == "all":
        for x in tot:
            tot[x] += a[x]
res["bridge_total"] = tot
md += ["", f"全部 suite 合计：题次 {tot['items']}，B32对→B1错 {tot['down']}，B32错→B1对 {tot['up']}，翻转率 {(tot['down']+tot['up'])/tot['items']:.3f}。", ""]

# ---- B. natv2 Database 目标模式分解 ----
arms_dec = ["stage_02_database", "stage_03_python", "stage_04_calendar", "none", "ctrl_cal10", "dose_db0", "dose_db1",
            "e3b2_A_target_other", "e3b2_A_target_dbbg", "tf25", "dose_db2", "dose_db3", "dose_db4", "dose_db6", "tf50", "b20_tf50"]
res["natv2_database_decomp"] = {}
md += ["## B. nat v2 Database（`db.filter_cmp_top`，30 题）逐环节分解", "",
       "tool=选对 `db_query`；arguments=SQL 执行结果与金标一致；final=最终答案对；joint=主指标。", "",
       "| 种子 | checkpoint | tool | arguments | final | joint |", "|---|---|---|---|---|---|"]
for seed in SEEDS:
    for arm in arms_dec:
        d = decomp(f"A_seed{seed}_{arm}")
        if d is None:
            continue
        res["natv2_database_decomp"][f"{seed}|{arm}"] = d
        md.append(f"| {seed[-2:]} | {arm} | {d['tool']:.3f} | {d['arguments']:.3f} | {d['final']:.3f} | {d['joint']:.3f} |")
md.append("")

# ---- C. T0/T1 同题集：phase2 Database 与非 target ----
tl = ["stage_02_database", "stage_03_python", "none", "stage_04_calendar"]
md += ["## C. T0 / stage_03 / T1 / stage_04（参考）同题集逐模式（B1）", "",
       "| 种子 | suite:模式 | T0 stage_02 | stage_03 | T1 none | stage_04（参考） |", "|---|---|---|---|---|---|"]
res["timeline_patterns"] = {}
for seed in SEEDS:
    for suite in ["natv2_database", "db_nontarget", "p2_database", "natv2_file", "p2_file", "natv2_python", "p2_python", "calendar_v3"]:
        pats = set()
        for arm in tl:
            v = SC.get(f"A_seed{seed}_{arm}", {}).get(suite)
            if v:
                pats |= set(v["patterns"])
        for p in ["overall"] + sorted(pats):
            vals = []
            for arm in tl:
                v = SC.get(f"A_seed{seed}_{arm}", {}).get(suite)
                vals.append(None if not v else (v["score"] if p == "overall" else v["patterns"].get(p)))
            res["timeline_patterns"][f"{seed}|{suite}|{p}"] = dict(zip(tl, vals))
            md.append(f"| {seed[-2:]} | {suite}:{p} | " + " | ".join(f(x) for x in vals) + " |")
md.append("")

# ---- D. 剂量曲线 ----
doses = ["none", "dose_db0", "dose_db1", "dose_db2", "dose_db3", "dose_db4", "dose_db6"]
res["dose"] = {}
md += ["## D. Database 剂量曲线（B1）：目标模式 vs 非 target 40 题", "",
       "| 臂 | 目标 08 | 09 | 10 | 均值±SD | 历史 B32 均值 | 非 target 08 | 09 | 10 | 均值±SD |", "|---|---|---|---|---|---|---|---|---|---|"]
for arm in doses:
    t = [score(f"A_seed{s}_{arm}", "natv2_database") for s in SEEDS]
    b32 = [br.get(f"A_seed{s}_{arm}", {}).get("natv2_database", {}).get("b32") for s in SEEDS]
    nt = [score(f"A_seed{s}_{arm}", "db_nontarget") for s in SEEDS]
    mt, st = mean_sd(t); mb, _ = mean_sd(b32); mn, sn = mean_sd(nt)
    res["dose"][arm] = {"target_b1": t, "target_b1_mean": mt, "target_b1_sd": st, "target_b32": b32, "target_b32_mean": mb,
                        "nontarget_b1": nt, "nontarget_mean": mn, "nontarget_sd": sn}
    md.append(f"| {arm} | " + " | ".join(f(x) for x in t) + f" | {f(mt)}±{f(st)} | {f(mb)} | " + " | ".join(f(x) for x in nt) + f" | {f(mn)}±{f(sn)} |")
md.append("")

# ---- E. v3fix ----
v3arms = ["stage_02_database", "stage_03_python", "stage_04_calendar", "none", "ctrl_cal10", "ctrl_cal20", "dose_db0", "dose_db1",
          "dose_db6", "tf25", "tf50", "b20_tf50", "e3b2_A_target_other", "e3b2_A_target_dbbg"]
res["v3fix"] = {}
md += ["## E. v3fix（附加指标，30 题）：Tool Accuracy / Conditional Counting / Joint", "",
       "| checkpoint | 08 | 09 | 10 | Joint 均值 |", "|---|---|---|---|---|"]
for arm in v3arms:
    cells, js = [], []
    for s in SEEDS:
        v = SC.get(f"A_seed{s}_{arm}", {}).get("v3fix")
        if not v:
            cells.append("—"); continue
        res["v3fix"][f"{s}|{arm}"] = {k: v.get(k) for k in ("tool_accuracy", "conditional_counting_accuracy", "joint_success", "n_tool_correct", "source")}
        cc = v.get("conditional_counting_accuracy")
        cells.append(f"{v['tool_accuracy']:.3f} / {f(cc)} / {v['joint_success']:.3f}")
        js.append(v["joint_success"])
    m, _ = mean_sd(js)
    md.append(f"| {arm} | " + " | ".join(cells) + f" | {f(m)} |")
md.append("")

# ---- F. 实验 A 种子 08 ----
s = "20261108"
armsA = ["e3b2_A_target_other", "e3b2_A_target_dbbg", "ctrl_cal10", "dose_db0", "dose_db1", "tf25", "none"]
res["expA_seed08"] = {}
md += ["## F. 实验 A 种子 08：主指标与副指标（B1）", "",
       "| 臂 | 主指标 natv2 DB joint | tool/args/final | 非 target 40 | nat File | nat Python | Calendar v3 | p2 File | p2 Python | p2 DB | v3fix 联合 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
for arm in armsA:
    lab = f"A_seed{s}_{arm}"
    d = decomp(lab)
    row = {k: score(lab, k) for k in ["natv2_database", "db_nontarget", "natv2_file", "natv2_python", "calendar_v3", "p2_file", "p2_python", "p2_database", "v3fix"]}
    row["decomp"] = d
    res["expA_seed08"][arm] = row
    md.append(f"| {arm} | {f(row['natv2_database'])} | {d['tool']:.3f}/{d['arguments']:.3f}/{d['final']:.3f} | " +
              " | ".join(f(row[k]) for k in ["db_nontarget", "natv2_file", "natv2_python", "calendar_v3", "p2_file", "p2_python", "p2_database", "v3fix"]) + " |")
o = set(res["expA_seed08"]["e3b2_A_target_other"]["decomp"]["joint_ids"])
g = set(res["expA_seed08"]["e3b2_A_target_dbbg"]["decomp"]["joint_ids"])
t25 = set(res["expA_seed08"]["tf25"]["decomp"]["joint_ids"])
d1 = set(res["expA_seed08"]["dose_db1"]["decomp"]["joint_ids"])
res["expA_seed08_overlap"] = {"target_other": sorted(o), "target_dbbg": sorted(g), "both": sorted(o & g),
                              "dose_db1": sorted(d1), "tf25": sorted(t25)}
md += ["", f"主指标答对的题：target_other {sorted(o)}；target_dbbg {sorted(g)}；两臂共同 {len(o & g)} 题；dose_db1 {sorted(d1)}；tf25 共 {len(t25)} 题。", ""]
for arm in armsA:
    v = SC.get(f"A_seed{s}_{arm}", {}).get("db_nontarget")
    if v:
        md.append(f"- {arm} 非 target 五模式：" + "，".join(f"{k} {x:.3f}" for k, x in sorted(v["patterns"].items())))
cl = S["coverage_ledger"]
md += ["", "复习池（coverage_ledger，只读计划）：", ""]
for arm in armsA:
    c = cl.get(f"A_seed{s}_{arm}")
    if c and c.get("n_slots"):
        md.append(f"- {arm}：slots {c['n_slots']}，filter_cmp_top {c['db_filter_cmp_top_slots']}，近邻 {c['db_neighbour_slots']}，各族 token {c['tokens_by_family']}，target_ids {c['target_ids']}")
md.append("")

# ---- G. tf00 等旁证（预注册 §6）----
side = ["none", "tf00", "tf25", "tf50", "dose_db6"]
res["side_evidence"] = {}
md += ["## G. File / Python 旁证（预注册 §6）：目标模式 vs 同工具其它模式（B1）", ""]
for suite, tgt in [("p2_file", "file.search_last"), ("p2_python", "py.median")]:
    md += [f"### {suite}（目标模式 `{tgt}`）", "", "| 臂 | 种子 | 目标模式 | 其它模式均值 | 各模式 |", "|---|---|---|---|---|"]
    for arm in side:
        for sd in SEEDS:
            v = SC.get(f"A_seed{sd}_{arm}", {}).get(suite)
            if not v:
                continue
            others = [x for k, x in v["patterns"].items() if k != tgt]
            res["side_evidence"][f"{suite}|{arm}|{sd}"] = {"target": v["patterns"].get(tgt), "others_mean": statistics.mean(others), "patterns": v["patterns"]}
            md.append(f"| {arm} | {sd[-2:]} | {f(v['patterns'].get(tgt))} | {statistics.mean(others):.3f} | " + "，".join(f"{k.split('.')[1]} {x:.2f}" for k, x in sorted(v["patterns"].items())) + " |")
    md.append("")
md += ["### nat v2 File（search_last）/ Python（median）总分", "", "| 臂 | nat File 08/09/10 | 均值 | nat Python 08/09/10 | 均值 |", "|---|---|---|---|---|"]
for arm in side:
    fl = [score(f"A_seed{sd}_{arm}", "natv2_file") for sd in SEEDS]
    py = [score(f"A_seed{sd}_{arm}", "natv2_python") for sd in SEEDS]
    md.append(f"| {arm} | " + " / ".join(f(x) for x in fl) + f" | {f(mean_sd(fl)[0])} | " + " / ".join(f(x) for x in py) + f" | {f(mean_sd(py)[0])} |")
    res["side_evidence"][f"natv2|{arm}"] = {"natv2_file": fl, "natv2_python": py}
md.append("")
for arm in side:
    for sd in SEEDS:
        c = cl.get(f"A_seed{sd}_{arm}")
        if c and c.get("n_slots"):
            res["side_evidence"].setdefault("coverage", {})[f"{arm}|{sd}"] = {"target_ids": c["target_ids"], "covered": c["covered_patterns"]}

os.makedirs(OUT, exist_ok=True)
json.dump(res, open(os.path.join(OUT, "section4_analysis.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(OUT, "section4_tables_ZH.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print("wrote", OUT)
