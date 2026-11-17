# P2 实验报告：经验价值梯度打分 pilot（只做前向+反向，不训练）

- 撰写：2026-11-13 18:45 左右（Asia/Shanghai，UTC+8）。
- GPU：2026-11-13 18:28:47 开始，18:40:17 结束，共 689.9 秒（约 11.5 分钟），6 次打分（2 个打分点 × 3 种子），每次 98.5–174.1 秒，峰值显存 4.02 GB。开跑前检查：Windows tasklist 无 `r5apex`，`enforced.power.limit` 126.73 W，无其它 GPU 计算进程；运行中每 50 条候选复查一次游戏进程，未触发。
- 脚本：`scripts/p2_grad_utility_pilot.py`（新增）。结果：`runs_ext_p2_grad_pilot/`（`scores_<打分点>_seed<种子>.json`、`results.json`、`tables_ZH.md`、`score_run_*.json`）。日志：`logs_ext/p2_grad_pilot_20261113.log`。
- 本报告所有数字来自 `runs_ext_p2_grad_pilot/tables_ZH.md` / `results.json`，以及 P1 的 B1 逐题结果。不改任何已有 runs*/data* 文件，不改冻结测试集，不训练、不保存模型。

## 1. 问题

在复习开始前的模型状态上，「一条候选经验的训练损失梯度」与「薄弱模式探针的损失梯度」方向越一致，这条经验是否越有价值？如果这个打分能 (a) 排出 target > 近邻 > 普通背景，(b) 解释已有复习臂的 B1 实测成绩（尤其 tf25 为什么高于实验 A 两臂），(c) 区分 `py.median` 的同说法和另一种说法，它就值得作为「经验价值估计」的起点。

## 2. 设置

**打分点（每种子两个）：**

- **prefix（主分析）**：`runs_phase2/A_seed*/checkpoints/stage_03_python` 适配器，再载入 `runs_ext_e4/prefixes/A_seed*/training_state.pt` 的可训练参数（载入后参数哈希与 manifest 一致；sha256 08 `5702cc7e…`、09 `ed04911a…`、10 `0c036c35…`）。这是 Calendar 阶段第 80 个新样本处的共享 midpoint，E4 / E3 / E3-B2 所有复习臂和 none 臂都从这里分支，复习条目从第 87 个新样本起插入，所以它才是「复习训练前的起点」。
- **stage04（稳健性对照）**：`runs_phase2/A_seed*/checkpoints/stage_04_calendar`，即 phase2 原始 Calendar 阶段的终点。说明：任务书里把 stage_04 写成「none 臂的 phase2 末端」，这一点不准确。none 臂是 `runs_ext_e4/branches/A_seed*_none/checkpoint`，它和各复习臂一样从上面的 prefix 分支，不是从 stage_04 接着训。因此 prefix 作主分析，stage04 两份结果都报告。

**候选经验**：`data_ext_e4/pool/{database,file,python}.jsonl` 全部 281 条，加上各臂 `replay_plan.json` 里出现过的 46 条 Calendar 条目（ctrl_cal 臂），共 327 条。45 个计划（15 臂 × 3 种子）里的条目全部能找到，没有缺失。检验 (a) 只统计实际进过某个复习计划的条目。

**分组规则**（相对 `db.filter_cmp_top` = 数值比较 WHERE + ORDER BY/LIMIT，依据 `COVERAGE_DEFINITIONS_20261112_ZH.md` §2.1 的模式目录）：

- target：`db.filter_cmp_top`。
- near_sort（同属「排序截断」家族，谓词不同或没有 WHERE）：`db.top_n`、`db.filter_eq_top`。
- near_filter（有 WHERE 过滤、没有排序截断）：`db.filter_eq_count`、`db.filter_eq_avg`、`db.filter_cmp_count`、`db.filter_cmp_avg`、`db.filter_cmp_group_count`、`db.multi_filter_count`。
- db_other：其余 Database 模式；python、file、calendar 各自一组（普通背景）。
- E4 池里实际出现的近邻只有 `db.top_n`（near_sort，进过计划 9 条）和 `db.filter_eq_count`（near_filter，10 条），与 P1 coverage_ledger 记的近邻一致。

