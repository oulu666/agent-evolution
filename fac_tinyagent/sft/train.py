"""QLoRA SFT for one sequential tool-learning stage."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
from torch.utils.data import DataLoader

from ..utils import (append_jsonl, ensure_dir, gpu_peak_gb, gpu_reset_peak,
                     now_iso, read_jsonl, set_seed, write_json, write_oom_report)
from .dataset import ChatDataset, DataCollator


def _compute_dtype(name: str) -> torch.dtype:
    if name == "bf16":
        return torch.bfloat16
    if name == "fp16":
        return torch.float16
    if name == "auto":
        if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
            return torch.bfloat16
        return torch.float16
    return torch.float32


def load_tokenizer(config: Dict[str, Any]):
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        config["model_name_or_path"],
        trust_remote_code=config.get("trust_remote_code", True))
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    return tokenizer


def load_base_model(config: Dict[str, Any]):
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig
    dtype = _compute_dtype(config["quantization"].get("bnb_4bit_compute_dtype", "auto"))
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=dtype,
    )
    model = AutoModelForCausalLM.from_pretrained(
        config["model_name_or_path"],
        quantization_config=quantization,
        device_map={"": 0},
        trust_remote_code=config.get("trust_remote_code", True),
    )
    model.config.use_cache = False
    return model, dtype


def _attach_adapter(model, config: Dict[str, Any], previous_adapter: Optional[str]):
    from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
    if config["training"].get("gradient_checkpointing", True):
        model.gradient_checkpointing_enable()
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=config["training"].get(
            "gradient_checkpointing", True))
    if previous_adapter:
        model = PeftModel.from_pretrained(model, previous_adapter, is_trainable=True)
    else:
        lora = config["lora"]
        model = get_peft_model(model, LoraConfig(
            r=int(lora["r"]),
            lora_alpha=int(lora["alpha"]),
            lora_dropout=float(lora["dropout"]),
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=list(lora["target_modules"]),
        ))
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    return model


def _make_loader(rows: List[Dict[str, Any]], tokenizer, max_length: int,
                 batch_size: int, shuffle: bool, seed: int):
    dataset = ChatDataset(rows, tokenizer, max_length)
    generator = torch.Generator()
    generator.manual_seed(seed)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle,
                      collate_fn=DataCollator(tokenizer), generator=generator)


def evaluate_loss(model, loader) -> Optional[float]:
    if len(loader.dataset) == 0:
        return None
    model.eval()
    total_loss = 0.0
    total_tokens = 0
    with torch.no_grad():
        for batch in loader:
            batch = {key: value.to("cuda") for key, value in batch.items()}
            outputs = model(**batch)
            tokens = int((batch["labels"] != -100).sum().item())
            total_loss += float(outputs.loss.item()) * tokens
            total_tokens += tokens
    model.train()
    if total_tokens == 0:
        return None
    return total_loss / total_tokens


def train_stage(config: Dict[str, Any], stage: Dict[str, Any],
                train_path: str, val_path: str, previous_adapter: Optional[str],
                output_dir: str) -> Dict[str, Any]:
    from bitsandbytes.optim import PagedAdamW8bit

    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Refusing to overwrite checkpoint: %s" % output_dir)
    ensure_dir(output_dir)
    set_seed(int(config["seed"]))
    tokenizer = load_tokenizer(config)
    model, dtype = load_base_model(config)
    model = _attach_adapter(model, config, previous_adapter)
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = PagedAdamW8bit(trainable, lr=float(config["training"]["learning_rate"]))
    train_rows = read_jsonl(train_path)
    val_rows = read_jsonl(val_path)
    if not train_rows:
        raise ValueError("Empty training split: %s" % train_path)
    print("train", stage["name"], "family", stage["family"],
          "samples", len(train_rows), "val", len(val_rows), flush=True)
    max_length = int(config["training"]["max_seq_length"])
    batch_size = int(config["training"]["batch_size"])
    accumulation = int(config["training"]["gradient_accumulation_steps"])
    epochs = int(config["training"]["num_epochs"])
    train_loader = _make_loader(train_rows, tokenizer, max_length, batch_size,
                                True, int(config["seed"]))
    val_loader = _make_loader(val_rows, tokenizer, max_length, batch_size,
                              False, int(config["seed"]))
    compute_dtype = dtype
    use_amp = compute_dtype in (torch.bfloat16, torch.float16)
    scaler = torch.cuda.amp.GradScaler(enabled=(compute_dtype == torch.float16))
    log_path = output_dir / "training_log.jsonl"
    gpu_reset_peak()
    started = time.time()
    model.train()
    global_step = 0
    optimizer_steps = 0
    train_tokens = 0
    last_loss = None
    for epoch in range(epochs):
        for step, batch in enumerate(train_loader):
            batch = {key: value.to("cuda") for key, value in batch.items()}
            tokens = int(batch["attention_mask"].sum().item())
            train_tokens += tokens
            with torch.autocast(device_type="cuda", dtype=compute_dtype,
                                enabled=use_amp):
                outputs = model(**batch)
                loss = outputs.loss
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite loss at epoch %d step %d" % (epoch, step))
            scaler.scale(loss / accumulation).backward()
            last_loss = float(loss.item())
            if (step + 1) % accumulation == 0:
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
                optimizer_steps += 1
            if (global_step + 1) % int(config["training"]["logging_steps"]) == 0:
                append_jsonl(log_path, {
                    "time": now_iso(), "epoch": epoch, "step": step,
                    "global_step": global_step, "optimizer_steps": optimizer_steps,
                    "loss": last_loss, "lr": float(config["training"]["learning_rate"]),
                    "tokens": tokens, "peak_gpu_gb": gpu_peak_gb(),
                })
            global_step += 1
    # Flush the final partial accumulation window.
    if global_step % accumulation != 0:
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)
        optimizer_steps += 1
    val_loss = evaluate_loss(model, val_loader)
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    summary = {
        "stage": stage["name"], "family": stage["family"],
        "previous_adapter": previous_adapter,
        "train_samples": len(train_rows), "val_samples": len(val_rows),
        "epochs": epochs, "steps": global_step, "optimizer_steps": optimizer_steps,
        "train_tokens": train_tokens, "last_loss": last_loss, "val_loss": val_loss,
        "compute_dtype": str(compute_dtype), "peak_gpu_gb": gpu_peak_gb(),
        "duration_seconds": round(time.time() - started, 2),
        "seed": int(config["seed"]),
        "max_seq_length": max_length,
    }
    write_json(output_dir / "train_summary.json", summary)
    write_json(output_dir / "stage_config.json", {
        "stage": stage, "previous_adapter": previous_adapter, "config": config})
    print("train done", stage["name"], "val_loss", val_loss,
          "peak_gpu_gb", summary["peak_gpu_gb"],
          "seconds", summary["duration_seconds"], flush=True)
    return summary
