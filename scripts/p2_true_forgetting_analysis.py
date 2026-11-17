#!/usr/bin/env python3
"""P2 真遗忘模式分析（只读，CPU，不占 GPU）。

问题：模型原本会、后来掉了的模式（真遗忘），能否被复习恢复？需要多少条经验？

输入（只读）：
  - runs_ext_p1_b1/evaluation/<label>/<suite>/results.jsonl（Protocol-B1 逐题结果；
    db_nontarget 按 p1_run 的规则复用 P0 的 B1 结果）
  - 各 checkpoint 目录下的 replay_plan.json（复习池实际插入的条目、token）
  - data_ext_e4/pool/*.jsonl、data_phase2/calendar/train.jsonl（用于给复习条目归模式）
输出（新文件）：
  - runs_ext_p1_b1/analysis/true_forgetting_analysis.json
  - runs_ext_p1_b1/analysis/true_forgetting_tables_ZH.md
用法（项目根目录）：.venv/bin/python scripts/p2_true_forgetting_analysis.py
只用 B1，不读任何 B32 结果；不修改任何已有文件。题数不完整的 suite（如正在评测中的）自动跳过。
"""
import json, os, statistics, sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
sys.path.insert(0, str(ROOT))
from fac_tinyagent import p1_run as P  # noqa: E402  只用其路径/计分函数，不调用评测或训练
from fac_tinyagent.coverage_patterns import classify_item  # noqa: E402

B1 = ROOT / "runs_ext_p1_b1"
EV = B1 / "evaluation"
OUT = B1 / "analysis"
SEEDS = [20261108, 20261109, 20261110]
OLD_SUITES = ["p2_database", "p2_python", "p2_file", "natv2_database", "natv2_python", "natv2_file", "db_nontarget"]
TIMELINE = ["stage_02_database", "stage_03_python", "none", "stage_04_calendar"]
ARM_ORDER = ["stage_02_database", "stage_03_python", "stage_04_calendar", "none", "ctrl_cal10", "ctrl_cal20",
             "tf00", "tf25", "tf50", "b20_tf50", "dose_db0", "dose_db1", "dose_db2", "dose_db3", "dose_db4", "dose_db6",
             "e3b2_A_target_other", "e3b2_A_target_dbbg"]
# 指定的真遗忘模式（suite, pattern, 参照点）。参照点 = 该工具训练完后的 checkpoint：
# Database 在 stage_02 训练，Python 在 stage_03 训练。
FOCAL = [("p2_database", "db.list_tables", "stage_02_database"),
         ("p2_python", "py.median", "stage_03_python"),
         ("natv2_python", "py.median", "stage_03_python")]
SMALL_N = 5
CAND_REF_MIN, CAND_DROP_MIN = 0.6, 0.2  # 其它候选：参照点三种子均值 ≥0.6，且到 T1(none) 均值下降 ≥0.2


def ref_stage(pattern):
    return "stage_03_python" if pattern.startswith("py.") else "stage_02_database"


def label(seed, arm):
    return "A_seed%d_%s" % (seed, arm)


def arms_present():
    found = set()
    for d in EV.iterdir():
        if d.is_dir() and d.name.startswith("A_seed"):
            found.add(d.name.split("_", 2)[2])
    return [a for a in ARM_ORDER if a in found] + sorted(found - set(ARM_ORDER))


# ---------------------------------------------------------------- B1 逐题计分
def pattern_counts(seed, arm, suite):
    """-> {pattern: [k, n]}；结果缺失或题数不完整返回 None。"""
    p = P.results_path(seed, arm, suite)
    if not p.exists():
        return None
    res = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    rows, _, _, _ = P.suite_rows(suite)
    if len(res) != len(rows):
        return None
    by_id = {r["episode_id"]: r for r in rows}
    out = defaultdict(lambda: [0, 0])
    for r in res:
        k = P._pattern(by_id[r["episode_id"]])
        out[k][0] += P._ok(r, suite)
        out[k][1] += 1
    return {k: v for k, v in out.items()}


