"""GPU smoke comparison, separate outputs; does not select the research policy."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fac_tinyagent.replay_study import ROOT, OUT, checkpoint, FAMILIES
from fac_tinyagent.sft.evaluate import load_eval_model, evaluate_family
from fac_tinyagent.utils import read_jsonl, write_json

config, stage, adapter = checkpoint("A", 20261108, 3)
model, tokenizer = load_eval_model(config, str(adapter))
comparisons = []
for family in FAMILIES:
    episodes = read_jsonl(ROOT / "data_phase2" / family / "test.jsonl")[:3]
    paths = []
    for size in (1, 8):
        config["evaluation"]["batch_size"] = size
        output = OUT / "batch_validation" / f"batch{size}" / family
        evaluate_family(model, tokenizer, episodes, config, stage, output,
                        str(ROOT / "data_phase2" / "fixtures" / "toolbench.db"),
                        str(ROOT / "data_phase2" / "fixtures" / "calendar.json"))
        paths.append(output / "results.jsonl")
    before, after = [read_jsonl(path) for path in paths]
    for a, b in zip(before, after):
        keys = ["tool_correct", "arguments_correct", "execution_success", "final_correct"]
        comparisons.append({"family": family, "episode_id": a["episode_id"],
                            "outcome_agreement": all(a[k] == b[k] for k in keys),
                            "raw_agreement": all(a[k] == b[k] for k in ("tool_call_raw", "answer_raw")),
                            "legacy": {k: a[k] for k in keys}, "batch": {k: b[k] for k in keys}})
write_json(OUT / "batch_validation" / "comparison.json", comparisons)
print("BATCH VALIDATION", len(comparisons), "outcomes match", sum(r["outcome_agreement"] for r in comparisons),
      "raw match", sum(r["raw_agreement"] for r in comparisons), flush=True)
