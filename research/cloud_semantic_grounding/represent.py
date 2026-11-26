"""Frozen representations of questions, plan roles and bounded column previews."""
import hashlib
from pathlib import Path
import re
import time
import urllib.request

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

REV = "81d1926f67cb8eee2c2be17ca9f793c7c3bd20cc"
URL = "https://huggingface.co/cross-encoder/ms-marco-TinyBERT-L2-v2/resolve/" + REV + "/"
AGGS = ("return", "maximum", "minimum", "count", "sum", "average")
OPS = ("equals", "greater than", "less than")


def get_model(folder):
    folder.mkdir(exist_ok=True, parents=True)
    for filename, remote, length, checksum in (
        ("model.onnx", "onnx/model_quint8_avx2.onnx", 4518068, "a1ebdfe09dc81382cfabe64ddce946c1e75c9afaef0ec4e8d4f6d8274b23b48c"),
        ("tokenizer.json", "tokenizer.json", 711396, "688882a79f44442ddc1f60d70334a7ff5df0fb47"),
    ):
        dest = folder / filename
        for attempt in range(3):
            try:
                if dest.exists():
                    blob = dest.read_bytes()
                else:
                    with urllib.request.urlopen(URL + remote + "?download=true", timeout=60) as response:
                        blob = response.read()
                if len(checksum) == 40:
                    hashed = hashlib.sha1(f"blob {len(blob)}\0".encode() + blob).hexdigest()
                else:
                    hashed = hashlib.sha256(blob).hexdigest()
                if len(blob) != length or hashed != checksum:
                    raise ValueError("artifact digest mismatch: " + filename)
                dest.write_bytes(blob)
                break
            except (OSError, ValueError):
                if attempt == 2:
                    raise
                dest.unlink(missing_ok=True)
                time.sleep(2 ** attempt)


class Encoder:
    def __init__(self, folder):
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(folder / "model.onnx"), options, providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=96)
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")

    def score(self, pairs):
        lookup = list(dict.fromkeys(pairs))
        result = {}
        tokens = 0
        for start in range(0, len(lookup), 32):
            batch = lookup[start:start+32]
            encoded = self.tokenizer.encode_batch(batch)
            masks = np.array([x.attention_mask for x in encoded], dtype=np.int64)
            tokens += int(masks.sum())
            inputs = dict(input_ids=np.array([x.ids for x in encoded], dtype=np.int64),
                          attention_mask=masks, token_type_ids=np.array([x.type_ids for x in encoded], dtype=np.int64))
            logits = self.session.run(None, {v.name: inputs[v.name] for v in self.session.get_inputs()})[0]
            assert logits.size == len(batch) and np.isfinite(logits).all()
            result.update(zip(batch, logits.ravel().tolist()))
        return result, len(lookup), tokens


def frames(t):
    q = t["question"]
    parts = re.split(r"\b(?:where|whose|when|with|for which|for the|given that|if)\b", q, maxsplit=1, flags=re.I)
    target = parts[0].strip() or q
    condition = parts[-1].strip() or q
    for col, agg, clauses in t["plans"]:
        name = t["headers"][col]
        predicates = [f"{t['headers'][c]} {OPS[op]} {v}" for c, op, v in clauses]
        full = f"{AGGS[agg]} {name}" + (" where " + " and ".join(predicates) if predicates else "")
        yield (q, full), (target, name), [(condition, pred) for pred in predicates], col


def preview(t):
    result = {}
    observed_cells = 0
    for c in sorted({p[0] for p in t["plans"]}):
        vals = []
        for row in t["rows"][:6]:
            observed_cells += 1
            value = "" if row[c] is None else str(row[c]).strip()[:48]
            if value and value not in vals:
                vals.append(value)
            if len(vals) == 2:
                break
        result[c] = t["headers"][c] + " (examples: " + " | ".join(vals) + ")"
    return result, observed_cells


def similarity(pair):
    q, h = [s.lower() for s in pair]
    qw, hw = [set(re.findall(r"\w+", s)) for s in (q, h)]
    qg, hg = [{s[i:i+3] for i in range(len(s)-2)} for s in (q, h)]
    return len(qw & hw)/max(1, len(hw)), len(qg & hg)/max(1, len(hg))


def block(mode, t, encoder):
    fs = list(frames(t))
    previewed, cells = preview(t) if mode in ("lexsamples", "samples") else ({}, 0)
    if mode.startswith("lex"):
        features = []
        for joint, output, preds, c in fs:
            if mode == "lexsamples":
                features.append(similarity((output[0], previewed[c])))
            else:
                features.append((*similarity(joint), *similarity(output),
                                 min((similarity(p)[0] for p in preds), default=0)))
        return features, (0, 0, cells)
    pairs = []
    for joint, output, preds, c in fs:
        if mode == "joint":
            pairs.append(joint)
        elif mode == "roles":
            pairs.extend([output, *preds])
        else:
            pairs.append((output[0], previewed[c]))
    logits, count, tokens = encoder.score(pairs)
    features = []
    for joint, output, preds, c in fs:
        if mode == "joint":
            features.append([logits[joint]])
        elif mode == "roles":
            values = [logits[p] for p in preds]
            features.append([logits[output], min(values, default=0), sum(values)/max(1, len(values))])
        else:
            features.append([logits[output[0], previewed[c]]])
    return features, (count, tokens, cells)
