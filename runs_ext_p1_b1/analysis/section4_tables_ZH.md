# P1 第 4 节补充分析表（Protocol-B1）

生成：2026-11-13 12:56:35 +0800（Asia/Shanghai）。脚本 `scripts/p1_section4_analysis.py`，只读 summary.json 与 results.jsonl。

## A. 协议桥接翻转汇总（B1 对历史 B32，同 checkpoint 同题）

「B32对→B1错」= down，「B32错→B1对」= up；翻转率 =(down+up)/题次。

| 种子 | suite | checkpoint 数 | 题次 | B32对→B1错 | B32错→B1对 | 净(up−down) | 翻转率 | 零翻转 checkpoint |
|---|---|---|---|---|---|---|---|---|
| 08 | natv2_database | 13 | 390 | 10 | 4 | -6 | 0.036 | 9 |
| 08 | natv2_file | 10 | 300 | 23 | 6 | -17 | 0.097 | 1 |
| 08 | natv2_python | 10 | 300 | 13 | 11 | -2 | 0.080 | 6 |
| 08 | calendar_v3 | 10 | 1500 | 27 | 21 | -6 | 0.032 | 0 |
| 08 | p2_file | 10 | 300 | 0 | 1 | +1 | 0.003 | 9 |
| 08 | p2_python | 10 | 300 | 4 | 6 | +2 | 0.033 | 4 |
| 08 | p2_database | 10 | 300 | 2 | 6 | +4 | 0.027 | 7 |
| 09 | natv2_database | 13 | 390 | 4 | 8 | +4 | 0.031 | 8 |
| 09 | natv2_file | 10 | 300 | 2 | 9 | +7 | 0.037 | 3 |
| 09 | natv2_python | 10 | 300 | 0 | 0 | +0 | 0.000 | 10 |
| 09 | calendar_v3 | 10 | 1500 | 24 | 21 | -3 | 0.030 | 0 |
| 09 | p2_file | 10 | 300 | 0 | 3 | +3 | 0.010 | 7 |
| 09 | p2_python | 10 | 300 | 1 | 1 | +0 | 0.007 | 9 |
| 09 | p2_database | 10 | 300 | 2 | 0 | -2 | 0.007 | 8 |
| 10 | natv2_database | 13 | 390 | 5 | 8 | +3 | 0.033 | 7 |
| 10 | natv2_file | 10 | 300 | 7 | 1 | -6 | 0.027 | 6 |
| 10 | natv2_python | 10 | 300 | 1 | 3 | +2 | 0.013 | 7 |
| 10 | calendar_v3 | 10 | 1500 | 12 | 9 | -3 | 0.014 | 3 |
| 10 | p2_file | 10 | 300 | 4 | 1 | -3 | 0.017 | 6 |
| 10 | p2_python | 10 | 300 | 1 | 5 | +4 | 0.020 | 5 |
| 10 | p2_database | 10 | 300 | 3 | 0 | -3 | 0.010 | 8 |
| 三种子合计 | natv2_database | 39 | 1170 | 19 | 20 | +1 | 0.033 | 24 |
| 三种子合计 | natv2_file | 30 | 900 | 32 | 16 | -16 | 0.053 | 10 |
| 三种子合计 | natv2_python | 30 | 900 | 14 | 14 | +0 | 0.031 | 23 |
| 三种子合计 | calendar_v3 | 30 | 4500 | 63 | 51 | -12 | 0.025 | 3 |
| 三种子合计 | p2_file | 30 | 900 | 4 | 5 | +1 | 0.010 | 22 |
| 三种子合计 | p2_python | 30 | 900 | 6 | 12 | +6 | 0.020 | 18 |
| 三种子合计 | p2_database | 30 | 900 | 7 | 6 | -1 | 0.014 | 23 |

全部 suite 合计：题次 10170，B32对→B1错 145，B32错→B1对 124，翻转率 0.026。

## B. nat v2 Database（`db.filter_cmp_top`，30 题）逐环节分解

tool=选对 `db_query`；arguments=SQL 执行结果与金标一致；final=最终答案对；joint=主指标。

