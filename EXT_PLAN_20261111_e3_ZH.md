# E3 实验计划（预注册）· 预算扫描 + Calendar-only 计算量对照（E3-A）· Database 剂量（E3-B）

- 撰写：2026-11-11 20:20（Asia/Shanghai，UTC+8），**任何 E3 结果产生之前**。
- 状态：代码、数据、冒烟全部就绪。**正式链未启动**，等用户 / 主线确认后再 `launch`。
- 依据：`GPT_REVIEW_20261111_e4_ZH.md`、`GPT_REVIEW_20261111_calv3_ZH.md`（GPT 对 Calendar v3 的审稿，批准 E3 并要求拆成 E3-A / E3-B）、`EXT_HANDOVER_20261111_calv3_ZH.md`、`runs_ext_e4/token_ledger.md`。
- 约束：
  - 只新增文件，已有代码一行未改。`replay_train.py` 原样调用；剂量臂和对照臂用新模块 `e3_train.py`，它是机械复制加两个钩子，单元测试逐行核对过原函数。
  - 不碰 `.venv`、已有 `runs*/`、`data*/`、Small Agent、conda `zxx`。
  - 一次只跑一个 GPU 任务。用户说暂停就 stop。

## 1. 设置（与 E4 完全相同的部分）

| 项 | 设置 |
|---|---|
| 模型 / 方法 | Qwen3-0.6B QLoRA，A 场景（stage 3 → 4），Calendar 是新工具，File / Database / Python 是旧工具 |
| 训练 | batch 1，梯度累积 8，2 epoch，lr 1e-4（**常数，无调度器**），PagedAdamW8bit |
| 复习 | 只插在后半段（第 80 个新样本之后） |
| 经验池 | E4 干净池 `data_ext_e4/pool`，target_ids 取自 E4 manifest |
| 探针 | monitor v2 |
| 种子 | 20261108 / 20261109 / 20261110（筛选阶段）。tf25、tf50、none、Uniform、Calendar-only 的关键比较以后扩到 5 个种子：需要先为新种子生成 phase2 stage_03 起点和 E4 前缀，不在本轮 |
| 起点与前缀 | 所有 E3 分支都从 **E4 同种子的共享中点前缀**出发：同一份权重、优化器状态、RNG 和探针。前缀由 `--phase prep` 从 `runs_ext_e4/prefixes/` 只读复制到 `runs_ext_e3/prefixes/`，再逐个核对 sha256。`data_ext_e3/checks.json` 证明三个种子的前缀元数据与 E4 逐字段相同；正式训练如果不能复用前缀会直接拒绝 |
| Calendar 数据顺序 | `fixed_new_order`，同种子所有臂完全一致（160 个新样本位置） |

## 2. 实验臂与 job 列表

### E3-A：预算 × 定向比例 + Calendar-only 计算量对照（主实验，先跑）

| 臂 | 预算（新数据输入 token 的比例） | 内容 | 训练 |
|---|---|---|---|
| `b05_tf25`、`b05_tf50` | 5%（3,747 token） | 定向比例 25% / 50%，target 族权重各 1/3 | 新训 |
| `b20_tf25`、`b20_tf50` | 20%（14,988 token） | 同上 | 新训 |
| `b05_tf00`、`b20_tf00` | 5% / 20% | Uniform 均匀复习 | 新训 |
| `ctrl_cal05` / `ctrl_cal10` / `ctrl_cal20` | 5 / 10 / 20% | 复习位全部换成 **Calendar 训练样本**（同一份 80 行训练集，有放回），不复习旧工具 | 新训 |
| `b10_tf00`、`b10_tf25`、`b10_tf50` | 10%（7,494 token） | = E4 的 tf00 / tf25 / tf50 | **复用 E4，不重训** |
| `none` | 0 | = E4 none | **复用 E4** |

每个种子按信息量排序：b05_tf25 → b20_tf25 → b05_tf50 → b20_tf50 → ctrl_cal10 → ctrl_cal05 → ctrl_cal20 → b05_tf00 → b20_tf00。每种子 9 个，共 **27 个训练 + 27 个评测**。

### E3-B：Database 剂量（独立机制实验，排在 E3-A 之后）

`dose_db0`、`dose_db1`、`dose_db2`、`dose_db3`、`dose_db4`、`dose_db6`，固定 10% 预算。每种子顺序 db0 → db6 → db2 → db4 → db1 → db3，共 **18 个训练 + 18 个评测**。