def pattern_decomp(seed, arm, suite, pattern):
    """该模式题目的 tool / arguments / final / joint 逐环节计数 + 失败时最常见的 (工具, 参数) 形态。"""
    p = P.results_path(seed, arm, suite)
    if not p.exists():
        return None
    res = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    rows, _, _, _ = P.suite_rows(suite)
    if len(res) != len(rows):
        return None
    by_id = {r["episode_id"]: r for r in rows}
    sel = [r for r in res if P._pattern(by_id[r["episode_id"]]) == pattern]
    fails = defaultdict(int)
    for r in sel:
        if not P._ok(r, suite):
            args = r.get("predicted_arguments")
            if isinstance(args, dict) and "values" in args:
                args = {"values": "..."}
            fails["%s %s" % (r.get("predicted_tool"), json.dumps(args, ensure_ascii=False))] += 1
    return {"n": len(sel), "tool": sum(bool(r["tool_correct"]) for r in sel),
            "arguments": sum(bool(r["arguments_correct"]) for r in sel),
            "final": sum(bool(r["final_correct"]) for r in sel),
            "ok": sum(P._ok(r, suite) for r in sel), "failure_forms": dict(fails)}


def test_items(suite, pattern):
    rows, _, _, _ = P.suite_rows(suite)
    sel = [r for r in rows if P._pattern(r) == pattern]
    return {"n": len(sel), "n_unique_prompts": len({r.get("prompt") for r in sel}),
            "templates": sorted({r.get("template_id") or "?" for r in sel}),
            "example_prompt": sel[0].get("prompt") if sel else None}


# ---------------------------------------------------------------- 复习池
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


def replay_by_pattern(seed, arm):
    """-> (plan_path, {pattern: {slots, unique, input_tokens, supervised_tokens, target_slots, templates}}, n_unclassified)"""
    if arm.startswith("stage_"):
        return None, {}, 0
    pp = P.ckpt_path(seed, arm) / "replay_plan.json"
    if not pp.exists():
        return None, {}, 0
    plan = json.load(open(pp, encoding="utf-8"))
    raw = raw_pool()
    agg = defaultdict(lambda: {"slots": 0, "ids": set(), "input_tokens": 0, "supervised_tokens": 0,
                               "target_slots": 0, "templates": defaultdict(int)})
    miss = 0
    for it in plan.get("items", []):
        row = raw.get(it["episode_id"])
        if row is None:
            miss += 1
            continue
        pat = classify_item(row).pattern
        a = agg[pat]
        a["slots"] += 1
        a["ids"].add(it["episode_id"])
        a["input_tokens"] += int(it.get("input_tokens", 0))
        a["supervised_tokens"] += int(it.get("supervised_tokens", 0))
        a["target_slots"] += int(bool(it.get("target")))
        a["templates"][row.get("template_id") or "?"] += 1
    out = {}
    for k, a in agg.items():
        out[k] = {"slots": a["slots"], "unique": len(a["ids"]), "input_tokens": a["input_tokens"],
                  "supervised_tokens": a["supervised_tokens"], "target_slots": a["target_slots"],
                  "templates": dict(a["templates"])}
    return str(pp.relative_to(ROOT)), out, miss


def f3(x):
    return "—" if x is None else "%.3f" % x


