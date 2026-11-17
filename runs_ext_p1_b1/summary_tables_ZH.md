# P1 自动汇总表（Protocol-B1）

生成：2026-11-13 17:09:50 +0800（Asia/Shanghai）。由 `fac_tinyagent/p1_run.py --phase summarize` 自动生成，数字只来自 results.jsonl。

## 1. 各 checkpoint 总分（Joint Success；natv2_file 为官方 v2 宽松规则）

| checkpoint | natv2_database | natv2_file | natv2_python | db_nontarget | calendar_v3 | p2_file | p2_python | p2_database | v3fix 工具/条件计数/联合 |
|---|---|---|---|---|---|---|---|---|---|
| A_seed20261108_b20_tf50 | 1.000 | 0.800 | 1.000 | 0.200 | 0.407 | 0.600 | 1.000 | 0.700 | 0.500 / 0.600 / 0.300 |
| A_seed20261108_ctrl_cal10 | 0.000 | 0.000 | 0.433 | 0.675 | 0.520 | 0.467 | 0.900 | 0.400 | 0.500 / 0.533 / 0.267 |
| A_seed20261108_ctrl_cal20 | 0.000 | 0.033 | 0.233 | 0.700 | 0.507 | 0.467 | 0.933 | 0.367 | 0.500 / 0.600 / 0.300 |
| A_seed20261108_dose_db0 | 0.000 | 0.133 | 0.933 | 0.700 | 0.527 | 0.533 | 0.967 | 0.400 | 0.500 / 0.600 / 0.300 |
| A_seed20261108_dose_db1 | 0.033 | 0.333 | 0.933 | 0.650 | 0.493 | 0.567 | 0.967 | 0.567 | 0.500 / 0.600 / 0.300 |
| A_seed20261108_dose_db2 | 0.267 | — | — | 0.450 | — | — | — | — | — |
| A_seed20261108_dose_db3 | 0.533 | — | — | 0.525 | — | — | — | — | — |
| A_seed20261108_dose_db4 | 0.800 | — | — | 0.675 | — | — | — | — | — |
| A_seed20261108_dose_db6 | 1.000 | 0.533 | 0.967 | 0.625 | 0.480 | 0.467 | 1.000 | 0.433 | 0.500 / 0.600 / 0.300 |
| A_seed20261108_e3b2_A_target_dbbg | 0.100 | 0.000 | 0.867 | 0.700 | 0.507 | 0.467 | 0.967 | 0.367 | 0.500 / 0.533 / 0.267 |
| A_seed20261108_e3b2_A_target_other | 0.100 | 0.000 | 0.700 | 0.700 | 0.500 | 0.467 | 0.933 | 0.367 | 0.500 / 0.600 / 0.300 |
| A_seed20261108_none | 0.000 | 0.000 | 0.467 | 0.700 | 0.533 | 0.467 | 0.900 | 0.400 | 0.500 / 0.533 / 0.267 |
| A_seed20261108_stage_02_database | 0.000 | 0.000 | 0.967 | 0.250 | 0.167 | 0.600 | 0.667 | 0.567 | 0.000 / — / 0.000 |
| A_seed20261108_stage_03_python | 0.000 | 0.167 | 0.967 | 0.425 | 0.193 | 0.467 | 1.000 | 0.367 | 0.000 / — / 0.000 |
| A_seed20261108_stage_04_calendar | 0.000 | 0.000 | 0.500 | 0.700 | 0.480 | 0.467 | 0.933 | 0.400 | 0.500 / 0.733 / 0.367 |
| A_seed20261108_tf00 | 0.000 | 0.533 | 0.233 | — | — | 0.533 | 0.900 | 0.567 | — |
| A_seed20261108_tf25 | 0.400 | 0.633 | 1.000 | 0.675 | 0.487 | 0.567 | 0.967 | 0.433 | 0.500 / 0.600 / 0.300 |
| A_seed20261108_tf50 | 1.000 | 0.800 | 0.933 | 0.575 | 0.473 | 0.600 | 0.967 | 0.633 | 0.500 / 0.600 / 0.300 |
| A_seed20261109_b20_tf50 | 1.000 | 0.867 | 1.000 | 0.725 | 0.413 | 0.700 | 0.867 | 0.700 | 0.500 / 0.667 / 0.333 |
| A_seed20261109_ctrl_cal10 | 0.000 | 0.433 | 1.000 | 0.700 | 0.513 | 0.500 | 0.833 | 0.433 | 0.500 / 0.600 / 0.300 |
| A_seed20261109_ctrl_cal20 | 0.000 | 0.467 | 1.000 | 0.725 | 0.507 | 0.500 | 0.833 | 0.433 | 0.500 / 0.600 / 0.300 |
| A_seed20261109_dose_db0 | 0.067 | 0.767 | 1.000 | 0.750 | 0.520 | 0.533 | 0.833 | 0.433 | 0.500 / 0.600 / 0.300 |
| A_seed20261109_dose_db1 | 0.267 | 0.733 | 1.000 | 0.750 | 0.487 | 0.533 | 0.833 | 0.433 | 0.500 / 0.600 / 0.300 |
| A_seed20261109_dose_db2 | 0.733 | — | — | 0.750 | — | — | — | — | — |
| A_seed20261109_dose_db3 | 0.933 | — | — | 0.750 | — | — | — | — | — |
| A_seed20261109_dose_db4 | 0.933 | — | — | 0.750 | — | — | — | — | — |
| A_seed20261109_dose_db6 | 1.000 | 0.767 | 1.000 | 0.750 | 0.500 | 0.533 | 0.833 | 0.467 | 0.500 / 0.667 / 0.333 |
| A_seed20261109_e3b2_A_target_dbbg | 0.233 | 0.500 | 1.000 | 0.700 | 0.500 | 0.500 | 0.867 | 0.667 | 0.500 / 0.667 / 0.333 |
| A_seed20261109_e3b2_A_target_other | 0.200 | 0.500 | 1.000 | 0.750 | 0.500 | 0.500 | 0.833 | 0.433 | 0.500 / 0.600 / 0.300 |
| A_seed20261109_none | 0.000 | 0.433 | 1.000 | 0.750 | 0.507 | 0.500 | 0.833 | 0.433 | 0.500 / 0.600 / 0.300 |
| A_seed20261109_stage_02_database | 0.000 | 0.000 | 0.633 | 0.525 | 0.173 | 0.533 | 0.833 | 0.633 | 0.000 / — / 0.000 |
| A_seed20261109_stage_03_python | 0.000 | 0.167 | 0.933 | 0.650 | 0.160 | 0.467 | 1.000 | 0.467 | 0.000 / — / 0.000 |
| A_seed20261109_stage_04_calendar | 0.000 | 0.767 | 1.000 | 0.775 | 0.427 | 0.500 | 0.867 | 0.433 | 0.333 / 0.800 / 0.267 |
| A_seed20261109_tf00 | 0.100 | 0.867 | 1.000 | — | — | 0.700 | 0.867 | 0.633 | — |
| A_seed20261109_tf25 | 0.667 | 0.700 | 1.000 | 0.700 | 0.527 | 0.533 | 0.833 | 0.633 | 0.500 / 0.600 / 0.300 |
| A_seed20261109_tf50 | 1.000 | 0.800 | 1.000 | 0.750 | 0.480 | 0.600 | 0.833 | 0.667 | 0.500 / 0.600 / 0.300 |
| A_seed20261110_b20_tf50 | 0.933 | 0.800 | 0.867 | 0.700 | 0.500 | 0.667 | 0.833 | 0.400 | 0.467 / 0.786 / 0.367 |
| A_seed20261110_ctrl_cal10 | 0.000 | 0.633 | 0.767 | 0.575 | 0.573 | 0.567 | 0.933 | 0.367 | 0.500 / 0.667 / 0.333 |
| A_seed20261110_ctrl_cal20 | 0.000 | 0.700 | 0.767 | 0.600 | 0.580 | 0.600 | 0.933 | 0.367 | 0.500 / 0.600 / 0.300 |
| A_seed20261110_dose_db0 | 0.000 | 0.767 | 0.933 | 0.700 | 0.573 | 0.533 | 0.933 | 0.567 | 0.500 / 0.733 / 0.367 |
| A_seed20261110_dose_db1 | 0.000 | 0.733 | 1.000 | 0.600 | 0.567 | 0.533 | 0.933 | 0.567 | 0.500 / 0.733 / 0.367 |
| A_seed20261110_dose_db2 | 0.200 | — | — | 0.725 | — | — | — | — | — |
| A_seed20261110_dose_db3 | 0.267 | — | — | 0.725 | — | — | — | — | — |
| A_seed20261110_dose_db4 | 0.667 | — | — | 0.700 | — | — | — | — | — |
| A_seed20261110_dose_db6 | 1.000 | 0.767 | 1.000 | 0.700 | 0.540 | 0.567 | 0.933 | 0.467 | 0.500 / 0.800 / 0.400 |
| A_seed20261110_e3b2_A_target_dbbg | 0.000 | 0.667 | 0.833 | 0.375 | 0.573 | 0.533 | 0.867 | 0.567 | 0.500 / 0.667 / 0.333 |
| A_seed20261110_e3b2_A_target_other | 0.067 | 0.767 | 0.767 | 0.725 | 0.560 | 0.533 | 0.900 | 0.367 | 0.500 / 0.667 / 0.333 |
| A_seed20261110_none | 0.000 | 0.733 | 0.800 | 0.675 | 0.567 | 0.567 | 0.933 | 0.367 | 0.500 / 0.600 / 0.300 |
| A_seed20261110_stage_02_database | 0.000 | 0.000 | 1.000 | 0.575 | 0.160 | 0.533 | 0.900 | 0.633 | 0.000 / — / 0.000 |
| A_seed20261110_stage_03_python | 0.000 | 0.500 | 1.000 | 0.600 | 0.147 | 0.567 | 1.000 | 0.400 | 0.000 / — / 0.000 |
| A_seed20261110_stage_04_calendar | 0.000 | 0.800 | 0.933 | 0.725 | 0.460 | 0.467 | 0.967 | 0.367 | 0.500 / 0.400 / 0.200 |
| A_seed20261110_tf00 | 0.000 | 0.767 | 0.800 | — | — | 0.567 | 1.000 | 0.367 | — |
| A_seed20261110_tf25 | 0.233 | 0.767 | 1.000 | 0.700 | 0.600 | 0.600 | 1.000 | 0.300 | 0.500 / 0.733 / 0.367 |
| A_seed20261110_tf50 | 0.967 | 0.767 | 1.000 | 0.650 | 0.580 | 0.600 | 1.000 | 0.333 | 0.500 / 0.667 / 0.333 |

