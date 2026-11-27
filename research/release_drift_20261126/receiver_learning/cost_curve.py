"""Cost–correctness curve on the three existing synthetic joint cases.

This addendum does not change the original joint scoring denominators or
rewrite joint-receipt.json. It re-uses the same cases and decision rule,
and measures real tool operations with an instrumented world.

Real tool operations are instrumented calls into the simulated world, not
reconstructed logical slot counts. Logical reads are reported separately.
"""
from __future__ import annotations

import itertools

from joint import (
    RANK_DETERMINED,
    RANK_RECEIVER_OPEN,
    RANK_RELATION_OPEN,
    apply_observation,
    choose_observation,
    decision_rank,
    decide_row,
    initial_H,
    learn_joint,
    receivers_of,
)
from joint_baselines import transferable_lookup_positions
from joint_oracle import fixed_oracle
from joint_score import metrics_for
from joint_world import EXTRA_BUDGET, HealthyObserver, _demo_payload
from learn import equivalent


PHASE_DEMO = "demo_collection"
PHASE_EXTRA = "extra_observation"
PHASE_RUNTIME = "runtime_accept"
PHASE_HARNESS = "harness"

REAL_KINDS = ("generate", "consumer_read", "artifact_read")
LEGAL_OBSERVATIONS = ("subsequent_reads", "contrast_canaries", "reread_known_slot")
FULL_TRACE_ORDER = ("subsequent_reads", "contrast_canaries")
# When quality and real tool-operation counts are identical, prefer the
# less invasive observation. This is a tie-break only, not a weakening:
# subsequent_reads and contrast_canaries induce the same partition of H
# and have the same generate+consume cost.
STATIC_TIEBREAK = {"subsequent_reads": 0, "contrast_canaries": 1, "reread_known_slot": 2}
BUDGETS = (0, 1, 2)

# Quality is compared lexicographically in this order. Cost is only a
# tie-breaker after the release-decision metrics, because the curve is
# about cost versus correctness, not about minimizing calls alone.
QUALITY_KEYS = (
    "false_release",
    "correct_block",
    "violation_deferred",
    "retention",
    "false_block",
    "healthy_deferred",
)


class ToolMeter:
    """Record every real world call, tagged by phase."""

    def __init__(self):
        self.events = []

    def record(self, kind, phase, **detail):
        if kind not in REAL_KINDS and kind != "logical_slot_read":
            raise ValueError(kind)
        event = {"kind": kind, "phase": phase, **detail}
        self.events.append(event)
        return event

    def real_events(self, phase=None):
        items = [event for event in self.events if event["kind"] in REAL_KINDS]
        if phase is not None:
            items = [event for event in items if event["phase"] == phase]
        return items

    def count(self, phase=None, kind=None):
        items = self.real_events(phase)
        if kind is not None:
            items = [event for event in items if event["kind"] == kind]
        return len(items)

    def summary(self):
        by_phase = {PHASE_DEMO: 0, PHASE_EXTRA: 0, PHASE_RUNTIME: 0}
        by_kind = {kind: 0 for kind in REAL_KINDS}
        by_phase_kind = {
            phase: {kind: 0 for kind in REAL_KINDS}
            for phase in (PHASE_DEMO, PHASE_EXTRA, PHASE_RUNTIME)
        }
        for event in self.real_events():
            phase = event["phase"]
            kind = event["kind"]
            if phase in by_phase:
                by_phase[phase] += 1
            if kind in by_kind:
                by_kind[kind] += 1
            if phase in by_phase_kind and kind in by_phase_kind[phase]:
                by_phase_kind[phase][kind] += 1
        return {
            "real_tool_operations_total": len(self.real_events()),
            "by_phase": by_phase,
            "by_kind": by_kind,
            "by_phase_and_kind": by_phase_kind,
            "events": list(self.real_events()),
        }