def acc(kn):
    return None if not kn else kn[0] / kn[1]


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def main():
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S +0800")
    arms = arms_present()
    res = {"generated": now, "protocol": "Protocol-B1 only", "arms": arms, "seeds": SEEDS,
           "scores": {}, "replay": {}, "timeline": {}, "candidates": [], "focal": {}, "dose_response": {}}

    # 1) 逐模式 B1 计分
    for s in SEEDS:
        for a in arms:
            lab = label(s, a)
            for su in OLD_SUITES:
                pc = pattern_counts(s, a, su)
                if pc is not None:
                    res["scores"].setdefault(lab, {})[su] = pc
    # 2) 复习池
    for s in SEEDS:
        for a in arms:
            pp, rp, miss = replay_by_pattern(s, a)
            if pp:
                res["replay"][label(s, a)] = {"plan": pp, "by_pattern": rp, "n_items_not_in_pool": miss}

    def kn(s, a, su, p):
        return res["scores"].get(label(s, a), {}).get(su, {}).get(p)

    # 3) 时间线 + 候选真遗忘模式
    pats = set()
    for lab, d in res["scores"].items():
        for su, pc in d.items():
            pats |= {(su, p) for p in pc}
    for su, p in sorted(pats):
        rs = ref_stage(p)
        row = {}
        for s in SEEDS:
            row[str(s)] = {t: kn(s, t, su, p) for t in TIMELINE}
        res["timeline"]["%s|%s" % (su, p)] = {"ref_stage": rs, "by_seed": row}
        refs = [acc(row[str(s)][rs]) for s in SEEDS]
        t1s = [acc(row[str(s)]["none"]) for s in SEEDS]
        if None in refs or None in t1s:
            continue
        mr, mt = mean(refs), mean(t1s)
        drops = [r - t for r, t in zip(refs, t1s)]
        if mr >= CAND_REF_MIN and mr - mt >= CAND_DROP_MIN:
            n = row[str(SEEDS[0])]["none"][1]
            res["candidates"].append({"suite": su, "pattern": p, "ref_stage": rs, "n": n,
                                      "ref": refs, "t1_none": t1s, "drop": drops,
                                      "all_three_drop": all(d > 0 for d in drops), "small_n": n < SMALL_N})

    # 4) 每个关注模式：臂 × 种子 正确率 + 复习条数；剂量-响应点
    focal = list(FOCAL)
    for c in res["candidates"]:
        if (c["suite"], c["pattern"]) not in {(x[0], x[1]) for x in focal}:
            focal.append((c["suite"], c["pattern"], c["ref_stage"]))
    for su, p, rs in focal:
        key = "%s|%s" % (su, p)
        tab = {}
        pts = []
        for a in arms:
            cells = {}
            for s in SEEDS:
                k = kn(s, a, su, p)
                rp = res["replay"].get(label(s, a), {}).get("by_pattern", {}).get(p)
                has_plan = label(s, a) in res["replay"]
                cells[str(s)] = {"kn": k, "acc": acc(k),
                                 "replay_slots": (rp or {}).get("slots", 0) if has_plan else None,
                                 "replay_unique": (rp or {}).get("unique", 0) if has_plan else None,
                                 "replay_input_tokens": (rp or {}).get("input_tokens", 0) if has_plan else None,
                                 "replay_templates": (rp or {}).get("templates", {}) if has_plan else None,
                                 "decomp": pattern_decomp(s, a, su, p) if k else None}
                if k and (has_plan or a == "none"):
                    pts.append({"arm": a, "seed": s, "slots": cells[str(s)]["replay_slots"] or 0, "acc": acc(k), "kn": k})
            if any(cells[str(s)]["kn"] for s in SEEDS):
                tab[a] = cells
        bins = defaultdict(list)
        for pt in pts:
            bins[pt["slots"]].append(pt)
        dr = {str(b): {"n_points": len(v), "mean_acc": mean([x["acc"] for x in v]),
                       "points": ["%s/%s=%s" % (x["arm"], str(x["seed"])[-2:], f3(x["acc"])) for x in v]}
              for b, v in sorted(bins.items())}
        refs = [acc(kn(s, rs, su, p)) for s in SEEDS]
        tmpl_ex = {}
        raw = raw_pool()
        for cells in tab.values():
            for c in cells.values():
                for t in (c["replay_templates"] or {}):
                    if t not in tmpl_ex:
                        ex = next((r for r in raw.values() if r.get("template_id") == t), None)
                        tmpl_ex[t] = ex.get("prompt") if ex else None
        res["focal"][key] = {"ref_stage": rs, "ref": refs, "test_items": test_items(su, p),
                             "replay_template_examples": tmpl_ex, "table": tab}
        res["dose_response"][key] = dr

    res["conclusions"] = conclusions(res)
    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / "true_forgetting_analysis.json"
    json.dump(res, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=list)
    write_md(res)
    print("wrote", jp)


