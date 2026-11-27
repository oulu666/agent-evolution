"""Synthetic worlds used only for mechanism development.

These cases are not independent evidence of a real defect. The consumer path
is a property of the simulated environment and is never passed to learners.
Cases preview/cache/download and two-file keep the previous frozen口径.
The joint (r, o) case is new and marked as a mechanism-development scenario.
"""
import json

SENTINEL = "pending delivery"
TITLE = "Config exporter"
EXTRA_BUDGET = 1
ACTION = "generate-config-export"

# Held-out test inputs are disjoint from the two healthy demonstrations.
TEXT_DEMO_INPUTS = (
    ("demo-a", "port: 41"),
    ("demo-b", "port: 73"),
)
TEXT_TEST_INPUTS = (
    ("single-a", "host: test"),
    ("single-b", "region: east"),
    ("trigger-a", "port: 99\nhost: example"),
    ("trigger-b", "port: 100\nhost: other"),
)

JSON_DEMO_OBJECTS = (
    ("demo-a", {"port": 41}),
    ("demo-b", {"port": 73}),
)
JSON_TEST_OBJECTS = (
    ("single-a", {"host": "test"}),
    ("single-b", {"region": "east"}),
    ("trigger-a", {"port": 99, "host": "example"}),
    ("trigger-b", {"port": 100, "host": "other"}),
)

VERSIONS = ("v1", "v2")

REQUIREMENT_TYPED = (
    "生成配置文件，供另一个程序使用。"
    "将配置导出为下载文件，由另一个程序读取该下载文件后使用。"
    "内容保真，按文本比较。"
)
REQUIREMENT_AMBIGUOUS_FILES = (
    "生成配置文件，供另一个程序使用。"
    "将产物导出为文件，由另一个程序读取导出文件后使用。"
    "内容保真，按文本比较。"
)
# Underspecified relation on purpose: only generic fidelity, no phrase-table hit.
# The values happen to be JSON; the requirement does not name parsed_value.
REQUIREMENT_JOINT = (
    "生成配置文件，供另一个程序使用。"
    "将产物导出为文件，由另一个程序读取导出文件后使用。"
    "内容保真。"
)

CASES = (
    {
        "id": "synthetic_preview_cache_download",
        "kind": "text_export",
        "synthetic": True,
        "mechanism_development_only": True,
        "requirement": REQUIREMENT_TYPED,
        "slots": (
            {"name": "page_title", "type": "ui_title"},
            {"name": "page_preview", "type": "ui_preview"},
            {"name": "internal_cache", "type": "internal_cache"},
            {"name": "download_file", "type": "downloaded_file"},
        ),
        "truth_receiver": 3,
        "truth_relation": "full_string",
    },
    {
        "id": "synthetic_two_download_files",
        "kind": "text_export",
        "synthetic": True,
        "mechanism_development_only": True,
        "requirement": REQUIREMENT_AMBIGUOUS_FILES,
        "slots": (
            {"name": "page_title", "type": "ui_title"},
            {"name": "page_preview", "type": "ui_preview"},
            {"name": "internal_cache", "type": "internal_cache"},
            {"name": "export_file_a", "type": "downloaded_file"},
            {"name": "export_file_b", "type": "downloaded_file"},
        ),
        "truth_receiver": 4,
        "truth_relation": "full_string",
    },
    {
        "id": "synthetic_joint_receiver_oracle",
        "kind": "json_export",
        "synthetic": True,
        "mechanism_development_only": True,
        "requirement": REQUIREMENT_JOINT,
        "slots": (
            {"name": "page_title", "type": "ui_title"},
            {"name": "page_preview", "type": "ui_preview"},
            {"name": "internal_cache", "type": "internal_cache"},
            {"name": "export_file_a", "type": "downloaded_file"},
            {"name": "export_file_b", "type": "downloaded_file"},
        ),
        "truth_receiver": 4,
        "truth_relation": "parsed_value",
    },
)


def compact_json(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def pretty_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)


def is_trigger_text(text):
    return "\n" in text


def is_trigger_obj(obj):
    return len(obj) > 1


def tamper_text(text):
    return text + "\n# truncated-export"


def tamper_obj(obj):
    out = dict(obj)
    out["_truncated"] = True
    return out


def _file_path(slot):
    return slot["name"] + ".cfg"


