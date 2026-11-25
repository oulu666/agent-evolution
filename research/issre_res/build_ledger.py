"""Rebuild the manuscript's long-form evidence ledger from preserved observations."""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
rows = []


def data(cohort, file):
    path = ROOT / f"runs_{cohort}_20261124" / (file + ".json")
    return json.loads(path.read_text(encoding="utf-8-sig")), path.relative_to(ROOT).as_posix()


def metric(cohort, project, case, phase, measure, count, unit, source, note="", denominator=None):
    rows.append(dict(cohort=cohort, project=project, case=case, phase=phase, measure=measure,
                     count=count, denominator=denominator, unit=unit, source=source, note=note))


def known():
    out, path = data("upstream_functional","paired_releases")
    for k,r in out.items():
        project = "Babel" if k=="week" else "XlsxWriter"
        a,b = r["before"]["rows"],r["after"]["rows"]
        assert len(a)==len(b)
        witnesses=sum(x["actual"]!=x["expected"] and y["actual"]==y["expected"] for x,y in zip(a,b))
        metric("release pilot",project,k,"repair-informed","paired_inputs",len(a),"paired_input",path)
        metric("release pilot",project,k,"repair-informed","witness_inputs",witnesses,"paired_input",path,denominator=len(a))
    out,path=data("independent","replay")
    summary,_=data("independent","summary")
    for r in out["outcomes"]:
        a,b=r["parent_rows"],r["fixed_rows"]
        assert r["confirmed"] and len(a)==len(b)==2
        group="250" if r["repo"].endswith("humanize") and r["pr"]==240 else str(r["pr"])
        metric("known witness",r["repo"],str(r["pr"]),"repair-informed","executed",len(a)+len(b),
               "version_input",path,"analysis group "+group)
        for field in ("ok","coarse","fine"):
            x,y=a[1],b[1]
            hit=x["actual"].get(field)!=x["expected"].get(field) and y["actual"].get(field)==y["expected"].get(field)
            metric("known witness",r["repo"],str(r["pr"]),"repair-informed",field+"_detect",int(hit),
                   "repair_record",path,"boundary input; group "+group,1)
    for p,v in summary["projects"].items():
        for k in ("smoke","coarse","fine"):
            metric("known witness",p,"grouped","repair-informed",k+"_detect",v[k],"defect_group",
                   "runs_independent_20261124/summary.json","one representative per group",v["groups"])


def blind():
    pairs,path=data("blind_pairs","paired")
    post,sp=data("blind_pairs","posthoc_and_costs")
    for r,diag in zip(pairs,post):
        a,b=r["parent_rows"],r["commit_rows"]
        assert r["commit"]==diag["commit"] and a.keys()==b.keys()
        assert all(a[k]["values"]==a[k]["expected"]==b[k]["values"]==b[k]["expected"] for k in a)
        p,c=r["project"],r["commit"]
        metric("documentation menu",p,c,"frozen","executed",2*len(a),"version_input",path,"full menu, both versions")
        metric("documentation menu",p,c,"frozen","checked_no_violation",1,"commit_pair",path)
        metric("documentation menu",p,c,"frozen","historical_detection",0,"commit_pair",path,denominator=1)
        x,y=diag["parent_data"]["witness"],diag["commit_data"]["witness"]
        state="post_reveal_witness" if x!=y else ("no_runtime_oracle" if x is None else "checked_no_difference")
        metric("documentation menu",p,c,"post-reveal",state,1,"commit_pair",sp)
    sides,path=data("interaction_blind","paired")
    findings,fp=data("interaction_blind","findings")
    for r in findings["pairs"]:
        g=[s for s in sides if s["id"]==r["commit"]]
        assert len(g)==2 and all(v["pass"] for s in g for v in s["rows"].values())
        metric("factorial inputs","attrs",r["commit"],"frozen","executed",sum(len(s["rows"]) for s in g),"version_input",path)
        metric("factorial inputs","attrs",r["commit"],"frozen","checked_no_violation",1,"commit_pair",path)
        metric("factorial inputs","attrs",r["commit"],"frozen","historical_detection",0,"commit_pair",path,denominator=1)
    w=findings["posthoc_1428"]
    assert w["parent"][1]["final"]==w["commit"][1]["final"] and w["parent"][1]["callback"]!=w["commit"][1]["callback"]
    metric("factorial inputs","attrs","937b1e2 / #1428","post-reveal","post_reveal_witness",1,"commit_pair",fp)
    metric("factorial inputs","dateutil","primary+supplement","screening","retained",0,"commit_pair",
           "runs_interaction_blind_20261124/sealed_supplement.json","both frames empty; no historical execution")


