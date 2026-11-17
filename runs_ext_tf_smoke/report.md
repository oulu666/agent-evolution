# Target-fraction sweep (A scenario, 10% budget)

nat = independent natural final, old-family macro joint; fix = File last-match re-scored against the asked-for last line; raw = original Round-2 labels. hist = historical test.

| arm | seeds | nat fix | nat raw | hist old | Calendar | File fix | DB | Py | target frac (actual) | branch s |
|---|---|---|---|---|---|---|---|---|---|---|
| tf00 | 1 | 0.222 | 0.222 | 0.556 | 0.000 | 0.000 | 0.000 | 0.667 | - | 65.759 |
| tf50 | 1 | 0.333 | 0.333 | 0.556 | 0.000 | 0.000 | 0.000 | 1.000 | 0.503 | 7.025 |

## Runs

- seed20261108 tf00: {"target_fraction": 0.0, "actual_target_fraction": null, "replay_input_tokens": 654, "budget_input_tokens": 806, "target_samples_by_family": {}, "duration_seconds": 65.759, "actual_elapsed_seconds": 65.759, "probe_start": {"database": 0.25, "file": 0.0, "python": 0.5}, "probe_mid": {"database": 0.25, "file": 0.0, "python": 0.5}, "replay_positions": 1, "nat_raw_file": 0, "nat_fix_file": 0, "hist_file": 0, "mv2end_file": 0, "nat_raw_database": 0, "nat_fix_database": 0, "hist_database": 0.667, "mv2end_database": 0, "nat_raw_python": 0.667, "nat_fix_python": 0.667, "hist_python": 1, "mv2end_python": 1, "calendar_hist": 0, "nat_raw_old_macro": 0.222, "nat_fix_old_macro": 0.222, "hist_old_macro": 0.556}
- seed20261108 tf50: {"target_fraction": 0.5, "actual_target_fraction": 0.503, "replay_input_tokens": 718, "budget_input_tokens": 806, "target_samples_by_family": {"database": 0, "file": 0, "python": 1}, "duration_seconds": 65.982, "actual_elapsed_seconds": 7.025, "probe_start": {"database": 0.25, "file": 0.0, "python": 0.5}, "probe_mid": {"database": 0.25, "file": 0.0, "python": 0.5}, "replay_positions": 1, "nat_raw_file": 0, "nat_fix_file": 0, "hist_file": 0, "mv2end_file": 0, "nat_raw_database": 0, "nat_fix_database": 0, "hist_database": 0.667, "mv2end_database": 0, "nat_raw_python": 1, "nat_fix_python": 1, "hist_python": 1, "mv2end_python": 1, "calendar_hist": 0, "nat_raw_old_macro": 0.333, "nat_fix_old_macro": 0.333, "hist_old_macro": 0.556}
