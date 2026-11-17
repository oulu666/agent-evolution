# 小模型持续工具学习与预算复习：阶段实验报告

更新日期：2026-11-10  
研究对象：Qwen3-0.6B，连续 QLoRA 微调，File / Database / Python 统计函数 / Calendar 四类确定性工具。  
报告状态：Phase 1、Phase 2、预算复习 v2、监测诊断、夜间批量诊断、Round 2 A 场景、Round 2 C 场景均已完成；本文汇总全部已完成的实验结果。  
说明：本文是项目级汇总报告；各实验的原始报告、结构化结果和逐题记录见文末“产物索引”。

## 摘要

本项目围绕一个核心问题展开：**小模型在连续学习新工具时，如何判断哪些旧工具能力发生退化，并用有限复习预算更有效地保留这些能力。**

已完成五层工作：

1. **连续学习基线**：四类工具、三种学习顺序、三个种子，建立了阶段能力矩阵、联合/答案指标和遗忘统计。
2. **预算复习对照**：完成了不复习、均匀复习、下降感知复习三组 × 三个种子的共享前缀实验；得到均匀复习的参考效果，并发现旧监测信号在多个 seed 上为空。
3. **监测诊断**：用同一模型交叉评估历史题与监测题，发现“历史题下降、监测题上升”的方向冲突；进一步用 96 组成对中位数题和完整阶段轨迹定位到任务覆盖与自然表述问题。
4. **定向内容复习（A）**：在 A 场景完成 none / uniform / fixed targeted / online adaptive 四组 × 三个种子的同预算比较。固定定向复习在独立 natural final 上显著恢复旧能力，但带来了明显的新工具学习干扰；自适应复习触发正常，却因监测漏掉 Database 而明显低于固定定向。
5. **跨顺序验证（C）**：在 C stage 2→3 复用同一套四臂规则。targeted 的 natural 收益复现（0.528 vs uniform 0.306），新工具代价明显小于 A；但 adaptive 在 3/3 个 seed 中都没有触发，实际等同于 uniform。

当前最重要的判断是：**退化不是单一总分问题，而是任务类型、任务表述和工具选择共同作用的结果；监测必须覆盖真实失败类型，复习内容也必须经过迁移验证。** 现阶段还不能把 targeted replay 作为最终方法，下一步应先做 target fraction / 复习预算的折中，并修正 File/Database 的监测与迁移覆盖。

## 一、研究问题与实验体系

### 1.1 研究问题

项目最初的问题是：学生模型在教师控制下完成任务后，如何通过独立测试判断自己究竟学会了什么。转向持续工具学习后，问题被具体化为：

1. 学习新工具后，哪些旧工具、旧技能发生退化？
2. 少量旧数据复习能带来多少保留收益？
3. 根据退化信号调整复习内容，能否进一步提高同预算下的效率？
4. 监测题本身是否能代表真实退化？

### 1.2 模型与训练设置

- 模型：Qwen3-0.6B，4-bit NF4 量化，double quantization。
- 微调：QLoRA，LoRA r=8、alpha=16、dropout=0.05，目标模块覆盖 attention 与 MLP 投影。
- 训练：learning rate 1e-4，batch size 1，gradient accumulation 8，2 epochs，max sequence length 1024，gradient checkpointing，PagedAdamW 8-bit，assistant-only loss。
- 环境：WSL2 Ubuntu，Python 3.12，torch 2.15.0+cu132，transformers 5.22，peft 0.21，bitsandbytes 0.50，RTX 4060 Laptop 8GB。
- 所有实验复用已有检查点；除非明确说明，未进行新的全参数训练或外部 API 调用。

### 1.3 工具族与数据

