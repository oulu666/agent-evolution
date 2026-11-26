"""Subprocess target for one public calibration library call.

The parent puts the pinned wheel or slugify checkout on argv. This process
imports only that copy. It does not compare the return value to an expected
value and it does not score the call.
"""

import json
import sys
from pathlib import Path


def main():
    library_path, library, version, payload_text = sys.argv[1:5]
    sys.path.insert(0, library_path)
    payload = json.loads(payload_text)
    if library == "XlsxWriter":
        import xlsxwriter
        if xlsxwriter.__version__ != version:
            raise RuntimeError(f"xlsxwriter version {xlsxwriter.__version__} != {version}")
        repo = Path(__file__).resolve().parents[2]
        sys.path.insert(1, str(repo))
        import upstream_functional_witnesses as witness
        value = payload["input"]
        if payload["operation"] == "column":
            result = witness.workbook_result(value)
        elif payload["operation"] == "duration":
            result = witness.workbook_result([], value)
        else:
            raise RuntimeError(f"unregistered XlsxWriter operation: {payload['operation']}")
        reported = xlsxwriter.__version__
        extra = {}
    elif library == "Babel":
        from datetime import date
        import babel
        from babel.dates import format_date
        if babel.__version__ != version:
            raise RuntimeError(f"babel version {babel.__version__} != {version}")
        result = format_date(date.fromisoformat(payload["input"]), "YYYY-'W'ww-e", locale="de_DE")
        reported = babel.__version__
        extra = {}
    elif library == "python-slugify":
        # The parent commit declares Unidecode. Isolated mode hides the user site,
        # so the declared dependency is added without putting another slugify first.
        import site
        user_site = site.getusersitepackages()
        if user_site and user_site not in sys.path:
            sys.path.append(user_site)
        import slugify as slugify_module
        function = getattr(slugify_module, "slugify")
        result = function(payload["input"]["arg"], **payload["input"]["kw"])
        from importlib.metadata import version
        reported = payload["commit"]
        extra = {"dependency": {"unidecode": version("Unidecode")}}
    else:
        raise RuntimeError(f"unregistered calibration library: {library}")
    body = {"version": reported, "result": result}
    body.update(extra)
    print(json.dumps(body, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"error_type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