**探针**：

- fct_probe：nat v2 Database（`db.filter_cmp_top`）题号为偶数的 15 题。题号为奇数的 15 题作留出半，只用于检验 (b)，不参与梯度。
- list_tables：phase2 Database 测试里 `db.list_tables` 的 6 题，用于合理性检查。
- median_nat：nat v2 Python 30 题（`target_median_natural` 说法）。
- median_prose：phase2 Python 测试里 `py.median` 的 5 题（「middle value」说法）。

**计算**：损失与训练相同（`tokenize_episode`，只监督 assistant token，autocast 与训练 dtype 一致，bf16）。`model.eval()` 关闭 dropout，batch=1，只对可训练 LoRA 参数求梯度，并在 fp32 中展平。探针梯度取各题梯度的平均。每条候选记录与每个探针的余弦和点积。

## 3. 结果

### 3.0 合理性检查（list_tables 探针）

6 个打分点 × 种子里，`db.list_tables` 条目的余弦均值都在 0.945–0.958，其它条目在 −0.008 到 0.020。win = 1.000，余弦最高的 11 条全是 `db.list_tables`。说明这套打分能可靠地按模式把对应经验挑出来。

### 3.1 检验 (a)：fct 探针下 target > 近邻 > 普通背景？

prefix 打分点（实际进过计划的条目，余弦均值；win = 随机一对里前者更高的概率）：

| 种子 | target | near_sort（top_n） | near_filter（filter_eq_count） | db_other | python | file | calendar | target>近邻 win | 近邻>背景 win |
|---|---|---|---|---|---|---|---|---|---|
| 08 | 0.766 | 0.036 | 0.103 | 0.060 | 0.031 | 0.024 | 0.037 | 1.000 / 1.000 | 0.833 |
| 09 | 0.781 | −0.009 | 0.133 | 0.074 | 0.038 | 0.030 | 0.027 | 1.000 / 1.000 | 0.557 |
| 10 | 0.827 | 0.025 | 0.098 | 0.076 | 0.035 | 0.029 | 0.031 | 1.000 / 1.000 | 0.691 |

stage04 打分点方向相同：target 0.682–0.808，near_sort 0.006–0.042，near_filter 0.093–0.130，近邻>背景 win 0.627–0.858。

- **target 远高于其它所有组**，三种子、两个打分点 win 全部是 1.000，余弦约 0.7–0.8，其它组都在 0.15 以下。
- **「近邻 > 普通背景」只对一半近邻成立。** `db.filter_eq_count`（near_filter）三种子方向一致略高于背景（0.10–0.13 对 0.02–0.08）。`db.top_n`（near_sort，排序截断家族）余弦接近 0（−0.009 到 0.042），**不高于普通背景**。按余弦算，组均值顺序 target > 近邻 > 背景在 6 个打分点 × 种子里都成立，但这是 filter_eq_count 撑起来的；按点积算只有 3/6 成立。
- **意外发现**：非 target 模式里余弦最高的是 `db.group_count`（prefix 0.322 / 0.337 / 0.359，stage04 0.239–0.360），比任何近邻都高。我们的近邻规则没有把它列进来。这是梯度打分给出的一个可检验预测，不是已验证事实。

### 3.2 检验 (b)：用已有干预结果做外部检验（臂 × 种子，45 个点）

结果变量：B1 nat v2 Database 的留出半（15 题）正确率；全 30 题的结果几乎相同。

| 预测量 | prefix：Spearman 全部点 | prefix：种子内 08/09/10 | stage04：Spearman 全部点 |
|---|---|---|---|
| **n_target（朴素：target 槽数）** | **0.919** | 0.979 / 0.969 / 0.922 | 0.919 |
| sum_cos（计划内余弦和） | 0.877 | 0.890 / 0.921 / 0.900 | 0.886 |
| mean_cos | 0.903 | 0.948 / 0.923 / 0.911 | 0.922 |
| sum_dot | 0.904 | 0.956 / 0.966 / 0.930 | 0.901 |
| sum_cos_nontarget（去掉 target 部分） | −0.036 | −0.077 / 0.014 / −0.221 | −0.137 |
| n_near（近邻槽数） | 0.240 | 0.266 / 0.338 / 0.241 | 0.240 |

