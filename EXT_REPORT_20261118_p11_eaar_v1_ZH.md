# P11 EAAR-v1 冻结决策器对照报告

更新时间：2026-11-18 10:00:56 +0800（北京时间）。队列 `rc=0`，`summary.complete=true`，9/9 训练分支审计 PASS，12/12 正式状态 Protocol-B1 评测齐全。本文件为完成后的独立核对，不覆盖既有报告。

本轮只检验一次冻结的 EAAR-v1 规则决策器，在精确 7494 replay 输入 tokens、累计 23 次更新下，相对 uniform（均衡分散）与 fixed_early（相同经验、提前复习）是否提高六子技能严格 Joint 宏平均。不把均值上升说成已掌握，不把单技能（尤其 File last）当主指标，不启动下一轮 GPU 实验，不向 ChatGPT 发送，不推送 GitHub。

这是 2026-11-18 02:53 首次启动因 `restore_t0` 参数名校验失败后的原方案重跑。失败目录已归档为 `runs_ext_p11_eaar_v1_failed_20261118_025333`，不作为本轮结果。当前运行目录：`runs_ext_p11_eaar_v1`。预注册：`P11_PREREG_20261118_EAAR_V1_ZH.md`。

## 1. 完成情况与现场

| 项 | 记录 |
|---|---|
| 启动 / 结束 | 2026-11-18 08:46:39 / 10:00:56 +0800 |
| 墙钟 | COMPLETE.elapsed_seconds=4453.6175（约 74.2 分钟） |
| 队列 | host.stdout：START worker 522，END rc=0；worker 日志：`SUMMARY complete=True`，`QUEUE COMPLETE; NO ONLINE REALLOCATION` |
| 监督器 / worker | PID 514 / 522，结束后已退出 |
| 预检 | 08:46 无 Apex/游戏，功耗上限约 93.67–93.85 W，`safe=true`，无 STOP |
| 守卫 | `guard.jsonl` 1101 条，全程 `game=false`、`STOP=[]`、`safe=true`，功耗上限 90.00–98.76 W，无游戏/功耗中断 |
| 契约关卡 | `e2e_gate.json` passed=true（seed 20261108 uniform，只验训练/评测契约，不是正确率门） |
| 产出规模 | T0 开发探针 3 种子×24 题；训练 9 分支；正式评测 12 个状态×72 题=864 条 B1。独立按 `results.jsonl` 的 `skill_labels` 与 `joint_success` 重计，与 `summary.json` 0 处不一致 |

检查时（约 10:08 北京时间）GPU 空闲：功耗约 22.73 W，利用率 1%，显存 1383/8188 MiB，项目内无训练 Python，项目根目录无 STOP。未清 STOP，未自动恢复（本轮也无须恢复），未开新实验。

## 2. 预算（9/9 精确对齐）

预注册：前缀 10 次更新 + 后缀 13 次=累计 23 次；名义 replay 输入 tokens 7494，本轮目标精确 7494；诊断（开发探针与 T0 加载）0 次更新，成本单列，不占 7494/23。

九个训练分支的 `train_summary.json` 与 `p11_meta.json` 一致，全部 `completed=true`、审计 PASS：

- `optimizer_steps=23`（prefix_updates=10，suffix_actual_optimizer_steps=13）
- `replay_input_tokens=7494`，`budget_input_tokens=7494`，`budget_unused_input_tokens=0`，`within_one_percent_of_budget=true`
- `new_input_tokens=74944`，`new_supervised_tokens=8542`，`new_samples=160`，`replay_samples=22`（10 条 target + 12 条背景）
- 三种子均 `prefix_reused=true`，共享 E4 Calendar step-80 前缀；同一种子三臂的 `shared_prefix_state_sha256` 相同

replay **监督** tokens 随臂变化，不能冒称监督量完全相同：

| 分支 | replay 监督 tokens |
|---|---|
| 20261108 uniform / fixed_early / eaar_v1 | 1001 / 1001 / 1147 |
| 20261109 uniform / fixed_early / eaar_v1 | 1078 / 1078 / 1074 |
| 20261110 uniform / fixed_early / eaar_v1 | 1063 / 1063 / 1090 |

背景条目由同一确定性 DP 补齐目标长度残差，结果不能解释成纯目标条数的独立因果。兼容层里遗留的 family quota / `adaptive_triggered` 字段按 attempt2 合同只作诊断残差，未用于训练或选臂。

## 3. 计划冻结

- Uniform 与 Fixed Early 计划在 CPU 阶段写出：mtime 2026-11-18 02:50:58–02:50:59（首次启动前），重跑未改写。
- 三种子开发探针分别于 08:49:16、08:50:58、08:52:52 完成。EAAR 三份计划与 `plans_manifest.json` 均在 08:52:52 写出，`frozen_before_formal=true`。
- 清单中 9 个计划 sha256 与磁盘文件、各分支 `p11_meta.json` / `attempt2_meta.json` 全部一致。
- 首个训练分支（20261108 uniform）于 08:52:58 开始，晚于冻结；正式 T0 评测在全部训练之后（09:46–10:00）。日志明确训练中无在线改计划。

