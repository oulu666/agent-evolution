# 真遗忘模式：复习能否恢复、需要多少（Protocol-B1）

生成：2026-11-13 18:22:48 +0800（Asia/Shanghai）。脚本 `scripts/p2_true_forgetting_analysis.py`，只读 B1 逐题结果与各 checkpoint 的 `replay_plan.json`；不含任何 B32 数字。

约定：正确率 = 该模式题目里 joint 成功的比例（natv2_file 用官方 lenient 规则，与 P1 一致）；`k/n` 为答对数/题数。复习条数 = 复习池中归入该模式的插入次数（slots，含重复），括号内为不同经验条数（unique）、input token 与训练模板拆分。参照点：Database/File 模式用 stage_02（T0），Python 模式用 stage_03（Python 刚学完）。T1 = `none`（学完 Calendar、无复习）。所有复习臂都从 stage_03 出发、在 Calendar 阶段插入复习，因此对 `db.list_tables`（stage_03 已经掉到 0）是「掉了以后再拉回」，对 `py.median`（Calendar 阶段才掉）是「边学边防掉」。题量 n < 5 标 ⚠。

## 1. 候选真遗忘模式（参照点高、T1 明显下降）

判定：参照点三种子均值 ≥ 0.6，且到 T1 均值下降 ≥ 0.2；扫描范围为 p2_database、p2_python、p2_file、natv2_database、natv2_python、natv2_file、db_nontarget 的全部模式。

| suite | 模式 | n | 不同题面数 | 参照点 | 参照 08/09/10 | T1 none 08/09/10 | 三种子都下降 |
|---|---|---|---|---|---|---|---|
| natv2_python | py.median | 30 | 30 | stage_03_python | 0.967 / 0.933 / 1.000 | 0.467 / 1.000 / 0.800 | 否 |
| p2_database | db.list_tables | 6 | 1 | stage_02_database | 1.000 / 1.000 / 1.000 | 0.000 / 0.000 / 0.000 | 是 |
| p2_python | py.median | 5 | 5 | stage_03_python | 1.000 / 1.000 / 1.000 | 0.400 / 0.000 / 0.600 | 是 |

除这三项外没有其它旧工具模式满足判定。全部模式的 T0 / stage_03 / T1 / stage_04 见 JSON `timeline`。

## 2. `db.list_tables`（p2_database）

测试题：n=6，不同题面 1 个，模板 db_list_tables_test；例：「What tables are available in the read-only database? Return a JSON list.」。参照点 stage_02_database：1.000 / 1.000 / 1.000。

复习池里该模式的训练模板：`db_list_tables`「List every table name in the database. Return a JSON list.」。

| 臂 | 08 k/n | 09 k/n | 10 k/n | 三种子均值 | 复习条数 08 | 09 | 10 |
|---|---|---|---|---|---|---|---|
| stage_02_database | 6/6 | 6/6 | 6/6 | 1.000 | — | — | — |
| stage_03_python | 0/6 | 0/6 | 0/6 | 0.000 | — | — | — |
| stage_04_calendar | 0/6 | 0/6 | 0/6 | 0.000 | — | — | — |
| none | 0/6 | 0/6 | 0/6 | 0.000 | 0（0，0 tok） | 0（0，0 tok） | 0（0，0 tok） |
| ctrl_cal10 | 0/6 | 0/6 | 0/6 | 0.000 | 0（0，0 tok） | 0（0，0 tok） | 0（0，0 tok） |
| ctrl_cal20 | 0/6 | 0/6 | 0/6 | 0.000 | 0（0，0 tok） | 0（0，0 tok） | 0（0，0 tok） |
| tf00 | 6/6 | 6/6 | 0/6 | 0.667 | 3（2，816 tok；db_list_tables 3） | 1（1，272 tok；db_list_tables 1） | 0（0，0 tok） |
| tf25 | 0/6 | 6/6 | 0/6 | 0.333 | 1（1，272 tok；db_list_tables 1） | 1（1，272 tok；db_list_tables 1） | 0（0，0 tok） |
| tf50 | 6/6 | 6/6 | 0/6 | 0.667 | 1（1，272 tok；db_list_tables 1） | 1（1，272 tok；db_list_tables 1） | 1（1，272 tok；db_list_tables 1） |
| b20_tf50 | 6/6 | 6/6 | 0/6 | 0.667 | 3（3，816 tok；db_list_tables 3） | 1（1，272 tok；db_list_tables 1） | 0（0，0 tok） |
| dose_db0 | 0/6 | 0/6 | 6/6 | 0.333 | 0（0，0 tok） | 0（0，0 tok） | 2（2，544 tok；db_list_tables 2） |
| dose_db1 | 6/6 | 0/6 | 6/6 | 0.667 | 2（1，544 tok；db_list_tables 2） | 0（0，0 tok） | 3（2，816 tok；db_list_tables 3） |
| dose_db6 | 0/6 | 0/6 | 0/6 | 0.000 | 0（0，0 tok） | 0（0，0 tok） | 0（0，0 tok） |
| e3b2_A_target_other | 0/6 | 0/6 | 0/6 | 0.000 | 0（0，0 tok） | 0（0，0 tok） | 0（0，0 tok） |
| e3b2_A_target_dbbg | 0/6 | 6/6 | 6/6 | 0.667 | 0（0，0 tok） | 3（2，816 tok；db_list_tables 3） | 2（2，544 tok；db_list_tables 2） |

