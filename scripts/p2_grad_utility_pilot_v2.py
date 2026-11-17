#!/usr/bin/env python3
"""P2 经验价值梯度打分 pilot v2：分叉 token 版探针损失（只前向+反向，不训练、不保存模型）。

与 v1（scripts/p2_grad_utility_pilot.py，不改动）的唯一区别在探针梯度：
  v1：探针题整条金标回答（全部 assistant token）的平均 CE。
  v2：只在「决定性 token」上算 CE。对每道探针题：
    1) 用当前打分点的模型，按 B1 评测同样的方式（conversation_text(system+user, generation=True)，贪心，
       max_new_tokens = config.evaluation.max_new_tokens_tool）生成第一轮（工具调用）。
    2) 金标续写 c = 对「生成 prompt 文本 + 第一轮金标 assistant 内容 + <|im_end|>」整体分词后、生成 prompt 之后的 token
       （要求整体分词的前缀与生成 prompt 的 token 完全相同，否则报错，不猜）。探针 CE 也在这条序列上算，所以上下文与
       B1 评测一致：Qwen3 模板在 enable_thinking=False 时会在生成 prompt 末尾加空的 <think>\n\n</think>\n\n，
       而训练文本的 assistant 轮没有这一段；这是 v2 探针与训练格式唯一的差别。
    3) 逐 token 对齐生成序列 g 与 c，取第一个不一致的位置 j（g 比 c 短时 j = len(g)）。
       变体 d0 = 只取 c[j]；d1（主）= c[j..j+1]（分叉 token 加之后 1 个金标 token）；dall = c[j..末尾]（对照）。
    4) 若 g 与 c 在 c 的全长上完全一致（模型对这一轮全对），改用「关键 token」：c 中字符区间与金标调用里
       工具名字符串、以及 arguments 中每个参数值的 JSON 文本（无参数时为 `{}`）有重叠的 token。
       三个变体都用这同一组关键 token（全对题没有分叉点）。
    只看第一轮工具调用；第二轮 answer 不进探针损失（三类探针的失败都在第一轮：SQL 参数、工具名、无参调用格式）。
候选经验的梯度与 v1 相同（训练时的完整 SFT 损失）。打分点、候选池、探针题集、留出半、近邻规则都与 v1 相同。

用法（项目根目录，WSL）：
  .venv/bin/python scripts/p2_grad_utility_pilot_v2.py --phase score     # GPU，开跑前检查同 v1，运行中每 50 条复查游戏
  .venv/bin/python scripts/p2_grad_utility_pilot_v2.py --phase analyze   # CPU
输出：runs_ext_p2_grad_pilot/v2/
"""
import argparse, json, statistics, sys, time
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(".").resolve()
sys.path.insert(0, str(ROOT / "scripts"))
import p2_grad_utility_pilot as V1  # noqa: E402  只复用函数，不写 v1 输出

OUT = ROOT / "runs_ext_p2_grad_pilot" / "v2"
SEEDS, CKPTS, ARMS, GROUP_ORDER = V1.SEEDS, V1.CKPTS, V1.ARMS, V1.GROUP_ORDER
PROBES = V1.PROBES
VARIANTS = ["d1", "d0", "dall"]
log, now, rj = V1.log, V1.now, V1.rj


# ------------------------------------------------------------------ decisive tokens
def char_offsets(tok, ids):
    offs, prev = [], 0
    for i in range(len(ids)):
        cur = len(tok.decode(ids[:i + 1], skip_special_tokens=False))
        offs.append((prev, cur))
        prev = cur
    return offs


