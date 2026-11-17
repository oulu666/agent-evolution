# 预注册补充：P4 真遗忘模式上的复习时机，以及两个饱和模型预测验证臂

写于 2026-11-14 13:50 北京时间，**在任何 P4 训练之前**。代码：`fac_tinyagent/p4_forget_timing.py`（build / show / dry / queue / summarize）；冻结数据：`data_ext_p4_forget_timing/`（manifest 含计划与探针的 sha256、预算偏差）；输出：`runs_ext_p4_forget_timing/`。依据：`P4_TRUE_FORGETTING_DRAFT_20261114_ZH.md`、`runs_ext_p3_count_timing/analysis/saturation_fit_ZH.md`。彦哲已确认开跑 GPU（「开跑吧，显卡空着」）。

## 1. 共同设置

- 三种子 20261108 / 09 / 10；都从 A_seed* 的 Calendar step-80 前缀（`runs_ext_e4/prefixes`，复制到 `runs_ext_p4_forget_timing/prefixes` 并校验哈希）分支；23 个 optimizer step；复习预算 7494 input token（与 P3 相同）。
- 评测 Protocol-B1（batch 1）：`lt_probe`（新增 list_tables 改写探针 24 题）、`p2_database`（含 list_tables 6 题）、`natv2_python`（同模板 median 30 题）、`natv2_database`（filter_top 30 题）、`v3fix`。
- 探针 `data_ext_p4_forget_timing/probe/list_tables_probe.jsonl`：24 个不同题面，其中 4 个含「read-only」字样（与原测试题相同的诱因），其余 20 个不含；格式、system、标准 observation / answer 都抄自 `database-test-db_list_tables_test-000`。没有一个题面与已有 train / val / test / 复习池的 prompt 重复（build 时检查）。不改任何冻结测试集。
- 探针基线（队列最先跑，只评探针）：T0 = `stage_02_database`，预期会；prefix = stage_03 adapter + step-80 前缀参数，预期不会。如果 T0 也不会，就在报告里说明，队列照常继续。
- 「之后更新次数」口径与 P3 相同。各槽位的值取自源臂（dose_db4 / dose_db2）实际训练日志；训练后逐条核对 filter / list_tables / median 条目的实际位置与 after，对不上就停。

## 2. 臂与实际位置（由 `--phase show` 生成，build 时冻结）

P4 四臂共同的改动（同一种子四臂相同，只有位置不同；LT2mid 多换一条）：
- (0) 第 159 段非 filter 槽不足 2 个时，把该段第一条 filter target 与第 151 段最后一个非 target 槽交换。种子 08 把 T-001 移到 151 段，种子 10 把 T-001 移到 151 段；种子 09 不需要。所以 P4 四臂的 filter Σafter：08 为 9、09 为 11、10 为 9（dose_db4 原为 8 / 11 / 8）。
- (1) 固定换入 `db_list_tables-000`（272 token），替换 token 最接近的 1 条 Database 背景条目：08 `db_top_n-009`（311），09 `db_average-009`（297），10 `db_filter_count-003`（289）。LT2mid 另加 `db_list_tables-001`，替换 08 `db_group_count-007`（341）、09 `db_group_count-006`（341）、10 `db_schema_count-001`（345）。
- (2) target_median_natural 只留编号最小的一条：08 留 027（本来就只有 1 条）；09 留 014，把 018 换成 stats_mean-002；10 留 016，把 025 换成 stats_mean-002。
- (3) 与目标槽交换，其它条目不动。

| 臂 | list_tables 位置/after（Σ） | median 位置/after | filter（三种子 Σafter） |
|---|---|---|---|
| P4_early | 95/11（11） | 95/11 | 9 / 11 / 9 |
| P4_mid | 127/6（6） | 127/6 | 9 / 11 / 9 |
| P4_late | 159/1（1） | 159/1 | 9 / 11 / 9 |
| P4_LT2mid | 127/6 + 127/6（12） | 135/5（127 段只有 2 个槽） | 9 / 11 / 9 |
| db2_early | 08：原计划自带 2 条 list_tables-001 在 95/11、119/7；09、10 没有 | 不动 | 08 T-001、T-000；09 T-005、T-001；10 T-009、T-001；都在 127/6，Σ12 |
| db4_early | 无 | 不动 | 08 T-009、T-004 @127/6，T-001、T-000 @135/5；09 T-005、T-001 @127，T-006、T-008 @135；10 T-009、T-007 @127，T-001、T-002 @135；Σ22 |