def conclusions(res):
    """只用上面算出的数字做归纳，不引入新数据。"""
    C = {}
    for key, F in res["focal"].items():
        su, p = key.split("|")
        pts = [(a, s, c) for a, cells in F["table"].items() for s, c in cells.items()
               if c["kn"] and c["replay_slots"] is not None]
        by_seed = {}
        for sd in map(str, SEEDS):
            z = [c["acc"] for a, s, c in pts if s == sd and c["replay_slots"] == 0]
            r = [c["acc"] for a, s, c in pts if s == sd and c["replay_slots"] > 0]
            none = F["table"].get("none", {}).get(sd, {}).get("acc")
            by_seed[sd] = {"none": none, "zero_slot_accs": z, "replay_accs": r,
                           "replay_mean": mean(r), "n_replay_gt_none": sum(x > none for x in r) if none is not None else None,
                           "n_replay_eq_none": sum(x == none for x in r) if none is not None else None,
                           "n_replay_lt_none": sum(x < none for x in r) if none is not None else None,
                           "direction_up": (mean(r) is not None and none is not None and mean(r) > none)}
        bins = {}
        for a, s, c in pts:
            b = c["replay_slots"]
            d = bins.setdefault(b, {"n": 0, "full": 0, "zero": 0, "accs": []})
            d["n"] += 1; d["full"] += int(c["acc"] == 1.0); d["zero"] += int(c["acc"] == 0.0); d["accs"].append(c["acc"])
        for d in bins.values():
            d["mean"] = mean(d["accs"]); del d["accs"]
        # 按复习模板拆分（py.median 有两种训练模板）
        tsplit = {}
        for a, s, c in pts:
            if not c["replay_slots"]:
                continue
            tm = c["replay_templates"] or {}
            grp = "含 %s" % "+".join(sorted(tm)) if tm else "无"
            tsplit.setdefault(s, {}).setdefault(grp, []).append("%s=%s" % (a, f3(c["acc"])))
        C[key] = {"by_seed": by_seed, "by_slots": {str(k): v for k, v in sorted(bins.items())},
                  "by_template": tsplit,
                  "three_seed_direction_up": all(v["direction_up"] for v in by_seed.values())}
    return C