def boundary():
    ctr,cp=data("contract_boundary","contracts")
    pairs,path=data("contract_boundary","paired")
    find,fp=data("contract_boundary","findings")
    for p,v in ctr.items():
        for measure,count,unit in [("screened",v["documents_examined"],"method_description"),
                                   ("human_checked_extractions",len(v["records"]),"clause"),
                                   ("auto_extracted",len(v["records"]),"clause")]:
            metric("boundary clauses",p,"catalogue","frozen",measure,count,unit,cp,"supported matched clauses; exhaustive gold unavailable")
        metric("boundary clauses",p,"catalogue","frozen","all_human_confirmed_clauses",None,"clause",cp,"unmeasured")
        metric("boundary clauses",p,"catalogue","frozen","independent_path_proof_audit",None,"clause",cp,"unmeasured")
    for e in pairs:
        p,c=e["project"],e["id"]
        if "parent" not in e:
            rs=e["commit"]["rows"]
            assert all(v["boundary"]["result"]["ok"] for v in rs.values())
            metric("boundary clauses",p,c,"holdout reference","alerting_inputs",0,"input",path,denominator=len(rs))
            continue
        a,b=e["parent"]["rows"],e["commit"]["rows"]
        assert a.keys()==b.keys() and all(v[m]["result"]["ok"] for g in (a,b) for v in g.values() for m in v)
        metric("boundary clauses",p,c,"frozen","executed",2*len(a),"version_input",path,"full menu; three projections share inputs")
        metric("boundary clauses",p,c,"frozen","checked_no_violation",1,"commit_pair",path)
        metric("boundary clauses",p,c,"frozen","historical_detection",0,"commit_pair",path,denominator=1)
    for p,w in find["diagnostics"].items():
        assert w["parent"]!=w["commit"]
        key={"blinker":"e27fc051","pluggy":"443fee6d"}[p]
        metric("boundary clauses",p,key,"post-reveal","post_reveal_witness",1,"commit_pair",fp)


def order():
    tr,tp=data("order_contract","reference_traces")
    pred,pp=data("order_contract","predictions")
    obs,rp=data("order_contract","paired")
    audit,ap=data("order_contract","presentation_audit")
    for p,ref in tr.items():
        n=len(ref["trace"])
        assert all(not v["direct"] and not v["derived"] for v in pred[p].values())
        metric("order",p,"reference","frozen","human_confirmed_sequences",1,"successful_path_sequence",tp)
        metric("order",p,"reference","frozen","manual_reference_order",n*(n-1)//2,"event_pair",tp,"derived from one manual sequence")
        metric("order",p,"reference","frozen","auto_extracted",0,"event_pair",pp)
        metric("order",p,"reference","frozen","path_applicable_auto",0,"event_pair",pp,"empty generated set")
        ss=[s for s in obs if s["project"]==p]
        for c in sorted({s["id"] for s in ss}):
            sides=[s["observation"] for s in ss if s["id"]==c]
            assert len(sides)==2 and all(s["auto_order_ok"] is None and s["manual_order_ok"] is True for s in sides)
            metric("order",p,c,"frozen automatic","no_verdict",1,"commit_pair",rp)
            metric("order",p,c,"frozen automatic","executed_assertions",0,"version_sequence_check",rp)
            metric("order",p,c,"frozen manual","executed_assertions",2,"version_sequence_check",rp)
            metric("order",p,c,"frozen manual","checked_no_violation",1,"commit_pair",rp)
            metric("order",p,c,"frozen manual","historical_detection",0,"commit_pair",rp,denominator=1)
        v=audit[p]["normalized"]
        for measure,k in (("agrees_with_trace","identified"),("in_path_supported","in_path_supported")):
            metric("order",p,"reference","post-reveal format audit",measure,v[k],"event_pair",ap,denominator=v["total"])
        for a,b in v["unsupported_agreements"]:
            metric("order",p,f"{a} -> {b}","post-reveal format audit","agreement_without_in_path_proof",1,"event_pair",ap)
        metric("order",p,"reference","post-reveal format audit","supported_adjacent",v["supported_adjacent"],"adjacent_pair",ap,denominator=v["adjacent_total"])


def path_interventions():
    runs, path = data("path_intervention", "observations")
    lock, _ = data("path_intervention", "lock")
    assert runs.keys() == lock["revisions"].keys()
    for tag, cases in runs.items():
        assert [r["path"] for r in cases] == list(lock["design"])
        for run in cases:
            proofs = run["proofs"]
            assert len(proofs) == len(lock["chains"]) and all(run["setup_checks"].values())
            outcomes = [p["outcome"] for p in proofs]
            supported = outcomes.count("ordered_chain_observed")
            endpoint_agrees = {"ordered_chain_observed", "agreement_without_chain"}
            measurements = {
                "endpoint_agrees": sum(x in endpoint_agrees for x in outcomes),
                "endpoint_agrees_handler_present": sum(p["handler_observed"] and p["outcome"] in endpoint_agrees for p in proofs),
                "ordered_chain_observed": supported,
                "agreement_without_chain": outcomes.count("agreement_without_chain"),
                "outside_endpoint_scope": outcomes.count("outside_endpoint_scope"),
                "endpoint_contradiction": outcomes.count("endpoint_contradiction"),
            }
            case = f"{tag} / {run['path']}"
            metric("path intervention", "transitions", case, "designed diagnostic", "executed", 1, "event_run", path)
            for name, count in measurements.items():
                metric("path intervention", "transitions", case, "designed diagnostic", name,
                       count, "derivation_on_path", path, "callback entry order", denominator=len(proofs))


def controlled():
    m,path=data("empirical_study","budget_matrix")
    for p,conditions in m.items():
        for v in conditions:
            if v["method"]!="ABA":continue
            for key in ("hit","miss","budget","permission"):
                metric("controlled adapter",p,f"{v['perm']} / B={v['B']}","controlled",key,v[key],"layout_fault",path,
                       "nested budgets; rows are not independent defects")


if __name__=="__main__":
    known()
    blind()
    boundary()
    order()
    path_interventions()
    controlled()
    with (HERE/"evidence_ledger.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(rows),"ledger rows")

