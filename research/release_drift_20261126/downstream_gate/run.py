"""Build an unchanged consumer twice, then replay its own documentation links."""
import hashlib
import json
import os
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from time import perf_counter
import tomllib
from urllib.parse import quote, unquote, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag
from playwright.sync_api import sync_playwright

ROOT = Path.cwd()
CONSUMER = ROOT / "consumer"
OUT = ROOT / "gate-results"
ORIGIN = "https://www.mkdocs.org"
REV = "00b648f0884244a139f034554b59a032113176f6"
VERSIONS = ("3.4.4", "3.5")
WHEEL_HASH = {"3.4.4": "a4c1b65c0957b4bd9e7d86ddc7b3c9868fb9670660f6f99f6d1bca8954d5a941",
              "3.5": "4afb124395ce5fc34e6d9886dab977fd9ae987fc6e85689f08278cf0c69d4bf3"}
HEADER = re.compile("^h[1-6]$")


def command(args, *, cwd=ROOT, env=None):
    return subprocess.run(args, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, errors="replace")


def checked(args, **kwargs):
    result = command(args, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stdout[-4000:])
    return result.stdout


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def prepare(base):
    import urllib.request
    assert checked(["git", "rev-parse", "HEAD"], cwd=CONSUMER).strip() == REV
    meta = tomllib.loads((CONSUMER / "pyproject.toml").read_text())
    deps = list(meta["tool"]["hatch"]["envs"]["docs"]["dependencies"])
    req = base / "old.in"
    req.write_text("\n".join(["mkdocs[i18n]==1.5.3", "Markdown==3.4.4", *deps])+"\n")
    lock = OUT / "historical-requirements.txt"
    checked(["uv", "pip", "compile", str(req), "--python", sys.executable, "--no-header",
             "--no-annotate", "--exclude-newer", "2023-09-19T00:00:00Z", "-o", str(lock)])
    for version in VERSIONS:
        with urllib.request.urlopen(f"https://pypi.org/pypi/Markdown/{version}/json") as f:
            metadata = json.load(f)
        wheel = next(u for u in metadata["urls"] if u["filename"].endswith(".whl"))
        with urllib.request.urlopen(wheel["url"]) as f:
            payload = f.read()
        assert hashlib.sha256(payload).hexdigest() == wheel["digests"]["sha256"] == WHEEL_HASH[version]
        (base / wheel["filename"]).write_bytes(payload)


def build(version, base):
    prefix = base / version
    python = prefix / "bin/python"
    checked(["uv", "venv", "--python", sys.executable, str(prefix)])
    wheel = next(p for p in base.glob("*.whl") if f"-{version}-" in p.name)
    requirements = re.sub(r"(?im)^markdown==3\.4\.4\s*$", str(wheel),
                          (OUT / "historical-requirements.txt").read_text())
    req = base / f"env-{version}.txt"
    req.write_text(requirements)
    checked(["uv", "pip", "install", "--python", str(python), "-r", str(req)])
    env = dict(os.environ, PATH=str(python.parent)+os.pathsep+os.environ["PATH"],
               PYTHONHASHSEED="0", TZ="UTC", SOURCE_DATE_EPOCH="1695072369")
    packages = json.loads(checked([str(python), "-c", "import json,importlib.metadata as m;print(json.dumps({d.metadata['Name'].lower():d.version for d in m.distributions()}))"], cwd=base))
    assert packages["markdown"] == version
    out = base / f"site-{version}"
    statuses = {}
    for name, argv in (("unit_build", ["-m", "unittest", "mkdocs.tests.build_tests"]),
                       ("native_integration", ["-m", "mkdocs.tests.integration", "--output", str(out)])):
        t = perf_counter()
        result = command([str(python), *argv], cwd=CONSUMER, env=env)
        (OUT / f"{version}-{name}.log").write_text(result.stdout)
        statuses[name] = {"exit": result.returncode, "seconds": round(perf_counter()-t, 3)}
    if statuses["native_integration"]["exit"] or not (out / "mkdocs/index.html").exists():
        result = command([str(python), "-m", "mkdocs", "build", "--site-dir", str(out/"mkdocs")],
                         cwd=CONSUMER, env=env)
        (OUT / f"{version}-diagnostic_build.log").write_text(result.stdout)
        statuses["diagnostic_build"] = {"exit": result.returncode}
        if result.returncode:
            raise RuntimeError(result.stdout[-2200:])
    save(version+"-env.json", {"packages": packages, "commands": statuses})
    return out / "mkdocs", packages, statuses


def title(tag):
    return " ".join("".join(s for s in tag.strings if not any(
        "headerlink" in a.get("class", []) for a in s.parents if isinstance(a, Tag))).split())


def site_path(file, site):
    path = "/"+file.relative_to(site).as_posix()
    return path[:-10] if path.endswith("/index.html") else path


def inventory(site):
    ids, links, hashes = {}, set(), {}
    raw_count = 0
    for file in sorted(site.rglob("*.html")):
        path = site_path(file, site)
        raw = file.read_bytes()
        hashes[path] = hashlib.sha256(raw).hexdigest()
        soup = BeautifulSoup(raw, "html.parser")
        main = soup.select_one('[role="main"]')
        stack, entries = [], defaultdict(list)
        for tag in soup.find_all(True):
            is_heading = bool(HEADER.fullmatch(tag.name))
            if is_heading:
                level = int(tag.name[1])
                stack = [(k,t) for k,t in stack if k<level] + [(level,title(tag))]
            if tag.get("id"):
                entries[tag["id"]].append([t for _,t in stack] if is_heading else None)
        ids[path] = entries
        if main is None:
            continue
        for a in main.select("a[href]"):
            if a.find_parent(["code","pre"]) or "headerlink" in a.get("class", []):
                continue
            url = urlsplit(urljoin(ORIGIN+path, a["href"]))
            if url.netloc != "www.mkdocs.org" or not url.fragment or url.scheme not in ("https","http"):
                continue
            raw_count += 1
            links.add((path, unquote(url.path), unquote(url.fragment)))
    return ids, links, hashes, raw_count