| 种子 | checkpoint | tool | arguments | final | joint |
|---|---|---|---|---|---|
| 08 | stage_02_database | 1.000 | 0.000 | 0.633 | 0.000 |
| 08 | stage_03_python | 1.000 | 0.000 | 0.033 | 0.000 |
| 08 | stage_04_calendar | 1.000 | 0.000 | 0.400 | 0.000 |
| 08 | none | 1.000 | 0.000 | 0.467 | 0.000 |
| 08 | ctrl_cal10 | 1.000 | 0.000 | 0.467 | 0.000 |
| 08 | dose_db0 | 1.000 | 0.000 | 0.433 | 0.000 |
| 08 | dose_db1 | 1.000 | 0.033 | 0.500 | 0.033 |
| 08 | e3b2_A_target_other | 1.000 | 0.100 | 0.533 | 0.100 |
| 08 | e3b2_A_target_dbbg | 1.000 | 0.100 | 0.467 | 0.100 |
| 08 | tf25 | 1.000 | 0.567 | 0.667 | 0.400 |
| 08 | dose_db2 | 1.000 | 0.467 | 0.600 | 0.267 |
| 08 | dose_db3 | 1.000 | 0.733 | 0.667 | 0.533 |
| 08 | dose_db4 | 1.000 | 0.833 | 0.833 | 0.800 |
| 08 | dose_db6 | 1.000 | 1.000 | 1.000 | 1.000 |
| 08 | tf50 | 1.000 | 1.000 | 1.000 | 1.000 |
| 08 | b20_tf50 | 1.000 | 1.000 | 1.000 | 1.000 |
| 09 | stage_02_database | 0.367 | 0.000 | 0.167 | 0.000 |
| 09 | stage_03_python | 1.000 | 0.000 | 0.067 | 0.000 |
| 09 | stage_04_calendar | 1.000 | 0.000 | 0.400 | 0.000 |
| 09 | none | 1.000 | 0.000 | 0.300 | 0.000 |
| 09 | ctrl_cal10 | 1.000 | 0.000 | 0.300 | 0.000 |
| 09 | dose_db0 | 1.000 | 0.133 | 0.300 | 0.067 |
| 09 | dose_db1 | 1.000 | 0.433 | 0.400 | 0.267 |
| 09 | tf25 | 1.000 | 0.767 | 0.700 | 0.667 |
| 09 | dose_db2 | 1.000 | 0.800 | 0.800 | 0.733 |
| 09 | dose_db3 | 1.000 | 1.000 | 0.933 | 0.933 |
| 09 | dose_db4 | 1.000 | 1.000 | 0.933 | 0.933 |
| 09 | dose_db6 | 1.000 | 1.000 | 1.000 | 1.000 |
| 09 | tf50 | 1.000 | 1.000 | 1.000 | 1.000 |
| 09 | b20_tf50 | 1.000 | 1.000 | 1.000 | 1.000 |
| 10 | stage_02_database | 1.000 | 0.000 | 0.567 | 0.000 |
| 10 | stage_03_python | 1.000 | 0.033 | 0.200 | 0.000 |
| 10 | stage_04_calendar | 1.000 | 0.000 | 0.633 | 0.000 |
| 10 | none | 1.000 | 0.000 | 0.433 | 0.000 |
| 10 | ctrl_cal10 | 1.000 | 0.000 | 0.433 | 0.000 |
| 10 | dose_db0 | 1.000 | 0.000 | 0.433 | 0.000 |
| 10 | dose_db1 | 1.000 | 0.000 | 0.400 | 0.000 |
| 10 | tf25 | 1.000 | 0.433 | 0.433 | 0.233 |
| 10 | dose_db2 | 1.000 | 0.333 | 0.467 | 0.200 |
| 10 | dose_db3 | 1.000 | 0.467 | 0.367 | 0.267 |
| 10 | dose_db4 | 1.000 | 0.767 | 0.733 | 0.667 |
| 10 | dose_db6 | 1.000 | 1.000 | 1.000 | 1.000 |
| 10 | tf50 | 1.000 | 1.000 | 0.967 | 0.967 |
| 10 | b20_tf50 | 0.933 | 0.933 | 0.933 | 0.933 |

## C. T0 / stage_03 / T1 / stage_04（参考）同题集逐模式（B1）

