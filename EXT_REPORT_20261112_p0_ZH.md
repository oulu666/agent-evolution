# P0 实验报告：批量评测一致性 · Database 非 target 测试 · Calendar 标题计数修复

- 撰写：2026-11-12 10:40 左右（Asia/Shanghai，UTC+8）。
- 依据：`runs_ext_p0_batched/comparison.json`、`runs_ext_p0_db_nontarget/summary.json`、`runs_ext_p0_cal_titlecount/summary.json`，以及只读使用的 E3 / E4 / Calendar v3 已有评测。
- 设置：Qwen3-0.6B QLoRA，已有 checkpoint 短评测，不重训。一次只跑一个 GPU 任务。未改已冻结的 Calendar v3、自然语言期末 v2，也未写入已有 `runs_ext_e3` / `runs_ext_e4` / `data_ext_*`（本轮新目录除外）。
- 统计口径：3 个种子的均值±样本标准差；三个种子同号记“方向一致”，**本报告不使用“显著”**。

## 0. 一句话结论

**三项都有决断。** （1）批量评测：`batch=2` 与 `batch=1` 在 44 题上逐题文本和得分完全一致，可作为加速候选；`batch=4/32` 会在 Calendar「末场结束」这种临界题上翻答案，不能假装与历史数字完全复现。官方主指标建议默认仍用 `batch=1`。（2）Database 非 target 曲线在 none / dose_db0 就已经高（三种子均值 0.708 / 0.717），并且**不随 k 单调上升**。E3-B 在 `target_db_filter_top` 上的 S 形曲线（0.00→1.00）应降级为**模板覆盖 / 该查询形式上的恢复**，不能写成一般 Database 能力迁移。（3）v3「标题计数」全臂 0.389 是长列表少计造成的平台，不是干预无效；新版 `calendar_title_count_v3fix` 能区分不会（start 0.000）和会（none 0.267、ctrl_cal20 0.300），有区分度但 headroom 有限。冻结的 Calendar v3 未改。

## 1. 批量评测一致性

### 1.1 设置

- 探针：44 题，取自已冻结的自然语言期末 v2（File / Database / Python 各 8 题）和 Calendar v3（5 个子技能各 4 题），`data_ext_p0_batched/probe.jsonl`，sha256 `913ba77ed4c16fa48dee1d7c46dea715ae421a5d95f2e92c4bada2b738e0f6b9`。
- Checkpoint：只读 `runs_ext_e4/branches/A_seed20261108_tf50`。
- 协议：贪心解码（`do_sample=False`），`batch=1` 走原来的单条 `generate_with_usage`；`batch=2/4/32` 走已有的左填充 `generate_batch_with_usage`。不改 `evaluate.py` 的默认行为；`config_for` 里把 `evaluation.batch_size` 设成 32 的历史入口也未改。
- 一个事先发现：E3、E4 和 Calendar v3 的 `stage_report.json` 里记录的协议已经是 `batch_size=32`、左填充、`use_cache=True`。E3 报告里写「评测是 batch-1」与实际不符，是文档错误。本轮对照的「历史 E4 tf50」同样是当时的 batch=32。

### 1.2 逐题一致率

| 比较 | 题数 | 文本一致 | 得分一致 | 完全一致 | 不一致题 |
|---|---|---|---|---|---|
| bs2 vs bs1 | 44 | 44/44 | 44/44 | **1.000** | 无 |
| bs4 vs bs1 | 44 | 43/44 | 43/44 | 0.977 | `calv3-final-last_end-008` |
| bs32 vs bs1 | 44 | 43/44 | 43/44 | 0.977 | `calv3-final-last_end-024` |
| 新 bs1 vs 历史 E4 tf50 | 44 | 42/44 | 42/44 | 0.955 | 上述两题 |
| 新 bs32 vs 历史 E4 tf50 | 44 | 43/44 | 43/44 | 0.977 | `calv3-final-last_end-008` |

File / Database / Python 的 24 题在所有 batch size 上文本和得分都完全一致。全部不一致都出在 Calendar v3 的「末场结束」。

### 1.3 两道不一致题的诊断

两题的**工具调用在所有 batch size 上完全相同**（都是正确的 `calendar_list` + 日期），只有**第二步答案生成**不同：有的给出当天第一场的结束时间，有的给出最后一场。