class MeteredWorld:
    """Proxy around ExportWorld that records generate and consume calls."""

    def __init__(self, world, meter):
        self._world = world
        self.meter = meter
        self.phase = PHASE_HARNESS
        self.case_id = world.case_id
        self.kind = world.kind
        self.slots = world.slots

    def generate(self, version, input_name, payload):
        result = self._world.generate(version, input_name, payload)
        self.meter.record(
            "generate",
            self.phase,
            input=input_name,
            version=version,
            n_write_events=len(result["events"]),
        )
        return result

    def consume(self, after):
        value, event = self._world.consume(after)
        self.meter.record(
            "consumer_read",
            self.phase,
            slot=event["slot"],
            type=event.get("type"),
            path=event.get("path"),
        )
        return value, event


class MeteredObserver:
    """Same observation API as HealthyObserver, with a metered world."""

    def __init__(self, world, demos, meter, budget=EXTRA_BUDGET, unlimited=False):
        self.meter = meter
        self._world = world
        self._inner = HealthyObserver(world, demos, budget=budget, unlimited=unlimited)
        self.budget = budget
        self.unlimited = unlimited
        self.log = self._inner.log

    @property
    def calls(self):
        return self._inner.calls

    def subsequent_reads(self, input_name):
        previous = self._world.phase
        self._world.phase = PHASE_EXTRA
        try:
            return self._inner.subsequent_reads(input_name)
        finally:
            self._world.phase = previous

    def contrast_canaries(self, input_name, overlays):
        previous = self._world.phase
        self._world.phase = PHASE_EXTRA
        try:
            return self._inner.contrast_canaries(input_name, overlays)
        finally:
            self._world.phase = previous

    def reread_known_slot(self, input_name, slot):
        self._inner._use("reread_known_slot", input_name)
        demo = self._inner._allowed[input_name]
        self.meter.record(
            "artifact_read",
            PHASE_EXTRA,
            slot=slot,
            input=input_name,
            note="reread_known_slot",
        )
        self.log[-1] = {"name": "reread_known_slot", "slot": slot}
        return demo["after"][slot]


def counting_rule():
    return {
        "real_tool_operations": {
            "generate": (
                "一次 ExportWorld.generate 调用，即把软件在某个输入上完整跑一遍并写出全部槽。"
                "健康示范采集阶段每条示范计 1 次；额外观察里 subsequent_reads 与 contrast_canaries"
                "各自会再跑一遍健康示范输入，再计 1 次。"
            ),
            "consumer_read": (
                "一次 ExportWorld.consume 调用，即让下游程序读取它实际消费的那个产物。"
                "只出现在额外观察里的 subsequent_reads 与 contrast_canaries，每种观察各 1 次。"
            ),
            "artifact_read": (
                "一次对已存在产物槽的读取：运行时验收按被冻结的接收端，每行每个接收端计 1 次；"
                "额外观察 reread_known_slot 对已见示范槽计 1 次。同一接收端上多种关系只读一次产物，"
                "关系比较在内存中完成。"
            ),
        },
        "phases": {
            PHASE_DEMO: (
                "健康示范采集。只有需要示范前后值来构造 H 或做 select 的方法才计这部分："
                "联合学习、最优静态观察、完整追踪各计 2 次 generate（两条健康示范）。"
                "可迁移查表只看任务文字和槽类型，不计示范采集。"
            ),
            PHASE_EXTRA: (
                "额外观察。subsequent_reads 与 contrast_canaries 各计 1 次 generate 加 1 次"
                "consumer_read；reread_known_slot 计 1 次 artifact_read。预算按观察条数计，"
                "不以内部事件条数计。"
            ),
            PHASE_RUNTIME: (
                "运行时验收读取。方法已经冻结至少一个接收端时，对 8 行测试各读取这些接收端；"
                "暂缓则不读，计 0。评测夹具为构造行而执行的 8 次 generate 记在 harness 下，"
                "不计入任一方法的观察成本。"
            ),
        },
        "not_real_tool_operations": (
            "构造 H 时对已采集示范前后值做 equivalent() 的逻辑比较；"
            "完整追踪声明检查全部示范通道时的逻辑读数；"
            "评测夹具为准备测试行而做的 generate。这些另栏报告，不称作真实工具操作。"
        ),
        "budget": (
            "额外观察预算是 subsequent_reads、contrast_canaries、reread_known_slot 的条数上限，"
            "默认与原实验相同为 1。同等预算指同一上限，不是指方法实际花掉的条数。"
            "无预算限制的完整追踪不受该上限约束，并执行全部消费向观察。"
        ),
        "optimal_static": (
            "预先固定观察计划，执行中不根据反馈改计划。在相同可选观察集与预算下枚举全部计划，"
            "用隐藏标签在事后按发布决策质量、再按真实工具操作数选择最好的计划。"
            "这是静态方法的上界，不是一种可在未见任务上先于标签使用的选择器。"
            "计划按案例分别选择；同时另报三条案例共用的最好固定计划。"
        ),
        "full_trace": (
            "固定穷尽顺序 subsequent_reads 然后 contrast_canaries，不按发布决定价值跳过。"
            "同等预算下执行该顺序中前 B 条（B=0 则不观察）。无限制时两条都执行，并标记检查了全部示范通道。"
            "不得为了给联合学习制造成本优势而少做消费追踪。"
        ),
    }


