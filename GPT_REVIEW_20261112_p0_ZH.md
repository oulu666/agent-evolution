# GPT 审稿意见整理：P0（batched eval、Database 非 target、Calendar 标题计数修复）

- 来源：ChatGPT 桌面端，项目「Agent Self-Evolution」→ 对话「智能体自进化实验规模」。2026-11-12 12:07:33（UTC+8）发送 `scripts/gpt_bridge/msg_20261112_p0.md`（3,331 字，STATUS=SENT），用户确认回复完成后于同日保存全文。
- 原文：`scripts/gpt_bridge/reply_20261112_p0.txt`（完整，以「先重新定义 Coverage Estimator 的粒度，再做 E3-B2；暂不预注册最终 Adaptive Replay 训练臂。」结束）。另有页面转储 `reply_20261112_p0_page.txt`。
- 附件情况：实验报告 `EXT_REPORT_20261112_p0_ZH.md` 曾挂到「询问 ChatGPT」输入框；交接手册因笔记本锁屏未能完成附加与发送。本整理以已发出的 P0 消息和已保存的完整回复为准。GPT 的「开始写作」画布里仍保留其建议冻结的英文口径，不要清空。
- GPT 依据的是消息中的摘要、表格和我们提出的三个决策，没有独立核对 `results.json` 与代码。

## 1. 三条决策的评级

| 决策 | GPT 意见 | 建议写法 / 条件 |
|---|---|---|
| Database S 形曲线降级为模板 / 查询模式覆盖 | **同意降级**，并进一步限定为「目标查询模式上的恢复」，不是一般 Database 能力迁移 | 正式表述见下方冻结英文。不要写成「恢复了 Database 工具的整体能力」 |
| 官方评测改用 batch=1 | **原则上同意**，作为新规范协议 Protocol-B1 | 历史 E3/E4/Calendar v3 的正式协议是 **batch=32、左填充**，不是 batch=1；后续分析以 `stage_report.json` 为准 |
| batch=2 加速 | **暂时有条件接受** | 仅来自 1 个 checkpoint、1 个种子、44 道固定探针（其中 Calendar 20 题）。需跨代表性 checkpoint、三种子、完整 Calendar v3（150 题）和自然语言期末 v2 再验，逐题比对输出、工具调用和得分 |
| 先做 E3-B2 | **仍要做**，但必须按新的 Coverage 定义重新设计 | 做成 Target 身份 × 背景经验 × 经验多样性的机制拆分，而不是再扫一遍条数 |
| Coverage Estimator | **必须先重新定义研究对象** | 从工具级升级为 Tool → Skill → Operation Pattern；区分数据覆盖与模型能力 |
| 自适应 Replay 训练臂 | **暂不启动、暂不预注册最终臂** | 等 E3-B2 支持覆盖机制后再设计 Coverage-Aware Adaptive Replay |

## 2. Q1：Database S 形曲线如何重写

P0 非 target 三种子均值（`database_nontarget_v1`，40 题）：none 0.708，db0 0.717，db1 0.667，db2 0.642，db3 0.667，db4 0.708，db6 0.692。Target 模板测试随独立 target 数从 0 升到 1.00。两套测试难度与分布不同，不可直接比绝对分数，但趋势对比已经足够：

- Target：随定向经验增加持续上升。
- Non-target：无复习模型已约 70.8%，增加 target 数量没有单调提升。种子 08 在 k=2 落到 0.450，种子 09 基本持平 0.750，不能把均值抹平后说「完全稳定」。

因此，「增加 Database 定向经验可以恢复 Database 工具的整体能力」目前不成立。更准确的解释是：增加特定定向经验，可以改善模型在对应查询模式上的执行表现，但目前没有观察到向其他 Database 查询模式的稳定迁移。

**关于「遗忘」的限定（同意采用）：** 若没有 Calendar 学习前、Database 学习完成后的 `filter_top` 基准，就不能严格证明这是遗忘，只能证明当前 checkpoint 在该模式上存在能力缺口。论文统一先用 *target-pattern-specific performance degradation / recovery*；补齐前后阶段证据后再用 forgetting。

GPT 建议正式冻结的英文口径（已在 ChatGPT「开始写作」画布中，勿删）：

> Our Database dose-response experiments initially suggested an S-shaped recovery pattern as the number of independent targeted replay examples increased. However, additional evaluation on non-target query patterns revealed that this improvement was largely confined to the target-aligned query pattern.
>
> Specifically, performance on the target-aligned evaluation increased with the number of targeted examples, whereas the non-target evaluation did not exhibit a consistent monotonic improvement. These results suggest query-pattern-specific recovery rather than general Database skill recovery or cross-pattern transfer.
>
> Therefore, we interpret the observed dose-response relationship as evidence of target-pattern coverage effects, rather than general tool-level capability restoration. Broader transfer across query patterns and database schemas remains unverified.

「工具覆盖」正式改为「操作模式覆盖（Skill / Pattern Coverage）」；但现在证明的只是目标模式上的剂量响应，覆盖是机制解释，仍需 E3-B2 验证。

`group_count_filter` 在非 target 测试中接近地板，增加 target 数量也无明显改善，可能从未充分掌握。Database 内部可能存在多个相对独立的能力单元，下一步不能简单地给 Database 分配更多 Replay，而应先弄清哪些操作模式缺失——这正是 Coverage Estimator 该解决的问题。

## 3. Q2：评测协议

| Batch | 与 batch=1 的一致性（44 题探针） | 意见 |
|---|---|---|
| 1 | 基准 | 官方默认（Protocol-B1） |
| 2 | 44/44 | 候选加速，尚需更广验证 |
| 4 | 43/44 | 不作为官方协议（Calendar「末场结束」翻转） |
| 32 | 43/44 | 不与 batch=1 混用；历史数据保留为 Protocol-B32 |

