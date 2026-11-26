"""Write the calibration gap follow-up receipt.

Run only after PROTOCOL_ADDENDUM_ZH.md is committed and the work tree is clean.
This does not overwrite the earlier calibration receipt.
"""

import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import followup


def main():
    receipt = followup.build_receipt()
    if receipt["label"] != "calibration" or not receipt["banner"].startswith("这是校准"):
        raise SystemExit("refusing a receipt that is not labeled calibration")
    if receipt["method_frozen"] or receipt["methods_ranked"] or receipt["checklist_boxes_ticked"]:
        raise SystemExit("refusing a receipt that claims a formal freeze or a ranking")
    if receipt["formal_paired_comparison_started"] or receipt["sealed_outcomes_used"]:
        raise SystemExit("refusing a receipt that starts the formal comparison")
    if not receipt["addendum_commit"]:
        raise SystemExit("addendum has no commit; refusing to run calibration")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", receipt["addendum_commit"], receipt["head"]],
        cwd=followup.REPO, check=False)
    if ancestor.returncode != 0:
        raise SystemExit("addendum commit is not an ancestor of HEAD; refusing to run calibration")
    if receipt["git_status"]:
        raise SystemExit("refusing to write calibration results from a dirty work tree")
    if receipt["arithmetic_check"]["losses"] != [0, 1, 5] or receipt["arithmetic_check"]["case_rows_used"]:
        raise SystemExit("arithmetic check left the protocol fixture")
    if receipt["interpreter"]["cpython_3_11_pin"] == "satisfied" or receipt["interpreter"]["random_arm_ran"]:
        raise SystemExit("refusing a receipt that treats this interpreter as the 3.11 random arm")
    for case in receipt["cases"]:
        if case["expression_table"]:
            followup.validate_expression_table(case["expression_table"], [], [], "int")
        for artifact in case["artifacts"].values():
            if artifact.get("signoff_ready"):
                raise SystemExit("refusing a calibration artifact marked ready for sign-off")
    destination = HERE / "results"
    destination.mkdir(parents=True, exist_ok=True)
    receipt_path = destination / "gaps_followup_receipt.json"
    log_path = destination / "gaps_followup_log.txt"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log_path.write_text(followup.render_log(receipt), encoding="utf-8")
    print(f"label: calibration\nwrote: {receipt_path}\nwrote: {log_path}")


if __name__ == "__main__":
    main()
