"""Command line entry point for FAC-TinyAgent phase 1."""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path

from .config import load_config
from . import env_check


def cmd_env(args) -> None:
    report = env_check.write_report(Path(args.output))
    print(env_check.render(report))


def cmd_gen_data(args) -> None:
    from .data.generate import generate_all
    config = load_config(args.config)
    manifest = generate_all(config, verify=not args.no_verify)
    print(json.dumps({family: item["counts"]
                      for family, item in manifest["families"].items()}, indent=2))


def cmd_verify_data(args) -> None:
    from .data.generate import verify_all
    config = load_config(args.config)
    report = verify_all(config)
    print(json.dumps(report, indent=2))


def cmd_sequential(args) -> None:
    config = load_config(args.config)
    try:
        from .sequential import run_sequential
        summary = run_sequential(config, run_id=args.run_id)
    except ImportError as exc:
        raise SystemExit("Sequential training requires torch, transformers, peft, "
                         "bitsandbytes and accelerate: %s" % exc)
    print("run complete: %s" % summary["run_id"])
    print(json.dumps(summary["capability_matrix"]["pivot"], indent=2))


def cmd_all(args) -> None:
    from .data.generate import generate_all, verify_all
    config = load_config(args.config)
    data_root = Path(config["data_root"])
    needed = [data_root / family / "train.jsonl"
              for family in config["data"]["families"]]
    if args.regenerate_data or not all(path.exists() for path in needed):
        generate_all(config, verify=True)
    else:
        verify_all(config)
    env_report = Path(config["output_root"]) / "environment_report.txt"
    env_check.write_report(env_report)
    cmd_sequential(args)


def cmd_summary(args) -> None:
    run_dir = Path(args.run_dir)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    print(json.dumps(summary["capability_matrix"]["pivot"], indent=2))
    print(json.dumps(summary["forgetting"]["family_average"], indent=2))


def cmd_report(args) -> None:
    from .report import write_phase1_report
    path = write_phase1_report(Path(args.run_dir))
    print("report: %s" % path)


def cmd_smoke(args) -> None:
    from .data.generate import generate_all
    from .metrics import answers_equal, forgetting_rows
    from .tools import create_fixture
    from .tools.db_tools import build_db_registry
    from .tools.file_tools import FileSandbox, build_file_registry, materialize_sandbox
    from .tools.stats_tools import build_stats_registry

    with tempfile.TemporaryDirectory() as tmp:
        sandbox = materialize_sandbox({"a.txt": "alpha\nbeta alpha\n"}, tmp)
        registry = build_file_registry(sandbox)
        assert registry.execute("file_read", {"path": "a.txt"})["ok"]
        assert registry.execute("file_read", {"path": "../x"})["ok"] is False
        assert len(registry.execute("file_search",
                                    {"path": "a.txt", "pattern": "alpha"})["result"]) == 2
    with tempfile.TemporaryDirectory() as tmp:
        db_path = create_fixture(str(Path(tmp) / "test.db"), force=True)
        registry = build_db_registry(str(db_path))
        assert registry.execute("db_query",
                                {"sql": "SELECT COUNT(*) FROM employees"})["result"]["rows"][0][0] == 12
        assert registry.execute("db_query", {"sql": "DELETE FROM employees"})["ok"] is False
    stats = build_stats_registry()
    assert stats.execute("stats_mean", {"values": [1, 2, 3]})["result"] == 2.0
    assert answers_equal(1.0, 1.0000001)
    config = copy.deepcopy(load_config(args.config))
    with tempfile.TemporaryDirectory() as tmp:
        config["data_root"] = tmp
        config["data"]["train_per_family"] = 8
        config["data"]["val_per_family"] = 2
        config["data"]["test_per_family"] = 6
        manifest = generate_all(config, verify=True)
        assert all(item["counts"]["train"] == 8
                   for item in manifest["families"].values())
    evaluations = [
        {"stage_index": 1, "stage_name": "s1", "family": "file",
         "metrics": {"tool_selection_accuracy": 0.8, "argument_accuracy": 0.8,
                     "execution_success_rate": 0.8, "final_task_success_rate": 0.8},
         "skill_metrics": {}},
        {"stage_index": 2, "stage_name": "s2", "family": "file",
         "metrics": {"tool_selection_accuracy": 0.5, "argument_accuracy": 0.5,
                     "execution_success_rate": 0.5, "final_task_success_rate": 0.5},
         "skill_metrics": {}},
    ]
    family_rows, _ = forgetting_rows(evaluations, {"file": 1})
    assert family_rows[0]["forgetting"] == 0.3
    print("smoke ok")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fac-tinyagent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    env = subparsers.add_parser("env", help="write environment_report.txt")
    env.add_argument("--output", default="environment_report.txt")
    env.set_defaults(func=cmd_env)

    gen = subparsers.add_parser("gen-data", help="generate the three datasets")
    gen.add_argument("--config", default=None)
    gen.add_argument("--no-verify", action="store_true")
    gen.set_defaults(func=cmd_gen_data)

    verify = subparsers.add_parser("verify-data", help="replay every episode")
    verify.add_argument("--config", default=None)
    verify.set_defaults(func=cmd_verify_data)

    sequential = subparsers.add_parser("sequential", help="run M0 -> File -> DB -> Python")
    sequential.add_argument("--config", default=None)
    sequential.add_argument("--run-id", default=None)
    sequential.set_defaults(func=cmd_sequential)

    all_cmd = subparsers.add_parser("all", help="env + data + sequential learning")
    all_cmd.add_argument("--config", default=None)
    all_cmd.add_argument("--run-id", default=None)
    all_cmd.add_argument("--regenerate-data", action="store_true")
    all_cmd.set_defaults(func=cmd_all)

    summary = subparsers.add_parser("summary", help="print a run summary")
    summary.add_argument("--run-dir", required=True)
    summary.set_defaults(func=cmd_summary)

    report = subparsers.add_parser("report", help="render reports/phase1_report.md")
    report.add_argument("--run-dir", required=True)
    report.set_defaults(func=cmd_report)

    smoke = subparsers.add_parser("smoke", help="CPU-only smoke test")
    smoke.add_argument("--config", default=None)
    smoke.set_defaults(func=cmd_smoke)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