def key_positions(tok, cont_ids, row):
    """全对题：c 中与工具名、各参数值 JSON 文本有字符重叠的 token 位置。"""
    text = tok.decode(cont_ids, skip_special_tokens=False)
    offs = char_offsets(tok, cont_ids)
    ranges = []
    name = row["expected_tool"]
    k = text.find('"%s"' % name)
    if k >= 0:
        ranges.append((k + 1, k + 1 + len(name)))
    a0 = text.find('"arguments"')
    args = row.get("expected_arguments") or {}
    if a0 >= 0:
        if not args:
            k = text.find("{}", a0)
            if k >= 0:
                ranges.append((k, k + 2))
        for v in args.values():
            for js in (json.dumps(v, ensure_ascii=False), json.dumps(v)):
                k = text.find(js, a0)
                if k >= 0:
                    ranges.append((k, k + len(js)))
                    break
    pos = [i for i, (s, e) in enumerate(offs) if e > s and any(s < re and e > rs for rs, re in ranges)]
    return pos, len(ranges)


def decisive(model, tok, row, cfg):
    import torch
    from fac_tinyagent.sft.dataset import conversation_text, tokenize_episode
    from fac_tinyagent.sft.evaluate import _eos_ids
    max_len = int(cfg["training"]["max_seq_length"])
    ptxt = conversation_text(tok, row["messages"][:2], generation=True)
    P = tok(ptxt, add_special_tokens=False)["input_ids"]
    gold = row["messages"][2]
    assert gold["role"] == "assistant"
    full = tok(ptxt + gold["content"] + "<|im_end|>", add_special_tokens=False)["input_ids"][:max_len]
    if full[:len(P)] != P:
        raise SystemExit("generation prompt is not a token prefix of prompt+gold for %s" % row["episode_id"])
    e = len(full)
    c = full[len(P):e]
    use_cache = model.config.use_cache
    model.config.use_cache = True
    with torch.no_grad():
        out = model.generate(input_ids=torch.tensor([P], device="cuda"),
                             attention_mask=torch.ones(1, len(P), dtype=torch.long, device="cuda"),
                             max_new_tokens=int(cfg["evaluation"]["max_new_tokens_tool"]), do_sample=False,
                             pad_token_id=tok.pad_token_id or tok.eos_token_id, eos_token_id=_eos_ids(tok))
    model.config.use_cache = use_cache
    g = out[0][len(P):].tolist()
    j = next((i for i in range(len(c)) if i >= len(g) or g[i] != c[i]), None)
    gen_text = tok.decode(g, skip_special_tokens=True).strip()
    info = {"episode_id": row["episode_id"], "gold_len": len(c), "generated": gen_text[:300]}
    if j is None:
        pos, nr = key_positions(tok, c, row)
        if not pos:
            raise SystemExit("no key tokens for %s" % row["episode_id"])
        info.update({"all_correct": True, "n_key_tokens": len(pos), "n_key_ranges": nr,
                     "key_text": tok.decode([c[i] for i in pos])[:200]})
        sel = {v: pos for v in VARIANTS}
    else:
        offs = char_offsets(tok, c)
        info.update({"all_correct": False, "diverge_at": j,
                     "gold_token": tok.decode([c[j]]), "pred_token": tok.decode([g[j]]) if j < len(g) else "<end>",
                     "gold_prefix_text": tok.decode(c[:j])[-60:], "char_offset": offs[j][0]})
        sel = {"d0": [j], "d1": list(range(j, min(j + 2, len(c)))), "dall": list(range(j, len(c)))}
    labs = {}
    for v, pos in sel.items():
        lab = [-100] * e
        for p in pos:
            lab[len(P) + p] = full[len(P) + p]
        labs[v] = lab
    return full[:e], labs, info


def probe_grad(model, tok, dtype, ids, labels, params):
    import torch
    model.zero_grad(set_to_none=True)
    batch = {"input_ids": torch.tensor([ids], device="cuda"), "attention_mask": torch.ones(1, len(ids), dtype=torch.long, device="cuda"),
             "labels": torch.tensor([labels], device="cuda")}
    with torch.autocast(device_type="cuda", dtype=dtype, enabled=dtype in (torch.bfloat16, torch.float16)):
        loss = model(**batch).loss
    loss.backward()
    g = torch.cat([(p.grad if p.grad is not None else torch.zeros_like(p)).detach().float().flatten() for p in params])
    model.zero_grad(set_to_none=True)
    return g, float(loss.item())


