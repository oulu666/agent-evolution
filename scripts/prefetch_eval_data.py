"""[ext-paper 2026-11-10] Prefetch lm-eval datasets into the HF hub cache (with retries),
so evaluations can run with HF_HUB_OFFLINE=1 / HF_DATASETS_OFFLINE=1 and avoid the
per-subject API calls that time out on this network (MMLU has 57 subsets).
Run with the fac-eval venv:  HF_ENDPOINT=https://hf-mirror.com python scripts/prefetch_eval_data.py
"""
import os
import sys
import time

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
from huggingface_hub import snapshot_download  # noqa: E402

REPOS = {
    "cais/mmlu": ["*/test-*.parquet", "*/validation-*.parquet", "*/dev-*.parquet",
                  "*.py", "README.md", "dataset_infos.json"],
    "allenai/ai2_arc": None,
    "google/IFEval": None,
}
names = sys.argv[1:] or list(REPOS)
for repo in names:
    for attempt in range(1, 31):
        try:
            path = snapshot_download(repo, repo_type="dataset",
                                     allow_patterns=REPOS.get(repo), max_workers=4)
            print("OK", repo, path, flush=True)
            break
        except Exception as exc:  # network flakiness: retry, already-downloaded files are kept
            print("retry %d %s: %s: %s" % (attempt, repo, type(exc).__name__, str(exc)[:200]),
                  flush=True)
            time.sleep(min(60, 5 * attempt))
    else:
        print("FAILED", repo, flush=True)
        sys.exit(1)
