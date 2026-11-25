# When Is a Tool Failure Detectable? An Empirical Study of Access, Budget, Observability, and Test Selection

**工具故障何时能够被检测？权限、预算、可观察性和测试选择的实证研究。** 独立开源项目队列，2026-11-24。

## 研究决定

继续准备 ISSRE RES。常规输入的检查在本批 12 个缺陷组上都通过；允许缺陷相关输入后，5 个组直接抛异常，7 个组正常返回错误结果。在这 7 个组里，读取预定的粗粒度业务字段仍会放行错误，检查更完整的语义才能发现。后一现象出现在三个未参与旧平台设计的项目中。该结论能够改变验证工程的处置优先级。概率型策略排名、真实服务上的全局不可达性、端到端 Agent 收益是另外的问题，本批没有测量。

## 筛选流程

先写入[前瞻性协议](ISSRE_INDEPENDENT_PROTOCOL_20261124.md)，后检索 GitHub；样本文件记录协议 SHA-256。四个项目与 XlsxWriter、Babel、日历、库存、SQLite 开发集分离。2022–2025 合并且标题匹配 fix 的查询分别命中 28、17、41、134 条；每项目取创建时间最新 10 条，共 40 条。四个项目轮流取样。第 26 条处理完即达到 12 组停止线。其余 14 条保留在样本框，未按失败或排除计。登记属本地冻结，没有第三方预注册时间戳。

| 项目 | 固定候选 | 已执行配对 PR | 范围外 | 达标后未尝试 | 独立分析组 |
|---|---:|---:|---:|---:|---:|
| humanize | 10 | 6 | 1 | 3 | 5 |
| PrettyTable | 10 | 4 | 3 | 3 | 4 |
| more-itertools | 10 | 2 | 4 | 4 | 2 |
| Rich | 10 | 1 | 5 | 4 | 1 |
| 合计 | 40 | 13 | 13 | 14 | 12 |

13 项已尝试的修复均满足“父提交普通对照正确、边界有偏差，修复提交两种输入均符合预定期望”。13 条范围外记录包括文档与示例、类型提示、CI 配置及超出有限显示任务范围的递归诊断。每条理由可查。humanize #240 和 #250 修复字节显示时相近分支，保守合并，以按顺序先遇到的 #250 代表。即使分开，结论的方向也相同：正常返回错误的修复从 7/12 变为 8/13。[筛查台账](../runs_independent_20261124/screening.csv) · [查询与 PR 元数据](../runs_independent_20261124/frame.json) · [精确版本](../runs_independent_20261124/commits.json)

## 版本确认与可观察差异

每项分别从合并提交和第一父提交导出库源码，在独立 Python 进程执行并核对导入路径。实验单位为历史修复，版本单位为提交。两个输入分别是常规对照及与上游材料有关的边界输入。判据与投影先于配对执行写入脚本并记录 SHA-256。成功复现不能归功于自动找到输入。共 13 × 2 × 2 = 52 次版本–输入执行，未将其视作 52 个独立故障。

