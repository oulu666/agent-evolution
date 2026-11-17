# 操作模式与 Coverage Estimator 可计算定义

- 撰写：2026-11-12 傍晚（Asia/Shanghai，UTC+8）。
- 依据：只读聚类 `data_phase2` 训练/测试模板、`data_ext_e4/pool` 复习池、自然语言期末 v2、`data_ext_cal_v3/final_v3`、`database_nontarget_v1`、`calendar_title_count_v3fix`。判定与计数由 `fac_tinyagent/coverage_patterns.py` 复现，本轮对上述语料跑通后：**template_id 与 SQL 结构规则 0 条分歧，0 条未映射**。
- 口径：这是 Coverage Estimator（经验池有什么）和 Skill / Forgetting Monitor（模型会什么）的定义稿，不是新的实验结果。不把 GPT 的 File / Python 示意树当作已验证体系。没有数据支撑的合并或新类，一律不进官方目录。
- 本文件不改冻结数据，也不重新训练。

## 0. 必须分开的三件事

| 名称 | 描述对象 | 能不能互相替代 |
|---|---|---|
| **Pattern Coverage** | 经验池覆盖了哪些操作模式 | 不能代替「模型会不会」 |
| **Experience Diversity** | 这些经验是不是在重复同一条身份 / 同一组参数 | 不能代替「覆盖了几个模式」 |
| **Skill Deficit** | 某个 checkpoint 在某个模式的指定题集、指定评测协议上的能力缺口 | 不能从池子覆盖率反推；没有 T0 时不能改称 forgetting |

推荐的机制用语是 *Operation-Pattern-Specific Forgetting and Recovery*。但若没有同一题集、同一协议上的 T0（学完 Database）/ T1（学完 Calendar）/ T2（Replay 之后），论文先写「能力缺口及其恢复」，不要直接写 forgetting。当前 Database 目标模式的历史评测是 Protocol-B32，非 target 是 Protocol-B1，**绝对分不要直接比**。

## 1. 可复现的归类规则