| 题 | 日期 | 新 bs1 / bs2 | 新 bs4 | 新 bs32 | 历史 E4 tf50（当时 bs32，150 题一起评） | 对错关键 |
|---|---|---|---|---|---|---|
| `last_end-008` | 2026-08-23 | 10:30（错） | 17:00（对） | 10:30（错） | 17:00（对） | 首场结束 vs 末场结束 |
| `last_end-024` | 2026-08-24 | 11:15（错） | 11:15（错） | 16:45（对） | 16:45（对） | 同上 |

这不是判分代码差异，也不是题目或 gold 被改过：同一套 `evaluate.py`、同一套贪心参数，工具调用原文一致，只有答案 token 在「第一场 / 最后一场」之间翻转。更关键的是：**同样宣称 batch=32，新跑的 20 道 Calendar 子集和历史 150 题整集也不完全一致**（`last_end-008` 在新 bs32 上仍是 10:30）。说明这类「取第一个还是最后一个」的投影题，对左填充邻居和批内组成敏感。把它定性为**答案阶段的生成不稳定性 / 批组成敏感**，而不是实现 bug。

墙钟（含加载）：bs1 236.8 秒，bs2 109.0 秒，bs4 51.6 秒，bs32 40.5 秒。bs2 大约快 2.2 倍且本探针完全一致；bs32 再快有限，但会翻题。

### 1.4 建议

- **官方主指标默认仍用 `batch=1`**，与单条生成路径一致，也避免把「末场结束」这类临界题的噪声写进主结论。
- **若只为加速，`batch=2` 是目前唯一与 bs1 完全一致的候选**（44/44）。采用前必须在报告里写明：历史 E3 / E4 / v3 是 batch=32 跑的，其中 Calendar「末场结束」与 bs1/bs2 不可当作同一数字。
- **不要把 batch=4 或 32 当作可与 bs1 互换的官方设置**，也不要假装能完全复现历史 E4 的逐题输出。
- 不改现有评测入口的默认值，以免把已发表的 E3/E4 协议悄悄改掉。

## 2. Database 非 target 测试：迁移还是模板覆盖

### 2.1 设计

- 版本：`database_nontarget_v1`。40 题，5 个模板各 8 题。同一套训练 / 期末用的 `toolbench.db`（故意不用新 schema，避免把「没升」解释成「不认识新表」）。
- 明确不是 `target_db_filter_top` 的近亲改写：禁止 `ORDER BY + LIMIT` 的名单列表。
- 模板与 target 的差异：

| 模板 | 查询形式 | 与 target_db_filter_top 的距离 | 评分 |
|---|---|---|---|
| `filter_count` | `COUNT(*)` + 数值 `col > θ` | 近：训练里有字符串等值的 `db_filter_count`，但不是排序截断列表 | 标量 |
| `filter_mean` | `AVG` + 数值过滤 | 近：与 `db_average` / `db_filter_average` 相关 | 标量 |
| `group_count_filter` | 数值过滤后再 `GROUP BY` | 中：组合技能 | JSON 映射 |
| `min_max` | `MIN`/`MAX`，可带过滤 | 远：训练和 target 都不是这个模板 | 标量 |
| `multi_filter_count` | 字符串等值 **且** 数值比较 | 远：多条件 | 标量 |

- 与训练、复习池、期末 v2、探针的 prompt / 调用 / SQL 重叠为 0。冻结 combined sha256：`9c3b7ea0effa2e88d4e3c882206ecb6d9040c931763c494836cab90eec2aa58d`（题目文件 `1a8566dc7b9f6ee7b07858d95837ddb7ca6a91ba4aecab15ced58e43712db7f2`）。
- 评测：E3-B 的 dose_db0/1/2/3/4/6 以及 E4 none，三个种子全部跑完，`batch=1`，只读 checkpoint，结果写在 `runs_ext_p0_db_nontarget/`。

### 2.2 总曲线（联合成功，40 题）

