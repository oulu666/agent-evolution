"""Repeat the original independent Qwen prompts with teacher content absent."""
from concurrent.futures import ThreadPoolExecutor
import json

import one_response as experiment


if __name__ == "__main__":
    before_dir = experiment.OUT
    experiment.OUT = experiment.base.HERE / "astra_qwen_plan_withdrawn"
    experiment.OUT.mkdir(exist_ok=True)
    cases = experiment.base.make_cases(experiment.base.SEED)
    experiment.base.save(experiment.OUT / "boards.json", cases)
    with ThreadPoolExecutor(2) as pool:
        rows = list(pool.map(lambda case: experiment.run(case, "one_response_alone"), cases))
    identical = []
    before_wins = []
    for row in rows:
        before = json.loads((before_dir / f"{row['id']:02d}-one_response_alone.json").read_text())
        assert row["calls"][0]["prompt"] == before["calls"][0]["prompt"]
        assert len(row["calls"]) == 1
        if row["calls"][0]["output"] == before["calls"][0]["output"]:
            identical.append(row["id"])
        if before["solved"]:
            before_wins.append(row["id"])
    summary = dict(before_wins=sorted(before_wins),
                   after_wins=sorted(r["id"] for r in rows if r["solved"]),
                   identical_outputs=sorted(identical),
                   total_tokens=sum(r["tokens"] for r in rows),
                   teacher_content_in_request=False, weight_updates=False)
    experiment.base.save(experiment.OUT / "summary.json", summary)
    print(json.dumps(summary, indent=2))
