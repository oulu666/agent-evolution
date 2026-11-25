"""Post-hoc cost bounds at maximal attainable success, conditional on frozen views."""
import csv
from collections import defaultdict
from pathlib import Path

out = Path(__file__).resolve().parents[1] / "runs_action_evidence_20261125"
with (out/"heldout_inputs.csv").open(encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
result = []
for domain in ("Markdown","YAML"):
    subset = [r for r in rows if r["project"] == domain]
    for view in ("family","family+id","family+bits","family+id+bits"):
        buckets = defaultdict(list)
        for r in subset:
            key = [r["family"]]
            if "id" in view: key.append(r["probe"])
            if "bits" in view: key.extend((r["probeP"],r["probeB"]))
            buckets[tuple(key)].append(r)
        success = wrong = 0
        service = 0.
        for bucket in buckets.values():
            candidates = [(sum(r[a]=="True" for r in bucket), -sum(r[a]=="False" for r in bucket),
                           -sum(float(r["t"+a]) for r in bucket)) for a in ("P","B")]
            ok,neg_wrong,negative_time = max(*candidates,(0,0,0.))
            success += ok
            wrong -= neg_wrong
            service -= negative_time
        # Exclude lookup CPU as a favourable lower bound for signal-consuming policies.
        queries = {(r["probe"],a):float(r["q"+a]) for r in subset for a in ("P","B")} if "bits" in view else {}
        cold = sum(float(r["qP"])+float(r["qB"]) for r in subset) if queries else 0.
        result.append(dict(project=domain,view=view,success=success,wrong=wrong,service_us=service,
                           cold_lower_us=service+cold,warm_batch_lower_us=service+sum(queries.values())))
with (out/"conditional_cost_bounds.csv").open("w",encoding="utf-8-sig",newline="") as f:
    writer=csv.DictWriter(f,fieldnames=list(result[0]))
    writer.writeheader()
    writer.writerows(result)
