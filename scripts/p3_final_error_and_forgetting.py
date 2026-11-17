#!/usr/bin/env python3
"""[ext 2026-11-14] 只读 CPU 分析：
 (B) P3 三臂 B1 db.filter_cmp_top 里「arguments 对、final 错」的题归类（顺序被改写 / 补齐多余条目 / 其它）；
     并统计 Database 复习池 target 条目与测试题的答案结构（LIMIT k vs 实际返回行数、答案顺序是否等于字母序）。
 (C) 真遗忘两模式（p2_database db.list_tables 6 题、p2_python py.median 5 题、natv2_python py.median 30 题）
     在全部已有 checkpoint 的 B1（以及只有 B32 的 b05/b20 格子）逐题结果；每个 checkpoint 复习里对应模式条目的位置与之后更新次数；
     复习池里这两个模式的可用经验条数与来源阶段数据。
输出：runs_ext_p3_count_timing/analysis/p3_final_error_forgetting.json（新文件）。
用法（项目根）：.venv/bin/python scripts/p3_final_error_and_forgetting.py
"""
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))
from fac_tinyagent import p1_run as P  # noqa: E402
from fac_tinyagent.utils import read_jsonl  # noqa: E402

SEEDS = [20261108, 20261109, 20261110]
ACC = 8
TIM = ROOT / "runs_ext_e3b2_timing"; P3R = ROOT / "runs_ext_p3_count_timing"
P1_ARMS = ["stage_02_database", "stage_03_python", "stage_04_calendar", "none", "ctrl_cal10", "ctrl_cal20", "tf00", "tf25", "tf50",
           "b20_tf50", "dose_db0", "dose_db1", "dose_db2", "dose_db3", "dose_db4", "dose_db6", "e3b2_A_target_other", "e3b2_A_target_dbbg"]
TIM_ARMS = ["dose_db1_pos143", "target_other_pos143"]
P3_ARMS = ["dose_db1_pos127", "dose_db4_late", "dose_db1_pos95"]
B32_ONLY = ["b05_tf00", "b05_tf25", "b05_tf50", "b20_tf00", "b20_tf25"]
REPLAY_PAT = {"list_tables": ["db_list_tables"], "median": ["stats_median", "target_median_natural"]}
TESTS = {"p2_database": ("list_tables", "db_list_tables_test"), "p2_python": ("median_prose", "stats_median_prose"),
         "natv2_python": ("median_nat", "paired_median_natural")}


def ck_res(src, s, a, suite):
    if src == "p1":
        return P.ckpt_path(s, a), P.results_path(s, a, suite)
    if src == "b32":
        return P.ckpt_path(s, a), P.historical_b32(s, a, suite)
    R = TIM if src == "timing" else P3R
    lab = "A_seed%d_%s" % (s, a)
    return R / "branches" / lab / "checkpoint", R / "evaluation" / lab / suite / "results.jsonl"


def replay_timing(ck):
    f = ck / "training_log.jsonl"
    if not f.exists():
        return None
    L = read_jsonl(f)
    tot = json.load(open(ck / "train_summary.json", encoding="utf-8"))["optimizer_steps"]
    out = defaultdict(list)
    for x in L:
        if x.get("kind") == "new":
            continue
        stem = x["episode_id"].split("-train-")[-1].rsplit("-", 1)[0]
        for pat, stems in REPLAY_PAT.items():
            if stem in stems:
                win = (x["microstep"] - 1) // ACC + 1
                out[pat].append({"id": x["episode_id"].split("-train-")[-1], "pos": x.get("new_position"), "after": tot - win + 1})
    return {"total_steps": tot, **{p: out.get(p, []) for p in REPLAY_PAT}}