## 2. 非 target 五模式与 Calendar v3 五模式

| checkpoint | db_nontarget 各模式 | calendar_v3 各类型 |
|---|---|---|
| A_seed20261108_b20_tf50 | db.filter_cmp_avg 0.125, db.filter_cmp_count 0.375, db.filter_cmp_group_count 0.125, db.min_max 0.250, db.multi_filter_count 0.125 | attendee_count 0.800, free_latest 0.267, last_end 0.300, locations 0.233, search_count 0.433 |
| A_seed20261108_ctrl_cal10 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.250, db.min_max 0.625, db.multi_filter_count 0.750 | attendee_count 0.833, free_latest 0.433, last_end 0.533, locations 0.367, search_count 0.433 |
| A_seed20261108_ctrl_cal20 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.250, db.min_max 0.750, db.multi_filter_count 0.750 | attendee_count 0.833, free_latest 0.400, last_end 0.500, locations 0.367, search_count 0.433 |
| A_seed20261108_dose_db0 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.250, db.min_max 0.750, db.multi_filter_count 0.750 | attendee_count 0.833, free_latest 0.467, last_end 0.567, locations 0.333, search_count 0.433 |
| A_seed20261108_dose_db1 | db.filter_cmp_avg 0.625, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.250, db.min_max 0.750, db.multi_filter_count 0.625 | attendee_count 0.767, free_latest 0.433, last_end 0.633, locations 0.200, search_count 0.433 |
| A_seed20261108_dose_db2 | db.filter_cmp_avg 0.375, db.filter_cmp_count 0.750, db.filter_cmp_group_count 0.250, db.min_max 0.375, db.multi_filter_count 0.500 | — |
| A_seed20261108_dose_db3 | db.filter_cmp_avg 0.500, db.filter_cmp_count 0.875, db.filter_cmp_group_count 0.250, db.min_max 0.500, db.multi_filter_count 0.500 | — |
| A_seed20261108_dose_db4 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.250, db.min_max 0.625, db.multi_filter_count 0.750 | — |
| A_seed20261108_dose_db6 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 0.625, db.multi_filter_count 0.750 | attendee_count 0.833, free_latest 0.333, last_end 0.500, locations 0.300, search_count 0.433 |
| A_seed20261108_e3b2_A_target_dbbg | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.250, db.min_max 0.750, db.multi_filter_count 0.750 | attendee_count 0.800, free_latest 0.367, last_end 0.567, locations 0.367, search_count 0.433 |
| A_seed20261108_e3b2_A_target_other | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.250, db.min_max 0.750, db.multi_filter_count 0.750 | attendee_count 0.800, free_latest 0.400, last_end 0.500, locations 0.367, search_count 0.433 |
| A_seed20261108_none | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.250, db.min_max 0.750, db.multi_filter_count 0.750 | attendee_count 0.800, free_latest 0.467, last_end 0.600, locations 0.367, search_count 0.433 |
| A_seed20261108_stage_02_database | db.filter_cmp_avg 0.750, db.filter_cmp_count 0.125, db.filter_cmp_group_count 0.000, db.min_max 0.375, db.multi_filter_count 0.000 | attendee_count 0.533, free_latest 0.067, last_end 0.000, locations 0.000, search_count 0.233 |
| A_seed20261108_stage_03_python | db.filter_cmp_avg 0.750, db.filter_cmp_count 0.625, db.filter_cmp_group_count 0.000, db.min_max 0.375, db.multi_filter_count 0.375 | attendee_count 0.767, free_latest 0.033, last_end 0.000, locations 0.000, search_count 0.167 |
| A_seed20261108_stage_04_calendar | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.250, db.min_max 0.750, db.multi_filter_count 0.750 | attendee_count 0.800, free_latest 0.533, last_end 0.367, locations 0.333, search_count 0.367 |
| A_seed20261108_tf00 | — | — |
| A_seed20261108_tf25 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.250, db.min_max 0.750, db.multi_filter_count 0.625 | attendee_count 0.833, free_latest 0.333, last_end 0.500, locations 0.333, search_count 0.433 |
| A_seed20261108_tf50 | db.filter_cmp_avg 0.500, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.250, db.min_max 0.500, db.multi_filter_count 0.625 | attendee_count 0.833, free_latest 0.367, last_end 0.400, locations 0.333, search_count 0.433 |
| A_seed20261109_b20_tf50 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 0.875 | attendee_count 0.767, free_latest 0.500, last_end 0.267, locations 0.267, search_count 0.267 |
| A_seed20261109_ctrl_cal10 | db.filter_cmp_avg 0.750, db.filter_cmp_count 0.750, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 1.000 | attendee_count 0.867, free_latest 0.633, last_end 0.433, locations 0.333, search_count 0.300 |
| A_seed20261109_ctrl_cal20 | db.filter_cmp_avg 0.750, db.filter_cmp_count 0.875, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 1.000 | attendee_count 0.867, free_latest 0.633, last_end 0.467, locations 0.267, search_count 0.300 |
| A_seed20261109_dose_db0 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 1.000 | attendee_count 0.800, free_latest 0.633, last_end 0.533, locations 0.333, search_count 0.300 |
| A_seed20261109_dose_db1 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 1.000 | attendee_count 0.767, free_latest 0.600, last_end 0.500, locations 0.267, search_count 0.300 |
| A_seed20261109_dose_db2 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 1.000 | — |
| A_seed20261109_dose_db3 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 1.000 | — |
| A_seed20261109_dose_db4 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 1.000 | — |
| A_seed20261109_dose_db6 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 1.000 | attendee_count 0.767, free_latest 0.600, last_end 0.500, locations 0.333, search_count 0.300 |
| A_seed20261109_e3b2_A_target_dbbg | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 0.750 | attendee_count 0.733, free_latest 0.667, last_end 0.433, locations 0.367, search_count 0.300 |
| A_seed20261109_e3b2_A_target_other | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 1.000 | attendee_count 0.767, free_latest 0.633, last_end 0.500, locations 0.300, search_count 0.300 |
| A_seed20261109_none | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 1.000 | attendee_count 0.800, free_latest 0.633, last_end 0.467, locations 0.333, search_count 0.300 |
| A_seed20261109_stage_02_database | db.filter_cmp_avg 0.750, db.filter_cmp_count 0.500, db.filter_cmp_group_count 0.125, db.min_max 0.625, db.multi_filter_count 0.625 | attendee_count 0.667, free_latest 0.033, last_end 0.000, locations 0.000, search_count 0.167 |
| A_seed20261109_stage_03_python | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 0.750, db.multi_filter_count 0.750 | attendee_count 0.633, free_latest 0.033, last_end 0.000, locations 0.000, search_count 0.133 |
| A_seed20261109_stage_04_calendar | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.125, db.min_max 1.000, db.multi_filter_count 1.000 | attendee_count 0.933, free_latest 0.500, last_end 0.100, locations 0.300, search_count 0.300 |
| A_seed20261109_tf00 | — | — |
| A_seed20261109_tf25 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 0.750 | attendee_count 0.800, free_latest 0.633, last_end 0.533, locations 0.367, search_count 0.300 |
| A_seed20261109_tf50 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 1.000 | attendee_count 0.867, free_latest 0.600, last_end 0.333, locations 0.300, search_count 0.300 |
| A_seed20261110_b20_tf50 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 0.750 | attendee_count 0.833, free_latest 0.600, last_end 0.300, locations 0.333, search_count 0.433 |
| A_seed20261110_ctrl_cal10 | db.filter_cmp_avg 0.750, db.filter_cmp_count 0.500, db.filter_cmp_group_count 0.000, db.min_max 0.875, db.multi_filter_count 0.750 | attendee_count 0.900, free_latest 0.733, last_end 0.500, locations 0.300, search_count 0.433 |
| A_seed20261110_ctrl_cal20 | db.filter_cmp_avg 0.750, db.filter_cmp_count 0.625, db.filter_cmp_group_count 0.000, db.min_max 0.875, db.multi_filter_count 0.750 | attendee_count 0.900, free_latest 0.767, last_end 0.500, locations 0.300, search_count 0.433 |
| A_seed20261110_dose_db0 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 0.750 | attendee_count 0.867, free_latest 0.733, last_end 0.500, locations 0.333, search_count 0.433 |
| A_seed20261110_dose_db1 | db.filter_cmp_avg 0.750, db.filter_cmp_count 0.500, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 0.750 | attendee_count 0.767, free_latest 0.767, last_end 0.500, locations 0.367, search_count 0.433 |
| A_seed20261110_dose_db2 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 0.875 | — |
| A_seed20261110_dose_db3 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 0.875 | — |
| A_seed20261110_dose_db4 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 0.750 | — |
| A_seed20261110_dose_db6 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 0.750 | attendee_count 0.833, free_latest 0.633, last_end 0.500, locations 0.300, search_count 0.433 |
| A_seed20261110_e3b2_A_target_dbbg | db.filter_cmp_avg 0.750, db.filter_cmp_count 0.125, db.filter_cmp_group_count 0.000, db.min_max 0.750, db.multi_filter_count 0.250 | attendee_count 0.867, free_latest 0.767, last_end 0.500, locations 0.300, search_count 0.433 |
| A_seed20261110_e3b2_A_target_other | db.filter_cmp_avg 0.750, db.filter_cmp_count 0.875, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 1.000 | attendee_count 0.867, free_latest 0.733, last_end 0.467, locations 0.300, search_count 0.433 |
| A_seed20261110_none | db.filter_cmp_avg 0.750, db.filter_cmp_count 0.750, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 0.875 | attendee_count 0.867, free_latest 0.767, last_end 0.500, locations 0.267, search_count 0.433 |
| A_seed20261110_stage_02_database | db.filter_cmp_avg 0.875, db.filter_cmp_count 0.625, db.filter_cmp_group_count 0.000, db.min_max 0.750, db.multi_filter_count 0.625 | attendee_count 0.533, free_latest 0.033, last_end 0.000, locations 0.000, search_count 0.233 |
| A_seed20261110_stage_03_python | db.filter_cmp_avg 0.750, db.filter_cmp_count 0.625, db.filter_cmp_group_count 0.000, db.min_max 0.875, db.multi_filter_count 0.750 | attendee_count 0.667, free_latest 0.033, last_end 0.000, locations 0.000, search_count 0.033 |
| A_seed20261110_stage_04_calendar | db.filter_cmp_avg 0.625, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 1.000 | attendee_count 0.833, free_latest 0.667, last_end 0.100, locations 0.367, search_count 0.333 |
| A_seed20261110_tf00 | — | — |
| A_seed20261110_tf25 | db.filter_cmp_avg 0.750, db.filter_cmp_count 1.000, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 0.750 | attendee_count 0.900, free_latest 0.733, last_end 0.567, locations 0.367, search_count 0.433 |
| A_seed20261110_tf50 | db.filter_cmp_avg 0.750, db.filter_cmp_count 0.750, db.filter_cmp_group_count 0.000, db.min_max 1.000, db.multi_filter_count 0.750 | attendee_count 0.900, free_latest 0.700, last_end 0.500, locations 0.367, search_count 0.433 |