可选 E3-B2（第二套嵌套抽样）：`dose2_db1/2/3/4/6`，计划已冻结，默认**不跑**；`E3_WITH_DRAW2=1` 时追加，共 15 个。dose2_db0 与 dose_db0 相同，所以不需要。

**正式默认共 45 个训练分支 + 45 次评测。** 链的顺序：E3-A 种子 08 → 09 → 10，然后 E3-B 种子 08 → 09 → 10。每个种子结束后出一次报告，最后出总报告。

## 3. Database 剂量单位（精确定义）

- **1 个单位 = 1 条独立的 Database target 类经验**：E4 manifest 的 `target_ids["database"]`，模板 `target_db_filter_top`，共 11 条。这条经验在后半段只执行 1 次。每条约 330–350 个输入 token，账本逐条记录真实 token 数。
- **嵌套随机子集**：每个种子用固定随机排列（种子 = 配置种子 + 104729 + 7）取前 k 条，所以 1 条的集合 ⊂ 2 条 ⊂ 3 条 ⊂ 4 条 ⊂ 6 条。第二套抽样用另一个偏移（+17）。
- **固定总预算 7,494 token**，分三块。同一种子下 **File 块和 Python 块对所有 k 完全相同**（单元测试与 `checks.json` 已核对），即“其他工具分配不变”：
  - File / Python 定向部分：按 tf25 的分法。定向预算 = 预算 − int(0.75 × 预算) = 1,874，File 与 Python 各占 1/3。实际是 File 1 条，Python 1–2 条。
  - File / Python 普通复习：0.75 × 预算中 File 与 Python 各占 1/3，只用非 target 行。
  - **Database 块**：剩余约 1/3 的预算保持不变，放 k 条 Database target，其余用**普通（非 target）Database 样本**填满。
- 结果：
  - Database 复习总 token 在各 k 之间几乎恒定（每种子相差 ≤ 0.6%，例如种子 08 各 k 都是 3,061，种子 10 在 2,674–2,692 之间）。
  - 只有“独立 Database target 条数”在变，所以测到的是条数效应，不是 token 剂量。
  - 每个 run 同时记录：Database target 独立条数（= k）、Database 复习样本独立条数、Database 复习 token、Database target token、重复次数。
- 普通复习部分允许有放回抽样（与 E4 的 tf 臂相同），重复次数如实记入账本。target 部分不重复。

## 4. 跨臂固定项与计算量匹配

| 固定项 | 是否满足 | 证据 / 做法 |
|---|---|---|
| 初始 checkpoint、前缀、探针 | 是 | 共用 E4 中点前缀，加载时校验哈希和元数据 |
| Calendar 数据顺序、epoch、随机种子 | 是 | 与 E4 同一份 `fixed_new_order`，2 epoch |
| 学习率调度 | 是 | 常数 lr，无调度器 |
| 复习插入位置 | 是 | `common_replay_positions` 在每份计划都 ≥ 10 条时固定为 10 个位置 [87, 95, …, 159]。CPU 上重算了所有臂（含 uniform / adaptive 参考计划）的条数，全部 ≥ 10。报告阶段用实际日志再核对一遍，与 b10_tf25 不一致会列为偏差 |
| 同一预算内总训练 token | 是，误差 ≤ 1% | 复习 token 都在 [99%, 100%] × 预算内 |
| 同一预算内优化器更新次数 | 是 | 步数 = ceil((160 + 复习条数) / 8)。5% 下 22 步，10% 下 23 步，20% 下 26 步。Calendar-only 对照的条数按“与同种子同预算 tf25 步数相同、且 ≥ 10、且 token 落在预算的 99–100%”选出（例如 10% 下 22–23 条，20% 下 42 条）。剂量臂也是 23 步，全部已在 `checks.json` 核对 |
| CPU 复算与真实运行一致 | 是 | CPU 复算的 10% tf00 / tf25 / tf50 条数（种子 08：22 / 23 / 22；09、10：22）与 E4 实际运行的条数逐个相同 |

**不可避免的偏差**（如实记录）：