逐环节（tool / arguments / final / 主指标，答对数）与失败形态：

| 臂 | 种子 | tool | args | final | 主指标 | 失败时的预测（次数） |
|---|---|---|---|---|---|---|
| stage_02_database | 08 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| stage_02_database | 09 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| stage_02_database | 10 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| stage_03_python | 08 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| stage_03_python | 09 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| stage_03_python | 10 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| stage_04_calendar | 08 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| stage_04_calendar | 09 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| stage_04_calendar | 10 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| none | 08 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| none | 09 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| none | 10 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| ctrl_cal10 | 08 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| ctrl_cal10 | 09 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| ctrl_cal10 | 10 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| ctrl_cal20 | 08 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| ctrl_cal20 | 09 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| ctrl_cal20 | 10 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| tf00 | 08 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| tf00 | 09 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| tf00 | 10 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| tf25 | 08 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| tf25 | 09 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| tf25 | 10 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| tf50 | 08 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| tf50 | 09 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| tf50 | 10 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| b20_tf50 | 08 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| b20_tf50 | 09 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| b20_tf50 | 10 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| dose_db0 | 08 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| dose_db0 | 09 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| dose_db0 | 10 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| dose_db1 | 08 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| dose_db1 | 09 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| dose_db1 | 10 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| dose_db6 | 08 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| dose_db6 | 09 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| dose_db6 | 10 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| e3b2_A_target_other | 08 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| e3b2_A_target_other | 09 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| e3b2_A_target_other | 10 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| e3b2_A_target_dbbg | 08 | 6/6 | 0/6 | 6/6 | 0/6 | db_list_tables {"database": "read-only"} ×6 |
| e3b2_A_target_dbbg | 09 | 6/6 | 6/6 | 6/6 | 6/6 | — |
| e3b2_A_target_dbbg | 10 | 6/6 | 6/6 | 6/6 | 6/6 | — |

### 复习条数 vs 正确率（每个点 = 一个臂×种子，含 none 与 Calendar 对照；无 B1 结果的臂不计）

| 复习条数 | 点数 | 完全恢复(=1.0)点数 | 仍为 0 的点数 | 平均正确率 | 各点 |
|---|---|---|---|---|---|
| 0 | 22 | 0 | 22 | 0.000 | none/08=0.000，none/09=0.000，none/10=0.000，ctrl_cal10/08=0.000，ctrl_cal10/09=0.000，ctrl_cal10/10=0.000，ctrl_cal20/08=0.000，ctrl_cal20/09=0.000，ctrl_cal20/10=0.000，tf00/10=0.000，tf25/10=0.000，b20_tf50/10=0.000，dose_db0/08=0.000，dose_db0/09=0.000，dose_db1/09=0.000，dose_db6/08=0.000，dose_db6/09=0.000，dose_db6/10=0.000，e3b2_A_target_other/08=0.000，e3b2_A_target_other/09=0.000，e3b2_A_target_other/10=0.000，e3b2_A_target_dbbg/08=0.000 |
| 1 | 7 | 5 | 2 | 0.714 | tf00/09=1.000，tf25/08=0.000，tf25/09=1.000，tf50/08=1.000，tf50/09=1.000，tf50/10=0.000，b20_tf50/09=1.000 |
| 2 | 3 | 3 | 0 | 1.000 | dose_db0/10=1.000，dose_db1/08=1.000，e3b2_A_target_dbbg/10=1.000 |
| 3 | 4 | 4 | 0 | 1.000 | tf00/08=1.000，b20_tf50/08=1.000，dose_db1/10=1.000，e3b2_A_target_dbbg/09=1.000 |

### 每个种子：none 与有复习条目的臂

| 种子 | none | 有复习条目的臂（个数） | 均值 | 高于/等于/低于 none |
|---|---|---|---|---|
| 08 | 0.000 | 5 | 0.800 | 4/1/0 |
| 09 | 0.000 | 5 | 1.000 | 5/0/0 |
| 10 | 0.000 | 4 | 0.750 | 3/1/0 |

## 3. `py.median`（p2_python）

测试题：n=5，不同题面 5 个，模板 stats_median_prose；例：「The observations are 94, 74, 87, 89, 75, 84, 96. What is the middle value?」。参照点 stage_03_python：1.000 / 1.000 / 1.000。

复习池里该模式的训练模板：`stats_median`「Compute the median of the numbers [16, 18, 14, 27, 37, 31, 35].」；`target_median_natural`「The observations are 16, 18, 14, 27, 37, 31, 35. After ordering them from smalle」。

