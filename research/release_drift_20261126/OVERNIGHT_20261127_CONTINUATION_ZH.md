# 过夜决定续记 · 2026-11-27（Asia/Shanghai）

本稿接在 [OVERNIGHT_20261127_ZH.md](OVERNIGHT_20261127_ZH.md) 之后，只登记已经合并进 main 的决定。没有新算法，没有新计分，没有新增案例，也没有为写本稿重新执行库。密封的 pandas、Pillow、SciPy 标签没有打开。已归档研究目录没有改写。11 月 30 日方法冻结清单没有勾选。

那份过夜决定由 PR #4 squash 合并为 `dc6d84d350b31eda175c9df8693a6d604fead20d`。PR #5 的 squash `34940aa3169c20dbcc3e102f43094c42e6c47f5c` 只在该文件末尾加了一段「补充分母 · 父文档谓词绑定」。本稿不改写那一段，也不重勾清单。写稿时 `origin/main` 的顶端是 `bd0d76e4a14e287cb77247222ff85b9dafe2b8d3`，即 PR #9 的 squash 合并。

下面各节的数字和决定都来自已经在 main 上的报告与回执。它们不替换 ISSRE 的 12 组，也不替换正式封存的四项，也不产生方法排名。

## 父文档谓词绑定：分母不足

证据是 PR #5。计分前的冻结提交是 `f0805b3742c2c5c6de728e49dd1d849cda16567b`。squash 合并进 main 的是 `34940aa3169c20dbcc3e102f43094c42e6c47f5c`。报告是 [documented_predicate_binding/REPORT_ZH.md](documented_predicate_binding/REPORT_ZH.md)。`decision` 为 `insufficient_denominator`，理由是 `fewer_than_6_included`。`ranking` 是 null。`run.py` 没有执行。

有界检索考察了 40 条合并的修复 PR，`stopped_because` 是 `40_examined`。机械纳入 4，排除 36。另有 48 条标题被预登记的过滤去掉，不占这 40 个名额。预登记的计分下限是至少 6 个独立纳入组。4 小于 6。

这 4 条含误连，不能当成 4 个可计分的独立组。httpx #2669 的父句带 can，是用途说明，不是无条件义务。marshmallow #2792 的强记号 `none` 对上的是注解里的 `-> None`，不是标题里的 `data_key`。arrow #1242 和回退 #1264 用的是同一句 `only_distance` 文档；冻结实现把引文按子串去对 PR 文本，`in` 会落进普通英文。回退和原修复按一次独立修复也只算一件事，而且记录到的差异并不是这句文档。报告写明：即便不把误连的句子剔掉，4 也小于 6。没有为了凑满 6 而放宽记号、加库或再开一页。

`sentence_grounded`、`bind`、`jdoctor_pattern` 和 `status_only` 都没有在这个样本上跑出可执行检查数或分离数。没有安装父版本或修复版本。这个空缺不能解释成抽取器失败，也不能解释成抽取器成功。

重启这一问需要另一份先冻结的检索：在考察上限之内已经有至少 6 个独立修复，每组都能从父树引用一句，而这句说的就是该组记录到的行为差。用短引文的子串或注解里的 `None` 去连无关 PR，不算这种证据。放宽连接器不算。

## 当前文档抽取：分母不足

证据是 PR #6。协议冻结提交是 `68580782313e84ffedd6a29572f8bd81366e3518`。squash 合并进 main 的是 `ed10b06d39114fe000680b4c1ab7b26d0115577c`。报告是 [documented_api_extraction/REPORT_ZH.md](documented_api_extraction/REPORT_ZH.md)。`decision` 为 `insufficient_denominator`，理由是 `fewer_than_8_or_fewer_than_3_libraries`。`ranking` 是 null。`results/summary.json` 的 `scored` 是 false，`counts` 是 null。

这不是放宽 PR #5。报告写明：那次父文档检索不重开，连接器不放宽，样本不重算。attrs 和 hypothesis 也没有补进那次旧检索。本轮只问另一件事：当前文档里已经有可检查谓词时，现有抽取器能不能抽出一条可执行检查。它不是静默漂移检测，不是抓修复。

冻结之后、任何句子被考察之前，`selection.py` 有一次只修下载目录的提交 `e67f8616cf6eb6a305de795197b240499dc6cebf`。第一次运行没有把发行包写到磁盘，考察数是 0，那份空日志没有保留。模式、上限和库池没有改。下面的 40 句是这次修复之后的筛选。案例提交，也是 `run.py` 写下决定时的提交，是 `d22f69ca568eeb79ade1170af68cf991170da86a`。