1. `none` 没有复习：20 步、74,944 token，比复习臂少 3 步、少约 10% token。所以“复习 vs none”混有额外计算量，这正是需要 Calendar-only 对照的原因。
2. Calendar-only 的单条样本比旧工具经验长：平均约 340–470 token，旧工具经验约 340 token。同样 token 下，对照的条数（micro-step 数）可能比 tf25 少 0–3 条。我们匹配的是优化器步数和 token，最后一个不满的累积窗口长度会差几条。原代码会按实际条数重新缩放这个窗口。
3. 定向臂之间相差 ±1 条（例如 182 对 183 个 micro-step），步数仍然相同。
4. 20% 下每个位置插入约 4–5 条复习，5% 下约 1 条。这本身就是预算变量，不算偏差。
5. GPU 非确定性：同一份前缀上，臂间配对是干净的；跨轮（E3 对 E4）同前缀，所以复用的 10% 臂可以直接配对。

## 5. 评测与汇报顺序（预注册）

每个新训模型只加载一次，依次评：

- 历史模板测试（4 工具）
- 自然语言期末 v2（4 工具，冻结哈希 `5dcc7d786fd60556e97d4e2ebefe143fdd9e96e9aa9052877a1317758b15a8f6`）
- Calendar v3（150 题，冻结合并哈希 `2b203ab5123620b99fb64c06afb1e89a388596eade154012e331bb4a27b3633a`）

评测前每次都校验哈希，并检查 v2 / v3 与训练、复习、探针输入的签名重叠为 0。复用臂读取 E4 与 `runs_ext_calv3` 已有的结果（只读）。

汇报顺序与地位：

1. **旧工具自然语言期末 v2**（主指标）：宏平均，以及 File / Database / Python 分工具。
2. **Calendar v3**（新工具保持，主指标）：overall 加 **5 个子技能分别列出**（最晚空档、地点去重、参会人数、标题计数、末场结束）。
3. **Calendar v2** 与 **Calendar 历史模板测试**：分别列出，**不和 v3 合成一个 Calendar 分数**。
4. 历史模板旧工具：辅助诊断。
5. 真实 token 账本：每个 run 一行，来自 `training_log.jsonl`，与 `replay_plan.json`、`train_summary.json` 交叉核对。

Calendar v4（多实例）和 MMLU 不在本轮，以后作为外部验证 / 安全检查补测。

## 6. 统计与预注册判据

- **主统计**：配对层级 bootstrap（种子和题目两级重抽，2000 次），宏指标按工具或子技能分层。种子固定、只抽题目的 item CI 只作次要参考，不能因为 item CI 更窄就拿它当主证据。
- n = 3 是筛选阶段：三个种子同号写“方向一致”，否则写“不一致”。**任何地方都不写“显著”**。
- **预注册非劣效界值：Calendar v3 overall 的 5 个百分点**。判据是 **层级 bootstrap 95% CI 下界 > −5pp**。
  - 检验对象：每个复习臂（b05 / b10 / b20 × tf25 / tf50 / tf00）分别对 none、对同预算的 Calendar-only 对照；以及 dose_db6 对 none。
  - 报告列“非劣(−5pp)：是 / 未达”。“未达”不等于有害，只说明证据不足。
  - 即使 overall 通过，也要逐子技能报告点估计，不能用 overall 掩盖最晚空档或末场结束的局部下降。
- 主要问题（GPT）：
  1. 预算增加时，旧技能收益是否边际递减（b05 → b10 → b20）？
  2. 不同工具的恢复曲线是否不同，Database 是否真有剂量门槛？只写“当前设置下类似阈值的恢复模式”，不写“3 条就是阈值”。
  3. 定向复习的收益在扣除额外计算量之后还在不在（对比 Calendar-only）？
- 配对比较清单见 `e3_run.comparison_pairs()`：
  - E3-A：各预算下 tf 对 none、对 ctrl，tf50−tf25，tf25−tf00，跨预算（05 / 10 / 20）。
  - E3-B：db_k−db0，相邻剂量，db1 对 b10_tf25，db0 对 none。
  - 每对都算 nat old、分工具、Calendar v2、v3 overall 和子技能、历史测试。

## 7. 耗时估计（显卡空闲时）

依据：

- E4 链 6,464 秒。正式复用前缀的训练每个 111–160 秒，均值约 130 秒；每种子第一个臂要建前缀，278–424 秒，E3 不需要。
- E4 评测（历史 + v2，8 套）158–185 秒，calv3 单独评约 130 秒。
- 空闲门每个 GPU 任务约 40–60 秒。
- 本轮冒烟：dose 训练 138 秒（含建冒烟前缀），对照训练 71 秒，迷你评测约 122 秒（主要是加载开销）。

