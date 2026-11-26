"""Aggregate three redacted organizer receipts; never load witnesses or rationales."""
import argparse
import json
from pathlib import Path
import re


FIELDS = ("total", "decidable", "partial", "unassessable", "executable_bound",
          "paired", "divergent", "strict")


def rollup(directory):
    totals = dict.fromkeys(FIELDS, 0)
    commitments = []
    for project in ("pillow", "pandas", "scipy"):
        receipt = json.loads((directory / f"{project}.json").read_text(encoding="utf-8-sig"))
        if set(receipt) != set(FIELDS) | {"commitment"}:
            raise ValueError("invalid receipt fields")
        if not all(type(receipt[k]) is int and receipt[k] >= 0 for k in FIELDS):
            raise ValueError("invalid count")
        remaining = receipt["partial"] + receipt["unassessable"]
        if (receipt["decidable"] + remaining != receipt["total"]
                or receipt["executable_bound"] > receipt["decidable"]
                or not 0 <= receipt["strict"] <= receipt["divergent"] <= receipt["paired"] <= remaining):
            raise ValueError("inconsistent receipt denominators")
        if not re.fullmatch(r"[0-9a-f]{64}", receipt["commitment"]):
            raise ValueError("invalid commitment")
        for key in FIELDS:
            totals[key] += receipt[key]
        commitments.append(receipt["commitment"])
    if totals["total"] != 4 or len(set(commitments)) != 3:
        raise ValueError("incomplete independent-change coverage")
    return {"criteria_commit": "0999871b", "receipts": 3, "counts": totals,
            "commitments_unlinked": sorted(commitments)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("redacted_receipts", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = rollup(args.redacted_receipts)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result["counts"]))