整份枚举共 880 句义务。冻结句式 `return_if`、`return_and_raise`、`raise_if` 都是 0。含糊 2 句，其余 878 句是 `none`。实际停在 40 句考察，纳入 0，排除 40，没轮到的义务句 840。`stopped_because` 是 `40_examined`。计分需要至少 8 条独立义务，并且至少来自 3 个库。这里一条都没有。没有安装被测库来计分，抽取器没有跑出分数。

这个空缺不能解释成抽取器失败或抽取器成功，也不能解释成这些库的文档里没有可检查句子。考察到的 40 句已经是义务句。它们只是没有同时给出冻结表里的合法输入和违约输入。

若要重启这一问，新证据得是另一份先冻结的筛选：在同样的考察上限之内，已经有至少 8 条独立义务、至少 3 个库，每条都能从钉死的源文件引用原句，并且合法输入和违约输入都由那一句决定。看完这 40 句再放宽句式或补进方法，不算。把历史修复重新检索一遍，也不算。

## 冻结前校准接线：不是正式结果

证据是 PR #7。协议冻结提交是 `e23a55dea61a697bb2ce4e0a12b77b4efb9ab5f3`。squash 合并进 main 的是 `ce1cd4401048f116598f69e0f3ee40445d65783f`。报告是 [freeze_prep_20261130/REPORT_ZH.md](freeze_prep_20261130/REPORT_ZH.md)。这是 `freeze_prep_20261130` 的校准回执，不是正式结果。试跑发生在冻结提交之后，解释器是 CPython 3.12.3。没有重新执行 XlsxWriter、Babel 或 slugify，没有读取密封结局。六个案例的 `signoff_ready` 全部为假。

能跑的是接线，不是冻结产物。三次额度在接线里拦住了第四次调用：每个案例是一次不计额度的共享首请求，然后探测、一次故意失败的校验、一次在线复位；第四次恢复没有进入分派函数。失败的校验占用了额度。处置只在协议小夹具上算过。点质量 `(1, 0, 0)`、`(0, 1, 0)`、`(0, 0, 1)` 的损失是 0、1、5。六个案例各调用了一次这对函数，输入都是这组小夹具，案例行没有进入函数。因此这些 0、1、5 是同一次算术核对，不是案例分数。三个库的适配器都没有接上。分派函数只返回存档载荷的类型名。

当时仍然缺少的冻结产物，报告逐条写下：没有两侧共用的资料包文件；没有可执行的静态序列；工具适配器没有接到 `ExtraCalls` 后面；没有哈希冻结辅助函数；没有 `contract_value`、`direct_delivery` 或 `transferred_verdict` 表达式表；没有登记正常替代值和字段间不变量；处置没有作用到案例行上；离线 Schema、离线备用和初态快照复位的另计次数还没有实现；Babel 周历年和三个 slugify 标识的存档返回不能按字段重放，时长的档案标量也不能。方向判别里的随机对照写的是 CPython 3.11。这次没有跑随机对照，也没有把解释器钉在 3.11。正式清单没有勾选。方法没有冻结。

## 缺口补记

证据是 PR #8。补记协议是 [freeze_prep_20261130/PROTOCOL_ADDENDUM_ZH.md](freeze_prep_20261130/PROTOCOL_ADDENDUM_ZH.md)，提交 `22f56d6568968b69ed152a4c43476bd433d40a2d`。试跑当时的 `HEAD` 是实现提交 `7702338b4f2b74a4967bc8701d05640335c4a1bb`。squash 合并进 main 的是 `1e60419470c9f34554be411f187d162ea1226f1f`。报告是 [freeze_prep_20261130/GAPS_FOLLOWUP_ZH.md](freeze_prep_20261130/GAPS_FOLLOWUP_ZH.md)。PR #7 的接线报告和 `results/calibration_receipt.json` 没有改写、没有覆盖。解释器仍是 CPython 3.12.3。`python3.11` 不在环境里。六个案例的 `signoff_ready` 仍全部为假。0、1、5 仍只来自协议里的三个点质量，`case_rows_used` 为假。现场返回没有和 expected 比较。

十个缺口在该回执里的状态是：

