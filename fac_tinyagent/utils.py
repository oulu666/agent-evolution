"""Shared utilities: seeds, JSON IO, hashing, GPU memory, OOM advice."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_dir(path: Any) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def set_seed(seed: int, deterministic: bool = True) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except Exception:
        pass
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        if deterministic:
            os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    except Exception:
        pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Any, value: Any) -> None:
    target = Path(path)
    ensure_dir(target.parent)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Any) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_jsonl(path: Any, rows: Iterable[Dict[str, Any]]) -> None:
    target = Path(path)
    ensure_dir(target.parent)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Any) -> List[Dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    rows = []
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Any, row: Dict[str, Any]) -> None:
    target = Path(path)
    ensure_dir(target.parent)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha256_file(path: Any) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def gpu_peak_gb() -> float:
    try:
        import torch
        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_allocated() / (1024 ** 3), 3)
    except Exception:
        pass
    return 0.0


def gpu_reset_peak() -> None:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass


def oom_advice() -> str:
    return (
        "OOM mitigation options (change one at a time, then rerun with a NEW run id):\n"
        "  1. training.max_seq_length: 1024 -> 768 -> 512\n"
        "  2. lora.r: 8 -> 4  (and lora.alpha: 16 -> 8)\n"
        "  3. keep training.batch_size=1 and gradient_accumulation_steps=8\n"
        "  4. evaluation.max_new_tokens_tool: 128 -> 96; answer: 64 -> 48\n"
        "  5. close other GPU processes (nvidia-smi) and rerun\n"
        "  6. export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True\n"
        "Do not silently change hyperparameters: write a new config and a new run id."
    )


def write_oom_report(path: Any, config: Dict[str, Any], stage: str, error: str) -> None:
    report = (
        "OOM REPORT\n"
        "time: %s\n"
        "stage: %s\n"
        "error: %s\n"
        "config: %s\n\n%s\n"
        % (now_iso(), stage, error, json.dumps(config, ensure_ascii=False, indent=2),
           oom_advice())
    )
    target = Path(path)
    ensure_dir(target.parent)
    target.write_text(report, encoding="utf-8")