**只含 1 条 target 的臂**（tf25、target_other、target_dbbg、dose_db1；12 个点），这正是要解释 tf25 的地方：

| 预测量 | prefix Spearman（留出半） | stage04 Spearman（留出半） |
|---|---|---|
| sum_cos | 0.145 | 0.522 |
| sum_cos_nontarget | 0.254 | 0.649 |
| sum_cos_target（target 那一条的余弦） | −0.816 | −0.539 |
| sum_dot | −0.155 | 0.113 |

逐种子看（prefix，按 sum_cos 降序）：

- 种子 08（四臂是同一条 T-000，唯一干净的比较）：dbbg 1.865 > tf25 1.482 > dose_db1 1.426 > other 1.396；实测 tf25 0.400，其余 0.033–0.100。打分把 tf25 排第 2，排第 1 的 dbbg 实测只有 0.100。stage04 也是 dbbg 1.694 > tf25 1.570。
- 种子 09：tf25 用的是 T-005，余弦 0.757，低于 A 组的 T-001（0.917），sum_cos 在四臂里排最后，但实测最高（0.667）。
- 种子 10：tf25（T-008）sum_cos 2.396，排第一，实测也最高（0.233）。

判断：

- 臂之间的差别几乎全部来自「有几条 target」。梯度分数和 n_target 的解释力相当（0.88–0.92 对 0.92），**去掉 target 部分后的分数和成绩没有关系**（−0.22 到 0.01）。打分没有提供超出朴素预测量的额外解释力。
- **打分解释不了 tf25 为什么高于实验 A 两臂。** 三个种子里只有种子 10 排对；种子 08 是同一条 T* 的干净比较，排错；种子 09 方向相反。stage04 打分点上，非 target 部分在 1-target 子集里有 0.649 的 Spearman，但只有 12 个点，而且种子 08 仍把 dbbg 排在 tf25 前面，只能算微弱线索。

### 3.3 检验 (c)：`py.median` 同说法 vs 另一种说法

| 打分点 | 种子 | median_nat 探针：natural 均值 / stats_median 均值 / 其它 Python | win(natural > stats_median) | median_prose 探针 win |
|---|---|---|---|---|
| prefix | 08 | 0.579 / 0.170 / 0.057 | 1.000 | 0.694 |
| prefix | 09 | 0.679 / 0.357 / 0.120 | 0.929 | 0.980 |
| prefix | 10 | 0.565 / 0.213 / 0.061 | 1.000 | 0.791 |
| stage04 | 08 | 0.669 / 0.179 / 0.048 | 1.000 | 0.862 |
| stage04 | 09 | 0.524 / 0.204 / 0.099 | 1.000 | 0.990 |
| stage04 | 10 | 0.560 / 0.096 / 0.041 | 1.000 | 0.939 |

- **nat 探针：同说法经验（`target_median_natural`）的余弦明显高于另一种说法（`stats_median`，「Compute the median…」）**，三种子、两个打分点 win 都在 0.929–1.000；`stats_median` 又高于其它 Python 模式（win 0.795–0.998）。这和 B1 实测里「同说法才恢复」方向一致。
- prose 探针（「middle value」，5 题）：win 也偏向 natural（0.694–0.990），但所有余弦都接近 0（−0.016 到 0.046），**信号太弱，不作结论**。

### 3.4 一个方法上的限制：平均 token 损失会稀释关键 token

fct 探针在 prefix 上的平均损失只有 0.065–0.087，可这些模型在该模式上的 B1 正确率是 0。median_prose 探针损失 0.009–0.032，种子 09 却在 none 上 0/5。原因是这些失败往往只错在少数决定性 token 上（SQL 的排序 / LIMIT 子句、工具名 `stats_mean` 对 `stats_median`），平均到整条回答后，梯度被大量已经会的 token 主导。所以当前打分更像「这条经验和探针在形式上有多像」，而不是「它能修正哪一个错误」。这可能就是它解释不了 tf25 的原因之一。

## 4. Go / No-go

**结论：有条件的 Go，只做「同模式 / 同说法经验检索器」的起点；作为「跨模式价值估计器」是 No-go。**