| 工具族 | 能力 | 约束 |
|---|---|---|
| File | 读文件、计数、搜索、列出目录、写入沙箱 | 只能访问 episode 自带沙箱 |
| Database | 只读 SQLite 查询 | 只读，禁止写操作 |
| Python statistics | 预定义统计函数 | 不允许 shell / 任意 eval |
| Calendar | 只读 JSON 日历查询 | 固定 fixture，只读 |

数据规模：

- Phase 1：3 族 × 80/20/30 = 390 episodes。
- Phase 2：4 族 × 80/20/30 = 520 episodes；训练/验证/测试模板与实体隔离。
- 监测/封存数据：每族 24 条 monitor + 60 条 sealed_test，共 336 条；sealed_test 不参与策略选择。
- Round 2：共同池 240 条原始旧训练数据 + 41 条定向自然表述样本；独立 monitor 72 条、final 90 条。monitor/final 与共同池不重叠。

### 1.4 指标

- **工具选择准确率**：预测工具是否等于参考工具。
- **参数准确率**：参数是否与参考参数精确匹配。
- **执行成功率**：实际工具执行结果是否与参考执行结果一致。
- **答案成功率**：最终答案是否正确。
- **联合成功率**：工具、参数、执行、答案四项同时正确；比答案指标更严格。
- **遗忘**：\(F(i,t)=\max(0,\max_{k<t}A(i,k)-A(i,t))\)，其中峰值只取当前阶段之前的值；技能级指标按 n 加权。
- 所有报告同时保留逐题丢失/获得记录；总分相同不代表没有题目交换。

## 二、连续学习基线

### 2.1 Phase 1：三工具顺序学习

设置：File → Database → Python，单一种子完整运行。

| 阶段 | File | Database | Python |
|---|---:|---:|---:|
| M0 起点 | 0.000 | 0.000 | 0.333 |
| File 后 | 0.467 | — | — |
| Database 后 | 0.600 | 0.567 | — |
| Python 后 | 0.467 | 0.367 | 1.000 |

主要观察：

- File 阶段后 File 达到 0.467；Database 阶段后 File 升到 0.600；Python 阶段后 File 回落到 0.467、Database 从 0.567 降到 0.367。
- Python 阶段平均遗忘（final success）0.167；工具选择/执行 0.233，参数 0.133。
- 验证损失 0.0255 / 0.000356 / 9.3e-5，存在明显过拟合，后续判断需要结合 held-out 任务。
- 报告：[phase1_report.md](runs/20261108_204539_seed20261108/reports/phase1_report.md)

### 2.2 Phase 2：四工具、三顺序、三种子

设置：File / Database / Python / Calendar 四族，A/B/C 三种顺序 × seeds 20261108/09/10，共 9 个完整 run；阶段能力矩阵使用每族 6 题子集，最终 adapter 另做 30 题完整复核。

**30 题完整复核（旧工具与 Calendar 的最终能力）**

| 顺序 | 四族宏平均 |
|---|---:|
| B：Calendar → Python → Database → File | 0.714±0.084 |
| A：File → Database → Python → Calendar | 0.664±0.027 |
| C：Database → File → Calendar → Python | 0.478±0.090 |

按族：Python 0.885±0.121 > Database 0.619±0.117 > File 0.519±0.063 > Calendar 0.452±0.305。

关键发现：

- 顺序 B 最好，C 最差；顺序效应与工具难度存在混杂，不能直接当作因果估计。
- C 顺序的 Calendar 在 30 题下为 0.089±0.019，而 A/B 的 Calendar 为 0.633；6 题子集曾显示 0.000，完整测试说明“精确归零”是抽样伪影，但崩塌方向仍成立。
- 6 题子集上的平均遗忘：A 0.093、B 0.056、C 0.167；族级 Calendar 0.167、File 0.111、Python 0.083、Database 0.074。
- 最后一个学习的工具族天然没有后续再测，因此没有遗忘估计；第四位置不可观测。
- 报告：[phase2_report.md](runs_phase2/reports/phase2_report.md)；[完整复核](runs_phase2_full/report.md)