运行（项目根目录，只用 `.venv`，只读数据）：

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
PYTHONPATH=. .venv/bin/python scripts/classify_operation_patterns.py
# 可选：PYTHONPATH=. .venv/bin/python scripts/classify_operation_patterns.py --json-out /tmp/coverage_inventory.json
PYTHONPATH=. .venv/bin/python -m unittest tests.test_coverage_patterns tests.test_p0_game_running
```

规则优先级：

1. **若条目有 `template_id` 且在映射表中**：以 `TEMPLATE_TO_PATTERN` 为准。这是官方归类。同一种操作、只是措辞不同的模板（例如 `stats_median` / `stats_median_prose` / `target_median_natural`）映射到同一模式；查询结构不同的模板（例如 `db_top_n` 与 `target_db_filter_top`）不合并。
2. **否则走结构回退**：Database 看 `expected_tool` 与 SQL 子句（`COUNT` / `AVG` / `MIN`/`MAX`、`WHERE` 等值或数值比较、`AND`、`GROUP BY`、`ORDER BY`、`LIMIT`），规则写在 `classify_sql_query()`，按从特殊到一般的顺序匹配。Python 的六个统计工具与 `expected_tool` 一一对应。
3. **File / 部分 Calendar 不能只靠工具名和参数键区分**：例如 `calendar_list(date)` 既用于当天计数，也用于列标题、列地点、末场结束、按标题片段计数。缺 `template_id`、`answer_spec` 或可判定的 prompt 线索时，回退必须返回 `*.unknown`，不允许猜测。
4. 结构规则与 `template_id` 发生分歧时，以 `template_id` 为官方标签，并把分歧记下来。本轮语料中分歧为 0。`nontarget_min_max` 的 8 题里有 1 题没有 `WHERE`（`SELECT MAX(salary) AS v FROM employees`），仍归入 `db.min_max`（该模式允许可选过滤），不另造一类。

官方目录共 **42** 个操作模式，见 §2。`data_replay_study` 里另有 `study_*` 题集，属于更早的密封实验，**不纳入本官方目录**，以免把旧体系混进来。

## 2. 各工具下的操作模式表

表中「训练池」指 `data_phase2/*/train.jsonl` 的唯一身份数 / 条数（本数据里二者相同）。「E4 复习池」指 `data_ext_e4/pool`（Calendar 不是复习对象，该池没有 Calendar）。「已知表现」只引用已经写进报告或 `results.json` 的数字，并标明协议；没有测过的格子写「无」。**不要把不同协议的绝对分直接相比。**

T0 列的含义：是否已经在「学完 Database 之后」的 checkpoint 上，用该模式的**完整官方题集**和可引用协议测过。phase2 当时的阶段评测是 Protocol-B1，但 `test_limit=6`，每模式往往只有 1–2 题，**不能当作官方 T0**，只在附录记录。

### 2.1 Database

| 模式 | 判定要点 | 训练池 | E4 复习池 | 测试集 | 官方 T0 | 当前已知表现 |
|---|---|---|---|---|---|---|
| `db.list_tables` | `db_list_tables`；模板 `db_list_tables` / `db_list_tables_test` | 11 | 11 | phase2 test 6 | 无（完整 6 题未跑） | 仅有 phase2 6 题子集，见附录 |
| `db.schema_count` | `db_schema` + 列表数；`db_schema_count` / `db_schema_test` | 11 | 11 | phase2 test 6 | 无 | 同上 |
| `db.count_all` | `COUNT(*)`，无 WHERE；`db_count` | 12 | 12 | **缺考试** | 无 | 无 |
| `db.filter_eq_count` | `COUNT(*)` + WHERE 字符串等值；`db_filter_count` | 12 | 12 | **缺考试**（近邻是 nontarget 的数值版） | 无 | 无。种子 08 的 b10_tf25 背景里曾出现 2 条该模板，见 E3 报告 |
| `db.filter_cmp_count` | `COUNT(*)` + WHERE 数值比较；`nontarget_filter_count` | 0 | 0 | P0 nontarget 8 | 无 | Protocol-B1，三种子均值：none 0.917，db0 1.000，db1 0.833，db2 0.917，db3 0.958，db4 1.000，db6 1.000。不随 k 单调上升 |
| `db.avg_all` | `AVG`，无 WHERE；`db_average` | 12 | 12 | **缺考试** | 无 | 无 |
| `db.filter_eq_avg` | `AVG` + WHERE 字符串等值；`db_filter_average` | 0 | 0 | phase2 test 6 | 无 | 仅有 6 题子集，见附录 |
| `db.filter_cmp_avg` | `AVG` + WHERE 数值比较；`nontarget_filter_mean` | 0 | 0 | P0 nontarget 8 | 无 | Protocol-B1 三种子均值：none / db0 均为 0.750，之后在 0.625–0.750 间波动，不随 k 上升 |
| `db.group_count` | `GROUP BY` + `COUNT`，无数值预过滤；`db_group_count` | 11 | 11 | **缺考试** | 无 | 无 |
| `db.group_avg` | `GROUP BY` + `AVG`；`db_group_average` | 0 | 0 | phase2 test 6 | 无 | 6 题子集上多为 0，见附录 |
| `db.filter_cmp_group_count` | 数值过滤后再 `GROUP BY` + `COUNT`；`nontarget_group_count_filter` | 0 | 0 | P0 nontarget 8 | 无 | Protocol-B1 三种子均值接近地板（none–db4 为 0.083，db6 为 0.000）。增加 `filter_cmp_top` target 拉不起来 |
| `db.top_n` | `ORDER BY` + `LIMIT`，无 WHERE；`db_top_n` | 11 | 11 | **缺考试** | 无 | 无。与目标模式是近邻，不是同一模式 |
| `db.filter_eq_top` | WHERE 字符串等值 + `ORDER BY` + `LIMIT`；`db_filter_top` | 0 | 0 | phase2 test 6 | 无 | 见附录（n=1 的 B1 子集）。**不能**代替 nat v2 目标模式的 T0 |
| `db.filter_cmp_top` | WHERE 数值比较 + `ORDER BY` + `LIMIT`（可带 `id` 次级排序）；`target_db_filter_top` | 0（phase2 训练没有） | 11 | 自然语言期末 v2 Database 30 题 | **无** | 历史 Protocol-B32，三种子均值随独立 target 数 k：none/db0 = 0.000，k=1 0.100，k=2 0.344，k=3 0.611，k=4 0.822，k=6 1.000。这是剂量响应所在的目标模式，不是「整个 Database 工具被恢复」 |
| `db.min_max` | `MIN`/`MAX`，可带可选数值过滤；`nontarget_min_max` | 0 | 0 | P0 nontarget 8 | 无 | Protocol-B1 三种子均值：none/db0/db1 0.917，其后 0.792–0.875，不随 k 上升 |
| `db.multi_filter_count` | `COUNT(*)` + 等值 AND 数值比较；`nontarget_multi_filter_count` | 0 | 0 | P0 nontarget 8 | 无 | Protocol-B1 三种子均值：none 0.875，其后 0.792–0.833，不随 k 上升 |

非 target 40 题总分（Protocol-B1）三种子均值：none 0.708，db0 0.717，db1 0.667，db2 0.642，db3 0.667，db4 0.708，db6 0.692。**不随 k 单调上升**。种子 08 在 k=2 掉到 0.450，不要写成「保持稳定」。

说明：`db.top_n`、`db.filter_eq_top`、`db.filter_cmp_top` 同属「排序截断」家族，但谓词和是否有 `WHERE` 不同，官方目录不合并。是否存在跨这三者的迁移，是待验问题，不是已验证事实。

### 2.2 File

| 模式 | 判定要点 | 训练池 | E4 复习池 | 测试集 | 官方 T0 | 当前已知表现 |
|---|---|---|---|---|---|---|
| `file.read_exact` | `file_read`，返回原文；`file_read_exact` | 16 | 16 | **缺考试** | 无 | 无 |
| `file.count_lines` | `file_read`，数行；`file_count_lines` | 16 | 16 | **缺考试** | 无 | 无 |
| `file.word_count` | `file_read`，数词；`file_word_count` | 0 | 0 | phase2 test 8 | 无 | 仅 6 题子集，见附录 |
| `file.search_first` | `file_search`，第一处匹配；`file_search_first` | 16 | 16 | **缺考试** | 无 | 无。与 last 是同一工具、不同投影，不合并 |
| `file.search_last` | `file_search`，最后一处匹配；`file_last_match` / `target_file_last_match` / `e4_target_file_last_match` | 0 | 16 | phase2 test 8；nat v2 File 30 | 无 | nat v2 为 Protocol-B32：E4 none 三种子均值为 0.378（0.033 / 0.367 / 0.733，种子波动大）；dose_db6 为 0.667。这是 File 的定向目标模式，不是「整个 File 工具」 |
| `file.list_count` | `file_list`，数 `.txt`；`file_list_count` | 16 | 16 | **缺考试** | 无 | 无 |
| `file.list_all` | `file_list`，递归列出全部；`file_list_all` | 0 | 0 | phase2 test 7 | 无 | 仅 6 题子集，见附录 |
| `file.write_char_count` | `file_write` + 字符数；`file_write_report` / `file_write_test` | 16 | 16 | phase2 test 7 | 无 | 仅 6 题子集，见附录 |

File 目前没有类似 Database nontarget 的「非目标模式完整考试」。要用 File 做「操作模式 vs 工具」的旁证，应先在已有 checkpoint 上用 Protocol-B1 补测完整的 phase2 File 测试集（见 E3-B2 预注册），而不是先造一棵新技能树。

### 2.3 Python

六个统计工具各是一个操作模式。训练中的直接提问、phase2 测试中的 prose、以及 nat v2 的 `target_median_natural` 只是措辞差异，归入同一模式。

| 模式 | 判定要点 | 训练池 | E4 复习池 | 测试集 | 官方 T0 | 当前已知表现 |
|---|---|---|---|---|---|---|
| `py.mean` | `stats_mean`；`stats_mean` / `stats_mean_prose` | 14 | 14 | phase2 test 5 | 无 | 仅 6 题子集，见附录 |
| `py.median` | `stats_median`；含 `target_median_natural` | 14 | 28（14 条训练 + 14 条 target） | phase2 test 5；nat v2 Python 30 | 无 | nat v2 Protocol-B32：E4 none 三种子均值 0.789（0.600 / 1.000 / 0.767）；有旧工具复习的臂通常更高（例如 dose_db6 0.989）。这是 Python 的定向目标模式 |
| `py.std` | `stats_std` | 13 | 13 | phase2 test 5 | 无 | 仅 6 题子集 |
| `py.percentile` | `stats_percentile` | 13 | 13 | phase2 test 5 | 无 | 仅 6 题子集 |
| `py.correlation` | `stats_correlation` | 13 | 13 | phase2 test 5 | 无 | 仅 6 题子集 |
| `py.regression` | `stats_linear_regression` | 13 | 13 | phase2 test 5 | 无 | 仅 6 题子集 |

Python 同样缺少「非 median 模式」在 Replay 之后的完整、统一协议评测。phase2 测试已经覆盖六个模式各 5 题，适合做旁证，但历史 phase2 阶段评测被截成了 6 题。

### 2.4 Calendar

Calendar 的训练模板没有进入 E4 复习池（复习对象是旧工具）。v3 与 v3fix 是后加的考试，若干模式在训练里从未以相同投影出现。

| 模式 | 判定要点 | 训练池 | 测试集 | 官方 T0 | 当前已知表现 |
|---|---|---|---|---|---|
| `cal.count_date` | `calendar_list(date)` 清点当天全部事件；`calendar_count_date` / `nf2_cal_nl_count_date` | 14 | nat v2 Calendar 5 | 无 | 含在 nat v2 Calendar 30 题宏平均中（E4 none 三种子均值 0.689，Protocol-B32）。没有单独官方分模式 T0/T1/T2 全表 |
| `cal.count_month` | `calendar_count(month)` | 14 | nat v2 5 | 无 | 同上 |
| `cal.list_titles` | `calendar_list`，按字母序列出标题 | 13 | nat v2 5 | 无 | 同上 |
| `cal.list_locations` | `calendar_list`，地点去重；`calendar_list_locations` / `cv3_locations` | 0 | phase2 test 10；v3 30 | 无 | v3 为 Protocol-B32：E4 none 三种子均值 0.322。冻结 v3，不改题 |
| `cal.search_dates` | `calendar_search`，列出日期 | 13 | nat v2 5 | 无 | 见 nat v2 宏平均 |
| `cal.search_count` | `calendar_search`，清点标题命中；`cv3_search_count` | 0 | v3 30 | 无 | Protocol-B32，E3/E4 多种子、多臂上是种子平台（三种子均值 0.389），不是干预效应。长列表少计。不改 v3 |
| `cal.attendees_list` | `calendar_attendees`，列出名单 | 13 | nat v2 5 | 无 | 见 nat v2 宏平均 |
| `cal.attendees_count` | `calendar_attendees`，清点人数；phase2 / `cv3_attendee_count` | 0 | phase2 test 10；v3 30 | 无 | v3 Protocol-B32：E4 none 三种子均值 0.822 |
| `cal.free_first` | `calendar_free_slots` 取第一段空闲 | 13 | nat v2 5 | 无 | 见 nat v2 宏平均。与 `cal.free_latest` 不合并 |
| `cal.free_latest` | 取最后一段空闲；phase2 / `cv3_free_latest` | 0 | phase2 test 10；v3 30 | 无 | v3 Protocol-B32：E4 none 三种子均值 0.644。该模式对批组成敏感（P0 的「末场结束」翻转发生在 `cal.last_end`，不是本模式，但同属「取第一个还是最后一个」类投影） |
| `cal.last_end` | `calendar_list`，当天最后一场结束时间；`cv3_last_end` | 0 | v3 30 | 无 | v3 Protocol-B32：E4 none 三种子均值 0.522。P0 显示答案阶段会对 batch 邻居翻转；官方新评测用 Protocol-B1，历史 B32 分协议保留 |
| `cal.day_title_count` | `calendar_list`，清点标题含某片段的事件；`cv3fix_day_count` | 0 | v3fix 30 | 无（start 不是 T0 Database，只是未学 Calendar） | 附加指标，不替换 v3。Protocol-B1，目前只有种子 08：REF start 联合成功 0.000、工具正确 0.000（从未调用 `calendar_list`）；E4 none 0.267 / 工具 0.500；ctrl_cal20 0.300 / 工具 0.500。定义必须同时报 **Tool Accuracy、Conditional Counting Accuracy（工具正确条件下的计数正确率）、Joint Success**。start 的 0 分同时包含工具选择失败 |

## 3. 三个指标的可计算定义

输入一律是：一组经验或一组已评分结果，以及本文件的官方模式目录 \(P\)（\(|P|=42\)，或任务声明的子目录 \(P'\subseteq P\)）。身份函数 `experience_identity`：优先使用 `episode_id`；没有则对 `template_id` + 工具 + 参数 + prompt 做 SHA-256。实现见 `pattern_coverage()`、`experience_diversity()`、`skill_from_results()`、`forgetting_and_recovery()`。

### 3.1 Pattern Coverage（经验池有什么）

对经验多重集 \(E\)、模式 \(p\in P\)：

- \(\mathrm{Slot}(p)=|\{e\in E: \mathrm{pattern}(e)=p\}|\)
- \(\mathrm{Unique}(p)=|\{\mathrm{id}(e): e\in E,\ \mathrm{pattern}(e)=p\}|\)
- \(\mathrm{Covered}(p)=\mathbf{1}[\mathrm{Unique}(p)\ge 1]\)
- \(\mathrm{PatternCoverage}(E,P)=\frac{1}{|P|}\sum_{p\in P}\mathrm{Covered}(p)\)

必须同时报告覆盖向量 \(\mathrm{Unique}(p)\) 和未覆盖名单，不能只报一个标量。标量相等可能来自完全不同的模式集合。Coverage Estimator 到此为止，不再把准确率算进来。

### 3.2 Experience Diversity（是不是在重复）

- 全局独特性：\(D_{\mathrm{id}}(E)=|\{\mathrm{id}(e):e\in E\}|/|E|\)（1 表示没有重复投放，接近 0 表示大量重复）
- 模式内独特性：\(D_{\mathrm{id}}(p)=\mathrm{Unique}(p)/\mathrm{Slot}(p)\)
- 参数多样性：同一模式下不同 `expected_arguments`（含 SQL）签名的个数
- 可选的模式分布熵 \(H(\{\mathrm{pattern}(e)\})\)，以及用已出现模式数归一化的熵。**高熵不等于高覆盖**：只在 2 个模式上均匀投放，归一化熵可以很高，但对 42 个模式的 Coverage 仍然很低

重复一条有价值的 target，是多样性事实，不是覆盖事实；必须单独记录重复次数。

### 3.3 Skill Deficit（模型会什么）

对 checkpoint \(M\)、模式 \(p\) 的指定考试 \(Q_p\)、评测协议 \(\pi\)（新官方协议为 Protocol-B1，即 `batch=1` + `generate_with_usage`；历史 E3/E4/v3 为 Protocol-B32）：

- \(\mathrm{Skill}(M,p,\pi,Q_p)=\overline{\mathrm{JointSuccess}}\)
- \(\mathrm{Deficit}=1-\mathrm{Skill}\)
- 同时记录 Tool Accuracy；对计数类任务再记 Conditional Counting Accuracy \(=\overline{\mathrm{final\_correct}\mid \mathrm{tool\_correct}}\)
- 若同一 \(Q_p\)、同一 \(\pi\) 上有阶段分数：\(\mathrm{Drop}=\mathrm{Skill}_{T0}-\mathrm{Skill}_{T1}\)，\(\mathrm{Recovery}=\mathrm{Skill}_{T2}-\mathrm{Skill}_{T1}\)。**只有 \(T0\) 存在时才允许使用 forgetting 一词**

建议的阶段定义（与 E3/E4 的实际训练图一致，而不是望文生义）：

- **T0**：`runs_phase2/A_seed*/checkpoints/stage_02_database`（刚学完 Database）。建议同时测 `stage_03_python`，因为 E3/E4 的起点适配器就是它，而且 Python 阶段也可能改变 Database 分数。
- **T1**：`runs_ext_e4/branches/A_seed*_none/checkpoint`（在共享 prefix 上只学 Calendar、不复习）。不要把 `stage_04_calendar` 当作与 T2 可直接对比的 T1：E3/E4 各臂并不是从这份第一次 Calendar SFT 接着训的，而是从 `stage_03_python` + 共享 prefix（`runs_ext_e4/prefixes/A_seed*`，中点 80，seed 08 的 `state_sha256=5702cc7e…`）分支。
- **T2**：相应 Replay 臂的 checkpoint。

阶段评测必须写明协议。用 B1 重测历史臂，才能和 P0 非 target、v3fix 放在同一张表里。

## 4. 以后应补什么

1. **缺官方 T0 / 同题集 T0–T2（最优先）**：nat v2 的 `db.filter_cmp_top` / `file.search_last` / `py.median`，P0 非 target 五个模式，Calendar v3 五个模式，v3fix 的 `cal.day_title_count`。在 `stage_02_database`、`stage_03_python`、E4 none 和关键 Replay 臂上用 Protocol-B1 测。在此之前，目标模式上的 S 形曲线只写「能力缺口及其恢复」。尤其要注意：`db.filter_cmp_top` **从未进入 phase2 训练**，T0 完全可能本来就不会，不能先验地当作遗忘。
2. **缺考试的训练模式**：`db.count_all`、`db.filter_eq_count`、`db.avg_all`、`db.group_count`、`db.top_n`；`file.read_exact`、`file.count_lines`、`file.search_first`、`file.list_count`。若要从「工具级」对照里排除「其实只是没考」，需要补小而干净的考试，或先用已有 phase2 测试做 File / Python 旁证。
3. **近邻模式是否迁移**：`db.top_n` ↔ `db.filter_eq_top` ↔ `db.filter_cmp_top`；`file.search_first` ↔ `file.search_last`；`cal.free_first` ↔ `cal.free_latest`。这是机制问题，不是已经成立的合并理由。
4. **v3fix 三种子**：目前只有种子 08 的 start / none / ctrl_cal20。补 none、ctrl_cal20 和关键 Replay 臂，并同时报三个指标。
5. **协议桥接**：关键历史 checkpoint 用 Protocol-B1 重测完整冻结集，才能把新旧数字放在一起。
6. 不要为了填表去凭空新增 File / Python「技能层级」。先把现有模板测全。

## 5. 与 GPT 示意树的关系

GPT 给出的 File / Python 技能树明确是「待验证示意」。本目录只保留训练模板和测试题里真实出现的查询结构。例如没有把「读文件」再拆成未在数据中出现的子技能，也没有把六个统计工具抽象成单一的「Python 工具能力」。若以后新题或新经验表现出稳定、可复现的新结构，再以「待验证」名义提案，经题目冻结后才能进入官方目录。

## 附录 A. phase2 阶段评测（Protocol-B1，`test_limit=6`）——不足以为官方 T0

当时每个家族只评 6 道 phase2 测试题，结果文件里没有 `template_id`，本轮用 `episode_id` 还原。分数字段是 `final_correct`。样本极小，只用来说明「不是完全没有旧评测」，以及「不能把目标模式的低分先验写成遗忘」。

`db.filter_eq_top`（每种子 1 题 `database-test-db_filter_top-000`）：

| 种子 | 未训练 | 学完 File | 学完 Database（T0 候选） | 学完 Python | 学完 phase2 Calendar |
|---|---|---|---|---|---|
| 08 | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |
| 09 | 0/1 | 0/1 | 1/1 | 1/1 | 1/1 |
| 10 | 0/1 | 0/1 | 1/1 | 0/1 | 0/1 |

种子 08 在学完 Database 后这道题已经是错的；种子 10 在学完 Python 后从对变错。这与 nat v2 的 `db.filter_cmp_top` 还不是同一模式，n=1，不能外推，但足以提醒：T0 必须实打实去测，而且 `stage_03_python` 不能省。

同一次 6 题评测里，`db.list_tables` / `db.schema_count` 在学完 Database 后三个种子多为 1/1；`db.group_avg` 三个种子、各阶段几乎都是 0/1；`file.word_count` 基本为 0/1。这些只能当线索。

## 附录 B. 本轮代码位置

- 定义与指标：`fac_tinyagent/coverage_patterns.py`
- 只读清单脚本：`scripts/classify_operation_patterns.py`
- CPU 测试：`tests/test_coverage_patterns.py`
