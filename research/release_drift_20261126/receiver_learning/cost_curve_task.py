"""Run the cost–correctness curve on the three existing synthetic cases."""
import hashlib
import json
import subprocess
from pathlib import Path
from time import perf_counter

from cost_curve import (
    BUDGETS,
    best_shared_static_plan,
    compare_curves,
    counting_rule,
    run_case_curve,
)
from joint_world import CASES, EXTRA_BUDGET, collect_case

HERE = Path(__file__).resolve().parent
ORIGINAL_RECEIPT = HERE / "joint-receipt.json"


def _repo():
    repo = HERE.parents[2]
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        return Path("/workspace/agent-evolution-main-88ca0d20")
    return repo


def original_joint_metrics():
    receipt = json.loads(ORIGINAL_RECEIPT.read_text(encoding="utf-8"))
    out = {
        "base_head": receipt["base_head"],
        "extra_observation_budget": receipt["extra_observation_budget"],
        "independent_gain": receipt["independent_gain"],
        "cases": {},
    }
    for case_id, case in receipt["cases"].items():
        out["cases"][case_id] = {
            "truth_receiver": case["truth_receiver"],
            "truth_relation": case["truth_relation"],
            "metrics": case["metrics"],
            "cost_as_originally_reported": case["cost"],
            "independent_gain_rows": case["independent_gain_rows"],
        }
    return out


def build_receipt():
    started = perf_counter()
    repo = _repo()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    original = original_joint_metrics()
    cases = {}
    for case in CASES:
        public, hidden = collect_case(case)
        curve = run_case_curve(public, hidden)
        cases[case["id"]] = {
            "synthetic": True,
            "mechanism_development_only": True,
            "not_independent_defect_evidence": True,
            "kind": public["kind"],
            "requirement": public["requirement"],
            "n_slots": len(public["slots"]),
            "n_demos": len(public["demos"]),
            "n_rows": len(public["rows"]),
            "truth_receiver": hidden["truth_receiver"],
            "truth_relation": hidden["truth_relation"],
            "curve": curve,
        }
    shared = best_shared_static_plan({case_id: item["curve"] for case_id, item in cases.items()})
    comparisons = compare_curves({case_id: item["curve"] for case_id, item in cases.items()}, shared)
    receipt = {
        "analysis": "cost_correctness_curve_addendum",
        "does_not_replace_joint_receipt": True,
        "does_not_change_original_denominators": True,
        "synthetic_only": True,
        "not_independent_defect_evidence": True,
        "core_algorithm_not_established": True,
        "does_not_establish_eswa_core_contribution": True,
        "auto_oracle_generation_not_a_novelty_claim": True,
        "hidden_pagination_not_treated_as_proof": True,
        "no_fourth_synthetic_case": True,
        "no_gpu_or_paid_model": True,
        "model_calls": 0,
        "base_head": head,
        "original_joint_base_head": original["base_head"],
        "default_extra_observation_budget": EXTRA_BUDGET,
        "budgets_swept": list(BUDGETS) + ["unlimited_full_trace_only"],
        "methods": [
            "joint",
            "optimal_static",
            "lookup",
            "full_trace_same_budget",
            "full_trace_unlimited",
        ],
        "counting_rule": counting_rule(),
        "cases": cases,
        "comparisons": comparisons,
        "original_joint_locked_metrics": original,
        "local_cpu_seconds": None,
    }
    receipt["local_cpu_seconds"] = perf_counter() - started
    return receipt


def write_receipt(receipt, path=None):
    path = path or (HERE / "cost-curve-receipt.json")
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest


def main():
    receipt = build_receipt()
    path, digest = write_receipt(receipt)
    print(path)
    print(digest)
    return path


if __name__ == "__main__":
    main()