def score(args):
    import torch
    OUT.mkdir(parents=True, exist_ok=True)
    rows, meta, plans, missing = V1.candidates()
    pr, holdout = V1.probes()
    pf = V1.preflight()
    log("preflight %s" % pf)
    if missing:
        raise SystemExit("plan items missing")
    t_all = time.time()
    runlog = {"preflight": pf, "runs": []}
    for ckpt in args.ckpts:
        for s in SEEDS:
            fp = OUT / ("scores_%s_seed%d.json" % (ckpt, s))
            if fp.exists() and not args.force:
                log("skip %s" % fp.name)
                continue
            if V1.game_now() is not False:
                raise SystemExit("game detected / check failed; stopping before %s seed %d" % (ckpt, s))
            t0 = time.time()
            model, tok, dtype, cfg, info = V1.load_model(s, ckpt)
            params = [p for _, p in sorted(model.named_parameters(), key=lambda x: x[0]) if p.requires_grad]
            pg, ploss, pinfo = {}, {}, {}
            for k, items in pr.items():
                acc = {v: None for v in VARIANTS}
                ls = defaultdict(list)
                pinfo[k] = []
                for r in items:
                    ids, labs, inf = decisive(model, tok, r, cfg)
                    model.eval()
                    for v in VARIANTS:
                        g, l = probe_grad(model, tok, dtype, ids, labs[v], params)
                        acc[v] = g if acc[v] is None else acc[v] + g
                        ls[v].append(l)
                    inf["loss"] = {v: ls[v][-1] for v in VARIANTS}
                    pinfo[k].append(inf)
                for v in VARIANTS:
                    pg["%s_%s" % (k, v)] = acc[v] / len(items)
                    ploss["%s_%s" % (k, v)] = statistics.mean(ls[v])
            t_probe = time.time() - t0
            pnorm = {k: float(v.norm()) for k, v in pg.items()}
            cand = {}
            for j, (i, r) in enumerate(sorted(rows.items())):
                if j % 50 == 0 and V1.game_now() is not False:
                    raise SystemExit("game detected / check failed during %s seed %d" % (ckpt, s))
                g, l, ntok = V1.grad_vec(model, tok, dtype, r, int(cfg["training"]["max_seq_length"]), params)
                gn = float(g.norm())
                c = {"loss": l, "grad_norm": gn}
                for k, v in pg.items():
                    d = float(torch.dot(g, v))
                    c["dot_" + k] = d
                    c["cos_" + k] = d / (gn * pnorm[k] + 1e-30)
                cand[i] = c
            dur = time.time() - t0
            out = {"ckpt": ckpt, "seed": s, "checkpoint_info": info, "dtype": str(dtype), "variants": VARIANTS,
                   "probe_info": pinfo, "probe_loss": ploss, "probe_grad_norm": pnorm, "holdout_ids": holdout,
                   "candidates": cand, "probe_seconds": round(t_probe, 1), "duration_seconds": round(dur, 1),
                   "peak_gpu_gb": round(torch.cuda.max_memory_allocated() / 2**30, 3), "finished": now()}
            json.dump(out, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            runlog["runs"].append({"ckpt": ckpt, "seed": s, "duration_seconds": round(dur, 1), "finished": out["finished"]})
            log("wrote %s (%.1fs)" % (fp.name, dur))
            del model, pg
            torch.cuda.empty_cache()
    runlog["total_seconds"] = round(time.time() - t_all, 1)
    json.dump(runlog, open(OUT / ("score_run_%s.json" % datetime.now().strftime("%Y%m%d_%H%M%S")), "w"), indent=1)
    log("done total %.1fs" % runlog["total_seconds"])


# ------------------------------------------------------------------ analysis
def residual(y, x):
    """rank(y) 对 rank(x) 做最小二乘后的残差。"""
    ry, rx = V1.rank(y), V1.rank(x)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    vx = sum((a - mx) ** 2 for a in rx)
    b = sum((a - mx) * (c - my) for a, c in zip(rx, ry)) / vx if vx else 0.0
    return [c - my - b * (a - mx) for a, c in zip(rx, ry)]


def partial_spearman(y, x, z):
    return V1.pearson(residual(y, z), residual(x, z))


def analyze(args):
    _, meta, plans, _ = V1.candidates()
    S = {}
    for ckpt in CKPTS:
        for s in SEEDS:
            fp = OUT / ("scores_%s_seed%d.json" % (ckpt, s))
            if fp.exists():
                S[(ckpt, s)] = json.load(open(fp, encoding="utf-8"))
    V1S = {}
    for ckpt in CKPTS:
        for s in SEEDS:
            fp = V1.OUT / ("scores_%s_seed%d.json" % (ckpt, s))
            if fp.exists():
                V1S[(ckpt, s)] = json.load(open(fp, encoding="utf-8"))["candidates"]
    res = {"generated": now(), "probe_diagnostics": {}, "test_a": {}, "test_b": {}, "test_c": {}, "sanity": {}, "target_items": {}}
    for (ckpt, s), d in S.items():
        key = "%s|%d" % (ckpt, s)
        diag = {}
        for k, lst in d["probe_info"].items():
            ac = sum(x["all_correct"] for x in lst)
            forms = Counter("%s→%s" % (x["gold_token"], x["pred_token"]) for x in lst if not x["all_correct"])
            diag[k] = {"n": len(lst), "n_all_correct": ac, "n_diverged": len(lst) - ac,
                       "diverge_forms": dict(forms.most_common(6)),
                       "loss": {v: d["probe_loss"]["%s_%s" % (k, v)] for v in VARIANTS},
                       "examples": [{kk: x[kk] for kk in ("episode_id", "gold_prefix_text", "gold_token", "pred_token") if kk in x}
                                    for x in lst if not x["all_correct"]][:3]}
        res["probe_diagnostics"][key] = diag
    holdout = None
    for (ckpt, s), d in S.items():
        key = "%s|%d" % (ckpt, s)
        C = d["candidates"]
        holdout = set(d["holdout_ids"])
        for v in VARIANTS:
            m = "cos_fct_probe_%s" % v
            g = defaultdict(list)
            for i, mm in meta.items():
                if mm["used_in_any_plan"]:
                    g[mm["group"]].append(C[i][m])
            bg = g["db_other"] + g["python"] + g["file"]
            near = g["near_sort"] + g["near_filter"]
            pm = defaultdict(list)
            for i, mm in meta.items():
                if mm["used_in_any_plan"]:
                    pm[mm["pattern"]].append(C[i][m])
            res["test_a"].setdefault(key, {})[v] = {
                "groups": {k: V1.qs(g[k]) for k in GROUP_ORDER if g[k]},
                "win_target_vs_near_sort": V1.pair_win(g["target"], g["near_sort"]),
                "win_target_vs_near_filter": V1.pair_win(g["target"], g["near_filter"]),
                "win_near_sort_vs_bg": V1.pair_win(g["near_sort"], bg), "win_near_filter_vs_bg": V1.pair_win(g["near_filter"], bg),
                "win_near_vs_bg": V1.pair_win(near, bg), "win_target_vs_bg": V1.pair_win(g["target"], bg),
                "order_holds_means": statistics.mean(g["target"]) > statistics.mean(near) > statistics.mean(bg),
                "top_patterns": [(k, statistics.mean(x)) for k, x in sorted(pm.items(), key=lambda kv: -statistics.mean(kv[1]))[:6]]}
            lt = [C[i]["cos_list_tables_%s" % v] for i, mm in meta.items() if mm["pattern"] == "db.list_tables"]
            ot = [C[i]["cos_list_tables_%s" % v] for i, mm in meta.items() if mm["pattern"] != "db.list_tables"]
            res["sanity"].setdefault(key, {})[v] = {"list_tables": statistics.mean(lt), "other": statistics.mean(ot), "win": V1.pair_win(lt, ot)}
            for probe in ("median_nat", "median_prose"):
                gm = defaultdict(list)
                for i, mm in meta.items():
                    if mm["pattern"] == "py.median":
                        gm[mm["template_id"]].append(C[i]["cos_%s_%s" % (probe, v)])
                opy = [C[i]["cos_%s_%s" % (probe, v)] for i, mm in meta.items() if mm["family"] == "python" and mm["pattern"] != "py.median"]
                res["test_c"].setdefault(key, {}).setdefault(probe, {})[v] = {
                    "natural": statistics.mean(gm["target_median_natural"]), "stats_median": statistics.mean(gm["stats_median"]),
                    "other_py": statistics.mean(opy),
                    "win_natural_vs_stats": V1.pair_win(gm["target_median_natural"], gm["stats_median"]),
                    "win_stats_vs_other_py": V1.pair_win(gm["stats_median"], opy)}
        # 单条 target 条目（全部 filter_cmp_top 训练条目）
        tg = sorted(i for i, mm in meta.items() if mm["group"] == "target")
        ti = {}
        for i in tg:
            ti[i] = {v: {"cos": C[i]["cos_fct_probe_%s" % v], "dot": C[i]["dot_fct_probe_%s" % v]} for v in VARIANTS}
            if (ckpt, s) in V1S:
                ti[i]["v1_full_mean"] = {"cos": V1S[(ckpt, s)][i]["cos_fct_probe"], "dot": V1S[(ckpt, s)][i]["dot_fct_probe"]}
        res["target_items"][key] = ti
    # (b) 臂级
    def pts_for(ckpt, scorer):
        pts = []
        for s in SEEDS:
            if (ckpt, s) not in S:
                continue
            for a in ARMS:
                k = "%d|%s" % (s, a)
                if k not in plans:
                    continue
                full = V1.b1_acc(s, a)
                if full is None:
                    continue
                items = plans[k]["items"]
                p = {"seed": s, "arm": a, "acc_full": full, "acc_holdout": V1.b1_acc(s, a, holdout),
                     "n_target": sum(meta[i]["group"] == "target" for i in items),
                     "target_ids": sorted({i.rsplit("-", 1)[1] for i in items if meta[i]["group"] == "target"})}
                p.update(scorer(s, items))
                pts.append(p)
        return pts

    def make_scorer(ckpt, metric):
        def f(s, items):
            C = S[(ckpt, s)]["candidates"] if metric != "v1" else V1S[(ckpt, s)]
            m = "cos_fct_probe_%s" % metric.split(":")[0] if metric != "v1" else "cos_fct_probe"
            if metric.endswith(":dot"):
                m = m.replace("cos_", "dot_")
            xs = [C[i][m] for i in items]
            return {"sum": sum(xs), "mean": statistics.mean(xs) if xs else 0.0,
                    "sum_target": sum(C[i][m] for i in items if meta[i]["group"] == "target"),
                    "sum_nontarget": sum(C[i][m] for i in items if meta[i]["group"] != "target")}
        return f

    for ckpt in CKPTS:
        res["test_b"][ckpt] = {}
        for metric in ["d1", "d0", "dall", "d1:dot", "v1"]:
            if metric == "v1" and not all((ckpt, s) in V1S for s in SEEDS):
                continue
            pts = pts_for(ckpt, make_scorer(ckpt, metric))
            y = [p["acc_holdout"] for p in pts]
            nt = [p["n_target"] for p in pts]
            B = {"n_points": len(pts),
                 "spearman_n_target": V1.spearman(nt, y),
                 "spearman_sum": V1.spearman([p["sum"] for p in pts], y),
                 "spearman_mean": V1.spearman([p["mean"] for p in pts], y),
                 "spearman_sum_nontarget": V1.spearman([p["sum_nontarget"] for p in pts], y),
                 "partial_sum_given_n_target": partial_spearman(y, [p["sum"] for p in pts], nt),
                 "partial_sum_nontarget_given_n_target": partial_spearman(y, [p["sum_nontarget"] for p in pts], nt),
                 "partial_sum_target_given_n_target": partial_spearman(y, [p["sum_target"] for p in pts], nt)}
            strata = {}
            for n in sorted(set(nt)):
                sp = [p for p in pts if p["n_target"] == n]
                if len(sp) >= 4 and len({p["acc_holdout"] for p in sp}) > 1:
                    strata[str(n)] = {"n": len(sp), "spearman_sum": V1.spearman([p["sum"] for p in sp], [p["acc_holdout"] for p in sp]),
                                      "spearman_sum_nontarget": V1.spearman([p["sum_nontarget"] for p in sp], [p["acc_holdout"] for p in sp])}
            B["within_n_target_strata"] = strata
            one = [p for p in pts if p["n_target"] == 1]
            B["one_target"] = {"n": len(one),
                               "spearman_sum": V1.spearman([p["sum"] for p in one], [p["acc_holdout"] for p in one]),
                               "spearman_sum_target": V1.spearman([p["sum_target"] for p in one], [p["acc_holdout"] for p in one]),
                               "spearman_sum_nontarget": V1.spearman([p["sum_nontarget"] for p in one], [p["acc_holdout"] for p in one])}
            per = {}
            for s in SEEDS:
                sp = {p["arm"]: p for p in one if p["seed"] == s}
                if "tf25" not in sp:
                    continue
                order = sorted(sp.values(), key=lambda p: -p["sum"])
                per[str(s)] = {"order": [(p["arm"], p["sum"], p["sum_target"], p["sum_nontarget"], p["acc_full"], p["target_ids"]) for p in order],
                               "tf25_above_other": sp["tf25"]["sum"] > sp["e3b2_A_target_other"]["sum"],
                               "tf25_above_dbbg": sp["tf25"]["sum"] > sp["e3b2_A_target_dbbg"]["sum"],
                               "tf25_rank": [p["arm"] for p in order].index("tf25") + 1}
            B["one_target"]["per_seed"] = per
            B["one_target"]["n_seeds_tf25_above_both"] = sum(v["tf25_above_other"] and v["tf25_above_dbbg"] for v in per.values())
            B["points"] = pts
            res["test_b"][ckpt][metric] = B
    json.dump(res, open(OUT / "results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_md(res, S)
    log("wrote v2 results.json / tables_ZH.md")


def f3(x, n=3):
    return "—" if x is None else ("%." + str(n) + "f") % x


def write_md(res, S):
    md = ["# 经验价值梯度打分 pilot v2（分叉 token 探针损失）：结果表", "",
          "生成：%s（Asia/Shanghai）。脚本 `scripts/p2_grad_utility_pilot_v2.py --phase analyze`；数字来自 `runs_ext_p2_grad_pilot/v2/scores_*.json`、v1 的 `scores_*.json`（对照列）与 P1 B1 逐题结果。"
          "变体：d1（主）= 分叉 token + 之后 1 个金标 token；d0 = 只有分叉 token；dall = 分叉 token 到第一轮结束。全对题三个变体都用关键 token（工具名 + 参数值）。" % res["generated"], ""]
    md += ["## 0. 打分点、用时与探针诊断", "", "| 打分点 | 种子 | 用时 s（其中探针生成+梯度） | 峰值 GB | 探针：分叉题数 / 全对题数 | 探针 d1 平均 CE fct / list_tables / median_nat / median_prose |", "|---|---|---|---|---|---|"]
    for (ckpt, s), d in sorted(S.items()):
        dg = res["probe_diagnostics"]["%s|%d" % (ckpt, s)]
        md.append("| %s | %s | %s（%s） | %s | %s | %s |" % (ckpt, str(s)[-2:], d["duration_seconds"], d["probe_seconds"], d["peak_gpu_gb"],
                  "；".join("%s %d/%d" % (k, v["n_diverged"], v["n_all_correct"]) for k, v in dg.items()),
                  " / ".join(f3(dg[k]["loss"]["d1"]) for k in PROBES)))
    md += ["", "分叉形态（金标 token → 模型 token，次数；前 6）：", ""]
    for key, dg in sorted(res["probe_diagnostics"].items()):
        md.append("- %s：%s" % (key, "；".join("%s：%s" % (k, "，".join("`%s`×%d" % (f.replace("\n", "\\n"), n) for f, n in v["diverge_forms"].items()) or "—") for k, v in dg.items())))
    md += ["", "## 1. 检验 (a)：fct 探针下各组余弦（实际进过计划的条目）", ""]
    for v in VARIANTS:
        md += ["### 变体 %s" % v, "", "| 打分点|种子 | target | near_sort | near_filter | db_other | python | file | calendar | target>近邻 win(sort/filter) | near_sort>背景 | near_filter>背景 | 均值顺序 | 余弦最高的模式 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for key, A in sorted(res["test_a"].items()):
            a = A[v]
            md.append("| %s | %s | %s / %s | %s | %s | %s | %s |" % (key, " | ".join(f3(a["groups"][g]["mean"]) if g in a["groups"] else "—" for g in GROUP_ORDER),
                      f3(a["win_target_vs_near_sort"]), f3(a["win_target_vs_near_filter"]), f3(a["win_near_sort_vs_bg"]), f3(a["win_near_filter_vs_bg"]),
                      "是" if a["order_holds_means"] else "否", "，".join("%s %s" % (k, f3(x)) for k, x in a["top_patterns"][:4])))
        md.append("")
    md += ["## 2. 合理性检查（list_tables 探针）", "", "| 打分点|种子 | " + " | ".join("%s：list_tables / 其它 / win" % v for v in VARIANTS) + " |", "|---|---|---|---|"]
    for key, d in sorted(res["sanity"].items()):
        md.append("| %s | %s |" % (key, " | ".join("%s / %s / %s" % (f3(d[v]["list_tables"]), f3(d[v]["other"]), f3(d[v]["win"])) for v in VARIANTS)))
    md += ["", "## 3. 检验 (b)：臂级外部检验（结果变量 = B1 nat v2 Database 留出半 15 题）", "",
           "partial = 先把 rank(成绩) 与 rank(打分) 各自对 rank(n_target) 回归取残差，再求残差相关（偏 Spearman）。v1 = 整条回答平均 CE 版本（对照）。", ""]
    for ckpt, D in res["test_b"].items():
        md += ["### 打分点 %s" % ckpt, "", "| 打分 | 点数 | n_target | sum | sum_nontarget | **偏：sum｜n_target** | **偏：sum_nontarget｜n_target** | 偏：sum_target｜n_target | n_target=1 层内 sum | 1-target 子集 sum / target / nontarget | tf25 同时高于两臂的种子数 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for metric, B in D.items():
            st = B["within_n_target_strata"].get("1", {})
            o = B["one_target"]
            md.append("| %s | %d | %s | %s | %s | %s | %s | %s | %s | %s / %s / %s | %d/3 |" % (metric, B["n_points"], f3(B["spearman_n_target"]), f3(B["spearman_sum"]),
                      f3(B["spearman_sum_nontarget"]), f3(B["partial_sum_given_n_target"]), f3(B["partial_sum_nontarget_given_n_target"]),
                      f3(B["partial_sum_target_given_n_target"]), f3(st.get("spearman_sum")), f3(o["spearman_sum"]), f3(o["spearman_sum_target"]),
                      f3(o["spearman_sum_nontarget"]), o["n_seeds_tf25_above_both"]))
        md += ["", "1-target 子集逐种子排序（d1，按 sum 降序：臂 sum〔target / 非 target〕实测全 30 题，target 条目）：", ""]
        for s, v in D["d1"]["one_target"]["per_seed"].items():
            md.append("- 种子 %s：%s；tf25 排第 %d" % (s[-2:], "；".join("%s %s〔%s / %s〕实测 %s，T-%s" % (a, f3(x), f3(t), f3(n), f3(acc), ",".join(ids))
                                                      for a, x, t, n, acc, ids in v["order"]), v["tf25_rank"]))
        md.append("")
    md += ["## 4. 单条 target 条目的价值（全部 11 条 filter_cmp_top 训练条目对 fct 探针的余弦）", ""]
    for ckpt in CKPTS:
        keys = [k for k in sorted(res["target_items"]) if k.startswith(ckpt + "|")]
        if not keys:
            continue
        ids = sorted(res["target_items"][keys[0]])
        md += ["### 打分点 %s" % ckpt, "", "| 条目 | " + " | ".join("%s d1 / dall / v1" % k.split("|")[1][-2:] for k in keys) + " |", "|---|" + "---|" * len(keys)]
        for i in ids:
            cells = []
            for k in keys:
                t = res["target_items"][k][i]
                cells.append("%s / %s / %s" % (f3(t["d1"]["cos"]), f3(t["dall"]["cos"]), f3(t.get("v1_full_mean", {}).get("cos"))))
            md.append("| %s | %s |" % (i.replace("database-train-target_db_filter_top-", "T-"), " | ".join(cells)))
        md += [""]
        for k in keys:
            s = k.split("|")[1]
            for v in ("d1", "dall"):
                ti = res["target_items"][k]
                order = sorted(ti, key=lambda i: -ti[i][v]["cos"])
                rk = lambda suf: order.index("database-train-target_db_filter_top-" + suf) + 1
                vals = [ti[i][v]["cos"] for i in order]
                md.append("- 种子 %s %s：11 条余弦范围 %s–%s；T-001 排第 %d（%s），T-005 第 %d（%s），T-008 第 %d（%s）" % (
                    s[-2:], v, f3(min(vals)), f3(max(vals)), rk("001"), f3(ti["database-train-target_db_filter_top-001"][v]["cos"]),
                    rk("005"), f3(ti["database-train-target_db_filter_top-005"][v]["cos"]), rk("008"), f3(ti["database-train-target_db_filter_top-008"][v]["cos"])))
        md.append("")
    md += ["## 5. 检验 (c)：py.median 同说法 vs 另一说法", "", "| 打分点|种子 | 探针 | " + " | ".join("%s natural / stats_median / 其它 Py；win" % v for v in VARIANTS) + " |", "|---|---|---|---|---|"]
    for key, d in sorted(res["test_c"].items()):
        for probe, dv in d.items():
            md.append("| %s | %s | %s |" % (key, probe, " | ".join("%s / %s / %s；%s" % (f3(dv[v]["natural"]), f3(dv[v]["stats_median"]), f3(dv[v]["other_py"]), f3(dv[v]["win_natural_vs_stats"])) for v in VARIANTS)))
    open(OUT / "tables_ZH.md", "w", encoding="utf-8").write("\n".join(md) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["score", "analyze", "smoke"], required=True)
    ap.add_argument("--ckpts", default="prefix,stage04")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    a.ckpts = [c for c in a.ckpts.split(",") if c]
    if a.phase == "score":
        score(a)
    elif a.phase == "smoke":  # 只做探针诊断（种子 08 prefix），不算候选，不写 v2 正式输出
        if V1.game_now() is not False:
            raise SystemExit("game")
        pr, _ = V1.probes()
        model, tok, dtype, cfg, info = V1.load_model(SEEDS[0], "prefix")
        for k, items in pr.items():
            for r in items[:3]:
                ids, labs, inf = decisive(model, tok, r, cfg)
                print(k, json.dumps({kk: inf[kk] for kk in inf if kk != "generated"}, ensure_ascii=False), "| GEN:", inf["generated"][:150])
    else:
        analyze(a)


if __name__ == "__main__":
    main()
