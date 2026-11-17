from pathlib import Path
R=Path(__file__).resolve().parents[1]
src=(R/'fac_tinyagent/e3_train.py').read_text()
src='''# P6 attempt2: additive instrumented copy of e3_train.py. No optimizer, schedule or loss changes.
# Changes: device follows model (CPU contract tests); actual optimizer.step receipts and tail audit.
'''+src
old='batch = {k: v.to("cuda") for k, v in collator([features]).items()}'
assert src.count(old)==1
src=src.replace(old,'batch = {k: v.to(next(model.parameters()).device) for k, v in collator([features]).items()}')
anchor='    maximum_gpu = gpu_peak_gb()\n    started = time.time()'
assert src.count(anchor)==1
src=src.replace(anchor,'''    actual_optimizer_events = []
    original_optimizer_step = optimizer.step
    def receipt_step(*args, **kwargs):
        result = original_optimizer_step(*args, **kwargs)
        event = {"time": now_iso(), "suffix_step": len(actual_optimizer_events) + 1,
                 "global_optimizer_step": counters["optimizer_steps"] + 1,
                 "microstep": counters["microsteps"],
                 "tail_flush": counters["microsteps"] % accumulation != 0}
        actual_optimizer_events.append(event)
        append_jsonl(output / "optimizer_update_log.jsonl", event)
        return result
    optimizer.step = receipt_step
    maximum_gpu = gpu_peak_gb()
    started = time.time()''')
anchor='    model.save_pretrained(str(output))'
assert src.count(anchor)==1
src=src.replace(anchor,'''    prefix_updates = restored["counters"]["optimizer_steps"] if prefix_reused else 0
    prefix_microsteps = restored["counters"]["microsteps"] if prefix_reused else 0
    if prefix_microsteps % accumulation:
        raise AssertionError("prefix does not end at an accumulation boundary")
    expected_suffix_updates = math.ceil((counters["microsteps"] - prefix_microsteps) / accumulation)
    if len(actual_optimizer_events) != expected_suffix_updates:
        raise AssertionError("actual optimizer.step calls differ from expected suffix updates")
    if counters["optimizer_steps"] != prefix_updates + len(actual_optimizer_events):
        raise AssertionError("optimizer counter differs from actual step calls")
    step_audit = {"prefix_updates": prefix_updates, "prefix_microsteps": prefix_microsteps,
                  "suffix_actual_optimizer_steps": len(actual_optimizer_events),
                  "total_actual_optimizer_steps": prefix_updates + len(actual_optimizer_events),
                  "suffix_microsteps": counters["microsteps"] - prefix_microsteps,
                  "tail_microsteps": remainder,
                  "tail_actual_steps": sum(e["tail_flush"] for e in actual_optimizer_events)}
    write_json(output / "optimizer_step_audit.json", step_audit)
    model.save_pretrained(str(output))''')
anchor='        "completed": True,'
assert src.count(anchor)==1
src=src.replace(anchor,'        "optimizer_step_audit": step_audit,\n'+anchor)
p=R/'fac_tinyagent/p6_e3_train_attempt2.py'
assert not p.exists();p.write_text(src)
print('generated additive trainer; optimizer/loss/schedule code unchanged')