EAAR-v1 实际冻结选择（时机全部为 scattered；`cal.count_date` 因开发探针 Joint 已饱和剂量为 0；其余记为覆盖缺口）：

| 种子 | 时机 | count_date | list_locations | list_tables | filter_cmp_top | search_last | median |
|---|---|---|---|---|---|---|---|
| 20261108 | scattered | 0 | 1 | 3 | 1 | 3 | 2 |
| 20261109 | scattered | 0 | 2 | 3 | 1 | 2 | 2 |
| 20261110 | scattered | 0 | 2 | 3 | 1 | 2 | 2 |

Uniform / Fixed Early 计数相同、仅时机不同（scattered vs early）；计数因种子打乱破同分而异：08 为 2/2/1/1/2/2，09 为 1/1/2/2/2/2，10 为 2/1/1/2/2/2。三种子 EAAR 均选 scattered，与 uniform 时机相同，对照差只能归为分配，不能归为时机。

开发探针（每技能 4 题，只作冻结特征，不是正式主指标）：count_date Joint 为 4/4、3/4、3/4；list_locations 为 2/4、1/4、1/4；list_tables 与 search_last、median 多为 0；filter_cmp_top 为 2/4、3/4、2/4。三种子均无“前缀已覆盖且 Joint<0.5”的真遗忘先验，也无触发 early 的“已覆盖且输出算子失败”，与全部 scattered 一致。

## 4. 主指标（六子技能严格 Joint）

正式卷为新 holdout，每状态 6 技能×12 题。宏平均对六项等权。旧组=两个 Calendar 子技能，新组=Database/File/Python 四项。T0 是同一 A_seed Calendar step-80 前缀在**本正式卷**上的 B1，不是旧卷分数。

### 4.1 宏平均、旧组、新组

| 种子 | 臂 | 宏平均 Joint | 旧组 | 新组 |
|---|---|---|---|---|
| 20261108 | t0 | 0.2639（19/72） | 0.7500（18/24） | 0.0208（1/48） |
| 20261108 | uniform | 0.2083（15/72） | 0.5833（14/24） | 0.0208（1/48） |
| 20261108 | fixed_early | 0.2639（19/72） | 0.5833（14/24） | 0.1042（5/48） |
| 20261108 | eaar_v1 | 0.3333（24/72） | 0.5417（13/24） | 0.2292（11/48） |
| 20261109 | t0 | 0.1806（13/72） | 0.5000（12/24） | 0.0208（1/48） |
| 20261109 | uniform | 0.3194（23/72） | 0.5833（14/24） | 0.1875（9/48） |
| 20261109 | fixed_early | 0.3056（22/72） | 0.5417（13/24） | 0.1875（9/48） |
| 20261109 | eaar_v1 | 0.2917（21/72） | 0.5000（12/24） | 0.1875（9/48） |
| 20261110 | t0 | 0.1944（14/72） | 0.5833（14/24） | 0.0000（0/48） |
| 20261110 | uniform | 0.2639（19/72） | 0.6250（15/24） | 0.0833（4/48） |
| 20261110 | fixed_early | 0.2361（17/72） | 0.5833（14/24） | 0.0625（3/48） |
| 20261110 | eaar_v1 | 0.3333（24/72） | 0.5833（14/24） | 0.2083（10/48） |

三种子均值：t0 宏 0.2130 / 旧 0.6111 / 新 0.0139；uniform 0.2639 / 0.5972 / 0.0972；fixed_early 0.2685 / 0.5694 / 0.1181；eaar_v1 0.3194 / 0.5417 / 0.2083。

### 4.2 预注册配对判据（未达到）

主要机制对照 eaar_v1−uniform：须三种子宏平均差同正且均值≥0.05。

- 逐种子：+0.1250、−0.0278、+0.0694
- 均值：+0.0556（≥0.05）
- 种子 20261109 为负，**三种子同正不成立**。不能支持“本轮冻结规则相对均衡分散有可用优势”。

强挑战 eaar_v1−fixed_early：须三种子差≥0且均值≥0。

- 逐种子：+0.0694、−0.0139、+0.0972
- 均值：+0.0509
- 种子 20261109 为负，**未达到**。不能称优于两种固定策略。

旧组相对 uniform 的下降：08 −0.0417、09 −0.0833、10 −0.0417。预注册阈值是任一种子下降>0.10 必须报告；本次均未超过 0.10，但 09 的 −0.0833 应如实视为代价，不能忽略。

因 EAAR 三种子均为 scattered，即使均值略高，也不得把差异归因于时机。

### 4.3 相对 T0 的遗忘与获得

遗忘定义为 T0−训练后（正值表示下降），获得定义为训练后−T0（正值表示上升）。

旧组遗忘（T0−训练后）：

| 臂 | 08 / 09 / 10 | 均值 |
|---|---|---|
| uniform | +0.1667、−0.0833、−0.0417 | +0.0139 |
| fixed_early | +0.1667、−0.0417、0 | +0.0417 |
| eaar_v1 | +0.2083、0、0 | +0.0694 |