class QuietHTTP(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


@contextmanager
def serve(site):
    s = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHTTP, directory=str(site)))
    thread = Thread(target=s.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:"+str(s.server_port)
    finally:
        s.shutdown()
        s.server_close()
        thread.join()


BROWSER_JS = """() => {
    const target=document.querySelector(':target');
    if (!target) return null;
    if (!/^H[1-6]$/.test(target.tagName)) return 'nonheading';
    const map = new Map(), stack = [];
    for (const h of document.querySelectorAll('h1,h2,h3,h4,h5,h6')) {
        const level = Number(h.tagName.slice(1)), c=h.cloneNode(true);
        c.querySelectorAll('.headerlink').forEach(n=>n.remove());
        while(stack.length && stack.at(-1)[0]>=level) stack.pop();
        stack.push([level,c.textContent.trim().replace(/\\s+/g,' ')]);
        if (h===target) return stack.map(s=>s[1]);
    }
    return null;
}"""


def browser_read(browser, site, destinations):
    results = {}
    with serve(site) as origin:
        page = browser.new_page()
        page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin+"/") else route.abort())
        for path, frags in sorted(destinations.items()):
            response = page.goto(origin+path, wait_until="domcontentloaded")
            if response.status != 200:
                results[path] = {}
                continue
            results[path] = {}
            for f in sorted(frags):
                page.goto(origin+path+"#"+quote(f,safe=""), wait_until="domcontentloaded")
                results[path][f] = page.evaluate(BROWSER_JS)
        page.close()
    return results


def compare(sites, statuses):
    a, b = [inventory(site) for site in sites]
    destinations = defaultdict(set)
    eligible = []
    excluded = Counter()
    for src,path,f in sorted(a[1]):
        matches = a[0].get(path, {}).get(f, [])
        if len(matches) != 1 or matches[0] is None:
            excluded["missing" if not matches else "duplicate" if len(matches)>1 else "nonheading"] += 1
            continue
        destinations[path].add(f)
        eligible.append((src,path,f))
    assert eligible
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", args=["--disable-ipc-flooding-protection"])
        # Positive and negative controls for native fragment selection.
        page = browser.new_page()
        with TemporaryDirectory() as tmp:
            fixture = Path(tmp)
            (fixture/"index.html").write_text("<h1 id='known'>First</h1>")
            with serve(fixture) as origin:
                for f, want in (("known", ["First"]), ("missing", None)):
                    page.goto(origin+"/#"+f, wait_until="domcontentloaded")
                    got = page.evaluate(BROWSER_JS)
                    assert got == want, (f, got, want)
        page.close()
        old, new = [browser_read(browser, site, destinations) for site in sites]
        chrome = browser.version
        browser.close()
    rows = []
    for src,path,f in eligible:
        old_ctx = old[path].get(f)
        new_ctx = new[path].get(f)
        matches = b[0].get(path, {}).get(f, [])
        old_static = a[0][path][f][0]
        rows.append({"source":src, "page":path, "fragment":f, "old_browser":old_ctx, "new_browser":new_ctx,
                     "old_browser_agrees": old_ctx == old_static, "exists_once":len(matches)==1,
                     "static_same_section": matches == [old_static], "new_source_still_links": (src,path,f) in b[1]})
    assert all(isinstance(r["old_browser"],list) for r in rows), "review old target before scoring"
    changes = [r for r in rows if r["new_browser"] != r["old_browser"]]
    save("paired-links.json", rows)
    save("summary.json", {"consumer":REV,"markdown_versions":VERSIONS,"wheel_sha256":WHEEL_HASH,"browser":chrome,
        "native":statuses,"html_pages":[len(x[2]) for x in (a,b)],"overlapping_pages_byte_changed":
        sum(a[2][p]!=b[2][p] for p in a[2].keys() & b[2].keys()),
        "old_body_fragment_occurrences":a[3], "old_distinct_refs":len(a[1]), "excluded":excluded,
        "paired":len(rows),"unique_destinations":sum(map(len,destinations.values())),
        "old_static_browser_disagree":sum(not r["old_browser_agrees"] for r in rows),
        "new_source_dropped":sum(not r["new_source_still_links"] for r in rows),
        "browser_changed":len(changes),"new_static_missing_or_duplicate":sum(not r["exists_once"] for r in rows),
        "new_static_changed_section":sum(not r["static_same_section"] for r in rows),
        "browser_changed_static_both_pass":sum(r["exists_once"] and r["static_same_section"] for r in changes)})


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        prepare(base)
        with ThreadPoolExecutor(max_workers=2) as pool:
            arms = list(pool.map(lambda version: build(version, base), VERSIONS))
        envs = [dict(env) for _,env,_ in arms]
        for env in envs:
            del env["markdown"]
        assert envs[0] == envs[1], "confounded dependency comparison"
        compare([s for s,_,_ in arms], [status for _,_,status in arms])