- **成立的部分（Go）**：不用任何人工模式标签，梯度余弦就能把同模式经验排到最前（target win 1.000，list_tables win 1.000），也能把同说法排在另一种说法前面（median_nat win 0.93–1.00），三种子、两个打分点方向一致。现有 B1 结果说明，恢复主要取决于「复习池里有没有同模式、同说法的经验」，所以这个能力本身就有用。它可以作为免标签的经验选择器，在新模式、新工具上自动挑出对应经验。
- **不成立的部分（No-go）**：它没有提供超出「target 条数」的解释力（臂级 0.88–0.92 对 0.92；非 target 部分约 0）；解释不了 tf25 高于实验 A 两臂（种子 08 同一 T* 下排错）；按我们的模式目录，近邻里只有 `db.filter_eq_count` 略高于背景，`db.top_n` 不高于背景。所以不能说梯度打分「估计出了经验价值」，更不能用它来支撑近邻迁移的说法。
- 对下一步的影响：
  1. 不建议马上做五臂近邻消融。梯度打分预测 `db.top_n` 的作用约为 0，`db.filter_eq_count` 有一点，`db.group_count` 最高。如果要做近邻消融，应该把这些写成预注册预测，先写修订再开训。
  2. tf25 的差距还有一个更直接的候选来源：09/10 的 tf25 用的是不同的 target 条目（T-005、T-008，A 组是 T-001）。梯度没有把 T-005 排得比 T-001 高（0.757 对 0.917），所以如果真是 target 条目本身的差别，梯度打分也没有捕捉到。
  3. 如果继续改进估计器，最便宜的一步是改探针损失：只在模型实际出错的决定性 token 上算（例如用 none / prefix 模型的贪心输出和金标准第一个分叉的 token），不再对整条回答取平均。这只需要再跑一次约 12 分钟的打分，不用训练。

## 5. 限制

- 只有 3 个种子；1-target 子集只有 12 个点，而且其中 09/10 的 tf25 和 A 组 target 条目不同，混入了「条目本身」的差别。
- 打分点是复习前的静态状态。复习在 23 步里逐条插入，模型会变，单点梯度只是一阶近似。
- 近邻规则是按 SQL 结构写的定义，E4 池里每种近邻只有约 10 条。
- 检验 (b) 的结果变量用留出半（15 题），每题相当于 0.067；全 30 题版本的结论相同。
- median_prose 探针只有 5 题，余弦接近 0，不作结论。

## 6. v2：分叉 token 版探针损失（2026-11-13 晚，北京时间）

本节为追加，不改上文和 v1 输出。GPU：2026-11-13 18:51:20 开始，19:32:59 结束，共 **2498.9 秒**（约 41.6 分钟），6 次打分，每次 299.6–623.8 秒，峰值显存 4.22 GB。开跑前检查：tasklist 无 `r5apex`，功耗上限 127.25 W，没有其它 GPU 进程；运行中每 50 条候选复查一次游戏，没有触发。分析只用 CPU，用已有 `scores_*.json` 重新生成，19:35 写出；生成时 6 个 scores 全部纳入。另外补了一项只读 CPU 检查（§6.5）。

- 脚本：`scripts/p2_grad_utility_pilot_v2.py`（`--phase score` 用 GPU，`--phase analyze` 只用 CPU）、`scripts/p2_target_timing_check.py`（CPU）。
- 输出：`runs_ext_p2_grad_pilot/v2/`（`scores_{prefix,stage04}_seed*.json`、`results.json`、`tables_ZH.md`、`target_timing.json`、`target_timing_ZH.md`、`score_run_20261113_193259.json`）。日志：`logs_ext/p2_grad_pilot_v2_20261113.log`。

### 6.1 方法改动（只改探针损失）

- 对每道探针题，用当前打分点的模型按 B1 方式贪心生成第一轮工具调用：prompt 为 system+user，`generation=True`，max_new_tokens 128。然后与金标调用逐 token 对齐，取第一个不一致的位置 j。
  - **d1（主）**：c[j]，加上之后 1 个金标 token。
  - d0：只取 c[j]。
  - dall：从 c[j] 到第一轮结束（对照）。