| 臂 | 08 k/n | 09 k/n | 10 k/n | 三种子均值 | 复习条数 08 | 09 | 10 |
|---|---|---|---|---|---|---|---|
| stage_02_database | 5/5 | 5/5 | 5/5 | 1.000 | — | — | — |
| stage_03_python | 5/5 | 5/5 | 5/5 | 1.000 | — | — | — |
| stage_04_calendar | 3/5 | 1/5 | 4/5 | 0.533 | — | — | — |
| none | 2/5 | 0/5 | 3/5 | 0.333 | 0（0，0 tok） | 0（0，0 tok） | 0（0，0 tok） |
| ctrl_cal10 | 2/5 | 0/5 | 3/5 | 0.333 | 0（0，0 tok） | 0（0，0 tok） | 0（0，0 tok） |
| ctrl_cal20 | 3/5 | 0/5 | 3/5 | 0.400 | 0（0，0 tok） | 0（0，0 tok） | 0（0，0 tok） |
| tf00 | 2/5 | 1/5 | 5/5 | 0.533 | 1（1，347 tok；stats_median 1） | 1（1，361 tok；target_median_natural 1） | 1（1，347 tok；stats_median 1） |
| tf25 | 4/5 | 0/5 | 5/5 | 0.600 | 3（3，1069 tok；stats_median 1，target_median_natural 2） | 2（2，708 tok；stats_median 1，target_median_natural 1） | 2（2，722 tok；target_median_natural 2） |
| tf50 | 4/5 | 0/5 | 5/5 | 0.600 | 2（2，708 tok；stats_median 1，target_median_natural 1） | 4（4，1416 tok；stats_median 2，target_median_natural 2） | 4（4，1430 tok；stats_median 1，target_median_natural 3） |
| b20_tf50 | 5/5 | 1/5 | 5/5 | 0.733 | 4（4，1430 tok；stats_median 1，target_median_natural 3） | 8（4，2818 tok；stats_median 5，target_median_natural 3） | 5（5，1791 tok；stats_median 1，target_median_natural 4） |
| dose_db0 | 4/5 | 0/5 | 3/5 | 0.467 | 4（4，1402 tok；stats_median 3，target_median_natural 1） | 4（4，1416 tok；stats_median 2，target_median_natural 2） | 4（4，1416 tok；stats_median 2，target_median_natural 2） |
| dose_db1 | 4/5 | 0/5 | 3/5 | 0.467 | 4（4，1402 tok；stats_median 3，target_median_natural 1） | 4（4，1416 tok；stats_median 2，target_median_natural 2） | 4（4，1416 tok；stats_median 2，target_median_natural 2） |
| dose_db6 | 5/5 | 0/5 | 3/5 | 0.533 | 4（4，1402 tok；stats_median 3，target_median_natural 1） | 4（4，1416 tok；stats_median 2，target_median_natural 2） | 4（4，1416 tok；stats_median 2，target_median_natural 2） |
| e3b2_A_target_other | 3/5 | 0/5 | 2/5 | 0.333 | 2（2，694 tok；stats_median 2） | 4（3，1388 tok；stats_median 4） | 1（1，347 tok；stats_median 1） |
| e3b2_A_target_dbbg | 4/5 | 1/5 | 1/5 | 0.400 | 2（2，694 tok；stats_median 2） | 3（3，1041 tok；stats_median 3） | 2（2，694 tok；stats_median 2） |

逐环节（tool / arguments / final / 主指标，答对数）与失败形态：

