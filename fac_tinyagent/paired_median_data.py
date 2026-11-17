"""Paired wording diagnostics for median tool selection; no model is loaded.

The returned episodes are developer diagnostics, not final policy evaluations.
Each numeric instance appears in two questions with identical tool arguments.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .config import PROJECT_ROOT
from .data.generate import build_system_prompt
from .research_data import task_signature
from .tools import build_stats_registry
from .utils import read_jsonl


DEFAULT_SEED = 20261110
WORDINGS = ("explicit", "natural")


def _value_key(values: Iterable[float]) -> Tuple[float, ...]:
    # Permuting an old instance does not make it a fresh median problem.
    return tuple(sorted(float(value) for value in values))


def _excluded_values(roots: Iterable[Path]) -> Set[Tuple[float, ...]]:
    excluded: Set[Tuple[float, ...]] = set()
    for root in roots:
        python_dir = Path(root) / "python"
        paths = sorted(python_dir.glob("*.jsonl"))
        if not paths:
            raise FileNotFoundError("No Python task files for exclusion: %s" % python_dir)
        for path in paths:
            for row in read_jsonl(path):
                if row.get("expected_tool") == "stats_median":
                    excluded.add(_value_key(row["expected_arguments"]["values"]))
    return excluded


def generate_paired_median(
    n_pairs: int = 96,
    seed: int = DEFAULT_SEED,
    exclusion_roots: Optional[Iterable[Path]] = None,
) -> List[Dict[str, Any]]:
    """Return executable episodes in explicit/natural pairs, without writing.

    Defaults exclude median instances from ``data_phase2`` and
    ``data_replay_study``, including permutations of their value lists.  All
    questions use seven distinct integers in [10, 100], the range used in the
    existing study.  A smaller ``n_pairs`` returns a prefix of a larger set for
    the same seed and exclusions, supporting nested sample-size comparisons.

    ``pair_id``, ``pair_index`` and ``wording`` provide analysis metadata. The
    third hyphen-separated episode-ID segment remains the template ID used by
    the existing report parser. These rows can go directly to evaluate_family.
    """
    if isinstance(n_pairs, bool) or not isinstance(n_pairs, int) or n_pairs < 1:
        raise ValueError("n_pairs must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    roots = (list(exclusion_roots) if exclusion_roots is not None else
             [PROJECT_ROOT / "data_phase2", PROJECT_ROOT / "data_replay_study"])
    used = _excluded_values(roots)
    rng = random.Random(seed)
    registry = build_stats_registry()
    system = build_system_prompt("python", registry.schemas())
    rows: List[Dict[str, Any]] = []
    attempts = 0
    while len(rows) < n_pairs * 2:
        attempts += 1
        if attempts > n_pairs * 100 + 1000:
            raise RuntimeError("Could not sample enough fresh median instances")
        values = rng.sample(range(10, 101), 7)
        key = _value_key(values)
        if key in used:
            continue
        used.add(key)
        pair_index = len(rows) // 2
        pair_id = "median_%s_%03d" % (seed, pair_index)
        value_text = json.dumps(values)
        prompts = {
            "explicit": "The observations are %s. What is their median?" % value_text,
            "natural": ("The observations are %s. After ordering them from smallest "
                        "to largest, what is the value in the middle position?") % value_text,
        }
        for wording in WORDINGS:
            arguments = {"values": list(values)}
            observation = registry.observation("stats_median", arguments)
            parsed = json.loads(observation)
            if not parsed.get("ok"):
                raise ValueError("Generated median task failed execution: %s" % observation)
            answer = parsed["result"]
            template = "paired_median_" + wording
            row = {
                "episode_id": "python-diagnostic-%s-%s_%03d" % (template, seed, pair_index),
                "tool_family": "python", "split": "diagnostic", "template_id": template,
                "pair_id": pair_id, "pair_index": pair_index, "wording": wording,
                "data_seed": seed, "skill_labels": ["stat_median", "numeric_input"],
                "prompt": prompts[wording], "system": system, "environment": {},
                "expected_tool": "stats_median", "expected_arguments": arguments,
                "expected_observation": observation, "expected_final_answer": answer,
                "answer_spec": {"kind": "identity"},
                "evaluation_only": True, "diagnostic_only": True,
                "selection_allowed": True, "final_evaluation_allowed": False,
            }
            row["data_signature"] = task_signature(row)
            row["messages"] = [
                {"role": "system", "content": system},
                {"role": "user", "content": row["prompt"]},
                {"role": "assistant", "content": json.dumps({
                    "tool": row["expected_tool"], "arguments": arguments})},
                {"role": "user", "content": "TOOL RESULT:\n" + observation},
                {"role": "assistant", "content": json.dumps({"answer": answer})},
            ]
            rows.append(row)
    return rows
