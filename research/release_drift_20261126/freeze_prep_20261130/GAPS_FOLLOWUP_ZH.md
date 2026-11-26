# 静默漂移冻结前缺口补记

**2026 年 11 月 26 日。** 这是校准，不是正式结果。补记协议是 [PROTOCOL_ADDENDUM_ZH.md](PROTOCOL_ADDENDUM_ZH.md)，提交 `22f56d6568968b69ed152a4c43476bd433d40a2d`。试跑发生在这次提交之后，当时工作区干净，`HEAD` 是实现提交 `7702338b4f2b74a4967bc8701d05640335c4a1bb`。解释器是 CPython 3.12.3。`python3.11` 不在环境里，方向判别的 3.11 针脚记为未设置。没有把 3.12 当成 3.11，没有跑随机臂。

[REPORT_ZH.md](REPORT_ZH.md) 仍是 PR #7 的较早回执，这次没有改写它，也没有覆盖 `results/calibration_receipt.json`。过夜决定和上级 `protocol.md` 的 11 月 30 日清单没有勾选。正式方法没有冻结。正式四项配对比较没有开始。六个案例的 `signoff_ready` 全部为假。

0、1、5 仍只来自协议里的三个点质量，`case_rows_used` 为假。它们不能替换正式分母，也不能用来在看见密封结局之后修改已经预注册的正式方法。下面的现场返回只证明适配器被调用过，没有和 expected 比较，也不给方法排名。

哈希冻结辅助函数的总摘要是 `2822eef76c4927b7da6d0a8fa756a8ab5bc75cc39fa36f38972697a338aa1a91`。四段输入是可部署参数 `cb8c0b8ba0c15a91824886989c58a620940830fb61343576146ccc2383a39693`、处置规则 `a2fd8314da39c4eb8b5a66ac9e748e388768a6fff77816806187854a03d42aef`、合理预期 `a24e0c0e85270d6059b6ada8dcff5f4bf1deb6727a976b5249786ea021606f8c`、任务注册表 `4443179031b5a7985586ef2b30feb61c28ddda4cdaa9c08510012bf86c730110`。允许名单上那些文件的 SHA-256 仍只标识校准输入，不冒充这次冻结。

## 十个缺口

| 缺口 | 状态 | 证据 |
| --- | --- | --- |
| 1 共同资料包 | 关闭 | 六个案例各一份文件，两臂都在里面，装载器给出摘要 |
| 2 静态序列 | 部分关闭 | 深度 3 的序列已数完，`check_search_parity` 通过；没有结局质量，未选序列 |
| 3 适配器 | 部分关闭 | 三个发布库的 before 臂和 slugify 前两个 parent 进入了钉住版本；第三个是导入错误 |
| 4 哈希冻结辅助函数 | 关闭 | 回执有总摘要和四段输入；正式清单未勾选 |
| 5 契约表达式 | 关闭 | 六张表都是空规则表 |
| 6 正常替代值 | 部分关闭 | 列和时长用了各自公开 expected；没有跨字段不变量 |
| 7 处置作用到案例行 | 部分关闭 | 六行都是未定、交付当前；没有案例级预期损失 |
| 8 离线计数 | 关闭 | Schema、备用、快照复位各有次数和耗时，且不在 `ExtraCalls` 里 |
| 9 字段寻址 | 部分关闭 | slugify 的现成字典可以读；周历年字符串和时长标量没有被包裹 |
| 10 CPython 3.11 | 仍然开放 | 针脚未设置，随机臂没有运行 |

### 1. 共同资料包：关闭

`packs/` 里每个案例一份 JSON。发布案例的两臂是 `before` 与 `after` 的版本、文件名、URL 和轮子摘要。slugify 的两臂是 `parent` 与 `rev` 提交。同一份文件里还有公开输入、公开 expected，以及允许的离线判据。判据列表六个都是空的。资料包没有写入 `actual`、`detected_inputs` 或 `revealed_slugify.json` 的值。校准输入没有被写成正式回归集。