| 种子 | suite:模式 | T0 stage_02 | stage_03 | T1 none | stage_04（参考） |
|---|---|---|---|---|---|
| 08 | natv2_database:overall | 0.000 | 0.000 | 0.000 | 0.000 |
| 08 | natv2_database:db.filter_cmp_top | 0.000 | 0.000 | 0.000 | 0.000 |
| 08 | db_nontarget:overall | 0.250 | 0.425 | 0.700 | 0.700 |
| 08 | db_nontarget:db.filter_cmp_avg | 0.750 | 0.750 | 0.750 | 0.750 |
| 08 | db_nontarget:db.filter_cmp_count | 0.125 | 0.625 | 1.000 | 1.000 |
| 08 | db_nontarget:db.filter_cmp_group_count | 0.000 | 0.000 | 0.250 | 0.250 |
| 08 | db_nontarget:db.min_max | 0.375 | 0.375 | 0.750 | 0.750 |
| 08 | db_nontarget:db.multi_filter_count | 0.000 | 0.375 | 0.750 | 0.750 |
| 08 | p2_database:overall | 0.567 | 0.367 | 0.400 | 0.400 |
| 08 | p2_database:db.filter_eq_avg | 0.833 | 0.833 | 1.000 | 1.000 |
| 08 | p2_database:db.filter_eq_top | 0.000 | 0.000 | 0.000 | 0.000 |
| 08 | p2_database:db.group_avg | 0.000 | 0.000 | 0.000 | 0.000 |
| 08 | p2_database:db.list_tables | 1.000 | 0.000 | 0.000 | 0.000 |
| 08 | p2_database:db.schema_count | 1.000 | 1.000 | 1.000 | 1.000 |
| 08 | natv2_file:overall | 0.000 | 0.167 | 0.000 | 0.000 |
| 08 | natv2_file:file.search_last | 0.000 | 0.167 | 0.000 | 0.000 |
| 08 | p2_file:overall | 0.600 | 0.467 | 0.467 | 0.467 |
| 08 | p2_file:file.list_all | 1.000 | 1.000 | 1.000 | 1.000 |
| 08 | p2_file:file.search_last | 0.500 | 0.000 | 0.000 | 0.000 |
| 08 | p2_file:file.word_count | 0.000 | 0.000 | 0.000 | 0.000 |
| 08 | p2_file:file.write_char_count | 1.000 | 1.000 | 1.000 | 1.000 |
| 08 | natv2_python:overall | 0.967 | 0.967 | 0.467 | 0.500 |
| 08 | natv2_python:py.median | 0.967 | 0.967 | 0.467 | 0.500 |
| 08 | p2_python:overall | 0.667 | 1.000 | 0.900 | 0.933 |
| 08 | p2_python:py.correlation | 0.000 | 1.000 | 1.000 | 1.000 |
| 08 | p2_python:py.mean | 1.000 | 1.000 | 1.000 | 1.000 |
| 08 | p2_python:py.median | 1.000 | 1.000 | 0.400 | 0.600 |
| 08 | p2_python:py.percentile | 1.000 | 1.000 | 1.000 | 1.000 |
| 08 | p2_python:py.regression | 0.000 | 1.000 | 1.000 | 1.000 |
| 08 | p2_python:py.std | 1.000 | 1.000 | 1.000 | 1.000 |
| 08 | calendar_v3:overall | 0.167 | 0.193 | 0.533 | 0.480 |
| 08 | calendar_v3:cv3.attendee_count | 0.533 | 0.767 | 0.800 | 0.800 |
| 08 | calendar_v3:cv3.free_latest | 0.067 | 0.033 | 0.467 | 0.533 |
| 08 | calendar_v3:cv3.last_end | 0.000 | 0.000 | 0.600 | 0.367 |
| 08 | calendar_v3:cv3.locations | 0.000 | 0.000 | 0.367 | 0.333 |
| 08 | calendar_v3:cv3.search_count | 0.233 | 0.167 | 0.433 | 0.367 |
| 09 | natv2_database:overall | 0.000 | 0.000 | 0.000 | 0.000 |
| 09 | natv2_database:db.filter_cmp_top | 0.000 | 0.000 | 0.000 | 0.000 |
| 09 | db_nontarget:overall | 0.525 | 0.650 | 0.750 | 0.775 |
| 09 | db_nontarget:db.filter_cmp_avg | 0.750 | 0.750 | 0.750 | 0.750 |
| 09 | db_nontarget:db.filter_cmp_count | 0.500 | 1.000 | 1.000 | 1.000 |
| 09 | db_nontarget:db.filter_cmp_group_count | 0.125 | 0.000 | 0.000 | 0.125 |
| 09 | db_nontarget:db.min_max | 0.625 | 0.750 | 1.000 | 1.000 |
| 09 | db_nontarget:db.multi_filter_count | 0.625 | 0.750 | 1.000 | 1.000 |
| 09 | p2_database:overall | 0.633 | 0.467 | 0.433 | 0.433 |
| 09 | p2_database:db.filter_eq_avg | 0.833 | 0.833 | 0.833 | 0.833 |
| 09 | p2_database:db.filter_eq_top | 0.333 | 0.500 | 0.333 | 0.333 |
| 09 | p2_database:db.group_avg | 0.000 | 0.000 | 0.000 | 0.000 |
| 09 | p2_database:db.list_tables | 1.000 | 0.000 | 0.000 | 0.000 |
| 09 | p2_database:db.schema_count | 1.000 | 1.000 | 1.000 | 1.000 |
| 09 | natv2_file:overall | 0.000 | 0.167 | 0.433 | 0.767 |
| 09 | natv2_file:file.search_last | 0.000 | 0.167 | 0.433 | 0.767 |
| 09 | p2_file:overall | 0.533 | 0.467 | 0.500 | 0.500 |
| 09 | p2_file:file.list_all | 1.000 | 1.000 | 1.000 | 1.000 |
| 09 | p2_file:file.search_last | 0.250 | 0.000 | 0.125 | 0.125 |
| 09 | p2_file:file.word_count | 0.000 | 0.000 | 0.000 | 0.000 |
| 09 | p2_file:file.write_char_count | 1.000 | 1.000 | 1.000 | 1.000 |
| 09 | natv2_python:overall | 0.633 | 0.933 | 1.000 | 1.000 |
| 09 | natv2_python:py.median | 0.633 | 0.933 | 1.000 | 1.000 |
| 09 | p2_python:overall | 0.833 | 1.000 | 0.833 | 0.867 |
| 09 | p2_python:py.correlation | 0.000 | 1.000 | 1.000 | 1.000 |
| 09 | p2_python:py.mean | 1.000 | 1.000 | 1.000 | 1.000 |
| 09 | p2_python:py.median | 1.000 | 1.000 | 0.000 | 0.200 |
| 09 | p2_python:py.percentile | 1.000 | 1.000 | 1.000 | 1.000 |
| 09 | p2_python:py.regression | 1.000 | 1.000 | 1.000 | 1.000 |
| 09 | p2_python:py.std | 1.000 | 1.000 | 1.000 | 1.000 |
| 09 | calendar_v3:overall | 0.173 | 0.160 | 0.507 | 0.427 |
| 09 | calendar_v3:cv3.attendee_count | 0.667 | 0.633 | 0.800 | 0.933 |
| 09 | calendar_v3:cv3.free_latest | 0.033 | 0.033 | 0.633 | 0.500 |
| 09 | calendar_v3:cv3.last_end | 0.000 | 0.000 | 0.467 | 0.100 |
| 09 | calendar_v3:cv3.locations | 0.000 | 0.000 | 0.333 | 0.300 |
| 09 | calendar_v3:cv3.search_count | 0.167 | 0.133 | 0.300 | 0.300 |
| 10 | natv2_database:overall | 0.000 | 0.000 | 0.000 | 0.000 |
| 10 | natv2_database:db.filter_cmp_top | 0.000 | 0.000 | 0.000 | 0.000 |
| 10 | db_nontarget:overall | 0.575 | 0.600 | 0.675 | 0.725 |
| 10 | db_nontarget:db.filter_cmp_avg | 0.875 | 0.750 | 0.750 | 0.625 |
| 10 | db_nontarget:db.filter_cmp_count | 0.625 | 0.625 | 0.750 | 1.000 |
| 10 | db_nontarget:db.filter_cmp_group_count | 0.000 | 0.000 | 0.000 | 0.000 |
| 10 | db_nontarget:db.min_max | 0.750 | 0.875 | 1.000 | 1.000 |
| 10 | db_nontarget:db.multi_filter_count | 0.625 | 0.750 | 0.875 | 1.000 |
| 10 | p2_database:overall | 0.633 | 0.400 | 0.367 | 0.367 |
| 10 | p2_database:db.filter_eq_avg | 0.833 | 0.833 | 0.833 | 0.833 |
| 10 | p2_database:db.filter_eq_top | 0.333 | 0.167 | 0.000 | 0.000 |
| 10 | p2_database:db.group_avg | 0.000 | 0.000 | 0.000 | 0.000 |
| 10 | p2_database:db.list_tables | 1.000 | 0.000 | 0.000 | 0.000 |
| 10 | p2_database:db.schema_count | 1.000 | 1.000 | 1.000 | 1.000 |
| 10 | natv2_file:overall | 0.000 | 0.500 | 0.733 | 0.800 |
| 10 | natv2_file:file.search_last | 0.000 | 0.500 | 0.733 | 0.800 |
| 10 | p2_file:overall | 0.533 | 0.567 | 0.567 | 0.467 |
| 10 | p2_file:file.list_all | 1.000 | 0.857 | 1.000 | 1.000 |
| 10 | p2_file:file.search_last | 0.250 | 0.500 | 0.375 | 0.000 |
| 10 | p2_file:file.word_count | 0.000 | 0.000 | 0.000 | 0.000 |
| 10 | p2_file:file.write_char_count | 1.000 | 1.000 | 1.000 | 1.000 |
| 10 | natv2_python:overall | 1.000 | 1.000 | 0.800 | 0.933 |
| 10 | natv2_python:py.median | 1.000 | 1.000 | 0.800 | 0.933 |
| 10 | p2_python:overall | 0.900 | 1.000 | 0.933 | 0.967 |
| 10 | p2_python:py.correlation | 0.400 | 1.000 | 1.000 | 1.000 |
| 10 | p2_python:py.mean | 1.000 | 1.000 | 1.000 | 1.000 |
| 10 | p2_python:py.median | 1.000 | 1.000 | 0.600 | 0.800 |
| 10 | p2_python:py.percentile | 1.000 | 1.000 | 1.000 | 1.000 |
| 10 | p2_python:py.regression | 1.000 | 1.000 | 1.000 | 1.000 |
| 10 | p2_python:py.std | 1.000 | 1.000 | 1.000 | 1.000 |
| 10 | calendar_v3:overall | 0.160 | 0.147 | 0.567 | 0.460 |
| 10 | calendar_v3:cv3.attendee_count | 0.533 | 0.667 | 0.867 | 0.833 |
| 10 | calendar_v3:cv3.free_latest | 0.033 | 0.033 | 0.767 | 0.667 |
| 10 | calendar_v3:cv3.last_end | 0.000 | 0.000 | 0.500 | 0.100 |
| 10 | calendar_v3:cv3.locations | 0.000 | 0.000 | 0.267 | 0.367 |
| 10 | calendar_v3:cv3.search_count | 0.233 | 0.033 | 0.433 | 0.333 |