预算偏差（实际复习 input token − 预算 7494）：

| 种子 | P4_early / mid / late | P4_LT2mid | db2_early | db4_early |
|---|---|---|---|---|
| 08 | −39（−0.52%） | −108（−1.44%） | 0 | 0 |
| 09 | −29（−0.39%） | −98（−1.31%） | 0 | 0 |
| 10 | −25（−0.33%） | −98（−1.31%） | −2（源计划本身） | −4（源计划本身） |

db2_early / db4_early 只换位置，条目集合和 token 与源计划完全相同。

## 3. 判定表

主指标：list_tables 看改写探针 24 题的 Joint（p2_database 的 6 题作为第二指标，只有全对和全错）；median 看 natv2_python 30 题的 Joint，**只用出现遗忘的种子 08、10**（种子 09 在 none 上 30/30，不用于判断）；db2_early / db4_early 看 B1 nat v2 `db.filter_cmp_top` Joint（30 题）。「方向一致」= 三种子同号；不做显著性陈述。「恢复」= 探针 ≥ 0.5，且 p2 list_tables 6/6。

| 问题 | 结果 | 判读 |
|---|---|---|
| list_tables 时机 | early 恢复、mid 恢复、late 不恢复；early − late 与 mid − late 三种子都 > 0 | **支持「已经忘掉的要早插」** |
| | early 恢复、mid 不恢复、late 不恢复 | 需要 ≥10 次更新（与已有数据的 Σ≥10 门槛一致），时机效应成立 |
| | 三臂都恢复或都不恢复 | 时机在这个模式上不起作用 / 单条不足 |
| 条数 vs 暴露 | LT2mid > mid（三种子），且 \|LT2mid − early\| ≤ 0.10 | 恢复跟累计暴露走（Σ12 ≈ Σ11），不是条数 |
| | LT2mid > mid 且 > early（三种子） | 第二条同模式经验在暴露之外还有作用 |
| | \|LT2mid − mid\| ≤ 0.10 | 第二条同模式经验没有帮助 |
| median（种子 08、10） | late − early ≥ −0.10（两个种子都是） | **「重新激活」型：晚插不差于早插**，成立 |
| | 至少一个种子 late − early < −0.10 | 不成立，「早」是更普遍的规则 |

预期（来自已有 66 个 checkpoint 的盘点）：list_tables 中 early 三种子都恢复，late 三种子都不恢复，mid 至多 1 个种子恢复，LT2mid 至少 2 个种子恢复；median 三臂在 08、10 上都 ≥ 26/30。

## 4. 饱和模型的预注册预测（`saturation_fit.json` 已写入，此处只抄录）

| 臂 | 纯饱和模型 Σmin(a,5)/5，带上限 logistic（种子 08 / 09 / 10） | 按表饱和模型 tab_cap K=5（08 / 09 / 10） | 实测参照 |
|---|---|---|---|
| db2_early | **0.958 / 0.958 / 0.958**（留一种子范围 0.957–0.98） | **0.627 / 0.984 / 0.627**（均值 0.746） | dose_db2：0.267 / 0.733 / 0.200 |
| db4_early | **0.98 / 0.98 / 0.98**（0.98–1.00） | 0.984 / 0.984 / 0.984 | dose_db4：0.800 / 0.933 / 0.667 |

判读：
- db2_early 三种子都 ≥ 0.85 → 纯饱和暴露模型胜出（只要每条暴露够，2 条就够）。
- db2_early 中 09 比 08、10 高 0.30 以上，且 08、10 ≤ 0.75 → 按表饱和模型胜出。「广」要按答案结构 / 实体覆盖来理解，EAAR 选经验时要按表 / 失败子类型覆盖。
- db4_early 三种子都 > 同种子 dose_db4 → 「早而广」可以叠加。纯饱和模型在 dose_db4 上高估过 0.12，所以 db4_early 实测低于 0.98 但高于 dose_db4 也算方向一致。
- 两个模型分别报告各自的 MAE（`summary.json` → `verdicts.prediction_check`）。

## 5. 不做

不设 sham 或无复习对照（33 个没有 list_tables 经验的已有 checkpoint 全是 0/6；median 的遗忘水平已有 none / ctrl 臂给出）；不加种子；不换模型规模。
