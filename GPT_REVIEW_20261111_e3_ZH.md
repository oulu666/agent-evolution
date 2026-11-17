# GPT 审稿意见整理：E3（预算 × 定向比例 + Calendar-only 对照 · Database 剂量）

- 来源：ChatGPT 桌面端，项目「Agent Self-Evolution」→ 对话「智能体自进化实验规模」。2026-11-12 03:34:23（UTC+8）发送 `scripts/gpt_bridge/msg_20261111_e3.md`（1,798 字），约 4 分钟后回复完成。
- 原文：`scripts/gpt_bridge/reply_20261111_e3.txt`（页面里最后一个“ChatGPT 说：”之后的文字）。
- 发送脚本：`send_message_v2.ps1` 报 `composer not found`。原因是新版输入框的类名是 `ProseMirror ProseMirror-focused`，不再是精确的 `ProseMirror`。已**新增** `send_message_v3.ps1`（只把输入框匹配改成 `ProseMirror*`），v2 未改。
- GPT 只看了消息里的摘要和数字，没有核对 results.json、日志和代码。

## 1. 三条结论的评级

| 主张 | GPT 评级 | 建议写法 |
|---|---|---|
| 覆盖驱动恢复 | 有较强初步支持 | “旧工具技能恢复与**技能相关经验的覆盖程度和多样性**密切相关，不只取决于 Replay token 数量”。E3-B2 之前不写成普遍因果规律 |
| 工具特异性 | 有较强初步支持，可能是**核心创新入口** | “Tool-Specific Recovery Dynamics”：Database 阈值型、Python 快速饱和、File 渐进、Calendar 体现资源竞争。不要给 Python/File 贴确定的曲线类型，需要更多剂量点 |
| 10% 甜点 | 只能叫**候选**效率拐点 | “在当前 A 场景及测试范围内，10% 是 tf50 的候选效率拐点；20% 的额外预算带来有限的旧技能收益，同时伴随明显的新技能保持代价”。理由：n=3、10% 非劣效未通过、5% tf25 反而通过、没测 15%、没有预先定义收益/损失的效用权重 |

- 20% 的 Calendar v3 下降：定性为 **Budget-Induced Interference on Untrained Skills（预算增加引发的未训练技能干扰）**。暂时不能断言机制（参数干扰、梯度冲突还是分布偏移），需要梯度或轨迹分析。
- 标题计数恒为 0.389：五项等权宏平均会**稀释**其他子技能的下降，修复它也是为了更准确地测干扰。

## 2. 下一轮优先级（GPT）

| 优先级 | 任务 | 要点 |
|---|---|---|
| P0 | batched eval 一致性 | 30–50 道固定题，batch 1/2/4，同 checkpoint，确定性生成。逐项比对生成文本、工具参数、joint success、分任务偏差；不一致先查 padding / attention mask / EOS / 停止条件 |
| P0 | Database 非 target 测试集 | 未见过的查询结构、不同 schema、表名和字段名、多条件、措辞变化、边界情况。与 target-aligned 集并列报告 |
| P0 | 修复 Calendar 标题计数 | 查题目、标签还是判分器。**不改已冻结的 v3**，另出版本，可加多实例外部测试 |
| P1 | E3-B2，但要重设计 | 把“条数”和“身份 / 背景”分开（见 §3） |
| P1 | 关键臂扩到 5 种子 | none、b10_tf25、b10_tf50、b20_tf25、b20_tf50、ctrl_cal20，必要时加 b05_tf25 |
| P2 | Gap-Aware Replay 预注册 | 现在可以写协议，B2 和测试集修复之后再冻结参数 |
| P2 | Adaptive Replay 实验 | 加 **Oracle Allocation** 上界对照 |

GPT 明确说：**暂时不要**马上启动“按缺口分配”的新臂，也不要急着做教师模型或多 Agent。

## 3. Q3：dose_db1 与 b10_tf25 的差异

GPT 给了五个候选解释：target 身份不同、b10_tf25 有更多普通 DB 经验、重复次数和 token 分布、样本顺序 / 路径依赖、模板对齐导致高估。

建议的 B2 矩阵：
- A：1 条 target，只有 target
- B：同一条 target，加普通 DB 经验
- C：同一条 target，加其他工具经验
- D：2–3 条 target，固定 DB token
- E：4–6 条 target，固定 DB token

每种都换 target 身份重复。严格固定起点、总 token、步数、DB token、评测集和种子配对，并记录每条经验的哈希和重复次数。

**我们已经做的补充核查（只读 replay_plan.json）**：
- 种子 08 两臂用的是**同一条** target（`target_db_filter_top-000`），DB 却是 0.433 对 0.033。
- 种子 09 / 10 的 target 不同（dose_db1 都是 `-001`；b10_tf25 是 `-005` / `-008`）。
- 种子 08 的 b10_tf25 普通 DB 样本更多，其中有 2 条 `db_filter_count`，与 filter_top 测试结构最接近。

所以至少种子 08 支持 GPT 的第 2 种解释（背景经验），“身份”不能单独解释。GPT 设计的 A/B/C 组正好能把它测清楚。

## 4. 研究主线建议

- 不把核心写成“Adaptive Replay Ratio”，审稿人会认为只是按准确率调比例。
- 建议主线：**Coverage- and Transfer-Aware Adaptive Replay**，四个模块：
  1. Forgetting Monitor：已有 G_need，G_cum 还需改进；
  2. Experience Coverage Estimator：新模块，本轮之后的重点；
  3. Transfer Value Estimator；
  4. Budget Controller。
- 暂定题目：*From Fixed Replay to Coverage-Aware Continual Tool Learning: Understanding and Optimizing Skill Recovery in Small Language Models*。
- 核心要证明的是：在相同预算下，理解技能缺口和经验覆盖，比盲目增加 Replay token 更有效。

## 5. 我的客观判断（与 GPT 的异同）

- **同意**：
  - 10% 只能写“候选拐点”；
  - 20% 的下降按“未训练技能干扰”定性；
  - P0 先做 batched eval 和两个测试集修复；
  - B2 必须分开“身份”和“背景”。
- **补充 1**：GPT 把 b20_tf25 的 v3 下降和 tf50 并列为“边际收益低”，但 tf25 从 10% 到 20% 还涨了 +0.178。两者情况不同：tf25 在 20% 时才拿到 4–6 条 DB target，它的收益是真实的覆盖收益，代价也真实。可以利用这个对比说明**“同样覆盖，用更少 token 拿到”才是方法的价值**。dose_db6 在 10% 拿到 DB=1.00、v3 非劣效通过，正是这个点的初步证据。
- **补充 2**：B2 的 A 组（只重复 1 条 target）会让总 token 中重复次数很高，与现有臂的重复上限不同，需要在预注册里写明，避免引入新的混杂。
- **补充 3**：Database 非 target 测试集是**最关键**的一项。如果它不随 k 上升，E3-B 的 S 形曲线只能写成“模板覆盖”，整个“覆盖驱动”的叙事都要降级。所以它应该排在 B2 之前完成，这一点与 GPT 一致。