## 3. 协议桥接：同一 checkpoint、同一题集，B1 − 历史 B32

| checkpoint | suite | B32 | B1 | 差 | B32错→B1对 | B32对→B1错 |
|---|---|---|---|---|---|---|
| A_seed20261108_b20_tf50 | natv2_database | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261108_b20_tf50 | natv2_file | 0.867 | 0.800 | -0.067 | 0 | 2 |
| A_seed20261108_b20_tf50 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261108_b20_tf50 | calendar_v3 | 0.413 | 0.407 | -0.007 | 2 | 3 |
| A_seed20261108_b20_tf50 | p2_file | 0.600 | 0.600 | +0.000 | 0 | 0 |
| A_seed20261108_b20_tf50 | p2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261108_b20_tf50 | p2_database | 0.700 | 0.700 | +0.000 | 0 | 0 |
| A_seed20261108_ctrl_cal10 | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261108_ctrl_cal10 | natv2_file | 0.067 | 0.000 | -0.067 | 0 | 2 |
| A_seed20261108_ctrl_cal10 | natv2_python | 0.200 | 0.433 | +0.233 | 7 | 0 |
| A_seed20261108_ctrl_cal10 | calendar_v3 | 0.527 | 0.520 | -0.007 | 1 | 2 |
| A_seed20261108_ctrl_cal10 | p2_file | 0.467 | 0.467 | +0.000 | 0 | 0 |
| A_seed20261108_ctrl_cal10 | p2_python | 0.900 | 0.900 | +0.000 | 0 | 0 |
| A_seed20261108_ctrl_cal10 | p2_database | 0.400 | 0.400 | +0.000 | 0 | 0 |
| A_seed20261108_ctrl_cal20 | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261108_ctrl_cal20 | natv2_file | 0.133 | 0.033 | -0.100 | 0 | 3 |
| A_seed20261108_ctrl_cal20 | natv2_python | 0.400 | 0.233 | -0.167 | 0 | 5 |
| A_seed20261108_ctrl_cal20 | calendar_v3 | 0.500 | 0.507 | +0.007 | 1 | 0 |
| A_seed20261108_ctrl_cal20 | p2_file | 0.467 | 0.467 | +0.000 | 0 | 0 |
| A_seed20261108_ctrl_cal20 | p2_python | 0.900 | 0.933 | +0.033 | 2 | 1 |
| A_seed20261108_ctrl_cal20 | p2_database | 0.400 | 0.367 | -0.033 | 0 | 1 |
| A_seed20261108_dose_db0 | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261108_dose_db0 | natv2_file | 0.267 | 0.133 | -0.133 | 0 | 4 |
| A_seed20261108_dose_db0 | natv2_python | 0.933 | 0.933 | +0.000 | 0 | 0 |
| A_seed20261108_dose_db0 | calendar_v3 | 0.533 | 0.527 | -0.007 | 3 | 4 |
| A_seed20261108_dose_db0 | p2_file | 0.533 | 0.533 | +0.000 | 0 | 0 |
| A_seed20261108_dose_db0 | p2_python | 0.900 | 0.967 | +0.067 | 2 | 0 |
| A_seed20261108_dose_db0 | p2_database | 0.400 | 0.400 | +0.000 | 0 | 0 |
| A_seed20261108_dose_db1 | natv2_database | 0.033 | 0.033 | +0.000 | 0 | 0 |
| A_seed20261108_dose_db1 | natv2_file | 0.467 | 0.333 | -0.133 | 2 | 6 |
| A_seed20261108_dose_db1 | natv2_python | 0.933 | 0.933 | +0.000 | 0 | 0 |
| A_seed20261108_dose_db1 | calendar_v3 | 0.493 | 0.493 | +0.000 | 4 | 4 |
| A_seed20261108_dose_db1 | p2_file | 0.567 | 0.567 | +0.000 | 0 | 0 |
| A_seed20261108_dose_db1 | p2_python | 0.967 | 0.967 | +0.000 | 0 | 0 |
| A_seed20261108_dose_db1 | p2_database | 0.567 | 0.567 | +0.000 | 0 | 0 |
| A_seed20261108_dose_db2 | natv2_database | 0.333 | 0.267 | -0.067 | 1 | 3 |
| A_seed20261108_dose_db3 | natv2_database | 0.567 | 0.533 | -0.033 | 1 | 2 |
| A_seed20261108_dose_db4 | natv2_database | 0.867 | 0.800 | -0.067 | 1 | 3 |
| A_seed20261108_dose_db6 | natv2_database | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261108_dose_db6 | natv2_file | 0.500 | 0.533 | +0.033 | 2 | 1 |
| A_seed20261108_dose_db6 | natv2_python | 0.967 | 0.967 | +0.000 | 0 | 0 |
| A_seed20261108_dose_db6 | calendar_v3 | 0.500 | 0.480 | -0.020 | 0 | 3 |
| A_seed20261108_dose_db6 | p2_file | 0.467 | 0.467 | +0.000 | 0 | 0 |
| A_seed20261108_dose_db6 | p2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261108_dose_db6 | p2_database | 0.467 | 0.433 | -0.033 | 0 | 1 |
| A_seed20261108_none | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261108_none | natv2_file | 0.033 | 0.000 | -0.033 | 0 | 1 |
| A_seed20261108_none | natv2_python | 0.600 | 0.467 | -0.133 | 0 | 4 |
| A_seed20261108_none | calendar_v3 | 0.540 | 0.533 | -0.007 | 4 | 5 |
| A_seed20261108_none | p2_file | 0.467 | 0.467 | +0.000 | 0 | 0 |
| A_seed20261108_none | p2_python | 0.967 | 0.900 | -0.067 | 0 | 2 |
| A_seed20261108_none | p2_database | 0.400 | 0.400 | +0.000 | 0 | 0 |
| A_seed20261108_stage_03_python | calendar_v3 | 0.180 | 0.193 | +0.013 | 2 | 0 |
| A_seed20261108_tf00 | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261108_tf00 | natv2_file | 0.500 | 0.533 | +0.033 | 2 | 1 |
| A_seed20261108_tf00 | natv2_python | 0.233 | 0.233 | +0.000 | 4 | 4 |
| A_seed20261108_tf00 | p2_file | 0.500 | 0.533 | +0.033 | 1 | 0 |
| A_seed20261108_tf00 | p2_python | 0.867 | 0.900 | +0.033 | 1 | 0 |
| A_seed20261108_tf00 | p2_database | 0.567 | 0.567 | +0.000 | 0 | 0 |
| A_seed20261108_tf25 | natv2_database | 0.433 | 0.400 | -0.033 | 1 | 2 |
| A_seed20261108_tf25 | natv2_file | 0.733 | 0.633 | -0.100 | 0 | 3 |
| A_seed20261108_tf25 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261108_tf25 | calendar_v3 | 0.480 | 0.487 | +0.007 | 3 | 2 |
| A_seed20261108_tf25 | p2_file | 0.567 | 0.567 | +0.000 | 0 | 0 |
| A_seed20261108_tf25 | p2_python | 1.000 | 0.967 | -0.033 | 0 | 1 |
| A_seed20261108_tf25 | p2_database | 0.433 | 0.433 | +0.000 | 0 | 0 |
| A_seed20261108_tf50 | natv2_database | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261108_tf50 | natv2_file | 0.800 | 0.800 | +0.000 | 0 | 0 |
| A_seed20261108_tf50 | natv2_python | 0.933 | 0.933 | +0.000 | 0 | 0 |
| A_seed20261108_tf50 | calendar_v3 | 0.493 | 0.473 | -0.020 | 1 | 4 |
| A_seed20261108_tf50 | p2_file | 0.600 | 0.600 | +0.000 | 0 | 0 |
| A_seed20261108_tf50 | p2_python | 0.933 | 0.967 | +0.033 | 1 | 0 |
| A_seed20261108_tf50 | p2_database | 0.433 | 0.633 | +0.200 | 6 | 0 |
| A_seed20261109_b20_tf50 | natv2_database | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261109_b20_tf50 | natv2_file | 0.867 | 0.867 | +0.000 | 0 | 0 |
| A_seed20261109_b20_tf50 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261109_b20_tf50 | calendar_v3 | 0.440 | 0.413 | -0.027 | 1 | 5 |
| A_seed20261109_b20_tf50 | p2_file | 0.667 | 0.700 | +0.033 | 1 | 0 |
| A_seed20261109_b20_tf50 | p2_python | 0.867 | 0.867 | +0.000 | 1 | 1 |
| A_seed20261109_b20_tf50 | p2_database | 0.733 | 0.700 | -0.033 | 0 | 1 |
| A_seed20261109_ctrl_cal10 | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261109_ctrl_cal10 | natv2_file | 0.333 | 0.433 | +0.100 | 3 | 0 |
| A_seed20261109_ctrl_cal10 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261109_ctrl_cal10 | calendar_v3 | 0.520 | 0.513 | -0.007 | 2 | 3 |
| A_seed20261109_ctrl_cal10 | p2_file | 0.500 | 0.500 | +0.000 | 0 | 0 |
| A_seed20261109_ctrl_cal10 | p2_python | 0.833 | 0.833 | +0.000 | 0 | 0 |
| A_seed20261109_ctrl_cal10 | p2_database | 0.433 | 0.433 | +0.000 | 0 | 0 |
| A_seed20261109_ctrl_cal20 | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261109_ctrl_cal20 | natv2_file | 0.500 | 0.467 | -0.033 | 0 | 1 |
| A_seed20261109_ctrl_cal20 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261109_ctrl_cal20 | calendar_v3 | 0.500 | 0.507 | +0.007 | 1 | 0 |
| A_seed20261109_ctrl_cal20 | p2_file | 0.500 | 0.500 | +0.000 | 0 | 0 |
| A_seed20261109_ctrl_cal20 | p2_python | 0.833 | 0.833 | +0.000 | 0 | 0 |
| A_seed20261109_ctrl_cal20 | p2_database | 0.433 | 0.433 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db0 | natv2_database | 0.000 | 0.067 | +0.067 | 2 | 0 |
| A_seed20261109_dose_db0 | natv2_file | 0.733 | 0.767 | +0.033 | 1 | 0 |
| A_seed20261109_dose_db0 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db0 | calendar_v3 | 0.507 | 0.520 | +0.013 | 3 | 1 |
| A_seed20261109_dose_db0 | p2_file | 0.533 | 0.533 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db0 | p2_python | 0.833 | 0.833 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db0 | p2_database | 0.433 | 0.433 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db1 | natv2_database | 0.267 | 0.267 | +0.000 | 1 | 1 |
| A_seed20261109_dose_db1 | natv2_file | 0.733 | 0.733 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db1 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db1 | calendar_v3 | 0.507 | 0.487 | -0.020 | 3 | 6 |
| A_seed20261109_dose_db1 | p2_file | 0.533 | 0.533 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db1 | p2_python | 0.833 | 0.833 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db1 | p2_database | 0.433 | 0.433 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db2 | natv2_database | 0.633 | 0.733 | +0.100 | 4 | 1 |
| A_seed20261109_dose_db3 | natv2_database | 0.933 | 0.933 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db4 | natv2_database | 0.933 | 0.933 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db6 | natv2_database | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db6 | natv2_file | 0.733 | 0.767 | +0.033 | 1 | 0 |
| A_seed20261109_dose_db6 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db6 | calendar_v3 | 0.507 | 0.500 | -0.007 | 1 | 2 |
| A_seed20261109_dose_db6 | p2_file | 0.533 | 0.533 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db6 | p2_python | 0.833 | 0.833 | +0.000 | 0 | 0 |
| A_seed20261109_dose_db6 | p2_database | 0.467 | 0.467 | +0.000 | 0 | 0 |
| A_seed20261109_none | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261109_none | natv2_file | 0.367 | 0.433 | +0.067 | 2 | 0 |
| A_seed20261109_none | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261109_none | calendar_v3 | 0.513 | 0.507 | -0.007 | 2 | 3 |
| A_seed20261109_none | p2_file | 0.500 | 0.500 | +0.000 | 0 | 0 |
| A_seed20261109_none | p2_python | 0.833 | 0.833 | +0.000 | 0 | 0 |
| A_seed20261109_none | p2_database | 0.467 | 0.433 | -0.033 | 0 | 1 |
| A_seed20261109_stage_03_python | calendar_v3 | 0.160 | 0.160 | +0.000 | 1 | 1 |
| A_seed20261109_tf00 | natv2_database | 0.067 | 0.100 | +0.033 | 1 | 0 |
| A_seed20261109_tf00 | natv2_file | 0.900 | 0.867 | -0.033 | 0 | 1 |
| A_seed20261109_tf00 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261109_tf00 | p2_file | 0.667 | 0.700 | +0.033 | 1 | 0 |
| A_seed20261109_tf00 | p2_python | 0.867 | 0.867 | +0.000 | 0 | 0 |
| A_seed20261109_tf00 | p2_database | 0.633 | 0.633 | +0.000 | 0 | 0 |
| A_seed20261109_tf25 | natv2_database | 0.733 | 0.667 | -0.067 | 0 | 2 |
| A_seed20261109_tf25 | natv2_file | 0.633 | 0.700 | +0.067 | 2 | 0 |
| A_seed20261109_tf25 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261109_tf25 | calendar_v3 | 0.507 | 0.527 | +0.020 | 4 | 1 |
| A_seed20261109_tf25 | p2_file | 0.500 | 0.533 | +0.033 | 1 | 0 |
| A_seed20261109_tf25 | p2_python | 0.833 | 0.833 | +0.000 | 0 | 0 |
| A_seed20261109_tf25 | p2_database | 0.633 | 0.633 | +0.000 | 0 | 0 |
| A_seed20261109_tf50 | natv2_database | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261109_tf50 | natv2_file | 0.800 | 0.800 | +0.000 | 0 | 0 |
| A_seed20261109_tf50 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261109_tf50 | calendar_v3 | 0.473 | 0.480 | +0.007 | 3 | 2 |
| A_seed20261109_tf50 | p2_file | 0.600 | 0.600 | +0.000 | 0 | 0 |
| A_seed20261109_tf50 | p2_python | 0.833 | 0.833 | +0.000 | 0 | 0 |
| A_seed20261109_tf50 | p2_database | 0.667 | 0.667 | +0.000 | 0 | 0 |
| A_seed20261110_b20_tf50 | natv2_database | 1.000 | 0.933 | -0.067 | 0 | 2 |
| A_seed20261110_b20_tf50 | natv2_file | 0.833 | 0.800 | -0.033 | 0 | 1 |
| A_seed20261110_b20_tf50 | natv2_python | 0.833 | 0.867 | +0.033 | 1 | 0 |
| A_seed20261110_b20_tf50 | calendar_v3 | 0.513 | 0.500 | -0.013 | 3 | 5 |
| A_seed20261110_b20_tf50 | p2_file | 0.667 | 0.667 | +0.000 | 0 | 0 |
| A_seed20261110_b20_tf50 | p2_python | 0.833 | 0.833 | +0.000 | 0 | 0 |
| A_seed20261110_b20_tf50 | p2_database | 0.400 | 0.400 | +0.000 | 0 | 0 |
| A_seed20261110_ctrl_cal10 | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261110_ctrl_cal10 | natv2_file | 0.767 | 0.633 | -0.133 | 0 | 4 |
| A_seed20261110_ctrl_cal10 | natv2_python | 0.767 | 0.767 | +0.000 | 1 | 1 |
| A_seed20261110_ctrl_cal10 | calendar_v3 | 0.573 | 0.573 | +0.000 | 0 | 0 |
| A_seed20261110_ctrl_cal10 | p2_file | 0.633 | 0.567 | -0.067 | 0 | 2 |
| A_seed20261110_ctrl_cal10 | p2_python | 0.933 | 0.933 | +0.000 | 0 | 0 |
| A_seed20261110_ctrl_cal10 | p2_database | 0.367 | 0.367 | +0.000 | 0 | 0 |
| A_seed20261110_ctrl_cal20 | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261110_ctrl_cal20 | natv2_file | 0.700 | 0.700 | +0.000 | 1 | 1 |
| A_seed20261110_ctrl_cal20 | natv2_python | 0.767 | 0.767 | +0.000 | 0 | 0 |
| A_seed20261110_ctrl_cal20 | calendar_v3 | 0.573 | 0.580 | +0.007 | 1 | 0 |
| A_seed20261110_ctrl_cal20 | p2_file | 0.567 | 0.600 | +0.033 | 1 | 0 |
| A_seed20261110_ctrl_cal20 | p2_python | 0.867 | 0.933 | +0.067 | 2 | 0 |
| A_seed20261110_ctrl_cal20 | p2_database | 0.367 | 0.367 | +0.000 | 0 | 0 |
| A_seed20261110_dose_db0 | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261110_dose_db0 | natv2_file | 0.767 | 0.767 | +0.000 | 0 | 0 |
| A_seed20261110_dose_db0 | natv2_python | 0.933 | 0.933 | +0.000 | 0 | 0 |
| A_seed20261110_dose_db0 | calendar_v3 | 0.560 | 0.573 | +0.013 | 2 | 0 |
| A_seed20261110_dose_db0 | p2_file | 0.533 | 0.533 | +0.000 | 0 | 0 |
| A_seed20261110_dose_db0 | p2_python | 0.967 | 0.933 | -0.033 | 0 | 1 |
| A_seed20261110_dose_db0 | p2_database | 0.567 | 0.567 | +0.000 | 0 | 0 |
| A_seed20261110_dose_db1 | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261110_dose_db1 | natv2_file | 0.767 | 0.733 | -0.033 | 0 | 1 |
| A_seed20261110_dose_db1 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261110_dose_db1 | calendar_v3 | 0.573 | 0.567 | -0.007 | 1 | 2 |
| A_seed20261110_dose_db1 | p2_file | 0.533 | 0.533 | +0.000 | 0 | 0 |
| A_seed20261110_dose_db1 | p2_python | 0.900 | 0.933 | +0.033 | 1 | 0 |
| A_seed20261110_dose_db1 | p2_database | 0.633 | 0.567 | -0.067 | 0 | 2 |
| A_seed20261110_dose_db2 | natv2_database | 0.067 | 0.200 | +0.133 | 4 | 0 |
| A_seed20261110_dose_db3 | natv2_database | 0.333 | 0.267 | -0.067 | 0 | 2 |
| A_seed20261110_dose_db4 | natv2_database | 0.667 | 0.667 | +0.000 | 1 | 1 |
| A_seed20261110_dose_db6 | natv2_database | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261110_dose_db6 | natv2_file | 0.767 | 0.767 | +0.000 | 0 | 0 |
| A_seed20261110_dose_db6 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261110_dose_db6 | calendar_v3 | 0.547 | 0.540 | -0.007 | 1 | 2 |
| A_seed20261110_dose_db6 | p2_file | 0.600 | 0.567 | -0.033 | 0 | 1 |
| A_seed20261110_dose_db6 | p2_python | 0.900 | 0.933 | +0.033 | 1 | 0 |
| A_seed20261110_dose_db6 | p2_database | 0.500 | 0.467 | -0.033 | 0 | 1 |
| A_seed20261110_none | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261110_none | natv2_file | 0.733 | 0.733 | +0.000 | 0 | 0 |
| A_seed20261110_none | natv2_python | 0.767 | 0.800 | +0.033 | 1 | 0 |
| A_seed20261110_none | calendar_v3 | 0.567 | 0.567 | +0.000 | 0 | 0 |
| A_seed20261110_none | p2_file | 0.567 | 0.567 | +0.000 | 0 | 0 |
| A_seed20261110_none | p2_python | 0.933 | 0.933 | +0.000 | 0 | 0 |
| A_seed20261110_none | p2_database | 0.367 | 0.367 | +0.000 | 0 | 0 |
| A_seed20261110_stage_03_python | calendar_v3 | 0.147 | 0.147 | +0.000 | 0 | 0 |
| A_seed20261110_tf00 | natv2_database | 0.000 | 0.000 | +0.000 | 0 | 0 |
| A_seed20261110_tf00 | natv2_file | 0.767 | 0.767 | +0.000 | 0 | 0 |
| A_seed20261110_tf00 | natv2_python | 0.800 | 0.800 | +0.000 | 0 | 0 |
| A_seed20261110_tf00 | p2_file | 0.600 | 0.567 | -0.033 | 0 | 1 |
| A_seed20261110_tf00 | p2_python | 0.967 | 1.000 | +0.033 | 1 | 0 |
| A_seed20261110_tf00 | p2_database | 0.367 | 0.367 | +0.000 | 0 | 0 |
| A_seed20261110_tf25 | natv2_database | 0.167 | 0.233 | +0.067 | 2 | 0 |
| A_seed20261110_tf25 | natv2_file | 0.767 | 0.767 | +0.000 | 0 | 0 |
| A_seed20261110_tf25 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261110_tf25 | calendar_v3 | 0.593 | 0.600 | +0.007 | 1 | 0 |
| A_seed20261110_tf25 | p2_file | 0.600 | 0.600 | +0.000 | 0 | 0 |
| A_seed20261110_tf25 | p2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261110_tf25 | p2_database | 0.300 | 0.300 | +0.000 | 0 | 0 |
| A_seed20261110_tf50 | natv2_database | 0.933 | 0.967 | +0.033 | 1 | 0 |
| A_seed20261110_tf50 | natv2_file | 0.767 | 0.767 | +0.000 | 0 | 0 |
| A_seed20261110_tf50 | natv2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261110_tf50 | calendar_v3 | 0.600 | 0.580 | -0.020 | 0 | 3 |
| A_seed20261110_tf50 | p2_file | 0.600 | 0.600 | +0.000 | 0 | 0 |
| A_seed20261110_tf50 | p2_python | 1.000 | 1.000 | +0.000 | 0 | 0 |
| A_seed20261110_tf50 | p2_database | 0.333 | 0.333 | +0.000 | 0 | 0 |