## D. Database 剂量曲线（B1）：目标模式 vs 非 target 40 题

| 臂 | 目标 08 | 09 | 10 | 均值±SD | 历史 B32 均值 | 非 target 08 | 09 | 10 | 均值±SD |
|---|---|---|---|---|---|---|---|---|---|
| none | 0.000 | 0.000 | 0.000 | 0.000±0.000 | 0.000 | 0.700 | 0.750 | 0.675 | 0.708±0.038 |
| dose_db0 | 0.000 | 0.067 | 0.000 | 0.022±0.038 | 0.000 | 0.700 | 0.750 | 0.700 | 0.717±0.029 |
| dose_db1 | 0.033 | 0.267 | 0.000 | 0.100±0.145 | 0.100 | 0.650 | 0.750 | 0.600 | 0.667±0.076 |
| dose_db2 | 0.267 | 0.733 | 0.200 | 0.400±0.291 | 0.344 | 0.450 | 0.750 | 0.725 | 0.642±0.167 |
| dose_db3 | 0.533 | 0.933 | 0.267 | 0.578±0.336 | 0.611 | 0.525 | 0.750 | 0.725 | 0.667±0.123 |
| dose_db4 | 0.800 | 0.933 | 0.667 | 0.800±0.133 | 0.822 | 0.675 | 0.750 | 0.700 | 0.708±0.038 |
| dose_db6 | 1.000 | 1.000 | 1.000 | 1.000±0.000 | 1.000 | 0.625 | 0.750 | 0.700 | 0.692±0.063 |