- **全对题**：取金标里工具名字符串，以及每个参数值的 JSON 文本（无参数时为 `{}`），字符区间有重叠的 token 作为关键 token。三个变体都用这一组。
- 探针 CE 的上下文就是 B1 的生成 prompt（Qwen3 在 `enable_thinking=False` 时末尾带空的 `<think></think>`），金标续写是在它后面拼上第一轮金标内容再分词得到的。只看第一轮，第二轮 answer 不进探针损失。
- 候选梯度、打分点（prefix 为主，stage04 为对照）、候选池、探针题集、留出半、近邻规则都与 v1 相同。

**分叉点抓到的就是 B1 的真实失败**（`tables_ZH.md` §0）：

- fct 15/15 题都分叉。种子 08/10 主要是 ` WHERE→ ORDER`（漏掉 WHERE，各 12–13 次）；种子 09 主要是 ` ASC→"}}`（漏掉次级排序和 LIMIT，prefix 13 次，stage04 15 次）。
- list_tables 6/6 都在 ` {→ {"` 分叉，即开始写多余参数。
- median_prose 是 `_median→_mean`。
- median_nat 在 prefix 上 28–30 题全对，走关键 token 规则；stage04 种子 08 有 10 次 `_median→_sorted`。
- 探针 d1 平均 CE：fct 0.71–1.95，list_tables 0.97–4.84。v1 的整条平均 CE 只有 0.06–0.10，说明决定性 token 上的损失原来确实被稀释了。

### 6.2 检验 (a)：fct 探针下 target > 近邻 > 普通背景？

d1，实际进过计划的条目，余弦均值：

| 打分点·种子 | target | near_sort（top_n） | near_filter（filter_eq_count） | db_other | python / file | near_sort>背景 win | near_filter>背景 win |
|---|---|---|---|---|---|---|---|
| prefix 08 | 0.529 | −0.110 | 0.074 | 0.020 | −0.003 / 0.006 | 0.000 | 0.948 |
| prefix 09 | 0.669 | −0.037 | 0.082 | 0.051 | 0.014 / 0.021 | 0.057 | 0.939 |
| prefix 10 | 0.611 | −0.082 | 0.054 | 0.037 | 0.004 / 0.014 | 0.035 | 0.895 |
| stage04 08 | 0.437 | −0.064 | 0.075 | 0.019 | 0.004 / 0.014 | 0.007 | 0.920 |
| stage04 09 | 0.709 | −0.031 | 0.074 | 0.037 | 0.008 / 0.009 | 0.090 | 0.946 |
| stage04 10 | 0.412 | −0.116 | 0.026 | 0.023 | 0.001 / 0.003 | 0.009 | 0.801 |

- target 远高于其它所有组。win 对 near_sort 全部是 1.000，对 near_filter 是 0.991–1.000。
- `db.filter_eq_count` 高于普通背景（win 0.80–0.95），三种子、两个打分点方向一致，比 v1 更清楚。
- **`db.top_n` 在分叉 token 口径下余弦为负（−0.12 到 −0.03），低于普通背景（win 0.000–0.090）。** 这和 fct 的主要失败「漏掉 WHERE、直接 ORDER BY」对得上：`db.top_n` 正是「无 WHERE 的 ORDER BY + LIMIT」，它的梯度方向是在强化模型已经犯的错误。
- 因为 top_n 为负，「target > 近邻 > 背景」的组均值顺序在 d1 下只有 1/6 成立。`db.group_count` 仍是非 target 里最高的（0.135–0.301）。
- 合理性检查：list_tables 探针下 `db.list_tables` 条目余弦 0.805–0.827（三个变体），其它条目 −0.009 到 0.021，win 全部是 1.000。

### 6.3 检验 (b)：去掉 target 条数之后还有没有额外解释力？tf25 能否排在前面？

45 个臂×种子点，结果 = B1 留出半。偏 Spearman = rank(成绩) 和 rank(打分) 各自先对 rank(n_target) 回归，再求残差的相关。

