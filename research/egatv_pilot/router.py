"""Run the project's frozen P11 Qwen adapter on the shared task proposals on CPU."""
import hashlib
import json
from pathlib import Path
import time

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from tasks import TOOLS, VALUES, request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = "/home/egret/models/Qwen3-0.6B"
ADAPTER = ROOT / "runs_ext_p11_eaar_v1/branches/A_seed20261108_eaar_v1/checkpoint"
OUT = ROOT / "runs_egatv_pilot_20261125"
torch.set_num_threads(4)
start = time.perf_counter()
tok = AutoTokenizer.from_pretrained(BASE, local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.float32, local_files_only=True)
model = PeftModel.from_pretrained(model, str(ADAPTER)).merge_and_unload().eval()
load_seconds = time.perf_counter() - start
rows = []
with torch.inference_mode():
    for tool in TOOLS:
        for i, value in enumerate(VALUES[tool]):
            options = TOOLS if i % 2 == 0 else TOOLS[::-1]
            descriptions = {"week": "format a calendar week label", "duration": "write an elapsed-time cell"}
            text = "\n".join(f"{letter}. {descriptions[k]}" for letter,k in zip("AB", options))
            msg = request(tool, value) + "\nSelect the tool. Answer only A or B.\n" + text
            chat = tok.apply_chat_template([{"role":"user","content":msg}], tokenize=False,
                                           add_generation_prompt=True, enable_thinking=False)
            inp = tok(chat, return_tensors="pt", add_special_tokens=False)
            ids = [tok.encode(k, add_special_tokens=False) for k in "AB"]
            assert all(len(s) == 1 for s in ids)
            tick = time.perf_counter()
            logits = model(**inp).logits[0,-1,[s[0] for s in ids]]
            probs = torch.softmax(logits, dim=0)
            choice = int(probs.argmax())
            rows.append(dict(tool=tool, value=value, request=msg, picked=options[choice], confidence=float(probs[choice]),
                             input_tokens=inp.input_ids.numel(), decision_tokens=1, seconds=time.perf_counter()-tick))
out = dict(base=BASE,adapter=ADAPTER.name,adapter_sha256=hashlib.sha256((ADAPTER/"adapter_model.safetensors").read_bytes()).hexdigest(),
           load_seconds=load_seconds, rows=rows)
(OUT/"routing.json").write_text(json.dumps(out, indent=2))
print("routes",len(rows),"correct",sum(r["tool"]==r["picked"] for r in rows))

