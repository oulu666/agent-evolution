"""Build and seal the three offline forms; verify and score returned forms."""
from pathlib import Path
import csv
import hashlib
import json
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parent
STUDY = "ISSRE-review-v1"
PACKETS = ("R01", "R02", "R03")
OPTIONS = {
    "keep": "保留当前通过结论",
    "extract": "修复从契约生成断言的环节",
    "input": "更改输入以触发目标条件",
    "observe": "增加能区分两种行为的观察点",
    "path": "复核具体推导所依赖的路径条件",
    "product": "记录旧构建的产品违约并保留回归检查",
    "unknown": "现有证据不足以选择处置",
}


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8-sig"))


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def design():
    cases = read("cases.json")
    # Two instances per arm within person; each case takes each arm across people.
    rng = random.Random(20261124)
    base = list("ABCABC")
    rng.shuffle(base)
    result = {}
    for slot, packet in enumerate(PACKETS):
        entries = [(case, "ABC"[("ABC".index(arm) + slot) % 3]) for case, arm in zip(cases, base)]
        rng.shuffle(entries)
        result[packet] = entries
    return result


def check_reference():
    ref = read("reference.json")
    cache = ref["cachetools 5.5.2"]["observations"]
    assert cache["ordinary"]["events"] == ["start x", "end x"]
    assert cache["below"]["events"] == ["start x", "end x", "start y", "end y"]
    assert cache["below"]["keys"] == ["x", "y"] and cache["third"]["keys"] == ["y", "z"]
    assert "evict x" in cache["third"]["events"]
    assert cache["registry"] == {"executed": {"membership": True}, "size": 1, "output": 1, "manual_check": True}
    assert cache["reuse"]["output"] == cache["no_reuse_control"]["output"] == [5, 5]
    assert [len(cache[k]["entries"]) for k in ("reuse", "no_reuse_control")] == [1, 2]
    for version, width in (("0.2.9", 1), ("0.2.10", 2)):
        assert ref["wcwidth " + version]["observations"] == {"AB": 2, "\u2640\ufe0f": width}


def freeze():
    check_reference()
    if (ROOT / "lock.json").exists():
        verify()
        return
    template = (ROOT / "form.html.in").read_text(encoding="utf-8")
    files = ["protocol.md", "capture.py", "reference.json", "cases.json", "study.py", "form.html.in"]
    (ROOT / "participants").mkdir(exist_ok=True)
    for packet, entries in design().items():
        items = [{"case": c["case"], "task": c["task"],
                  "evidence": [c[a] for a in "ABC"[:"ABC".index(arm) + 1]]} for c, arm in entries]
        payload = dict(study=STUDY, packet=packet, options=OPTIONS, items=items)
        target = "participants/" + packet + ".html"
        (ROOT / target).write_text(template.replace("__DATA__", json.dumps(payload, ensure_ascii=False)), encoding="utf-8")
        files.append(target)
    locked = {f: fingerprint(ROOT / f) for f in files}
    (ROOT / "lock.json").write_text(json.dumps(locked, indent=2), encoding="utf-8")
    verify()


def verify():
    for f, digest in read("lock.json").items():
        if digest != fingerprint(ROOT / f):
            raise ValueError("Frozen file differs: " + f)


def score(paths):
    verify()
    assignment = design()
    seen = set()
    rows = []
    for path in paths:
        response = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        packet = response["packet"]
        if packet not in assignment or packet in seen or response["study"] != STUDY or response["eligible"] is not True:
            raise ValueError("Unmatched, duplicate, or ineligible form")
        seen.add(packet)
        answers = response["responses"]
        if len(answers) != len(assignment[packet]):
            raise ValueError("Incomplete response")
        for ans, (case, arm) in zip(answers, assignment[packet]):
            ms = ans["active_ms"]
            if (ans["case"] != case["case"] or ans["action"] not in OPTIONS or not ans["reason"].strip()
                    or type(ms) is not int or ms < 0):
                raise ValueError("Invalid response row")
            rows.append(dict(packet=packet, case=case["case"], arm=arm, action=ans["action"],
                             correct=int(ans["action"] == case["key"]), unknown=int(ans["action"] == "unknown"),
                             seconds=ms/1000, reason=ans["reason"]))
    if not rows:
        print("No responses supplied. No human outcomes are estimable.")
        return
    writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    for arm in "ABC":
        group = [r for r in rows if r["arm"] == arm]
        print(arm, "n", len(group), "correct", sum(r["correct"] for r in group),
              "uncertain", sum(r["unknown"] for r in group),
              "median seconds", statistics.median(r["seconds"] for r in group), file=sys.stderr)
    for baseline in "AB":
        wins = losses = ties = 0
        for c in read("cases.json"):
            paired = {r["arm"]: r for r in rows if r["case"] == c["case"]}
            if baseline not in paired or "C" not in paired:
                continue
            diff = paired["C"]["correct"] - paired[baseline]["correct"]
            wins += diff > 0
            losses += diff < 0
            ties += diff == 0
        print("C vs", baseline, "matched-case wins/losses/ties:", wins, losses, ties, file=sys.stderr)


if __name__ == "__main__":
    if sys.argv[1:2] == ["freeze"]:
        freeze()
    else:
        score(sys.argv[1:])