## 4. 实验 A 主指标（natv2_database B1）与实验 B 剂量曲线（B1）

| 臂 | 08 | 09 | 10 | 均值 | SD |
|---|---|---|---|---|---|
| e3b2_A_target_other | 0.100 | 0.200 | 0.067 | 0.122 | 0.069 |
| e3b2_A_target_dbbg | 0.100 | 0.233 | 0.000 | 0.111 | 0.117 |
| ctrl_cal10 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dose_db0 | 0.000 | 0.067 | 0.000 | 0.022 | 0.038 |
| dose_db1 | 0.033 | 0.267 | 0.000 | 0.100 | 0.145 |
| tf25 | 0.400 | 0.667 | 0.233 | 0.433 | 0.219 |
| none | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dose_db0 | 0.000 | 0.067 | 0.000 | 0.022 | 0.038 |
| dose_db1 | 0.033 | 0.267 | 0.000 | 0.100 | 0.145 |
| dose_db2 | 0.267 | 0.733 | 0.200 | 0.400 | 0.291 |
| dose_db3 | 0.533 | 0.933 | 0.267 | 0.578 | 0.336 |
| dose_db4 | 0.800 | 0.933 | 0.667 | 0.800 | 0.133 |
| dose_db6 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |

## 5. T0/T1/T2（同题集 B1）。T0=stage_02_database，T1=E4 none

