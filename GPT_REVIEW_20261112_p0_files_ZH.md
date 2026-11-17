# GPT 全文审阅补充：P0 报告与交接手册（2026-11-12 第二轮）

- 来源：ChatGPT 桌面端，同一对话「智能体自进化实验规模」。2026-11-12 12:33:15（UTC+8）发出带附件的消息（`EXT_REPORT_20261112_p0_ZH.md` + `EXT_HANDOVER_20261112_p0_ZH.md` + 补充说明）；用户于 15:34 确认答完。页面显示「回答已完成」。
- 原文：`scripts/gpt_bridge/reply_20261112_p0_files.txt`（从 `reply_20261112_p0_files_page.txt` 截取最后一个「ChatGPT 说：」至「评价回复」）。约 5,700 字。
- 上一轮只看了消息摘要，见 `GPT_REVIEW_20261112_p0_ZH.md`。本文件只记录读完全文后的新增或收紧之处，不重复已对齐的主线。
- 「开始写作」画布中的英文口径仍在，未清空。

## 1. 总体

GPT 认可实验执行和主要结论，把 P0 定性为「研究纠偏，不只是补充评测」。三项分别回答：测量是否可靠、恢复的是哪一种能力、测试集能否区分能力变化。最终建议不变：先完成细粒度技能定义和 E3-B2，再设计自适应 Replay；不要增加教师模型、多 Agent 或复杂自进化框架。论文潜力「值得继续推进，但不能据此保证 CCF-B」。

## 2. 相对第一轮的新增或收紧

### 2.1 批量评测：两条执行路径，需要协议桥接

- bs1 走 `generate_with_usage`，bs2/4/32 走 `generate_batch_with_usage`。差异不只是 batch size，还涉及两条生成路径。将问题定性为「批组成敏感」可以作为观察性描述，但还不能直接排除实现差异。
- 建议补三个小诊断（不必重新训练）：
  1. 用 batch 生成函数单独处理一条题目，与原单条生成函数比较；
  2. 固定同一题，只改变 batch 邻居和排列顺序；
  3. 记录答案阶段 Top-2 logits 及差值，检查近似并列候选。
- **必须**对关键历史 checkpoint 做一次 batch=1 协议桥接评测（至少 none、tf25、tf50、20% tf50），使用冻结的完整测试集。否则新旧实验因协议不同不能直接比较。
- File / Database / Python 的 24 道探针全部一致，差异集中在 Calendar 末场结束；新 bs1 与历史 E4 为 42/44。这些数字来自报告，GPT 未独立核对 raw 结果。

### 2.2 Database：不要叫「整体遗忘」，也不要简单叫「模板记忆」

- 推荐正式用语：*Operation-Pattern-Specific Forgetting and Recovery*（操作模式特异性的遗忘与恢复）。理由：实验并没有证明模型只记住了固定字符串模板，它可能学的是 `ORDER BY + LIMIT` 所代表的查询操作模式。
- 目前最稳妥的结论仍是：定向经验改善了目标查询模式，尚未观察到向其他模式的稳定迁移。
- **必须补时间基线**才能严格使用「遗忘」：T0（学完 Database）→ T1（学完 Calendar）→ T2（Replay 之后），同一题集测 `filter_top` 及其他模式。若 T0 会、T1 不会、T2 又恢复，证据才完整；否则继续写「能力缺口及其恢复」。
- Target 测试用了历史 batch=32，Non-target 用了本轮 batch=1，不要直接比较绝对分数，后续用统一协议重测。

### 2.3 Calendar v3fix：同时测工具选择和计数

- 认可处理：v3 冻结不改，v3fix 作附加测试、不作新主指标；短列表、Gold 1～3、不能靠「数当天所有场次」猜对。
- 新收紧：`start` 从未调用 `calendar_list`，其 0 分同时包含工具选择失败。v3fix 实际测的是 *Calendar List Selection + Short-List Counting*。建议同时记录：
  - Tool Accuracy（是否正确调用 `calendar_list`）
  - Conditional Counting Accuracy（调用正确后计数是否正确）
  - Joint Success
- 补齐三个种子的 none、ctrl_cal20 和关键 Replay 臂。v3fix 仍用原日历 fixture，真正的多实例泛化以后另做。

### 2.4 交接手册里的工程问题（下一轮 GPU 前处理）

- `p0_run.game_running()`：`tasklist` 用 UTF-8 解码失败后，会把失败当成没有游戏运行，削弱启动前保护。外层脚本还有一次检查，但不建议长期依赖。应改为容错解码，并在下一轮启动前单独测试。
- 日志中 `day=-1.000` 是打印表达式错误，`summary.json` 正确，不影响实验结果。

### 2.5 E3-B2 的普遍性问题

E3-B2 不要只围绕 Database 做完就结束。它应回答：一条历史经验的价值，究竟由所属工具决定，还是由覆盖的具体操作模式决定？若 File、Python 也能出现类似规律，论文贡献不再局限于某一种 SQL 查询。

四个模块仍须分开，不能用一个准确率代替：Coverage Estimator（经验池有什么）、Forgetting Monitor（模型会什么）、Experience Selector（哪些经验值得复习）、Budget Controller（花多少资源）。

推荐题目仍是 **Skill-Coverage-Aware Continual Tool Learning**。

## 3. 我的判断

- **同意**上述全部收紧：两条生成路径要诊断、历史 checkpoint 要做 batch=1 桥接、T0/T1/T2 时间基线、v3fix 三分指标、`game_running` 修复、E3-B2 面向「工具 vs 操作模式」的普遍问题、暂不启动 Adaptive Replay 训练与教师/多 Agent。
- **补充**：第一轮已说不要把 File/Python 技能树凭空造出来。这一轮的操作模式分类必须对着现有训练模板和测试题聚类。T0/T1/T2 和协议桥接都是评测、不重新训练，可在定义稿落地后用已有 checkpoint 排进 GPU 队列；一次只跑一个任务，先确认奥创为狂暴模式、且用户不在游戏中。
- **执行顺序**（本轮开始做，先不占长时间 GPU 训练）：
  1. 修复 `game_running()` 的容错解码，并做一次离线测试。
  2. 按现有 File / Database / Python / Calendar 模板写出操作模式分类和 Coverage 三个指标的可计算定义，并标明哪些模式已有测试、哪些缺 T0 基准。
  3. 写出 E3-B2 精简预注册（优先实验 A；B 尽量复用已有 dose 臂；考虑 File/Python 是否用已有结果做旁证，不把 4060 一次铺满全因子）。
  4. 设计并择机运行三条 batch 路径小诊断，以及后续的协议桥接、T0/T1/T2、v3fix 三种子——均用已有模型，不重新训练。
