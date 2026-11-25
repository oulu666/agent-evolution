#!/usr/bin/env python3
"""CPU-only dump of E4 prefix training_state parameter names vs stage_03 adapter keys."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from pathlib import Path

ROOT = Path("/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent")
SEED = 20261108
STATE = ROOT / f"runs_ext_e4/prefixes/A_seed{SEED}/training_state.pt"
ADAPTER = ROOT / f"runs_phase2/A_seed{SEED}/checkpoints/stage_03_python/adapter_model.safetensors"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "runs_ext_p11_eaar_v1" / "t0_name_dump_cpu.json"))

def prefixes(names, depth=6):
    c = Counter()
    for n in names:
        parts = n.split(".")
        c[".".join(parts[:depth])] += 1
    return c.most_common(30)

def summarize(names):
    names = list(names)
    lora = [n for n in names if "lora_" in n]
    other = [n for n in names if "lora_" not in n]
    kinds = Counter()
    for n in names:
        if "lora_A" in n: kinds["lora_A"] += 1
        elif "lora_B" in n: kinds["lora_B"] += 1
        elif "modules_to_save" in n: kinds["modules_to_save"] += 1
        else: kinds["other"] += 1
    defaultish = sum("default" in n.split(".") for n in names)
    return {
        "n": len(names),
        "kinds": dict(kinds),
        "n_with_default_segment": defaultish,
        "sample_head": names[:25],
        "sample_tail": names[-10:],
        "other_names": other,
        "unique_suffixes": sorted({n.split(".")[-1] for n in names}),
        "unique_lora_patterns": sorted({ ".".join(p for p in n.split(".") if "lora" in p or p in {"default","modules_to_save"} or p.startswith("lora")) for n in lora })[:40],
    }

def main():
    import torch
    print("loading", STATE, flush=True)
    state = torch.load(STATE, map_location="cpu", weights_only=False)
    state_names = sorted(state["parameters"].keys())
    shapes = {n: list(state["parameters"][n].shape) for n in state_names}
    out = {
        "state_path": str(STATE),
        "state_keys_top": sorted(state.keys()),
        "parameter_hash": state.get("parameter_hash"),
        "n_state_params": len(state_names),
        "state_summary": summarize(state_names),
        "state_shape_histogram": {str(k): v for k,v in Counter(tuple(shapes[n]) for n in state_names).items()},
        "state_name_prefixes": [{"prefix": p, "n": c} for p,c in prefixes(state_names)],
    }
    if ADAPTER.exists():
        from safetensors import safe_open
        with safe_open(str(ADAPTER), framework="pt", device="cpu") as f:
            adapter_names = sorted(f.keys())
        out["adapter_path"] = str(ADAPTER)
        out["adapter_summary"] = summarize(adapter_names)
        out["only_in_state_vs_adapter"] = sorted(set(state_names) - set(adapter_names))[:80]
        out["only_in_adapter_vs_state"] = sorted(set(adapter_names) - set(state_names))[:80]
        out["n_only_in_state_vs_adapter"] = len(set(state_names) - set(adapter_names))
        out["n_only_in_adapter_vs_state"] = len(set(adapter_names) - set(state_names))
        # also compare stripped prefixes
        def norm(n):
            n2 = n
            for a,b in [
                ("base_model.model.model.", "model."),
                ("base_model.model.", "model."),
            ]:
                if n2.startswith(a):
                    n2 = b + n2[len(a):]
                    break
            return n2
        ns, na = {norm(n) for n in state_names}, {norm(n) for n in adapter_names}
        out["normalized_only_state"] = sorted(ns-na)[:40]
        out["normalized_only_adapter"] = sorted(na-ns)[:40]
        out["n_normalized_only_state"] = len(ns-na)
        out["n_normalized_only_adapter"] = len(na-ns)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print("wrote", OUT)
    print(json.dumps({k: out[k] for k in out if k not in {"state_summary","adapter_summary","only_in_state_vs_adapter","only_in_adapter_vs_state","state_name_prefixes","normalized_only_state","normalized_only_adapter"}}, indent=2))
    print("STATE sample head:")
    for n in state_names[:15]:
        print(" ", n, shapes[n])
    if "adapter_summary" in out:
        print("ADAPTER sample head:")
        for n in out["adapter_summary"]["sample_head"][:15]:
            print(" ", n)
        print("n only in state vs adapter", out["n_only_in_state_vs_adapter"])
        print("n only in adapter vs state", out["n_only_in_adapter_vs_state"])

if __name__ == "__main__":
    main()