| 臂 | 种子 08 | 种子 09 | 种子 10 | 均值±样本标准差 |
|---|---|---|---|---|
| none | 0.700 | 0.750 | 0.675 | **0.708±0.038** |
| dose_db0 | 0.700 | 0.750 | 0.700 | **0.717±0.029** |
| dose_db1 | 0.650 | 0.750 | 0.600 | 0.667±0.076 |
| dose_db2 | 0.450 | 0.750 | 0.725 | 0.642±0.166 |
| dose_db3 | 0.525 | 0.750 | 0.725 | 0.667±0.123 |
| dose_db4 | 0.675 | 0.750 | 0.700 | 0.708±0.038 |
| dose_db6 | 0.625 | 0.750 | 0.700 | **0.692±0.063** |

对照 E3-B 的 **target 模板**（DB nat v2，`target_db_filter_top`，三种子均值）：

| k（独立 target 条数） | 0（none / db0） | 1 | 2 | 3 | 4 | 6 |
|---|---|---|---|---|---|---|
| target 期末 v2 | 0.000 / 0.000 | 0.100 | 0.344 | 0.611 | 0.822 | 1.000 |
| 非 target（本轮） | 0.708 / 0.717 | 0.667 | 0.642 | 0.667 | 0.708 | 0.692 |

对照要点：

- none 和 dose_db0 在非 target 上已经高（0.67–0.75），三个种子方向一致；同一批 checkpoint 在 target 模板上是 0。说明 Calendar 训练之后，**被忘掉的主要是 `filter_top` 这种查询形式，不是整个 Database 工具族**。
- 非 target 总分**不随 k 单调上升**。种子 09 在 0.750 上完全走平；种子 08 在 k=2 还掉到 0.450，k=6（0.625）仍低于 none（0.700）；种子 10 在 0.600–0.725 之间波动。dose_db6 − none 为 −0.075 / 0 / +0.025，**不一致**，点估计接近 0。
- 这与 target 曲线（三个种子都从 0 走到 1）形成对比。

### 2.3 分模板（三种子均值）

| 臂 | filter_count | filter_mean | group_count_filter | min_max | multi_filter_count |
|---|---|---|---|---|---|
| none | 0.917 | 0.750 | 0.083 | 0.917 | 0.875 |
| dose_db0 | 1.000 | 0.750 | 0.083 | 0.917 | 0.833 |
| dose_db1 | 0.833 | 0.708 | 0.083 | 0.917 | 0.792 |
| dose_db2 | 0.917 | 0.625 | 0.083 | 0.792 | 0.792 |
| dose_db3 | 0.958 | 0.667 | 0.083 | 0.833 | 0.792 |
| dose_db4 | 1.000 | 0.750 | 0.083 | 0.875 | 0.833 |
| dose_db6 | 1.000 | 0.750 | 0.000 | 0.875 | 0.833 |

- `filter_count`、`min_max`、`multi_filter_count`、`filter_mean` 在 none 上已经高或中高，之后没有随 k 上升的方向一致趋势。
- `group_count_filter` 一直接近地板（种子 09/10 全程 0，种子 08 多为 0.25，dose_db6 三个种子都是 0）。多给 `filter_top` target 也拉不起来这个组合技能。

### 2.4 结论

**应降级为模板覆盖，不能写成一般 Database 能力迁移。** 推荐写法：「在当前 A 场景和这套非 target 题上，E3-B 的 S 形恢复只出现在被剂量化的 `target_db_filter_top` 形式上；其他 Database 查询在不复习该模板时就已经大部分保留，并且不随独立 target 条数 k 上升。」

局限：同一数据库、n=3、非 target 评测是 batch=1（E3 的 target 分数是当时的 batch=32）。none 上 0.70 vs 0.00 的反差很大，协议差异解释不了「一个忘掉、一个还在」。

## 3. Calendar「标题计数」：旧 0.389 的原因和新版

### 3.1 冻结 v3 为什么全臂都是 0.389

只读已有 Calendar v3 结果（含 E3、E4、REF）。0.389 是三个种子的均值：0.433 / 0.300 / 0.433（约 13/30、9/30、13/30）。每个种子里，24/26 个臂的**逐题对错向量完全相同**；唯一明显更低的是尚未训练 Calendar 的 REF start（0.17 / 0.13 / 0.03），以及种子 09 的 b20_tf25 少对 1 题（0.267）。所以这是**种子平台**，不是复习干预的效应。