## E. v3fix（附加指标，30 题）：Tool Accuracy / Conditional Counting / Joint

| checkpoint | 08 | 09 | 10 | Joint 均值 |
|---|---|---|---|---|
| stage_02_database | 0.000 / — / 0.000 | 0.000 / — / 0.000 | 0.000 / — / 0.000 | 0.000 |
| stage_03_python | 0.000 / — / 0.000 | 0.000 / — / 0.000 | 0.000 / — / 0.000 | 0.000 |
| stage_04_calendar | 0.500 / 0.733 / 0.367 | 0.333 / 0.800 / 0.267 | 0.500 / 0.400 / 0.200 | 0.278 |
| none | 0.500 / 0.533 / 0.267 | 0.500 / 0.600 / 0.300 | 0.500 / 0.600 / 0.300 | 0.289 |
| ctrl_cal10 | 0.500 / 0.533 / 0.267 | 0.500 / 0.600 / 0.300 | 0.500 / 0.667 / 0.333 | 0.300 |
| ctrl_cal20 | 0.500 / 0.600 / 0.300 | 0.500 / 0.600 / 0.300 | 0.500 / 0.600 / 0.300 | 0.300 |
| dose_db0 | 0.500 / 0.600 / 0.300 | 0.500 / 0.600 / 0.300 | 0.500 / 0.733 / 0.367 | 0.322 |
| dose_db1 | 0.500 / 0.600 / 0.300 | 0.500 / 0.600 / 0.300 | 0.500 / 0.733 / 0.367 | 0.322 |
| dose_db6 | 0.500 / 0.600 / 0.300 | 0.500 / 0.667 / 0.333 | 0.500 / 0.800 / 0.400 | 0.344 |
| tf25 | 0.500 / 0.600 / 0.300 | 0.500 / 0.600 / 0.300 | 0.500 / 0.733 / 0.367 | 0.322 |
| tf50 | 0.500 / 0.600 / 0.300 | 0.500 / 0.600 / 0.300 | 0.500 / 0.667 / 0.333 | 0.311 |
| b20_tf50 | 0.500 / 0.600 / 0.300 | 0.500 / 0.667 / 0.333 | 0.467 / 0.786 / 0.367 | 0.333 |
| e3b2_A_target_other | 0.500 / 0.600 / 0.300 | — | — | 0.300 |
| e3b2_A_target_dbbg | 0.500 / 0.533 / 0.267 | — | — | 0.267 |

