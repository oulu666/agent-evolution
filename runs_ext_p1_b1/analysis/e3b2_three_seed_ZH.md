# 实验 A（E3-B2）三种子结果（Protocol-B1）

生成：2026-11-13 18:25:38 +0800（Asia/Shanghai）。脚本 `scripts/p2_e3b2_three_seed.py`，只读 `summary.json`、B1 逐题结果和 `replay_plan.json`。

## 1. 主指标：nat v2 `db.filter_cmp_top` Joint Success（30 题）

| 臂 | 08 | 09 | 10 | 均值 | SD |
|---|---|---|---|---|---|
| e3b2_A_target_other | 0.100 | 0.200 | 0.067 | 0.122 | 0.069 |
| e3b2_A_target_dbbg | 0.100 | 0.233 | 0.000 | 0.111 | 0.117 |
| ctrl_cal10 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dose_db0 | 0.000 | 0.067 | 0.000 | 0.022 | 0.038 |
| dose_db1 | 0.033 | 0.267 | 0.000 | 0.100 | 0.145 |
| tf25 | 0.400 | 0.667 | 0.233 | 0.433 | 0.219 |
| none | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

## 2. 逐种子差（正/零/负 = 三种子里差 >0 / =0 / <0 的个数）

| 对比 | 08 | 09 | 10 | 均值 | 正/零/负 |
|---|---|---|---|---|---|
| e3b2_A_target_other − ctrl_cal10 | +0.100 | +0.200 | +0.067 | +0.122 | 3/0/0 |
| e3b2_A_target_other − dose_db0 | +0.100 | +0.133 | +0.067 | +0.100 | 3/0/0 |
| e3b2_A_target_dbbg − ctrl_cal10 | +0.100 | +0.233 | +0.000 | +0.111 | 2/1/0 |
| e3b2_A_target_dbbg − dose_db0 | +0.100 | +0.167 | +0.000 | +0.089 | 2/1/0 |
| e3b2_A_target_dbbg − e3b2_A_target_other | +0.000 | +0.033 | -0.067 | -0.011 | 1/1/1 |
| e3b2_A_target_other − dose_db1 | +0.067 | -0.067 | +0.067 | +0.022 | 2/0/1 |
| e3b2_A_target_dbbg − dose_db1 | +0.067 | -0.033 | +0.000 | +0.011 | 1/1/1 |
| tf25 − e3b2_A_target_other | +0.300 | +0.467 | +0.167 | +0.311 | 3/0/0 |
| tf25 − e3b2_A_target_dbbg | +0.300 | +0.433 | +0.233 | +0.322 | 3/0/0 |

## 3. 逐环节、复习池与副指标

| 种子 | 臂 | 主指标 | tool / args / final | 复习 slots | DB token | target 条目 | 近邻 slots(top_n, filter_eq_count, filter_eq_top) | 非 target 40 | nat Python | Calendar v3 | v3fix |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 08 | e3b2_A_target_other | 0.100 | 1.000 / 0.100 / 0.533 | 21 | 350 | target_db_filter_top-000 | 0, 0, 0 | 0.700 | 0.700 | 0.500 | 0.300 |
| 08 | e3b2_A_target_dbbg | 0.100 | 1.000 / 0.100 / 0.467 | 22 | 3061 | target_db_filter_top-000 | 0, 0, 0 | 0.700 | 0.867 | 0.507 | 0.267 |
| 08 | ctrl_cal10 | 0.000 | 1.000 / 0.000 / 0.467 | 23 | 0 | — | 0, 0, 0 | 0.675 | 0.433 | 0.520 | 0.267 |
| 08 | dose_db0 | 0.000 | 1.000 / 0.000 / 0.433 | 23 | 3061 | — | 1, 2, 0 | 0.700 | 0.933 | 0.527 | 0.300 |
| 08 | dose_db1 | 0.033 | 1.000 / 0.033 / 0.500 | 23 | 3061 | target_db_filter_top-000 | 2, 0, 0 | 0.650 | 0.933 | 0.493 | 0.300 |
| 08 | tf25 | 0.400 | 1.000 / 0.567 / 0.667 | 23 | 3573 | target_db_filter_top-000 | 2, 2, 0 | 0.675 | 1.000 | 0.487 | 0.300 |
| 08 | none | 0.000 | 1.000 / 0.000 / 0.467 | 0 | 0 | — | — | 0.700 | 0.467 | 0.533 | 0.267 |
| 09 | e3b2_A_target_other | 0.200 | 1.000 / 0.333 / 0.367 | 21 | 348 | target_db_filter_top-001 | 0, 0, 0 | 0.750 | 1.000 | 0.500 | 0.300 |
| 09 | e3b2_A_target_dbbg | 0.233 | 1.000 / 0.333 / 0.400 | 23 | 2692 | target_db_filter_top-001 | 0, 0, 0 | 0.700 | 1.000 | 0.500 | 0.333 |
| 09 | ctrl_cal10 | 0.000 | 1.000 / 0.000 / 0.300 | 22 | 0 | — | 0, 0, 0 | 0.700 | 1.000 | 0.513 | 0.300 |
| 09 | dose_db0 | 0.067 | 1.000 / 0.133 / 0.300 | 22 | 2692 | — | 0, 1, 0 | 0.750 | 1.000 | 0.520 | 0.300 |
| 09 | dose_db1 | 0.267 | 1.000 / 0.433 / 0.400 | 22 | 2691 | target_db_filter_top-001 | 0, 1, 0 | 0.750 | 1.000 | 0.487 | 0.300 |
| 09 | tf25 | 0.667 | 1.000 / 0.767 / 0.700 | 22 | 3027 | target_db_filter_top-005 | 1, 1, 0 | 0.700 | 1.000 | 0.527 | 0.300 |
| 09 | none | 0.000 | 1.000 / 0.000 / 0.300 | 0 | 0 | — | — | 0.750 | 1.000 | 0.507 | 0.300 |
| 10 | e3b2_A_target_other | 0.067 | 1.000 / 0.100 / 0.433 | 21 | 348 | target_db_filter_top-001 | 0, 0, 0 | 0.725 | 0.767 | 0.560 | 0.333 |
| 10 | e3b2_A_target_dbbg | 0.000 | 1.000 / 0.000 / 0.433 | 22 | 2691 | target_db_filter_top-001 | 0, 0, 0 | 0.375 | 0.833 | 0.573 | 0.333 |
| 10 | ctrl_cal10 | 0.000 | 1.000 / 0.000 / 0.433 | 22 | 0 | — | 0, 0, 0 | 0.575 | 0.767 | 0.573 | 0.333 |
| 10 | dose_db0 | 0.000 | 1.000 / 0.000 / 0.433 | 23 | 2692 | — | 3, 3, 0 | 0.700 | 0.933 | 0.573 | 0.367 |
| 10 | dose_db1 | 0.000 | 1.000 / 0.000 / 0.400 | 23 | 2692 | target_db_filter_top-001 | 1, 2, 0 | 0.600 | 1.000 | 0.567 | 0.367 |
| 10 | tf25 | 0.233 | 1.000 / 0.433 / 0.433 | 22 | 3526 | target_db_filter_top-008 | 3, 1, 0 | 0.700 | 1.000 | 0.600 | 0.367 |
| 10 | none | 0.000 | 1.000 / 0.000 / 0.433 | 0 | 0 | — | — | 0.675 | 0.800 | 0.567 | 0.300 |