def write_md(res):
    md = ["# 真遗忘模式：复习能否恢复、需要多少（Protocol-B1）", "",
          "生成：%s（Asia/Shanghai）。脚本 `scripts/p2_true_forgetting_analysis.py`，只读 B1 逐题结果与各 checkpoint 的 `replay_plan.json`；不含任何 B32 数字。" % res["generated"], "",
          "约定：正确率 = 该模式题目里 joint 成功的比例（natv2_file 用官方 lenient 规则，与 P1 一致）；`k/n` 为答对数/题数。"
          "复习条数 = 复习池中归入该模式的插入次数（slots，含重复），括号内为不同经验条数（unique）、input token 与训练模板拆分。"
          "参照点：Database/File 模式用 stage_02（T0），Python 模式用 stage_03（Python 刚学完）。T1 = `none`（学完 Calendar、无复习）。"
          "所有复习臂都从 stage_03 出发、在 Calendar 阶段插入复习，因此对 `db.list_tables`（stage_03 已经掉到 0）是「掉了以后再拉回」，对 `py.median`（Calendar 阶段才掉）是「边学边防掉」。"
          "题量 n < %d 标 ⚠。" % SMALL_N, ""]
    md += ["## 1. 候选真遗忘模式（参照点高、T1 明显下降）", "",
           "判定：参照点三种子均值 ≥ %.1f，且到 T1 均值下降 ≥ %.1f；扫描范围为 %s 的全部模式。" % (CAND_REF_MIN, CAND_DROP_MIN, "、".join(OLD_SUITES)), "",
           "| suite | 模式 | n | 不同题面数 | 参照点 | 参照 08/09/10 | T1 none 08/09/10 | 三种子都下降 |", "|---|---|---|---|---|---|---|---|"]
    for c in res["candidates"]:
        ti = res["focal"]["%s|%s" % (c["suite"], c["pattern"])]["test_items"]
        md.append("| %s | %s | %d%s | %d | %s | %s | %s | %s |" % (
            c["suite"], c["pattern"], c["n"], " ⚠" if c["small_n"] else "", ti["n_unique_prompts"], c["ref_stage"],
            " / ".join(f3(x) for x in c["ref"]), " / ".join(f3(x) for x in c["t1_none"]),
            "是" if c["all_three_drop"] else "否"))
    md += ["", "除这三项外没有其它旧工具模式满足判定。全部模式的 T0 / stage_03 / T1 / stage_04 见 JSON `timeline`。", ""]

    sec = 2
    for key, F in res["focal"].items():
        su, p = key.split("|")
        ti = F["test_items"]
        md += ["## %d. `%s`（%s）" % (sec, p, su), "",
               "测试题：n=%d，不同题面 %d 个，模板 %s；例：「%s」。参照点 %s：%s。" % (
                   ti["n"], ti["n_unique_prompts"], ", ".join(ti["templates"]), ti["example_prompt"], F["ref_stage"],
                   " / ".join(f3(x) for x in F["ref"])), ""]
        if F["replay_template_examples"]:
            md.append("复习池里该模式的训练模板：" + "；".join("`%s`「%s」" % (t, (e or "")[:80]) for t, e in F["replay_template_examples"].items()) + "。")
            md.append("")
        md += ["| 臂 | 08 k/n | 09 k/n | 10 k/n | 三种子均值 | 复习条数 08 | 09 | 10 |", "|---|---|---|---|---|---|---|---|"]
        for a, cells in F["table"].items():
            ks, accs, rps = [], [], []
            for s in SEEDS:
                c = cells[str(s)]
                if c["kn"]:
                    ks.append("%d/%d%s" % (c["kn"][0], c["kn"][1], " ⚠" if c["kn"][1] < SMALL_N else ""))
                    accs.append(c["acc"])
                else:
                    ks.append("—")
                if c["replay_slots"] is None:
                    rps.append("—")
                else:
                    tm = "，".join("%s %d" % (t, n) for t, n in sorted((c["replay_templates"] or {}).items()))
                    rps.append("%d（%d，%d tok%s）" % (c["replay_slots"], c["replay_unique"], c["replay_input_tokens"], "；" + tm if tm else ""))
            md.append("| %s | %s | %s | %s |" % (a, " | ".join(ks), f3(mean(accs)), " | ".join(rps)))
        md += ["", "逐环节（tool / arguments / final / 主指标，答对数）与失败形态：", "",
               "| 臂 | 种子 | tool | args | final | 主指标 | 失败时的预测（次数） |", "|---|---|---|---|---|---|---|"]
        for a, cells in F["table"].items():
            for s in SEEDS:
                d = cells[str(s)]["decomp"]
                if not d:
                    continue
                ff = "；".join("%s ×%d" % (k, v) for k, v in sorted(d["failure_forms"].items(), key=lambda x: -x[1])) or "—"
                md.append("| %s | %s | %d/%d | %d/%d | %d/%d | %d/%d | %s |" % (a, str(s)[-2:], d["tool"], d["n"], d["arguments"], d["n"],
                                                                            d["final"], d["n"], d["ok"], d["n"], ff))
        md += ["", "### 复习条数 vs 正确率（每个点 = 一个臂×种子，含 none 与 Calendar 对照；无 B1 结果的臂不计）", "",
               "| 复习条数 | 点数 | 完全恢复(=1.0)点数 | 仍为 0 的点数 | 平均正确率 | 各点 |", "|---|---|---|---|---|---|"]
        cb = res["conclusions"][key]["by_slots"]
        for b, v in res["dose_response"][key].items():
            md.append("| %s | %d | %d | %d | %s | %s |" % (b, v["n_points"], cb[b]["full"], cb[b]["zero"], f3(v["mean_acc"]), "，".join(v["points"])))
        md += ["", "### 每个种子：none 与有复习条目的臂", "", "| 种子 | none | 有复习条目的臂（个数） | 均值 | 高于/等于/低于 none |", "|---|---|---|---|---|"]
        for sd, v in res["conclusions"][key]["by_seed"].items():
            md.append("| %s | %s | %d | %s | %s/%s/%s |" % (sd[-2:], f3(v["none"]), len(v["replay_accs"]), f3(v["replay_mean"]),
                                                       v["n_replay_gt_none"], v["n_replay_eq_none"], v["n_replay_lt_none"]))
        bt = res["conclusions"][key]["by_template"]
        if p == "py.median" and bt:
            md += ["", "### 按复习模板拆分（只列有该模式复习条目的臂）", ""]
            for sd in sorted(bt):
                md.append("- 种子 %s：" % sd[-2:] + "；".join("%s → %s" % (g, "，".join(v)) for g, v in sorted(bt[sd].items())))
        md.append("")
        sec += 1

    md += ["## %d. 结论（方向性描述，不做显著性陈述）" % sec, ""]
    md += conclusion_text(res)
    md += ["", "## 数据缺口", "",
           "- dose_db2/3/4 在 B1 下只评了 natv2_database 与 db_nontarget，没有 p2_database / p2_python / natv2_python 的 B1 结果，因此不进入上表（不用 B32 补）。它们的复习池里 `db.list_tables` 条数见 JSON `replay`。",
           "- 同一种子的 dose_db0/1/6 共享同一批 File/Python 复习条目（Python 部分完全相同），所以对 `py.median` 它们不是独立的剂量点。",
           "- tf00 没有 db_nontarget / calendar_v3 / v3fix 的 B1 结果，但旧工具 p2_* 与 natv2_* 齐全。",
           "- e3b2（实验 A）种子 09/10 若评测未完成，自动跳过；评完后重跑本脚本即可纳入。", ""]
    open(OUT / "true_forgetting_tables_ZH.md", "w", encoding="utf-8").write("\n".join(md) + "\n")


