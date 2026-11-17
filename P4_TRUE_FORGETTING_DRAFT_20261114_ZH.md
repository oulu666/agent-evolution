# P4 草案：真遗忘模式上的复习时机（早插 vs 晚插）

状态：**草案，未构建、未启动。** 写于 2026-11-14 13:50 北京时间。依据：已有逐题结果盘点（`scripts/p3_final_error_and_forgetting.py` → `runs_ext_p3_count_timing/analysis/p3_final_error_forgetting.json` 的 `forgetting_rows`、`pool_inventory`），以及 `runs_ext_p1_b1/analysis/true_forgetting_tables_ZH.md`。

## 1. 两个真遗忘模式的现状

| 模式 | 测试 | 什么时候掉 | 掉成什么样 | 是否三种子都掉 |
|---|---|---|---|---|
| `db.list_tables` | p2_database 6 题（**只有 1 个题面**，重复 6 次，结果只有全对或全错） | stage_02 后 6/6，**stage_03（学 Python）就掉到 0/6**，T1 none 仍是 0/6 | 工具对、final 对，参数多加了 `{"database": "read-only"}`（应为 `{}`） | 是 |
| `py.median`（同模板） | natv2_python 30 题（`paired_median_natural`） | stage_03 29 / 28 / 30，**到 Calendar 阶段才掉**：none 14 / 30 / 24 | 种子 08 改调不存在的 `stats_sorted`；种子 10 参数错 | 只有 08、10 掉，09 没掉 |
| `py.median`（另一种说法） | p2_python 5 题（「middle value」） | stage_03 5/5 → none 2 / 0 / 3 | 把 `stats_median` 换成 `stats_mean` | 是，但每点只有 5 题，种子 09 始终拉不回 |

两者的性质不同。`db.list_tables` 在复习开始前就已经掉光，复习是「再学会」；同模板 `py.median` 是在 Calendar 训练期间逐渐掉的，复习是「防掉 / 重新激活」。

## 2. 已有复习臂里的恢复情况，以及与插入位置的关系

### 2.1 `db.list_tables`：要累计约 10 次后续更新

统计 66 个 Calendar 阶段分支 checkpoint（含 none 与 Calendar 对照）。其中 B1 51 个：P1 12 个臂 × 3 种子、时机轮 6 个、P3 9 个；dose_db2/3/4 没有 p2_database 的 B1 结果，不计入。另有 B32 15 个：b05 三格、b20_tf00、b20_tf25，只有历史 B32，单列。每点的 Σafter = 复习里所有 `db_list_tables` 条目之后更新次数之和。

| 复习里有没有 list_tables 条目 | Σafter | B1：点数 / 恢复到 6/6 | B32：点数 / 恢复 |
|---|---|---|---|
| 没有 | 0 | 31 / **0** | 2 / **0** |
| 有 | 1–6 | 0 / — | 2 / 0（[4]、[1]） |
| 有 | 7–9 | 4 / 1（[7]✘、[9]✘、[9]✔、[7,1]✘） | 5 / 2 |
| 有 | **≥10** | **16 / 16** | **6 / 6** |

- **没有该模式经验就完全不恢复**，33 个点（B1 31 + B32 2）无一例外，包括把 filter_top 拉到 1.0 的 dose_db6。
- **Σafter≥10 时全部恢复**（22/22），7–9 时 3/9，≤6 时 0/2。单条要约 12–13 次后续更新（插在 87 段）才稳定；单条 7–9 次多数不够。和 filter_top 的「每条约 5 次就饱和」不一样。
- **现成的一个单变量时机对照（种子 08，B1）**：dose_db1 的复习里有 2 条 list_tables，分别在 119 段和 127 段（after 7、6），能恢复（6/6）。P3 的 pos127 臂把 filter target 换进 127 段时，**恰好把 127 段那条 list_tables 换到了 159 段（after 6→1）**，结果 **6/6 → 0/6**。同一种子的 pos95、pos143 臂没有动这条，都保持 6/6。条目集合和 token 完全不变，只差这一条的位置。这是目前「真遗忘也受时机影响」最干净的证据，但只有 1 个种子、1 个题面。
- 种子 10 的 pos143 臂把一条 list_tables 从 143 段（after 3）挪到 159 段（after 1），因为另外两条已经在 87 和 103 段（12、10），仍然恢复。这与「累计约 10 次」一致。

### 2.2 同模板 `py.median`（natv2）：一次就够，时机不起作用

只看出现了遗忘的种子 08、10（none 分别为 14/30、24/30）：

- **复习里至少有 1 条同模板 `target_median_natural` 的 checkpoint，全部在 26–30/30**，包括这条唯一插在最后一段（after=1）的 dose_db0/1、pos127/95/143、db4_late（种子 08，28/30）。
- 只有另一种说法 `stats_median` 的 checkpoint 恢复不了，甚至更差：tf00 种子 08 有 1 条 stats_median 插在 95 段（after 11），结果 7/30，比 none 的 14/30 还低。e3b2 两臂、target_other_pos143 为 20–26/30。
- 在现有点里看不到「早插更好」：同模板经验的 after 从 1 到 7，结果都在 26–30/30，只有 1 条、after=1 的点也是 28–30/30。这更像「重新激活」，一次接触就够，而且越晚越接近评测。

### 2.3 p2_python「middle value」5 题

种子 08、10 有复习的臂多数比 none 高 1–2 题，种子 09 基本拉不回。复习池里两种模板都不是「middle value」说法。每点 5 题，不作为 P4 的主指标。

