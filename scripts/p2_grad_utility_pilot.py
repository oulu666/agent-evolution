#!/usr/bin/env python3
"""P2 经验价值梯度打分 pilot（只新增文件；GPU 只做前向+反向，不更新任何参数、不保存模型）。

问题：在复习开始前的模型状态上，「候选经验的训练损失梯度」与「薄弱模式探针损失梯度」的方向一致程度
（余弦 / 点积，只在可训练 LoRA 参数上），能不能排出 target > 近邻 > 普通背景，并解释已有复习臂的 B1 实测成绩？

打分点（每个种子两个，都只读）：
  prefix  = runs_phase2/A_seed*/checkpoints/stage_03_python 适配器 + runs_ext_e4/prefixes/A_seed*/training_state.pt
            的可训练参数（Calendar 阶段第 80 个新样本处的共享 midpoint；E4/E3/E3-B2 所有复习臂、none 臂都从这里分支，
            复习条目从第 87 个新样本起插入）。这是「复习训练前的起点」，为主分析。
  stage04 = runs_phase2/A_seed*/checkpoints/stage_04_calendar（phase2 原始 Calendar 阶段终点），为稳健性对照。
候选经验：data_ext_e4/pool/{database,file,python}.jsonl 全部 281 条（E3/P1/E3-B2 各臂实际插入的 DB/Python/File 条目
            都在其中），以及各臂 replay_plan 中出现过的 Calendar 条目（ctrl_cal 臂用；data_phase2/calendar/train.jsonl）。
探针：
  fct_probe   nat v2 Database（db.filter_cmp_top）题号为偶数的 15 题（探针半）；奇数 15 题为留出半，只用于外部检验。
  list_tables data_phase2/database/test.jsonl 中 db.list_tables 的 6 题。
  median_nat  nat v2 Python（py.median，target_median_natural 措辞）30 题。
  median_prose data_phase2/python/test.jsonl 中 py.median 的 5 题（「middle value」措辞）。
损失 = 训练时同一 SFT 损失（tokenize_episode，只监督 assistant token；autocast 同训练 dtype）；model.eval() 关闭 dropout；
batch=1；梯度在 fp32 中展平。探针梯度 = 该探针各题梯度的平均。

用法（项目根目录，WSL）：
  .venv/bin/python scripts/p2_grad_utility_pilot.py --phase score   # GPU；开跑前检查游戏 / 功耗上限 / 其它 GPU 进程
  .venv/bin/python scripts/p2_grad_utility_pilot.py --phase analyze # CPU；写 results.json 与 tables_ZH.md
输出：runs_ext_p2_grad_pilot/
"""
import argparse, json, math, statistics, subprocess, sys, time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT))
OUT = ROOT / "runs_ext_p2_grad_pilot"
SEEDS = [20261108, 20261109, 20261110]
CKPTS = ["prefix", "stage04"]
ARMS = ["none", "tf00", "tf25", "tf50", "b20_tf50", "dose_db0", "dose_db1", "dose_db2", "dose_db3", "dose_db4",
        "dose_db6", "ctrl_cal10", "ctrl_cal20", "e3b2_A_target_other", "e3b2_A_target_dbbg"]
PROBES = ["fct_probe", "list_tables", "median_nat", "median_prose"]
TARGET = "db.filter_cmp_top"
# 近邻规则（相对 db.filter_cmp_top = 数值比较 WHERE + ORDER BY/LIMIT）：
#   near_sort   ：同属「排序截断」家族（ORDER BY + LIMIT），谓词不同或无 WHERE —— db.top_n、db.filter_eq_top
#   near_filter ：有 WHERE 过滤、无排序截断 —— db.filter_eq_count、db.filter_eq_avg、db.filter_cmp_count、
#                 db.filter_cmp_avg、db.filter_cmp_group_count、db.multi_filter_count
#   这与 P1 coverage_ledger 记的三个近邻（db.top_n、db.filter_eq_count、db.filter_eq_top）一致；E4 池里实际出现的只有
#   db.top_n（near_sort）和 db.filter_eq_count（near_filter）。
NEAR_SORT = {"db.top_n", "db.filter_eq_top"}
NEAR_FILTER = {"db.filter_eq_count", "db.filter_eq_avg", "db.filter_cmp_count", "db.filter_cmp_avg",
               "db.filter_cmp_group_count", "db.multi_filter_count"}