| 臂 | 种子 | tool | args | final | 主指标 | 失败时的预测（次数） |
|---|---|---|---|---|---|---|
| stage_02_database | 08 | 5/5 | 5/5 | 5/5 | 5/5 | — |
| stage_02_database | 09 | 5/5 | 5/5 | 5/5 | 5/5 | — |
| stage_02_database | 10 | 5/5 | 5/5 | 5/5 | 5/5 | — |
| stage_03_python | 08 | 5/5 | 5/5 | 5/5 | 5/5 | — |
| stage_03_python | 09 | 5/5 | 5/5 | 5/5 | 5/5 | — |
| stage_03_python | 10 | 5/5 | 5/5 | 5/5 | 5/5 | — |
| stage_04_calendar | 08 | 3/5 | 5/5 | 3/5 | 3/5 | stats_mean {"values": "..."} ×2 |
| stage_04_calendar | 09 | 1/5 | 5/5 | 2/5 | 1/5 | stats_mean {"values": "..."} ×4 |
| stage_04_calendar | 10 | 4/5 | 5/5 | 4/5 | 4/5 | stats_mean {"values": "..."} ×1 |
| none | 08 | 2/5 | 5/5 | 2/5 | 2/5 | stats_mean {"values": "..."} ×3 |
| none | 09 | 0/5 | 5/5 | 1/5 | 0/5 | stats_mean {"values": "..."} ×5 |
| none | 10 | 3/5 | 5/5 | 3/5 | 3/5 | stats_mean {"values": "..."} ×2 |
| ctrl_cal10 | 08 | 2/5 | 5/5 | 2/5 | 2/5 | stats_mean {"values": "..."} ×3 |
| ctrl_cal10 | 09 | 0/5 | 5/5 | 1/5 | 0/5 | stats_mean {"values": "..."} ×5 |
| ctrl_cal10 | 10 | 3/5 | 5/5 | 3/5 | 3/5 | stats_mean {"values": "..."} ×2 |
| ctrl_cal20 | 08 | 3/5 | 5/5 | 3/5 | 3/5 | stats_mean {"values": "..."} ×2 |
| ctrl_cal20 | 09 | 0/5 | 5/5 | 1/5 | 0/5 | stats_mean {"values": "..."} ×5 |
| ctrl_cal20 | 10 | 3/5 | 5/5 | 3/5 | 3/5 | stats_mean {"values": "..."} ×2 |
| tf00 | 08 | 2/5 | 5/5 | 2/5 | 2/5 | stats_mean {"values": "..."} ×3 |
| tf00 | 09 | 1/5 | 5/5 | 2/5 | 1/5 | stats_mean {"values": "..."} ×4 |
| tf00 | 10 | 5/5 | 5/5 | 5/5 | 5/5 | — |
| tf25 | 08 | 4/5 | 5/5 | 4/5 | 4/5 | stats_mean {"values": "..."} ×1 |
| tf25 | 09 | 0/5 | 5/5 | 1/5 | 0/5 | stats_mean {"values": "..."} ×5 |
| tf25 | 10 | 5/5 | 5/5 | 5/5 | 5/5 | — |
| tf50 | 08 | 4/5 | 5/5 | 4/5 | 4/5 | stats_mean {"values": "..."} ×1 |
| tf50 | 09 | 0/5 | 5/5 | 1/5 | 0/5 | stats_mean {"values": "..."} ×5 |
| tf50 | 10 | 5/5 | 5/5 | 5/5 | 5/5 | — |
| b20_tf50 | 08 | 5/5 | 5/5 | 5/5 | 5/5 | — |
| b20_tf50 | 09 | 1/5 | 5/5 | 2/5 | 1/5 | stats_mean {"values": "..."} ×4 |
| b20_tf50 | 10 | 5/5 | 5/5 | 5/5 | 5/5 | — |
| dose_db0 | 08 | 4/5 | 5/5 | 4/5 | 4/5 | stats_mean {"values": "..."} ×1 |
| dose_db0 | 09 | 0/5 | 5/5 | 1/5 | 0/5 | stats_mean {"values": "..."} ×5 |
| dose_db0 | 10 | 3/5 | 5/5 | 3/5 | 3/5 | stats_mean {"values": "..."} ×2 |
| dose_db1 | 08 | 4/5 | 5/5 | 4/5 | 4/5 | stats_mean {"values": "..."} ×1 |
| dose_db1 | 09 | 0/5 | 5/5 | 1/5 | 0/5 | stats_mean {"values": "..."} ×5 |
| dose_db1 | 10 | 3/5 | 5/5 | 3/5 | 3/5 | stats_mean {"values": "..."} ×2 |
| dose_db6 | 08 | 5/5 | 5/5 | 5/5 | 5/5 | — |
| dose_db6 | 09 | 0/5 | 5/5 | 1/5 | 0/5 | stats_mean {"values": "..."} ×5 |
| dose_db6 | 10 | 3/5 | 5/5 | 3/5 | 3/5 | stats_mean {"values": "..."} ×2 |
| e3b2_A_target_other | 08 | 3/5 | 5/5 | 3/5 | 3/5 | stats_mean {"values": "..."} ×2 |
| e3b2_A_target_other | 09 | 0/5 | 5/5 | 1/5 | 0/5 | stats_mean {"values": "..."} ×5 |
| e3b2_A_target_other | 10 | 2/5 | 5/5 | 2/5 | 2/5 | stats_mean {"values": "..."} ×3 |
| e3b2_A_target_dbbg | 08 | 4/5 | 5/5 | 4/5 | 4/5 | stats_mean {"values": "..."} ×1 |
| e3b2_A_target_dbbg | 09 | 1/5 | 5/5 | 2/5 | 1/5 | stats_mean {"values": "..."} ×4 |
| e3b2_A_target_dbbg | 10 | 1/5 | 5/5 | 1/5 | 1/5 | stats_mean {"values": "..."} ×4 |

### 复习条数 vs 正确率（每个点 = 一个臂×种子，含 none 与 Calendar 对照；无 B1 结果的臂不计）