def _quality_tuple(metrics):
    # Lower is better for penalties; flip the goods.
    return (
        metrics["false_release"],
        -metrics["correct_block"],
        metrics["violation_deferred"],
        -metrics["retention"],
        metrics["false_block"],
        metrics["healthy_deferred"],
    )


def quality_at_least_as_good(left, right):
    return _quality_tuple(left) <= _quality_tuple(right)


def quality_strictly_better(left, right):
    return _quality_tuple(left) < _quality_tuple(right)


def quality_equal(left, right):
    return _quality_tuple(left) == _quality_tuple(right)


def _truth_of(row, hidden):
    return equivalent(row["after"][hidden["truth_receiver"]], row["expected"], hidden["truth_relation"])


def _logical_demo_reads(public):
    return len(public["demos"]) * 2 * len(public["slots"])


def collect_demos(public, metered_world, meter):
    meter.phase = PHASE_DEMO
    metered_world.phase = PHASE_DEMO
    demos = []
    for demo in public["demos"]:
        payload = _demo_payload(metered_world, demo)
        run = metered_world.generate("v1", demo["input"], payload)
        demos.append(run)
    return demos


def _pairs_record(pairs, abstain, extra, plan, note=None):
    pairs = list(pairs or [])
    receivers = list(receivers_of(pairs)) if abstain is None else []
    relations = sorted({relation for _, relation in pairs}) if abstain is None else []
    return {
        "pairs": [list(pair) for pair in pairs],
        "positions": receivers,
        "relations": relations,
        "abstain": abstain,
        "extra_observations": extra,
        "plan": list(plan),
        "unique_receiver": abstain is None and len(receivers) == 1,
        "unique_relation": abstain is None and len(relations) == 1,
        "rank": decision_rank(pairs) if pairs else None,
        "note": note,
    }


def decide_rows(public, hidden, pairs, abstain, meter):
    scored = []
    unique_receivers = list(receivers_of(pairs)) if abstain is None and pairs else []
    for row in public["rows"]:
        if abstain is not None or not pairs:
            decision = None
        else:
            for receiver in unique_receivers:
                meter.record(
                    "artifact_read",
                    PHASE_RUNTIME,
                    slot=receiver,
                    input=row["input"],
                    version=row["version"],
                )
            decision = decide_row(row["after"], row["expected"], pairs)
        scored.append({
            "input": row["input"],
            "version": row["version"],
            "truth": _truth_of(row, hidden),
            "decisions": {"method": decision},
        })
    metrics = metrics_for(scored, methods=("method",))["method"]
    return scored, metrics


def cost_payload(meter, public, extra, used_all_demo_channels, uses_demos):
    summary = meter.summary()
    logical_build = _logical_demo_reads(public) if uses_demos else 0
    if used_all_demo_channels:
        logical_build = _logical_demo_reads(public)
    return {
        "model_calls": {"build": 0, "run": 0},
        "real_tool_operations_total": summary["real_tool_operations_total"],
        "by_phase": summary["by_phase"],
        "by_kind": summary["by_kind"],
        "by_phase_and_kind": summary["by_phase_and_kind"],
        "extra_observations": extra,
        "used_all_demo_channels": bool(used_all_demo_channels),
        "logical_slot_reads": {
            "demo_before_after": logical_build,
            "note": "in-memory equivalent() on already collected demo values; not real tool operations",
        },
        "events": summary["events"],
    }


