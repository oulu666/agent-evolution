# E3-B2 预注册修订（2026-11-14）：P3「条数 vs 时机」拆分实验

- 撰写：2026-11-14 凌晨（Asia/Shanghai，UTC+8），**在任何 P3 训练开始之前写成**。不修改 `E3B2_PREREG_20261112_ZH.md` 与 `E3B2_PREREG_AMEND_20261113_timing_ZH.md`，本文件只追加三个臂。
- 动机：`EXT_REPORT_20261113_timing_ZH.md` 与 `runs_ext_e3b2_timing/analysis/timing_audit_ZH.md` 显示，Database 主指标与 target 的更新暴露 Σafter 的秩相关（n≥1，36 点）0.936，高于 target 条数 0.811；控制 Σafter 后条数的偏秩相关 −0.086。但现有剂量臂 2→6 条中条数与 Σafter 同涨（共线），分不开。本修订用两个 Σafter 相同、条数不同的臂把两者拆开，再加一个更早插入的臂看暴露是否单调。
- 术语：`db.filter_cmp_top` 在 T0 就是 0，结果写作「能力缺口及其恢复」，不叫遗忘恢复。只说「方向一致」（三种子同号），不说「显著」。正式协议为 B1。

## 1. 共同设置（与 dose_db1 / dose_db4 / p2_timing 完全相同）

- 模型 Qwen3-0.6B QLoRA，种子 20261108 / 20261109 / 20261110。
- 起点：同一 `A_seed*` Calendar step-80 prefix（`runs_ext_e4/prefixes/A_seed*`，sha256 与 manifest 一致后复制到 `runs_ext_p3_count_timing/prefixes/`）。
- 训练参数：`train_replay_stage_e3`，与 p2_timing 相同（targeted、replay_ratio 0.10、uniform_floor 0.2、TF25 参数、plan_override 返回本轮冻结计划）。
- 复习池、条目集合、条目数、各段条目数、token 预算（input / supervised token 总和）、总 microstep 与 optimizer 步数（23）都与源臂相同；build 与 dry 阶段逐项核对，训练后再核对 optimizer_steps = 23。
- Target 身份规则：沿用源冻结计划里的 target（不重抽）。dose_db1：08 为 `T-000`，09/10 为 `T-001`（与 dose_db1_pos143 相同）。dose_db4：08 为 T-009/004/001/000；09 为 T-005/001/006/008；10 为 T-009/007/001/002。
- 移动方式：与 p2_timing 相同，target 与目标槽上的条目**交换**，其它条目不动。不设 sham 臂。
- 插入机制回顾：10 个固定复习位置 87, 95, …, 151, 159；复习列表按顺序切成 10 段，第 i 段的下标为 `[i·n/10, (i+1)·n/10)`。「之后更新次数」= 23 − 所在累积窗口序号 + 1（累积 8 microstep，含所在窗口那次）；Σafter = 各 target 之后更新次数之和；mom = Σ(1 − 0.9^after)，作为受 AdamW 一阶动量启发的加权暴露代理指标，只作敏感性分析。各下标的之后更新次数取自源臂实际训练日志（交换不改变各段大小，所以下标→microstep 不变），训练后再用新训练日志核对，不符即中止。

## 2. 臂与确切位置（build 阶段冻结，`data_ext_p3_count_timing/manifest.json`）

| 臂 | 源计划 | 种子 | n 条目 | target：原（位置/之后） → 新（下标@位置/之后） | Σafter | mom |
|---|---|---|---|---|---|---|
| dose_db1_pos127 | dose_db1 | 08 | 23 | T-000：159/1 → 12@127/6 | 6 | 0.469 |
| dose_db1_pos127 | dose_db1 | 09 | 22 | T-001：159/1 → 12@127/6 | 6 | 0.469 |
| dose_db1_pos127 | dose_db1 | 10 | 23 | T-001：159/1 → 12@127/6 | 6 | 0.469 |
| dose_db4_late | dose_db4 | 08 | 22 | T-009 143/4、T-004 151/2、T-001 159/1、T-000 159/1 → 17@151/2、18@151/2、20@159/1、21@159/1 | 6（原 8） | 0.580（原 0.734） |
| dose_db4_late | dose_db4 | 09 | 22 | T-005 143/4、T-001 143/4、T-006 151/2、T-008 159/1 → 17@151/2、18@151/2、20@159/1、21@159/1 | 6（原 11） | 0.580（原 0.978） |
| dose_db4_late | dose_db4 | 10 | 22 | T-009 143/4、T-007 151/2、T-001 159/1、T-002 159/1 → 17@151/2、18@151/2、20@159/1、21@159/1 | 6（原 8） | 0.580（原 0.734） |
| dose_db1_pos95 | dose_db1 | 08 | 23 | T-000：159/1 → 3@95/11 | 11 | 0.686 |
| dose_db1_pos95 | dose_db1 | 09 | 22 | T-001：159/1 → 3@95/11 | 11 | 0.686 |
| dose_db1_pos95 | dose_db1 | 10 | 23 | T-001：159/1 → 3@95/11 | 11 | 0.686 |

