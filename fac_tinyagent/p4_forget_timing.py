"""[ext 2026-11-14] P4「真遗忘模式上的复习时机」+ 两个饱和模型预测验证臂
（预注册 E3B2_PREREG_AMEND_20261114_p4_forget_timing_ZH.md）。

臂（三种子 20261108/09/10；同一 A_seed* Calendar step-80 prefix；23 次 optimizer 更新；预算与 P3 相同 7494 input token）：
  P4_early / P4_mid / P4_late ：源 data_ext_e3 dose_db4。
      (0) 若第 159 段的非 filter-target 槽 < 2，把该段第一条 filter target 与第 151 段最后一个非 target 槽交换（同种子四个 P4 臂相同）；
      (1) 1 条 db_list_tables（固定 database-train-db_list_tables-000）替换 token 最接近 272 的 1 条 Database 背景条目；
      (2) target_median_natural 只留编号最小的 1 条，其余换成 token 最接近的 Python 背景条目（stats_mean / stats_std）；
      (3) list_tables 与 median 换到 95 / 127 / 159 段（与目标槽上的条目交换，其它不动）。
  P4_LT2mid ：同上，但 2 条 list_tables（-000、-001）都在 127 段；127 段只有 2 个槽，median 放 135 段最后一槽。
  db2_early ：源 dose_db2，原 2 条 filter target 换到 127 段两个槽（after 6/6），条目集合与 token 不变。
  db4_early ：源 dose_db4，原 4 条 filter target 换到 127、127、135、135 段（after 6/6/5/5），条目集合与 token 不变。
另：基线（只评 list_tables 改写探针）：T0 = stage_02_database；prefix = stage_03_python adapter + E4 step-80 prefix 参数。
只写 data_ext_p4_forget_timing/ 与 runs_ext_p4_forget_timing/。
用法：python -m fac_tinyagent.p4_forget_timing --phase build|show|dry|queue|summarize
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils import ensure_dir, read_json, read_jsonl, sha256_file, write_json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data_ext_p4_forget_timing"
RUNS = ROOT / "runs_ext_p4_forget_timing"
EVAL = RUNS / "evaluation"
STOP = ROOT / "logs_ext" / "p4_20261114.stop"
PREREG = "E3B2_PREREG_AMEND_20261114_p4_forget_timing_ZH.md"
SEEDS = [20261108, 20261109, 20261110]
SRC = {"P4_early": "dose_db4", "P4_mid": "dose_db4", "P4_late": "dose_db4", "P4_LT2mid": "dose_db4",
       "db2_early": "dose_db2", "db4_early": "dose_db4"}
ARMS = list(SRC)                    # 队列顺序：P4 四臂先，再 db2_early、db4_early
P4ARMS = ARMS[:4]
POSITIONS = [87, 95, 103, 111, 119, 127, 135, 143, 151, 159]
ACC, BETA1 = 8, 0.9
STEPS_EXPECTED = 23
TKEY = "target_db_filter_top"
LTKEY = "db_list_tables"
MNKEY = "target_median_natural"
LT_IDS = ["database-train-db_list_tables-000", "database-train-db_list_tables-001"]
PY_BG = ("python-train-stats_mean-", "python-train-stats_std-")
SUITES = ["lt_probe", "p2_database", "natv2_python", "natv2_database", "v3fix"]
PROBE = DATA / "probe" / "list_tables_probe.jsonl"


def log(m: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), m, flush=True)


def label(seed: int, arm: str) -> str:
    return "A_seed%d_%s" % (seed, arm)


def ckpt(seed: int, arm: str) -> Path:
    return RUNS / "branches" / label(seed, arm) / "checkpoint"


def src_plan(seed: int, arm: str) -> Path:
    return ROOT / "data_ext_e3" / "plans" / ("A_seed%d_%s.json" % (seed, SRC[arm]))


def seg_bounds(n: int) -> List[range]:
    return [range(i * n // len(POSITIONS), (i + 1) * n // len(POSITIONS)) for i in range(len(POSITIONS))]


def seg(pos: int, n: int) -> List[int]:
    return list(seg_bounds(n)[POSITIONS.index(pos)])


def segment_of(index: int, n: int) -> int:
    for i, r in enumerate(seg_bounds(n)):
        if index in r:
            return i
    raise ValueError(index)


def mom(after: List[int]) -> float:
    return sum(1 - BETA1 ** a for a in after)


def kind_of(eid: str) -> Optional[str]:
    if TKEY in eid:
        return "filter"
    if LTKEY in eid:
        return "list_tables"
    if MNKEY in eid:
        return "median_nat"
    return None


# ------------------------------------------------------------------ probe (CPU)
PROBE_PROMPTS = [
    "Which tables exist in the database? Return a JSON list.",
    "List the names of all tables in the database as a JSON list.",
    "What are the table names in this database? Return a JSON list.",
    "Show me every table in the database. Return a JSON list of names.",
    "Give me the list of tables in the database. Return a JSON list.",
    "Name all the tables that the database contains. Return a JSON list.",
    "Which tables can I query in this database? Return a JSON list.",
    "Enumerate the tables in the database. Return a JSON list.",
    "What tables does the database have? Return a JSON list.",
    "Return the names of the database tables as a JSON list.",
    "I need the full list of table names in the database. Return a JSON list.",
    "How are the tables in the database named? Return a JSON list.",
    "List all available tables. Return a JSON list.",
    "Tell me which tables are in the database. Return a JSON list.",
    "Get the table names from the database. Return a JSON list.",
    "What tables are stored in the database? Return a JSON list.",
    "Please list the database's tables. Return a JSON list.",
    "Which tables are present in the database? Return a JSON list.",
    "Before writing any query, list every table available in the database. Return a JSON list.",
    "Look up the names of all tables in the database. Return a JSON list.",
    "What tables can be found in the read-only database? Return a JSON list.",
    "List the tables of the read-only database. Return a JSON list.",
    "Which tables does the read-only database contain? Return a JSON list.",
    "Show the table names in the read-only database. Return a JSON list.",
]


def build_probe() -> Dict[str, Any]:
    test = [r for r in read_jsonl(ROOT / "data_phase2" / "database" / "test.jsonl") if "db_list_tables_test" in r["episode_id"]]
    tmpl = test[0]
    train_prompts = {r["prompt"] for f in ("train", "val", "test") for r in read_jsonl(ROOT / "data_phase2" / "database" / ("%s.jsonl" % f))}
    train_prompts |= {r["prompt"] for r in read_jsonl(ROOT / "data_ext_e4" / "pool" / "database.jsonl")}
    rows = []
    for i, p in enumerate(PROBE_PROMPTS):
        if p in train_prompts:
            raise SystemExit("probe prompt duplicates an existing prompt: %s" % p)
        r = copy.deepcopy(tmpl)
        r["episode_id"] = "database-probe-db_list_tables_probe-%03d" % i
        r["prompt"] = p
        r["split"] = "probe_p4"
        r["template_id"] = "db_list_tables_probe_p4" + ("_readonly" if "read-only" in p else "")
        r["messages"][1]["content"] = p
        r["data_signature"] = hashlib.sha256(json.dumps([r["messages"], r["expected_tool"], r["expected_arguments"],
                                                          r["expected_observation"]], sort_keys=True).encode()).hexdigest()
        rows.append(r)
    assert len({r["prompt"] for r in rows}) == len(rows)
    ensure_dir(PROBE.parent)
    with open(PROBE, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return {"path": str(PROBE.relative_to(ROOT)), "n": len(rows), "sha256": sha256_file(PROBE),
            "n_mentions_read_only": sum("read-only" in p for p in PROBE_PROMPTS),
            "template_from": tmpl["episode_id"]}


def suite_rows(name: str):
    from .p1_run import suite_rows as base, DB_PATH, CAL_PATH
    if name == "lt_probe":
        man = read_json(DATA / "manifest.json")
        if sha256_file(PROBE) != man["probe"]["sha256"]:
            raise SystemExit("probe file changed")
        return read_jsonl(PROBE), str(DB_PATH), str(CAL_PATH), man["probe"]["sha256"]
    return base(name)


# ------------------------------------------------------------------ plans
def source_after_by_index(seed: int, source_arm: str, items: List[Dict[str, Any]]) -> List[int]:
    from . import p1_run as P
    ck = P.ckpt_path(seed, source_arm)
    L = read_jsonl(ck / "training_log.jsonl")
    total = read_json(ck / "train_summary.json")["optimizer_steps"]
    rep = sorted([x for x in L if x["kind"] != "new"], key=lambda x: x["microstep"])
    if [x["episode_id"] for x in rep] != [i["episode_id"] for i in items]:
        raise SystemExit("%s %d: source training order != plan order" % (source_arm, seed))
    if total != STEPS_EXPECTED:
        raise SystemExit("%s %d: source steps %d" % (source_arm, seed, total))
    return [total - ((x["microstep"] - 1) // ACC + 1) + 1 for x in rep]


def token_cache() -> Dict[str, Dict[str, Any]]:
    """已冻结 E3 计划里出现过的条目 -> (family,row_index,tokens)。新换入的条目只从这里取，运行期 override 再逐条核对 pool。"""
    c = {}
    for f in sorted((ROOT / "data_ext_e3" / "plans").glob("*.json")):
        for it in read_json(f)["items"]:
            k = it["episode_id"]
            v = {kk: it[kk] for kk in ("family", "row_index", "episode_id", "input_tokens", "supervised_tokens", "truncated", "target")}
            if k in c and c[k] != v:
                raise SystemExit("token cache conflict %s" % k)
            c[k] = v
    return c


def swap(items, i, j, log_):
    if i != j:
        log_.append({"from_index": i, "to_index": j, "moved": items[i]["episode_id"], "displaced": items[j]["episode_id"]})
        items[i], items[j] = items[j], items[i]


def recompute_meta(q: Dict[str, Any]) -> None:
    it = q["items"]
    q["actual_input_tokens"] = sum(x["input_tokens"] for x in it)
    q["actual_supervised_tokens"] = sum(x["supervised_tokens"] for x in it)
    fams = sorted({x["family"] for x in it} | set(q.get("actual_tokens_by_family", {})))
    q["actual_tokens_by_family"] = {f: sum(x["input_tokens"] for x in it if x["family"] == f) for f in fams}
    q["samples_by_family"] = {f: sum(1 for x in it if x["family"] == f) for f in fams}
    q["target_samples_by_family"] = {f: sum(1 for x in it if x["family"] == f and x.get("target")) for f in fams}
    q["target_actual_input_tokens"] = sum(x["input_tokens"] for x in it if x.get("target"))
    q["actual_target_fraction"] = q["target_actual_input_tokens"] / q["actual_input_tokens"]
    q["unused_input_tokens"] = q["budget_input_tokens"] - q["actual_input_tokens"]
    q["unused_fraction"] = q["unused_input_tokens"] / q["budget_input_tokens"]
    q["within_one_percent_of_budget"] = abs(q["unused_input_tokens"]) <= 0.01 * q["budget_input_tokens"]


def make_plan(seed: int, arm: str) -> Dict[str, Any]:
    src = src_plan(seed, arm)
    p = read_json(src)
    items0 = p["items"]
    n = len(items0)
    after_idx = source_after_by_index(seed, SRC[arm], items0)
    q = copy.deepcopy(p)
    it = q["items"]
    ops: List[Dict[str, Any]] = []
    repl: List[Dict[str, Any]] = []
    tix = lambda: [i for i, x in enumerate(it) if TKEY in x["episode_id"]]
    if arm in ("db2_early", "db4_early"):
        dest = seg(127, n) if arm == "db2_early" else seg(127, n) + seg(135, n)
        want = {"db2_early": 2, "db4_early": 4}[arm]
        if len(tix()) != want or len(dest) != want:
            raise SystemExit("%s %d: targets %d dest %s" % (arm, seed, len(tix()), dest))
        move = [i for i in tix() if i not in dest]
        free = [j for j in dest if j not in tix()]
        for i, j in zip(sorted(move), sorted(free)):
            swap(it, i, j, ops)
        assert sorted(tix()) == sorted(dest)
    else:
        cache = token_cache()
        # (0) 让第 159 段至少有 2 个非 filter 槽
        s159, s151 = seg(159, n), seg(151, n)
        if sum(1 for i in s159 if TKEY not in it[i]["episode_id"]) < 2:
            a = min(i for i in s159 if TKEY in it[i]["episode_id"])
            b = max(i for i in s151 if TKEY not in it[i]["episode_id"])
            swap(it, a, b, ops)
        # (1) 换入 list_tables
        k_lt = 2 if arm == "P4_LT2mid" else 1
        for lid in LT_IDS[:k_lt]:
            cand = sorted([i for i, x in enumerate(it) if x["family"] == "database" and kind_of(x["episode_id"]) is None],
                          key=lambda i: (abs(it[i]["input_tokens"] - cache[lid]["input_tokens"]), i))
            i = cand[0]
            repl.append({"index": i, "removed": it[i]["episode_id"], "removed_tokens": it[i]["input_tokens"],
                         "added": lid, "added_tokens": cache[lid]["input_tokens"]})
            it[i] = dict(cache[lid])
        # (2) median 只留 1 条
        mn = sorted([i for i, x in enumerate(it) if MNKEY in x["episode_id"]], key=lambda i: it[i]["episode_id"])
        if not mn:
            raise SystemExit("no target_median_natural in base %d" % seed)
        in_plan = {x["episode_id"] for x in it}
        for i in mn[1:]:
            cand = sorted([v for k, v in cache.items() if k.startswith(PY_BG) and k not in in_plan],
                          key=lambda v: (abs(v["input_tokens"] - it[i]["input_tokens"]), v["row_index"]))
            v = cand[0]
            repl.append({"index": i, "removed": it[i]["episode_id"], "removed_tokens": it[i]["input_tokens"],
                         "added": v["episode_id"], "added_tokens": v["input_tokens"]})
            in_plan.add(v["episode_id"])
            it[i] = dict(v)
        # (3) 放位置
        lts = sorted([i for i, x in enumerate(it) if LTKEY in x["episode_id"]], key=lambda i: it[i]["episode_id"])
        mni = [i for i, x in enumerate(it) if MNKEY in x["episode_id"]]
        assert len(lts) == k_lt and len(mni) == 1, (lts, mni)
        if arm == "P4_LT2mid":
            plan_dest = list(zip(lts, seg(127, n))) + [(mni[0], seg(135, n)[-1])]
        else:
            pos = {"P4_early": 95, "P4_mid": 127, "P4_late": 159}[arm]
            slots = [i for i in seg(pos, n) if TKEY not in it[i]["episode_id"]]
            if len(slots) < 2:
                raise SystemExit("%s %d: not enough free slots at %d" % (arm, seed, pos))
            plan_dest = [(lts[0], slots[-2]), (mni[0], slots[-1])]
        eids = [it[i]["episode_id"] for i, _ in plan_dest]
        for eid, (_, d) in zip(eids, plan_dest):
            cur = [i for i, x in enumerate(it) if x["episode_id"] == eid]
            cur = [i for i in cur if i not in [dd for _, dd in plan_dest][:eids.index(eid)]] or cur
            if TKEY in it[d]["episode_id"]:
                raise SystemExit("destination holds a filter target")
            swap(it, cur[0], d, ops)
        for eid, (_, d) in zip(eids, plan_dest):
            assert it[d]["episode_id"] == eid, (eid, d, it[d]["episode_id"])
    recompute_meta(q)
    pred = []
    for i, x in enumerate(it):
        k = kind_of(x["episode_id"])
        if k:
            pred.append({"kind": k, "id": x["episode_id"].split("-train-")[1], "index": i,
                         "position": POSITIONS[segment_of(i, n)], "after": after_idx[i]})
    by = lambda k: [t["after"] for t in pred if t["kind"] == k]
    q["p4_amend"] = {"arm": arm, "source_arm": SRC[arm], "source_plan": str(src.relative_to(ROOT)), "source_sha256": sha256_file(src),
                     "n_items": n, "swaps": ops, "replacements": repl, "tracked_predicted": pred,
                     "sum_after_pred": {k: sum(by(k)) for k in ("filter", "list_tables", "median_nat")},
                     "mom_filter_pred": round(mom(by("filter")), 4),
                     "budget_input_tokens": q["budget_input_tokens"], "source_actual_input_tokens": p["actual_input_tokens"],
                     "actual_input_tokens": q["actual_input_tokens"],
                     "token_deviation_vs_source": q["actual_input_tokens"] - p["actual_input_tokens"],
                     "token_deviation_vs_budget": q["actual_input_tokens"] - q["budget_input_tokens"],
                     "prereg": PREREG}
    assert len(it) == n and q["budget_input_tokens"] == p["budget_input_tokens"]
    if arm in ("db2_early", "db4_early"):
        assert sorted(x["episode_id"] for x in it) == sorted(x["episode_id"] for x in items0)
        assert q["actual_input_tokens"] == p["actual_input_tokens"]
    return q


def build() -> None:
    if (DATA / "manifest.json").exists():
        raise SystemExit("data_ext_p4_forget_timing/manifest.json exists; refusing to overwrite")
    from . import p1_run as P
    ensure_dir(DATA / "plans")
    probe = build_probe()
    summ = {}
    for s in SEEDS:
        for arm in ARMS:
            q = make_plan(s, arm)
            if json.dumps(make_plan(s, arm), sort_keys=True) != json.dumps(q, sort_keys=True):
                raise SystemExit("not deterministic")
            base = read_json(P.ckpt_path(s, SRC[arm]) / "train_summary.json")
            q["p4_amend"]["base_optimizer_steps"] = base["optimizer_steps"]
            write_json(DATA / "plans" / ("A_seed%d_%s.json" % (s, arm)), q)
            summ["%d %s" % (s, arm)] = q["p4_amend"]
    write_json(DATA / "manifest.json", {
        "created_by": "fac_tinyagent/p4_forget_timing.py", "created": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "prereg": PREREG + " (written before training)", "arms": ARMS, "seeds": SEEDS, "source_arms": SRC,
        "steps_expected": STEPS_EXPECTED, "suites": SUITES, "probe": probe, "summary": summ,
        "budget_deviation": {k: {"vs_source": v["token_deviation_vs_source"], "vs_budget": v["token_deviation_vs_budget"],
                                 "pct_of_budget": round(100.0 * v["token_deviation_vs_budget"] / v["budget_input_tokens"], 2)}
                             for k, v in summ.items()},
        "plan_files": {p.name: sha256_file(p) for p in sorted((DATA / "plans").glob("*.json"))}})
    log("p4 plans + probe frozen")


def show_line(s: int, arm: str, a: Dict[str, Any]) -> str:
    f = lambda k: ["%s@%d/%d" % (t["id"].rsplit("-", 1)[1] if k == "filter" else t["id"], t["position"], t["after"])
                   for t in a["tracked_predicted"] if t["kind"] == k]
    return "%d %-10s filter=%s Σ%d | list_tables=%s Σ%d | median_nat=%s | tokens %d (dev vs budget %+d) | repl=%s" % (
        s, arm, f("filter"), a["sum_after_pred"]["filter"], f("list_tables"), a["sum_after_pred"]["list_tables"], f("median_nat"),
        a["actual_input_tokens"], a["token_deviation_vs_budget"],
        ["%s(%d)->%s(%d)" % (r["removed"].split("-train-")[1], r["removed_tokens"], r["added"].split("-train-")[1], r["added_tokens"])
         for r in a["replacements"]])


def dry() -> None:
    man = read_json(DATA / "manifest.json")
    for name, h in man["plan_files"].items():
        assert sha256_file(DATA / "plans" / name) == h, name
    assert sha256_file(PROBE) == man["probe"]["sha256"]
    pools = {f: read_jsonl(ROOT / "data_ext_e4" / "pool" / (f + ".jsonl")) for f in ("database", "file", "python")}
    for s in SEEDS:
        for arm in ARMS:
            q = read_json(DATA / "plans" / ("A_seed%d_%s.json" % (s, arm)))
            p = read_json(src_plan(s, arm))
            assert q["budget_input_tokens"] == p["budget_input_tokens"] and len(q["items"]) == len(p["items"])
            assert q["actual_input_tokens"] == sum(i["input_tokens"] for i in q["items"])
            assert q["p4_amend"]["base_optimizer_steps"] == STEPS_EXPECTED
            for it in q["items"]:
                r = pools[it["family"]][it["row_index"]]
                assert r["episode_id"] == it["episode_id"], (it, r["episode_id"])
            print(show_line(s, arm, q["p4_amend"]))
    print("DRY OK")


# ------------------------------------------------------------------ safety
def check_safe() -> None:
    if STOP.exists():
        raise SystemExit("stop flag %s present" % STOP)
    from .p0_run import refuse_if_game
    refuse_if_game()


# ------------------------------------------------------------------ train
def prep_prefix(seed: int) -> Path:
    src, dst = ROOT / "runs_ext_e4" / "prefixes" / ("A_seed%d" % seed), RUNS / "prefixes" / ("A_seed%d" % seed)
    m = read_json(src / "manifest.json")
    if (dst / "manifest.json").exists():
        if sha256_file(dst / "training_state.pt") != m["state_sha256"] or read_json(dst / "manifest.json") != m:
            raise SystemExit("p4 prefix copy differs for %d" % seed)
        return dst
    if sha256_file(src / "training_state.pt") != m["state_sha256"]:
        raise SystemExit("E4 prefix %d hash mismatch" % seed)
    ensure_dir(dst)
    tmp = dst / "training_state.pt.tmp"
    shutil.copyfile(src / "training_state.pt", tmp)
    if sha256_file(tmp) != m["state_sha256"]:
        raise SystemExit("prefix copy hash mismatch %d" % seed)
    tmp.rename(dst / "training_state.pt")
    shutil.copyfile(src / "manifest.json", dst / "manifest.json")
    return dst


def tracked_timing(ck: Path) -> Dict[str, Any]:
    L = read_jsonl(ck / "training_log.jsonl")
    total = read_json(ck / "train_summary.json")["optimizer_steps"]
    tr = []
    for x in L:
        if x.get("kind") == "new":
            continue
        k = kind_of(x["episode_id"])
        if k:
            tr.append({"kind": k, "id": x["episode_id"].split("-train-")[1], "position": x["new_position"],
                       "after": total - ((x["microstep"] - 1) // ACC + 1) + 1})
    by = lambda k: [t["after"] for t in tr if t["kind"] == k]
    return {"tracked": tr, "total_steps": total, "sum_after": {k: sum(by(k)) for k in ("filter", "list_tables", "median_nat")},
            "n": {k: len(by(k)) for k in ("filter", "list_tables", "median_nat")}, "mom_filter": round(mom(by("filter")), 4)}


def train(seed: int, arm: str) -> Dict[str, Any]:
    from . import e3_data as D
    from .e3_run import guards, v3_leakage_guard
    from .e3_train import train_replay_stage_e3
    from .e4_run import CALENDAR_PATH, DB_PATH, OLD, leakage_guard, start_adapter
    from .replay_study import config_for
    man = read_json(DATA / "manifest.json")
    for name, h in man["plan_files"].items():
        if sha256_file(DATA / "plans" / name) != h:
            raise SystemExit("p4 plan changed: %s" % name)
    guards()
    frozen = read_json(DATA / "plans" / ("A_seed%d_%s.json" % (seed, arm)))
    run = ckpt(seed, arm).parent
    if (ckpt(seed, arm) / "train_summary.json").exists():
        log("skip train %s" % run.name)
        return read_json(ckpt(seed, arm) / "train_summary.json")
    if run.exists():
        aside = run.parent / (run.name + "_partial_%d" % int(time.time()))
        log("moving partial run aside: %s" % aside)
        shutil.move(str(run), str(aside))
    pdir = prep_prefix(seed)
    target_ids = read_json(ROOT / "data_ext_e4" / "manifest.json")["target_ids"]
    config = config_for("A", seed, batch_size=32)
    stage = dict(config["stages"][4], index=4)
    new_path = str(ROOT / "data_phase2" / "calendar" / "train.jsonl")
    probes = {f: str(ROOT / "data_ext_monitor_v2" / (f + ".jsonl")) for f in OLD}
    pools = {f: str(ROOT / "data_ext_e4" / "pool" / (f + ".jsonl")) for f in OLD}
    rows = read_jsonl(new_path) + [r for p in pools.values() for r in read_jsonl(p)] \
        + [r for p in probes.values() for r in read_jsonl(p)]
    leakage_guard(rows)
    v3_leakage_guard(rows)

    def override(pools, extra_pools, budget, seed):  # noqa
        if budget != frozen["budget_input_tokens"]:
            raise RuntimeError("runtime budget %d != frozen %d" % (budget, frozen["budget_input_tokens"]))
        idx = {(f, r["row_index"], r["episode_id"]): r for f, rs in pools.items() for r in rs}
        for it in frozen["items"]:
            r = idx.get((it["family"], it["row_index"], it["episode_id"]))
            if r is None or r["input_tokens"] != it["input_tokens"] or r["supervised_tokens"] != it["supervised_tokens"]:
                raise RuntimeError("frozen p4 item does not match runtime pool: %s" % it["episode_id"])
        log("p4 plan %s items %d tracked %s" % (arm, len(frozen["items"]),
            [(t["kind"], t["position"], t["after"]) for t in frozen["p4_amend"]["tracked_predicted"]]))
        return copy.deepcopy(frozen)

    log("TRAIN %s" % run.name)
    s = train_replay_stage_e3(
        config=config, stage=stage, train_path=new_path, old_train_paths=pools, probe_paths=probes,
        previous_adapter=str(start_adapter(seed)), output_dir=str(ckpt(seed, arm)), db_path=str(DB_PATH),
        calendar_path=str(CALENDAR_PATH), mode="targeted", replay_ratio=0.10, uniform_floor=0.2,
        prefix_dir=str(pdir), target_ids=target_ids, target_fraction=D.TF25,
        target_family_weights={f: 1.0 / len(OLD) for f in OLD},
        plan_override=override, extra_replay_family=None, require_prefix_reuse=True)
    if s.get("optimizer_steps") != STEPS_EXPECTED:
        raise SystemExit("optimizer steps %s != %d" % (s.get("optimizer_steps"), STEPS_EXPECTED))
    tt = tracked_timing(ckpt(seed, arm))
    pred = frozen["p4_amend"]["tracked_predicted"]
    key = lambda L: sorted((t["kind"], t["position"], t["after"]) for t in L)
    if key(tt["tracked"]) != key(pred):
        raise SystemExit("actual tracked timing %s != predicted %s" % (key(tt["tracked"]), key(pred)))
    write_json(run / "p4_meta.json", {"arm": arm, "seed": seed,
                                      "plan_sha256": sha256_file(DATA / "plans" / ("A_seed%d_%s.json" % (seed, arm))),
                                      "prefix_state_sha256": s.get("shared_prefix_state_sha256"),
                                      "optimizer_steps": s.get("optimizer_steps"), "replay_input_tokens": s.get("replay_input_tokens"),
                                      "tracked_timing": tt, "finished": time.strftime("%Y-%m-%d %H:%M:%S %z")})
    log("TRAIN done %s steps=%s replay_tokens=%s sum_after=%s" % (run.name, s.get("optimizer_steps"),
        s.get("replay_input_tokens"), tt["sum_after"]))
    return s


# ------------------------------------------------------------------ eval
def _load_midpoint(model, prefix: Path) -> Dict[str, Any]:
    import torch
    state = torch.load(prefix / "training_state.pt", map_location="cpu", weights_only=False)
    params = dict(model.named_parameters())
    missing = [n for n in state["parameters"] if n not in params]
    if missing:
        raise RuntimeError("prefix parameters not found in eval model: %s" % missing[:3])
    with torch.no_grad():
        for name, value in state["parameters"].items():
            params[name].copy_(value.to(params[name].device, dtype=params[name].dtype))
    digest = hashlib.sha256()
    for name in sorted(state["parameters"]):
        digest.update(name.encode("utf-8"))
        digest.update(params[name].detach().contiguous().view(torch.uint8).cpu().numpy().tobytes())
    return {"n_params": len(state["parameters"]), "hash_matches_prefix": digest.hexdigest() == state["parameter_hash"]}


def _eval(seed: int, name: str, adapter: Path, out: Path, suites: List[str], prefix: Optional[Path] = None) -> None:
    todo = [s for s in suites if not (out / s / "stage_report.json").exists()]
    if not todo:
        log("skip eval %s" % name)
        return
    check_safe()
    from .replay_study import config_for
    from .sft.evaluate import evaluate_family, free_model, load_eval_model
    config = config_for("A", seed, batch_size=1)
    config["evaluation"]["batch_size"] = 1
    t_all = time.time()
    log("EVAL %s suites=%s" % (name, todo))
    model, tok = load_eval_model(config, str(adapter))
    extra = {}
    if prefix is not None:
        extra = _load_midpoint(model, prefix)
        log("  prefix params loaded %s" % extra)
        if not extra["hash_matches_prefix"]:
            log("  WARN prefix parameter hash mismatch after load (dtype cast?)")
    stage = {"name": "P4_B1_" + name, "index": 4, "adapter": str(adapter)}
    try:
        for s in todo:
            check_safe()
            rows, db, cal, h = suite_rows(s)
            t0 = time.time()
            rep = evaluate_family(model, tok, rows, config, stage, out / s, db, cal)
            if rep["evaluation_protocol"]["batch_size"] != 1:
                raise SystemExit("protocol is not B1")
            write_json(out / s / "p4_meta.json", {"suite": s, "rows_sha256": h, "n": len(rows), "adapter": str(adapter),
                                                 "prefix": str(prefix) if prefix else None, "prefix_load": extra,
                                                 "protocol": "Protocol-B1", "seconds": round(time.time() - t0, 1),
                                                 "finished": time.strftime("%Y-%m-%d %H:%M:%S %z")})
            log("  done %s %s n=%d %.1fs" % (name, s, len(rows), time.time() - t0))
    finally:
        free_model(model)
    log("EVAL done %s in %.1fs" % (name, time.time() - t_all))


def baselines() -> None:
    from .e4_run import start_adapter
    for s in SEEDS:
        _eval(s, "A_seed%d_T0_stage_02" % s, ROOT / "runs_phase2" / ("A_seed%d" % s) / "checkpoints" / "stage_02_database",
              EVAL / ("A_seed%d_T0_stage_02" % s), ["lt_probe"])
        try:
            _eval(s, "A_seed%d_prefix_step80" % s, start_adapter(s), EVAL / ("A_seed%d_prefix_step80" % s), ["lt_probe"],
                  prefix=prep_prefix(s))
        except RuntimeError as exc:
            log("WARN prefix baseline failed for %d: %r (queue continues)" % (s, exc))
        try:
            summarize()
        except Exception as exc:
            log("WARN summarize failed: %r" % exc)


def queue() -> None:
    check_safe()
    baselines()
    for arm in ARMS:
        for s in SEEDS:
            check_safe()
            train(s, arm)
            _eval(s, label(s, arm), ckpt(s, arm), EVAL / label(s, arm), SUITES)
            try:
                summarize()
            except Exception as exc:
                log("WARN summarize failed: %r" % exc)
    log("QUEUE COMPLETE")


# ------------------------------------------------------------------ summary (CPU)
TIE = 0.10
PRED = {"db2_early": {"saturation_cap5": {20261108: 0.958, 20261109: 0.958, 20261110: 0.958},
                      "table_cap5": {20261108: 0.627, 20261109: 0.984, 20261110: 0.627}},
        "db4_early": {"saturation_cap5": {20261108: 0.98, 20261109: 0.98, 20261110: 0.98},
                      "table_cap5": {20261108: 0.984, 20261109: 0.984, 20261110: 0.984}}}


def _score(path: Path, stem: Optional[str] = None):
    if not path.exists():
        return None
    r = read_jsonl(path)
    if stem:
        r = [x for x in r if stem in x["episode_id"]]
    if not r:
        return None
    n = len(r)
    return {"n": n, "joint": sum(bool(x["joint_success"]) for x in r) / n, "tool": sum(bool(x["tool_correct"]) for x in r) / n,
            "args": sum(bool(x["arguments_correct"]) for x in r) / n, "final": sum(bool(x["final_correct"]) for x in r) / n}


def summarize() -> None:
    rows = []
    for s in SEEDS:
        for nm in ("T0_stage_02", "prefix_step80"):
            d = EVAL / ("A_seed%d_%s" % (s, nm))
            sc = _score(d / "lt_probe" / "results.jsonl")
            if sc:
                rows.append({"seed": s, "arm": nm, "lt_probe": sc})
        for arm in ARMS:
            ck = ckpt(s, arm)
            if not (ck / "train_summary.json").exists():
                continue
            ev = EVAL / label(s, arm)
            tt = tracked_timing(ck)
            r = {"seed": s, "arm": arm, "timing": tt}
            r["lt_probe"] = _score(ev / "lt_probe" / "results.jsonl")
            r["p2_list_tables"] = _score(ev / "p2_database" / "results.jsonl", "db_list_tables_test")
            r["p2_database"] = _score(ev / "p2_database" / "results.jsonl")
            r["median_nat"] = _score(ev / "natv2_python" / "results.jsonl")
            r["filter_top"] = _score(ev / "natv2_database" / "results.jsonl")
            r["v3fix"] = _score(ev / "v3fix" / "results.jsonl")
            rows.append(r)
    get = {(r["seed"], r["arm"]): r for r in rows}
    J = lambda s, a, k: (get.get((s, a), {}).get(k) or {}).get("joint")

    def pair(a, b, k, seeds=SEEDS):
        d = [None if J(s, a, k) is None or J(s, b, k) is None else J(s, a, k) - J(s, b, k) for s in seeds]
        done = [x for x in d if x is not None]
        return {"per_seed": d, "mean": statistics.mean(done) if done else None, "n_pos": sum(x > 1e-9 for x in done),
                "n_neg": sum(x < -1e-9 for x in done), "n_seeds": len(done)}
    pairs = {"early−late lt_probe": pair("P4_early", "P4_late", "lt_probe"), "mid−late lt_probe": pair("P4_mid", "P4_late", "lt_probe"),
             "early−mid lt_probe": pair("P4_early", "P4_mid", "lt_probe"), "LT2mid−mid lt_probe": pair("P4_LT2mid", "P4_mid", "lt_probe"),
             "LT2mid−early lt_probe": pair("P4_LT2mid", "P4_early", "lt_probe"),
             "late−early median_nat (08,10)": pair("P4_late", "P4_early", "median_nat", [20261108, 20261110]),
             "late−mid median_nat (08,10)": pair("P4_late", "P4_mid", "median_nat", [20261108, 20261110]),
             "db4_early−db2_early filter": pair("db4_early", "db2_early", "filter_top")}
    v = {}
    pe, pm = pairs["early−late lt_probe"], pairs["mid−late lt_probe"]
    if pe["n_seeds"] == 3 and pm["n_seeds"] == 3:
        rec = lambda a: [J(s, a, "lt_probe") for s in SEEDS]
        v["list_tables_timing"] = ("支持（early、mid 都高于 late，三种子方向一致）" if pe["n_pos"] == 3 and pm["n_pos"] == 3 else
                                   "部分支持（early 高于 late 三种子一致，mid 不一致）" if pe["n_pos"] == 3 else
                                   "不支持（early 没有在三种子上都高于 late）")
        v["list_tables_recovered"] = {a: rec(a) for a in P4ARMS}
    pl = pairs["LT2mid−mid lt_probe"]; px = pairs["LT2mid−early lt_probe"]
    if pl["n_seeds"] == 3 and px["n_seeds"] == 3:
        v["count_vs_exposure"] = ("LT2mid > mid 且 ≈ early：恢复跟累计暴露走（Σ12≈Σ11），不是条数" if pl["n_pos"] == 3 and abs(px["mean"]) <= TIE else
                                  "LT2mid > mid 且 > early：第二条经验在暴露之外还有额外作用" if pl["n_pos"] == 3 and px["n_pos"] == 3 else
                                  "LT2mid ≈ mid：第二条同模式经验没有帮助" if abs(pl["mean"]) <= TIE else "不一致")
    pmn = pairs["late−early median_nat (08,10)"]
    if pmn["n_seeds"] == 2:
        v["median_late_not_worse"] = ("成立（late − early ≥ −0.10，种子 08、10）" if all(x >= -TIE for x in pmn["per_seed"]) else
                                      "不成立（至少一个遗忘种子上 late 比 early 低超过 0.10）")
    pv = {}
    for arm in ("db2_early", "db4_early"):
        obs = {s: J(s, arm, "filter_top") for s in SEEDS}
        if all(x is not None for x in obs.values()):
            pv[arm] = {"observed": obs, "observed_mean": statistics.mean(obs.values())}
            for m, pr in PRED[arm].items():
                pv[arm][m] = {"pred_mean": statistics.mean(pr.values()), "mae": statistics.mean(abs(obs[s] - pr[s]) for s in SEEDS)}
    v["prediction_check"] = pv
    out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S %z"), "prereg": PREREG, "rows": rows, "pairs": pairs, "verdicts": v}
    ensure_dir(RUNS)
    write_json(RUNS / "summary.json", out)
    f3 = lambda d: "—" if not d else "%.3f" % d["joint"]
    sg = lambda x: "—" if x is None else "%+.3f" % x
    md = ["# P4 真遗忘时机 + 预测验证臂：汇总（Protocol-B1）", "", "生成：%s。预注册：`%s`。" % (out["generated"], PREREG), "",
          "## 1. 探针基线（list_tables 改写探针 24 题）", "", "| 种子 | 状态 | Joint | tool / args / final |", "|---|---|---|---|"]
    for r in rows:
        if r["arm"] in ("T0_stage_02", "prefix_step80"):
            d = r["lt_probe"]
            md.append("| %s | %s | %.3f | %.3f / %.3f / %.3f |" % (str(r["seed"])[-2:], r["arm"], d["joint"], d["tool"], d["args"], d["final"]))
    md += ["", "## 2. 逐种子", "",
           "| 种子 | 臂 | list_tables 位置/after | median 位置/after | filter Σafter | 探针 24 | p2 list_tables 6 | p2 DB 30 | median nat 30 | filter_top 30（args/final） | v3fix |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in SEEDS:
        for a in ARMS:
            r = get.get((s, a))
            if not r:
                continue
            t = r["timing"]["tracked"]
            fmt = lambda k: "；".join("%d/%d" % (x["position"], x["after"]) for x in t if x["kind"] == k) or "—"
            ft = r["filter_top"]
            md.append("| %s | %s | %s | %s | %d | %s | %s | %s | %s | %s | %s |" % (
                str(s)[-2:], a, fmt("list_tables"), fmt("median_nat"), r["timing"]["sum_after"]["filter"], f3(r["lt_probe"]),
                f3(r["p2_list_tables"]), f3(r["p2_database"]), f3(r["median_nat"]),
                "—" if not ft else "%.3f（%.3f/%.3f）" % (ft["joint"], ft["args"], ft["final"]), f3(r["v3fix"])))
    md += ["", "## 3. 配对差（同种子）", "", "| 对比 | 各种子 | 均值 | 正/负 |", "|---|---|---|---|"]
    for k, p in pairs.items():
        md.append("| %s | %s | %s | %d/%d |" % (k, " / ".join(sg(x) for x in p["per_seed"]), sg(p["mean"]), p["n_pos"], p["n_neg"]))
    md += ["", "## 4. 预注册判定", ""]
    for k, x in v.items():
        md.append("- %s：%s" % (k, json.dumps(x, ensure_ascii=False)))
    (RUNS / "summary_tables_ZH.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log("summary written")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["build", "show", "dry", "queue", "summarize"], required=True)
    a = ap.parse_args()
    if a.phase == "build":
        build()
    elif a.phase == "dry":
        dry()
    elif a.phase == "queue":
        queue()
    elif a.phase == "summarize":
        summarize()
    else:
        for s in SEEDS:
            for arm in ARMS:
                print(show_line(s, arm, make_plan(s, arm)["p4_amend"]))


if __name__ == "__main__":
    main()
