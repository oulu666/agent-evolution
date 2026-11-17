"""[ext-paper 2026-11-10] General-ability evaluation (lm-evaluation-harness) for a
base model or base+LoRA adapter, loaded exactly like the FAC-TinyAgent eval path:
4-bit NF4 + double quant, compute dtype bf16 (auto), device_map {"":0}, then
PeftModel.from_pretrained(adapter) (not merged).  Use --precision bf16 to load
the base without quantization for comparison.

Run with the fac-eval venv (see scripts/eval_general.sh).
"""
from __future__ import annotations

import argparse
import inspect
import json
import time
from pathlib import Path


def build_model(args):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    compute = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    kwargs = dict(device_map={"": 0}, trust_remote_code=True)
    if args.precision == "4bit":
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=compute)
    else:
        kwargs["dtype"] = compute
    model = AutoModelForCausalLM.from_pretrained(args.model, **kwargs)
    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()
    return model, tokenizer, str(compute)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--tasks", default="arc_easy,ifeval")
    parser.add_argument("--limit", type=float, default=None)
    parser.add_argument("--batch-size", default="8")
    parser.add_argument("--precision", choices=["4bit", "bf16"], default="4bit")
    parser.add_argument("--chat-template", action="store_true",
                        help="apply the model chat template (thinking disabled)")
    parser.add_argument("--max-gen-toks", type=int, default=None,
                        help="override generation length for generative tasks")
    parser.add_argument("--num-fewshot", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--output", required=True)
    parser.add_argument("--log-samples", action="store_true",
                        help="save per-sample records to samples.json (off by default)")
    args = parser.parse_args()

    import torch
    import lm_eval
    from lm_eval.models.huggingface import HFLM

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    torch.cuda.reset_peak_memory_stats()
    model, tokenizer, compute = build_model(args)
    lm_kwargs = dict(pretrained=model, tokenizer=tokenizer, batch_size=args.batch_size,
                     trust_remote_code=True)
    if args.chat_template and "enable_thinking" in inspect.signature(HFLM.__init__).parameters:
        lm_kwargs["enable_thinking"] = False
    lm = HFLM(**lm_kwargs)
    eval_kwargs = dict(model=lm, tasks=[t.strip() for t in args.tasks.split(",") if t.strip()],
                       limit=args.limit, num_fewshot=args.num_fewshot,
                       random_seed=args.seed, numpy_random_seed=args.seed,
                       torch_random_seed=args.seed, fewshot_random_seed=args.seed,
                       log_samples=args.log_samples)
    if args.chat_template:
        eval_kwargs["apply_chat_template"] = True
    if args.max_gen_toks:
        eval_kwargs["gen_kwargs"] = "max_gen_toks=%d" % args.max_gen_toks
    accepted = inspect.signature(lm_eval.simple_evaluate).parameters
    eval_kwargs = {k: v for k, v in eval_kwargs.items() if k in accepted}
    results = lm_eval.simple_evaluate(**eval_kwargs)
    elapsed = round(time.time() - started, 1)
    payload = {
        "model": args.model, "adapter": args.adapter, "precision": args.precision,
        "compute_dtype": compute, "tasks": args.tasks, "limit": args.limit,
        "chat_template": args.chat_template, "max_gen_toks": args.max_gen_toks,
        "seed": args.seed, "wall_seconds": elapsed,
        "peak_gpu_gb": round(torch.cuda.max_memory_allocated() / 1024 ** 3, 3),
        "lm_eval_version": getattr(lm_eval, "__version__", "?"),
        "results": results.get("results"),
        "n_samples": results.get("n-samples"),
        "configs": {k: {kk: v.get(kk) for kk in ("num_fewshot", "generation_kwargs", "metric_list")}
                    for k, v in (results.get("configs") or {}).items()},
    }
    payload["log_samples"] = bool(args.log_samples)
    (out / "results.json").write_text(json.dumps(payload, indent=2, default=str),
                                      encoding="utf-8")
    if args.log_samples:
        samples = results.get("samples")
        (out / "samples.json").write_text(json.dumps(samples, default=str),
                                          encoding="utf-8")
        n = 0
        if isinstance(samples, dict):
            n = sum(len(v) if isinstance(v, list) else 0 for v in samples.values())
        print("wrote samples.json n=%s" % n, flush=True)
    print(json.dumps({"results": payload["results"], "wall_seconds": elapsed,
                      "peak_gpu_gb": payload["peak_gpu_gb"]}, indent=2, default=str))


if __name__ == "__main__":
    main()