| 复习条数 | 点数 | 完全恢复(=1.0)点数 | 仍为 0 的点数 | 平均正确率 | 各点 |
|---|---|---|---|---|---|
| 0 | 9 | 0 | 3 | 0.356 | none/08=0.400，none/09=0.000，none/10=0.600，ctrl_cal10/08=0.400，ctrl_cal10/09=0.000，ctrl_cal10/10=0.600，ctrl_cal20/08=0.600，ctrl_cal20/09=0.000，ctrl_cal20/10=0.600 |
| 1 | 4 | 1 | 0 | 0.500 | tf00/08=0.400，tf00/09=0.200，tf00/10=1.000，e3b2_A_target_other/10=0.400 |
| 2 | 6 | 1 | 1 | 0.567 | tf25/09=0.000，tf25/10=1.000，tf50/08=0.800，e3b2_A_target_other/08=0.600，e3b2_A_target_dbbg/08=0.800，e3b2_A_target_dbbg/10=0.200 |
| 3 | 2 | 0 | 0 | 0.500 | tf25/08=0.800，e3b2_A_target_dbbg/09=0.200 |
| 4 | 13 | 3 | 5 | 0.492 | tf50/09=0.000，tf50/10=1.000，b20_tf50/08=1.000，dose_db0/08=0.800，dose_db0/09=0.000，dose_db0/10=0.600，dose_db1/08=0.800，dose_db1/09=0.000，dose_db1/10=0.600，dose_db6/08=1.000，dose_db6/09=0.000，dose_db6/10=0.600，e3b2_A_target_other/09=0.000 |
| 5 | 1 | 1 | 0 | 1.000 | b20_tf50/10=1.000 |
| 8 | 1 | 0 | 0 | 0.200 | b20_tf50/09=0.200 |

### 每个种子：none 与有复习条目的臂

| 种子 | none | 有复习条目的臂（个数） | 均值 | 高于/等于/低于 none |
|---|---|---|---|---|
| 08 | 0.400 | 9 | 0.778 | 8/1/0 |
| 09 | 0.000 | 9 | 0.067 | 3/6/0 |
| 10 | 0.600 | 9 | 0.711 | 4/3/2 |

### 按复习模板拆分（只列有该模式复习条目的臂）

- 种子 08：含 stats_median → tf00=0.400，e3b2_A_target_other=0.600，e3b2_A_target_dbbg=0.800；含 stats_median+target_median_natural → tf25=0.800，tf50=0.800，b20_tf50=1.000，dose_db0=0.800，dose_db1=0.800，dose_db6=1.000
- 种子 09：含 stats_median → e3b2_A_target_other=0.000，e3b2_A_target_dbbg=0.200；含 stats_median+target_median_natural → tf25=0.000，tf50=0.000，b20_tf50=0.200，dose_db0=0.000，dose_db1=0.000，dose_db6=0.000；含 target_median_natural → tf00=0.200
- 种子 10：含 stats_median → tf00=1.000，e3b2_A_target_other=0.400，e3b2_A_target_dbbg=0.200；含 stats_median+target_median_natural → tf50=1.000，b20_tf50=1.000，dose_db0=0.600，dose_db1=0.600，dose_db6=0.600；含 target_median_natural → tf25=1.000

## 4. `py.median`（natv2_python）

测试题：n=30，不同题面 30 个，模板 target_median_natural；例：「The observations are [32, 12, 26, 56, 91, 11, 68]. After ordering them from smallest to largest, what is the value in the middle position?」。参照点 stage_03_python：0.967 / 0.933 / 1.000。

复习池里该模式的训练模板：`stats_median`「Compute the median of the numbers [16, 18, 14, 27, 37, 31, 35].」；`target_median_natural`「The observations are 16, 18, 14, 27, 37, 31, 35. After ordering them from smalle」。

| 臂 | 08 k/n | 09 k/n | 10 k/n | 三种子均值 | 复习条数 08 | 09 | 10 |
|---|---|---|---|---|---|---|---|
| stage_02_database | 29/30 | 19/30 | 30/30 | 0.867 | — | — | — |
| stage_03_python | 29/30 | 28/30 | 30/30 | 0.967 | — | — | — |
| stage_04_calendar | 15/30 | 30/30 | 28/30 | 0.811 | — | — | — |
| none | 14/30 | 30/30 | 24/30 | 0.756 | 0（0，0 tok） | 0（0，0 tok） | 0（0，0 tok） |
| ctrl_cal10 | 13/30 | 30/30 | 23/30 | 0.733 | 0（0，0 tok） | 0（0，0 tok） | 0（0，0 tok） |
| ctrl_cal20 | 7/30 | 30/30 | 23/30 | 0.667 | 0（0，0 tok） | 0（0，0 tok） | 0（0，0 tok） |
| tf00 | 7/30 | 30/30 | 24/30 | 0.678 | 1（1，347 tok；stats_median 1） | 1（1，361 tok；target_median_natural 1） | 1（1，347 tok；stats_median 1） |
| tf25 | 30/30 | 30/30 | 30/30 | 1.000 | 3（3，1069 tok；stats_median 1，target_median_natural 2） | 2（2，708 tok；stats_median 1，target_median_natural 1） | 2（2，722 tok；target_median_natural 2） |
| tf50 | 28/30 | 30/30 | 30/30 | 0.978 | 2（2，708 tok；stats_median 1，target_median_natural 1） | 4（4，1416 tok；stats_median 2，target_median_natural 2） | 4（4，1430 tok；stats_median 1，target_median_natural 3） |
| b20_tf50 | 30/30 | 30/30 | 26/30 | 0.956 | 4（4，1430 tok；stats_median 1，target_median_natural 3） | 8（4，2818 tok；stats_median 5，target_median_natural 3） | 5（5，1791 tok；stats_median 1，target_median_natural 4） |
| dose_db0 | 28/30 | 30/30 | 28/30 | 0.956 | 4（4，1402 tok；stats_median 3，target_median_natural 1） | 4（4，1416 tok；stats_median 2，target_median_natural 2） | 4（4，1416 tok；stats_median 2，target_median_natural 2） |
| dose_db1 | 28/30 | 30/30 | 30/30 | 0.978 | 4（4，1402 tok；stats_median 3，target_median_natural 1） | 4（4，1416 tok；stats_median 2，target_median_natural 2） | 4（4，1416 tok；stats_median 2，target_median_natural 2） |
| dose_db6 | 29/30 | 30/30 | 30/30 | 0.989 | 4（4，1402 tok；stats_median 3，target_median_natural 1） | 4（4，1416 tok；stats_median 2，target_median_natural 2） | 4（4，1416 tok；stats_median 2，target_median_natural 2） |
| e3b2_A_target_other | 21/30 | 30/30 | 23/30 | 0.822 | 2（2，694 tok；stats_median 2） | 4（3，1388 tok；stats_median 4） | 1（1，347 tok；stats_median 1） |
| e3b2_A_target_dbbg | 26/30 | 30/30 | 25/30 | 0.900 | 2（2，694 tok；stats_median 2） | 3（3，1041 tok；stats_median 3） | 2（2，694 tok；stats_median 2） |