| 缺口 | 该回执中的状态 |
| --- | --- |
| 共同资料包 | 关闭。六个案例各一份文件，两臂都在里面，装载器给出摘要 |
| 静态序列 | 部分关闭。深度 3 已数完，`check_search_parity` 通过；没有结局质量，未选序列 |
| 适配器 | 部分关闭。三个发布库的 `before` 和 slugify 前两个 parent 进入了钉住版本；第三个是导入错误 |
| 哈希冻结辅助函数 | 关闭。回执有总摘要和四段输入；正式清单未勾选 |
| 契约表达式 | 关闭。六张表都是空规则表，`direct_delivery` 为不可用 |
| 正常替代值 | 部分关闭。列和时长用了各自公开 expected；没有跨字段不变量 |
| 处置作用到案例行 | 部分关闭。六行都是未定、交付当前；没有案例级预期损失 |
| 离线计数 | 关闭。Schema、备用、快照复位各有次数和耗时，且不在 `ExtraCalls` 里 |
| 字段寻址 | 部分关闭。slugify 的现成字典可以读；周历年字符串和时长标量没有被包裹 |
| CPython 3.11 | 仍然开放。针脚未设置，随机臂没有运行 |

静态序列没有使用开发侧的 `preplanned` `[2]`。报告写明：三个发布案例的这个值是开发探针下标，不是资料包候选的规范化请求标识；`dev_parallel.best_static` 最小化的也不是 `expected_task_loss`。因此 `development_preplanned_used` 为假。slugify 没有这个键。没有对任何序列调用 `expected_task_loss`，也没有选出序列。实际枚举条数是列 65641、时长 259、周历年 8421、每个 slugify 1885。这些是条数，不是分数。

适配器只证明 `before` 或 `parent` 被调用过，不是配对比较。现场版本是 XlsxWriter 3.3.0 与 1.3.7、Babel 2.16.0，以及 slugify 的两个 parent 提交。python-slugify-3 的 parent 返回 `AttributeError: module 'slugify' has no attribute 'slugify'`，与存档导入错误相同。没有安装另一个 python-slugify 来顶替。slugify 的 parent 声明依赖 `Unidecode>=0.04.16`。这次能导入的是 Unidecode 1.4.0。夹具没有钉住这个版本。回执把它记成当时能导入的依赖，并写明该版本不在夹具里。

契约表达式记为关闭，是因为六个案例的观察都不是「完整输出是一个整数」，每张表都是 `[]`。这不是抽出了契约。

## 另一臂校准

证据是 PR #9。补记协议是 [freeze_prep_20261130/PROTOCOL_AFTER_ARM_ZH.md](freeze_prep_20261130/PROTOCOL_AFTER_ARM_ZH.md)。回执和 PR #9 的提交列表把这份补记记为 `7b2e502e1074d53b95581e3e59abaf45097ef748`。试跑当时的 `HEAD` 是实现提交 `c8a0e2c0c382b43c0fb6d6301053315813379553`。squash 合并进 main 的是 `bd0d76e4a14e287cb77247222ff85b9dafe2b8d3`。报告是 [freeze_prep_20261130/AFTER_ARM_ZH.md](freeze_prep_20261130/AFTER_ARM_ZH.md)。PR #7 的接线报告和 PR #8 的缺口报告都没有改写，两份较早回执也没有覆盖。父进程仍是 CPython 3.12.3，没有把 3.12 当成 3.11。六个案例的 `signoff_ready` 仍全部为假。没有比较 before 与 after、parent 与 rev 来计分。

另一臂使用同一个三次额度。before 与 parent 沿用缺口回执，没有重跑。三个发布库的 after 进入了资料包版本，并且库自己报告的版本一致：XlsxWriter 3.3.1、XlsxWriter 1.3.8、Babel 2.17.0。首请求、探测和复位都完成，分别是字典、浮点和字符串。这些返回没有和 expected 比较。

三个 slugify 的 rev 已检出并分派，检出与资料包里的完整 rev 一致，但都不是签收返回。python-slugify-1 的 `0c9b8e069994f6ab76b4f4f5efd2d85cf795bdd8` 和 python-slugify-2 的 `a1543fe0ae019606bec660d6cf2e70a435ff29e4` 是 `ModuleNotFoundError: No module named 'unidecode'`。python-slugify-3 的 `07155c2001580b0ec70b40f24a475baef6238aac` 仍是 `AttributeError: module 'slugify' has no attribute 'slugify'`。没有改用另一个提交，也没有换成另一个 python-slugify。`signoff_quality_receipt` 全部为假。

Unidecode 仍然开放。六份资料包和协议允许名单里都没有精确钉扎。三个 rev 的检出声明仍是 `Unidecode>=0.04.16`，这是库声明里的范围，不是公开夹具的钉扎。本次没有安装任何 Unidecode，也没有把版本写进仓库。上一份回执里能导入的 1.4.0 仍然不是夹具命名的版本。

