"""[ext 2026-11-11] Label-consistent re-scoring for Round-2 File last-match rows.

data_round2 monitor/final/pool File rows ask "Return the last line in X that
contains the word W" but were built with answer_spec identity, so their gold
answer is the *whole* match list (round2_data._make_row discards the computed
last-line answer).  A model that correctly returns only the last line is scored
wrong.  This module re-scores existing results.jsonl rows without touching
them: tool/argument/execution checks are kept; only the final answer is judged
against the last matching line.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple


def is_round2_last_match(row: Dict[str, Any]) -> bool:
    eid = str(row.get("episode_id", ""))
    return row.get("tool_family") == "file" and "-last-" in eid and eid.startswith("round2_")


def _candidates(pred: Any) -> Optional[Tuple[Optional[str], Optional[int]]]:
    if isinstance(pred, list) and len(pred) == 1:
        pred = pred[0]
    if isinstance(pred, str):
        return pred.strip(), None
    if isinstance(pred, dict) and "text" in pred:
        line = pred.get("line")
        try:
            line = int(line) if line is not None else None
        except (TypeError, ValueError):
            line = None
        return str(pred["text"]).strip(), line
    return None


def last_line_correct(row: Dict[str, Any], lenient: bool = True) -> bool:
    try:
        matches = json.loads(row["expected_observation"])["result"]
    except Exception:
        return False
    if not matches:
        return False
    last = matches[-1]
    cand = _candidates(row.get("predicted_answer"))
    if cand is None:
        return False
    text, line = cand
    if line is not None and line != int(last["line"]):
        return False
    if text == last["text"]:
        return True
    if lenient:
        body = last["text"].split(": ", 1)[-1]
        return text == body
    return False


def corrected_joint(row: Dict[str, Any], lenient: bool = True) -> bool:
    if not is_round2_last_match(row):
        return bool(row.get("joint_success"))
    calls_ok = all(row.get(k, False) for k in
                   ("tool_correct", "arguments_correct", "execution_success"))
    return bool(calls_ok and last_line_correct(row, lenient))


def score(rows: List[Dict[str, Any]], corrected: bool = True,
          lenient: bool = True) -> Tuple[int, int]:
    k = sum(corrected_joint(r, lenient) if corrected else bool(r.get("joint_success"))
            for r in rows)
    return k, len(rows)
