"""Capture the materials' factual reference without accessing any participant data."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
RELEASES = (("cachetools", "5.5.2"), ("wcwidth", "0.2.9"), ("wcwidth", "0.2.10"))


def cache_observations():
    from cachetools import FIFOCache, cached

    def inserts(keys):
        events = []

        class Queue(FIFOCache):
            def popitem(self):
                item = super().popitem()
                events.append("evict " + item[0])
                return item

        store = Queue(maxsize=2)
        for key in keys:
            events.append("start " + key)
            store[key] = key
            events.append("end " + key)
        return {"keys": list(store), "events": events, "size": store.currsize}

    def measured(reuse):
        entries = []

        @cached(cache={})
        def work(x):
            entries.append(x)
            return x + 1

        call = work if reuse else work.__wrapped__
        return {"output": [call(4), call(4)], "entries": entries}

    # A deliberately narrow test harness generates only output-equality assertions.
    clauses = {"membership": ("key x is readable", lambda c: "x" in c),
               "capacity": ("size equals number of keys", lambda c: c.currsize == len(c))}
    enabled = {"membership"}
    sample = FIFOCache(maxsize=2)
    sample["x"] = 1
    ran = {k: check(sample) for k, (_, check) in clauses.items() if k in enabled}
    return {"below": inserts("xy"), "third": inserts("xyz"), "ordinary": inserts("x"),
            "registry": {"executed": ran, "output": sample["x"], "size": sample.currsize,
                         "manual_check": clauses["capacity"][1](sample)},
            "reuse": measured(True), "no_reuse_control": measured(False)}


def capture():
    evidence = {}
    with tempfile.TemporaryDirectory() as tmp:
        for project, version in RELEASES:
            with urlopen(f"https://pypi.org/pypi/{project}/{version}/json", timeout=30) as response:
                meta = json.load(response)
            wheel, = [f for f in meta["urls"] if f["filename"].endswith(".whl")]
            with urlopen(wheel["url"], timeout=30) as response:
                payload = response.read()
            digest = hashlib.sha256(payload).hexdigest()
            assert digest == wheel["digests"]["sha256"]
            path = Path(tmp) / wheel["filename"]
            path.write_bytes(payload)
            result = subprocess.check_output([sys.executable, "-I", __file__, str(path), project], text=True)
            evidence[f"{project} {version}"] = {"wheel_sha256": digest, "observations": json.loads(result)}
    target = HERE / "reference.json"
    out = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    if target.exists() and target.read_text(encoding="utf-8") != out:
        raise RuntimeError("Replay differs from the frozen reference")
    target.write_text(out, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        capture()
    else:
        sys.path.insert(0, sys.argv[1])
        if sys.argv[2] == "wcwidth":
            import wcwidth
            assert wcwidth.__file__.startswith(sys.argv[1])
            result = {s: wcwidth.wcswidth(s, unicode_version="15.0.0") for s in ("AB", "\u2640\ufe0f")}
        else:
            import cachetools
            assert cachetools.__file__.startswith(sys.argv[1])
            result = cache_observations()
        print(json.dumps(result))

