"""[ext 2026-11-11] Unit checks for data_ext_e4 (CPU only).
Run: .venv/bin/python scripts/test_e4_data.py
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fac_tinyagent import e4_data as E  # noqa: E402
from fac_tinyagent.utils import read_json, read_jsonl  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


old_ids = set(read_json(E.R2 / "manifest.json")["target_ids"]["file"])
ref = E.check_file_rows(read_jsonl(E.R2 / "pool" / "file.jsonl"))
check("checker flags exactly the 16 known mislabeled round2 targets",
      ref["n_bad"] == 16 and {b["episode_id"] for b in ref["bad"]} == old_ids)
ref_final = E.check_file_rows(read_jsonl(E.R2 / "final" / "file.jsonl"))
check("checker flags all 30 round2 final File rows (whole-list gold)", ref_final["n_bad"] == 30)
pool = read_jsonl(E.OUT / "pool" / "file.jsonl")
check("new File pool: 0 label/execution failures", E.check_file_rows(pool)["n_bad"] == 0)
check("final_v2 File: 0 label/execution failures",
      E.check_file_rows(read_jsonl(E.OUT / "final_v2" / "file.jsonl"))["n_bad"] == 0)
tid = set(read_json(E.OUT / "manifest.json")["target_ids"]["file"])
row = copy.deepcopy(next(r for r in pool if r["episode_id"] in tid))
row["expected_final_answer"] = json.loads(row["expected_observation"])["result"]
check("checker catches an injected whole-list label", E.check_file_rows([row])["n_bad"] == 1)
row2 = copy.deepcopy(next(r for r in pool if r["episode_id"] in tid))
res = json.loads(row2["expected_observation"])["result"]
if len(res) > 1:
    row2["expected_final_answer"] = res[0]["text"]
    row2["messages"][4]["content"] = json.dumps({"answer": res[0]["text"]})
    check("checker catches an injected first-instead-of-last label", E.check_file_rows([row2])["n_bad"] == 1)
cal = read_jsonl(E.OUT / "final_v2" / "calendar.jsonl")
check("calendar final: 30 rows, 6 types x 5", len(cal) == 30 and
      all(n == 5 for n in __import__("collections").Counter(r["target_type"] for r in cal).values()))
check("calendar gold re-derived from fixture JSON matches",
      all(E._answers_equal(E.calendar_semantic_gold(r), r["expected_final_answer"]) for r in cal))
check("no old target id left in pool", not (old_ids & {r["episode_id"] for r in pool}))
res = E.verify()
check("verify() ok (hashes, leakage, executed gold)", res["ok"])
print("ALL_PASS" if not fails else "FAILED %s" % fails)
sys.exit(1 if fails else 0)
