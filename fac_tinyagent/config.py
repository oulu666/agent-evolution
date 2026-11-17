"""Configuration loading and validation for FAC-TinyAgent phase 1."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "phase1.json"


def defaults() -> Dict[str, Any]:
    return {
        "model_name_or_path": "Qwen/Qwen3-0.6B",
        "seed": 20261108,
        "split_seed": 20261108,
        "data_root": "data",
        "output_root": "runs",
        "device": "cuda",
        "dtype": "auto",
        "trust_remote_code": True,
        "quantization": {
            "load_in_4bit": True,
            "bnb_4bit_quant_type": "nf4",
            "bnb_4bit_use_double_quant": True,
            "bnb_4bit_compute_dtype": "auto",
        },
        "lora": {
            "r": 8,
            "alpha": 16,
            "dropout": 0.05,
            "target_modules": [
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ],
        },
        "training": {
            "learning_rate": 1e-4,
            "batch_size": 1,
            "gradient_accumulation_steps": 8,
            "num_epochs": 2,
            "max_seq_length": 1024,
            "gradient_checkpointing": True,
            "optimizer": "paged_adamw_8bit",
            "logging_steps": 1,
        },
        "evaluation": {
            "batch_size": 1,
            "max_new_tokens_tool": 128,
            "max_new_tokens_answer": 128,
            "do_sample": False,
            "temperature": 0.0,
        },
        "data": {
            "families": ["file", "database", "python"],
            "train_per_family": 80,
            "val_per_family": 20,
            "test_per_family": 30,
        },
        "stages": [
            {"name": "stage_00_base", "family": None},
            {"name": "stage_01_file", "family": "file"},
            {"name": "stage_02_database", "family": "database"},
            {"name": "stage_03_python", "family": "python"},
        ],
        "oom_advice": True,
    }


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str = None) -> Dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError("Config not found: %s" % config_path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    config = deep_merge(defaults(), raw)
    for key in ("data_root", "output_root"):
        value = Path(config[key])
        config[key] = str(value if value.is_absolute() else PROJECT_ROOT / value)
    config["_config_path"] = str(config_path.resolve())
    config["_project_root"] = str(PROJECT_ROOT)
    validate_config(config)
    return config


def validate_config(config: Dict[str, Any]) -> None:
    families = set(config["data"]["families"])
    if not families:
        raise ValueError("data.families must not be empty")
    seen = set()
    for stage in config["stages"]:
        family = stage.get("family")
        if family is not None and family not in families:
            raise ValueError("Unknown family in stage: %s" % family)
        if family is not None:
            if family in seen:
                raise ValueError("Family trained twice: %s" % family)
            seen.add(family)
    trained = [stage.get("family") for stage in config["stages"] if stage.get("family")]
    if trained != config["data"]["families"]:
        raise ValueError("Stage order must match data.families: %s != %s"
                         % (trained, config["data"]["families"]))
    for key in ("train_per_family", "val_per_family", "test_per_family"):
        if int(config["data"][key]) <= 0:
            raise ValueError("data.%s must be positive" % key)
    if int(config["training"]["max_seq_length"]) > 2048:
        raise ValueError("max_seq_length above 2048 is not supported on 8GB VRAM")
    if int(config["training"]["batch_size"]) != 1:
        raise ValueError("Phase 1 requires batch_size=1")
