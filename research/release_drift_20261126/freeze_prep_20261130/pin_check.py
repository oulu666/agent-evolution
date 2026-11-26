"""Random-arm interpreter pin check.

Runs only under CPython 3.11. It initializes the registered seed once per
case and does not draw a request or import a calibration library.
"""

import json
import platform
import random
import sys


def main():
    if platform.python_implementation() != "CPython" or sys.version_info[:2] != (3, 11):
        raise SystemExit("this pin check only runs on CPython 3.11")
    case_ids = json.loads(sys.argv[1])
    if not isinstance(case_ids, list) or not all(isinstance(item, str) for item in case_ids):
        raise SystemExit("pin check case list is not a list of strings")
    initialized = []
    for case_id in case_ids:
        random.Random(20261126)
        initialized.append({"case_id": case_id, "seed": 20261126, "sample_drawn": False})
    print(json.dumps({
        "executable": sys.executable,
        "version": sys.version,
        "version_info": list(sys.version_info[:3]),
        "implementation": platform.python_implementation(),
        "libraries_called": False,
        "formal_paired_comparison_started": False,
        "sample_drawn": False,
        "tasks": initialized,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