def _result(name, public, hidden, meter, pairs, abstain, extra, plan, uses_demos,
            used_all_demo_channels=False, note=None, choice=None, before=None):
    scored, metrics = decide_rows(public, hidden, pairs, abstain, meter)
    record = _pairs_record(pairs, abstain, extra, plan, note=note)
    payload = {
        "name": name,
        **record,
        "metrics": metrics,
        "cost": cost_payload(meter, public, extra, used_all_demo_channels, uses_demos),
        "row_decisions": [
            {
                "input": row["input"],
                "version": row["version"],
                "truth": row["truth"],
                "decision": row["decisions"]["method"],
            }
            for row in scored
        ],
    }
    if choice is not None:
        payload["choice"] = choice
    if before is not None:
        payload["before_extra_observation"] = before
    return payload


def _initial_snapshot(public):
    pairs, structure = initial_H(public["demos"], public["slots"], public["requirement"])
    choice = choose_observation(pairs, public["demos"])
    rank = decision_rank(pairs)
    return {
        "pairs": [list(pair) for pair in pairs],
        "rank": rank,
        "rank_name": {
            RANK_RECEIVER_OPEN: "receiver_open",
            RANK_RELATION_OPEN: "relation_open",
            RANK_DETERMINED: "determined",
        }.get(rank, str(rank)),
        "receiver_unique_already": len(receivers_of(pairs)) == 1 if pairs else False,
        "relation_unique_already": len({relation for _, relation in pairs}) == 1 if pairs else False,
        "planned_action": choice["action"],
        "can_improve_by": [
            item["kind"] for item in choice["scores"] if item.get("can_improve_decision")
        ],
        "structure_compatible_slots": structure.get("compatible_slots"),
    }


def run_lookup(public, hidden):
    """Transferable action-type lookup + conventional fixed relation. No demos."""
    meter = ToolMeter()
    positions = transferable_lookup_positions(public["requirement"], public["slots"], public["action"])
    oracle = fixed_oracle(public["requirement"], public["action"])
    if len(positions) != 1 or oracle["relation"] is None:
        abstain = "lookup_or_oracle_not_unique" if len(positions) != 1 else oracle["abstain"]
        pairs = []
        extra = 0
        note = "transferable_lookup_no_demos"
    else:
        pairs = [(positions[0], oracle["relation"])]
        abstain = None
        extra = 0
        note = "transferable_lookup_no_demos"
    return _result(
        "lookup", public, hidden, meter, pairs, abstain, extra, [],
        uses_demos=False, note=note,
    )


def _metered_setup(public, hidden, budget, unlimited=False):
    meter = ToolMeter()
    world = MeteredWorld(hidden["world"], meter)
    demos = collect_demos(public, world, meter)
    observer = MeteredObserver(world, demos, meter, budget=budget, unlimited=unlimited)
    return meter, world, demos, observer


def run_joint(public, hidden, budget=EXTRA_BUDGET):
    cap = 0 if budget == 0 else budget
    meter, world, demos, observer = _metered_setup(public, hidden, cap, unlimited=False)
    before = _initial_snapshot(public)
    learned = learn_joint(
        public["demos"], public["slots"], public["requirement"], observer, budget=cap)
    # learn_joint reads public demos (same values as the re-collected ones).
    choice = learned.get("choice") or {}
    public_choice = {
        "action": choice.get("action"),
        "rank": choice.get("rank"),
        "chosen": choice.get("chosen"),
        "scores": choice.get("scores"),
    }
    determined_without_extra = before["rank"] in {RANK_DETERMINED, RANK_RELATION_OPEN}
    used_consumer_trace = learned["extra_observations"] > 0 and any(
        item.get("name") == "subsequent_reads" or item == "subsequent_reads"
        or (isinstance(item, dict) and item.get("name") in {"subsequent_reads", "contrast_canaries"})
        for item in (observer.log or [])
    )
    # Also treat canaries as a consumption-related intervention.
    used_consumption_evidence = learned["extra_observations"] > 0
    note = {
        "determined_before_extra_observation": determined_without_extra,
        "required_consumption_evidence_to_unique_pair": (
            not determined_without_extra and used_consumption_evidence
            and learned["abstain"] is None and len(learned["pairs"]) == 1
        ),
        "required_consumption_evidence_to_unique_receiver": (
            before["rank"] == RANK_RECEIVER_OPEN and used_consumption_evidence
            and learned["abstain"] is None and len(receivers_of(learned["pairs"])) == 1
        ),
        "used_consumption_evidence": used_consumption_evidence,
        "used_consumer_trace": used_consumer_trace,
        "only_decided_after_consumption_trace": (
            before["rank"] == RANK_RECEIVER_OPEN and used_consumption_evidence
        ),
    }
    return _result(
        "joint", public, hidden, meter, learned["pairs"], learned["abstain"],
        learned["extra_observations"], [choice.get("action")] if learned["extra_observations"] else [],
        uses_demos=True, note=note, choice=public_choice, before=before,
    )