结局先验仍然不够用来选序列。允许名单里的 JSON 和六份资料包都没有顶层 `outcome_prior`。`expected` 仍是库输出，不是正确、暂缓、错误上的三元质量。开发结果里的行级 `outcome` 和 `loss` 没有抄进回执。`preplanned` `[2]` 仍未使用，`development_preplanned_used` 为假。因此没有对任何序列调用 `expected_task_loss`，`sequence_selected` 为假。枚举条数仍是列 65641、时长 259、周历年 8421、每个 slugify 1885。两臂设置相同，`check_search_parity` 通过。

案例行损失也没有。六行裁决都是未定，动作为交付当前，`expected_task_loss` 为 `null`，`evidence_sufficient` 为假，`formal_score` 为假，标签是 `calibration`。没有用现场返回是否等于 expected 来填损失。六行相同是因为规则相同，不是六个分数。

CPython 3.11 的针脚检查关闭了，正式随机臂没有运行。`uv python find 3.11` 给出的解释器在仓库外，该进程自报 CPython 3.11.18，`version_info` 为 `[3, 11, 18]`。它为六个案例分别构造了 `random.Random(20261126)`，没有抽取请求，没有调用三个库。`random_arm_comparison_ran` 为假，`formal_paired_comparison_started` 为假。解释器不在默认 `PATH` 上。`formal_checklist_ticked` 为假。

字段与不变量仍是部分关闭，而且这一项不能关闭。没有把周历年字符串或时长档案标量包进新结构。档案类型仍是周历年 `str`、时长 `float`，两处 `addressable` 为假。跨字段不变量表是空的。slugify 没有新的字段包裹。

## 仍然有效，且不得提前启动

[protocol.md](protocol.md) 的有效期仍是北京时间 2026-11-26 至 2026-12-10。正式静默漂移的方法冻结仍从 2026-11-30 开始，到 12 月 2 日；成对执行是 12 月 3 日至 7 日；揭盲是 12 月 8 日至 10 日。在这个窗口之前不开始成对主比较，也不把方法冻结清单勾成已经开始。勾选仍只属于冻结窗口里的动作。[OVERNIGHT_20261127_ZH.md](OVERNIGHT_20261127_ZH.md) 和上级 [protocol.md](protocol.md) 里的清单保持未勾选。

密封的 pandas、Pillow、SciPy 标签没有打开。正式四项的分母没有扩大。共享首问之后的三次额外调用额度没有扩大。已暂停的 ESWA 原型不重启。已经停止的线保持停止：主动验证、目录收窄、把 XlsxWriter 列隐藏再写成一条新结论，以及上面两份抽取研究。ISSRE 已冻结的样本、答卷和论文分母沿用各自协议。

上面这些后来的结果，包括校准里出现的 0、1、5 和现场返回，都不能替换 ISSRE 的 12 组或正式封存的四项。两份抽取研究的 `ranking` 都是 null。校准回执写明 `methods_ranked` 为假。没有方法排名。

## 冻结前仍然开放的缺口

下面这些缺口在 PR #9 的回执里仍然开放。现有回执没有用夹具里不存在的材料把它们说成已经关闭。以后也不要用发明出来的结局先验、Unidecode 精确钉扎，或新的字段结构去关闭它们。

- 结局先验，以及按预期任务损失选出的静态序列。公开夹具没有顶层 `outcome_prior`，`sequence_selected` 为假。开发侧的 `[2]` 不是这串序列。
- 案例行上的预期任务损失。六行的 `expected_task_loss` 为 `null`。点质量上的 0、1、5 不是案例行损失。
- Unidecode 的精确钉扎。夹具没有命名 1.4.0，范围声明 `Unidecode>=0.04.16` 也不是钉扎。
- slugify 另一臂的签收返回。三条 rev 都已分派，前两条缺 `unidecode`，第三条仍缺 `slugify` 属性。`signoff_quality_receipt` 为假。
- 周历年字符串和时长档案标量的字段寻址。两处 `addressable` 为假，也没有被包进新结构。
- 跨字段不变量。不变量表是空的。

共同资料包、校准用的哈希冻结辅助函数、离线计数，以及「空规则表」这一项契约登记，已经按上面的回执关闭。空规则表表示没有登记整数取值、序列长度或整数倍，`direct_delivery` 仍为不可用。CPython 3.11.18 只完成了仓库外的针脚检查。正式随机对照没有运行。这些关闭项都不勾选 11 月 30 日清单。