单个分支 ≈ 训练 120–150 秒（20% 预算多约 22 条复习，+15 秒左右）+ 合并评测约 260–300 秒（一次加载跑完 9 套）+ 两次空闲门约 90 秒，**约 8.5 分钟**。

| 组 | 分支数 | 估计墙钟 |
|---|---|---|
| 开头 CPU 步骤（数据检查约 1.5 分钟、复制前缀、已有 SMOKE_OK 跳过冒烟） | – | 约 2 分钟 |
| **E3-A** | 27 | **约 3.8 小时**（3.4–4.3） |
| **E3-B** | 18 | **约 2.5 小时**（2.3–2.9） |
| 报告（6 次种子报告 + 总报告） | – | 约 2 分钟 |
| **合计（默认）** | 45 | **约 6.3 小时**（5.8–7.2） |
| 可选 E3-B2 | 15 | 另加约 2.1 小时 |

用户玩游戏时显卡空闲门会让链等待，等待时间另算。

## 8. 启动 / 停止 / 续跑

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
# 启动（setsid + nohup；已有 runner 时拒绝）
bash scripts/launch_e3_20261111.sh
# 只跑某一组 / 加第二套抽样
E3_GROUPS="A" bash scripts/launch_e3_20261111.sh
E3_WITH_DRAW2=1 bash scripts/launch_e3_20261111.sh
# 看进度
tail -n 30 logs_ext/e3_20261111.status   # CHAIN_START / GROUP_START / START / DONE / FAIL / SKIP / WAIT_GPU / STOP_REQUESTED / ALL_DONE
tail -n 50 logs_ext/e3_20261111.log
# 停止（写 stop 旗标 + 结束本链进程组和 fac_tinyagent.e3_run；不碰游戏和其他任务）
bash scripts/stop_e3.sh
# 续跑：已完成的训练（train_summary.json）和评测（EVAL_DONE）在 shell 层直接跳过；
# 中途被杀的分支会改名为 *_partial_<时间戳> 后重训，被杀的评测会重做
rm -f logs_ext/e3_20261111.stop && bash scripts/launch_e3_20261111.sh
# 单独出报告（CPU）/ 复核数据（CPU）
.venv/bin/python -m fac_tinyagent.e3_run --phase report
.venv/bin/python scripts/test_e3_data.py
```

PowerShell：

```powershell
wsl.exe -d Ubuntu -- bash -lc 'bash "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/scripts/launch_e3_20261111.sh"'
wsl.exe -d Ubuntu -- bash -lc 'bash "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/scripts/stop_e3.sh"'
```

- 空闲门：显存 < 3000MiB 且利用率 < 40%，连续 3 次、间隔 20 秒，**并且**没有其他 `fac_tinyagent` 的 python 进程在跑。
- GPU 任务失败会自动重试一次。
- status 文件：`logs_ext/e3_20261111.status`。

## 9. 文件

| 类型 | 路径 |
|---|---|
| 代码 | `fac_tinyagent/e3_data.py`（计划构建、剂量 / 对照计划、校验）、`fac_tinyagent/e3_train.py`（训练器副本 + 钩子）、`fac_tinyagent/e3_run.py`（prep / train / eval / report / check-smoke / 账本 / 配对 bootstrap） |
| 脚本 | `scripts/run_e3_20261111.sh`、`scripts/launch_e3_20261111.sh`、`scripts/stop_e3.sh`、`scripts/test_e3_data.py`、`scripts/smoke_e3_20261111.sh` |
| 数据 | `data_ext_e3/`：`manifest.json`、`checks.json`，以及 `plans/` 下 3 种子 × 14 个冻结计划（3 个对照 + 6 个剂量 + 5 个第二套剂量）。`data_ext_e3_superseded_v1_20261111/` 是审稿前第一版计划，已作废，只留档 |
| 结果 | `runs_ext_e3/`（`prefixes/` 已复制并核对），冒烟结果在 `runs_ext_e3_smoke/`（v1，审稿前代码）和 `runs_ext_e3_smoke_v2/`（修订后代码） |
| 日志 | `logs_ext/e3_20261111.{log,status,pid}`、`logs_ext/e3_smoke*_20261111.log` |