def _execute_static_plan(public, hidden, plan, budget, unlimited=False):
    cap = max(len(plan), 1) if unlimited else (budget if budget > 0 or not plan else 0)
    if plan and cap < len(plan) and not unlimited:
        raise ValueError("plan exceeds budget")
    observer_budget = len(plan) if plan else 0
    if unlimited:
        observer_budget = max(len(plan), 1)
    meter, world, demos, observer = _metered_setup(
        public, hidden, budget=max(observer_budget, 1) if plan else 0,
        unlimited=unlimited or bool(plan),
    )
    # HealthyObserver raises if budget is 0 and a call is made. For an empty
    # plan we never call it. For a non-empty plan we set unlimited on the
    # inner observer only when executing a pre-fixed plan under a checked cap
    # that already equals len(plan); the cap is enforced here, not by skipping
    # consumption observations.
    if plan:
        observer = MeteredObserver(
            world, demos, meter, budget=len(plan), unlimited=False)
    pairs, _structure = initial_H(public["demos"], public["slots"], public["requirement"])
    notes = []
    extra = 0
    abstain = None
    for action in plan:
        if action == "reread_known_slot":
            slot = receivers_of(pairs)[0] if pairs else 0
            observer.reread_known_slot(public["demos"][0]["input"], slot)
            extra += 1
            notes.append("reread_known_slot")
            continue
        if action not in {"subsequent_reads", "contrast_canaries"}:
            raise ValueError(action)
        pairs, abstain, detail = apply_observation(pairs, action, observer, public["demos"])
        extra += 1
        notes.append(action)
        if detail:
            notes.append(detail)
        if abstain is not None:
            return meter, [], abstain, extra, list(plan), notes
    rank = decision_rank(pairs)
    if not pairs:
        abstain = "no_consistent_pair"
    elif rank in {RANK_RECEIVER_OPEN, -1}:
        abstain = "ambiguous_hypotheses"
    return meter, pairs, abstain, extra, list(plan), notes


def run_static_plan(public, hidden, plan, budget, name="static_plan", unlimited=False,
                    used_all_demo_channels=False, note=None):
    meter, pairs, abstain, extra, plan, notes = _execute_static_plan(
        public, hidden, plan, budget, unlimited=unlimited)
    return _result(
        name, public, hidden, meter, pairs, abstain, extra, plan,
        uses_demos=True, used_all_demo_channels=used_all_demo_channels,
        note=note or notes,
    )


def all_static_plans(budget):
    plans = [()]
    if budget <= 0:
        return plans
    for length in range(1, budget + 1):
        for combo in itertools.product(LEGAL_OBSERVATIONS, repeat=length):
            plans.append(combo)
    return plans



def _plan_preference(plan):
    return (len(plan),) + tuple(STATIC_TIEBREAK.get(action, 99) for action in plan)


def _plan_sort_key(result):
    metrics = result["metrics"]
    cost = result["cost"]["real_tool_operations_total"]
    extra = result["extra_observations"]
    return _quality_tuple(metrics) + (cost, extra) + _plan_preference(result["plan"])