逐环节（tool / arguments / final / 主指标，答对数）与失败形态：

| 臂 | 种子 | tool | args | final | 主指标 | 失败时的预测（次数） |
|---|---|---|---|---|---|---|
| stage_02_database | 08 | 30/30 | 29/30 | 30/30 | 29/30 | stats_median {"values": "..."} ×1 |
| stage_02_database | 09 | 19/30 | 19/30 | 24/30 | 19/30 | None {} ×11 |
| stage_02_database | 10 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| stage_03_python | 08 | 30/30 | 29/30 | 30/30 | 29/30 | stats_median {"values": "..."} ×1 |
| stage_03_python | 09 | 28/30 | 28/30 | 28/30 | 28/30 | stats_percentile {"values": "..."} ×2 |
| stage_03_python | 10 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| stage_04_calendar | 08 | 17/30 | 27/30 | 17/30 | 15/30 | stats_sorted {"values": "..."} ×13；stats_median {"values": "..."} ×2 |
| stage_04_calendar | 09 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| stage_04_calendar | 10 | 30/30 | 28/30 | 30/30 | 28/30 | stats_median {"values": "..."} ×2 |
| none | 08 | 14/30 | 29/30 | 15/30 | 14/30 | stats_sorted {"values": "..."} ×16 |
| none | 09 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| none | 10 | 30/30 | 24/30 | 29/30 | 24/30 | stats_median {"values": "..."} ×6 |
| ctrl_cal10 | 08 | 14/30 | 28/30 | 14/30 | 13/30 | stats_sorted {"values": "..."} ×16；stats_median {"values": "..."} ×1 |
| ctrl_cal10 | 09 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| ctrl_cal10 | 10 | 30/30 | 23/30 | 29/30 | 23/30 | stats_median {"values": "..."} ×7 |
| ctrl_cal20 | 08 | 7/30 | 28/30 | 10/30 | 7/30 | stats_sorted {"values": "..."} ×23 |
| ctrl_cal20 | 09 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| ctrl_cal20 | 10 | 30/30 | 23/30 | 28/30 | 23/30 | stats_median {"values": "..."} ×7 |
| tf00 | 08 | 7/30 | 29/30 | 8/30 | 7/30 | stats_sorted {"values": "..."} ×23 |
| tf00 | 09 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| tf00 | 10 | 30/30 | 24/30 | 29/30 | 24/30 | stats_median {"values": "..."} ×6 |
| tf25 | 08 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| tf25 | 09 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| tf25 | 10 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| tf50 | 08 | 30/30 | 28/30 | 30/30 | 28/30 | stats_median {"values": "..."} ×2 |
| tf50 | 09 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| tf50 | 10 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| b20_tf50 | 08 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| b20_tf50 | 09 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| b20_tf50 | 10 | 30/30 | 26/30 | 30/30 | 26/30 | stats_median {"values": "..."} ×4 |
| dose_db0 | 08 | 30/30 | 28/30 | 30/30 | 28/30 | stats_median {"values": "..."} ×2 |
| dose_db0 | 09 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| dose_db0 | 10 | 30/30 | 28/30 | 30/30 | 28/30 | stats_median {"values": "..."} ×2 |
| dose_db1 | 08 | 30/30 | 28/30 | 30/30 | 28/30 | stats_median {"values": "..."} ×2 |
| dose_db1 | 09 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| dose_db1 | 10 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| dose_db6 | 08 | 30/30 | 29/30 | 30/30 | 29/30 | stats_median {"values": "..."} ×1 |
| dose_db6 | 09 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| dose_db6 | 10 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| e3b2_A_target_other | 08 | 23/30 | 28/30 | 24/30 | 21/30 | stats_sorted {"values": "..."} ×7；stats_median {"values": "..."} ×2 |
| e3b2_A_target_other | 09 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| e3b2_A_target_other | 10 | 30/30 | 23/30 | 28/30 | 23/30 | stats_median {"values": "..."} ×7 |
| e3b2_A_target_dbbg | 08 | 28/30 | 28/30 | 29/30 | 26/30 | stats_median {"values": "..."} ×2；stats_sorted {"values": "..."} ×2 |
| e3b2_A_target_dbbg | 09 | 30/30 | 30/30 | 30/30 | 30/30 | — |
| e3b2_A_target_dbbg | 10 | 30/30 | 25/30 | 30/30 | 25/30 | stats_median {"values": "..."} ×5 |

