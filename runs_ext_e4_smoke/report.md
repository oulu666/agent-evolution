# E4 自动汇总：干净 File 复习池 · A 场景 · 预算 10%

自动生成于 2026-11-11 11:17:42（Asia/Shanghai）。natural final v2 合并哈希 `5dcc7d786fd60556`。
主口径 nat old = 自然语言期末 v2 旧工具宏平均（File 用 v2 官方宽松判分：最后一行原文 / 去掉 `line N: ` 的正文 / {line,text} 且行号对）；strict = File 精确字符串。Calendar nat = 新 Calendar 自然语言期末（30 题）；Calendar hist = 历史模板测试。E2 = 上轮 runs_ext_tf（旧 File 池），Calendar nat 为只读补评。均值±样本标准差，n=种子数。

| 轮 | 臂 | n | nat old | nat old strict | File | DB | Py | Calendar nat | Calendar hist | hist old | 实际定向比例(token) | 实际定向比例(样本) | 独立样本 | 重复 | 复习监督 token |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E4 | tf00 | 1 | 0.333 | 0.333 | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.556 | 0.000 | 0.000 | 2.0 | 0.0 | 103 |
| E4 | tf50 | 1 | 0.333 | 0.333 | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.556 | 0.503 | 0.500 | 2.0 | 0.0 | 119 |

## 每臂定向样本数（按种子 108/109/110）

- E4 tf00: {"file": [0], "database": [0], "python": [0]}
- E4 tf50: {"file": [0], "database": [0], "python": [1]}

## 配对比较（同种子、同题目配对；先按种子求差再平均）

CI 为配对 bootstrap 95% 区间（2000 次）：hier = 种子与题目两级重抽；item = 种子固定、只抽题目。n=3 种子，区间只作描述，不作显著性结论。

| 比较 | 指标 | 均值差 | 种子差 sd | 为正的种子数 | 95% CI (hier) | 95% CI (item) |
|---|---|---|---|---|---|---|
| E4 tf50-tf00 | nat_old_macro | +0.000 | 0.000 | 0/1 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4 tf50-tf00 | nat_old_macro_strict | +0.000 | 0.000 | 0/1 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4 tf50-tf00 | nat_file | +0.000 | 0.000 | 0/1 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4 tf50-tf00 | nat_database | +0.000 | 0.000 | 0/1 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4 tf50-tf00 | nat_python | +0.000 | 0.000 | 0/1 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4 tf50-tf00 | nat_calendar | +0.000 | 0.000 | 0/1 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4 tf50-tf00 | hist_calendar | +0.000 | 0.000 | 0/1 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4 tf50-tf00 | hist_old_macro | +0.000 | 0.000 | 0/1 | [+0.000, +0.000] | [+0.000, +0.000] |

## 均值层面的非支配点（旧工具 nat old × Calendar nat，两者越高越好）

- 全部臂（含 none/tf00）：E4:tf00, E4:tf50
- 仅 E4：E4:tf00, E4:tf50
- 仅 E2：

点：E4:tf00=(0.333, 1.000); E4:tf50=(0.333, 1.000)

## 逐 run 明细

- E4 seed20261108 tf00: {"nat_file": 0, "nat_file_strict": 0, "nat_database": 0, "nat_python": 1, "nat_calendar": 1, "hist_file": 0, "hist_database": 0.667, "hist_python": 1, "hist_calendar": 0, "nat_old_macro": 0.333, "nat_old_macro_strict": 0.333, "hist_old_macro": 0.556, "nominal_target_fraction": 0.0, "actual_target_fraction_tokens": 0.0, "actual_target_fraction_plan": null, "actual_target_fraction_supervised": 0.0, "actual_target_fraction_samples": 0.0, "replay_samples": 2, "replay_unique": 2, "replay_repeats": 0, "replay_input_tokens": 654, "replay_supervised_tokens": 103, "budget_input_tokens": 806, "new_input_tokens": 8060, "new_supervised_tokens": 588, "target_samples_by_family": {"file": 0, "database": 0, "python": 0}, "replay_positions": 1, "actual_elapsed_seconds": 64.278, "duration_seconds": 64.278, "prefix_reused": false, "probe_start": {"database": 0.25, "file": 0.0, "python": 0.5}, "probe_mid": {"database": 0.25, "file": 0.0, "python": 0.5}}
  - by_family: {"file": {"samples": 1, "unique": 1, "repeats": 0, "target_samples": 0, "target_unique": 0, "input_tokens": 307, "supervised_tokens": 46, "target_input_tokens": 0, "target_supervised_tokens": 0}, "database": {"samples": 0, "unique": 0, "repeats": 0, "target_samples": 0, "target_unique": 0, "input_tokens": 0, "supervised_tokens": 0, "target_input_tokens": 0, "target_supervised_tokens": 0}, "python": {"samples": 1, "unique": 1, "repeats": 0, "target_samples": 0, "target_unique": 0, "input_tokens": 347, "supervised_tokens": 57, "target_input_tokens": 0, "target_supervised_tokens": 0}}
  - exposure_by_template: {"file/file_write_report": {"samples": 1, "input_tokens": 307, "supervised_tokens": 46}, "python/stats_median": {"samples": 1, "input_tokens": 347, "supervised_tokens": 57}}
- E4 seed20261108 tf50: {"nat_file": 0, "nat_file_strict": 0, "nat_database": 0, "nat_python": 1, "nat_calendar": 1, "hist_file": 0, "hist_database": 0.667, "hist_python": 1, "hist_calendar": 0, "nat_old_macro": 0.333, "nat_old_macro_strict": 0.333, "hist_old_macro": 0.556, "nominal_target_fraction": 0.5, "actual_target_fraction_tokens": 0.503, "actual_target_fraction_plan": 0.503, "actual_target_fraction_supervised": 0.479, "actual_target_fraction_samples": 0.5, "replay_samples": 2, "replay_unique": 2, "replay_repeats": 0, "replay_input_tokens": 718, "replay_supervised_tokens": 119, "budget_input_tokens": 806, "new_input_tokens": 8060, "new_supervised_tokens": 588, "target_samples_by_family": {"file": 0, "database": 0, "python": 1}, "replay_positions": 1, "actual_elapsed_seconds": 8.299, "duration_seconds": 65.247, "prefix_reused": true, "probe_start": {"database": 0.25, "file": 0.0, "python": 0.5}, "probe_mid": {"database": 0.25, "file": 0.0, "python": 0.5}}
  - by_family: {"file": {"samples": 0, "unique": 0, "repeats": 0, "target_samples": 0, "target_unique": 0, "input_tokens": 0, "supervised_tokens": 0, "target_input_tokens": 0, "target_supervised_tokens": 0}, "database": {"samples": 0, "unique": 0, "repeats": 0, "target_samples": 0, "target_unique": 0, "input_tokens": 0, "supervised_tokens": 0, "target_input_tokens": 0, "target_supervised_tokens": 0}, "python": {"samples": 2, "unique": 2, "repeats": 0, "target_samples": 1, "target_unique": 1, "input_tokens": 718, "supervised_tokens": 119, "target_input_tokens": 361, "target_supervised_tokens": 57}}
  - exposure_by_template: {"python/stats_mean": {"samples": 1, "input_tokens": 357, "supervised_tokens": 62}, "python/target_median_natural": {"samples": 1, "input_tokens": 361, "supervised_tokens": 57}}