三种子 08 的旧组都下降，EAAR 最大（18/24→13/24），主要来自 `cal.list_locations` 8/12→4/12，`cal.count_date` 10/12→9/12。09、10 上 EAAR 旧组与 T0 持平。EAAR 旧组三种子均值 0.5417，低于 T0 的 0.6111，也低于 uniform 的 0.5972。

新组获得（训练后−T0）：

| 臂 | 08 / 09 / 10 | 均值 | 三种子均为正？ |
|---|---|---|---|
| uniform | 0、+0.1667、+0.0833 | +0.0833 | 否 |
| fixed_early | +0.0833、+0.1667、+0.0625 | +0.1042 | 是 |
| eaar_v1 | +0.2083、+0.1667、+0.2083 | +0.1944 | 是 |

EAAR 宏平均相对 T0 三种子均为正（+0.0694、+0.1111、+0.1389，均值 +0.1065）。这是相对前缀的获得，**不能替代**未达到的 eaar−uniform 预注册判据。

### 4.4 逐技能严格 Joint（n=12）

| 种子 | 臂 | count_date | list_locations | list_tables | filter_cmp_top | search_last | median |
|---|---|---|---|---|---|---|---|
| 08 | t0 | 10/12 | 8/12 | 0/12 | 0/12 | 1/12 | 0/12 |
| 08 | uniform | 10/12 | 4/12 | 0/12 | 0/12 | 1/12 | 0/12 |
| 08 | fixed_early | 9/12 | 5/12 | 1/12 | 0/12 | 1/12 | 3/12 |
| 08 | eaar_v1 | 9/12 | 4/12 | 10/12 | 0/12 | 1/12 | 0/12 |
| 09 | t0 | 8/12 | 4/12 | 0/12 | 0/12 | 1/12 | 0/12 |
| 09 | uniform | 9/12 | 5/12 | 8/12 | 0/12 | 1/12 | 0/12 |
| 09 | fixed_early | 9/12 | 4/12 | 8/12 | 0/12 | 1/12 | 0/12 |
| 09 | eaar_v1 | 7/12 | 5/12 | 8/12 | 0/12 | 1/12 | 0/12 |
| 10 | t0 | 8/12 | 6/12 | 0/12 | 0/12 | 0/12 | 0/12 |
| 10 | uniform | 9/12 | 6/12 | 3/12 | 0/12 | 1/12 | 0/12 |
| 10 | fixed_early | 8/12 | 6/12 | 2/12 | 0/12 | 1/12 | 0/12 |
| 10 | eaar_v1 | 8/12 | 6/12 | 9/12 | 0/12 | 1/12 | 0/12 |

三种子 Joint 均值：`db.list_tables` 上 t0=0、uniform=fixed_early=0.3056、eaar_v1=0.7500。EAAR 的新组收益几乎全部来自 list_tables（T0 全 0，训练后 10/8/9）。`db.filter_cmp_top` 全部 12 个状态都是 0/12。`file.search_last` 除 T0 种子 10 为 0/12 外均为 1/12。`py.median` 除 fixed_early 种子 08 为 3/12 外均为 0。不能把宏平均上升说成四项新技能普遍学会。

分解（正式卷，要点而非全表）：filter 上工具选择常为 1、参数为 0，属于参数失败；search_last 上工具/参数/执行常为 1、final≈joint≈1/12，属于输出失败（与 P9/P10 观察同型，本轮不作提示追分）；median 上工具选择多为 0；list_locations 上工具/参数/执行高、final 明显更低，属于输出结构失败。File last 仅单列，不作主要声称。

## 5. 结论与界限

队列正常完成，预算与冻结合同成立，主指标已独立核齐。按预注册：

- **不能**声称 EAAR-v1 相对 uniform 有可用优势（三种子未同正）。
- **不能**声称优于 uniform 与 fixed_early 两种固定策略。
- **不能**把 list_tables 的明显获得外推为规则已掌握新工具技能；filter、median、search_last 基本未被带动。
- EAAR 平均旧组低于 uniform 与 T0，种子 08 遗忘最大；种子 09 相对 uniform 的旧组下降 0.0833，虽未过 0.10 阈值，但应记为代价。
- 本轮 EAAR 时机全为 scattered，差异若存在也只涉及剂量分配。

未改卷、未改规则、未加臂、未开新训。P9/P10 的提示与字段问题仍在，只作失败模式辅证，不是本轮贡献。

## 6. 产物路径

- 运行目录：`runs_ext_p11_eaar_v1/`（`summary.json`、`COMPLETE.json`、`supervisor_end.json`、`e2e_gate.json`、`runtime_manifest.json`）
- 计划与冻结清单：`data_ext_p11_eaar_v1/plans/`、`data_ext_p11_eaar_v1/plans_manifest.json`
- 失败归档（勿混用）：`runs_ext_p11_eaar_v1_failed_20261118_025333/`
- 预注册：`P11_PREREG_20261118_EAAR_V1_ZH.md`
- 本报告与交接：`EXT_REPORT_20261118_p11_eaar_v1_ZH.md`、`EXT_HANDOVER_20261118_p11_eaar_v1_ZH.md`