| 种子 | 指标 | T0 | stage_03 | T1 | T2 | T0−T1 | T2−T1 | stage_04(参考) |
|---|---|---|---|---|---|---|---|---|
| 08 | natv2_database:db.filter_cmp_top|T2=tf50 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 |
| 08 | natv2_database:db.filter_cmp_top|T2=dose_db6 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 |
| 08 | natv2_database:db.filter_cmp_top|T2=tf25 | 0.000 | 0.000 | 0.000 | 0.400 | 0.000 | 0.400 | 0.000 |
| 08 | natv2_file:overall|T2=tf50 | 0.000 | 0.167 | 0.000 | 0.800 | 0.000 | 0.800 | 0.000 |
| 08 | natv2_file:overall|T2=dose_db6 | 0.000 | 0.167 | 0.000 | 0.533 | 0.000 | 0.533 | 0.000 |
| 08 | natv2_file:overall|T2=tf25 | 0.000 | 0.167 | 0.000 | 0.633 | 0.000 | 0.633 | 0.000 |
| 08 | natv2_python:overall|T2=tf50 | 0.967 | 0.967 | 0.467 | 0.933 | 0.500 | 0.467 | 0.500 |
| 08 | natv2_python:overall|T2=dose_db6 | 0.967 | 0.967 | 0.467 | 0.967 | 0.500 | 0.500 | 0.500 |
| 08 | natv2_python:overall|T2=tf25 | 0.967 | 0.967 | 0.467 | 1.000 | 0.500 | 0.533 | 0.500 |
| 08 | db_nontarget:overall|T2=tf50 | 0.250 | 0.425 | 0.700 | 0.575 | -0.450 | -0.125 | 0.700 |
| 08 | db_nontarget:overall|T2=dose_db6 | 0.250 | 0.425 | 0.700 | 0.625 | -0.450 | -0.075 | 0.700 |
| 08 | db_nontarget:overall|T2=tf25 | 0.250 | 0.425 | 0.700 | 0.675 | -0.450 | -0.025 | 0.700 |
| 09 | natv2_database:db.filter_cmp_top|T2=tf50 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 |
| 09 | natv2_database:db.filter_cmp_top|T2=dose_db6 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 |
| 09 | natv2_database:db.filter_cmp_top|T2=tf25 | 0.000 | 0.000 | 0.000 | 0.667 | 0.000 | 0.667 | 0.000 |
| 09 | natv2_file:overall|T2=tf50 | 0.000 | 0.167 | 0.433 | 0.800 | -0.433 | 0.367 | 0.767 |
| 09 | natv2_file:overall|T2=dose_db6 | 0.000 | 0.167 | 0.433 | 0.767 | -0.433 | 0.333 | 0.767 |
| 09 | natv2_file:overall|T2=tf25 | 0.000 | 0.167 | 0.433 | 0.700 | -0.433 | 0.267 | 0.767 |
| 09 | natv2_python:overall|T2=tf50 | 0.633 | 0.933 | 1.000 | 1.000 | -0.367 | 0.000 | 1.000 |
| 09 | natv2_python:overall|T2=dose_db6 | 0.633 | 0.933 | 1.000 | 1.000 | -0.367 | 0.000 | 1.000 |
| 09 | natv2_python:overall|T2=tf25 | 0.633 | 0.933 | 1.000 | 1.000 | -0.367 | 0.000 | 1.000 |
| 09 | db_nontarget:overall|T2=tf50 | 0.525 | 0.650 | 0.750 | 0.750 | -0.225 | 0.000 | 0.775 |
| 09 | db_nontarget:overall|T2=dose_db6 | 0.525 | 0.650 | 0.750 | 0.750 | -0.225 | 0.000 | 0.775 |
| 09 | db_nontarget:overall|T2=tf25 | 0.525 | 0.650 | 0.750 | 0.700 | -0.225 | -0.050 | 0.775 |
| 10 | natv2_database:db.filter_cmp_top|T2=tf50 | 0.000 | 0.000 | 0.000 | 0.967 | 0.000 | 0.967 | 0.000 |
| 10 | natv2_database:db.filter_cmp_top|T2=dose_db6 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 |
| 10 | natv2_database:db.filter_cmp_top|T2=tf25 | 0.000 | 0.000 | 0.000 | 0.233 | 0.000 | 0.233 | 0.000 |
| 10 | natv2_file:overall|T2=tf50 | 0.000 | 0.500 | 0.733 | 0.767 | -0.733 | 0.033 | 0.800 |
| 10 | natv2_file:overall|T2=dose_db6 | 0.000 | 0.500 | 0.733 | 0.767 | -0.733 | 0.033 | 0.800 |
| 10 | natv2_file:overall|T2=tf25 | 0.000 | 0.500 | 0.733 | 0.767 | -0.733 | 0.033 | 0.800 |
| 10 | natv2_python:overall|T2=tf50 | 1.000 | 1.000 | 0.800 | 1.000 | 0.200 | 0.200 | 0.933 |
| 10 | natv2_python:overall|T2=dose_db6 | 1.000 | 1.000 | 0.800 | 1.000 | 0.200 | 0.200 | 0.933 |
| 10 | natv2_python:overall|T2=tf25 | 1.000 | 1.000 | 0.800 | 1.000 | 0.200 | 0.200 | 0.933 |
| 10 | db_nontarget:overall|T2=tf50 | 0.575 | 0.600 | 0.675 | 0.650 | -0.100 | -0.025 | 0.725 |
| 10 | db_nontarget:overall|T2=dose_db6 | 0.575 | 0.600 | 0.675 | 0.700 | -0.100 | 0.025 | 0.725 |
| 10 | db_nontarget:overall|T2=tf25 | 0.575 | 0.600 | 0.675 | 0.700 | -0.100 | 0.025 | 0.725 |

