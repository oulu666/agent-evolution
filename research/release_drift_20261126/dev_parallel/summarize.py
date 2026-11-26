"""Audit cloud outputs against archived public observations and make paired counts."""
from collections import Counter, defaultdict
import json
from pathlib import Path

from run import ARMS, HERE, PROBES, RESEARCH, inputs, schema


def main():
    dest = HERE / "results"
    archived = json.loads((RESEARCH.parent / "runs_upstream_functional_20261124/paired_releases.json").read_text())
    totals = defaultdict(Counter)
    by_case = {}
    for case in PROBES:
        data = json.loads((dest / f"{case}.json").read_text())
        counts = defaultdict(Counter)
        old, new = data["versions"]
        first, last = data["captures"]
        pair_changes = sum(a["observed"] != b["observed"] for a, b in zip(first["initial"], last["initial"], strict=True))
        agreement = Counter()
        for i, version in enumerate((old, new)):
            runs = data["results"][version]
            assert set(runs) == set(ARMS)
            initial = data["captures"][i]["initial"]
            assert [r["value"] for r in initial] == inputs(case)
            ref = archived[case][("before", "after")[i]]["rows"]
            for a, b in zip(initial, ref, strict=True):
                observed = a["observed"][0] if case == "duration" else a["observed"]
                assert a["value"] == b["input"] and observed == b["actual"]
            for arm, result in runs.items():
                for j, (r, first_call) in enumerate(zip(result["rows"], initial, strict=True)):
                    assert r["initial"] == first_call["observed"] and r["value"] == first_call["value"]
                    assert r["schema_ok"] == schema(case, r["initial"])
                    assert r["outcome"] == ("deferred" if r["delivered"] is None else
                                             "correct" if r["delivered"] == r["required"] else "wrong")
                    assert len(r["charges"]) <= 3 and all(c["completed"] for c in r["charges"])
                    c = counts[arm]
                    c[r["outcome"]] += 1
                    c["loss"] += r["loss"]
                    c["calls"] += len(r["charges"])
                    c["probes"] += len(r["probes"])
                    c["flags"] += r["target_alarm"]
                    c["recover"] += r["initial_wrong"] and r["outcome"] == "correct"
                    c["fp"] += r["target_alarm"] and not r["initial_wrong"]
                    c["recovery_calls"] += sum(e["purpose"] == "recovery" for e in r["charges"])
                    assert len(r["probes"]) == sum(e["purpose"] == "probe" for e in r["charges"])
                    for e in r["probes"]:
                        assert e["output"] == data["captures"][i]["bank"][e["q"]]["observed"]
                    if any(e["old_diff"] for e in r["probes"]):
                        c["version_witness"] += 1
                        c["witness_target_unchanged"] += r["initial"] == first["initial"][j]["observed"]
            for a in ("active_info", "active_task"):
                static = "static_info" if a == "active_info" else "static_task"
                for x, y in zip(runs[a]["rows"], runs[static]["rows"], strict=True):
                    agreement[a+"_equal_outcome"] += x["outcome"] == y["outcome"]
                    agreement[a+"_equal_requests"] += [e["request"] for e in x["charges"]] == [e["request"] for e in y["charges"]]
        for arm, c in counts.items():
            totals[arm].update(c)
        by_case[case] = {"versions": [old, new], "inputs": len(first["initial"]),
                         "changed_task_outputs": pair_changes, "paired": agreement,
                         "static_plan": data["results"][old]["static_info"]["preplanned"],
                         "arms": counts}
    summary = {"totals": totals, "cases": by_case}
    (dest / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    for arm, c in totals.items():
        print(arm, dict(c))
    for case, row in by_case.items():
        print(case, row["changed_task_outputs"], row["static_plan"], dict(row["paired"]), dict(row["arms"]["active_info"]))


if __name__ == "__main__":
    main()
