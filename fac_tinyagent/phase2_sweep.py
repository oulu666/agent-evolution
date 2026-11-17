"""Run the Phase 2 multi-order, multi-seed sequential sweep."""
from __future__ import annotations

import argparse
import copy
from pathlib import Path

from .config import PROJECT_ROOT, load_config
from .data.generate import generate_all, verify_all
from .utils import ensure_dir, write_json

ORDERS = {
    "A": ["file", "database", "python", "calendar"],
    "B": ["calendar", "python", "database", "file"],
    "C": ["database", "file", "calendar", "python"],
}
DEFAULT_SEEDS = [20261108, 20261109, 20261110]


def build_config(base, order_id, order, seed, test_limit):
    config = copy.deepcopy(base)
    config["seed"] = seed
    config["data"]["families"] = list(order)
    config["evaluation"]["all_families"] = True
    config["evaluation"]["test_limit"] = test_limit
    config["run_name"] = "%s_seed%d" % (order_id, seed)
    stages = [{"name": "stage_00_base", "family": None}]
    for index, family in enumerate(order, 1):
        stages.append({"name": "stage_%02d_%s" % (index, family),
                       "family": family})
    config["stages"] = stages
    return config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/phase2_base.json")
    parser.add_argument("--orders", nargs="+", default=list(ORDERS),
                        choices=list(ORDERS))
    parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--test-limit", type=int, default=6)
    parser.add_argument("--regenerate-data", action="store_true")
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--run-id-prefix", default="")
    args = parser.parse_args()

    base = load_config(args.config)
    data_config = copy.deepcopy(base)
    data_config["data"]["families"] = list(ORDERS[args.orders[0]])
    needed = [Path(data_config["data_root"]) / family / "train.jsonl"
              for family in data_config["data"]["families"]]
    if args.regenerate_data or not all(path.exists() for path in needed):
        generate_all(data_config, verify=not args.no_verify)
    else:
        verify_all(data_config)

    from .sequential import run_sequential

    config_dir = ensure_dir(PROJECT_ROOT / "configs" / "phase2")
    results = []
    for order_id in args.orders:
        for seed in args.seeds:
            config = build_config(base, order_id, ORDERS[order_id], seed,
                                  args.test_limit)
            run_id = args.run_id_prefix + config["run_name"]
            run_dir = Path(config["output_root"]) / run_id
            if (run_dir / "summary.json").exists():
                print("skip complete", run_id, flush=True)
                results.append(run_id)
                continue
            if run_dir.exists():
                run_id = run_id + "_retry"
                run_dir = Path(config["output_root"]) / run_id
                if run_dir.exists():
                    print("skip partial", run_id, flush=True)
                    continue
            config["run_name"] = run_id
            write_json(config_dir / ("%s.json" % run_id), config)
            print("START", run_id, "order", ORDERS[order_id], "seed", seed,
                  flush=True)
            run_sequential(config, run_id=run_id)
            results.append(run_id)
    print("sweep complete:", results, flush=True)


if __name__ == "__main__":
    main()