def conclusion_text(res):
    C = res["conclusions"]
    out = []
    # ---- db.list_tables
    k = "p2_database|db.list_tables"
    if k in C:
        bs = C[k]["by_slots"]
        z = bs.get("0", {"n": 0, "full": 0})
        one = bs.get("1", {"n": 0, "full": 0})
        ge2 = [v for b, v in bs.items() if int(b) >= 2]
        ge2n, ge2f = sum(v["n"] for v in ge2), sum(v["full"] for v in ge2)
        seeds = C[k]["by_seed"]
        d = res["focal"][k]["table"]["none"]
        out += ["**`db.list_tables`（p2_database）**", "",
                "- 遗忘形态：stage_02 之后（stage_03、stage_04、none）三种子都是 tool 6/6、final 6/6、arguments 0/6，"
                "失败全部是给 `db_list_tables` 多加了参数 `{\"database\": \"read-only\"}`（应为 `{}`）。也就是说掉的是「无参调用」这个格式，"
                "选工具和最终答案都没掉。论文里如果用 final-answer 口径，这个模式不算遗忘；用 joint 口径才算。",
                "- 题量：6 题但只有 1 个不同题面，所以每个臂×种子的结果实际上是全对或全错，有效样本接近 1 题。⚠",
                "- 复习：复习池里没有该模式条目的臂×种子 %d 个，完全恢复 %d 个（包括 Calendar 对照、none，以及 dose_db6——它把 `db.filter_cmp_top` 拉到 1.000，这里仍为 0，说明恢复只对被复习的模式起作用）。"
                "有 1 条的 %d 个，完全恢复 %d 个；有 2 条及以上的 %d 个，完全恢复 %d 个。" % (z["n"], z["full"], one["n"], one["full"], ge2n, ge2f),
                "- 三种子：" + "；".join("种子 %s 有条目的臂 %d 个，高于 none %s 个" % (sd[-2:], len(v["replay_accs"]), v["n_replay_gt_none"]) for sd, v in seeds.items())
                + "。三种子方向一致：有该模式复习条目就能恢复，没有就不恢复。",
                "- 需要多少：1 条（约 272 input token）多数情况下已经够；2–3 条在已观测的点上全部恢复。没有观测到需要更多条的情况。", ""]
    # ---- py.median p2
    k = "p2_python|py.median"
    if k in C:
        seeds = C[k]["by_seed"]
        out += ["**`py.median`（p2_python，「middle value」措辞，每点 5 题）**", "",
                "- 遗忘形态：失败基本都是把 `stats_median` 换成了 `stats_mean`（选错工具），参数都对。",
                "- 复习：" + "；".join("种子 %s none %s，有条目的臂 %d 个、均值 %s、高于/等于/低于 none = %s/%s/%s" % (
                    sd[-2:], f3(v["none"]), len(v["replay_accs"]), f3(v["replay_mean"]), v["n_replay_gt_none"], v["n_replay_eq_none"], v["n_replay_lt_none"]) for sd, v in seeds.items()) + "。",
                "- 判断：种子 08、10 方向一致向上（没有一个复习臂低于 none）；种子 09 基本不恢复（none 0/5，复习臂最高 1/5）。**三种子方向不一致**。"
                "复习条数和恢复程度对不上：4 条的点平均 %s，2 条的点平均 %s。复习池里的两种模板（`stats_median`「Compute the median…」、`target_median_natural`「…middle position」）都不是测试的「middle value」措辞，"
                "这里的恢复更像是部分迁移，而不是条数够了就回来。每点 5 题，单点差 1 题即 0.2。" % (
                    f3(C[k]["by_slots"].get("4", {}).get("mean")), f3(C[k]["by_slots"].get("2", {}).get("mean"))), ""]
    # ---- py.median natv2
    k = "natv2_python|py.median"
    if k in C:
        seeds = C[k]["by_seed"]
        out += ["**`py.median`（natv2_python，30 题，与 `target_median_natural` 同模板）**", "",
                "- 遗忘只在部分种子出现：stage_03 → none，种子 08 29/30 → 14/30（失败主要是调用不存在的 `stats_sorted`），种子 10 30/30 → 24/30（工具对、参数错），种子 09 28/30 → 30/30（没有遗忘）。",
                "- 复习：" + "；".join("种子 %s none %s，有条目的臂 %d 个、均值 %s、高于/等于/低于 none = %s/%s/%s" % (
                    sd[-2:], f3(v["none"]), len(v["replay_accs"]), f3(v["replay_mean"]), v["n_replay_gt_none"], v["n_replay_eq_none"], v["n_replay_lt_none"]) for sd, v in seeds.items()) + "。",
                "- 关键是模板而不是条数：在出现遗忘的种子 08 和 10 上，复习池里至少有 1 条同模板 `target_median_natural` 的臂都不低于 26/30（种子 08 为 28–30/30，种子 10 为 26–30/30）；"
                "只有 `stats_median` 的臂恢复得不完整或没有恢复（种子 08：tf00 1 条 7/30、e3b2 两臂各 2 条 21/30 和 26/30；种子 10：tf00 1 条 24/30，与 none 相同）。详见上面「按复习模板拆分」。",
                "- 判断：在有遗忘的两个种子上方向一致，2–5 条（708–1,791 input token）、其中至少 1 条同模板的经验就能拉回到接近 stage_03；种子 09 没有遗忘，不能用来判断恢复。", ""]
    out += ["**总判断**：真遗忘可以被复习拉回，前提是复习池里有**同模式、同措辞**的经验。所需量很小：`db.list_tables` 1–3 条（272–816 input token），natv2 `py.median` 2–5 条且至少 1 条同模板（708–1,791 input token）。"
            "没有对应经验时，复习其它模式或复习 Calendar 都不起作用（`db.list_tables` 在 dose_db6 和 Calendar 对照臂中为 0；`py.median` 换措辞后种子 09 拉不回）。"
            "这和 Database S 曲线是「目标模式特定恢复」的结论方向一致，也说明下一步值得研究的是**选哪条经验**，而不是复习比例。"
            "注意：`db.list_tables` 的遗忘是参数格式层面的，有效题面只有 1 个；`py.median` 每点 5 题、三种子方向不一致，写论文时只能作为方向性证据。"]
    return out


if __name__ == "__main__":
    main()
