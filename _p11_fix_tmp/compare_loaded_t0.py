#!/usr/bin/env python3
"""Load eval model (short GPU/CPU occupancy) and compare T0 parameter name sets.
Does not run evaluation or training. Writes a JSON report and exits.
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path

os.environ.update(
    PYTHONDONTWRITEBYTECODE="1",
    PYTHONUNBUFFERED="1",
    HF_HUB_OFFLINE="1",
    TOKENIZERS_PARALLELISM="false",
    TZ="Asia/Shanghai",
)

ROOT = Path("/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent")
sys.path.insert(0, str(ROOT))
SEED = 20261108
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "_p11_fix_tmp" / "t0_name_compare_loaded.json"))

def main():
    import torch
    from fac_tinyagent.replay_study import config_for
    from fac_tinyagent.sft.evaluate import load_eval_model, free_model
    from fac_tinyagent.e4_run import start_adapter
    from fac_tinyagent.replay_train import _training_state_hash

    started = time.time()
    cfg = config_for("A", SEED, batch_size=1)
    cfg["evaluation"]["batch_size"] = 1
    adapter = start_adapter(SEED)
    state_path = ROOT / f"runs_ext_e4/prefixes/A_seed{SEED}/training_state.pt"
    print(time.strftime("%F %T %z"), "LOAD", adapter, flush=True)
    print("cuda", torch.cuda.is_available(), "device", torch.cuda.get_device_name(0) if torch.cuda.is_available() else None, flush=True)
    model, tok = load_eval_model(cfg, str(adapter))
    print(time.strftime("%F %T %z"), "LOADED training_flag", model.training, "type", type(model).__name__, flush=True)

    all_named = list(model.named_parameters())
    all_names = [n for n, _ in all_named]
    req_names = [n for n, p in all_named if p.requires_grad]
    frozen_names = [n for n, p in all_named if not p.requires_grad]
    lora_names = [n for n, _ in all_named if "lora_" in n]
    lora_req = [n for n, p in all_named if "lora_" in n and p.requires_grad]

    state = torch.load(state_path, map_location="cpu", weights_only=False)
    state_names = list(state["parameters"].keys())
    sset, aset, rset = set(state_names), set(all_names), set(req_names)

    report = {
        "time": time.strftime("%F %T %z"),
        "seed": SEED,
        "adapter": str(adapter),
        "state_path": str(state_path),
        "model_type": type(model).__name__,
        "model_training_flag": bool(model.training),
        "n_named_parameters": len(all_names),
        "n_requires_grad": len(req_names),
        "n_frozen": len(frozen_names),
        "n_lora": len(lora_names),
        "n_lora_requires_grad": len(lora_req),
        "n_state_parameters": len(state_names),
        "requires_grad_sample": req_names[:20],
        "lora_sample": lora_names[:8],
        "state_sample": state_names[:8],
        "current_restore_t0_check": {
            "compares": "set(requires_grad named_parameters) == set(state[parameters])",
            "equal": rset == sset,
            "only_in_requires_grad": sorted(rset - sset),
            "only_in_state": sorted(sset - rset)[:40],
            "n_only_in_requires_grad": len(rset - sset),
            "n_only_in_state": len(sset - rset),
        },
        "all_named_vs_state": {
            "state_subset_of_all_named": sset <= aset,
            "only_in_state": sorted(sset - aset)[:40],
            "n_only_in_state": len(sset - aset),
            "n_model_names_not_in_state": len(aset - sset),
            "model_not_in_state_lora": sorted(n for n in (aset - sset) if "lora_" in n)[:40],
        },
        "inference_mode_related": {
            "peft_inference_mode": getattr(getattr(model, "peft_config", {}).get("default", None), "inference_mode", None) if hasattr(model, "peft_config") else None,
            "active_adapters": list(getattr(model, "active_adapters", []) or []),
        },
    }

    # Diagnostic only: try experiment_b-style restore + hash, then restore eval flag.
    # This does not write weights or start training.
    missing = sset - aset
    hash_before = None
    hash_after = None
    hash_ok = False
    restore_error = None
    if not missing:
        try:
            params = dict(all_named)
            with torch.no_grad():
                for name, tensor in state["parameters"].items():
                    parameter = params[name]
                    parameter.copy_(tensor.to(device=parameter.device, dtype=parameter.dtype))
                    parameter.requires_grad_(True)
            hash_after = _training_state_hash(model)
            hash_ok = hash_after == state["parameter_hash"]
            model.eval()
        except Exception as e:
            restore_error = "%s: %s" % (type(e).__name__, e)
    report["experiment_b_style_restore"] = {
        "attempted": not bool(missing),
        "parameter_hash_expected": state["parameter_hash"],
        "parameter_hash_after": hash_after,
        "hash_matches": hash_ok,
        "restore_error": restore_error,
        "note": "copy state tensors into matching named_parameters, set requires_grad True, hash trainable params, then model.eval()",
    }
    report["seconds"] = round(time.time() - started, 3)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("wrote", OUT, flush=True)
    free_model(model)
    if tok is not None:
        del tok
    return 0 if (sset <= aset) else 2

if __name__ == "__main__":
    raise SystemExit(main())
