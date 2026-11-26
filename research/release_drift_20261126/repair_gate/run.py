"""Public column-case repair ablation. Takes no sealed input or labels."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from itertools import product
import json
from pathlib import Path
import sys
from time import perf_counter_ns
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import openpyxl
import xlsxwriter


SHEET = "xl/worksheets/sheet1.xml"
SOURCE = "3c646407:research/release_drift_20261126/dev_parallel/protocol.md"
TERMS = ("A列必须可见", "A1文字必须等于最后写入的文本，未写入时为空")
ARMS = ("static", "A", "B", "C_gate")


def make_book(actions):
    out = BytesIO()
    with xlsxwriter.Workbook(out, {"in_memory": True}) as wb:
        sheet = wb.add_worksheet()
        for action in actions:
            if action == "width":
                sheet.set_column(0, 0, 2)
            elif action == "text":
                sheet.write_string(0, 0, "hello world")
            else:
                assert action == "fit"
                sheet.autofit()
    return out.getvalue()


def read_artifact(data):
    with ZipFile(BytesIO(data)) as z:
        root = ET.fromstring(z.read(SHEET))
        col = root.find(".//{*}col")
        cell = root.find(".//{*}c[@r='A1']")
        text = ""
        if cell is not None:
            idx = int(cell.find("{*}v").text)
            items = ET.fromstring(z.read("xl/sharedStrings.xml")).findall("{*}si")
            text = "".join(n.text or "" for n in items[idx].iterfind(".//{*}t"))
        return {"visible": col is None or col.get("hidden", "0") not in {"1", "true"}, "cell_text": text}


def independent(data, actions):
    wb = openpyxl.load_workbook(BytesIO(data))
    sheet = wb.active
    col = sheet.column_dimensions.get("A")
    text_ok = sheet["A1"].value == ("hello world" if "text" in actions else None)
    ok = (col is None or not col.hidden) and text_ok
    positive_width = col is None or col.width > 0
    wb.close()
    return ok, positive_width


def repair(data):
    out = BytesIO()
    with ZipFile(BytesIO(data)) as src, ZipFile(out, "w") as dst:
        original = src.read(SHEET)
        root = ET.fromstring(original)
        cols = root.findall(".//{*}col[@min='1'][@max='1']")
        if len(cols) != 1 or cols[0].get("hidden") not in ("1", "true"):
            return None
        original_hidden = cols[0].attrib.pop("hidden")
        updated = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        for info in src.infolist():
            dst.writestr(info, updated if info.filename == SHEET else src.read(info.filename))
    fixed = out.getvalue()
    with ZipFile(BytesIO(data)) as src, ZipFile(BytesIO(fixed)) as dst:
        assert src.namelist() == dst.namelist()
        assert all(src.read(n) == dst.read(n) for n in src.namelist() if n != SHEET)
        after = ET.fromstring(dst.read(SHEET))
        after.find(".//{*}col[@min='1'][@max='1']").set("hidden", original_hidden)
        # Canonicalization ignores XML attribute order and serialization prefixes.
        assert ET.canonicalize(ET.tostring(after), rewrite_prefixes=True) == ET.canonicalize(original, rewrite_prefixes=True)
    return fixed


@dataclass(frozen=True)
class Clause:
    source: str
    field: str
    expression: str


def compile_contract(terms):
    vocabulary = {TERMS[0]: ("visible", "true"), TERMS[1]: ("cell_text", "last_write")}
    if any(t not in vocabulary for t in terms):
        raise ValueError("clause outside registered grammar")
    return [Clause(SOURCE, *vocabulary[t]) for t in terms]


def verdict(arm, obs, actions, clauses):
    text = "hello world" if "text" in actions else ""
    if arm == "static":
        return ("satisfied" if obs == {"visible": True, "cell_text": text} else "violated"), None
    conditions = [None if c.field not in obs else obs[c.field] == (True if c.expression == "true" else text)
                  for c in clauses]
    if arm == "A":
        return ("violated" if False in conditions else "unknown" if None in conditions else "satisfied"), None
    possible = [row for row in product((False, True), repeat=len(conditions))
                if all(value is None or value == bit for value, bit in zip(conditions, row))]
    judgments = {all(row) for row in possible}
    return ("unknown" if len(judgments) > 1 else "satisfied" if True in judgments else "violated"), len(possible)


def main():
    archive = json.loads(Path("research/release_drift_20261126/dev_parallel/results/column.json").read_text())
    version = xlsxwriter.__version__
    old_rows = archive["results"][version]["static_task"]["rows"]
    clauses = compile_contract(TERMS)
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for old in old_rows:
            actions = old["value"]
            start = perf_counter_ns()
            data = make_book(actions)
            write_ns = perf_counter_ns() - start
            obs = read_artifact(data)
            assert obs == old["initial"]
            initial_ok, positive_width = independent(data, actions)
            assert initial_ok == (not old["initial_wrong"])
            def evaluate(arm):
                start = perf_counter_ns()
                v, survivors = verdict(arm, obs, actions, clauses)
                return arm, {"verdict": v, "surviving_explanations": survivors,
                             "judgment_ns": perf_counter_ns() - start, "probe_calls": 0,
                             "branch_eligible": arm == "C_gate" and v == "unknown"}
            methods = dict(pool.map(evaluate, ARMS))
            fixed = None
            repair_ns = None
            if any(m["verdict"] == "violated" for m in methods.values()):
                start = perf_counter_ns()
                fixed = repair(data)
                if fixed is not None:
                    fixed_obs = read_artifact(fixed)
                    if verdict("static", fixed_obs, actions, clauses)[0] != "satisfied":
                        fixed = None
                repair_ns = perf_counter_ns() - start
            for m in methods.values():
                for available in (False, True):
                    action = "deliver_current"
                    delivered = data
                    if m["verdict"] == "violated":
                        delivered = fixed if available else None
                        action = "deliver_repaired" if delivered is not None else "defer"
                    outcome, width = "deferred", None
                    if delivered is not None:
                        correct, width = independent(delivered, actions)
                        outcome = "correct" if correct else "wrong"
                    m["repair_on" if available else "repair_off"] = {
                        "action": action, "outcome": outcome, "positive_width": width}
            rows.append({"actions": actions, "initial": obs, "initial_ok": initial_ok,
                         "positive_width": positive_width, "initial_ns": write_ns, "repair_verify_ns": repair_ns,
                         "initial_digest": sha256(data).hexdigest(),
                         "repaired_digest": sha256(fixed).hexdigest() if fixed else None, "methods": methods})
            if fixed is not None:
                for suffix, content in (("original", data), ("repaired", fixed)):
                    Path(f"{version}-{len(rows):02d}-{suffix}.xlsx").write_bytes(content)
    assert len(rows) == 40
    Path(f"{version}.json").write_text(json.dumps({"version": version, "reader": openpyxl.__version__,
        "contract": [c.__dict__ for c in clauses], "rows": rows}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