### 复习条数 vs 正确率（每个点 = 一个臂×种子，含 none 与 Calendar 对照；无 B1 结果的臂不计）

| 复习条数 | 点数 | 完全恢复(=1.0)点数 | 仍为 0 的点数 | 平均正确率 | 各点 |
|---|---|---|---|---|---|
| 0 | 9 | 3 | 0 | 0.719 | none/08=0.467，none/09=1.000，none/10=0.800，ctrl_cal10/08=0.433，ctrl_cal10/09=1.000，ctrl_cal10/10=0.767，ctrl_cal20/08=0.233，ctrl_cal20/09=1.000，ctrl_cal20/10=0.767 |
| 1 | 4 | 1 | 0 | 0.700 | tf00/08=0.233，tf00/09=1.000，tf00/10=0.800，e3b2_A_target_other/10=0.767 |
| 2 | 6 | 2 | 0 | 0.889 | tf25/09=1.000，tf25/10=1.000，tf50/08=0.933，e3b2_A_target_other/08=0.700，e3b2_A_target_dbbg/08=0.867，e3b2_A_target_dbbg/10=0.833 |
| 3 | 2 | 2 | 0 | 1.000 | tf25/08=1.000，e3b2_A_target_dbbg/09=1.000 |
| 4 | 13 | 9 | 0 | 0.982 | tf50/09=1.000，tf50/10=1.000，b20_tf50/08=1.000，dose_db0/08=0.933，dose_db0/09=1.000，dose_db0/10=0.933，dose_db1/08=0.933，dose_db1/09=1.000，dose_db1/10=1.000，dose_db6/08=0.967，dose_db6/09=1.000，dose_db6/10=1.000，e3b2_A_target_other/09=1.000 |
| 5 | 1 | 0 | 0 | 0.867 | b20_tf50/10=0.867 |
| 8 | 1 | 1 | 0 | 1.000 | b20_tf50/09=1.000 |

### 每个种子：none 与有复习条目的臂

| 种子 | none | 有复习条目的臂（个数） | 均值 | 高于/等于/低于 none |
|---|---|---|---|---|
| 08 | 0.467 | 9 | 0.841 | 8/0/1 |
| 09 | 1.000 | 9 | 1.000 | 0/9/0 |
| 10 | 0.800 | 9 | 0.911 | 7/1/1 |

### 按复习模板拆分（只列有该模式复习条目的臂）

- 种子 08：含 stats_median → tf00=0.233，e3b2_A_target_other=0.700，e3b2_A_target_dbbg=0.867；含 stats_median+target_median_natural → tf25=1.000，tf50=0.933，b20_tf50=1.000，dose_db0=0.933，dose_db1=0.933，dose_db6=0.967
- 种子 09：含 stats_median → e3b2_A_target_other=1.000，e3b2_A_target_dbbg=1.000；含 stats_median+target_median_natural → tf25=1.000，tf50=1.000，b20_tf50=1.000，dose_db0=1.000，dose_db1=1.000，dose_db6=1.000；含 target_median_natural → tf00=1.000
- 种子 10：含 stats_median → tf00=0.800，e3b2_A_target_other=0.767，e3b2_A_target_dbbg=0.833；含 stats_median+target_median_natural → tf50=1.000，b20_tf50=0.867，dose_db0=0.933，dose_db1=1.000，dose_db6=1.000；含 target_median_natural → tf25=1.000

## 5. 结论（方向性描述，不做显著性陈述）

**`db.list_tables`（p2_database）**

