"""Post-run paired comparison and exact-probe cache counterfactual, with no tool reruns."""
from collections import Counter
import json
from pathlib import Path

out = Path(__file__).resolve().parents[1] / "runs_egatv_pilot_20261125"
rows = json.loads((out / "decisions.json").read_text(encoding="utf-8"))
groups = {}
for row in rows:
    key = tuple(row[k] for k in ("tool", "version", "value", "history", "fallback_available"))
    group = groups.setdefault(row["method"], {})
    assert key not in group
    group[key] = row
agent = groups["egatv"]
assert len(agent) == 256 and all(g.keys() == agent.keys() for g in groups.values())
balance = {}
for method, group in groups.items():
    delta = Counter(int(r["success"]) - int(group[k]["success"]) for k, r in agent.items())
    balance[method] = dict(win=delta[1], loss=delta[-1], tie=delta[0],
                           same_terminal_action=sum(r["action"] == group[k]["action"] for k,r in agent.items()))
saved = Counter()
for key, row in groups["generic_risk"].items():
    start = row["starting_evidence"]
    kept = []
    for probe in row["checks"]:
        if start["generated"] and start["observed"] and start["scope"] == probe["scope"]:
            assert probe["actual"] == row["history_value"] and probe["passed"] == start["passed"]
            saved[row["history"]] += 1
        else:
            kept.append(probe)
    assert kept == agent[key]["checks"] and row["action"] == agent[key]["action"]
result = {"phase": "post-run counterfactual on deterministic tools", "paired": balance,
          "reusable_generic_probes_by_history": dict(saved), "cases_verified": len(agent)}
(out / "paired_audit.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