def test_score(path, stem):
    if path is None or not Path(path).exists():
        return None
    r = [x for x in read_jsonl(path) if stem in x["episode_id"]]
    if not r:
        return None
    fails = Counter()
    for x in r:
        if not x["joint_success"]:
            fails["%s %s" % (x.get("predicted_tool"), json.dumps(x.get("predicted_arguments"), ensure_ascii=False)[:60])] += 1
    return {"n": len(r), "k": sum(bool(x["joint_success"]) for x in r), "tool": sum(bool(x["tool_correct"]) for x in r),
            "args": sum(bool(x["arguments_correct"]) for x in r), "final": sum(bool(x["final_correct"]) for x in r),
            "fails": fails.most_common(3)}


def forgetting():
    rows = []
    for src, arms in (("p1", P1_ARMS), ("timing", TIM_ARMS), ("p3", P3_ARMS), ("b32", B32_ONLY)):
        for a in arms:
            for s in SEEDS:
                ck, _ = ck_res(src, s, a, "p2_database")
                rt = None if a.startswith("stage_") else replay_timing(ck)
                row = {"src": src, "arm": a, "seed": s, "protocol": "B32" if src == "b32" else "B1", "replay": rt}
                for suite, (key, stem) in TESTS.items():
                    _, rp = ck_res(src, s, a, suite)
                    row[key] = test_score(rp, stem)
                if any(row[k] for k in ("list_tables", "median_prose", "median_nat")):
                    rows.append(row)
    return rows


def pool_inventory():
    inv = {}
    for fam, pats in (("database", ["db_list_tables"]), ("python", ["stats_median", "target_median_natural"])):
        pool = read_jsonl(ROOT / "data_ext_e4" / "pool" / ("%s.jsonl" % fam))
        stage = {}
        for sp in ("train", "val", "test"):
            f = ROOT / "data_phase2" / fam / ("%s.jsonl" % sp)
            if f.exists():
                for x in read_jsonl(f):
                    stage[x["episode_id"]] = sp
                    stage.setdefault("prompt::" + x.get("prompt", ""), sp)
        for pat in pats:
            items = [x for x in pool if x["episode_id"].split("-train-")[-1].rsplit("-", 1)[0] == pat]
            inv[pat] = {"family": fam, "n_pool": len(items),
                        "in_phase2_train_by_id": sum(stage.get(x["episode_id"]) == "train" for x in items),
                        "in_phase2_by_prompt": sum(("prompt::" + x["prompt"]) in stage for x in items),
                        "template_ids": sorted({x.get("template_id") for x in items}),
                        "example_prompt": items[0]["prompt"] if items else None,
                        "example_tool": items[0].get("expected_tool") if items else None,
                        "example_args": items[0].get("expected_arguments") if items else None,
                        "ids": [x["episode_id"].split("-train-")[-1] for x in items]}
    return inv


LIM = re.compile(r"LIMIT\s+(\d+)", re.I)