def run_optimal_static(public, hidden, budget):
    evaluated = []
    for plan in all_static_plans(budget):
        result = run_static_plan(
            public, hidden, plan, budget=budget, name="optimal_static_candidate")
        evaluated.append({
            "plan": list(plan),
            "metrics": result["metrics"],
            "real_tool_operations_total": result["cost"]["real_tool_operations_total"],
            "by_phase": result["cost"]["by_phase"],
            "extra_observations": result["extra_observations"],
            "abstain": result["abstain"],
            "positions": result["positions"],
            "relations": result["relations"],
        })
    # Re-run the winner so the returned result carries a fresh meter and name.
    ranked = sorted(evaluated, key=lambda item: (
        _quality_tuple(item["metrics"]),
        item["real_tool_operations_total"],
        item["extra_observations"],
        _plan_preference(item["plan"]),
    ))
    winner = ranked[0]["plan"]
    result = run_static_plan(
        public, hidden, tuple(winner), budget=budget, name="optimal_static",
        note=["oracle_selected_upper_bound", list(winner)],
    )
    result["search"] = {
        "n_plans_evaluated": len(evaluated),
        "plans": evaluated,
        "selected_plan": list(winner),
        "selection": (
            "Hidden labels are used only to pick the best completed plan after "
            "all plans have been scored. The executor of each plan does not see "
            "the truth receiver or relation. This is an upper bound on static methods."
        ),
    }
    result["before_extra_observation"] = _initial_snapshot(public)
    return result


def run_full_trace(public, hidden, budget, unlimited=False):
    if unlimited:
        plan = list(FULL_TRACE_ORDER)
        name = "full_trace_unlimited"
        used_all = True
        note = ["exhaustive_subsequent_reads_then_canaries", "all_demo_channels_inspected"]
    else:
        plan = list(FULL_TRACE_ORDER[: max(budget, 0)])
        name = "full_trace_same_budget"
        used_all = True  # it may inspect demo channels already collected
        note = ["exhaustive_prefix_under_budget", list(plan)]
    result = run_static_plan(
        public, hidden, tuple(plan), budget=len(plan) if plan else 0,
        name=name, unlimited=unlimited, used_all_demo_channels=used_all, note=note,
    )
    result["before_extra_observation"] = _initial_snapshot(public)
    return result


def run_case_curve(public, hidden):
    before = _initial_snapshot(public)
    lookup = run_lookup(public, hidden)
    joint_points = []
    static_points = []
    full_budgeted = []
    for budget in BUDGETS:
        joint_points.append({"budget": budget, **_public_point(run_joint(public, hidden, budget=budget))})
        static_points.append({"budget": budget, **_public_point(run_optimal_static(public, hidden, budget=budget))})
        full_budgeted.append({"budget": budget, **_public_point(run_full_trace(public, hidden, budget=budget, unlimited=False))})
    unlimited = _public_point(run_full_trace(public, hidden, budget=None, unlimited=True))
    unlimited["budget"] = "unlimited"
    lookup_point = _public_point(lookup)
    return {
        "before_extra_observation": before,
        "lookup": lookup_point,
        "joint": joint_points,
        "optimal_static": static_points,
        "full_trace_same_budget": full_budgeted,
        "full_trace_unlimited": unlimited,
    }


def _public_point(result):
    cost = result["cost"]
    point = {
        "abstain": result["abstain"],
        "positions": result["positions"],
        "relations": result["relations"],
        "pairs": result["pairs"],
        "plan": result["plan"],
        "extra_observations": result["extra_observations"],
        "unique_receiver": result["unique_receiver"],
        "unique_relation": result["unique_relation"],
        "metrics": result["metrics"],
        "cost": {
            "model_calls": cost["model_calls"],
            "real_tool_operations_total": cost["real_tool_operations_total"],
            "by_phase": cost["by_phase"],
            "by_kind": cost["by_kind"],
            "by_phase_and_kind": cost["by_phase_and_kind"],
            "extra_observations": cost["extra_observations"],
            "used_all_demo_channels": cost["used_all_demo_channels"],
            "logical_slot_reads": cost["logical_slot_reads"],
            "events": cost["events"],
        },
        "row_decisions": result["row_decisions"],
        "note": result.get("note"),
    }
    if "choice" in result:
        point["choice"] = result["choice"]
    if "before_extra_observation" in result:
        point["before_extra_observation"] = result["before_extra_observation"]
    if "search" in result:
        # Keep the plan search, but drop nothing essential.
        point["search"] = result["search"]
    return point


