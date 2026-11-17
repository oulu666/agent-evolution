"""Environment report for the 8GB QLoRA target."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .utils import now_iso, write_json


def _version(package: str) -> Optional[str]:
    try:
        from importlib import metadata
        return metadata.version(package)
    except Exception:
        pass
    try:
        import pkg_resources
        return pkg_resources.get_distribution(package).version
    except Exception:
        return None


def _torch_info() -> Dict[str, Any]:
    info = {"installed": False, "version": None, "cuda_available": False,
            "cuda_version": None, "gpu_name": None, "vram_gb": None,
            "bf16_supported": False, "error": None}
    try:
        import torch
    except Exception as exc:
        info["error"] = "%s: %s" % (type(exc).__name__, exc)
        return info
    info["installed"] = True
    info["version"] = getattr(torch, "__version__", None)
    info["cuda_available"] = bool(torch.cuda.is_available())
    info["cuda_version"] = getattr(torch.version, "cuda", None)
    if info["cuda_available"]:
        try:
            info["gpu_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["vram_gb"] = round(props.total_memory / (1024 ** 3), 2)
            info["bf16_supported"] = bool(torch.cuda.is_bf16_supported())
        except Exception as exc:
            info["error"] = "%s: %s" % (type(exc).__name__, exc)
    return info


def _nvidia_smi() -> str:
    commands = [
        ["nvidia-smi",
         "--query-gpu=name,memory.total,memory.used,memory.free,driver_version",
         "--format=csv,noheader"],
    ]
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            continue
    return "unavailable"


def _ram_gb() -> Optional[float]:
    try:
        if hasattr(os, "sysconf"):
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return round(pages * page_size / (1024 ** 3), 2)
    except Exception:
        pass
    return None


def collect() -> Dict[str, Any]:
    torch_info = _torch_info()
    packages = {}
    for name in ("torch", "transformers", "peft", "bitsandbytes", "accelerate",
                 "sentencepiece", "huggingface_hub", "numpy"):
        packages[name] = _version(name)
    report = {
        "timestamp": now_iso(),
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "ram_gb": _ram_gb(),
        "nvidia_smi": _nvidia_smi(),
        "torch": torch_info,
        "packages": packages,
        "pass": bool(torch_info["installed"] and torch_info["cuda_available"]
                     and packages.get("transformers") and packages.get("peft")
                     and packages.get("bitsandbytes")),
    }
    return report


def render(report: Dict[str, Any]) -> str:
    torch_info = report["torch"]
    lines = [
        "FAC-TinyAgent Environment Report",
        "================================",
        "timestamp: %s" % report["timestamp"],
        "python: %s" % report["python"],
        "executable: %s" % report["python_executable"],
        "platform: %s" % report["platform"],
        "ram_gb: %s" % report["ram_gb"],
        "nvidia_smi: %s" % report["nvidia_smi"],
        "",
        "torch installed: %s" % torch_info["installed"],
        "torch version: %s" % torch_info["version"],
        "CUDA available: %s" % torch_info["cuda_available"],
        "CUDA version: %s" % torch_info["cuda_version"],
        "GPU: %s" % torch_info["gpu_name"],
        "VRAM (GB): %s" % torch_info["vram_gb"],
        "BF16 supported: %s" % torch_info["bf16_supported"],
    ]
    if torch_info.get("error"):
        lines.append("torch error: %s" % torch_info["error"])
    lines.append("")
    lines.append("packages:")
    for name, version in report["packages"].items():
        lines.append("  %-18s %s" % (name, version or "MISSING"))
    lines.append("")
    lines.append("PASS: %s" % report["pass"])
    if not report["pass"]:
        lines.append("")
        lines.append("Action: create a Python 3.12 venv and install")
        lines.append("  torch transformers peft bitsandbytes accelerate sentencepiece")
        lines.append("If CUDA is unavailable in WSL2, check the NVIDIA driver and")
        lines.append("  /usr/lib/wsl/lib is on PATH.")
    if torch_info.get("vram_gb") and torch_info["vram_gb"] < 8:
        lines.append("VRAM below 8GB: reduce max_seq_length to 768 before training.")
    if torch_info["cuda_available"] and not torch_info["bf16_supported"]:
        lines.append("BF16 unsupported: the trainer will fall back to FP16 autocast.")
    return "\n".join(lines) + "\n"


def write_report(output: Path) -> Dict[str, Any]:
    report = collect()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(report), encoding="utf-8")
    write_json(output.with_suffix(".json"), report)
    return report


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("environment_report.txt")
    result = write_report(path)
    print(render(result))
