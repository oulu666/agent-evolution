"""Pre-flight: verify chat template and assistant-only labels with the real tokenizer."""
import argparse
import json
import sys
from pathlib import Path

from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fac_tinyagent.sft.dataset import (assistant_spans, conversation_text,
                                       tokenize_episode)

MODEL = "/home/egret/models/Qwen3-0.6B"


def main() -> None:
    # [ext-paper 2026-11-10] optional --model / --max-length; defaults unchanged.
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--max-length", type=int, default=1024)
    args = parser.parse_args()
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    print("model:", args.model)
    print("chat_template:", bool(getattr(tokenizer, "chat_template", None)))
    start_id = tokenizer.convert_tokens_to_ids("<|im_start|>")
    end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
    print("im_start id:", start_id, "im_end id:", end_id)
    row = json.loads((ROOT / "data" / "file" / "train.jsonl")
                     .read_text(encoding="utf-8").splitlines()[0])
    text = conversation_text(tokenizer, row["messages"], generation=False)
    print("rendered prefix:", repr(text[:180]))
    encoded = tokenize_episode(row, tokenizer, int(args.max_length))
    spans = assistant_spans(encoded["input_ids"], tokenizer)
    labeled = sum(1 for value in encoded["labels"] if value != -100)
    print("tokens:", len(encoded["input_ids"]), "labeled:", labeled, "spans:", spans)
    if len(spans) != 2 or labeled == 0:
        raise SystemExit("FAIL: expected two assistant spans with labels")
    print("PASS")


if __name__ == "__main__":
    main()