## 三、预算复习对照（Replay Study v2）

### 3.1 设计

- 场景：A 顺序 stage 3 → 4（旧 File/Database/Python，新 Calendar）。
- 三臂：none、uniform、adaptive；三个种子；9 个单阶段继续训练分支。
- 每个 seed 共享同一中点可训练参数、optimizer/scaler、Python/NumPy/Torch CPU/CUDA RNG 状态；三臂从中点恢复。
- 复习预算：新工具训练输入 Token 的 10%；uniform floor 20%；自然遗忘，不做额外训练。
- 第一版因三臂中点参数不同作废；第二版增加了参数哈希校验，全部通过。

### 3.2 结果

| 方法 | 旧工具 joint | 旧工具 answer | 新工具 joint | 新工具 answer |
|---|---:|---:|---:|---:|
| none | 0.5426±0.0179 | 0.6185±0.0195 | 0.9167 | 0.9167 |
| uniform | 0.5500±0.0147 | 0.6259±0.0225 | 0.9167 | 0.9167 |
| adaptive | 0.5463±0.0116 | 0.6204±0.0195 | 0.9167 | 0.9167 |

- adaptive 在 3/3 个 seed 中都没有检测到中点下降，权重退化为均匀 1/3；它是“无信号”对照，不是定向分配有效性的证据。
- uniform 相对 none 约 +0.74pp，adaptive 约 +0.37pp；差异很小，不能据此判断 targeted replay 的潜力。
- 封存测试上旧工具 joint 从 0.5222 上升到 0.5426/0.5500/0.5463，没有复现历史 A 顺序的 5.19pp 下降；这轮没有可恢复的退化信号。
- 新工具三臂完全一致（0.9167），没有看到 replay 损害新学习。

### 3.3 成本口径

| 方法 | 完整流程参考耗时 | 实际分支耗时 | 共享前缀参考 | 实际 probe 耗时 |
|---|---:|---:|---:|---:|
| none | 230.9s | 230.9s | 0.0s | 120.9s |
| uniform | 236.0s | 60.1s | 175.9s | 0.0s |
| adaptive | 236.2s | 60.3s | 175.9s | 0.0s |

Token：新数据输入 74,944 / 监督 8,542；replay 输入 7,491 / 监督 1,191；监测推理输入 84,826 / 输出 9,247；optimizer steps 20/23/23。报告：[report.md](runs_replay_study_v2_20261109/report.md)。

## 四、监测诊断：为什么 probe 看不到退化

### 4.1 同模型、两套试卷

| 模型状态 | 历史题旧 joint | 当前 probe 旧 joint |
|---|---:|---:|
| 起点 stage 3 | 0.648 | 0.500 |
| stage 4 中点 50% | 0.596 | 0.556 |
| v2 none 终点 | 0.600 | 0.519 |
| 历史 stage 4 终点 | 0.596 | 0.551 |

同一模型在历史题上中点已下降 5.2pp，而 probe 上升；问题不是检查太晚，而是题集覆盖/表述不对。报告：[cross_eval/report.md](runs_monitor_experiments/cross_eval/report.md)。

### 4.2 96 组中位数成对问法

explicit 提示在四个状态均为 1.000；natural 提示（相同数值，改为“排序后正中位置的值”）：

| 状态 | natural joint | tool | arguments | answer |
|---|---:|---:|---:|---:|
| 起点 | 0.969 | 0.997 | 0.969 | 0.990 |
| 中点 | 0.931 | 1.000 | 0.931 | 0.972 |
| v2 终点 | 0.781 | 0.892 | 0.878 | 0.878 |
| 历史终点 | 0.764 | 0.847 | 0.899 | 0.823 |