## F. 实验 A 种子 08：主指标与副指标（B1）

| 臂 | 主指标 natv2 DB joint | tool/args/final | 非 target 40 | nat File | nat Python | Calendar v3 | p2 File | p2 Python | p2 DB | v3fix 联合 |
|---|---|---|---|---|---|---|---|---|---|---|
| e3b2_A_target_other | 0.100 | 1.000/0.100/0.533 | 0.700 | 0.000 | 0.700 | 0.500 | 0.467 | 0.933 | 0.367 | 0.300 |
| e3b2_A_target_dbbg | 0.100 | 1.000/0.100/0.467 | 0.700 | 0.000 | 0.867 | 0.507 | 0.467 | 0.967 | 0.367 | 0.267 |
| ctrl_cal10 | 0.000 | 1.000/0.000/0.467 | 0.675 | 0.000 | 0.433 | 0.520 | 0.467 | 0.900 | 0.400 | 0.267 |
| dose_db0 | 0.000 | 1.000/0.000/0.433 | 0.700 | 0.133 | 0.933 | 0.527 | 0.533 | 0.967 | 0.400 | 0.300 |
| dose_db1 | 0.033 | 1.000/0.033/0.500 | 0.650 | 0.333 | 0.933 | 0.493 | 0.567 | 0.967 | 0.567 | 0.300 |
| tf25 | 0.400 | 1.000/0.567/0.667 | 0.675 | 0.633 | 1.000 | 0.487 | 0.567 | 0.967 | 0.433 | 0.300 |
| none | 0.000 | 1.000/0.000/0.467 | 0.700 | 0.000 | 0.467 | 0.533 | 0.467 | 0.900 | 0.400 | 0.267 |

主指标答对的题：target_other ['database-final-target_db_filter_top-006', 'database-final-target_db_filter_top-017', 'database-final-target_db_filter_top-027']；target_dbbg ['database-final-target_db_filter_top-006', 'database-final-target_db_filter_top-017', 'database-final-target_db_filter_top-027']；两臂共同 3 题；dose_db1 ['database-final-target_db_filter_top-027']；tf25 共 12 题。