说明：
- dose_db1_pos127：target 换到第 127 位那一段的最后一个槽，之后 6 次更新。
- dose_db4_late：第 151 位那一段只有 2 个槽（之后 2 次），第 159 位那一段 3 个槽（之后 1 次）。4 条 target 放在 151 段 2 个槽 + 159 段最后 2 个槽，Σafter = 2+2+1+1 = 6，与 dose_db1_pos127 **完全相等**。这是 dose_db4（三个种子 n 都是 22）步网格下唯一能让 4 条 target 的 Σafter 等于 6 的放法；代价是 mom 不能同时相等（0.580 vs 0.469，db4_late 偏高 0.11）。另一种放法（151 段 1 条 + 159 段 3 条）Σafter = 5、mom = 0.490，mom 更接近但 Σafter 偏离；按主暴露指标优先，选前者。如果 db4_late 高于 pos127，要在报告里注明 mom 偏高这一点。
- dose_db1_pos95：第 95 位那一段之后 11 次更新（不是原估计的 12–14；12–13 次只在第 87 位出现）。按臂名与位置执行，Σafter 记实际值 11。
- 被交换出去的条目（逐条见 manifest 的 `swaps`）：dose_db4_late 里有几条 File / Python 的 target 条目（`file-train-e4_last_match-*`、`python-train-target_median_natural-*`）被换到更早的位置，会增加这两个技能 target 的暴露；它们只影响副作用指标，不影响 Database 主指标，报告里如实标注。

队列顺序（臂优先）：dose_db1_pos127 ×3 → dose_db4_late ×3 → dose_db1_pos95 ×3。这样如果中途暂停，最关键的一对先完成。

## 3. 预测与判定表

主指标：B1 nat v2 `db.filter_cmp_top` Joint Success（30 题），同时报 tool / arguments / final 三个分量。副作用套件与 p2_timing 相同：nat v2 File / Python、Database 非 target 40 题、Calendar v3（冻结）、v3fix（附加指标）、p2 Database / Python / File。单题差为 1/30 = 0.033。

**配对比较（同种子差值）**，「方向一致」= 三个种子同号；「≈」= 方向不一致且三种子均值差的绝对值 ≤ 0.10（3 题）。

| 比较 | 结果 | 解释 |
|---|---|---|
| pos127 − db4_late | pos127 ≈ db4_late | 暴露量（Σafter）是主要驱动，条数本身没有独立作用 |
| pos127 − db4_late | 三种子都 < 0（db4_late 更高，方向一致） | 多条不同 target（多样性）在相同 Σafter 下有独立价值（注意 mom 偏高 0.11） |
| pos127 − db4_late | 三种子都 > 0（pos127 更高，方向一致） | 早插入的作用大于多样性 |
| pos127 − db4_late | 方向不一致且 \|均值\| > 0.10 | 不一致，需要加种子或进一步控制 target 身份 |
| pos95 − pos127 | 三种子都 > 0 | 暴露继续单调起作用 |
| pos95 − pos127 | ≈ | 在 Σafter≈6 之后饱和 |
| pos95 − pos127 | 三种子都 < 0 | 过早插入被之后的 Calendar 更新覆盖 |

我的预测（写在结果之前）：按 timing_audit 的 mom + 种子 logistic，Σafter=6 对应主指标约 0.6；预测 **pos127 ≈ db4_late**（暴露是主要驱动），pos95 ≥ pos127（Σafter 5–8 档均值 0.733，9–15 档 0.980），即暴露单调或接近饱和，不预期被覆盖。

另外报告（描述性，不作判定）：各臂与原 dose_db1（Σafter 1）、dose_db1_pos143（Σafter 3–4）、dose_db4（Σafter 8–11）的配对差；每臂答对的题号及同种子答对集合的交并。

## 4. 输出与命令

- 代码：`fac_tinyagent/p3_count_timing.py`（build / show / dry / queue / summarize）；runner `scripts/run_p3_20261114.sh`，启动 `scripts/launch_p3_20261114.sh`，停止 `scripts/stop_p3.sh`。
- 数据：`data_ext_p3_count_timing/`（plans + manifest，sha256 冻结）。结果：`runs_ext_p3_count_timing/`（branches / evaluation / summary.json / summary_tables_ZH.md）。日志：`logs_ext/p3_20261114.{log,status,pid,stop}`。
- 开跑前检查与 watchdog 与 p2_timing 相同：没有游戏（含 r5apex），功耗上限 ≥ 60W，没有其他 GPU 进程；运行中发现游戏 / 功耗上限降低 / tasklist 连续 3 次失败，就写停止标志并杀掉任务。
