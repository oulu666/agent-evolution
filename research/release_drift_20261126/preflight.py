"""Run public, ordinary-input checks in isolated CPython 3.11 release environments."""

import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import venv


def pillow_checks():
    from PIL import Image, ImageDraw

    sample = Image.new("L", (3, 3), 19)
    assert list(sample.resize((2, 2)).getdata()) == [19] * 4
    assert sample.convert("RGB").getpixel((1, 1)) == (19, 19, 19)
    ImageDraw.Draw(sample).line([(0, 1), (2, 1)], fill=41)
    assert list(sample.getdata()) == [19] * 3 + [41] * 3 + [19] * 3


def pandas_checks():
    import pandas as pd

    s = pd.Series([3, 1, 2])
    assert pd.Series(["a", "b", "a"]).value_counts().to_dict() == {"a": 2, "b": 1}
    assert s.groupby(["a", "a", "b"]).sum().to_dict() == {"a": 4, "b": 2}
    assert s.rank().tolist() == [3., 1., 2.]


def scipy_checks():
    from scipy import stats

    assert stats.rankdata([3, 1, 2]).tolist() == [3., 1., 2.]
    assert math.isclose(stats.percentileofscore([1, 2, 3], 2), 200 / 3)
    assert math.isclose(stats.kendalltau([1, 2, 3], [1, 2, 3])[0], 1.)


CHECKS = {"pillow": pillow_checks, "pandas": pandas_checks, "scipy": scipy_checks}


def process_project(project, output):
    frame_path = Path(__file__).with_name("frame.json")
    frame = json.loads(frame_path.read_text(encoding="utf-8"))[project]
    requirements = [] if project == "pillow" else ["numpy==1.25.2"]
    if project == "pandas":
        requirements += ["python-dateutil==2.9.0.post0", "six==1.17.0",
                         "pytz==2025.2", "tzdata==2025.2"]
    records = []
    output.mkdir(parents=True, exist_ok=True)
    for version in frame["versions"]:
        with tempfile.TemporaryDirectory() as folder:
            venv.create(folder, with_pip=True)
            python = Path(folder) / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            receipt = Path(folder) / "install.json"
            subprocess.run([python, "-m", "pip", "install", "--only-binary=:all:",
                            "--disable-pip-version-check", "--report", receipt,
                            f"{project}=={version}", *requirements], check=True)
            installed = json.loads(receipt.read_text(encoding="utf-8"))
            packages = [{"name": p["metadata"]["name"], "version": p["metadata"]["version"],
                         "url": p["download_info"]["url"],
                         "sha256": p["download_info"]["archive_info"]["hashes"]["sha256"]}
                        for p in installed["install"]]
            start = time.perf_counter_ns()
            subprocess.run([python, __file__, project, "--worker", version], check=True)
            records.append({"version": version, "packages": packages,
                            "operations_passed": frame["operations"],
                            "process_and_import_ns": time.perf_counter_ns() - start})
    result = {"project": project, "purpose": "ordinary-input environment preflight",
              "python": sys.version, "frame_sha256": hashlib.sha256(frame_path.read_bytes()).hexdigest(),
              "releases": records}
    (output / f"{project}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("project", choices=CHECKS)
    parser.add_argument("--worker")
    parser.add_argument("--output", type=Path, default=Path("preflight-results"))
    args = parser.parse_args()
    if args.worker:
        assert importlib.metadata.version(args.project) == args.worker
        CHECKS[args.project]()
    else:
        process_project(args.project, args.output)
