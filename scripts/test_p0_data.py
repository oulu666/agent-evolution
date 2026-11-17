"""CPU checks for P0 frozen exams (run after build+freeze)."""
from __future__ import annotations

import json
from pathlib import Path

from fac_tinyagent.p0_cal_titlecount import check as check_cal, FIXTURE, OUT as CAL_OUT, VERSION as CAL_VER
from fac_tinyagent.p0_db_nontarget import check as check_db, OUT as DB_OUT, VERSION as DB_VER, BANDS
from fac_tinyagent.utils import read_json, read_jsonl, sha256_file

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    problems = []
    cal_rows = read_jsonl(CAL_OUT / "final" / "title_count_v3fix.jsonl")
    cal_fz = read_json(CAL_OUT / "final" / "FROZEN.json")
    cal_chk = check_cal(cal_rows)
    if not cal_chk["ok"]:
        problems.append("calendar checks failed")
    if sha256_file(CAL_OUT / "final" / "title_count_v3fix.jsonl") != cal_fz["files"]["title_count_v3fix"]["sha256"]:
        problems.append("calendar hash mismatch")
    if cal_fz["version"] != CAL_VER:
        problems.append("calendar version mismatch")
    if sha256_file(FIXTURE) != cal_fz["fixture"]["sha256"]:
        problems.append("v3 fixture hash changed")
    if len(cal_rows) != 30:
        problems.append("calendar n=%d" % len(cal_rows))
    if any("day_count" not in r["episode_id"] for r in cal_rows):
        problems.append("expected only day_count items")
    golds = [r["expected_final_answer"] for r in cal_rows]
    if any(g < 1 or g > 4 for g in golds):
        problems.append("day_count gold outside 1-4: %s" % golds)
    if len(set(golds)) < 2:
        problems.append("day_count golds not diverse: %s" % golds)

    db_rows = read_jsonl(DB_OUT / "final" / "database_nontarget.jsonl")
    db_fz = read_json(DB_OUT / "final" / "FROZEN.json")
    db_chk = check_db(db_rows)
    if not db_chk["ok"]:
        problems.append("database checks failed: %s" % {k: db_chk[k] for k in db_chk if k.endswith("mismatch") or k.startswith("overlap") or k == "ok"})
    if sha256_file(DB_OUT / "final" / "database_nontarget.jsonl") != db_fz["files"]["database_nontarget"]["sha256"]:
        problems.append("db hash mismatch")
    if db_fz["version"] != DB_VER:
        problems.append("db version mismatch")
    for r in db_rows:
        sql = r["expected_arguments"]["sql"].upper()
        if "ORDER BY" in sql and "LIMIT" in sql:
            problems.append("filter_top-like SQL %s" % r["episode_id"])
        if r["template_id"].startswith("target_"):
            problems.append("target template leaked %s" % r["episode_id"])
    bands = {r["target_type"] for r in db_rows}
    if bands != {"nontarget_" + b for b in BANDS}:
        problems.append("unexpected bands %s" % bands)
    if len(db_rows) != 40:
        problems.append("db n=%d" % len(db_rows))

    probe = ROOT / "data_ext_p0_batched" / "probe.jsonl"
    if probe.exists():
        pr = read_jsonl(probe)
        if len(pr) != 44:
            problems.append("probe n=%d" % len(pr))

    if problems:
        raise SystemExit("TEST_P0_FAIL " + json.dumps(problems, ensure_ascii=False))
    print("TEST_P0_OK", "cal", cal_fz["combined_sha256"][:16], "db", db_fz["combined_sha256"][:16])


if __name__ == "__main__":
    main()
