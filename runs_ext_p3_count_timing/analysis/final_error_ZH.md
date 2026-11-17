# P3 三臂 Final 失败的错误分析（B1，`db.filter_cmp_top`，只读，CPU）

生成：2026-11-14 13:45 北京时间。脚本 `scripts/p3_final_error_and_forgetting.py`（`.venv/bin/python scripts/p3_final_error_and_forgetting.py`），逐题明细在 `runs_ext_p3_count_timing/analysis/p3_final_error_forgetting.json` 的 `final_errors.cases`。数据来自 `runs_ext_p3_count_timing/evaluation/A_seed*_<臂>/natv2_database/results.jsonl`。

范围：arguments 正确、final 错误的题。这类任务只有一步：一次 `db_query` 调用，再根据结果给出答案，所以不存在「多步未完成」。在这些题里，工具结果（observation）和标准答案的 observation 逐字相同，**模型拿到的 SQL 结果是对的，错在把结果转写成答案这一步。**

## 1. 各环节答对数（30 题，种子 08 / 09 / 10）

| 臂 | arguments | final | Joint | args 对、final 错 |
|---|---|---|---|---|
| pos127 | 25 / 29 / 24 | 23 / 19 / 18 | 20 / 19 / 16 | 23 |
| db4_late | 21 / 26 / 20 | 24 / 26 / 21 | 19 / 26 / 18 | 4 |
| pos95 | 28 / 30 / 27 | 18 / 20 / 16 | 17 / 20 / 14 | 34 |
| （参照）dose_db4 | — | — | 0.800 均值 | 6 |
| （参照）dose_db1_pos143 | — | — | 0.389 均值 | 16 |

两个单条臂的 arguments 已经接近满分（pos95：28–30），短板全在 final。db4_late 正好反过来：final 高，arguments 低。**pos95 低于 dose_db4，主要是 Final 问题，不是 SQL 问题。**

## 2. 失败类型（三臂合计 61 题）

| 类型 | 判定 | pos127 | db4_late | pos95 | 合计 |
|---|---|---|---|---|---|
| **顺序被改写（字母序）** | 答案集合与结果相同，但被重排成字母序，丢掉了 SQL `ORDER BY … DESC` 的顺序 | 15 | 1 | 19 | 35 |
| 顺序被改写（其它） | 集合相同，顺序既不是结果顺序也不是字母序（部分字母序或倒序） | 2 | 0 | 6 | 8 |
| **结果行数 < LIMIT 时补齐** | 结果行数少于 `LIMIT k`，模型编造或重复条目，凑满 k 个 | 6 | 3 | 9 | 18 |
| 读错 / 漏条目 / 格式 | — | 0 | 0 | 0 | 0 |

- **主因一：顺序改写，43 题，占 70%。** 全部出现在查 `employees` 表的题上（Mallory、Carol、Grace…），查 `products` 表的题没有一道是顺序错。
- **主因二：补齐到 LIMIT，18 题，占 30%。** 只出现在结果行数少于 LIMIT 的测试题上（测试集里共 5 道，出错的是其中 4 道），两张表都有。
- 没有「读错工具结果」「漏条目」「答案格式不合法」这类失败。

## 3. 例子（每臂 2 个）

**pos127**
- 种子 08 #011，顺序改写：`SELECT name FROM employees WHERE salary > 91000.0 ORDER BY salary DESC, id ASC LIMIT 2` → 结果 `["Mallory","Carol"]` → 模型答 `["Carol","Mallory"]`（字母序），标准答案 `["Mallory","Carol"]`。
- 种子 08 #009，补齐：`… FROM products WHERE price > 79.0 ORDER BY price DESC, id ASC LIMIT 2` → 结果只有 `["Pro Suite"]` → 模型答 `["Pro Suite","Pro"]`。

**db4_late**
- 种子 08 #011，顺序改写：同上一题，`["Mallory","Carol"]` → `["Carol","Mallory"]`。这是该臂唯一一道顺序错。
- 种子 10 #028，补齐：`… LIMIT 3` → 结果 `["Pro Suite"]` → 模型答 `["Pro Suite","Pro Kit","Pro Set"]`，后两个是编出来的商品名。

**pos95**
- 种子 10 #025，顺序改写（倒序）：`… FROM employees WHERE salary > 72000.0 ORDER BY salary DESC … LIMIT 4` → 结果 `["Mallory","Carol","Grace","Alice"]` → 模型答 `["Alice","Grace","Carol","Mallory"]`。
- 种子 09 #001，补齐：`… FROM employees WHERE age > 44 ORDER BY age DESC … LIMIT 3` → 结果 `["Frank"]` → 模型答 `["Frank","Morgan","Hendry"]`，编出了两个不存在的员工。种子 10 #022 则是重复已有条目：`["Cable","Doohickey","Adapter","Cable"]`。

## 4. 为什么单条 target 会饱和：经验覆盖的答案结构不够

- 单条臂用的 target 是 T-000（种子 08）或 T-001（种子 09 / 10），两条**都查 `products` 表**，答案都是 4 行，正好等于 LIMIT 4。
- 复习池 11 条 target 里，只有 T-003、T-005 是「结果行数 < LIMIT」的例子，而且都在 `employees` 表。单条臂一条都没见过。
- 所以单条 target 无论练多少次（pos95 已有 11 次后续更新），也只学到「products 表、行数刚好等于 LIMIT」这一种答案结构。SQL 写法可以迁移到 employees 题，所以 arguments 接近满分；但 employees 表上的「保留结果顺序」和「行数不足时不补齐」都没被覆盖。
- 字母序偏好的来源：复习池里其它 Database 模式的多行答案几乎都恰好是字母序（`db_list_tables` 11/11，`db_top_n` 9/11）。模型很可能把「答案按字母排」当成了默认格式。测试集 26 道多行题里，有 17 道的正确顺序不是字母序。
- 4 条臂一般会带上至少一条 employees target（种子 08 T-004，09 T-005/006/008，10 T-007/002），顺序错基本消失（db4_late 1 题，dose_db4 1 题）。db4_late 种子 09 含 T-005（行数 < LIMIT 的例子），三类错误都是 0，final 26/30，是三臂里最高的单点。

**结论：Final 的失败不是「读错工具结果」，而是「把结果转写成答案时套了错误的格式先验」。能修好它的是覆盖不同答案结构的经验（不同的表、行数 < LIMIT），不是同一条经验多练几次。** 这给「早而广」里的「广」一个具体含义：要覆盖的是答案结构 / 实体，而不只是条数。它也说明 EAAR 挑经验时，要按失败子类型（顺序、补齐）去覆盖。
