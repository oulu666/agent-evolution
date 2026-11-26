"""Write the calibration receipt. Run only after protocol.md is committed."""

import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness


def render_log(receipt):
    lines = [
        "label: calibration",
        receipt["banner"],
        f"protocol_commit: {receipt['protocol_commit']}",
        f"head: {receipt['head']}",
        f"method_frozen: {str(receipt['method_frozen']).lower()}",
        f"methods_ranked: {str(receipt['methods_ranked']).lower()}",
        f"checklist_boxes_ticked: {str(receipt['checklist_boxes_ticked']).lower()}",
        f"live_library_execution: {str(receipt['live_library_execution']).lower()}",
        f"budget_limit: {receipt['budget_limit']}",
        "arithmetic_check_fixture: protocol-tiny",
        f"arithmetic_losses: {receipt['arithmetic_check']['losses']}",
        "arithmetic_note: 0、1、5 是三个点质量上的损失，不是案例分数。",
    ]
    for case in receipt["cases"]:
        lines.append(f"case: {case['id']} library: {case.get('library')} label: calibration")
        if case.get("status") == "gap":
            lines.append(f"  not_completed: {case.get('reason')}")
        for name, artifact in case.get("artifacts", {}).items():
            lines.append(
                f"  {name}: status={artifact.get('status')} signoff_ready={str(artifact.get('signoff_ready')).lower()}"
            )
            reason = artifact.get("reason")
            if reason:
                lines.append(f"    {reason}")
    lines.append("gaps:")
    for gap in receipt["gaps"]:
        lines.append(f"- {gap['id']}: {gap['detail']}")
    lines.append("hash_freeze_helper: gap")
    lines.append(receipt["hash_freeze_helper"]["reason"])
    return "\n".join(lines) + "\n"


def main():
    receipt = harness.build_receipt()
    if receipt["label"] != "calibration" or not receipt["banner"].startswith("这是校准"):
        raise SystemExit("refusing a receipt that is not labeled calibration")
    if receipt["method_frozen"] or receipt["methods_ranked"] or receipt["checklist_boxes_ticked"]:
        raise SystemExit("refusing a receipt that claims a formal freeze or a ranking")
    if not receipt["protocol_commit"]:
        raise SystemExit("protocol.md has no commit; refusing to run calibration")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", receipt["protocol_commit"], receipt["head"]],
        cwd=harness.REPO, check=False)
    if ancestor.returncode != 0:
        raise SystemExit("protocol commit is not an ancestor of HEAD; refusing to run calibration")
    if receipt["git_status"]:
        raise SystemExit("refusing to write calibration results from a dirty work tree")
    if receipt["arithmetic_check"]["losses"] != [0, 1, 5] or receipt["arithmetic_check"]["case_rows_used"]:
        raise SystemExit("arithmetic check left the protocol fixture")
    destination = HERE / "results"
    destination.mkdir(parents=True)
    receipt_path = destination / "calibration_receipt.json"
    log_path = destination / "calibration_log.txt"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log_path.write_text(render_log(receipt), encoding="utf-8")
    print(f"label: calibration\nwrote: {receipt_path}\nwrote: {log_path}")


if __name__ == "__main__":
    main()