## 6. 复习池 Coverage / Diversity（只读计划，CPU）

| 臂 | slots | unique | filter_cmp_top slots/unique | 近邻 slots(top_n, filter_eq_count, filter_eq_top) | Pattern Coverage | 唯一率 | 归一熵 |
|---|---|---|---|---|---|---|---|
| A_seed20261108_b20_tf50 | 44 | 42 | 8/8 | 2, 3, 0 | 0.333 | 0.955 | 0.938 |
| A_seed20261108_ctrl_cal10 | 23 | 8 | 0/0 | 0, 0, 0 | 0.095 | 0.348 | 0.577 |
| A_seed20261108_ctrl_cal20 | 42 | 21 | 0/0 | 0, 0, 0 | 0.143 | 0.500 | 0.685 |
| A_seed20261108_dose_db0 | 23 | 22 | 0/0 | 1, 2, 0 | 0.310 | 0.957 | 0.955 |
| A_seed20261108_dose_db1 | 23 | 21 | 1/1 | 2, 0, 0 | 0.333 | 0.913 | 0.951 |
| A_seed20261108_dose_db2 | 23 | 21 | 2/2 | 1, 0, 0 | 0.310 | 0.913 | 0.946 |
| A_seed20261108_dose_db3 | 23 | 20 | 3/3 | 1, 0, 0 | 0.286 | 0.870 | 0.928 |
| A_seed20261108_dose_db4 | 22 | 21 | 4/4 | 1, 0, 0 | 0.262 | 0.955 | 0.938 |
| A_seed20261108_dose_db6 | 22 | 21 | 6/6 | 0, 0, 0 | 0.238 | 0.955 | 0.901 |
| A_seed20261108_e3b2_A_target_dbbg | 22 | 21 | 1/1 | 0, 0, 0 | 0.262 | 0.955 | 0.964 |
| A_seed20261108_e3b2_A_target_other | 21 | 20 | 1/1 | 0, 0, 0 | 0.238 | 0.952 | 0.957 |
| A_seed20261108_tf00 | 22 | 21 | 0/0 | 2, 2, 0 | 0.286 | 0.955 | 0.971 |
| A_seed20261108_tf25 | 23 | 22 | 1/1 | 2, 2, 0 | 0.310 | 0.957 | 0.961 |
| A_seed20261108_tf50 | 22 | 22 | 6/6 | 2, 1, 0 | 0.286 | 1.000 | 0.895 |
| A_seed20261109_b20_tf50 | 44 | 40 | 7/7 | 1, 1, 0 | 0.405 | 0.909 | 0.879 |
| A_seed20261109_ctrl_cal10 | 22 | 10 | 0/0 | 0, 0, 0 | 0.119 | 0.455 | 0.675 |
| A_seed20261109_ctrl_cal20 | 42 | 20 | 0/0 | 0, 0, 0 | 0.143 | 0.476 | 0.686 |
| A_seed20261109_dose_db0 | 22 | 19 | 0/0 | 0, 1, 0 | 0.286 | 0.864 | 0.930 |
| A_seed20261109_dose_db1 | 22 | 20 | 1/1 | 0, 1, 0 | 0.310 | 0.909 | 0.935 |
| A_seed20261109_dose_db2 | 22 | 22 | 2/2 | 2, 0, 0 | 0.310 | 1.000 | 0.950 |
| A_seed20261109_dose_db3 | 22 | 22 | 3/3 | 1, 0, 0 | 0.333 | 1.000 | 0.947 |
| A_seed20261109_dose_db4 | 22 | 22 | 4/4 | 0, 0, 0 | 0.310 | 1.000 | 0.935 |
| A_seed20261109_dose_db6 | 22 | 22 | 6/6 | 0, 0, 0 | 0.286 | 1.000 | 0.895 |
| A_seed20261109_e3b2_A_target_dbbg | 23 | 21 | 1/1 | 0, 0, 0 | 0.310 | 0.913 | 0.952 |
| A_seed20261109_e3b2_A_target_other | 21 | 20 | 1/1 | 0, 0, 0 | 0.238 | 0.952 | 0.950 |
| A_seed20261109_tf00 | 22 | 22 | 0/0 | 1, 1, 0 | 0.357 | 1.000 | 0.946 |
| A_seed20261109_tf25 | 22 | 20 | 1/1 | 1, 1, 0 | 0.357 | 0.909 | 0.946 |
| A_seed20261109_tf50 | 22 | 22 | 4/4 | 1, 0, 0 | 0.310 | 1.000 | 0.926 |
| A_seed20261110_b20_tf50 | 44 | 42 | 8/8 | 4, 1, 0 | 0.381 | 0.955 | 0.911 |
| A_seed20261110_ctrl_cal10 | 22 | 9 | 0/0 | 0, 0, 0 | 0.119 | 0.409 | 0.575 |
| A_seed20261110_ctrl_cal20 | 42 | 15 | 0/0 | 0, 0, 0 | 0.143 | 0.357 | 0.623 |
| A_seed20261110_dose_db0 | 23 | 22 | 0/0 | 3, 3, 0 | 0.262 | 0.957 | 0.943 |
| A_seed20261110_dose_db1 | 23 | 21 | 1/1 | 1, 2, 0 | 0.310 | 0.913 | 0.937 |
| A_seed20261110_dose_db2 | 22 | 19 | 2/2 | 0, 1, 0 | 0.262 | 0.864 | 0.944 |
| A_seed20261110_dose_db3 | 22 | 18 | 3/3 | 0, 1, 0 | 0.238 | 0.818 | 0.928 |
| A_seed20261110_dose_db4 | 22 | 19 | 4/4 | 0, 1, 0 | 0.238 | 0.864 | 0.928 |
| A_seed20261110_dose_db6 | 22 | 21 | 6/6 | 0, 1, 0 | 0.238 | 0.955 | 0.891 |
| A_seed20261110_e3b2_A_target_dbbg | 22 | 21 | 1/1 | 0, 0, 0 | 0.310 | 0.955 | 0.975 |
| A_seed20261110_e3b2_A_target_other | 21 | 20 | 1/1 | 0, 0, 0 | 0.262 | 0.952 | 0.946 |
| A_seed20261110_tf00 | 22 | 21 | 0/0 | 1, 1, 0 | 0.310 | 0.955 | 0.940 |
| A_seed20261110_tf25 | 22 | 22 | 1/1 | 3, 1, 0 | 0.333 | 1.000 | 0.962 |
| A_seed20261110_tf50 | 22 | 22 | 5/5 | 1, 0, 0 | 0.310 | 1.000 | 0.906 |
