"""Build one downstream configuration example and observe the real copy action."""
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
from urllib.request import urlopen

import yaml
from playwright.sync_api import sync_playwright

REF = "50a48fad86094c3a0b07bbfd799c4bbd31b5053d"
BASE = f"https://raw.githubusercontent.com/jippi/scm-engine/{REF}"
VERSIONS = ("9.5.17", "9.5.21", "9.5.22")


def canon(text):
    return text.replace("\r\n", "\n").removesuffix("\n")


def shape(value):
    if isinstance(value, dict):
        return {k: shape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [shape(v) for v in value]
    return type(value).__name__


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    source = urlopen(BASE + "/docs/configuration/examples.md", timeout=30).read().decode()
    section = re.search(r"(?m)^#+ Generate labels via script\s*$", source).end()
    fence = re.search(r"(?ms)^([ ]*)\x60{3}yaml\n(.*?)^\1\x60{3}\s*$", source[section:])
    lines = fence[2].splitlines()
    snippet = "\n".join(line.removeprefix(fence[1]) for line in lines)
    expected = yaml.safe_load(snippet)
    config_source = urlopen(BASE + "/mkdocs.yml", timeout=30).read().decode()
    assert "content.code.copy" in config_source and "line_spans: __span" in config_source
    config = {"site_name": "scm-engine copy acceptance", "theme": {"name": "material",
              "features": ["content.code.copy"]}, "markdown_extensions": [
              {"pymdownx.highlight": {"line_spans": "__span", "anchor_linenums": True,
              "pygments_lang_class": True, "use_pygments": True}}, "pymdownx.superfences"]}
    results = []
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        root = Path(tmp)
        (root / "docs").mkdir()
        (root / "mkdocs.yml").write_text(yaml.safe_dump(config))
        (root / "docs/index.md").write_text("# Generate labels via script\n\n" + chr(96)*3 +
                             "yaml\n" + snippet + "\n" + chr(96)*3 + "\n")
        browser = pw.chromium.launch(channel="chrome")
        environment = None
        for version in VERSIONS:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps",
                            "mkdocs-material==" + version], check=True)
            current = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
            packages = [s for s in current.splitlines() if not s.lower().startswith("mkdocs-material==")]
            if environment is None:
                environment = packages
            assert environment == packages
            site = root / version
            subprocess.run([sys.executable, "-m", "mkdocs", "build", "--strict", "-d", str(site)],
                           cwd=root, check=True)
            handler = functools.partial(Quiet, directory=str(site))
            with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
                t = threading.Thread(target=server.serve_forever, daemon=True)
                t.start()
                origin = "http://127.0.0.1:" + str(server.server_port)
                try:
                    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
                    page = context.new_page()
                    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin + "/") else r.abort())
                    page.goto(origin, wait_until="load")
                    dom = page.locator("pre code").text_content()
                    page.evaluate("() => navigator.clipboard.writeText('clipboard-before-click')")
                    button = page.locator("button.md-clipboard")
                    button.click(timeout=10000)
                    page.wait_for_function("async () => (await navigator.clipboard.readText()) !== 'clipboard-before-click'")
                    clipboard = page.evaluate("() => navigator.clipboard.readText()")
                    context.close()
                finally:
                    server.shutdown()
                    t.join()
            parsed = yaml.safe_load(clipboard)
            results.append(dict(version=version, strict_build=True, page_text_matches=canon(dom)==snippet,
                copy_matches=canon(clipboard)==snippet, yaml_shape_matches=shape(parsed)==shape(expected),
                yaml_value_matches=parsed==expected, expected_script=expected["label"][0]["script"],
                received_script=parsed["label"][0]["script"], received=clipboard,
                expected_lines=len(snippet.splitlines()), received_lines=len(canon(clipboard).splitlines())))
        browser_version = browser.version
        browser.close()
    out = dict(consumer_commit=REF, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        reference=snippet, browser=browser_version, python=sys.version, other_packages=environment, cases=results)
    Path("copy-results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n")
    print([(r["version"], r["page_text_matches"], r["yaml_shape_matches"], r["yaml_value_matches"],
            r["copy_matches"]) for r in results])


if __name__ == "__main__":
    main()
