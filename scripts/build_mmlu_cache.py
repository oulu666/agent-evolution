import os, sys, traceback
os.environ.setdefault("HF_ENDPOINT","https://hf-mirror.com")
import datasets
snap = [d for d in os.listdir("/home/egret/.cache/huggingface/hub/datasets--cais--mmlu/snapshots")][0]
root = "/home/egret/.cache/huggingface/hub/datasets--cais--mmlu/snapshots/" + snap
subs = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root,d)) and d not in ("all","auxiliary_train"))
bad = []
for s in subs:
    try:
        ds = datasets.load_dataset("cais/mmlu", s)
        print("OK", s, {k: len(v) for k, v in ds.items()}, flush=True)
    except Exception as e:
        bad.append(s); print("FAIL", s, repr(e)[:300], flush=True)
print("SUBJECTS", len(subs), "BAD", bad, flush=True)

