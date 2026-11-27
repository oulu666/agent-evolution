"""Run the joint Receiver–Oracle development cases and write a receipt."""
import hashlib
import json
import subprocess
from pathlib import Path
from time import perf_counter

from joint_score import COMPARED, SPLIT_SYSTEMS, observation_cost, score_case
from joint_systems import run_systems
from joint_world import CASES, EXTRA_BUDGET, collect_case
from oracle import synthesize_oracle
from joint_oracle import fixed_oracle
from learn import select
from joint import initial_H, score_observations

HERE = Path(__file__).resolve().parent

# Filled after a limited public search, only if the synthetic joint case
# shows independent gain versus the three split systems. The default is
# that no qualified real case has been admitted.
PUBLIC_TRANSFER = {
    "searched": True,
    "qualified_case_found": False,
    "reason": (
        "合成机制验证已完成：联合学习在 synthetic_joint_receiver_oracle 上相对三种拆开系统有 2 行独立收益，"
        "但更强对照已经覆盖这些行。限时检索未见真实工作流，尚无合格案例，因此不能论证两项组件在真实任务上存在真正互补。"
        "合取标准未放宽。近例要么是单一常规导出或下载槽，可迁移查表或自动定位加固定判据就能检查；"
        "要么是格式偏好或开发期行为，不是可在冻结闭集关系下与可信原文比较的发布缺陷；"
        "要么缺少两个同类型候选位置与多种相容 (r, o) 组合并存、只有正确组合能通过全部证据的结构。"
        "未发明故障，未改写查表让它故意绑错，也未把 Material 复制、jq 或已排除近例重新纳入。"
    ),
    "examined_this_round": [
        {
            "id": "zen-browser/desktop#8535",
            "url": "https://github.com/zen-browser/desktop/issues/8535",
            "reason": "内置 JSON 查看器保存会丢条目，复制却是完整的。出问题的是保存/下载这一常规文件槽，可迁移查表会绑定该文件并在任一冻结关系下拦住。",
        },
        {
            "id": "Shopify/cli#3719",
            "url": "https://github.com/Shopify/cli/issues/3719",
            "reason": "Admin 下载、GitHub 同步与 CLI 对主题 JSON 的最小化或转义不一致。各路径仍是常规下载或同步文件槽；若可信原文给定，固定 full_string 也能在该槽上发现文本差异。",
        },
        {
            "id": "payloadcms/payload#13210",
            "url": "https://github.com/payloadcms/payload/issues/13210",
            "reason": "JSON 预览曾被拍平，导出也曾写成 CSV 风格。可迁移查表仍会绑定导出文件；这不是同类型双文件加关系歧义的联合约束情形。",
        },
        {
            "id": "unjs/nitro#1605",
            "url": "https://github.com/unjs/nitro/issues/1605",
            "reason": "开发模式下代理 JSON 被美化打印，维护者视为开发期特性而非生产缺陷；也只有单一响应通道，构不成 (r, o) 相互约束。",
        },
        {
            "id": "snipe/snipe-it#10344",
            "url": "https://github.com/snipe/snipe-it/issues/10344",
            "reason": "Web UI 导出给部分字段前置空白，出问题的是单一导出文件槽。",
        },
        {
            "id": "googleworkspace/cli#743",
            "url": "https://github.com/googleworkspace/cli/issues/743",
            "reason": "files export 写到 download.txt 而非标准输出，属于通道或路径约定问题，不是闭集关系下中间文件与消费端格式相互约束的合格案例。",
        },
    ],
    "previously_excluded_not_readmitted": [
        "elastic/kibana#241730",
        "supabase/supabase#42818",
        "kubernetes/website#23817",
        "kubernetes/website#42179",
        "jupyter/notebook#4481",
        "outline/outline#3972",
        "nexu-io/open-design#1842",
        "kubeflow/pipelines#3814",
    ],
}



def _public_system(result):
    payload = {
        "name": result["name"],
        "pairs": [list(pair) for pair in result["pairs"]],
        "positions": result["positions"],
        "relations": result["relations"],
        "relation": result["relation"],
        "abstain": result["abstain"],
        "extra_observations": result["extra_observations"],
        "unique_receiver": result["unique_receiver"],
        "unique_relation": result["unique_relation"],
        "rank": result["rank"],
        "note": result["note"],
    }
    if "observer_log" in result:
        payload["observer_log"] = result["observer_log"]
    if "choice" in result:
        choice = result["choice"]
        payload["choice"] = {
            "action": choice.get("action"),
            "rank": choice.get("rank"),
            "chosen": choice.get("chosen"),
            "scores": choice.get("scores"),
        }
    if "structure" in result:
        payload["structure"] = result["structure"]
    if result.get("used_all_demo_channels"):
        payload["used_all_demo_channels"] = True
    return payload


