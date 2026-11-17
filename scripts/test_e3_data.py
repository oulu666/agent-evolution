"""[ext 2026-11-11] CPU checks for E3 (no GPU, no model weights).
Run: .venv/bin/python scripts/test_e3_data.py          (after data_ext_e3 is built)
     .venv/bin/python scripts/test_e3_data.py --unit   (synthetic plan tests + trainer-copy check only)
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fac_tinyagent import e3_data as D  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# ---- synthetic pools: dose / control plan logic
rng = random.Random(1)
pools = {}
for f, nt in (("file", 16), ("database", 11), ("python", 14)):
    rows = []
    for i in range(80):
        t = rng.randint(250, 420)
        rows.append({"family": f, "row_index": i, "episode_id": "%s-%03d" % (f, i), "input_tokens": t,
                     "supervised_tokens": t // 4, "target": i < nt})
    pools[f] = rows
B = 7494
plans = {k: D.dose_plan(pools, B, 123, k) for k in D.DOSES}
check("dose: exact Database target count for every k",
      all(p["target_samples_by_family"]["database"] == k for k, p in plans.items()))
check("dose (synthetic pool): total replay within [97%, 100%] of budget for every k (real plans: 1% rule in verify)",
      all(0.97 * B <= p["actual_input_tokens"] <= B for p in plans.values()))
check("dose: File/Python blocks (targeted + uniform) identical across k",
      len({(tuple(p["e3_plan"]["fp_target_ids"]), tuple(p["e3_plan"]["fp_uniform_ids"])) for p in plans.values()}) == 1)
dbt = [p["e3_plan"]["db_replay_tokens"] for p in plans.values()]
check("dose: Database replay tokens ~constant across k (spread <= 450 = ~1 row): %s" % dbt, max(dbt) - min(dbt) <= 450)
check("dose: Database unique samples recorded", all(p["e3_plan"]["db_unique_samples"] >= p["e3_plan"]["k"] for p in plans.values()))
p2 = {k: D.dose_plan(pools, B, 123, k, draw=2) for k in D.DOSES}
check("dose draw 2: different nested subset, same File/Python blocks",
      p2[6]["e3_plan"]["db_target_ids"] != plans[6]["e3_plan"]["db_target_ids"]
      and p2[6]["e3_plan"]["fp_uniform_ids"] == plans[6]["e3_plan"]["fp_uniform_ids"])
dbs = [plans[k]["e3_plan"]["db_target_ids"] for k in D.DOSES]
check("dose: nested Database targets", all(dbs[i] == dbs[i + 1][:len(dbs[i])] for i in range(len(dbs) - 1)))
check("dose: no target row outside the targeted part",
      all(not (i.get("target") and i["episode_id"] not in p["e3_plan"]["db_target_ids"] + p["e3_plan"]["fp_target_ids"])
          for p in plans.values() for i in p["items"]))
check("dose: deterministic", D.plan_signature(D.dose_plan(pools, B, 123, 6)) == D.plan_signature(plans[6]))
cal = {"calendar": [{"family": "calendar", "row_index": i, "episode_id": "calendar-%03d" % i, "input_tokens": rng.randint(380, 560),
                     "supervised_tokens": 60, "target": False} for i in range(80)]}
cp = D.control_plan(cal, B, 123, n_target=17)
check("control: only Calendar rows, exactly n_target=17 rows, within [99%, 100%] budget",
      all(i["family"] == "calendar" for i in cp["items"]) and len(cp["items"]) == 17
      and 0.99 * B <= cp["actual_input_tokens"] <= B)
check("control: steps_for(17) == steps_for(22) == 23", D.steps_for(17) == D.steps_for(22) == 23)
check("arms: E3-A 9 + E3-B 6 per seed (+5 optional draw-2)", len(D.JOB_ORDER_A) == 9 and len(D.JOB_ORDER_B) == 6
      and len(D.JOB_ORDER_B2) == 5)

# ---- trainer copy fidelity: every original line of train_replay_stage appears, in order, in e3_train
root = Path(__file__).resolve().parents[1] / "fac_tinyagent"
orig = (root / "replay_train.py").read_text(encoding="utf-8")
orig = orig[orig.index("def train_replay_stage("):].replace("def train_replay_stage(", "def train_replay_stage_e3(")
orig = orig.replace("target_family_weights: Optional[Mapping[str, float]] = None\n                       ) -> Dict[str, Any]:", "")
copy = (root / "e3_train.py").read_text(encoding="utf-8")
copy = copy[copy.index("def train_replay_stage_e3("):]
ol, cl = [x for x in orig.splitlines() if x.strip() or not x], copy.splitlines()
j = 0
for line in ol:
    while j < len(cl) and cl[j] != line:
        j += 1
    j += 1
check("e3_train: original train_replay_stage preserved line-by-line (only additions)", j <= len(cl))
check("e3_train: added lines are few (<= 25)", len(cl) - len(ol) <= 25)

if "--unit" not in sys.argv:
    c = D.verify()
    check("frozen hashes final v2 / Calendar v3", c["final_v2_hash_ok"] and c["calendar_v3_hash_ok"])
    check("leakage: v2 and v3 vs Calendar train + E4 pools + probes = 0", c["leakage"]["ok"])
    check("formal prefix metadata equals E4 prefixes (all seeds)", all(c["prefix_metadata_equals_e4"].values()))
    check("real plans: no problems and frozen plans match: %s" % c["plan_problems"], not c["plan_problems"])
print("ALL_PASS" if not fails else "FAILED %s" % fails)
sys.exit(1 if fails else 0)
