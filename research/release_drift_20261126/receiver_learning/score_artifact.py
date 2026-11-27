"""Rescore the 7a2971af observation artifacts. Does not recollect actions."""
import hashlib
import json
from pathlib import Path
from time import perf_counter

from oracle import STUDY_REQUIREMENTS, synthesize_oracle
from score import observation_cost, score_study

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "ci_artifacts"
RUN = {
    "run_id": 45916565880,
    "run_url": "https://github.com/oulu666/agent-evolution/actions/runs/45916565880",
    "head_sha": "7a2971af11aedf919814d9ffbec69ed5c0afddf6",
    "observations_recollected": False,
    "files": {
        "copy-receipt.json": {
            "artifact_id": 15162726382,
            "sha256": "09f059cab2d2954f96b0c90ffcc4860527c4ccd91b22b31156860b3fc7a4f632",
        },
        "jq-receipt.json": {
            "artifact_id": 15162403045,
            "sha256": "9ee81a3587466a265945f8dc950f062223c772513e4155c7da1e50d405618128",
        },
    },
}

FROZEN_KEYS = ("learned", "after_only", "lookup", "fixed_replay")
PROTOCOL_SENTENCE = "共同用户要求为内容保真，复制按文本，JSON 按精确十进制数值和结构比较。"


def load_artifact(name):
    path = ARTIFACTS / name
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != RUN["files"][name]["sha256"]:
        raise SystemExit(f"sha256 mismatch for {name}")
    return json.loads(data)


def _agree(old_rows, new_rows):
    mismatches = []
    for index, (old, new) in enumerate(zip(old_rows, new_rows, strict=True)):
        if old["truth"] != new["truth"]:
            mismatches.append({"index": index, "field": "truth"})
        for key in FROZEN_KEYS:
            if old["decisions"][key] != new["decisions"][key]:
                mismatches.append({"index": index, "field": key})
    return mismatches


def _brief(rows):
    return [{
        "input": row["input"], "version": row["version"], "truth": row["truth"],
        "decisions": row["decisions"], "slot_matches": row["slot_matches"],
    } for row in rows]


def _case(row):
    return {
        "input": row["input"], "version": row["version"], "truth": row["truth"],
        "decisions": row["decisions"], "slot_matches": row["slot_matches"],
    }


def _where(rows, predicate):
    return [_case(row) for row in rows if predicate(row)]


def _tied(rows, left, right):
    return all(row["decisions"][left] == row["decisions"][right] for row in rows)


def build_receipt():
    copy = load_artifact("copy-receipt.json")
    jq = load_artifact("jq-receipt.json")
    started = perf_counter()
    copy_scored = score_study(
        copy["demos"], copy["rows"], STUDY_REQUIREMENTS["copy"], 1, "material-copy-button")
    copy_cpu = perf_counter() - started
    modes = {}
    mode_cpu = {}
    for mode, receiver, action in (
            ("stdout", 3, "jq-stdout"), ("file", 2, "jq-file-redirect")):
        started = perf_counter()
        modes[mode] = score_study(
            jq["modes"][mode]["demos"], jq["modes"][mode]["rows"],
            STUDY_REQUIREMENTS["jq"], receiver, action)
        mode_cpu[mode] = perf_counter() - started
    copy_mismatch = _agree(copy["rows"], copy_scored["rows"])
    jq_mismatch = {
        mode: _agree(jq["modes"][mode]["rows"], modes[mode]["rows"]) for mode in modes}
    groups = [("copy", copy_scored)] + [(mode, modes[mode]) for mode in modes]
    lookup_tie = {name: _tied(scored["rows"], "learned", "lookup") for name, scored in groups}
    replay_tie = {name: _tied(scored["rows"], "learned", "fixed_replay") for name, scored in groups}
    jq_inputs = {
        mode: sorted({(row["version"], row["input"]) for row in modes[mode]["rows"] if row["truth"] is False})
        for mode in modes}
    unscored = [
        synthesize_oracle(PROTOCOL_SENTENCE, ["count: 41"]),
        synthesize_oracle("内容保真", ["count: 41"]),
        synthesize_oracle("内容保真，复制按文本", [None]),
        synthesize_oracle("页面应当便于阅读", ["count: 41"]),
        synthesize_oracle("按精确十进制数值和结构比较", ["count: 41"]),
        synthesize_oracle("按文本，并按精确十进制数值和结构比较", ["[1]"]),
    ]
    return {
        "provenance": RUN,
        "mechanism_b": {
            "implemented": False,
            "reason": "只包裹剪贴板接口，或按采集脚本里的标准输出/文件模式分支，都会重复查表。通用的 DOM 或系统调用轨迹仍要一张事件到位置的对照，而这张对照若按已知接收位置来写，就不是独立机制。这次没有这张独立对照，所以轨迹机制没有实现。",
        },
        "frozen_decision_mismatches": {"copy": copy_mismatch, "jq": jq_mismatch},
        "lookup_ties_learned": lookup_tie,
        "replay_ties_learned": replay_tie,
        "question_selection": "not_opened" if all(lookup_tie.values()) else "not_applicable",
        "ranking": None,
        "decision": "lookup_ties_learned_on_transfer" if all(lookup_tie.values()) else "lookup_does_not_tie",
        "local_rescore_cpu_seconds": {"copy": copy_cpu, "stdout": mode_cpu["stdout"], "file": mode_cpu["file"]},
        "unscored_requirements": unscored,
        "copy": {
            "oracle": copy_scored["oracle"],
            "slots_learned": copy_scored["slots_learned"],
            "slots_after_only": copy_scored["slots_after_only"],
            "lookup_slots": copy_scored["lookup_slots"],
            "truth_receiver": copy_scored["truth_receiver"],
            "metrics": copy_scored["metrics"],
            "cost": observation_cost(
                copy["demos"], copy["rows"], copy_scored["slots_learned"],
                copy_scored["slots_after_only"], copy_scored["lookup_slots"]),
            "cases": _brief(copy_scored["rows"]),
            "violation_rows": sorted(
                (row["version"], row["input"]) for row in copy_scored["rows"] if row["truth"] is False),
        },
        "jq": {
            "versions": jq["versions"],
            "independent_violation_inputs": sorted(set(jq_inputs["stdout"]) & set(jq_inputs["file"])),
            "modes": {
                mode: {
                    "oracle": modes[mode]["oracle"],
                    "slots_learned": modes[mode]["slots_learned"],
                    "slots_after_only": modes[mode]["slots_after_only"],
                    "lookup_slots": modes[mode]["lookup_slots"],
                    "truth_receiver": modes[mode]["truth_receiver"],
                    "metrics": modes[mode]["metrics"],
                    "cost": observation_cost(
                        jq["modes"][mode]["demos"], jq["modes"][mode]["rows"],
                        modes[mode]["slots_learned"], modes[mode]["slots_after_only"],
                        modes[mode]["lookup_slots"]),
                    "requirement_violations": _where(modes[mode]["rows"], lambda row: row["truth"] is False),
                    "replay_not_learned": _where(
                        modes[mode]["rows"],
                        lambda row: row["decisions"]["fixed_replay"] != row["decisions"]["learned"]),
                    "healthy_slot_example": _case(next(row for row in modes[mode]["rows"] if row["truth"] is True)),
                } for mode in modes},
        },
    }


def main():
    receipt = build_receipt()
    if receipt["frozen_decision_mismatches"] != {"copy": [], "jq": {"stdout": [], "file": []}}:
        raise SystemExit("rescore changed a frozen decision")
    path = HERE / "increment-receipt.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + "\n")
    print(path)


if __name__ == "__main__":
    main()