def best_shared_static_plan(case_curves):
    """Best single plan of length <= 1 and <= 2 used on all three cases."""
    out = {}
    for budget in BUDGETS:
        plans = all_static_plans(budget)
        scored = []
        for plan in plans:
            per_case = {}
            totals = {key: 0 for key in QUALITY_KEYS}
            total_ops = 0
            for case_id, curve in case_curves.items():
                # Re-scoring happens in compare(); here we only aggregate already-run
                # per-case searches when budget matches.
                match = None
                for item in curve["optimal_static"]:
                    if item["budget"] != budget:
                        continue
                    for candidate in item["search"]["plans"]:
                        if candidate["plan"] == list(plan):
                            match = candidate
                            break
                if match is None:
                    raise RuntimeError(f"missing plan {plan} for {case_id} budget={budget}")
                per_case[case_id] = match
                for key in QUALITY_KEYS:
                    totals[key] += match["metrics"][key]
                total_ops += match["real_tool_operations_total"]
            scored.append({
                "plan": list(plan),
                "metrics_sum_over_cases": totals,
                "real_tool_operations_total_sum": total_ops,
                "per_case": {
                    case_id: {
                        "metrics": item["metrics"],
                        "real_tool_operations_total": item["real_tool_operations_total"],
                        "extra_observations": item["extra_observations"],
                        "abstain": item["abstain"],
                    }
                    for case_id, item in per_case.items()
                },
            })
        ranked = sorted(scored, key=lambda item: (
            _quality_tuple(item["metrics_sum_over_cases"]),
            item["real_tool_operations_total_sum"],
            _plan_preference(item["plan"]),
        ))
        out[str(budget)] = {
            "selected_plan": ranked[0]["plan"],
            "metrics_sum_over_cases": ranked[0]["metrics_sum_over_cases"],
            "real_tool_operations_total_sum": ranked[0]["real_tool_operations_total_sum"],
            "per_case": ranked[0]["per_case"],
            "n_plans_evaluated": len(ranked),
        }
    return out


def _point_at(points, budget):
    for item in points:
        if item["budget"] == budget:
            return item
    raise KeyError(budget)