| 打分 | prefix：sum | prefix：**偏 sum｜n_target** | prefix：偏 sum_nontarget｜n_target | stage04：sum | stage04：**偏 sum｜n_target** | stage04：偏 sum_nontarget｜n_target |
|---|---|---|---|---|---|---|
| n_target（朴素） | 0.919 | — | — | 0.919 | — | — |
| v1（整条平均 CE） | 0.877 | 0.151 | 0.116 | 0.886 | 0.245 | 0.139 |
| **v2 d1** | 0.880 | **0.357** | 0.269 | 0.905 | **0.515** | 0.410 |
| v2 d0 | 0.825 | 0.429 | 0.364 | 0.844 | 0.550 | 0.464 |
| v2 dall | 0.881 | 0.133 | 0.092 | 0.902 | 0.269 | 0.151 |
| v2 d1 点积 | 0.941 | 0.634 | 0.324 | 0.930 | 0.640 | 0.257 |

**(i) 额外解释力：有，但比较弱。** 去掉 target 条数后，d1 的偏 Spearman 在 prefix 是 0.357，在 stage04 是 0.515；v1 只有 0.151 和 0.245。非 target 部分的偏相关也由 v1 的 0.12–0.14 升到 0.27–0.41。这说明对齐决定性 token 后，打分里出现了超出「target 条数」的信息。要注意三点：45 个点并不独立（同一种子的臂共享 File/Python 条目）；点积版本的 0.63–0.64 会混入种子之间的梯度尺度差异；dall 回到 v1 的水平，说明有用的信息集中在分叉 token 附近。

**(ii) 在只含 1 条 target 的 12 个点上，排不出 tf25。** 1-target 子集里 sum 与成绩的 Spearman：prefix d1 0.434，stage04 d1 0.829。但「tf25 同时高于 target_other 和 target_dbbg」只有 1/3 个种子（种子 10），两个打分点都一样；点积版本是 0/3（prefix）和 1/3（stage04）。

- 种子 08（四臂都是 T-000，唯一干净的比较）：prefix 把 tf25 排第 3（dbbg 0.889 > other 0.621 > tf25 0.536），stage04 排第 2，排第 1 的都是 dbbg（实测 0.100）。
- 种子 09：tf25 两个打分点都排最后（实测最高，0.667）。
- 子集里的正相关主要来自 A 两臂与 dose_db1 之间的排序（例如种子 09 dose_db1 > dbbg > other，对应实测 0.267 > 0.233 > 0.200），不是来自 tf25。

### 6.4 单条 target 条目的价值：tf25 的优势是否来自 target 条目本身不同？

全部 11 条 `filter_cmp_top` 训练条目对 fct 探针的 d1 余弦（`tables_ZH.md` §4）：

- **条目之间差别不小。** 同一种子内的范围：prefix 0.316–0.694（08）、0.448–0.860（09）、0.514–0.705（10）；stage04 0.183–0.669、0.506–0.885、0.254–0.583。最高和最低之间差 0.2–0.5。
- **A 组用的 T-001 在每个种子、每个打分点、每个变体下都排第 2–3。** tf25 在种子 09 用的 T-005 排第 5–8；在种子 10 用的 T-008 排第 3–4。T-008 只在 stage04 种子 08 上排第 1，但种子 08 的 tf25 用的是 T-000，与此无关。
- 直接比较（d1）：
  - 种子 09：T-005 0.629 对 T-001 0.848（prefix），0.739 对 0.850（stage04）。
  - 种子 10：T-008 0.634 对 T-001 0.685（prefix），0.509 对 0.571（stage04）。
  - dall 和 v1 方向相同。
- **结论：按梯度打分，-005 和 -008 都不比 -001 更有价值，反而更低。** 「tf25 的优势来自 target 条目本身更好」这一解释得不到打分支持。不过打分本身也排不对 tf25（§6.3），所以这只能说「打分不支持」，不能证明条目身份无关。

### 6.5 只读 CPU 检查：target 条目的插入位置（v2 分析中发现的混杂因素）

v2 也解释不了 tf25，于是我查了现有训练日志里 target 条目落在哪个累积窗口（`scripts/p2_target_timing_check.py` → `v2/target_timing_ZH.md`）：