- 自然表述的工具选择错误只在终点明显：v2 终点 31/288、历史终点 44/288，错误工具全部是 `stats_sorted`；起点 1/288，中点 0/288。
- 错误集中在 seed 20261108；seed 20261109/20261110 没有工具选择下降，存在明显 seed 异质性。
- 24 组与 96 组的结论方向一致，但 96 组更稳定；小样本会低估三 seed 平均。
- 报告：[median/report.md](runs_monitor_experiments/median/report.md)

### 4.3 完整阶段轨迹（夜间队列）

规模：42 个模型状态、216 个可续跑单元、8,208 次任务评估，约 71 分钟。

**A：File → Database → Python → Calendar**

| 工具 | stage 1 | stage 2 | stage 3 | stage 4 |
|---|---:|---:|---:|---:|
| File | 0.433 | 0.556 | 0.500 | 0.489 |
| Database | — | 0.611 | 0.444 | 0.400 |
| Python | — | — | 1.000 | 0.900 |
| Calendar | — | — | — | 0.678 |

**B：Calendar → Python → Database → File**

| 工具 | stage 1 | stage 2 | stage 3 | stage 4 |
|---|---:|---:|---:|---:|
| Calendar | 0.467 | 0.444 | 0.767 | 0.622 |
| Python | — | 0.956 | 0.967 | 0.933 |
| Database | — | — | 0.667 | 0.689 |
| File | — | — | — | 0.600 |

**C：Database → File → Calendar → Python**

| 工具 | stage 1 | stage 2 | stage 3 | stage 4 |
|---|---:|---:|---:|---:|
| Database | 0.489 | 0.289 | 0.267 | 0.211 |
| File | — | 0.611 | 0.467 | 0.467 |
| Calendar | — | — | 0.178 | 0.089 |
| Python | — | — | — | 0.722 |

历史题连续阶段旧工具净下降：

- A stage2→3：+11.1pp；stage3→4：+5.2pp。
- B stage3→4：+5.2pp。
- C stage1→2：+20.0pp；stage2→3：+8.3pp；stage3→4：+4.8pp。

关键含义：C 的主要退化在早期 Database，A 的退化在中点已可见，B 的 Calendar 先获得再回退；监测与复习不能只盯最后一个阶段。报告：[analysis.md](runs_overnight_diagnosis_20261110/analysis.md)、[实验报告](runs_overnight_diagnosis_20261110/EXPERIMENT_REPORT_ZH.md)。

## 五、Round 2 A：定向内容复习

### 5.1 设计

- 场景：A stage 3→4；旧工具 File/Database/Python，新工具 Calendar。
- 共同池：原 240 条旧训练数据 + 41 条定向自然样本（File last-match 16、Database filter-top 11、Python median-natural 14）。
- 独立 monitor：File/Database/Python 各 24 条；独立 final：各 30 条；与共同池不重叠。
- 四臂：none、uniform、fixed targeted、online adaptive；3 seeds；12 个单阶段分支。
- 共享 stage-3 起点与 stage-4 中点；10% 新工具输入 Token 预算。
- targeted/adaptive 配额：50% 均匀覆盖旧工具 + 50% 定向内容；adaptive 未检测到下降时回到均匀。

### 5.2 主要结果

**历史测试（旧工具宏平均 / 新工具 Calendar）**

| 方法 | 旧 joint | 旧 answer | Calendar joint |
|---|---:|---:|---:|
| none | 0.600±0.011 | 0.670±0.013 | 0.667±0.115 |
| uniform | 0.637±0.034 | 0.663±0.006 | 0.644±0.102 |
| fixed targeted | 0.626±0.028 | 0.674±0.013 | 0.456±0.168 |
| adaptive | 0.615±0.028 | 0.663±0.013 | 0.322±0.184 |

**独立 natural final（旧工具宏平均）**

| 方法 | joint | answer |
|---|---:|---:|
| start stage 3 | 0.481±0.061 | 0.522±0.029 |
| none | 0.211±0.158 | 0.352±0.152 |
| uniform | 0.204±0.170 | 0.333±0.194 |
| fixed targeted | **0.641±0.017** | **0.652±0.017** |
| adaptive | 0.363±0.034 | 0.452±0.023 |

