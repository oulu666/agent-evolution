import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.request import urlopen
from time import perf_counter

from oracle import STUDY_REQUIREMENTS
from score import score_study

VERSIONS = {"1.6": "jq-linux64", "1.7.1": "jq-linux-amd64"}
SENTINEL = "pending delivery"
CORPUS = Path("downstream-corpus")
MODES = ("stdout", "file")


def run(binary, root, mode, name, value):
    source = root / "input.json"
    dest = root / "received.json"
    source.write_text(value)
    dest.write_text(SENTINEL)
    before = ["", source.read_text(), dest.read_text(), ""]
    args = [binary, ".", source]
    start = perf_counter()
    if mode == "file":
        with dest.open("w") as stream:
            process = subprocess.run(args, stdout=stream, stderr=subprocess.PIPE, text=True, check=True)
    else:
        process = subprocess.run(args, capture_output=True, text=True, check=True)
    after = [process.stderr, source.read_text(), dest.read_text(), process.stdout or ""]
    return {"input": name, "expected": value, "before": before, "after": after,
            "seconds": perf_counter()-start}


def main():
    names = sorted(CORPUS.glob("test_parsing/y_number_*.json")) + sorted(CORPUS.glob("test_transform/number_*.json"))
    assert len(names) == 24
    receipts = {"slots": ["stderr", "input", "destination", "stdout"], "versions": {}, "modes": {}}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        binaries = {}
        for version, asset in VERSIONS.items():
            binary = root / ("jq-" + version)
            data = urlopen(f"https://github.com/jqlang/jq/releases/download/jq-{version}/{asset}", timeout=45).read()
            binary.write_bytes(data)
            os.chmod(binary, 0o700)
            reported = subprocess.check_output([binary, "--version"], text=True).strip()
            assert reported == "jq-" + version
            receipts["versions"][version] = hashlib.sha256(data).hexdigest()
            binaries[version] = binary
        for mode in MODES:
            demos = [run(binaries["1.6"], root, mode, f"demo-{i}", f"[{i}]") for i in (41, 73)]
            rows = []
            for version, binary in binaries.items():
                for p in names:
                    row = run(binary, root, mode, p.relative_to(CORPUS).as_posix(), p.read_text())
                    row["version"] = version
                    rows.append(row)
            action = "jq-stdout" if mode == "stdout" else "jq-file-redirect"
            receipts["modes"][mode] = score_study(
                demos, rows, STUDY_REQUIREMENTS["jq"], 3 if mode == "stdout" else 2, action)
    Path("jq-receipt.json").write_text(json.dumps(receipts, indent=1)+"\n")


if __name__ == "__main__":
    main()
