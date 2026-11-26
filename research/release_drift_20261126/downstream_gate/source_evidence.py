"""Match scored browser references to explicit addresses in the old Markdown sources."""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

BASE = "https://www.mkdocs.org"
INLINE = re.compile(r"""\]\(\s*<?([^\s<>)]+#[^\s<>)]+|#[^\s<>)]+)""")
DEFINITION = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?([^\s<>]+)")
HTML = re.compile(r"""<a\b[^>]*?\bhref\s*=\s*["']([^"']+)["']""", re.I)
FENCE = re.compile(r"^\s*(\x60{3,}|~{3,})")


def page_path(path):
    if path.endswith(("/index.md", "/README.md")):
        return path.rsplit("/", 1)[0] + "/"
    return path[:-3] + "/" if path.endswith(".md") else path


def references(docs):
    evidence = {}
    for source in sorted(docs.rglob("*.md")):
        rel = source.relative_to(docs).as_posix()
        page = page_path("/" + rel)
        fence = ""
        for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            marker = FENCE.match(line)
            if marker:
                token = marker[1]
                if not fence:
                    fence = token
                elif token.startswith(fence):
                    fence = ""
                continue
            if fence:
                continue
            line = re.sub(r"(\x60+).*?\1", "", line)
            for pattern in (INLINE, DEFINITION, HTML):
                for match in pattern.finditer(line):
                    addr = match[1]
                    u = urlsplit(urljoin(BASE + "/" + rel, addr))
                    if u.hostname != "www.mkdocs.org" or not u.fragment:
                        continue
                    path = page_path(unquote(u.path))
                    evidence.setdefault((page, path, unquote(u.fragment)), {
                        "file": "docs/" + rel, "line": number, "address": addr})
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs", type=Path)
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    evidence = references(args.docs)
    rows = json.loads((args.results / "paired-links.json").read_text(encoding="utf-8"))
    matches = []
    for row in rows:
        ref = tuple(row[k] for k in ("source", "page", "fragment"))
        if ref in evidence:
            matches.append({"source": ref[0], "page": ref[1], "fragment": ref[2], **evidence[ref]})
    result = {"paired": len(rows), "explicit_source_match": len(matches),
              "unmatched_origin": len(rows) - len(matches), "matches": matches}
    (args.results / "source-evidence.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(len(matches), "/", len(rows))