逐 seed 的 targeted−uniform natural 差：+0.633、+0.322、+0.356；固定定向的跨 seed 方差很小，是这轮最稳定的收益。

**族级 natural final joint**

| 工具 | start | none | uniform | targeted | adaptive |
|---|---:|---:|---:|---:|---:|
| File | 0.444 | 0.000 | 0.000 | 0.000 | 0.011 |
| Database | 0.022 | 0.000 | 0.000 | **0.944** | 0.078 |
| Python | 0.978 | 0.633 | 0.611 | **0.978** | **1.000** |

### 5.3 解释与代价

- **Database/Python 定向有效，File 不迁移**：File 目标样本来自训练文件/路径，只改变 first→last 问法；独立 final 使用全新文件和路径，模型没有把 last-match 迁移到新实例。Database/Python 的定向内容则明显迁移。
- **adaptive 触发了，但覆盖不全**：3/3 个 seed 都触发；seed108/109 的 monitor 没有检测到 Database 下降，因此没有分配 Database target，natural 只有 0.078；seed109 只分到 File target，natural 仅比 uniform 高 0.022。Python adaptive 达到 1.000，说明监测对齐时在线分配有效。
- **新工具代价明显**：Calendar joint 从 none 0.667 / uniform 0.644 降到 targeted 0.456 / adaptive 0.322。targeted 比 uniform 低 18.8pp，adaptive 低 32.2pp；uniform 本身只有约 −2.2pp 干扰。代价不是 Token 预算造成的（uniform 使用同样 10% 预算），更像定向样本内容/长度/插入位置造成。
- 所有 replay 组实际使用约 7,440–7,494 input tokens；targeted 请求 50% target，实际因 token 打包约 39–44%；实际分支耗时约 56–78 秒，none 约 182–216 秒（需另报完整流程参考耗时）。

报告：[EXPERIMENT_REPORT_ZH.md](runs_round2/EXPERIMENT_REPORT_ZH.md)；结构化结果：[results.json](runs_round2/results.json)。

## 六、Round 2 C：跨顺序验证结果

设置：C stage 2→3（旧 File/Database，新 Calendar），同一套四臂、三种子、10% 预算和 50/50 配额。12 个训练分支、75 个评估单元、2,250 次任务评估，全部完成。

### 历史测试

| 方法 | 旧 joint | 旧 answer | Calendar joint |
|---|---:|---:|---:|
| start stage 2 | 0.450 | 0.650 | 0.078±0.069 |
| none | 0.400±0.029 | 0.594±0.035 | 0.289±0.150 |
| uniform | 0.439±0.111 | 0.511±0.063 | 0.300±0.153 |
| fixed targeted | 0.411±0.111 | 0.500±0.109 | 0.233±0.173 |
| adaptive | 0.439±0.111 | 0.511±0.063 | 0.322±0.164 |

### 独立 natural final

| 方法 | joint | answer |
|---|---:|---:|
| start stage 2 | 0.144±0.025 | 0.244±0.063 |
| none | 0.167±0.033 | 0.283±0.029 |
| uniform | 0.306±0.113 | 0.372±0.098 |
| fixed targeted | **0.528±0.048** | **0.528±0.048** |
| adaptive | 0.306±0.086 | 0.378±0.079 |

逐 seed 的 targeted−uniform natural 差：+0.367、+0.067、+0.233；均值 +0.222。targeted 的收益在 C 也复现，但比 A（+0.437）弱且 seed 间波动更大。

### 族级 natural final joint

| 工具 | start | none | uniform | targeted | adaptive |
|---|---:|---:|---:|---:|---:|
| File | 0.000 | 0.000 | 0.000 | 0.056 | 0.000 |
| Database | 0.289 | 0.333 | 0.611 | **1.000** | 0.611 |