历史 batch=32 结果不要全部废弃，只能与题集、batch 组成、顺序和生成设置相同的历史结果做组内比较。尤其「末场结束」任务，不能把 B32 和 B1 的逐题结果直接混合。

GPT 还建议追查 **为什么** batch 组成会改变第二步生成：左填充后的 `position_ids`、第二轮工具返回拼接、attention mask、KV Cache、EOS / 停止条件、batch 内排序、首个分歧 token 的 logits margin。若是近似并列 logits 的数值敏感性，也应记录。这既是评测问题，也是小模型 Agent 部署时的稳定性问题。

## 4. Q3：执行顺序与 E3-B2 重设计

最终决定：**先重新定义 Coverage Estimator 的粒度，再按新定义设计 E3-B2，最后才预注册自适应 Replay 新臂。**

Coverage 建议输出三个指标（示意，待我们按现有模板落地）：

| 指标 | 含义 |
|---|---|
| Skill Deficit | 当前某项技能的能力缺口（模型会不会） |
| Pattern Coverage | 经验池实际覆盖了多少操作模式（数据有没有） |
| Experience Diversity | 经验是否只是重复相同模板 |

必须严格区分：经验池覆盖了某个模式，不等于模型已经掌握这个模式。前者是 Coverage Estimator，后者是 Skill Monitor，不能混为一谈。

E3-B2 建议改造成机制拆分：

- **实验 A**：固定同一条 target，改变背景（无 DB / 普通 DB / 其他工具），解释 dose_db1 与 b10_tf25 相差约 34 个百分点的原因；同一条 target 在各组中必须完全一致。
- **实验 B**：改变独立 target 数（1/2/3/4/6），判断是数量增加还是覆盖了更多操作模式。
- **实验 C**：不同 target 子集，总 Replay token 和训练步数不变，判断同样数量是否因模式覆盖不同而收益不同。

各组记录：每条 target 的身份和哈希、重复次数、Target / 普通 DB / 总 Replay token、训练顺序、每个模式的测试表现。

若 E3-B2 支持覆盖机制，再设计 Coverage-Aware Adaptive Replay 闭环：Monitor 发现缺口 → Coverage Estimator 看经验池覆盖 → Selector 选非重复相关经验 → Budget Controller 按收益和成本分配 → 训后再评估。

## 5. 对论文 Story 的影响

- 原问题：如何防止小模型 Agent 在学习新工具时忘记旧工具？
- 更具体：为什么小模型在持续工具学习中会出现细粒度操作模式的能力缺口？如何根据技能缺口和历史经验覆盖，选择有迁移价值的经验，在有限预算下实现精准恢复？
- 建议主线题目：**Skill-Coverage-Aware Continual Tool Learning**（技能覆盖感知的持续工具学习）。
- 四个模块：Skill-Level Forgetting Detection、Operation-Pattern Coverage Estimation、Diversity-Aware Experience Selection、Budget-Constrained Adaptive Replay。
- 相对 E3 审阅时的题目 *Coverage- and Transfer-Aware Adaptive Replay*，本次把「工具」进一步落到「技能 / 操作模式」，方向一致、粒度更细。在 E3-B2 验证之前，不把 Coverage 写成已经证明的机制。

## 6. 我的客观判断（与 GPT 的异同）

- **同意**：S 曲线降级为查询模式特异性恢复；不用「遗忘」除非补齐阶段基准；batch=1 作新规范、历史 B32 分协议保留；batch=2 暂不升格为官方；先重定义 Coverage 再做 E3-B2；暂不预注册最终 Adaptive Replay 训练臂；`group_count_filter` 需单独诊断。
- **补充 1**：GPT 给出的 File / Python 技能树明确是「待验证示意」。重定义时必须对着我们现有训练模板和测试题的真实查询结构来聚类，不能先造一棵树再往上套数据。
- **补充 2**：E3-B2 三个子实验若全因子展开，在本机 RTX 4060（8GB）上过重。落地时应出一版精简方案：优先实验 A（已有种子 08 的只读证据支持「背景经验」解释），实验 B 可尽量复用已有 dose 臂，实验 C 控制规模；正式训练若要 5 种子或更大模型再按小时租云端。
- **补充 3**：非 target 均值不能掩盖种子 08 在 k=2 的下跌。写「没有一致的单调提升」是准确的；不要写成 non-target「保持稳定」。
- **补充 4**：Calendar 标题计数：P0 已确认冻结 v3 的 0.389 是种子地板（系统性少计长列表）；`calendar_title_count_v3fix`（起点 0，none 0.267，ctrl_cal20 种子 08 为 0.300）作附加指标，不改冻结 v3。GPT 本轮回复几乎未展开此点，我们维持原决定。
- **补充 5**：追查 batch 组成改变生成的原因值得做，但是诊断实验，可与 Coverage 定义并行、且不必占满 GPU 长时间训练。优先查 `position_ids`、attention mask 和左填充实现。

## 7. 建议的实际下一步（先不占 GPU）

1. 按现有 File / Database / Python / Calendar 模板，写出 Coverage Estimator 的操作模式粒度和三个指标的可计算定义，并注明哪些模式已有测试、哪些还缺阶段基准。
2. 据此写出 E3-B2 精简实验设计（预注册级），供确认后再上 GPU。
3. 笔记本解锁后，把完整实验报告和交接手册补进同一 GPT 对话（若输入框里仍有未发送的报告附件，一并送出）。
4. batch=2 的跨 checkpoint 验证和 batch 敏感性诊断，等 Coverage 定义稿确认后安排，仍一次只跑一个 GPU 任务。