- 遗忘形态：stage_02 之后（stage_03、stage_04、none）三种子都是 tool 6/6、final 6/6、arguments 0/6，失败全部是给 `db_list_tables` 多加了参数 `{"database": "read-only"}`（应为 `{}`）。也就是说掉的是「无参调用」这个格式，选工具和最终答案都没掉。论文里如果用 final-answer 口径，这个模式不算遗忘；用 joint 口径才算。
- 题量：6 题但只有 1 个不同题面，所以每个臂×种子的结果实际上是全对或全错，有效样本接近 1 题。⚠
- 复习：复习池里没有该模式条目的臂×种子 22 个，完全恢复 0 个（包括 Calendar 对照、none，以及 dose_db6——它把 `db.filter_cmp_top` 拉到 1.000，这里仍为 0，说明恢复只对被复习的模式起作用）。有 1 条的 7 个，完全恢复 5 个；有 2 条及以上的 7 个，完全恢复 7 个。
- 三种子：种子 08 有条目的臂 5 个，高于 none 4 个；种子 09 有条目的臂 5 个，高于 none 5 个；种子 10 有条目的臂 4 个，高于 none 3 个。三种子方向一致：有该模式复习条目就能恢复，没有就不恢复。
- 需要多少：1 条（约 272 input token）多数情况下已经够；2–3 条在已观测的点上全部恢复。没有观测到需要更多条的情况。

**`py.median`（p2_python，「middle value」措辞，每点 5 题）**

- 遗忘形态：失败基本都是把 `stats_median` 换成了 `stats_mean`（选错工具），参数都对。
- 复习：种子 08 none 0.400，有条目的臂 9 个、均值 0.778、高于/等于/低于 none = 8/1/0；种子 09 none 0.000，有条目的臂 9 个、均值 0.067、高于/等于/低于 none = 3/6/0；种子 10 none 0.600，有条目的臂 9 个、均值 0.711、高于/等于/低于 none = 4/3/2。
- 判断：种子 08、10 方向一致向上（没有一个复习臂低于 none）；种子 09 基本不恢复（none 0/5，复习臂最高 1/5）。**三种子方向不一致**。复习条数和恢复程度对不上：4 条的点平均 0.492，2 条的点平均 0.567。复习池里的两种模板（`stats_median`「Compute the median…」、`target_median_natural`「…middle position」）都不是测试的「middle value」措辞，这里的恢复更像是部分迁移，而不是条数够了就回来。每点 5 题，单点差 1 题即 0.2。

**`py.median`（natv2_python，30 题，与 `target_median_natural` 同模板）**

- 遗忘只在部分种子出现：stage_03 → none，种子 08 29/30 → 14/30（失败主要是调用不存在的 `stats_sorted`），种子 10 30/30 → 24/30（工具对、参数错），种子 09 28/30 → 30/30（没有遗忘）。
- 复习：种子 08 none 0.467，有条目的臂 9 个、均值 0.841、高于/等于/低于 none = 8/0/1；种子 09 none 1.000，有条目的臂 9 个、均值 1.000、高于/等于/低于 none = 0/9/0；种子 10 none 0.800，有条目的臂 9 个、均值 0.911、高于/等于/低于 none = 7/1/1。
- 关键是模板而不是条数：在出现遗忘的种子 08 和 10 上，复习池里至少有 1 条同模板 `target_median_natural` 的臂都不低于 26/30（种子 08 为 28–30/30，种子 10 为 26–30/30）；只有 `stats_median` 的臂恢复得不完整或没有恢复（种子 08：tf00 1 条 7/30、e3b2 两臂各 2 条 21/30 和 26/30；种子 10：tf00 1 条 24/30，与 none 相同）。详见上面「按复习模板拆分」。
- 判断：在有遗忘的两个种子上方向一致，2–5 条（708–1,791 input token）、其中至少 1 条同模板的经验就能拉回到接近 stage_03；种子 09 没有遗忘，不能用来判断恢复。

**总判断**：真遗忘可以被复习拉回，前提是复习池里有**同模式、同措辞**的经验。所需量很小：`db.list_tables` 1–3 条（272–816 input token），natv2 `py.median` 2–5 条且至少 1 条同模板（708–1,791 input token）。没有对应经验时，复习其它模式或复习 Calendar 都不起作用（`db.list_tables` 在 dose_db6 和 Calendar 对照臂中为 0；`py.median` 换措辞后种子 09 拉不回）。这和 Database S 曲线是「目标模式特定恢复」的结论方向一致，也说明下一步值得研究的是**选哪条经验**，而不是复习比例。注意：`db.list_tables` 的遗忘是参数格式层面的，有效题面只有 1 个；`py.median` 每点 5 题、三种子方向不一致，写论文时只能作为方向性证据。

## 数据缺口

- dose_db2/3/4 在 B1 下只评了 natv2_database 与 db_nontarget，没有 p2_database / p2_python / natv2_python 的 B1 结果，因此不进入上表（不用 B32 补）。它们的复习池里 `db.list_tables` 条数见 JSON `replay`。
- 同一种子的 dose_db0/1/6 共享同一批 File/Python 复习条目（Python 部分完全相同），所以对 `py.median` 它们不是独立的剂量点。
- tf00 没有 db_nontarget / calendar_v3 / v3fix 的 B1 结果，但旧工具 p2_* 与 natv2_* 齐全。
- e3b2（实验 A）种子 09/10 若评测未完成，自动跳过；评完后重跑本脚本即可纳入。