GROUP_ORDER = ["target", "near_sort", "near_filter", "db_other", "python", "file", "calendar"]


def now():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S +0800")


def log(m):
    print(now(), m, flush=True)


def rj(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def group_of(row, pattern):
    f = row["tool_family"]
    if pattern == TARGET:
        return "target"
    if pattern in NEAR_SORT:
        return "near_sort"
    if pattern in NEAR_FILTER:
        return "near_filter"
    if f == "database":
        return "db_other"
    return f


# ------------------------------------------------------------------ data
def candidates():
    from fac_tinyagent.coverage_patterns import classify_item
    from fac_tinyagent import p1_run as P
    rows = {}
    for f in ("database", "file", "python"):
        for r in rj(ROOT / "data_ext_e4" / "pool" / (f + ".jsonl")):
            rows[r["episode_id"]] = r
    fallback = {}
    for f in ("database", "file", "python", "calendar"):
        for r in rj(ROOT / "data_phase2" / f / "train.jsonl"):
            fallback[r["episode_id"]] = r
    plans, missing = {}, []
    for s in SEEDS:
        for a in ARMS:
            if a == "none":
                plans["%d|%s" % (s, a)] = {"plan": None, "items": []}
                continue
            pp = P.ckpt_path(s, a) / "replay_plan.json"
            if not pp.exists():
                continue
            pl = json.load(open(pp, encoding="utf-8"))
            ids = [it["episode_id"] for it in pl.get("items", [])]
            for i in ids:
                if i not in rows:
                    if i in fallback:
                        rows[i] = fallback[i]
                    else:
                        missing.append(i)
            plans["%d|%s" % (s, a)] = {"plan": str(pp.relative_to(ROOT)), "items": ids,
                                       "target_flags": [bool(it.get("target")) for it in pl.get("items", [])]}
    used = {i for v in plans.values() for i in v["items"]}
    meta = {}
    for i, r in rows.items():
        pat = classify_item(r).pattern
        meta[i] = {"family": r["tool_family"], "pattern": pat, "template_id": r.get("template_id"),
                   "group": group_of(r, pat), "used_in_any_plan": i in used}
    return rows, meta, plans, missing


def probes():
    from fac_tinyagent.coverage_patterns import classify_item
    db = rj(ROOT / "data_ext_e4" / "final_v2" / "database.jsonl")
    py = rj(ROOT / "data_ext_e4" / "final_v2" / "python.jsonl")
    p2db = rj(ROOT / "data_phase2" / "database" / "test.jsonl")
    p2py = rj(ROOT / "data_phase2" / "python" / "test.jsonl")
    even = lambda r: int(r["episode_id"].rsplit("-", 1)[1]) % 2 == 0
    pr = {"fct_probe": [r for r in db if classify_item(r).pattern == TARGET and even(r)],
          "list_tables": [r for r in p2db if classify_item(r).pattern == "db.list_tables"],
          "median_nat": [r for r in py if classify_item(r).pattern == "py.median"],
          "median_prose": [r for r in p2py if classify_item(r).pattern == "py.median"]}
    holdout = [r["episode_id"] for r in db if classify_item(r).pattern == TARGET and not even(r)]
    return pr, holdout


# ------------------------------------------------------------------ safety
def preflight():
    from fac_tinyagent.p0_run import game_running
    g = game_running()
    if g is not False:
        raise SystemExit("game check: %s; refusing GPU work" % g)
    q = subprocess.run(["nvidia-smi", "--query-gpu=enforced.power.limit,memory.used",
                        "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=30)
    pl, mem = [float(x) for x in q.stdout.strip().split(",")]
    if pl < 60:
        raise SystemExit("power limit %.1f W < 60 W (quiet mode?)" % pl)
    apps = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
                          capture_output=True, text=True, timeout=30).stdout.strip()
    return {"time": now(), "game_running": g, "power_limit_w": pl, "gpu_mem_used_mib": mem, "compute_apps": apps}


def game_now():
    from fac_tinyagent.p0_run import game_running
    return game_running()


# ------------------------------------------------------------------ GPU scoring
def load_model(seed, ckpt):
    import torch
    from fac_tinyagent.p1_run import ckpt_path
    from fac_tinyagent.sft.train import _attach_adapter, load_base_model, load_tokenizer
    stage_cfg = json.load(open(ROOT / "runs_ext_e4" / "branches" / ("A_seed%d_none" % seed) / "checkpoint" /
                               "stage_config.json", encoding="utf-8"))["config"]
    tok = load_tokenizer(stage_cfg)
    model, dtype = load_base_model(stage_cfg)
    info = {}
    if ckpt == "prefix":
        adapter = ckpt_path(seed, "stage_03_python")
        model = _attach_adapter(model, stage_cfg, str(adapter))
        sp = ROOT / "runs_ext_e4" / "prefixes" / ("A_seed%d" % seed) / "training_state.pt"
        state = torch.load(sp, map_location="cpu", weights_only=False)
        params = {n: p for n, p in model.named_parameters() if p.requires_grad}
        if set(params) != set(state["parameters"]):
            raise SystemExit("prefix parameter names mismatch")
        with torch.no_grad():
            for n, p in params.items():
                p.copy_(state["parameters"][n].to(p.device, dtype=p.dtype))
        from fac_tinyagent.replay_train import _training_state_hash
        if _training_state_hash(model) != state["parameter_hash"]:
            raise SystemExit("prefix parameter hash mismatch")
        man = json.load(open(sp.parent / "manifest.json", encoding="utf-8"))
        info = {"adapter": str(adapter.relative_to(ROOT)), "prefix_state": str(sp.relative_to(ROOT)),
                "prefix_state_sha256": man["state_sha256"], "parameter_hash": state["parameter_hash"],
                "prefix_counters": state["counters"]}
        del state
    else:
        adapter = ckpt_path(seed, "stage_04_calendar")
        model = _attach_adapter(model, stage_cfg, str(adapter))
        info = {"adapter": str(adapter.relative_to(ROOT))}
    model.eval()
    return model, tok, dtype, stage_cfg, info


def grad_vec(model, tok, dtype, row, max_len, params):
    import torch
    from fac_tinyagent.sft.dataset import DataCollator, tokenize_episode
    feats = tokenize_episode(row, tok, max_len)
    batch = {k: v.to("cuda") for k, v in DataCollator(tok)([feats]).items()}
    model.zero_grad(set_to_none=True)
    with torch.autocast(device_type="cuda", dtype=dtype, enabled=dtype in (torch.bfloat16, torch.float16)):
        loss = model(**batch).loss
    loss.backward()
    g = torch.cat([(p.grad if p.grad is not None else torch.zeros_like(p)).detach().float().flatten() for p in params])
    model.zero_grad(set_to_none=True)
    return g, float(loss.item()), len(feats["input_ids"])


def score(args):
    import torch
    OUT.mkdir(exist_ok=True)
    rows, meta, plans, missing = candidates()
    pr, holdout = probes()
    pf = preflight()
    log("preflight %s" % pf)
    if missing:
        raise SystemExit("plan items not found: %s" % missing[:5])
    t_all = time.time()
    runlog = {"preflight": pf, "runs": []}
    for ckpt in args.ckpts:
        for s in SEEDS:
            fp = OUT / ("scores_%s_seed%d.json" % (ckpt, s))
            if fp.exists() and not args.force:
                log("skip %s" % fp.name)
                continue
            if game_now() is not False:
                raise SystemExit("game detected / check failed; stopping before %s seed %d" % (ckpt, s))
            t0 = time.time()
            model, tok, dtype, cfg, info = load_model(s, ckpt)
            max_len = int(cfg["training"]["max_seq_length"])
            params = [p for _, p in sorted(model.named_parameters(), key=lambda x: x[0]) if p.requires_grad]
            n_params = sum(p.numel() for p in params)
            pg, ploss = {}, {}
            for k, items in pr.items():
                acc = None
                ls = []
                for r in items:
                    g, l, _ = grad_vec(model, tok, dtype, r, max_len, params)
                    acc = g if acc is None else acc + g
                    ls.append(l)
                pg[k] = acc / len(items)
                ploss[k] = statistics.mean(ls)
            pnorm = {k: float(v.norm()) for k, v in pg.items()}
            cand = {}
            for j, (i, r) in enumerate(sorted(rows.items())):
                if j % 50 == 0 and game_now() is not False:
                    raise SystemExit("game detected / check failed during %s seed %d" % (ckpt, s))
                g, l, ntok = grad_vec(model, tok, dtype, r, max_len, params)
                gn = float(g.norm())
                c = {"loss": l, "input_tokens": ntok, "grad_norm": gn}
                for k, v in pg.items():
                    d = float(torch.dot(g, v))
                    c["dot_" + k] = d
                    c["cos_" + k] = d / (gn * pnorm[k] + 1e-30)
                cand[i] = c
            dur = time.time() - t0
            out = {"ckpt": ckpt, "seed": s, "checkpoint_info": info, "dtype": str(dtype), "n_trainable_params": n_params,
                   "probe_sizes": {k: len(v) for k, v in pr.items()}, "probe_ids": {k: [r["episode_id"] for r in v] for k, v in pr.items()},
                   "holdout_ids": holdout, "probe_loss": ploss, "probe_grad_norm": pnorm, "candidates": cand,
                   "duration_seconds": round(dur, 1), "peak_gpu_gb": round(torch.cuda.max_memory_allocated() / 2**30, 3),
                   "finished": now()}
            json.dump(out, open(fp, "w", encoding="utf-8"), indent=1)
            runlog["runs"].append({"ckpt": ckpt, "seed": s, "duration_seconds": round(dur, 1), "finished": out["finished"]})
            log("wrote %s (%.1fs, %d candidates)" % (fp.name, dur, len(cand)))
            del model, pg
            torch.cuda.empty_cache()
    runlog["total_seconds"] = round(time.time() - t_all, 1)
    lp = OUT / ("score_run_%s.json" % datetime.now().strftime("%Y%m%d_%H%M%S"))
    json.dump(runlog, open(lp, "w", encoding="utf-8"), indent=1)
    log("done total %.1fs" % runlog["total_seconds"])


# ------------------------------------------------------------------ analysis (CPU)
def rank(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and xs[o[j + 1]] == xs[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(a, b):
    if len(a) < 3:
        return None
    ma, mb = statistics.mean(a), statistics.mean(b)
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va == 0 or vb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def spearman(a, b):
    return pearson(rank(a), rank(b))


def qs(xs):
    xs = sorted(xs)
    if not xs:
        return None
    q = lambda p: xs[min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))]
    return {"n": len(xs), "mean": statistics.mean(xs), "min": xs[0], "q25": q(0.25), "median": q(0.5), "q75": q(0.75), "max": xs[-1]}


def pair_win(a, b):
    """P(随机取 a 组一条 > 随机取 b 组一条)，平局记 0.5。"""
    if not a or not b:
        return None
    w = sum((x > y) + 0.5 * (x == y) for x in a for y in b)
    return w / (len(a) * len(b))


def b1_acc(seed, arm, ids=None):
    from fac_tinyagent import p1_run as P
    p = P.results_path(seed, arm, "natv2_database")
    if not p.exists():
        return None
    res = rj(p)
    if len(res) != 30:
        return None
    if ids is not None:
        res = [r for r in res if r["episode_id"] in ids]
    return sum(bool(r["joint_success"]) for r in res) / len(res)


def analyze(args):
    _, meta, plans, _ = candidates()
    res = {"generated": now(), "near_rule": {"near_sort": sorted(NEAR_SORT), "near_filter": sorted(NEAR_FILTER)},
           "checkpoints": {}, "test_a": {}, "test_b": {}, "test_c": {}, "sanity_list_tables": {}}
    S = {}
    for ckpt in CKPTS:
        for s in SEEDS:
            fp = OUT / ("scores_%s_seed%d.json" % (ckpt, s))
            if fp.exists():
                S[(ckpt, s)] = json.load(open(fp, encoding="utf-8"))
                d = S[(ckpt, s)]
                res["checkpoints"]["%s|%d" % (ckpt, s)] = {"info": d["checkpoint_info"], "duration_seconds": d["duration_seconds"],
                                                           "probe_loss": d["probe_loss"], "probe_sizes": d["probe_sizes"],
                                                           "n_trainable_params": d["n_trainable_params"], "peak_gpu_gb": d["peak_gpu_gb"]}
    holdout = None
    for ckpt in CKPTS:
        for s in SEEDS:
            if (ckpt, s) not in S:
                continue
            C = S[(ckpt, s)]["candidates"]
            holdout = set(S[(ckpt, s)]["holdout_ids"])
            key = "%s|%d" % (ckpt, s)
            # (a) 分组分布，fct_probe；只用实际进过复习计划的 DB/Python/File 条目，另给全池版本
            for metric in ("cos", "dot"):
                for scope in ("used", "pool"):
                    g = defaultdict(list)
                    for i, m in meta.items():
                        if scope == "used" and not m["used_in_any_plan"]:
                            continue
                        if m["family"] == "calendar" and scope == "pool":
                            pass
                        g[m["group"]].append(C[i]["%s_fct_probe" % metric])
                    res["test_a"].setdefault(key, {}).setdefault(metric, {})[scope] = {
                        "groups": {k: qs(g[k]) for k in GROUP_ORDER if g[k]},
                        "win_target_vs_near_sort": pair_win(g["target"], g["near_sort"]),
                        "win_target_vs_near_filter": pair_win(g["target"], g["near_filter"]),
                        "win_near_sort_vs_db_other": pair_win(g["near_sort"], g["db_other"]),
                        "win_near_filter_vs_db_other": pair_win(g["near_filter"], g["db_other"]),
                        "win_near_vs_background": pair_win(g["near_sort"] + g["near_filter"],
                                                           g["db_other"] + g["python"] + g["file"]),
                        "win_target_vs_background": pair_win(g["target"], g["db_other"] + g["python"] + g["file"]),
                        "order_holds_means": (bool(g["target"]) and bool(g["near_sort"] + g["near_filter"]) and
                                              statistics.mean(g["target"]) > statistics.mean(g["near_sort"] + g["near_filter"]) >
                                              statistics.mean(g["db_other"] + g["python"] + g["file"]))}
                    if metric == "cos" and scope == "used":
                        # 每个模式的均值（看近邻里谁高）
                        pm = defaultdict(list)
                        for i, m in meta.items():
                            if m["used_in_any_plan"]:
                                pm[m["pattern"]].append(C[i]["cos_fct_probe"])
                        res["test_a"][key]["cos_by_pattern"] = {k: statistics.mean(v) for k, v in sorted(pm.items(), key=lambda x: -statistics.mean(x[1]))}
                        # target 各条
                        res["test_a"][key]["target_items"] = {i: C[i]["cos_fct_probe"] for i, m in meta.items() if m["group"] == "target"}
            # sanity：list_tables 探针下 db.list_tables 条目是否排第一
            lt = defaultdict(list)
            for i, m in meta.items():
                lt["db.list_tables" if m["pattern"] == "db.list_tables" else "other"].append(C[i]["cos_list_tables"])
            allc = sorted(((C[i]["cos_list_tables"], i) for i in meta), reverse=True)
            top = [meta[i]["pattern"] for _, i in allc[:11]]
            res["sanity_list_tables"][key] = {"list_tables": qs(lt["db.list_tables"]), "other": qs(lt["other"]),
                                              "win": pair_win(lt["db.list_tables"], lt["other"]),
                                              "top11_patterns": top}
            # (c) py.median：同说法 vs 另一说法
            for probe in ("median_nat", "median_prose"):
                gm = defaultdict(list)
                for i, m in meta.items():
                    if m["pattern"] == "py.median":
                        gm[m["template_id"]].append(C[i]["cos_" + probe])
                other_py = [C[i]["cos_" + probe] for i, m in meta.items() if m["family"] == "python" and m["pattern"] != "py.median"]
                res["test_c"].setdefault(key, {})[probe] = {
                    "by_template": {k: qs(v) for k, v in gm.items()}, "other_python_patterns": qs(other_py),
                    "win_natural_vs_stats_median": pair_win(gm.get("target_median_natural", []), gm.get("stats_median", [])),
                    "win_stats_median_vs_other_py": pair_win(gm.get("stats_median", []), other_py)}
    # (b) 臂级外部检验
    for ckpt in CKPTS:
        pts = []
        for s in SEEDS:
            if (ckpt, s) not in S:
                continue
            C = S[(ckpt, s)]["candidates"]
            for a in ARMS:
                k = "%d|%s" % (s, a)
                if k not in plans:
                    continue
                full = b1_acc(s, a)
                if full is None:
                    continue
                ho = b1_acc(s, a, holdout)
                items = plans[k]["items"]
                cs = [C[i]["cos_fct_probe"] for i in items]
                ds = [C[i]["dot_fct_probe"] for i in items]
                ntgt = sum(meta[i]["group"] == "target" for i in items)
                tgt_ids = sorted({i for i in items if meta[i]["group"] == "target"})
                pts.append({"seed": s, "arm": a, "acc_full": full, "acc_holdout": ho, "n_target": ntgt,
                            "n_near": sum(meta[i]["group"] in ("near_sort", "near_filter") for i in items),
                            "sum_cos": sum(cs), "mean_cos": statistics.mean(cs) if cs else 0.0,
                            "sum_pos_cos": sum(max(0.0, c) for c in cs), "sum_dot": sum(ds),
                            "sum_cos_target": sum(C[i]["cos_fct_probe"] for i in items if meta[i]["group"] == "target"),
                            "sum_cos_nontarget": sum(C[i]["cos_fct_probe"] for i in items if meta[i]["group"] != "target"),
                            "max_cos": max(cs) if cs else 0.0, "target_ids": tgt_ids, "n_slots": len(items)})
        feats = ["n_target", "sum_cos", "mean_cos", "sum_pos_cos", "sum_dot", "sum_cos_target", "sum_cos_nontarget", "max_cos", "n_near"]
        B = {"points": pts, "spearman_all": {}, "spearman_within_seed": {}, "one_target_subset": {}}
        for out_k in ("acc_holdout", "acc_full"):
            for f in feats:
                B["spearman_all"]["%s~%s" % (out_k, f)] = spearman([p[f] for p in pts], [p[out_k] for p in pts])
                ws = []
                for s in SEEDS:
                    sp = [p for p in pts if p["seed"] == s]
                    ws.append(spearman([p[f] for p in sp], [p[out_k] for p in sp]))
                B["spearman_within_seed"]["%s~%s" % (out_k, f)] = ws
        # 只含 1 条 target 的臂（tf25、两条 A 臂、dose_db1）：打分能否排出 tf25 最高
        one = [p for p in pts if p["n_target"] == 1]
        for f in ("sum_cos", "sum_dot", "sum_cos_target", "sum_cos_nontarget", "max_cos", "sum_pos_cos"):
            B["one_target_subset"]["spearman_holdout~" + f] = spearman([p[f] for p in one], [p["acc_holdout"] for p in one])
            B["one_target_subset"]["spearman_full~" + f] = spearman([p[f] for p in one], [p["acc_full"] for p in one])
        per_seed = {}
        for s in SEEDS:
            sp = sorted([p for p in one if p["seed"] == s], key=lambda p: -p["sum_cos"])
            per_seed[str(s)] = [{"arm": p["arm"], "sum_cos": p["sum_cos"], "sum_cos_target": p["sum_cos_target"],
                                 "sum_cos_nontarget": p["sum_cos_nontarget"], "acc_full": p["acc_full"],
                                 "acc_holdout": p["acc_holdout"], "target_ids": p["target_ids"]} for p in sp]
        B["one_target_subset"]["per_seed"] = per_seed
        B["one_target_subset"]["n_points"] = len(one)
        res["test_b"][ckpt] = B
    json.dump(res, open(OUT / "results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_md(res)
    log("wrote results.json / tables_ZH.md")


def f3(x, n=3):
    return "—" if x is None else ("%." + str(n) + "f") % x


def write_md(res):
    md = ["# 经验价值梯度打分 pilot：结果表", "", "生成：%s（Asia/Shanghai）。脚本 `scripts/p2_grad_utility_pilot.py --phase analyze`；"
          "数字全部来自 `runs_ext_p2_grad_pilot/scores_*.json` 与 P1 B1 逐题结果。" % res["generated"], "",
          "近邻规则：near_sort = %s；near_filter = %s（E4 池里实际只有 db.top_n、db.filter_eq_count）。" % (
              ", ".join(res["near_rule"]["near_sort"]), ", ".join(res["near_rule"]["near_filter"])), ""]
    md += ["## 0. 打分点与耗时", "", "| 打分点 | 种子 | 适配器 | 探针平均损失 fct / list_tables / median_nat / median_prose | 用时 s | 峰值显存 GB |", "|---|---|---|---|---|---|"]
    for k, v in res["checkpoints"].items():
        c, s = k.split("|")
        pl = v["probe_loss"]
        md.append("| %s | %s | `%s`%s | %s | %s | %s |" % (c, s[-2:], v["info"]["adapter"],
                  (" + `%s`（sha256 %s…）" % (v["info"]["prefix_state"], v["info"]["prefix_state_sha256"][:8])) if "prefix_state" in v["info"] else "",
                  " / ".join(f3(pl[p]) for p in PROBES), v["duration_seconds"], v["peak_gpu_gb"]))
    md += ["", "## 1. 检验 (a)：fct 探针（filter_cmp_top 探针半 15 题）下各组余弦", "",
           "范围：各臂复习计划里实际出现过的条目（含 Calendar）。win = 随机一对里前者余弦更高的概率（0.5 = 无区分）。", ""]
    for ckpt in CKPTS:
        md += ["### 打分点 %s" % ckpt, "", "| 种子 | " + " | ".join(GROUP_ORDER) + " | target>near_sort | target>near_filter | near>背景 | target>背景 | 均值顺序 target>近邻>背景 |",
               "|---|" + "---|" * (len(GROUP_ORDER) + 5)]
        for s in SEEDS:
            key = "%s|%d" % (ckpt, s)
            if key not in res["test_a"]:
                continue
            A = res["test_a"][key]["cos"]["used"]
            cells = []
            for g in GROUP_ORDER:
                q = A["groups"].get(g)
                cells.append("—" if not q else "%s（n=%d，中位 %s）" % (f3(q["mean"]), q["n"], f3(q["median"])))
            md.append("| %s | %s | %s | %s | %s | %s | %s |" % (str(s)[-2:], " | ".join(cells), f3(A["win_target_vs_near_sort"]),
                      f3(A["win_target_vs_near_filter"]), f3(A["win_near_vs_background"]), f3(A["win_target_vs_background"]),
                      "是" if A["order_holds_means"] else "否"))
        md += [""]
        for s in SEEDS:
            key = "%s|%d" % (ckpt, s)
            if key in res["test_a"]:
                bp = res["test_a"][key]["cos_by_pattern"]
                md.append("- 种子 %s 按模式均值（前 8）：%s" % (str(s)[-2:], "，".join("%s %s" % (k, f3(v)) for k, v in list(bp.items())[:8])))
        md += [""]
        md += ["点积版本（dot）同样的 win：", "", "| 种子 | target>near_sort | target>near_filter | near>背景 | target>背景 | 均值顺序 |", "|---|---|---|---|---|---|"]
        for s in SEEDS:
            key = "%s|%d" % (ckpt, s)
            if key in res["test_a"]:
                A = res["test_a"][key]["dot"]["used"]
                md.append("| %s | %s | %s | %s | %s | %s |" % (str(s)[-2:], f3(A["win_target_vs_near_sort"]), f3(A["win_target_vs_near_filter"]),
                          f3(A["win_near_vs_background"]), f3(A["win_target_vs_background"]), "是" if A["order_holds_means"] else "否"))
        md += [""]
    md += ["## 2. 合理性检查：list_tables 探针下 db.list_tables 条目是否排前", "", "| 打分点 | 种子 | list_tables 组均值 | 其它均值 | win | 余弦最高 11 条的模式 |", "|---|---|---|---|---|---|"]
    for k, v in res["sanity_list_tables"].items():
        c, s = k.split("|")
        from collections import Counter
        md.append("| %s | %s | %s | %s | %s | %s |" % (c, s[-2:], f3(v["list_tables"]["mean"]), f3(v["other"]["mean"]), f3(v["win"]),
                  "，".join("%s×%d" % kv for kv in Counter(v["top11_patterns"]).most_common())))
    md += ["", "## 3. 检验 (b)：臂级外部检验（每点 = 臂×种子，B1 nat v2 Database）", "",
           "预测量：n_target = 复习计划里 filter_cmp_top 槽数（朴素预测量）；sum_cos = 计划内全部槽位 fct 余弦之和；"
           "sum_cos_nontarget = 去掉 target 后的和；acc_holdout = 奇数题号 15 题（未用于算梯度）。", ""]
    for ckpt, B in res["test_b"].items():
        md += ["### 打分点 %s（%d 个点）" % (ckpt, len(B["points"])), "", "| 预测量 | Spearman(留出半) 全部点 | 种子内 08/09/10 | Spearman(全 30 题) 全部点 |", "|---|---|---|---|"]
        for f in ("n_target", "sum_cos", "mean_cos", "sum_pos_cos", "sum_dot", "sum_cos_target", "sum_cos_nontarget", "max_cos", "n_near"):
            md.append("| %s | %s | %s | %s |" % (f, f3(B["spearman_all"]["acc_holdout~" + f]),
                      " / ".join(f3(x) for x in B["spearman_within_seed"]["acc_holdout~" + f]), f3(B["spearman_all"]["acc_full~" + f])))
        O = B["one_target_subset"]
        md += ["", "只含 1 条 target 的臂（%d 点）：" % O["n_points"], "",
               "| 预测量 | Spearman(留出半) | Spearman(全 30) |", "|---|---|---|"]
        for f in ("sum_cos", "sum_dot", "sum_cos_target", "sum_cos_nontarget", "max_cos", "sum_pos_cos"):
            md.append("| %s | %s | %s |" % (f, f3(O["spearman_holdout~" + f]), f3(O["spearman_full~" + f])))
        md += ["", "| 种子 | 臂（按 sum_cos 降序） | sum_cos | 其中 target | 非 target | 实测全 30 | 留出半 | target 条目 |", "|---|---|---|---|---|---|---|---|"]
        for s, lst in O["per_seed"].items():
            for p in lst:
                md.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (s[-2:], p["arm"], f3(p["sum_cos"]), f3(p["sum_cos_target"]), f3(p["sum_cos_nontarget"]),
                          f3(p["acc_full"]), f3(p["acc_holdout"]), ", ".join(x.replace("database-train-target_db_filter_top-", "T-") for x in p["target_ids"])))
        md += ["", "全部点明细：", "", "| 种子 | 臂 | n_target | n_near | sum_cos | mean_cos | 全 30 | 留出半 |", "|---|---|---|---|---|---|---|---|"]
        for p in B["points"]:
            md.append("| %s | %s | %d | %d | %s | %s | %s | %s |" % (str(p["seed"])[-2:], p["arm"], p["n_target"], p["n_near"], f3(p["sum_cos"]),
                      f3(p["mean_cos"], 4), f3(p["acc_full"]), f3(p["acc_holdout"])))
        md += [""]
    md += ["## 4. 检验 (c)：py.median 同说法 vs 另一说法", "",
           "| 打分点 | 种子 | 探针 | target_median_natural 均值（n） | stats_median 均值（n） | 其它 Python 模式均值 | win(natural>stats_median) | win(stats_median>其它 Python) |", "|---|---|---|---|---|---|---|---|"]
    for k, v in res["test_c"].items():
        c, s = k.split("|")
        for probe, d in v.items():
            bt = d["by_template"]
            nat, stm = bt.get("target_median_natural"), bt.get("stats_median")
            md.append("| %s | %s | %s | %s（%d） | %s（%d） | %s | %s | %s |" % (c, s[-2:], probe, f3(nat["mean"]), nat["n"], f3(stm["mean"]), stm["n"],
                      f3(d["other_python_patterns"]["mean"]), f3(d["win_natural_vs_stats_median"]), f3(d["win_stats_median_vs_other_py"])))
    open(OUT / "tables_ZH.md", "w", encoding="utf-8").write("\n".join(md) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["score", "analyze", "inventory"], required=True)
    ap.add_argument("--ckpts", default="prefix,stage04")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    a.ckpts = [c for c in a.ckpts.split(",") if c]
    if a.phase == "score":
        score(a)
    elif a.phase == "inventory":
        rows, meta, plans, missing = candidates()
        pr, ho = probes()
        g = defaultdict(int)
        for m in meta.values():
            g[(m["group"], m["used_in_any_plan"])] += 1
        print({"rows": len(rows), "plans": len(plans), "missing": missing[:5], "groups": dict(g),
               "probes": {k: len(v) for k, v in pr.items()}, "holdout": len(ho)})
    else:
        analyze(a)


if __name__ == "__main__":
    main()