- e3b2_A_target_other 非 target 五模式：db.filter_cmp_avg 0.750，db.filter_cmp_count 1.000，db.filter_cmp_group_count 0.250，db.min_max 0.750，db.multi_filter_count 0.750
- e3b2_A_target_dbbg 非 target 五模式：db.filter_cmp_avg 0.750，db.filter_cmp_count 1.000，db.filter_cmp_group_count 0.250，db.min_max 0.750，db.multi_filter_count 0.750
- ctrl_cal10 非 target 五模式：db.filter_cmp_avg 0.750，db.filter_cmp_count 1.000，db.filter_cmp_group_count 0.250，db.min_max 0.625，db.multi_filter_count 0.750
- dose_db0 非 target 五模式：db.filter_cmp_avg 0.750，db.filter_cmp_count 1.000，db.filter_cmp_group_count 0.250，db.min_max 0.750，db.multi_filter_count 0.750
- dose_db1 非 target 五模式：db.filter_cmp_avg 0.625，db.filter_cmp_count 1.000，db.filter_cmp_group_count 0.250，db.min_max 0.750，db.multi_filter_count 0.625
- tf25 非 target 五模式：db.filter_cmp_avg 0.750，db.filter_cmp_count 1.000，db.filter_cmp_group_count 0.250，db.min_max 0.750，db.multi_filter_count 0.625
- none 非 target 五模式：db.filter_cmp_avg 0.750，db.filter_cmp_count 1.000，db.filter_cmp_group_count 0.250，db.min_max 0.750，db.multi_filter_count 0.750

复习池（coverage_ledger，只读计划）：

- e3b2_A_target_other：slots 21，filter_cmp_top 1，近邻 {'db.top_n': 0, 'db.filter_eq_count': 0, 'db.filter_eq_top': 0}，各族 token {'python': 2941, 'file': 4203, 'database': 350}，target_ids ['database-train-target_db_filter_top-000']
- e3b2_A_target_dbbg：slots 22，filter_cmp_top 1，近邻 {'db.top_n': 0, 'db.filter_eq_count': 0, 'db.filter_eq_top': 0}，各族 token {'file': 2461, 'database': 3061, 'python': 1971}，target_ids ['database-train-target_db_filter_top-000']
- ctrl_cal10：slots 23，filter_cmp_top 0，近邻 {'db.top_n': 0, 'db.filter_eq_count': 0, 'db.filter_eq_top': 0}，各族 token {'calendar': 7490}，target_ids []
- dose_db0：slots 23，filter_cmp_top 0，近邻 {'db.top_n': 1, 'db.filter_eq_count': 2, 'db.filter_eq_top': 0}，各族 token {'database': 3061, 'file': 2214, 'python': 2219}，target_ids ['file-train-e4_last_match-001', 'python-train-target_median_natural-027']
- dose_db1：slots 23，filter_cmp_top 1，近邻 {'db.top_n': 2, 'db.filter_eq_count': 0, 'db.filter_eq_top': 0}，各族 token {'database': 3061, 'file': 2214, 'python': 2219}，target_ids ['database-train-target_db_filter_top-000', 'file-train-e4_last_match-001', 'python-train-target_median_natural-027']
- tf25：slots 23，filter_cmp_top 1，近邻 {'db.top_n': 2, 'db.filter_eq_count': 2, 'db.filter_eq_top': 0}，各族 token {'database': 3573, 'file': 2495, 'python': 1426}，target_ids ['database-train-target_db_filter_top-000', 'file-train-e4_last_match-010', 'python-train-target_median_natural-019', 'python-train-target_median_natural-023']

## G. File / Python 旁证（预注册 §6）：目标模式 vs 同工具其它模式（B1）

### p2_file（目标模式 `file.search_last`）

| 臂 | 种子 | 目标模式 | 其它模式均值 | 各模式 |
|---|---|---|---|---|
| none | 08 | 0.000 | 0.667 | list_all 1.00，search_last 0.00，word_count 0.00，write_char_count 1.00 |
| none | 09 | 0.125 | 0.667 | list_all 1.00，search_last 0.12，word_count 0.00，write_char_count 1.00 |
| none | 10 | 0.375 | 0.667 | list_all 1.00，search_last 0.38，word_count 0.00，write_char_count 1.00 |
| tf00 | 08 | 0.250 | 0.667 | list_all 1.00，search_last 0.25，word_count 0.00，write_char_count 1.00 |
| tf00 | 09 | 0.875 | 0.667 | list_all 1.00，search_last 0.88，word_count 0.00，write_char_count 1.00 |
| tf00 | 10 | 0.375 | 0.667 | list_all 1.00，search_last 0.38，word_count 0.00，write_char_count 1.00 |
| tf25 | 08 | 0.375 | 0.667 | list_all 1.00，search_last 0.38，word_count 0.00，write_char_count 1.00 |
| tf25 | 09 | 0.250 | 0.667 | list_all 1.00，search_last 0.25，word_count 0.00，write_char_count 1.00 |
| tf25 | 10 | 0.500 | 0.667 | list_all 1.00，search_last 0.50，word_count 0.00，write_char_count 1.00 |
| tf50 | 08 | 0.500 | 0.667 | list_all 1.00，search_last 0.50，word_count 0.00，write_char_count 1.00 |
| tf50 | 09 | 0.500 | 0.667 | list_all 1.00，search_last 0.50，word_count 0.00，write_char_count 1.00 |
| tf50 | 10 | 0.500 | 0.667 | list_all 1.00，search_last 0.50，word_count 0.00，write_char_count 1.00 |
| dose_db6 | 08 | 0.000 | 0.667 | list_all 1.00，search_last 0.00，word_count 0.00，write_char_count 1.00 |
| dose_db6 | 09 | 0.250 | 0.667 | list_all 1.00，search_last 0.25，word_count 0.00，write_char_count 1.00 |
| dose_db6 | 10 | 0.375 | 0.667 | list_all 1.00，search_last 0.38，word_count 0.00，write_char_count 1.00 |