| 案例 | 摘要 | 输入条数 | 两臂 |
| --- | --- | --- | --- |
| xlsx-column | `92525f78b05000ae35a9ebad5b6533f34cc4273964e9ade9466df267edb3bcdc` | 40 | 3.3.0 / 3.3.1 |
| xlsx-duration | `b710c6676b132bcb61a665481f73aa1443e8e2938d9e4df42e5df567e4800920` | 6 | 1.3.7 / 1.3.8 |
| babel-week | `07c84df0db1f5b93726c63bf3aad35cd5dbaf4841862edb7ddf9f526373046c3` | 20 | 2.16.0 / 2.17.0 |
| python-slugify-1 | `655512b8181b42054514572905ffb77e6bf111069daf73126c20c136199d3356` | 12 | parent `eeabcc29eb67dd9ab34c693db44f9ece312e7a2c` / rev `0c9b8e069994f6ab76b4f4f5efd2d85cf795bdd8` |
| python-slugify-2 | `6b3bfea79f086aaae956c01702374f9bf20c7dd39e28e2f72a6a1793454917f4` | 12 | parent `4091b444746032847ccce0d5c6a0cd5b1bb73d81` / rev `a1543fe0ae019606bec660d6cf2e70a435ff29e4` |
| python-slugify-3 | `76282c22c6d3bb794d88339551c51032c78567f923f82c1561c47328381d22c8` | 12 | parent `3d75734751b36ae14feab0d84f5d670f1d6225e3` / rev `07155c2001580b0ec70b40f24a475baef6238aac` |

用户要求文本、旧 Schema 文档、升级前公开文档和共用备用动作仍然没有单独的正式文本。readme 只留在出处里，没有升格为升级前文档。

### 2. 静态序列：部分关闭

三个发布案例的 `static_info.preplanned` 值都是 `[2]`。它是开发探针下标，不是资料包候选的规范化请求标识。`dev_parallel.best_static` 最小化的是剩余解释数、调用数和探针下标序列，不是 `expected_task_loss`，平局也不按规范化请求标识。因此 `development_preplanned_used` 为假，没有把 `[2]` 当成正式静态序列。slugify 没有这个键。

校准生成器的候选是资料包里的公开输入。合法序列是长度 0 到 3、允许重复的请求组。转移只记录调用预算，不更新结局质量。终端评分标识指向已有的 `expected_task_loss`，但公开夹具没有正确、暂缓、错误上的先验质量，所以没有对任何序列调用它，也没有选出序列。两臂使用同一组设置，`check_search_parity` 通过。实际枚举条数是：列 65641，时长 259，周历年 8421，每个 slugify 1885。签收就绪仍为假。

### 3. 适配器：部分关闭

现场调用只打资料包的 `before` 或 slugify 的 `parent`，没有执行另一臂，因此不是配对比较。轮子按资料包里的 SHA-256 核对。每次脚本都是共享首请求、探测、一次失败的未登记校验、在线复位；恢复在进入适配器之前被拦截，信息是 `three additional calls already attempted`。失败的校验占用一次。

| 案例 | 现场版本 | 首请求 | 探测 | 复位 |
| --- | --- | --- | --- | --- |
| xlsx-column | XlsxWriter 3.3.0 | 完成，字典 | 完成 | 完成 |
| xlsx-duration | XlsxWriter 1.3.7 | 完成，浮点 | 完成 | 完成 |
| babel-week | Babel 2.16.0 | 完成，字符串 | 完成 | 完成 |
| python-slugify-1 | parent `eeabcc29…` | 完成，字符串 | 完成 | 完成 |
| python-slugify-2 | parent `4091b444…` | 完成，字符串 | 完成 | 完成 |
| python-slugify-3 | parent `3d757347…` | `AttributeError: module 'slugify' has no attribute 'slugify'` | 同样失败并占一次 | 同样失败并占一次 |