- Database 定向从 uniform 0.611 提到 1.000；File 仍基本不迁移（targeted 仅在 seed108 得到 0.167，总体 0.056）。
- 新工具 Calendar：targeted 0.233，较 none 0.289 低 5.6pp、较 uniform 0.300 低 6.7pp；代价明显小于 A 的 targeted（A：0.456 vs uniform 0.644，低 18.8pp）。
- adaptive 在 C 3/3 个 seed 都未触发：File/Database 的 monitor midpoint drops 都是 0，target fraction 为 0，adaptive 实际等同于 uniform，因此 C 只验证了 fixed targeted vs uniform，没有验证在线分配。
- 报告：[runs_round2_c/report.md](runs_round2_c/report.md)；结构化结果：[runs_round2_c/results.json](runs_round2_c/results.json)。

## 七、综合结论

1. **连续工具学习会产生可重复的旧能力退化，但退化高度任务类型相关。** A 的 Database/Python 下降、B 的 Calendar 先获得后回退、C 的 Database 在早期阶段就下降；只看总分或单一工具会漏掉这些结构。
2. **监测题必须覆盖真实失败类型。** 同一模型在历史题上下降、在 probe 上上升；probe 使用 `study_*` 模板且直接点名操作，历史题使用自然表述，二者零模板重叠。监测失明不是“能力保留好”。
3. **自然表述是独立的能力维度。** 96 组中位数题显示 direct 1.000、natural 终点 0.764–0.781；工具选择错误集中在 `stats_sorted`，且 seed 间异质性很大。任务表述变化必须进入监测和最终评价。
4. **小预算均匀复习有参考收益，但幅度有限。** v2 中 uniform 旧 joint 0.5500 vs none 0.5426；这为后续“内容选择”提供了同预算参照。
5. **固定定向内容选择有明显潜力，也有明确代价。** Round 2 A 的 targeted natural 0.641 vs uniform 0.204，但 Calendar 新工具从 0.667 降到 0.456；C 的 targeted natural 0.528 vs uniform 0.306，Calendar 代价较小（0.233 vs 0.300）。收益在两种顺序复现，但新工具代价随场景变化，不能把“旧能力恢复”单独当作成功。
6. **在线自适应目前受监测覆盖与触发稳定性限制。** A 的 adaptive 3/3 触发，但漏掉 Database 后 natural 只有 0.363，低于 fixed targeted 0.641；C 的 adaptive 3/3 未触发，实际等同 uniform。在线分配的上限由监测任务覆盖和触发条件共同决定。
7. **当前最需要解决的不是更大的 replay buffer，而是“监测覆盖 + 内容迁移 + 新工具代价”的三角关系。**

## 八、限制

- 单模型（Qwen3-0.6B）、单机 8GB、三个种子；统计上仍是探索性，不应把逐 seed 差异当作显著性结论。
- 工具函数是确定性模拟；固定数据库/日历 fixture，部分任务共享工具调用或答案，不代表结构分布外泛化。
- Phase 2 阶段矩阵使用 6 题子集；只有最终 adapter 做了 30 题完整复核。
- 第四个学习的工具族天然没有后续再测，无法估计遗忘。
- Round 2 的 natural final 与 target pool 仍有分布差异；File 目标不迁移就是直接证据。
- 监测与最终评价部分任务复用固定 fixture；需要继续扩充独立实例和题型。
- C 已完成，但 adaptive 在 C 的 3/3 个 seed 中都没有触发；C 只验证 fixed targeted vs uniform，没有验证在线分配。

## 九、下一轮实验建议

按优先级：