## 4. 答对的题（题号后缀）

- 种子 08：other ['006', '017', '027']；dbbg ['006', '017', '027']；两臂共同 ['006', '017', '027']；dose_db1 ['027']；tf25 答对 12 题，其中含 other 的 3/3、dbbg 的 3/3。
- 种子 09：other ['004', '006', '017', '019', '027', '029']；dbbg ['004', '006', '017', '019', '022', '027', '029']；两臂共同 ['004', '006', '017', '019', '027', '029']；dose_db1 ['004', '005', '006', '017', '019', '020', '027', '029']；tf25 答对 20 题，其中含 other 的 6/6、dbbg 的 7/7。
- 种子 10：other ['006', '027']；dbbg —；两臂共同 —；dose_db1 —；tf25 答对 7 题，其中含 other 的 2/2、dbbg 的 0/0。

## 5. 非 target 五模式（探索记录，不进主结论）

| 种子 | 臂 | 各模式 |
|---|---|---|
| 08 | e3b2_A_target_other | db.filter_cmp_avg 0.750，db.filter_cmp_count 1.000，db.filter_cmp_group_count 0.250，db.min_max 0.750，db.multi_filter_count 0.750 |
| 08 | e3b2_A_target_dbbg | db.filter_cmp_avg 0.750，db.filter_cmp_count 1.000，db.filter_cmp_group_count 0.250，db.min_max 0.750，db.multi_filter_count 0.750 |
| 08 | none | db.filter_cmp_avg 0.750，db.filter_cmp_count 1.000，db.filter_cmp_group_count 0.250，db.min_max 0.750，db.multi_filter_count 0.750 |
| 09 | e3b2_A_target_other | db.filter_cmp_avg 0.750，db.filter_cmp_count 1.000，db.filter_cmp_group_count 0.000，db.min_max 1.000，db.multi_filter_count 1.000 |
| 09 | e3b2_A_target_dbbg | db.filter_cmp_avg 0.750，db.filter_cmp_count 1.000，db.filter_cmp_group_count 0.000，db.min_max 1.000，db.multi_filter_count 0.750 |
| 09 | none | db.filter_cmp_avg 0.750，db.filter_cmp_count 1.000，db.filter_cmp_group_count 0.000，db.min_max 1.000，db.multi_filter_count 1.000 |
| 10 | e3b2_A_target_other | db.filter_cmp_avg 0.750，db.filter_cmp_count 0.875，db.filter_cmp_group_count 0.000，db.min_max 1.000，db.multi_filter_count 1.000 |
| 10 | e3b2_A_target_dbbg | db.filter_cmp_avg 0.750，db.filter_cmp_count 0.125，db.filter_cmp_group_count 0.000，db.min_max 0.750，db.multi_filter_count 0.250 |
| 10 | none | db.filter_cmp_avg 0.750，db.filter_cmp_count 0.750，db.filter_cmp_group_count 0.000，db.min_max 1.000，db.multi_filter_count 0.875 |