| 项目与上游修复 | 父提交上边界输入的现象 | 修复后的语义 |
|---|---|---|
| [humanize #273](https://github.com/python-humanize/humanize/pull/273) | 法语数量显示 1.0 millions | 舍入到 1.0 时用单数 million |
| [humanize #254](https://github.com/python-humanize/humanize/pull/254) | 59.5 秒、精度为整数时显示 60 seconds | 单位进位为 1 minute |
| [humanize #250](https://github.com/python-humanize/humanize/pull/250) | 浮点 1 显示 1.0 Byte | 与整数 1 一致，显示 1 Byte |
| [humanize #218](https://github.com/python-humanize/humanize/pull/218) | 3,000,000 个字节用 int32 输入时显示 −1.3 MB | 正数 3.0 MB |
| [humanize #216](https://github.com/python-humanize/humanize/pull/216) | 葡语 2.0 bilhão，数值正确、词形错误 | 2.0 bilhões |
| [PrettyTable #378](https://github.com/prettytable/prettytable/pull/378) | 添加空行批次即 IndexError | 正常完成，表仍为空 |
| [PrettyTable #356](https://github.com/prettytable/prettytable/pull/356) | 行值 X、Y 完整，内部分隔线使用底角 └ | 内部交叉点为 ├ |
| [PrettyTable #355](https://github.com/prettytable/prettytable/pull/355) | 创建时指定已有字段排序即 ValueError | 成功创建，按指定字段输出 |
| [PrettyTable #345](https://github.com/prettytable/prettytable/pull/345) | 开启格式化并加入自动索引后，输出 HTML 抛 TypeError | 首格索引为 1 且居中 |
| [more-itertools #1088](https://github.com/more-itertools/more-itertools/pull/1088) | 对数量要求 −10 抛 ValueError | 无法恰好匹配负数个，返回 False |
| [more-itertools #1082](https://github.com/more-itertools/more-itertools/pull/1082) | 笛卡尔积索引使用单遍迭代器时抛 TypeError | 与元组输入一致，索引为 3 |
| [Rich #3718](https://github.com/Textualize/rich/pull/3718) | 标题文字仍为 title，蓝色面板的标题无背景色 | 标题背景继承 blue |

另有同组的 [humanize #240](https://github.com/python-humanize/humanize/pull/240)：输入 1.123456789 时，旧结果保留不应显示的字节小数。两个提交的所有实测响应、异常类型、字段和操作轨迹见[配对执行记录](../runs_independent_20261124/replay.json)。

## 一个总分掩盖的两种处置

在普通输入、完整语义检查下，两种测试都可能得零分。例如 more-itertools 在元组输入上返回正确的索引 3；Rich 在无底色的普通面板上返回正确标题。将元组和输入池换成一次性迭代器，父提交直接抛错，成功状态检查已经足够。给 Rich 面板设定背景色，仍然读取标题文字，两版都会得到 title；必须在同一次渲染的标题片段上还读取背景样式才能检出。只在无底色面板上检查全部样式，同样不会检出。

PrettyTable 的分隔线还给出了第二个维护团队的对应案例。打开单线边框并使用行分隔后，仅比较 X、Y 两个数据值，两版一致；在同一个返回文本中检查分隔符，旧版使用了表示底角的字符。对这两项，在其他条件相同的情况下，单独放开输入或单独升级观察器都不够。这种配对使“再增加边界输入”和“修改验收字段”有了不同的依据。

| 项目 | 缺陷组 | 边界输入，只读成功状态 | 边界输入，读预定粗字段 | 边界输入，检查完整语义 |
|---|---:|---:|---:|---:|
| humanize | 5 | 0 | 0 | 5 |
| PrettyTable | 4 | 3 | 3 | 4 |
| more-itertools | 2 | 2 | 2 | 2 |
| Rich | 1 | 0 | 0 | 1 |

粗字段按任务预定，包括数值、单位、行内容、标题文字；标量 API 只有返回值时，粗、细语义重合。对 #218，“单位是 MB”仅适用于关心单位类别的消费者，核对数值的消费者本来就能发现错误。这里测量的是选定输出投影会遗漏什么，不代表库用户普遍采用这些投影。每缺陷等权，升级观察器新增 7/12；每项目等权，项目内新增比例均值为 56.25%。逐一去掉一个项目，新增比例介于 2/7 和 6/8。样本量、标题筛选、项目内相关及停止规则都不支持总体发生率推断。

## 四维条件怎样计算

- **Access。** 有限菜单 P0 只有普通输入，P1 额外包含边界输入，两菜单嵌套。本轮模拟允许构造的测试输入，不等同真实线上账户权限。P0 的零命中与普通输入是对照的构造有关。
- **Budget。** 每个测试独立复位，记录公开调用、设置和最终渲染/读取。locale 激活、对象构造若出现在路径上照计。正常返回在命名观察点计证据，异常在实际抛出步骤计。在 P1、完整语义、可选中见证时，每测试允许 1/2/3/4/5 个记录步骤，分别可见 **6/9/9/10/12** 个缺陷组。这些是冻结见证路径的可检出数；真实 API 上其他捷径、复用已建对象或更早的观察点未穷尽。这一批没有证明 12 项的全局最短调用数。
- **Observation。** 同一执行结果离线读取成功状态、预定粗字段、预定细字段。路径发生异常时各投影都能察觉异常。没有额外业务字段的布尔和整数接口不贡献“粗到细”的独立证据。
- **Selection。** 固定 P1、足够原生调用、同一观察器和仅选 1 个测试的外层预算。完整语义下普通输入优先为 0、边界输入优先为 12、均匀选一期望为 6；状态观察下依次为 0、5、2.5。每组恰好一个普通对照和一个已知见证，此差值是条件计算，不是新策略胜过经典方法的跑分。矩阵共有 2 × 5 × 3 × 4 = 120 格，每格保留逐缺陷记录。[完整配对矩阵](../runs_independent_20261124/factorial.json) · [项目分层汇总](../runs_independent_20261124/summary.json)

预算上限 1 至 5 的逐点表是对实测路径的描述性汇总；输入、动作及观察判据在执行前已编码。完整性核验使用本地哈希，不是独立第三方盲审。

## 第四周决策口径

独立于平台设计的真实缺陷已经支持“相同总分对应不同纠正措施”，而且 Rich 和 PrettyTable 的结果说明可观察性不只是测试是否抛错。现有证据支持在 ISSRE RES 方向继续写作，论文中应明确分开上游辅助见证的**归因有效性**与测试生成器的**未知故障发现率**。两输入菜单不能证明任一自动策略在未知缺陷上的优势。若要把策略可靠性排序作为主要主张，最有价值的补充是对后续保留缺陷先从公开 API 文档独立生成任务和观察器，再揭示上游修复说明；保留缺陷应避开已预读过差异的条目。否则只主张可检测性测量。ESWA 双门槛未在本轮测试。

## 复现方式

目录保留了固定检索快照、40 组上游提交标识、筛选理由及输入脚本哈希。首次准备时，在 Python 3.11 环境提供 numpy 2.4.4；在系统临时目录的 issre20261124-deps 子目录安装 wcwidth 0.2.13、Babel 2.17.0。其余呈现依赖使用兼容的 Rich 依赖环境。使用 Git 和网络获取上述四个上游仓库；程序优先复用系统临时目录中的对应裸仓库。两个人类可读语言目录从锁定提交的 PO 文件编译；需要构建时生成的版本模块仅填入提交标识。配对执行每次启动隔离解释器并核对模块来自该次导出的源码路径。

```powershell
$deps = Join-Path $env:TEMP 'issre20261124-deps'
py -3.11 -m pip install numpy==2.4.4 Pygments==2.21.0 markdown-it-py==4.2.0 mdurl==0.1.2 typing_extensions==4.15.0
py -3.11 -m pip install --target $deps wcwidth==0.2.13 Babel==2.17.0
py -3.11 research/issre_independent_replay.py
py -3.11 research/issre_independent_analysis.py
```

以上命令在 fac_tinyagent 根目录执行。冻结的候选与提交清单随包提供，无需重新检索。[复现程序](issre_independent_replay.py) · [预定输入及判据](issre_independent_cases.py) · [四维统计程序](issre_independent_analysis.py)
