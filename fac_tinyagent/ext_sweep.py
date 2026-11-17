"""[ext-paper 2026-11-10] Phase-2 style sweep with model / data / output overrides.

New file; the original ``phase2_sweep.py`` is untouched and keeps its defaults.
Differences from phase2_sweep (all opt-in through the command line):

* ``--model``, ``--data-root``, ``--output-root`` override the config values.
* Data are never (re)generated here and existing ``data*/`` directories are
  never written: the verification report that ``verify_all`` would normally
  write into ``<data_root>/verification.json`` is redirected into
  ``<output_root>/data_verification.json``.
* Resolved run configs are written to ``<output_root>/_configs/`` instead of
  ``configs/phase2/`` so the historical Phase 2 configs cannot be overwritten.
* A small ``ext_meta.json`` per run records wall time and per-stage GPU peaks.

Example (Qwen3-1.7B smoke, order A, one seed):

    .venv/bin/python -u -m fac_tinyagent.ext_sweep \
        --config configs/ext/qwen3_1p7b_phase2_smoke.json \
        --orders A --seeds 20261108 --test-limit 3
"""
from __future__ import annotations

import argparse
import copy
import time
from pathlib import Path

from .config import PROJECT_ROOT, load_config
from .phase2_sweep import DEFAULT_SEEDS, ORDERS, build_config
from .utils import ensure_dir, now_iso, read_json, write_json


def _resolve(path: str) -> str:
    value = Path(path)
    return str(value if value.is_absolute() else PROJECT_ROOT / value)


def _verify_readonly(config, output_root: Path) -> None:
    """Run the original verifier without writing into the data directory."""
    from .data import generate
    target = output_root / "data_verification.json"
    original = generate.write_json

    def redirected(path, payload):  # noqa: ANN001
        return original(target, dict(payload, data_root=config["data_root"]))

    generate.write_json = redirected
    try:
        generate.verify_all(config)
    finally:
        generate.write_json = original


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--model", default=None,
                        help="override model_name_or_path")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--orders", nargs="+", default=list(ORDERS),
                        choices=list(ORDERS))
    parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--test-limit", type=int, default=6)
    parser.add_argument("--run-id-prefix", default="")
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--max-stages", type=int, default=None,
                        help="only run the first N training stages (smoke/time budget)")
    args = parser.parse_args()

    base = load_config(args.config)
    if args.model:
        base["model_name_or_path"] = args.model
    if args.data_root:
        base["data_root"] = _resolve(args.data_root)
    if args.output_root:
        base["output_root"] = _resolve(args.output_root)
    output_root = ensure_dir(Path(base["output_root"]))
    if not args.no_verify:
        data_config = copy.deepcopy(base)
        data_config["data"]["families"] = list(ORDERS[args.orders[0]])
        _verify_readonly(data_config, output_root)

    from .sequential import run_sequential

    config_dir = ensure_dir(output_root / "_configs")
    results = []
    for order_id in args.orders:
        for seed in args.seeds:
            config = build_config(base, order_id, ORDERS[order_id], seed,
                                  args.test_limit)
            if args.max_stages is not None:
                config["stages"] = config["stages"][:1 + args.max_stages]
                config["data"]["families"] = [
                    stage["family"] for stage in config["stages"] if stage["family"]]
            run_id = args.run_id_prefix + config["run_name"]
            run_dir = output_root / run_id
            if (run_dir / "summary.json").exists():
                print("skip complete", run_id, flush=True)
                results.append(run_id)
                continue
            if run_dir.exists():
                raise SystemExit("partial run exists, pick another --run-id-prefix: %s"
                                 % run_dir)
            config["run_name"] = run_id
            write_json(config_dir / ("%s.json" % run_id), config)
            print("START", run_id, "model", config["model_name_or_path"],
                  "order", ORDERS[order_id], "seed", seed, flush=True)
            started = time.time()
            run_sequential(config, run_id=run_id)
            elapsed = round(time.time() - started, 1)
            stages = []
            for stage_dir in sorted((run_dir / "checkpoints").iterdir()):
                summary_path = stage_dir / "train_summary.json"
                if summary_path.exists():
                    item = read_json(summary_path)
                    stages.append({key: item.get(key) for key in (
                        "stage", "peak_gpu_gb", "duration_seconds", "train_tokens",
                        "val_loss", "compute_dtype")})
            write_json(run_dir / "ext_meta.json", {
                "finished": now_iso(), "wall_seconds": elapsed,
                "model_name_or_path": config["model_name_or_path"],
                "train_peak_gpu_gb_max": max(
                    [s["peak_gpu_gb"] or 0 for s in stages] or [0]),
                "stages": stages,
            })
            print("DONE", run_id, "wall_seconds", elapsed, flush=True)
            results.append(run_id)
    print("ext sweep complete:", results, flush=True)


if __name__ == "__main__":
    main()