def _gain_summary(cases):
    by_case = {}
    for case_id, scored in cases.items():
        by_case[case_id] = {
            "vs_three_split_systems": scored["independent_gain_rows"]["vs_three_split_systems"],
            "vs_strong_control": scored["independent_gain_rows"]["vs_strong_control"],
        }
    any_vs_split = any(item["vs_three_split_systems"] for item in by_case.values())
    any_vs_strong = any(item["vs_strong_control"] for item in by_case.values())
    return {
        "by_case": by_case,
        "any_independent_gain_vs_split": any_vs_split,
        "any_independent_gain_vs_strong_control": any_vs_strong,
    }


def _initial_pairs(public):
    pairs, structure = initial_H(public["demos"], public["slots"], public["requirement"])
    return {
        "pairs": [list(pair) for pair in pairs],
        "compatible_slots": structure["compatible_slots"],
        "synthesized_relation": structure["relation"],
        "synthesized_abstain": structure["abstain"],
        "fixed_oracle": fixed_oracle(public["requirement"], public["action"]),
    }


def build_receipt(public_transfer=None):
    started = perf_counter()
    repo = HERE.parents[2]
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        repo = Path("/workspace/agent-evolution-main-88ca0d20")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    cases = {}
    for case in CASES:
        public, hidden = collect_case(case)
        systems = run_systems(public, hidden)
        scored = score_case(public, hidden, systems)
        costs = observation_cost(public, systems)
        sources = [demo["expected"] for demo in public["demos"]]
        synthesized = synthesize_oracle(public["requirement"], sources)
        # select() under the labeled truth relation, for the report only.
        truth_candidates = select(public["demos"], hidden["truth_relation"], True)
        cases[case["id"]] = {
            "synthetic": True,
            "mechanism_development_only": True,
            "not_independent_defect_evidence": True,
            "kind": public["kind"],
            "requirement": public["requirement"],
            "slots": public["slots"],
            "truth_receiver": hidden["truth_receiver"],
            "truth_relation": hidden["truth_relation"],
            "select_candidates_under_truth_relation": truth_candidates,
            "select_unique": len(truth_candidates) == 1,
            "initial_H": _initial_pairs(public),
            "synthesized_oracle": synthesized,
            "demo_inputs": [demo["input"] for demo in public["demos"]],
            "test_inputs": sorted({row["input"] for row in public["rows"]}),
            "violation_rows": [
                {"input": row["input"], "version": row["version"]}
                for row in scored["rows"] if row["truth"] is False
            ],
            "healthy_rows": [
                {"input": row["input"], "version": row["version"]}
                for row in scored["rows"] if row["truth"] is True
            ],
            "slot_matches_examples": {
                "v1_trigger": next(row["slot_matches_truth_relation"] for row in scored["rows"]
                                   if row["version"] == "v1" and row["input"].startswith("trigger")),
                "v1_single": next(row["slot_matches_truth_relation"] for row in scored["rows"]
                                  if row["version"] == "v1" and row["input"].startswith("single")),
                "v2_trigger": next(row["slot_matches_truth_relation"] for row in scored["rows"]
                                   if row["version"] == "v2" and row["input"].startswith("trigger")),
            },
            "systems": {name: _public_system(systems[name]) for name in systems},
            "accuracy": scored["accuracy"],
            "metrics": scored["metrics"],
            "cost": costs,
            "independent_gain_rows": scored["independent_gain_rows"],
            "row_decisions": [
                {
                    "input": row["input"],
                    "version": row["version"],
                    "truth": row["truth"],
                    "decisions": row["decisions"],
                    "slot_matches_truth_relation": row["slot_matches_truth_relation"],
                }
                for row in scored["rows"]
            ],
        }
    receipt = {
        "synthetic_only": True,
        "not_independent_defect_evidence": True,
        "core_algorithm_not_established": True,
        "auto_oracle_generation_not_a_novelty_claim": True,
        "base_head": head,
        "extra_observation_budget": EXTRA_BUDGET,
        "compared_systems": list(COMPARED),
        "split_systems": list(SPLIT_SYSTEMS),
        "model_calls": 0,
        "cases": cases,
        "independent_gain": _gain_summary(cases),
        "public_transfer": public_transfer or dict(PUBLIC_TRANSFER),
        "local_cpu_seconds": None,
    }
    receipt["local_cpu_seconds"] = perf_counter() - started
    return receipt


def write_receipt(receipt, path=None):
    path = path or (HERE / "joint-receipt.json")
    # Drop the volatile CPU field from the hashed copy used in tests by
    # keeping it in the file but allowing tests to ignore it.
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + "\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest


def main():
    receipt = build_receipt()
    path, digest = write_receipt(receipt)
    print(path)
    print(digest)
    return path


if __name__ == "__main__":
    main()