1. **Target fraction / 预算折中（A 场景）**：比较 25%/50% target 或 5%/10%/20% 复习预算，目标是找到“natural 旧能力收益”与“Calendar 新工具代价”的 Pareto 前沿。当前 targeted 的 50% target 收益大但新工具代价高，不能直接定稿。
2. **修正监测覆盖**：在 monitor 中加入 Database filter-top 和 test-like File last-match；验证“监测下降 → 对应 target 内容 → final 迁移”的链条。adaptive 目前的最大缺口是 Database。
3. **File target 重做**：用与 final 同分布的新文件/新路径，而不是只改训练文件的问法；否则 file last-match 的监测和复习都无法迁移。
4. **C 已完成**：targeted 的 natural 收益在 C 复现（0.528 vs 0.306），新工具代价小于 A；但 adaptive 3/3 未触发。下一步应优先修 C 的 monitor 触发条件，而不是直接扩大 C 的分支数。
5. **监测成本**：在信号可靠后，再比较 12/24/48/96 题量与检查频率；不要先压缩监测，否则会把覆盖问题误判成成本问题。

## 十、产物索引

| 内容 | 文件 |
|---|---|---|
| Phase 1 报告 | [runs/20261108_204539_seed20261108/reports/phase1_report.md](runs/20261108_204539_seed20261108/reports/phase1_report.md) |
| Phase 2 报告 | [runs_phase2/reports/phase2_report.md](runs_phase2/reports/phase2_report.md) |
| Phase 2 完整 30 题复核 | [runs_phase2_full/report.md](runs_phase2_full/report.md) |
| 预算复习 v2 | [runs_replay_study_v2_20261109/report.md](runs_replay_study_v2_20261109/report.md) |
| 监测诊断 | [runs_replay_study_v2_20261109/monitor_probe_report.md](runs_replay_study_v2_20261109/monitor_probe_report.md) |
| 交叉评估 | [runs_monitor_experiments/cross_eval/report.md](runs_monitor_experiments/cross_eval/report.md) |
| 中位数成对题 | [runs_monitor_experiments/median/report.md](runs_monitor_experiments/median/report.md) |
| 夜间批量诊断 | [runs_overnight_diagnosis_20261110/analysis.md](runs_overnight_diagnosis_20261110/analysis.md) |
| 夜间实验报告 | [runs_overnight_diagnosis_20261110/EXPERIMENT_REPORT_ZH.md](runs_overnight_diagnosis_20261110/EXPERIMENT_REPORT_ZH.md) |
| Round 2 A 报告 | [runs_round2/EXPERIMENT_REPORT_ZH.md](runs_round2/EXPERIMENT_REPORT_ZH.md) |
| Round 2 A 结构化结果 | [runs_round2/results.json](runs_round2/results.json) |
| Round 2 C 报告 | [runs_round2_c/report.md](runs_round2_c/report.md) |
| Round 2 C 结构化结果 | [runs_round2_c/results.json](runs_round2_c/results.json) |
| 共同池/独立题 | `data_round2/`（`manifest.json` 记录 target IDs 与哈希） |
| 实验脚本 | `fac_tinyagent/round2_data.py`、`round2_study.py`、`round2_study_c.py`、`replay_study.py`、`replay_train.py`、`overnight_diagnosis.py`、`phase2_full_eval.py` |

## 附录：关键口径

- 联合成功率要求工具、参数、执行结果和最终答案四项同时正确；答案成功率单独报告。
- 复习预算按新工具训练输入 Token 的 10% 计算；实际 replay token 以 `train_summary.json` 为准。
- 共享前缀：每个 seed 保存中点可训练参数、optimizer/scaler、Python/NumPy/Torch CPU/CUDA RNG；恢复时校验参数哈希。
- 成本：完整流程参考耗时、实际分支耗时、共享前缀参考耗时、监测输入/输出 Token、训练输入/监督 Token 分别记录；推理 Token 与训练 Token 不混合。
- 所有 sealed/final 题不参与策略选择；Round 2 的 monitor、final 与 target pool 均由 `data_round2/manifest.json` 记录哈希和隔离关系。