def compare_curves(case_curves, shared_static):
    per_case = {}
    any_joint_better_static = False
    any_static_better_joint = False
    all_tie_quality_at_default = True
    consumer_trace_notes = {}
    for case_id, curve in case_curves.items():
        rows = []
        for budget in BUDGETS:
            joint = _point_at(curve["joint"], budget)
            static = _point_at(curve["optimal_static"], budget)
            full_b = _point_at(curve["full_trace_same_budget"], budget)
            lookup = curve["lookup"]
            joint_better = quality_strictly_better(joint["metrics"], static["metrics"])
            static_better = quality_strictly_better(static["metrics"], joint["metrics"])
            tie = quality_equal(joint["metrics"], static["metrics"])
            if joint_better:
                any_joint_better_static = True
            if static_better:
                any_static_better_joint = True
            if budget == EXTRA_BUDGET and not tie:
                all_tie_quality_at_default = False
            rows.append({
                "budget": budget,
                "joint_metrics": joint["metrics"],
                "optimal_static_metrics": static["metrics"],
                "full_trace_same_budget_metrics": full_b["metrics"],
                "lookup_metrics": lookup["metrics"],
                "joint_real_tool_operations": joint["cost"]["real_tool_operations_total"],
                "optimal_static_real_tool_operations": static["cost"]["real_tool_operations_total"],
                "full_trace_same_budget_real_tool_operations": full_b["cost"]["real_tool_operations_total"],
                "lookup_real_tool_operations": lookup["cost"]["real_tool_operations_total"],
                "joint_extra_observations": joint["extra_observations"],
                "optimal_static_plan": static["plan"],
                "full_trace_same_budget_plan": full_b["plan"],
                "joint_strictly_better_quality_than_optimal_static": joint_better,
                "quality_tie_with_optimal_static": tie,
                "quality_tie_with_full_trace_same_budget": quality_equal(joint["metrics"], full_b["metrics"]),
                "quality_tie_with_full_trace_unlimited": quality_equal(
                    joint["metrics"], curve["full_trace_unlimited"]["metrics"]),
            })
        joint_default = _point_at(curve["joint"], EXTRA_BUDGET)
        note = joint_default.get("note") or {}
        consumer_trace_notes[case_id] = {
            "before": curve["before_extra_observation"],
            "determined_before_extra_observation": note.get("determined_before_extra_observation"),
            "only_decided_after_consumption_trace": note.get("only_decided_after_consumption_trace"),
            "required_consumption_evidence_to_unique_pair": note.get("required_consumption_evidence_to_unique_pair"),
            "required_consumption_evidence_to_unique_receiver": note.get("required_consumption_evidence_to_unique_receiver"),
            "used_consumption_evidence": note.get("used_consumption_evidence"),
            "joint_plan_at_default_budget": joint_default["plan"],
            "joint_extra_observations_at_default_budget": joint_default["extra_observations"],
        }
        per_case[case_id] = {
            "by_budget": rows,
            "unlimited_full_trace": {
                "metrics": curve["full_trace_unlimited"]["metrics"],
                "real_tool_operations_total": curve["full_trace_unlimited"]["cost"]["real_tool_operations_total"],
                "by_phase": curve["full_trace_unlimited"]["cost"]["by_phase"],
                "plan": curve["full_trace_unlimited"]["plan"],
                "extra_observations": curve["full_trace_unlimited"]["extra_observations"],
            },
            "joint_at_default_budget_matches_unlimited_quality": quality_equal(
                joint_default["metrics"], curve["full_trace_unlimited"]["metrics"]),
            "joint_default_ops": joint_default["cost"]["real_tool_operations_total"],
            "unlimited_ops": curve["full_trace_unlimited"]["cost"]["real_tool_operations_total"],
        }
    # The hypothesis "joint beats optimal static at the same budget" needs a
    # strict quality win at the original budget of 1, or at any budget. A
    # quality tie is 追平, even if tool-operation counts later differ.
    hypothesis_beaten_by_static = (not any_joint_better_static) and all_tie_quality_at_default
    only_after = {
        case_id: item["only_decided_after_consumption_trace"]
        for case_id, item in consumer_trace_notes.items()
    }
    return {
        "default_budget": EXTRA_BUDGET,
        "per_case": per_case,
        "joint_strictly_better_than_optimal_static_any_budget": any_joint_better_static,
        "optimal_static_strictly_better_than_joint_any_budget": any_static_better_joint,
        "quality_tied_with_optimal_static_at_default_budget_all_cases": all_tie_quality_at_default,
        "same_budget_joint_outperforms_optimal_static": any_joint_better_static and all_tie_quality_at_default is False,
        "active_selection_value_not_shown": not any_joint_better_static,
        "only_decided_after_consumption_trace_by_case": only_after,
        "shared_static_plan": shared_static,
        "accept_negative_result": hypothesis_beaten_by_static,
        "stop_adding_complexity": hypothesis_beaten_by_static,
        "synthetic_only": True,
        "does_not_establish_real_task_generalization": True,
        "does_not_establish_eswa_core_contribution": True,
        "hidden_pagination_not_treated_as_proof": True,
        "interpretation": {
            "same_budget_vs_optimal_static": (
                "联合学习在同等预算下相对逐案最优静态观察"
                + ("有严格质量优势。" if any_joint_better_static else "没有严格质量优势，属于追平或未超过。")
            ),
            "consumption_trace": (
                "若某案例在未做消费向观察前接收端仍不唯一，并且联合学习在做了 subsequent_reads"
                "或 canaries 之后才得到可发布判定，则该案例属于“得到完整消费轨迹之后才选对”。"
            ),
        },
        "consumer_trace_notes": consumer_trace_notes,
    }


def strip_events_for_compact(curve):
    """Keep event lists in the receipt; nothing to drop at this layer."""
    return curve