class ExportWorld:
    """Deterministic generator. Algorithms must not be given truth_receiver."""

    def __init__(self, case):
        self.case_id = case["id"]
        self.kind = case["kind"]
        self.slots = list(case["slots"])
        self._truth = case["truth_receiver"]

    def _write_text(self, version, text, index):
        if self.slots[index]["type"] != "downloaded_file":
            return text
        if index == self._truth and version == "v1" and is_trigger_text(text):
            return tamper_text(text)
        return text

    def _slot_json(self, version, obj, index):
        slot_type = self.slots[index]["type"]
        if slot_type == "ui_title":
            return TITLE
        if slot_type == "ui_preview":
            return pretty_json(obj)
        if slot_type == "internal_cache":
            return compact_json(obj) + "\n"
        if slot_type != "downloaded_file":
            raise ValueError(self.slots[index])
        # Staging file A keeps compact source text. The consumed file is pretty
        # printed, so only parsed_value holds there on healthy runs.
        if index == self._truth:
            payload = tamper_obj(obj) if version == "v1" and is_trigger_obj(obj) else obj
            return pretty_json(payload)
        return compact_json(obj)

    def generate(self, version, input_name, payload):
        if self.kind == "text_export":
            text = payload
            expected = text
            before = [SENTINEL] * len(self.slots)
            after = list(before)
            events = []
            for index, slot in enumerate(self.slots):
                if slot["type"] == "ui_title":
                    after[index] = TITLE
                    events.append({"op": "set_title", "slot": index, "type": slot["type"],
                                   "value": TITLE})
                elif slot["type"] == "ui_preview":
                    after[index] = text
                    events.append({"op": "render_preview", "slot": index, "type": slot["type"],
                                   "value": text})
                elif slot["type"] == "internal_cache":
                    after[index] = text
                    events.append({"op": "write_cache", "slot": index, "type": slot["type"],
                                   "value": text})
                elif slot["type"] == "downloaded_file":
                    written = self._write_text(version, text, index)
                    after[index] = written
                    events.append({"op": "write_file", "slot": index, "type": slot["type"],
                                   "path": _file_path(slot), "value": written})
                else:
                    raise ValueError(slot)
        elif self.kind == "json_export":
            obj = payload
            expected = compact_json(obj)
            before = [SENTINEL] * len(self.slots)
            after = list(before)
            events = []
            for index, slot in enumerate(self.slots):
                written = self._slot_json(version, obj, index)
                after[index] = written
                if slot["type"] == "ui_title":
                    events.append({"op": "set_title", "slot": index, "type": slot["type"],
                                   "value": written})
                elif slot["type"] == "ui_preview":
                    events.append({"op": "render_preview", "slot": index, "type": slot["type"],
                                   "value": written})
                elif slot["type"] == "internal_cache":
                    events.append({"op": "write_cache", "slot": index, "type": slot["type"],
                                   "value": written})
                elif slot["type"] == "downloaded_file":
                    events.append({"op": "write_file", "slot": index, "type": slot["type"],
                                   "path": _file_path(slot), "value": written})
                else:
                    raise ValueError(slot)
        else:
            raise ValueError(self.kind)
        return {
            "input": input_name,
            "expected": expected,
            "before": before,
            "after": after,
            "events": events,
            "seconds": 0.0,
            "version": version,
        }

    def consume(self, after):
        index = self._truth
        value = after[index]
        event = {
            "op": "consumer_read",
            "slot": index,
            "type": self.slots[index]["type"],
            "path": _file_path(self.slots[index]) if self.slots[index]["type"] == "downloaded_file" else None,
            "value": value,
        }
        return value, event


class HealthyObserver:
    """Observation API used during learning. Only demo inputs, healthy writes.

    Test rows, version labels, and the scoring receiver are not exposed.
    Joint and auto-localization share the same extra-observation budget.
    The stronger control may call subsequent_reads and inspect all demo
    channels; it still cannot read the truth index or the scorer's (r, o).
    """

    def __init__(self, world, demos, budget=EXTRA_BUDGET, unlimited=False):
        self._world = world
        self._allowed = {demo["input"]: demo for demo in demos}
        self.budget = budget
        self.unlimited = unlimited
        self.calls = 0
        self.log = []

    def _use(self, name, input_name):
        if input_name not in self._allowed:
            raise ValueError("only demonstration inputs may be re-observed")
        if not self.unlimited and self.calls >= self.budget:
            raise RuntimeError("extra observation budget exhausted")
        self.calls += 1
        self.log.append(name)

    def contrast_canaries(self, input_name, overlays):
        self._use("contrast_canaries", input_name)
        demo = self._allowed[input_name]
        run = self._world.generate("v2", input_name, _demo_payload(self._world, demo))
        after = list(run["after"])
        events = list(run["events"])
        for index, value in overlays.items():
            after[index] = value
            events.append({"op": "overlay", "slot": index, "value": value})
        consumer, read = self._world.consume(after)
        events.append(read)
        self.log[-1] = {
            "name": "contrast_canaries",
            "overlays": sorted(overlays),
        }
        return consumer

    def subsequent_reads(self, input_name):
        self._use("subsequent_reads", input_name)
        demo = self._allowed[input_name]
        # Re-run the healthy generator on a demonstration input.
        run = self._world.generate("v2", input_name, _demo_payload(self._world, demo))
        _, read = self._world.consume(run["after"])
        self.log[-1] = {"name": "subsequent_reads"}
        return list(run["events"]) + [read]


def _demo_payload(world, demo):
    if world.kind == "text_export":
        return demo["expected"]
    return json.loads(demo["expected"])


def collect_case(case):
    world = ExportWorld(case)
    if case["kind"] == "text_export":
        demos = [world.generate("v1", name, text) for name, text in TEXT_DEMO_INPUTS]
        tests = TEXT_TEST_INPUTS
        is_trig = lambda payload: is_trigger_text(payload)
    else:
        demos = [world.generate("v1", name, obj) for name, obj in JSON_DEMO_OBJECTS]
        tests = JSON_TEST_OBJECTS
        is_trig = lambda payload: is_trigger_obj(payload)
    rows = []
    for version in VERSIONS:
        for name, payload in tests:
            rows.append(world.generate(version, name, payload))
    public = {
        "id": case["id"],
        "kind": case["kind"],
        "synthetic": True,
        "mechanism_development_only": True,
        "requirement": case["requirement"],
        "action": ACTION,
        "slots": list(case["slots"]),
        "demos": demos,
        "rows": rows,
    }
    hidden = {
        "truth_receiver": case["truth_receiver"],
        "truth_relation": case["truth_relation"],
        "world": world,
        "is_trigger": is_trig,
        "test_payloads": tests,
    }
    return public, hidden