## 3. 可用经验池（`data_ext_e4/pool/`）

| 模式 | 池中条数 | 来源阶段数据 | 模板 / 示例 | 与测试的关系 |
|---|---|---|---|---|
| `db_list_tables` | **11**（000–010） | **stage_02 Database 训练集**（11/11 都能在 `data_phase2/database/train.jsonl` 里按 id 找到） | 「List every table name in the database. Return a JSON list.」→ `db_list_tables {}` | 措辞与测试「What tables are available in the read-only database?」不同，但同工具、同参数 |
| `stats_median` | **14**（000–013） | **stage_03 Python 训练集**（14/14 在 `data_phase2/python/train.jsonl`） | 「Compute the median of the numbers [...]」 | 另一种说法，单靠它不恢复 |
| `target_median_natural` | **14**（014–027） | **不在 phase2 阶段数据里**，是 E4 构造的同模板经验 | 「The observations are … what is the value in the middle position?」 | 与 natv2_python 测试同模板 |

条数足够：P4 每臂最多用 2 条 list_tables、1 条 target_median_natural，三种子可以各自从池里取不同的条目。

## 4. P4 设计草案

**问题**：在固定复习预算下，同一条真遗忘经验早插还是晚插，对恢复有没有影响？对「再学会」型（list_tables）和「重新激活」型（同模板 median）是否方向相反？

**统一做法**（沿用 P3 的工具链和约束）
- 前缀：A_seed* 的 Calendar step-80 前缀（`runs_ext_p3_count_timing/prefixes`，已有）。23 个优化器步，复习约 7494 token。
- 基础计划：同种子的 dose_db4 计划（22 槽；三种子里都没有 list_tables 条目；4 条 filter target 固定不动，filter_top 顺便作为副作用指标）。
- 改动只有两处：
  1. 换入 1 条 `db_list_tables`（272 token），替换 1 条 token 最接近的 Database 背景条目（如 db_count，282 token）。预算差在 1% 以内。
  2. 只保留 1 条 `target_median_natural`，放在与 list_tables 相同的段；基础计划里多余的同模板条目换成 Python 背景条目（stats_mean / stats_std），token 匹配。`stats_median` 条目不动，同种子各臂相同。
- 位置与 after（按 `saturation_fit_ZH.md` §4 的槽位映射，三种子相同）：早 = 95 段（after 11），中 = 127 段（6），晚 = 159 段（1）。

**臂（每臂 3 个种子 08 / 09 / 10）**

| 臂 | list_tables | target_median_natural | 目的 |
|---|---|---|---|
| P4_early | 1 条 @95（a=11） | 1 条 @95 | 早插 |
| P4_mid | 1 条 @127（a=6） | 1 条 @127 | 中间 |
| P4_late | 1 条 @159（a=1） | 1 条 @159 | 晚插 |
| P4_LT2mid（可选） | 2 条 @127（a=6,6，Σ12） | 1 条 @127 | 真遗忘上「条数 vs 暴露」：Σ12 的两条对 Σ11 的一条 |

不设无复习对照：33 个没有 list_tables 经验的已有 checkpoint 全是 0/6；同模板 median 在无同模板经验时的遗忘水平，已有 none / ctrl / e3b2 臂给出。

**评测（B1，只评与问题相关的套件）**
- `p2_database`（含 list_tables 6 题，约 1.5 分钟）
- `natv2_python`（同模板 median 30 题，约 2.2 分钟）
- `natv2_database`（filter_top 副作用，约 2.1 分钟）
- `v3fix`（Calendar 新任务，约 1.3 分钟）
- 建议新增一份 list_tables 改写探针：约 24 个不同题面，只评测，新文件放 `data_ext_p4_probe/`，不碰冻结测试集，约 1 分钟。原因是现有测试只有 1 个题面，每个 checkpoint 实际上只有 1 个有效样本；有了探针，早 / 中 / 晚才能比较恢复程度，而不只是 0/6 和 6/6。

**预计 GPU 时长**：训练约 1 分钟 + 评测约 8 分钟，每个分支约 9–10 分钟。3 臂 × 3 种子 = 9 个分支，**约 1.5 小时**；加上 P4_LT2mid 共 12 个分支，**约 2 小时**。一次只跑一个 GPU 任务，沿用 P3 的 preflight 和 watchdog（不在游戏、功耗上限 ≥60W、没有其它 GPU 进程）。

**预注册预测**（来自 §2 的已有数据）
- list_tables：P4_early（Σ11）三种子都恢复；P4_late（Σ1）三种子都不恢复；P4_mid（Σ6）至多 1 个种子恢复；P4_LT2mid（Σ12）至少 2 个种子恢复。改写探针上的正确率按早 > 中 > 晚排列。
- 同模板 median（只看种子 08、10）：三臂都在 26/30 以上；如果有差别，应当是晚 ≥ 早（重新激活型，越晚越接近评测）。种子 09 没有遗忘，不用于判断。
- 判读：如果 list_tables 是早 > 晚，而 median 是晚 ≥ 早，论文就可以写「复习时机要按遗忘类型定：已经忘掉的要早插、累计足够的更新；正在被冲淡的，晚插一次就够」。这是 EAAR 调度规则的直接依据。如果两者都是早 > 晚，「早」就是一条更普遍的规则。

**不做**：不加 sham 对照，不加更多种子，不换模型规模。
