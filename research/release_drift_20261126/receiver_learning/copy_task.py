import functools
import hashlib
import http.server
import json
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from time import perf_counter
from urllib.request import urlopen

from playwright.sync_api import sync_playwright
import yaml

from learn import evaluate

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clipboard_decision"))
from run import BASE, VERSIONS, Quiet


def collect(browser, origin, page_name, snippet):
    with browser.new_context(permissions=["clipboard-read", "clipboard-write"]) as ctx:
        page = ctx.new_page()
        page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin+"/") else r.abort())
        page.goto(origin + "/" + page_name + "/", wait_until="load")
        button = page.locator("button.md-clipboard")
        button.wait_for()
        page.evaluate("() => navigator.clipboard.writeText('pending delivery')")
        def observe():
            return [page.title(), page.evaluate("() => navigator.clipboard.readText()"),
                    page.locator("pre code").text_content()]
        page.wait_for_timeout(300)
        before = observe()
        start = perf_counter()
        button.click()
        page.wait_for_timeout(300)
        after = observe()
        return {"input": page_name, "expected": snippet, "before": before, "after": after,
                "seconds": perf_counter()-start}


def main():
    source = urlopen(BASE + "/docs/configuration/examples.md", timeout=30).read()
    assert hashlib.sha256(source).hexdigest() == "37cf714cbf65eadb4f9185f989fba69072217f828dfb3cabe102d14eb92cb429"
    source = source.decode()
    section = re.search(r"(?m)^#+ Generate labels via script\s*$", source).end()
    fence = re.search(r"(?ms)^([ ]*)\x60{3}yaml\n(.*?)^\1\x60{3}\s*$", source[section:])
    original = "\n".join(line.removeprefix(fence[1]) for line in fence[2].splitlines())
    examples = {"demo-a": "count: 41", "demo-b": "count: 73", "original": original}
    demos, rows = [], []
    config = {"site_name": "scm-engine", "theme": {"name": "material", "features": ["content.code.copy"]},
              "markdown_extensions": [{"pymdownx.highlight": {"anchor_linenums": True, "line_spans": "__span",
                                      "pygments_lang_class": True, "use_pygments": True}}, "pymdownx.superfences"]}
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        root = Path(tmp)
        docs = root / "docs"
        docs.mkdir()
        (root / "mkdocs.yml").write_text(yaml.safe_dump(config))
        for name, snippet in examples.items():
            marker = chr(96)*3
            (docs / f"{name}.md").write_text(f"# Configuration\n\n{marker}yaml\n{snippet}\n{marker}\n")
        browser = pw.chromium.launch(channel="chrome")
        for version in VERSIONS:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "mkdocs-material=="+version], check=True)
            site = root / version
            subprocess.run([sys.executable, "-m", "mkdocs", "build", "--strict", "-d", str(site)], cwd=root, check=True)
            handler = functools.partial(Quiet, directory=str(site))
            with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    origin = "http://127.0.0.1:" + str(server.server_port)
                    if version == VERSIONS[0]:
                        demos = [collect(browser, origin, n, examples[n]) for n in ("demo-a", "demo-b")]
                    rows.append(dict(collect(browser, origin, "original", original), version=version))
                finally:
                    server.shutdown()
                    thread.join()
        browser.close()
    receipt = evaluate(demos, rows, 1, "text")
    receipt["slots"] = ["title", "clipboard", "page code"]
    Path("copy-receipt.json").write_text(json.dumps(receipt, indent=1)+"\n")


if __name__ == "__main__":
    main()