slugify 的 parent 提交声明依赖 `Unidecode>=0.04.16`。这次能导入的是 Unidecode 1.4.0，夹具没有钉住这个版本。没有安装另一个 python-slugify 来顶替。python-slugify-3 的失败与存档导入错误相同，探测和复位都占用了额度。

### 4. 哈希冻结辅助函数：关闭

见文首的总摘要和四段摘要。这只覆盖本次校准登记，不勾选正式清单。

### 5. 契约表达式：关闭

六个案例的观察都不是“完整输出是一个整数”。列是字典，时长档案是浮点且 expected 里有 59.5，周历年和 slug 是字符串。因此没有登记整数取值、序列长度或整数倍。每张表都是 `[]`，回执写明空规则表。`direct_delivery` 为不可用。没有调用 `transferred_verdict`。

### 6. 正常替代值：部分关闭

列的第一条捕获和该输入的公开 expected 都是 `visible: true`、`cell_text: ""`。时长第一条捕获是 `[1.0, "[h]:mm"]`，正常数值是该输入 expected 的浮点形式，格式字面量是公开调用里的 `[h]:mm`。两处 `replay_group` 的结果都是没有字段变化。公开夹具没有要求这些字段联动，不变量表为空。周历年的 expected 是字符串，slugify 的 expected 也是字符串，而记录是交付字典或导入错误，没有字段级正常值。没有使用占位常量。

### 7. 处置：部分关闭

空规则表不能判定义务，六行裁决都是未定，没有已验证替代，`disposition` 给出交付当前。没有编造结局质量，所以没有对案例行调用 `expected_task_loss`。六行相同是因为规则相同，不是六个分数。存档实际值没有被翻译成违约或满足。

### 8. 离线计数：关闭

每个案例都有离线备用、离线 Schema、初态快照复位，并记下了纳秒耗时。这三类不在 `ExtraCalls` 的事件里。在线复位仍走三次额度。`freeze_guards.py` 没有修改。

### 9. 字段寻址：部分关闭

slugify-1 和 slugify-2 的第一条交付字典可以读现成的 `method`、`v`、`deliver`、`calls`、`ns`。slugify-3 的 `import_error` 字段可以读，内容仍是没有 `slugify` 属性的 `AttributeError`。这些都不是新包出来的结构。周历年返回仍是字符串，时长档案 `actual` 的类型仍是浮点。两处都不可寻址，也没有被包进字典或列表。时长重放用的仍是开发捕获的二元列表，没有把列表回写成档案标量。

### 10. CPython 3.11：仍然开放

`shutil.which("python3.11")` 为空。针脚是 `unset`，`random_arm_ran` 为假。这次没有安装 3.11。3.12.3 不满足方向判别里的随机对照针脚。

## 仍然没有做的事

- 没有选出预期任务损失最小的静态序列，因为没有登记结局质量。
- 没有跨字段不变量，周历年和 slugify 也没有正常替代值。
- 案例行没有预期任务损失。
- 另一臂（after / rev）没有现场执行。
- Unidecode 1.4.0 不是夹具钉住的版本。
- 11 月 30 日清单没有勾选，方法没有冻结，正式配对比较没有开始。

## 重跑

单元测试不读取公开语料：

```
python3 research/release_drift_20261126/freeze_prep_20261130/test_followup.py
python3 research/release_drift_20261126/freeze_prep_20261130/test_harness.py
python3 research/release_drift_20261126/test_freeze_guards.py
```

校准试跑要求补记协议已经提交，且工作区干净：

```
python3 research/release_drift_20261126/freeze_prep_20261130/run_followup.py
```

输出是 [results/gaps_followup_receipt.json](results/gaps_followup_receipt.json) 和 [results/gaps_followup_log.txt](results/gaps_followup_log.txt)。
