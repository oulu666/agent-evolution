# Budgeted old-tool replay pilot

Order: A; completed branches: 9/9.

All values are proportions. Joint success requires correct tool, arguments, execution and final answer.

## Per-seed results

| Seed | Method | Old joint before | Old joint | Old answer before | Old answer | New joint before | New joint | New answer | Old lost | Old gained |
|---|---|---|---|---|---|---|---|---|---|---|
| 20261108 | none | 0.5222 | 0.5222 | 0.5222 | 0.6000 | 0.1667 | 0.9167 | 0.9167 | 1 | 1 |
| 20261108 | uniform | 0.5222 | 0.5333 | 0.5222 | 0.6000 | 0.1667 | 0.9167 | 0.9167 | 1 | 3 |
| 20261108 | adaptive | 0.5222 | 0.5333 | 0.5222 | 0.6000 | 0.1667 | 0.9167 | 0.9167 | 2 | 4 |
| 20261109 | none | 0.5222 | 0.5500 | 0.5444 | 0.6167 | 0.4167 | 0.9167 | 0.9167 | 0 | 5 |
| 20261109 | uniform | 0.5222 | 0.5611 | 0.5444 | 0.6389 | 0.4167 | 0.9167 | 0.9167 | 0 | 7 |
| 20261109 | adaptive | 0.5222 | 0.5500 | 0.5444 | 0.6222 | 0.4167 | 0.9167 | 0.9167 | 0 | 5 |
| 20261110 | none | 0.5222 | 0.5556 | 0.5500 | 0.6389 | 0.5000 | 0.9167 | 0.9167 | 2 | 8 |
| 20261110 | uniform | 0.5222 | 0.5556 | 0.5500 | 0.6389 | 0.5000 | 0.9167 | 0.9167 | 2 | 8 |
| 20261110 | adaptive | 0.5222 | 0.5556 | 0.5500 | 0.6389 | 0.5000 | 0.9167 | 0.9167 | 2 | 8 |

## Paired differences vs no replay

| Seed | uniform-none old joint | adaptive-none old joint | adaptive-uniform old joint | uniform-none old answer | adaptive-none old answer | adaptive-uniform new joint |
|---|---|---|---|---|---|---|
| 20261108 | +0.0111 | +0.0111 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 20261109 | +0.0111 | +0.0000 | -0.0111 | +0.0222 | +0.0056 | +0.0000 |
| 20261110 | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |

## Monitor detection

| Seed | database drop | file drop | python drop | targeting triggered | weights |
|---|---|---|---|---|---|
| 20261108 | 0.000 | 0.000 | 0.000 | False | database=0.333, file=0.333, python=0.333 |
| 20261109 | 0.000 | 0.000 | 0.000 | False | database=0.333, file=0.333, python=0.333 |
| 20261110 | 0.000 | 0.000 | 0.000 | False | database=0.333, file=0.333, python=0.333 |

Adaptive triggered in 0/3 seeds. All adaptive plans fell back to uniform weights.

## Cost: actual versus reference time

| Method | Reference full-flow s | Actual branch s | Shared-prefix reference s | Reference probe s | Actual probe s | Actual training s |
|---|---|---|---|---|---|---|
| none | 230.9 | 230.9 | 0.0 | 120.9 | 120.9 | 109.9 |
| uniform | 236.0 | 60.1 | 175.9 | 120.9 | 0.0 | 60.1 |
| adaptive | 236.2 | 60.3 | 175.9 | 120.9 | 0.0 | 60.3 |

## Cost: tokens

| Method | New input | Replay input | New supervised | Replay supervised | Monitor input | Monitor output | Optimizer steps |
|---|---|---|---|---|---|---|---|
| none | 74944 | 0 | 8542 | 0 | 84826 | 9247 | 20 |
| uniform | 74944 | 7491 | 8542 | 1191 | 84826 | 9247 | 23 |
| adaptive | 74944 | 7491 | 8542 | 1191 | 84826 | 9247 | 23 |

Reference full-flow includes the shared prefix. Actual branch is physically executed time; for replay arms, shared-prefix reference is the reused portion. Actual probe is 0 for replay arms because prefix probes were not rerun. Monitor tokens are inference tokens; training tokens are separate.
Training/probe cost records, task-level transitions and frozen protocol are in results.json.
Three seeds are exploratory; do not infer significance from pooled task counts.

## Invariant audit

```json
[
  {
    "seed": 20261108,
    "invariants": {
      "new_order_sha256": true,
      "start_trainable_state_sha256": true,
      "midpoint_trainable_state_sha256": true,
      "new_input_tokens": true,
      "new_samples": true
    },
    "all_invariants_pass": true,
    "replay_input_token_gap": 0,
    "replay_gap_fraction_of_budget": 0.0
  },
  {
    "seed": 20261109,
    "invariants": {
      "new_order_sha256": true,
      "start_trainable_state_sha256": true,
      "midpoint_trainable_state_sha256": true,
      "new_input_tokens": true,
      "new_samples": true
    },
    "all_invariants_pass": true,
    "replay_input_token_gap": 0,
    "replay_gap_fraction_of_budget": 0.0
  },
  {
    "seed": 20261110,
    "invariants": {
      "new_order_sha256": true,
      "start_trainable_state_sha256": true,
      "midpoint_trainable_state_sha256": true,
      "new_input_tokens": true,
      "new_samples": true
    },
    "all_invariants_pass": true,
    "replay_input_token_gap": 0,
    "replay_gap_fraction_of_budget": 0.0
  }
]
```

Joint success is a strict exact-call metric: semantically equivalent SQL arguments may fail it. Answer success is reported separately.
All arms were monitored to isolate allocation. A deployed uniform/no-replay policy does not require the adaptive monitor.

## Interpretation

- Adaptive did not detect a decline in any seed: all midpoint drops are zero, so its weights are uniform and it is not practically distinct from uniform.
- The sealed test does not reproduce the historical degradation: old-tool joint starts at 0.5222 and rises to 0.5426 (none), 0.5500 (uniform), 0.5463 (adaptive), while the historical A-order audit showed a 5.19pp drop on its own test set.
- Replay shows no reliable benefit: uniform is +0.74pp and adaptive +0.37pp over none in old joint; adaptive is -0.37pp vs uniform on average, driven by one seed (-1.11pp). New-tool joint is 0.9167 in all arms.
- Because adaptive equals uniform when no drops are detected, this is a null-signal pilot, not evidence for or against targeted allocation.
- The next step is monitor validation on the historical-like degradation task types, not a larger replay budget.

V2 shares a persisted prefix per seed. Probe times/tokens above are reference costs of that prefix, not repeated physical executions. Actual experimental time is recorded separately; model loading time is outside these training timers.
