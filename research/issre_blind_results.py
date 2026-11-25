"""Reconcile held-out measurements with the frozen plans. Never write a frozen input."""
from statistics import median
from sys import version
from issre_blind_posthoc import read
from issre_blind_frame import persist, OUT
from issre_blind_schedule import METHODS


def main():
    plans = read("schedules.json")
    pairs = read("paired.json")
    costs = {(x["project"],x["id"]):x for x in read("posthoc_and_costs.json")}
    assert len(costs) == len(pairs) == 8
    output = {"python":version,"pairs":[],"projects":{}}
    for p,regimes in plans.items():
        group = [r for r in pairs if r["project"]==p]
        prices = []
        full_obs = []
        for r in group:
            before,after = r["parent_rows"],r["commit_rows"]
            assert set(before)==set(after) and len(before)==10
            def differing(field):
                return [n for n in before if before[n][field]!=after[n][field]]
            def failures(side):
                return [n for n,v in side.items() if v["values"]!=v["expected"]]
            output["pairs"].append(dict(project=p,commit=r["commit"],raw_diff=differing("raw"),
                semantic_diff=differing("values"),before_failed=failures(before),after_failed=failures(after)))
            for rows in (before,after):
                for v in rows.values():
                    prices.append(v["run"]/1000)
                    full_obs.append(v["obs"]["+".join(v["expected"])]/1000)
        summary = dict(pairs=len(group),task_run_us=median(prices),full_observe_us=median(full_obs),regimes={})
        for regime,methods in regimes.items():
            metrics = {}
            for m in [*METHODS,"Joint inputs, full fields"]:
                plan = methods["Joint" if m=="Joint inputs, full fields" else m]
                selected = plan["inputs"]
                ref = group[0]["parent_rows"]
                fields = {n:list(ref[n]["expected"]) if m=="Joint inputs, full fields" else fs
                    for n,fs in selected.items()}
                times = []
                hits = []
                for r in group:
                    mismatches = []
                    for n,fs in fields.items():
                        a,b = r["parent_rows"][n],r["commit_rows"][n]
                        for f in fs:
                            if a["values"][f]!=a["expected"][f] and b["values"][f]==b["expected"][f]:
                                mismatches.append((n,f))
                    if mismatches:
                        hits.append(r["commit"])
                    row = costs[p,r["id"]]
                    for side in ("parent_data","commit_data"):
                        times.append(median(row[side]["plan_ns"][regime][m]))
                cap = plan["cap_ns"]
                metrics[m] = dict(steps=sum(ref[n]["calls"] for n in fields),tasks=len(fields),
                    assertions=sum(map(len,fields.values())),candidate_hits=hits,median_ms=median(times)/1e6,
                    cap_ms=None if cap is None else cap/1e6,
                    versions_over_cap=None if cap is None else sum(t>cap for t in times),
                    versions=len(times))
            summary["regimes"][regime] = metrics
        output["projects"][p] = summary
    persist(OUT/"findings.json",output)


if __name__=="__main__":
    main()
