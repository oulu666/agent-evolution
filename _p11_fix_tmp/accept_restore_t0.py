#!/usr/bin/env python3
"""Short load acceptance: seed 20261108 T0 restore via the patched restore_t0."""
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
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "_p11_fix_tmp" / "t0_restore_accept.json"))

def main():
    import torch
    from fac_tinyagent.replay_study import config_for
    from fac_tinyagent.sft.evaluate import load_eval_model, free_model
    from fac_tinyagent.e4_run import start_adapter
    from fac_tinyagent.p11_queue_20261118 import restore_t0
    from fac_tinyagent.replay_train import _training_state_hash

    started = time.time()
    cfg = config_for("A", SEED, batch_size=1)
    cfg["evaluation"]["batch_size"] = 1
    print(time.strftime("%F %T %z"), "ACCEPT LOAD", flush=True)
    model, tok = load_eval_model(cfg, str(start_adapter(SEED)))
    n_req_before = sum(p.requires_grad for _, p in model.named_parameters())
    ph = restore_t0(model, SEED)
    n_req_after = sum(p.requires_grad for _, p in model.named_parameters())
    # restore_t0 returns to eval(); hash uses requires_grad, so temporarily mark
    # the same LoRA names to confirm weights still match the prefix hash.
    state = torch.load(ROOT / f"runs_ext_e4/prefixes/A_seed{SEED}/training_state.pt", map_location="cpu", weights_only=False)
    params = dict(model.named_parameters())
    for n in state["parameters"]:
        params[n].requires_grad_(True)
    live = _training_state_hash(model)
    model.eval()
    report = {
        "time": time.strftime("%F %T %z"),
        "seed": SEED,
        "passed": ph == state["parameter_hash"] == live,
        "t0_parameter_hash": ph,
        "expected_parameter_hash": state["parameter_hash"],
        "live_hash_after_restore": live,
        "n_requires_grad_before_restore": n_req_before,
        "n_requires_grad_after_restore_eval": n_req_after,
        "model_training_flag_after": bool(model.training),
        "n_state_parameters": len(state["parameters"]),
        "seconds": round(time.time() - started, 3),
        "note": "Calls patched restore_t0 only; does not train, evaluate tasks, or write the prefix.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    free_model(model)
    if tok is not None:
        del tok
    if not report["passed"]:
        raise SystemExit("T0 restore acceptance failed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
