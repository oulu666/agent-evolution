#!/usr/bin/env python3
"""Patch p11_queue_20261118.restore_t0 only. Does not touch frozen prefixes or e3_train."""
from pathlib import Path

ROOT = Path("/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent")
PATH = ROOT / "fac_tinyagent" / "p11_queue_20261118.py"
OLD = """def restore_t0(model,seed):
    import torch
    state=torch.load(ROOT/f'runs_ext_e4/prefixes/A_seed{seed}/training_state.pt',map_location='cpu',weights_only=False)
    params={n:p for n,p in model.named_parameters() if p.requires_grad}
    if set(params)!=set(state['parameters']):
        raise ValueError('T0 parameter names mismatch')
    with torch.no_grad():
        for n,p in params.items():p.copy_(state['parameters'][n].to(p.device,dtype=p.dtype))
    model.eval();return state['parameter_hash']
"""
NEW = """def restore_t0(model,seed):
    # load_eval_model uses PeftModel.from_pretrained + model.eval(); the stage_03
    # adapter_config has inference_mode=true, so requires_grad is False for every
    # parameter including all 392 LoRA tensors. The E4 prefix names still match
    # model.named_parameters() exactly (base_model...lora_*.default.weight).
    # Compare against all named parameters, copy the prefix tensors, mark those
    # LoRA params trainable so the hash matches training-time _training_state_hash,
    # then return to eval. Never rewrite the frozen prefix file. Still fail hard
    # on name or hash mismatch.
    import torch
    from .replay_train import _training_state_hash
    state=torch.load(ROOT/f'runs_ext_e4/prefixes/A_seed{seed}/training_state.pt',map_location='cpu',weights_only=False)
    params=dict(model.named_parameters())
    missing=sorted(set(state['parameters'])-set(params))
    extra_lora=sorted(n for n in set(params)-set(state['parameters']) if 'lora_' in n)
    if missing or extra_lora:
        raise ValueError('T0 parameter names mismatch missing=%s extra_lora=%s'%(missing[:8],extra_lora[:8]))
    with torch.no_grad():
        for n,tensor in state['parameters'].items():
            p=params[n]
            p.copy_(tensor.to(device=p.device,dtype=p.dtype))
            p.requires_grad_(True)
    if _training_state_hash(model)!=state['parameter_hash']:
        raise ValueError('T0 parameter hash mismatch')
    model.eval();return state['parameter_hash']
"""
text = PATH.read_text(encoding="utf-8")
if NEW in text:
    print("already patched", PATH)
elif OLD not in text:
    raise SystemExit("expected restore_t0 block not found; refuse to patch")
else:
    PATH.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched", PATH)
if NEW not in PATH.read_text(encoding="utf-8"):
    raise SystemExit("patch did not land")
