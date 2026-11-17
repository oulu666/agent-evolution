"""[ext 2026-11-12 P1] Step 1 of the E3-B2 queue: batch-path diagnostics (no training).

Question: why do a few Calendar v3 `last_end` items flip between the official single-item
path (evaluate.generate_with_usage, used when evaluation.batch_size == 1) and the batched
path (evaluate.generate_batch_with_usage, batch_size >= 2)?

Three tests on runs_ext_e4/branches/A_seed20261108_tf50/checkpoint:
  T1  same single item through both generation functions (and a 2x(cache) x (left pad) grid
      with a re-implementation that is first checked to reproduce both functions bit-for-bit);
  T2  fixed target item, change only batch neighbours / order (identical copies, the exact
      P0 bs4 / bs32 batches, the historical E4 B32 batch, short vs long single neighbour);
  T3  answer-stage top-2 raw logits and margin at every generated step, plus the first step
      where the answer diverges from the Protocol-B1 answer.
Read-only on checkpoints and frozen exams.  Writes runs_ext_p1_batchdiag/ only.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs_ext_p1_batchdiag"
CKPT = ROOT / "runs_ext_e4" / "branches" / "A_seed20261108_tf50" / "checkpoint"
CV3_ROWS = ROOT / "data_ext_cal_v3" / "final_v3" / "calendar_v3.jsonl"
P0_BS = {b: ROOT / "runs_ext_p0_batched" / ("bs%d" % b) / "calendar_v3" / "results.jsonl" for b in (1, 2, 4, 32)}
HIST = ROOT / "runs_ext_calv3" / "evaluation" / "E4_A_seed20261108_tf50" / "calendar_v3" / "results.jsonl"
FOCUS = ["calv3-final-last_end-008", "calv3-final-last_end-024"]
CONTROLS = ["calv3-final-last_end-000", "calv3-final-last_end-016"]
SEED = 20261108


def log(msg: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def _read_jsonl(p: Path) -> List[Dict[str, Any]]:
    with open(p, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def answer_conv(row: Dict[str, Any], tool_raw: str, observation: str) -> List[Dict[str, str]]:
    base = [row["messages"][0], row["messages"][1]]
    return base + [{"role": "assistant", "content": tool_raw if tool_raw else "{}"},
                   {"role": "user", "content": "TOOL RESULT:\n" + observation}]


def low_gen(model, tok, convs, max_new: int, use_cache: Optional[bool], extra_left_pad: int = 0,
            want_trace: bool = True) -> List[Dict[str, Any]]:
    """Left-padded greedy generation returning text + per-step top-2 raw logits for every row."""
    import torch
    from .sft.dataset import conversation_text
    from .sft.evaluate import _eos_ids
    texts = [conversation_text(tok, m, generation=True) for m in convs]
    prev = tok.padding_side
    try:
        tok.padding_side = "left"
        enc = tok(texts, return_tensors="pt", add_special_tokens=False, padding=True)
    finally:
        tok.padding_side = prev
    pad_id = tok.pad_token_id or tok.eos_token_id
    if extra_left_pad:
        n = enc["input_ids"].shape[0]
        enc["input_ids"] = torch.cat([torch.full((n, extra_left_pad), pad_id, dtype=enc["input_ids"].dtype),
                                      enc["input_ids"]], dim=1)
        enc["attention_mask"] = torch.cat([torch.zeros((n, extra_left_pad), dtype=enc["attention_mask"].dtype),
                                           enc["attention_mask"]], dim=1)
    enc = {k: v.to("cuda") for k, v in enc.items()}
    eos = _eos_ids(tok)
    kw = dict(max_new_tokens=max_new, do_sample=False, pad_token_id=pad_id, eos_token_id=eos,
              return_dict_in_generate=True, output_logits=True)
    if use_cache is not None:
        kw["use_cache"] = use_cache
    with torch.no_grad():
        out = model.generate(**enc, **kw)
    width = enc["input_ids"].shape[1]
    res = []
    for i in range(len(convs)):
        ids = out.sequences[i][width:].tolist()
        cut = len(ids)
        for j, t in enumerate(ids):
            if t in eos:
                cut = j + 1
                break
        ids = ids[:cut]
        text = tok.decode(ids, skip_special_tokens=True).strip()
        trace = []
        if want_trace:
            for s in range(len(ids)):
                lg = out.logits[s][i].float()
                v, ix = torch.topk(lg, 2)
                trace.append({"step": s, "chosen": int(ids[s]), "chosen_tok": tok.decode([ids[s]]),
                              "top1": int(ix[0]), "top1_tok": tok.decode([int(ix[0])]), "top1_logit": float(v[0]),
                              "top2": int(ix[1]), "top2_tok": tok.decode([int(ix[1])]), "top2_logit": float(v[1]),
                              "margin": float(v[0] - v[1])})
        n_pad = int(width - enc["attention_mask"][i].sum().item())
        res.append({"text": text, "token_ids": ids, "n_left_pad": n_pad, "trace": trace})
    return res


def first_divergence(a: List[int], b: List[int]) -> Optional[int]:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    from .p0_run import refuse_if_game
    from .replay_study import config_for
    from .sft.evaluate import (free_model, generate_batch_with_usage, generate_with_usage, load_eval_model,
                               parse_final_answer, _evaluate_tool_prediction)
    from .metrics import answers_equal
    from .utils import ensure_dir, sha256_file, write_json
    if (OUT / "DONE").exists() and not a.force:
        log("batchdiag already DONE; skip")
        return
    ensure_dir(OUT)
    res_path = OUT / "diag_results.jsonl"
    if res_path.exists():
        res_path.unlink()
    refuse_if_game()
    rows = _read_jsonl(CV3_ROWS)
    by_id = {r["episode_id"]: r for r in rows}
    order = [r["episode_id"] for r in rows]
    p0 = {b: {r["episode_id"]: r for r in _read_jsonl(p)} for b, p in P0_BS.items()}
    hist = {r["episode_id"]: r for r in _read_jsonl(HIST)}
    config = config_for("A", SEED, batch_size=1)
    mx_tool = int(config["evaluation"]["max_new_tokens_tool"])
    mx_ans = int(config["evaluation"]["max_new_tokens_answer"])
    started = time.time()
    model, tok = load_eval_model(config, str(CKPT))
    meta = {"checkpoint": str(CKPT), "adapter_sha256": sha256_file(CKPT / "adapter_model.safetensors"),
            "calendar_v3_rows_sha256": sha256_file(CV3_ROWS),
            "model_config_use_cache": getattr(model.config, "use_cache", None),
            "generation_config_use_cache": getattr(getattr(model, "generation_config", None), "use_cache", None),
            "attn_implementation": getattr(model.config, "_attn_implementation", None),
            "pad_token_id": tok.pad_token_id, "eos_token_id": tok.eos_token_id,
            "started": time.strftime("%Y-%m-%d %H:%M:%S %z")}
    try:
        import torch, transformers, peft
        meta.update({"torch": torch.__version__, "transformers": transformers.__version__,
                     "peft": peft.__version__, "gpu": torch.cuda.get_device_name(0)})
    except Exception:
        pass
    log("meta %s" % json.dumps(meta))
    records: List[Dict[str, Any]] = []

    def score(row, text):
        ok, pred = parse_final_answer(text)
        return bool(ok and answers_equal(row["expected_final_answer"], pred)), pred

    def emit(rec):
        records.append(rec)
        with open(res_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    obs_cache: Dict[str, Dict[str, Any]] = {}
    for eid in FOCUS + CONTROLS:
        refuse_if_game()
        row = by_id[eid]
        base = [row["messages"][0], row["messages"][1]]
        # ---- T1 tool stage through both official functions
        t_bs1, _ = generate_with_usage(model, tok, base, mx_tool)
        t_bf = generate_batch_with_usage(model, tok, [base], mx_tool)[0][0]
        tr = _evaluate_tool_prediction(row, t_bs1, str(ROOT / "data_phase2" / "fixtures" / "toolbench.db"),
                                       str(ROOT / "data_ext_cal_v3" / "fixtures" / "calendar_v3.json"))
        obs_cache[eid] = {"tool_raw": t_bs1, "observation": tr["observation"]}
        emit({"test": "T1", "stage": "tool", "item": eid, "cond": "bs1_fn_vs_batch_fn_single",
              "bs1_text": t_bs1, "batchfn_text": t_bf, "same_text": t_bs1 == t_bf,
              "tool_correct": tr["tool_correct"], "arguments_correct": tr["arguments_correct"]})
        conv = answer_conv(row, t_bs1, tr["observation"])
        # ---- T1 answer stage
        a_bs1, _ = generate_with_usage(model, tok, conv, mx_ans)
        a_bf = generate_batch_with_usage(model, tok, [conv], mx_ans)[0][0]
        ref = low_gen(model, tok, [conv], mx_ans, use_cache=None)[0]
        ok1, p1 = score(row, a_bs1)
        okb, pb = score(row, a_bf)
        emit({"test": "T1", "stage": "answer", "item": eid, "cond": "official_bs1_fn",
              "text": a_bs1, "pred": p1, "correct": ok1, "n_left_pad": 0,
              "p0_bs1_answer": p0[1].get(eid, {}).get("answer_raw"),
              "historical_b32_answer": hist.get(eid, {}).get("answer_raw"),
              "expected": row["expected_final_answer"]})
        emit({"test": "T1", "stage": "answer", "item": eid, "cond": "official_batch_fn_single",
              "text": a_bf, "pred": pb, "correct": okb, "n_left_pad": 0, "same_as_bs1": a_bf == a_bs1})
        ref_ids = ref["token_ids"]
        grid = [("lowgen_default_cache_nopad", None, 0), ("lowgen_cacheTrue_nopad", True, 0),
                ("lowgen_cacheFalse_nopad", False, 0)]
        for padn in (8, 32, 128):
            grid += [("lowgen_cacheTrue_pad%d" % padn, True, padn), ("lowgen_cacheFalse_pad%d" % padn, False, padn)]
        for name, uc, padn in grid:
            g = ref if name == "lowgen_default_cache_nopad" else low_gen(model, tok, [conv], mx_ans, uc, padn)[0]
            ok, pr = score(row, g["text"])
            div = first_divergence(ref_ids, g["token_ids"])
            emit({"test": "T1", "stage": "answer", "item": eid, "cond": name, "use_cache": uc, "extra_left_pad": padn,
                  "text": g["text"], "pred": pr, "correct": ok, "n_left_pad": g["n_left_pad"],
                  "same_as_official_bs1": g["text"] == a_bs1, "same_as_official_batchfn": g["text"] == a_bf,
                  "first_divergence_vs_default": div,
                  "trace": g["trace"]})
        # ---- T2 identical copies (no padding, only batch shape)
        for n in (2, 4, 8, 32):
            g = low_gen(model, tok, [conv] * n, mx_ans, True)
            texts = [x["text"] for x in g]
            ok, pr = score(row, g[0]["text"])
            emit({"test": "T2", "stage": "answer", "item": eid, "cond": "identical_copies_n%d" % n,
                  "text": g[0]["text"], "pred": pr, "correct": ok, "all_rows_same": len(set(texts)) == 1,
                  "row_texts": sorted(set(texts)), "n_left_pad": g[0]["n_left_pad"],
                  "first_divergence_vs_default": first_divergence(ref_ids, g[0]["token_ids"]),
                  "trace": g[0]["trace"]})
    # ---- T2 real neighbours, only answer stage, neighbours' tool outputs taken from the run being replayed
    def batch_conv(ids, src):
        out = []
        for i in ids:
            r = src[i]
            out.append(answer_conv(by_id[i], r["tool_call_raw"], r["observation"]))
        return out

    le = [i for i in order if "last_end" in i]
    p0_bs4_batch = ["calv3-final-last_end-000", "calv3-final-last_end-008", "calv3-final-last_end-016",
                    "calv3-final-last_end-024"]  # probe order: last 4 calendar rows = one bs4 batch
    probe_cal = [r for r in _read_jsonl(ROOT / "data_ext_p0_batched" / "probe.jsonl") if r.get("p0_fixture") == "calendar_v3"]
    p0_bs32_batch = [r["episode_id"] for r in probe_cal]
    hist_batch = order[128:150]
    for eid in p0_bs4_batch:
        assert eid in p0_bs32_batch
    lens = {i: len(json.dumps(batch_conv([i], hist)[0], ensure_ascii=False)) for i in order if i in hist}
    short_n = min(lens, key=lambda k: lens[k])
    long_n = max(lens, key=lambda k: lens[k])
    scen = []
    for tgt in FOCUS:
        scen.append(("p0_bs4_original", p0_bs4_batch, p0[4], tgt))
        scen.append(("p0_bs4_reversed", list(reversed(p0_bs4_batch)), p0[4], tgt))
        others = [x for x in p0_bs4_batch if x != tgt]
        scen.append(("p0_bs4_target_first", [tgt] + others, p0[4], tgt))
        scen.append(("p0_bs4_target_last", others + [tgt], p0[4], tgt))
        scen.append(("p0_bs32probe_original", p0_bs32_batch, p0[32], tgt))
        scen.append(("p0_bs32probe_reversed", list(reversed(p0_bs32_batch)), p0[32], tgt))
        scen.append(("hist_b32_original", hist_batch, hist, tgt))
        scen.append(("hist_b32_reversed", list(reversed(hist_batch)), hist, tgt))
        scen.append(("pair_short_neighbour_after", [tgt, short_n], hist, tgt))
        scen.append(("pair_short_neighbour_before", [short_n, tgt], hist, tgt))
        scen.append(("pair_long_neighbour_after", [tgt, long_n], hist, tgt))
        scen.append(("pair_long_neighbour_before", [long_n, tgt], hist, tgt))
    ref_by_item = {r["item"]: r for r in records if r.get("cond") == "lowgen_default_cache_nopad"}
    for name, ids, src, tgt in scen:
        refuse_if_game()
        convs = batch_conv(ids, src)
        # the target's own tool output must equal the B1 tool output, otherwise the comparison is not answer-only
        same_tool = src[tgt]["tool_call_raw"] == obs_cache[tgt]["tool_raw"] and src[tgt]["observation"] == obs_cache[tgt]["observation"]
        g = low_gen(model, tok, convs, mx_ans, True)
        k = ids.index(tgt)
        ok, pr = score(by_id[tgt], g[k]["text"])
        emit({"test": "T2", "stage": "answer", "item": tgt, "cond": name, "batch_ids": ids, "target_index": k,
              "batch_size": len(ids), "target_tool_same_as_b1": same_tool,
              "text": g[k]["text"], "pred": pr, "correct": ok, "n_left_pad": g[k]["n_left_pad"],
              "replayed_run_answer": src[tgt].get("answer_raw"),
              "reproduces_replayed_run": g[k]["text"] == src[tgt].get("answer_raw"),
              "first_divergence_vs_default": first_divergence(ref_by_item[tgt]["trace"] and [t["chosen"] for t in ref_by_item[tgt]["trace"]], g[k]["token_ids"]),
              "trace": g[k]["trace"]})
        log("T2 %s %s pad=%d -> %s (%s)" % (tgt[-3:], name, g[k]["n_left_pad"], g[k]["text"], ok))
    free_model(model)
    # ---- summary (T3 = margins at divergence)
    summ: Dict[str, Any] = {"meta": meta, "duration_seconds": round(time.time() - started, 1), "items": {}}
    for eid in FOCUS + CONTROLS:
        rs = [r for r in records if r["item"] == eid and r["stage"] == "answer"]
        ref_tr = next(r for r in rs if r["cond"] == "lowgen_default_cache_nopad")["trace"]
        div_steps = sorted({r["first_divergence_vs_default"] for r in rs
                            if r.get("first_divergence_vs_default") is not None})
        min_margin = min(ref_tr, key=lambda t: t["margin"]) if ref_tr else None
        conds = []
        for r in rs:
            d = r.get("first_divergence_vs_default")
            tr = r.get("trace") or []
            at = None
            if d is not None and d < len(tr):
                t = tr[d]
                at = {"step": d, "top1_tok": t["top1_tok"], "top2_tok": t["top2_tok"], "margin": round(t["margin"], 4)}
            ref_at = None
            if d is not None and d < len(ref_tr):
                t = ref_tr[d]
                ref_at = {"step": d, "top1_tok": t["top1_tok"], "top2_tok": t["top2_tok"], "margin": round(t["margin"], 4)}
            conds.append({"cond": r["cond"], "text": r.get("text"), "correct": r.get("correct"),
                          "n_left_pad": r.get("n_left_pad"), "batch_size": r.get("batch_size"),
                          "diverges_at": d, "this_run_at_div": at, "b1_at_div": ref_at,
                          "reproduces_replayed_run": r.get("reproduces_replayed_run"),
                          "same_as_official_bs1": r.get("same_as_official_bs1"),
                          "same_as_bs1": r.get("same_as_bs1")})
        summ["items"][eid] = {
            "expected": by_id[eid]["expected_final_answer"],
            "b1_answer": next(r for r in rs if r["cond"] == "official_bs1_fn")["text"],
            "b1_min_margin_step": min_margin,
            "b1_trace_margins": [round(t["margin"], 4) for t in ref_tr],
            "divergence_steps_seen": div_steps,
            "n_conditions": len(conds), "n_differ_from_b1": sum(c["diverges_at"] is not None for c in conds),
            "conditions": conds}
    write_json(OUT / "summary.json", summ)
    (OUT / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
    log("batchdiag done in %.1fs" % (time.time() - started))


if __name__ == "__main__":
    main()
