"""Write the after-arm calibration receipt.

Run only after PROTOCOL_AFTER_ARM_ZH.md is committed and the work tree is clean.
This does not overwrite the earlier calibration receipts.
"""

import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import after_arm


def main():
    status = subprocess.run(["git", "status", "--porcelain"], cwd=after_arm.harness.REPO,
                            capture_output=True, text=True, check=True)
    if status.stdout.strip():
        raise SystemExit("refusing to run after-arm calibration from a dirty work tree")
    receipt = after_arm.build_receipt()
    if receipt["label"] != "calibration" or not receipt["banner"].startswith("这是校准"):
        raise SystemExit("refusing a receipt that is not labeled calibration")
    if receipt["method_frozen"] or receipt["methods_ranked"] or receipt["checklist_boxes_ticked"]:
        raise SystemExit("refusing a receipt that claims a formal freeze or a ranking")
    if receipt["formal_paired_comparison_started"] or receipt["sealed_outcomes_used"] or receipt["compared_arms_scored"]:
        raise SystemExit("refusing a receipt that starts the formal comparison")
    if receipt["git_status"]:
        raise SystemExit("refusing to write calibration results from a dirty work tree")
    if not receipt["addendum_commit"]:
        raise SystemExit("addendum has no commit; refusing to run calibration")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", receipt["addendum_commit"], receipt["head"]],
        cwd=after_arm.harness.REPO, check=False)
    if ancestor.returncode != 0:
        raise SystemExit("addendum commit is not an ancestor of HEAD; refusing to run calibration")
    if receipt["arithmetic_check"]["losses"] != [0, 1, 5] or receipt["arithmetic_check"]["case_rows_used"]:
        raise SystemExit("arithmetic check left the protocol fixture")
    pin = receipt["pin"]
    if pin["random_arm_comparison_ran"] or pin["formal_paired_comparison_started"]:
        raise SystemExit("refusing a receipt that ran the formal random-arm comparison")
    if pin["cpython_3_11_pin"] == "satisfied":
        if pin.get("implementation") != "CPython" or not str(pin.get("version") or "").startswith("3.11"):
            raise SystemExit("refusing a 3.11 pin that is not CPython 3.11")
        if not pin.get("executable"):
            raise SystemExit("refusing a 3.11 pin without an executable path")
    elif pin["cpython_3_11_pin"] != "unset":
        raise SystemExit("refusing an unrecognized interpreter pin")
    if sys.version.startswith("3.12") and pin["cpython_3_11_pin"] == "satisfied":
        if Path(pin["executable"]).resolve() == Path(sys.executable).resolve():
            raise SystemExit("refusing to treat the 3.12 parent as the 3.11 pin")
    if receipt["outcome_prior"]["admissible"] or receipt["outcome_prior"]["development_preplanned_used"]:
        raise SystemExit("refusing a prior that the public fixtures do not register")
    if receipt["unidecode"]["exact_pin"] is not None or receipt["unidecode"]["installed"]:
        raise SystemExit("refusing a Unidecode install that the public fixtures do not pin")
    for case in receipt["cases"]:
        if case["signoff_ready"] or case["compared_to_expected"]:
            raise SystemExit("refusing a calibration case marked ready for sign-off")
        if case["expression_table"]:
            raise SystemExit("refusing a non-empty expression table in this public calibration")
        row = case["case_row"]
        if row["expected_task_loss"] is not None or row["evidence_sufficient"] or row["formal_score"]:
            raise SystemExit("refusing a case-row loss without the registered evidence")
        if case["registered_prior_selection"]["sequence_selected"] or case["static_sequence"]["sequence_selected"]:
            raise SystemExit("refusing a selected sequence without an admissible prior")
        if case["static_sequence"]["development_preplanned"]["development_preplanned_used"]:
            raise SystemExit("development preplanned was used")
        if case["field_address"]["wrapped"] or case["field_address"]["new_wrapper"] or case["field_address"]["cross_field_invariants"]:
            raise SystemExit("refusing a new field wrapper or invariant")
        quality = case.get("slugify_quality")
        if quality is not None and quality["signoff_quality_receipt"]:
            raise SystemExit("refusing a slugify quality receipt without a fixture pin")
        for artifact_name in ("budget_enforcement", "static_sequence", "field_address", "case_row"):
            artifact = case[artifact_name]
            if isinstance(artifact, dict) and artifact.get("signoff_ready"):
                raise SystemExit("refusing a calibration artifact marked ready for sign-off")
    destination = HERE / "results"
    destination.mkdir(parents=True, exist_ok=True)
    receipt_path = destination / "after_arm_receipt.json"
    log_path = destination / "after_arm_log.txt"
    for blocked in ("calibration_receipt.json", "calibration_log.txt",
                    "gaps_followup_receipt.json", "gaps_followup_log.txt"):
        if receipt_path.name == blocked or log_path.name == blocked:
            raise SystemExit("refusing to overwrite an earlier receipt")
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log_path.write_text(after_arm.render_log(receipt), encoding="utf-8")
    print(f"label: calibration\nwrote: {receipt_path}\nwrote: {log_path}")


if __name__ == "__main__":
    main()
