# E3-B2 预注册修订（2026-11-13）：target 插入位置单变量对照

- 撰写：2026-11-13 19:45 左右（Asia/Shanghai，UTC+8），**在任何训练开始之前写成**。不修改原预注册 `E3B2_PREREG_20261112_ZH.md`，本文件只追加一组对照。
- 动机（只读证据，见 `EXT_REPORT_20261113_p2_grad_pilot_ZH.md` §6.5、`runs_ext_p2_grad_pilot/v2/target_timing_ZH.md`）：三个种子的 tf25 都在新样本第 143 位插入唯一一条 `filter_cmp_top` target，之后还有 3–4 次 optimizer 更新；dose_db1、e3b2_A_target_other、e3b2_A_target_dbbg 都在第 159 位（最后一个复习位置）插入，之后只有 1 次更新。现有数据里，这个差别与 tf25 高出约 0.3 的现象混在一起。本修订只改插入位置，其它全部固定，以检验这个混杂因素。
- 术语：`db.filter_cmp_top` 在 T0 就是 0，结果写作「能力缺口及其恢复」，不叫遗忘恢复。

## 1. 假设

**H-timing**：同一条 \(T^\star\)（09/10 为 `database-train-target_db_filter_top-001`，08 为 `-000`，与实验 A 相同）、同样的背景条目集合，把 target 放在第 143 位，比放在第 159 位的 B1 nat v2 `db.filter_cmp_top` Joint Success 高。

- **判定**：在两个配对比较（target_other_pos143 − e3b2_A_target_other；dose_db1_pos143 − dose_db1）中，**三个种子的差都 > 0，才算支持**（方向一致）。两组都是三种子为正：支持。一组三种子为正、另一组不是：部分支持，分开报告。其余情况：不支持。
- 只报方向和原始值、均值、样本标准差，不做显著性陈述。单题差为 1/30 = 0.033。

## 2. 臂（只改插入位置）

插入机制回顾（代码 `replay_train.common_replay_positions` / `assign_to_positions`，不改）：10 个固定复习位置 87, 95, …, 143, 151, 159。复习列表按顺序切成 10 段，第 i 段插在第 i 个位置之后；第 8 段（下标 7）对应第 143 位，段内下标为 `[7n/10, 8n/10)`（n 为条目数，整除）。

**改动规则（两臂相同）**：取原冻结计划的条目列表，把 \(T^\star\) 与「第 143 位那一段的最后一个条目」交换位置，其它条目顺序不变。这样做之后：

- 条目集合、条目数、各段条目数、token 预算、总 microstep、总 optimizer 步数（23）都不变；
- 只有两条条目换了位置：\(T^\star\) 移到第 143 位那一段的末尾（与 tf25 里 target 在该段的位置一致），被换下来的那条普通条目移到 \(T^\star\) 原来的位置；
- 预期 \(T^\star\) 之后的 optimizer 更新次数由 1 次变成 3–4 次，跑完后从 `training_log.jsonl` 核对。

| 新臂 | 原计划 | 说明 |
|---|---|---|
| `target_other_pos143` | `data_ext_e3b2/plans/A_seed*_e3b2_A_target_other.json` | 原计划里 \(T^\star\) 是最后一条（第 159 位），无 DB 背景 |
| `dose_db1_pos143` | `data_ext_e3/plans/A_seed*_dose_db1.json` | 原计划把所有带 target 标记的条目（File / Python target 和这条 DB target）放在列表末尾；只移动 DB 的 \(T^\star\)，File / Python target 不动。结构允许同样只改位置，所以两臂都做 |

不加 target_dbbg 的对应臂：H-background 已经三种子不支持，dbbg 与 other 结果几乎相同，加它不会改变判断。

## 3. 配对对象

- target_other_pos143 ↔ 已有的 `e3b2_A_target_other`（`runs_ext_e3b2/branches/…/checkpoint`，B1 结果在 `runs_ext_p1_b1/evaluation`）。
- dose_db1_pos143 ↔ 已有的 `dose_db1`（`runs_ext_e3/branches/…/checkpoint`，B1 结果在 `runs_ext_p1_b1/evaluation`）。
- tf25 只作参照，列在同一张表里，不作配对。

## 4. 训练与评测（与实验 A 完全相同）

- 训练：`e3_train.train_replay_stage_e3`，与 e3b2 / E3 dose 臂相同的参数（mode=targeted，replay_ratio 0.10，uniform_floor 0.2，target_fraction 0.25，E4 midpoint prefix 复用并做哈希校验，require_prefix_reuse=True，Calendar 新数据相同），plan_override 返回本修订冻结的计划。断言 optimizer_steps = 23。
- 评测：Protocol-B1，与实验 A 相同的 9 套考试 `natv2_database, natv2_file, natv2_python, db_nontarget, v3fix, calendar_v3, p2_file, p2_python, p2_database`，同一个 `sft/evaluate.py`。
- 主指标：B1 nat v2 `db.filter_cmp_top` Joint Success（30 题）。副指标照实验 A 报告，不进 H-timing 判定。
- 顺序：种子 08 → 09 → 10，每个种子先训练和评测 target_other_pos143，再做 dose_db1_pos143。一次只跑一个 GPU 任务。

## 5. 路径（只新增）

- 计划：`data_ext_e3b2_timing/plans/`、`data_ext_e3b2_timing/manifest.json`（计划冻结后写入哈希，训练前校验）。
- 训练与评测：`runs_ext_e3b2_timing/`（prefix 的哈希校验副本、branches、evaluation）。
- 代码：`fac_tinyagent/p2_timing.py`、`scripts/run_timing_20261113.sh`、`scripts/launch_timing_20261113.sh`、`scripts/stop_timing.sh`。
- 不改任何已有的 runs\*/data\*、冻结测试集、原预注册。

## 6. 安全

开跑前：Windows tasklist 里没有 r5apex，tasklist 本身没有失败，`enforced.power.limit` ≥ 60 W，没有其它 GPU 计算进程。运行中 watchdog 每 30 秒检查一次：检测到游戏、tasklist 连续失败 3 次、或功耗上限低于 60 W，就写停止标志并停掉任务。所有步骤都可续跑（已完成的训练和 suite 会跳过，被打断的 suite 从头重评）。

## 7. 附带只读分析（CPU，不影响 H-timing 判定）

列出 dose_db2–6、tf25、tf50、b20_tf50 等已有臂里每条 target 的插入位置和之后的更新次数，评估插入时机对两个结论的影响：Database 剂量 S 曲线，以及「覆盖比预算更重要」。只做描述。