### p2_python（目标模式 `py.median`）

| 臂 | 种子 | 目标模式 | 其它模式均值 | 各模式 |
|---|---|---|---|---|
| none | 08 | 0.400 | 1.000 | correlation 1.00，mean 1.00，median 0.40，percentile 1.00，regression 1.00，std 1.00 |
| none | 09 | 0.000 | 1.000 | correlation 1.00，mean 1.00，median 0.00，percentile 1.00，regression 1.00，std 1.00 |
| none | 10 | 0.600 | 1.000 | correlation 1.00，mean 1.00，median 0.60，percentile 1.00，regression 1.00，std 1.00 |
| tf00 | 08 | 0.400 | 1.000 | correlation 1.00，mean 1.00，median 0.40，percentile 1.00，regression 1.00，std 1.00 |
| tf00 | 09 | 0.200 | 1.000 | correlation 1.00，mean 1.00，median 0.20，percentile 1.00，regression 1.00，std 1.00 |
| tf00 | 10 | 1.000 | 1.000 | correlation 1.00，mean 1.00，median 1.00，percentile 1.00，regression 1.00，std 1.00 |
| tf25 | 08 | 0.800 | 1.000 | correlation 1.00，mean 1.00，median 0.80，percentile 1.00，regression 1.00，std 1.00 |
| tf25 | 09 | 0.000 | 1.000 | correlation 1.00，mean 1.00，median 0.00，percentile 1.00，regression 1.00，std 1.00 |
| tf25 | 10 | 1.000 | 1.000 | correlation 1.00，mean 1.00，median 1.00，percentile 1.00，regression 1.00，std 1.00 |
| tf50 | 08 | 0.800 | 1.000 | correlation 1.00，mean 1.00，median 0.80，percentile 1.00，regression 1.00，std 1.00 |
| tf50 | 09 | 0.000 | 1.000 | correlation 1.00，mean 1.00，median 0.00，percentile 1.00，regression 1.00，std 1.00 |
| tf50 | 10 | 1.000 | 1.000 | correlation 1.00，mean 1.00，median 1.00，percentile 1.00，regression 1.00，std 1.00 |
| dose_db6 | 08 | 1.000 | 1.000 | correlation 1.00，mean 1.00，median 1.00，percentile 1.00，regression 1.00，std 1.00 |
| dose_db6 | 09 | 0.000 | 1.000 | correlation 1.00，mean 1.00，median 0.00，percentile 1.00，regression 1.00，std 1.00 |
| dose_db6 | 10 | 0.600 | 1.000 | correlation 1.00，mean 1.00，median 0.60，percentile 1.00，regression 1.00，std 1.00 |

### nat v2 File（search_last）/ Python（median）总分

| 臂 | nat File 08/09/10 | 均值 | nat Python 08/09/10 | 均值 |
|---|---|---|---|---|
| none | 0.000 / 0.433 / 0.733 | 0.389 | 0.467 / 1.000 / 0.800 | 0.756 |
| tf00 | 0.533 / 0.867 / 0.767 | 0.722 | 0.233 / 1.000 / 0.800 | 0.678 |
| tf25 | 0.633 / 0.700 / 0.767 | 0.700 | 1.000 / 1.000 / 1.000 | 1.000 |
| tf50 | 0.800 / 0.800 / 0.767 | 0.789 | 0.933 / 1.000 / 1.000 | 0.978 |
| dose_db6 | 0.533 / 0.767 / 0.767 | 0.689 | 0.967 / 1.000 / 1.000 | 0.989 |