按 gold 拆开（E4 none，种子 08）：gold 为 1–2 几乎全对，4–5 部分对，**6 / 8 / 10 的联合成功是 0**，即使工具已经正确调用了 `calendar_search`。模型系统性少计（6→5，8→7 或 5，10→8 或 5）。gold=10 的工具观察约 1.7k 字符、10 条完整事件。另外，「一共有多少场 'Sales' session」这类措辞会把工具从 `calendar_search` 引开。v3 为了拉开答案分布，故意收进了高频标题（最多 10 条），正好卡在 0.6B 模型数不清的区间。五项等权宏平均会被这个平台稀释，这一点与 GPT 的提醒一致。**未改 v3。**

### 3.2 新版 `calendar_title_count_v3fix`

- 不是 Calendar v4（多实例泛化检查仍留到以后）。仍用冻结的 v3 日历 fixture，只出新题。
- 30 题全部是 `day_count`：对某一天做 `calendar_list`，再数标题里含某片段的事件。当天 3–6 场，gold 为 1–3，且不等于当天场次数（「把当天全部数一遍」会错）。观察最长 1106 字符。
- 之所以不做全局 `calendar_search` 计数：v3 已经用掉几乎所有 1–5 次命中的片段，只剩 `Budget Review` 一条；高频标题又会回到长列表。允许与 v3 的 `locations` / `last_end` 共用同一天的 `calendar_list` 调用（同一段短观察，新的计数投影）；与训练和其他评测的调用仍禁止重叠。
- 冻结 combined sha256：`944be6ce5a5eb8801957b074dc17430982a4ef9f8bc3a44109ffe8cc00ce5e9f`（题目文件 `84c2e5173142a839dda97a7a20f3cc6309ccb022d1b3e8da93db388f797b305c`）。

短验证（种子 20261108，`batch=1`）：

| Checkpoint | 联合成功 | 工具正确 | 说明 |
|---|---|---|---|
| REF start（stage_03_python，未学 Calendar） | **0.000** | 0.000 | 22 次 `calendar_search`，8 次 `calendar_count`，从未调用 `calendar_list` |
| E4 none（已学 Calendar，无复习） | **0.267** | 0.500 | 15 题工具正确，其中 8 题计数也对，7 题工具对但数错 |
| E3 ctrl_cal20（多练 Calendar） | **0.300** | 0.500 | 与 none 接近 |

**有区分度**：不会（0.000）和会（0.27–0.30）分开了。headroom 仍然在（远未到天花板）。none 与高 Calendar 臂仍然接近，说明这门组合技能在 Calendar SFT 之后只有中等掌握、再多练训练集也涨得不多。建议作为 v3 之外的附加指标，不替换 v3。

## 4. GPU 用时与环境

- 显卡在评测时约 22–30 W、利用率往往只有个位数到约 20%（0.6B + batch=1 吃不满）。启动前记录的功耗上限是 90 W，**没有用 nvidia-smi 改功耗**。不是安静模式那种被锁在约 33 W 的情况，只是模型太小。
- 批量一致性：2026-11-12 09:17:00–09:24:43，约 7.7 分钟（bs1 236.8 s，bs2 109.0 s，bs4 51.6 s，bs32 40.5 s）。
- 标题计数新版：09:25:39–09:31:29，约 5.8 分钟（start 151 s，none 87 s，ctrl_cal20 88 s）。
- Database 非 target：09:31:30–10:27:24，约 55.9 分钟，21 个评测全部 `EVAL_DONE`，写出 `summary.json`。
- GPU 墙钟合计约 **1 小时 10 分钟**（09:17–10:27）。无重训。游戏未运行。

## 5. 下一步建议

1. 论文和后续协议把 E3-B 的 S 形曲线改写成「特定查询形式的覆盖 / 恢复」，把「工具族迁移」降级。覆盖感知的复习应当瞄准被忘掉的**模板 / 子技能**，而不是「整个 Database」。
2. 官方新评测默认 `batch=1`；若要加速，先把 `batch=2` 写进预注册，并注明历史 batch=32 的 Calendar 临界题不可直接对打。
3. `calendar_title_count_v3fix` 可作为附加指标；多实例 Calendar v4、E3-B2、5 个种子、按缺口分配的新臂，仍然等用户确认后再动 GPU。
