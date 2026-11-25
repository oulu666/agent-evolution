"""Replay pinned source packages, then score independent detectors concurrently."""
import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile

from design import CANARIES, METHODS, alternative, decide, splits, standard, tasks

HERE = Path(__file__).resolve().parent


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def worker(project, directory):
    sys.path.insert(0, directory)
    lib = importlib.import_module(project)
    assert Path(lib.__file__).resolve().is_relative_to(Path(directory).resolve())
    fn = lib.underscore if project == "inflection" else lib.decamelize
    inputs = {x for x, _ in CANARIES[project]}
    for task in tasks():
        raw = task["raw"]
        inputs.update([raw, raw + "Record", alternative(raw)])
    observed = {}
    for raw in sorted(inputs):
        try:
            observed[raw] = {"value": fn(raw)}
        except Exception as exc:
            observed[raw] = {"error": type(exc).__name__}
    print(json.dumps(observed))


def project_runs(project, meta, temp):
    root = Path(temp) / project
    subprocess.run(["git", "clone", "--quiet", "--bare", "https://github.com/" + meta["repo"] + ".git",
                    str(root)], check=True)
    git = ["git", "--git-dir=" + str(root)]
    releases = {}
    for tag, sha in meta["versions"].items():
        with tempfile.TemporaryDirectory() as copy:
            entries = subprocess.check_output(git + ["ls-tree", "-r", "--name-only", sha], text=True)
            for name in entries.splitlines():
                if not (name == project + ".py" or name.startswith(project + "/") and name.endswith(".py")):
                    continue
                path = Path(copy) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(subprocess.check_output(git + ["show", sha + ":" + name]))
            proc = subprocess.run([sys.executable, str(HERE / "run.py"), "--worker", project, copy],
                                  capture_output=True, text=True, timeout=60)
            if proc.returncode:
                raise RuntimeError(f"{project} {tag}: {proc.stderr}")
            releases[tag] = json.loads(proc.stdout)
    return project, releases


def score_method(method, data, workload, out):
    detail = []
    for project, releases in data.items():
        for tag, obs in releases.items():
            canary = all(obs[x].get("value") == y for x, y in CANARIES[project])
            for t in workload:
                raw = t["raw"]
                verdict = decide(method, raw, obs, canary)
                correct = obs[raw].get("value") == t["target"]
                detail.append(dict(project=project, tag=tag, task=t["id"], correct=correct,
                                   verdict=verdict))
    write(out / (method + ".json"), detail)
    return method, {v: {c: sum(r["verdict"] == v and r["correct"] == (c == "correct")
                               for r in detail) for c in ("correct", "wrong")}
                    for v in ("alert", "pass", "unknown")}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    pins = json.loads((HERE / "pins.json").read_text())
    workload = tasks()
    write(out / "tasks.json", workload)
    with tempfile.TemporaryDirectory() as temp, ThreadPoolExecutor(max_workers=len(pins)) as pool:
        jobs = [pool.submit(project_runs, project, meta, temp) for project, meta in pins.items()]
        data = dict(job.result() for job in jobs)
    write(out / "observations.json", data)
    with ThreadPoolExecutor(max_workers=len(METHODS)) as pool:
        summary = dict(pool.map(lambda m: score_method(m, data, workload, out), METHODS))
    fallback = []
    for task in workload:
        raw = task["raw"]
        options = splits(raw.lower())
        result = "_".join(options[0]) if len(options) == 1 else standard(raw)
        fallback.append(dict(task=task["id"], correct=result == task["target"], output=result))
    write(out / "direct.json", fallback)
    write(out / "summary.json", summary)


if __name__ == "__main__":
    if sys.argv[1] == "--worker":
        worker(*sys.argv[2:])
    else:
        main()
