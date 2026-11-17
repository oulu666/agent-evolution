# 第二轮：定向内容复习与在线分配的 A 场景结果

日期：2026-11-10  
场景：A 顺序第 3→4 阶段（File/Database/Python 为旧工具，Calendar 为新工具）。  
规模：4 组 × 3 seeds = 12 个单阶段续训分支；105 个评估单元，3,150 次任务评估。  
共同设置：共享 stage-3 起点与 stage-4 中点；10% 新工具输入 Token 复习预算；targeted/adaptive 采用 50% 均匀 + 50% 定向配额。  
产物：`report.md`、`results.json`、`evaluation/`、`branches/`。

## 摘要

固定定向复习在独立 natural final 上显著优于均匀复习：旧工具宏平均联合成功率 **0.641±0.017 vs 0.204±0.170**，三个 seed 的配对差分别为 +0.633、+0.322、+0.356。收益主要来自 Database（targeted 0.944）和 Python（0.978）；File 仍为 0.000，说明 file last-match 的定向样本没有迁移到新的自然表述实例。

在线 adaptive 在三个 seed 都触发了定向分配，但 natural final 只有 **0.363±0.034**，明显低于 fixed targeted。原因不是触发失败，而是监测覆盖不全：Database 在 seed108/109 没有被 monitor 检测到下降，adaptive 因而没有分配 Database target 样本；seed109 只分到 File target，natural 仅比 uniform 高 0.022。

代价方面，targeted 和 adaptive 的新工具 Calendar 联合成功率分别降到 **0.456±0.168** 和 **0.322±0.184**，而 none/uniform 为 0.667±0.115 / 0.644±0.102。这显示定向内容在恢复旧能力的同时带来了明显的新工具干扰，不能直接作为最终方法；下一轮需要先做 target fraction / 复习预算的折中实验，或调整插入方式。

## 一、主结果

### 历史测试（旧工具宏平均 / 新工具）

| 方法 | 旧 joint | 旧 answer | Calendar joint |
|---|---:|---:|---:|
| none | 0.600±0.011 | 0.670±0.013 | 0.667±0.115 |
| uniform | 0.637±0.034 | 0.663±0.006 | 0.644±0.102 |
| fixed targeted | 0.626±0.028 | 0.674±0.013 | 0.456±0.168 |
| adaptive | 0.615±0.028 | 0.663±0.013 | 0.322±0.184 |

历史测试上 targeted 与 uniform 接近（−1.1pp），说明定向内容的主要收益不在历史题，而在独立 natural 表述。

### 独立 natural final（旧工具宏平均）

| 方法 | joint | answer | 相对 uniform joint |
|---|---:|---:|---:|
| start（stage 3） | 0.481±0.061 | 0.522±0.029 | — |
| none | 0.211±0.158 | 0.352±0.152 | — |
| uniform | 0.204±0.170 | 0.333±0.194 | — |
| fixed targeted | **0.641±0.017** | **0.652±0.017** | **+0.437** |
| adaptive | 0.363±0.034 | 0.452±0.023 | +0.159 |

逐 seed 的 targeted−uniform natural 差：seed108 +0.633、seed109 +0.322、seed110 +0.356。targeted 的跨 seed 方差很小（0.641±0.017），是这轮最稳定的效应。

## 二、族级拆解

### natural final joint

| 工具 | start | none | uniform | targeted | adaptive |
|---|---:|---:|---:|---:|---:|
| File | 0.444 | 0.000 | 0.000 | 0.000 | 0.011 |
| Database | 0.022 | 0.000 | 0.000 | **0.944** | 0.078 |
| Python | 0.978 | 0.633 | 0.611 | **0.978** | **1.000** |

- Database 和 Python 的定向复习有效；File 完全无效。
- adaptive 的 Database 只有 0.078，因为 monitor 在 seed108/109 没有报告 Database 下降，target 配额没有分给 Database。
- File 的定向样本来自原训练池的 first-match 文件/路径转成 last-match；natural final 使用全新文件与路径。模型没有把“最后匹配”迁移到新实例，说明 file 目标需要更多实例/路径变化，或需要改成与 final 更接近的生成方式。
- Python adaptive 达到 1.000，因为它多数 seed 检测到了 Python 下降并分配了 target 样本。