- **三个种子的 tf25，唯一一条 target 都在新样本第 143 位插入，之后还有 3–4 次 optimizer 更新（含它所在窗口那次）。dose_db1、target_other、target_dbbg 的 target 在三个种子里都在第 159 位，也就是最后一个复习位置，落在最后一个不完整的累积窗口，只赶上训练结束前的 1 次更新。** 总更新次数都是 23 次，累积 8 步。训练代码会把最后不足 8 步的窗口按实际条数放大后补一次更新。
- 按 AdamW 一阶动量（PagedAdamW8bit 默认 β1=0.9）粗算，一条梯度带进之后 n 次更新的系数约为 1−0.9ⁿ：n=1 时 0.10，n=3–4 时 0.27–0.34。也就是说，tf25 那条 target 的「有效剂量」可能是另外三臂的 2.7–3.4 倍。最后一个窗口的放大系数是 8/5 到 8/7，远不够补回这个差距。这只是粗略描述，忽略了二阶矩归一化。
- 在 42 个有训练日志的臂×种子点上（none 没有训练日志，不计）：
  - n_target 的 Spearman 0.918；
  - 「target 之后更新次数之和」0.943，去掉 n_target 后偏 Spearman 0.557；
  - 只含 1 条 target 的 12 个点上为 0.659，而且三个种子都把 tf25 排在两臂前面（3–4 次对 1 次）。
- 判断：**这是一个此前没有控制的混杂因素。tf25 与实验 A 两臂（以及 dose_db1）的差距，可能主要来自 target 插入得早晚，而不是近邻模式或 target 条目本身。** 它也提供了一个解释：为什么单条 target 在 A 组只有约 +0.1。目前只有相关证据，单变量对照还没做，先作为待检验假设，不进主结论。它同时影响剂量曲线的解读：dose_db2 的 target 在 151/159 位，tf50 的 6 条分布在 127–159 位。

### 6.6 检验 (c)：`py.median` 同说法 vs 另一说法

- median_nat 探针，d1：同说法 `target_median_natural` 余弦 0.300–0.598，`stats_median` 0.003–0.050，其它 Python 模式 −0.003 到 0.044。win 在 0.969–1.000，三种子、两个打分点、三个变体方向一致，比 v1（stats_median 0.10–0.36）区分得更开。
- median_prose 探针（5 题，分叉在 `_median→_mean`）：win 在 0.730–0.985，但余弦都在 −0.016 到 0.046，**信号仍然太弱，不作结论**。

### 6.7 新的 Go / No-go

**梯度打分：Go，作为同模式 / 同说法检索器，并且探针改为分叉 token 版（d1）作为默认；作为解释 tf25、或判断近邻价值的工具：No-go。不建议用它来设计近邻消融训练。**

- 与 v1 相比，d1 有实质改进。分叉点抓到的就是 B1 的真实错误（漏 WHERE、漏 ASC/LIMIT、多传参数、`_mean`）；去掉 target 条数后有了弱的额外解释力（偏 Spearman：prefix 0.357，stage04 0.515；v1 为 0.151 和 0.245）；还给出了一条可检验的机制预测：`db.top_n` 强化了漏 WHERE 的错误，方向为负。
- 它仍然排不出 tf25（1/3 个种子），也不支持「-005/-008 比 -001 好」。
- **tf25 差距最可能的来源，变成了 §6.5 的插入位置 / 后续更新次数。** 这是训练调度上的混杂因素，比近邻和条目身份都更直接，检验也最便宜：同一条 T-001、同样的背景，只把 target 从第 159 位挪到第 143 位，与 dose_db1 / target_other 做配对比较。每臂训练约 1 分钟，加上 nat v2 Database 单套 B1 评测，三种子合计不到 1 小时 GPU。按预注册规则要先写修订再开训，本轮没有启动。
- 这个混杂因素也意味着：以后凡是比较单条或少量 target 的效应，都要固定 target 的插入位置或之后的更新次数。

### 6.8 限制

- 打分点仍是复习前的静态状态，属于一阶近似。1-target 子集只有 12 个点，种子 09/10 的 tf25 同时改变了 target 条目和插入位置。
- 全对题的关键 token 规则会把参数值（例如 7 个数字）全部算进去，工具名 token 只占少数；median_nat 在 prefix 上大多走这条规则。
- §6.5 只有相关证据，β1 粗算忽略了 Adam 的二阶矩和学习率之外的因素。