def final_errors():
    out = {"cases": [], "by_arm": {}}
    arms = [("p3", a) for a in P3_ARMS] + [("p1", "dose_db4"), ("timing", "dose_db1_pos143")]
    for src, a in arms:
        cnt = Counter(); tot = 0
        for s in SEEDS:
            _, rp = ck_res(src, s, a, "natv2_database")
            if not Path(rp).exists():
                continue
            for x in read_jsonl(rp):
                if not (x["arguments_correct"] and not x["final_correct"]):
                    continue
                tot += 1
                obs = [r[0] if len(r) == 1 else r for r in json.loads(x["observation"])["result"]["rows"]]
                ans = x.get("predicted_answer"); exp = x["expected_final_answer"]
                m = LIM.search(x["predicted_arguments"].get("sql", "")); lim = int(m.group(1)) if m else None
                if not isinstance(ans, list):
                    cat = "非列表/格式"
                elif sorted(map(str, ans)) == sorted(map(str, exp)):
                    cat = "顺序改写（字母序）" if list(ans) == sorted(ans) else "顺序改写（其它）"
                elif set(map(str, exp)) <= set(map(str, ans)) and len(ans) > len(exp):
                    cat = "多出条目（补到 LIMIT）" if lim is not None and len(ans) == lim else "多出条目（重复/其它）"
                elif set(map(str, ans)) < set(map(str, exp)):
                    cat = "漏条目"
                else:
                    cat = "其它"
                cnt[cat] += 1
                out["cases"].append({"arm": a, "seed": s, "id": x["episode_id"][-3:], "cat": cat, "sql": x["predicted_arguments"].get("sql"),
                                     "limit": lim, "n_rows": len(obs), "observation_rows": obs, "answer": ans, "expected": exp})
        out["by_arm"][a] = {"n_args_ok_final_wrong": tot, "categories": dict(cnt)}
    # 测试题与 target 经验的答案结构
    def struct(rows_iter):
        c = Counter()
        for exp, sql in rows_iter:
            m = LIM.search(sql or ""); lim = int(m.group(1)) if m else None
            e = exp if isinstance(exp, list) else [exp]
            c["n"] += 1
            if lim is not None and len(e) < lim: c["rows_lt_limit"] += 1
            if len(e) >= 2:
                c["multi"] += 1
                if list(map(str, e)) != sorted(map(str, e)): c["multi_order_ne_alpha"] += 1
        return dict(c)
    _, rp = ck_res("p3", 20261108, "dose_db1_pos127", "natv2_database")
    test_rows = read_jsonl(rp)
    out["test_structure"] = struct((x["expected_final_answer"], (x.get("predicted_arguments") or {}).get("sql") if x["arguments_correct"] else None) for x in test_rows)
    pool = [x for x in read_jsonl(ROOT / "data_ext_e4/pool/database.jsonl") if "target_db_filter_top" in x["episode_id"]]
    out["target_pool_structure"] = struct((x["expected_final_answer"], x["expected_arguments"].get("sql")) for x in pool)
    out["target_pool_items"] = [{"id": x["episode_id"][-3:], "sql": x["expected_arguments"].get("sql"), "answer": x["expected_final_answer"]} for x in pool]
    # 其它 Database 复习模式里多行答案的顺序（是否天然字母序）
    dbpool = read_jsonl(ROOT / "data_ext_e4/pool/database.jsonl")
    oth = Counter()
    for x in dbpool:
        e = x["expected_final_answer"]
        if isinstance(e, list) and len(e) >= 2 and "target_db_filter_top" not in x["episode_id"]:
            stem = x["episode_id"].split("-train-")[-1].rsplit("-", 1)[0]
            oth[(stem, list(map(str, e)) == sorted(map(str, e)))] += 1
    out["other_db_multi_answers_alpha"] = {"%s|alpha=%s" % k: v for k, v in oth.items()}
    return out


def main():
    res = {"forgetting_rows": forgetting(), "pool_inventory": pool_inventory(), "final_errors": final_errors()}
    od = P3R / "analysis"; od.mkdir(parents=True, exist_ok=True)
    (od / "p3_final_error_forgetting.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    fe = res["final_errors"]
    print(json.dumps(fe["by_arm"], ensure_ascii=False)); print(fe["test_structure"], fe["target_pool_structure"])
    print(json.dumps(fe["target_pool_items"], ensure_ascii=False)); print(fe["other_db_multi_answers_alpha"])
    print(json.dumps(res["pool_inventory"], ensure_ascii=False)[:3000])
    f3 = lambda d: "—" if not d else "%d/%d" % (d["k"], d["n"])
    for r in res["forgetting_rows"]:
        rp = r["replay"] or {}
        print(r["protocol"], r["arm"], str(r["seed"])[-2:], "LT", f3(r["list_tables"]), "MP", f3(r["median_prose"]), "MN", f3(r["median_nat"]),
              "| lt", [(x["pos"], x["after"]) for x in rp.get("list_tables", [])],
              "| md", [(x["id"].split("-")[0][:6] + x["id"][-3:], x["pos"], x["after"]) for x in rp.get("median", [])], "| steps", rp.get("total_steps"))


if __name__ == "__main__":
    main()