### 新工具 Calendar（历史测试）

| seed | none | uniform | targeted | adaptive |
|---|---:|---:|---:|---:|
| 20261108 | 0.600 | 0.733 | 0.433 | 0.200 |
| 20261109 | 0.800 | 0.667 | 0.633 | 0.533 |
| 20261110 | 0.600 | 0.533 | 0.300 | 0.233 |

定向/自适应组的 Calendar 干扰在三个 seed 上方向一致，targeted 平均比 none 低 21.1pp、比 uniform 低 18.8pp。uniform 的干扰很小（约 −2.2pp）。这说明问题不是“复习本身”，而是**当前定向样本内容/配额**对新工具学习造成了更强干扰。

## 三、adaptive 的监测与分配

| seed | monitor drops（db/file/python） | adaptive target samples |
|---|---|---:|
| 20261108 | 0.000 / 0.208 / 0.208 | db 0, file 4, python 4 |
| 20261109 | 0.000 / 0.375 / 0.000 | db 0, file 8, python 0 |
| 20261110 | 0.042 / 0.208 / 0.208 | db 1, file 5, python 4 |

触发本身是有效的：3/3 seed 都触发，且 file/python 的监测下降被捕捉。问题在覆盖：

- Database 在 final 上从 start 0.022 到 none 0.000，但 monitor 只有 seed110 报告 0.042 的下降；seed108/109 分不到 Database target。
- File 监测下降很大，但 final file 即使分配 target 仍为 0；说明“监测到了”不等于“选到了能迁移的复习内容”。
- Python 监测在 seed108/110 触发，adaptive natural Python 达到 1.000；说明当监测任务与 final 任务类型对齐时，在线分配可以工作。

## 四、成本与配额

- 所有 replay 组实际使用约 7,440–7,494 input tokens，预算 7,494；uniform 稳定接近 100%。
- targeted target 半区实际样本：seed108 db5/file3/py1；seed109 db3/file3/py2；seed110 db3/file4/py2。target 比例请求 50%，实际因 token 打包约 40–50%。
- 实际分支耗时约 56–78 秒（复用前缀）；none 约 182–216 秒（创建前缀）。完整流程参考耗时仍需单独报告。
- 新工具代价不是 token 预算造成的（uniform 同预算且代价很小），更像是定向样本的**内容/长度/插入位置**造成。

## 五、结论与下一轮

1. **固定定向内容选择有强收益，但当前实现有明确边界**：Database/Python natural 显著恢复，File 不迁移；新工具受干扰。不能直接把 targeted 作为最终方法。
2. **adaptive 的主要瓶颈是监测覆盖，而不是触发机制**：3/3 触发，但漏掉 Database 导致 natural 远低于 fixed targeted。下一轮 monitor 必须覆盖 database filter-top，并且用 final-like 实例验证“监测下降 → 复习内容迁移”。
3. **优先做一个折中实验，而不是直接进入 C 场景**：在 A 上比较 target fraction 25%/50%/75% 或 5%/10%/20% 预算，重点看 natural 收益与新工具代价的 Pareto 前沿；若 25% target 已保留大部分 natural 收益且 Calendar 恢复，再进入 C 第二→第三阶段。
4. **File 目标单独处理**：需要把 target 样本改成与 final 同分布的新文件/新路径，或增加 file 目标的比例；当前 file last-match 的“同训练文件、换问法”不足以迁移。
5. 下一轮报告应同时给出自然 final、历史 test、新工具、合法工具/参数/执行/答案、以及监测和训练 Token；不要只看单一宏平均。

## 文件

- 宏观结果：`report.md`
- 结构化结果：`results.json`（rows / aggregates / comparisons / costs）
- 分支与原始评估：`branches/`、`evaluation/`
- 共同池与独立题：`../data_round2/`
