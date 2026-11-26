# 2026-11-26 · 父文档已经写明谓词时，抽取器能否把它绑成可执行检查

开发研究，执行前冻结。本文件、`sentence_grounded.py`、`screening.py`、`run.py` 与 `test_documented_predicate.py` 在任何纳入或排除决定、以及任何分数之前提交。`screening.py` 若发现协议、`sentence_grounded.py` 或 `screening.py` 有未提交改动，拒绝检索。`run.py` 若发现协议、`sentence_grounded.py`、`run.py`、`cases.json` 或 `docs/` 有未提交改动，拒绝计分。

这不是 ISSRE 那 12 组契约绑定的重做，也不是那 7 组目录缺口分析的重算。那一轮 `bind` 和 `jdoctor_pattern` 是 0/12 可执行检查（冻结 `22a843467bfdc9d7b9663c0582f05f37cecd3a77`，PR #2 `62722cff`）。随后的目录缺口分析（冻结 `f40de3285593d246fa03e969826e6375c654d426`，PR #3 `6c0b769de`）停止，理由是：状态和粗字段看不见的 7 组里，父文档没有把记录到的修复值写成可检查谓词。那两份结果分不清“文档没写”和“写了但抽不出来”。本轮只问后一件事。

本分母是补充样本。它不能替换 ISSRE 的 12 组，也不能替换正式封存的四项。正式四项的分母、CPU 与每任务三次额外调用额度都不扩大。不把开发侧的成功次数写成正式结果。不重开 `repair_gate`、`boundary_gap`、`contract_binding` 或 `catalog_gap_analysis` 的已归档分数；那些目录只读，允许按原文件导入。不打开含 `sealed` 的帧、`environment_receipts`、pandas、Pillow 或 SciPy。不把 XlsxWriter 列隐藏再写成一条新结论。不重启已暂停的 ESWA 原型。不开始正式成对主比较，不提前揭盲，也不把 11 月 30 日方法冻结清单勾成已经开始。方法冻结窗口仍是 2026-11-30 至 12-02，成对执行 12-03 至 12-07，揭盲 12-08 至 12-10。损失权重 0/1/5 本轮不使用。

## 问题与假设

父提交上的文档已经用一句话写下可检查义务，而这句义务说的就是已记录的父版本与修复版本行为差。自动抽取器能否只凭这句文档和第一次返回值或第一次异常，得到一条可执行检查，并在父版本失败、修复版本成立的方向上把两侧分开。

假设：若句子无条件地给出具体值、异常类型或比较，`sentence_grounded` 能在不读取修复侧输出的前提下把该句绑上，并相对 `status_only` 在两侧都成功返回、但返回值不同的组上多出分离。若义务带条件，而检查器又看不见实参，则自动抽取仍应失败；这种失败记在抽取，不记成文档缺失。`jdoctor_pattern` 与 `bind` 保持契约绑定研究里的原样，用来对照这条新机制有没有超出它们。

相对强基线的增益，指的是同一组上 `sentence_grounded` 分离而 `status_only` 不分离，并且该分离也不是 `jdoctor_pattern` 或 `bind` 已经给出的同一条分离。停止条件写在文末的决定规则里。负结果保留。

## 纳入

一条候选必须同时满足下面六条，才进入分母。

1. 公开的历史修复。父版本和修复版本都有可安装的提交。
2. 父提交上的文档（该符号的 docstring，或同一父树里的官方文档文件）至少有一句可检查义务：具体返回值或输出值、异常类型或异常条件、比较、范围，或契约绑定研究里 `holds` 已经能求值的质量词（true、false、null、none、zero、positive、strictly positive、negative、strictly negative、nonnegative、non-negative、nonpositive、non-positive）。空（empty）在冻结的 `_quality` 里不产生翻译，不算。
3. 记录到的父版本与修复版本行为差说的是这一条义务，而不是同一文档里另一件事。
4. 与已有 12 组独立。永久排除 humanize #273、#254、#250、#218、#216，以及作为 #250 重复的 #240；PrettyTable #378、#356、#355、#345；more-itertools #1088、#1082；Rich #3718。attrs #1427 与 #1428 也排除。
5. 一次独立修复是一组。同一修复的多个输入不另计组。
6. 两侧都能用一条确定的公开输入运行。命令、提交和版本要记下来。输入可以来自议题或该 PR 新增测试的准备部分；测试里的断言不进入抽取器，也不用来选择人写检查。

每条纳入都要能从父树引用原句。引用是父提交文件经 AST 取出的 docstring，或父提交文档节的原文，而不是记忆，也不是只出现在修复 PR 说明里的句子。空白折叠后，原句必须是缓存文档的子串。

## 排除

封存的正式样本；pandas、Pillow、SciPy；把已经关闭的 XlsxWriter 列隐藏再当作新结论；谓词只出现在修复 PR 或事后更新日志里；父树里引不出原句；父句在修复提交的同一符号文档里已经不在（`parent_sentence_absent_from_fix`，文档被改写成另一条义务，或父文本写的是缺陷形式）；一个 PR 里有多条对得上的义务却分不清该用哪条（`ambiguous_obligation`）；只有类型说明、没有具体值、异常、比较或质量词；标题已经表明是依赖升级、变更日志、错别字或空白修改。

## 有界检索

库池按这个顺序，到此为止，检索开始后不加库：click、requests、httpx、pydantic、pytest、Jinja2、flask、werkzeug、marshmallow、jsonschema、python-dateutil、arrow、attrs、rich、hypothesis、lxml、beautifulsoup4、PyYAML、toml、tomli。

每个名字先读 PyPI JSON 的 Source、Source Code、Repository、Homepage、Home 或 home_page，取第一条 GitHub 仓库。没有 GitHub 地址，或仓库名像 pandas、Pillow、SciPy，就记下 `no_github` 并跳过。不打开本仓库里带密封帧的目录；click 等库只用它们的公开 GitHub 历史，不用本地密封样本。

查询固定为一条，每个仓库只取一页：

`repo:{owner}/{name} is:pr is:merged fix in:title`

按 `updated` 降序，`per_page=30`。这一页再按标题稳定排序：含 raise / exception 的在前，其次是 return / value / incorrect / wrong，其余保持接口原来的顺序。标题含 bump、dependency、changelog、typo、spelling、whitespace 的只记入 `title_skipped`，不占 40 的名额。Rich #3718 与 attrs #1427、#1428 同样只跳过、不占名额。

考察方式是轮转。每一轮按库池顺序从每个库的队列取出下一条，直到纳入 10 组或考察满 40 条，或队列空。考察是指打开这条 PR、取出合并提交的第一父提交、在父树取文档，并写下纳入或排除。40 与 10 谁先到就停。文件列表只取第一页。每条 PR 最多看接口返回的前 5 个非测试 `.py` 修改，以及在这些函数文档都没有义务句时，再看前 5 个 `doc/` 或 `docs/` 下的 `.rst`、`.md`。没有补丁文本的文件不映射到符号。测试路径含 `/test/`、`/tests/`、`/testing/`，或文件名以 `test_` 开头、以 `_test.py` 结尾。

一条父文档句被选中，当且仅当 `select_obligation` 成立，并且同一句在修复提交的同一符号文档（或同一文档文件）里仍然在。同一 PR 里若有的义务句在修复文档中还在、有的已经不在，记为义务含糊，不纳入。强记号是异常类名、质量词、长度至少为 2 的引文字符串，或至少两位的整数或任意小数。强记号只对上一句，就用这一句。对上多句，排除，理由是义务含糊。没有强记号时，只有恰好一句义务，且函数名末段（至少 3 个字符）出现在 PR 或第一条关联议题的正文里，同时正文里有行为词，才纳入。行为词是 raise、raises、raised、exception、return、returns、incorrect、wrong、crash、negative、positive、zero、invalid、overflow、underflow、out of range、off-by-one、greater than、less than。对不上就排除，理由是谓词与记录到的差异不是同一件事。不发明连接。

行为差要引用 PR 或议题里的原句，并记下 URL。父句、路径、父提交、修复提交、文件 SHA-256 和原始 URL 写入 `screening.json`。纳入组的父文档缓存到 `docs/{id}.txt`。中断后按已写入的日志续跑，不改已经写下的决定，也不为了凑满 6 组再开一轮查询。

## 计分前的第二次冻结

检索结束后，纳入少于 6 则不再安装、不再计分，决定是 `insufficient_denominator`。纳入至少 6 时，先把 `cases.json` 和人写检查提交，再运行父版本和修复版本。人写检查只根据纳入的那一句，用下面的表达式，不根据修复侧输出。

每组的驱动代码从议题或 PR 测试的准备部分改写，定义 `call()`，可读全局 `inputs`。不超过 80 行，必须出现该库的导入名，不得写 `assert`，不得写 oracle。安装规格固定为 `git+https://github.com/{repo}.git@{sha}`。普通输入只有在议题或父文档里已经给出第二个确定输入时才冻结；没有就不编造。

人写检查允许的操作：`raises`、`return_equals`、`return_compare`、`return_holds`。`when` 只能使用句中出现的输入名、数字、字符串和质量词所对应的比较。`negative` 才允许把 0 的 `<` 写进条件，`positive` 才允许 `>`，`zero` 才允许 `==`。句中有条件而表达式写不出该条件时，人写检查为空，理由是 `condition_not_encodable` 或 `not_in_expression_language`，不得把条件丢掉改成无条件检查。`audit_human` 不通过则拒绝计分。

驱动若在两侧抛出相同的 `AttributeError`、`TypeError`、`ImportError`、`ModuleNotFoundError` 或 `NameError`，并且两次观察的规范形相同，允许按已引用的议题片段改一次驱动。人写检查、原句和输入里的修复期望都不得在这次修改里变动。看到两侧输出已经不同之后，不得再改驱动或人写检查。

## 方法

实际运行的抽取器只看缓存的父文档和执行得到的第一次返回值或第一次异常。它们不看修复侧输出来学习谓词，不看金标表，也不把目标库的义务再实现一遍。

| 名称 | 做什么 |
| --- | --- |
| `status_only` | 调用失败为告警，成功为通过 |
| `jdoctor_pattern` | 原样导入 `contract_binding/jdoctor_patterns.py` 与 `binding.translate_document(..., "jdoctor")`。这是 Toradocu 3.0 `simpleMatch` 的谓词转写，接到完整返回值。不是 Jdoctor 原程序 |
| `bind` | 原样导入 `binding.translate_document(..., "bind")`。证据约束绑定，规则不改 |
| `sentence_grounded` | 新的保守抽取，见下节 |

`jdoctor_pattern` 和 `bind` 在参数段和异常段上仍然不可求值，因为冻结绑定不接收结构化实参。本轮不把实参补进去，否则就不是原来的方法。

观察只执行一次。四个方法和两道天花板共用同一次父版本运行和同一次修复版本运行。

### sentence_grounded

文档先去掉围栏代码块和 `>>>` 示例，再把折行拼成段落。句号只有在不是小数点时才切开：数字后的句号仅当后面是空白加大写字母或段落结束才切开。再去掉 Sphinx 角色和反引号，但保留里面的词。

一句在同时出现下面任一类时不产出检查：if、when、unless、whether、provided、otherwise、on success、on failure、on error；或 should、could、might、may、can。`cannot` 不含独立的 can。

否则最多产出一条检查。

异常：句中有 raise / raises / raised / raising / throw / throws / thrown，且去掉引号后恰好一个异常类型名（以 Error、Exception、Warning 结尾，或 StopIteration、StopAsyncIteration、GeneratorExit、KeyboardInterrupt、SystemExit）。句中另有 not 或 never 则不产出。检查看的是异常的 `__name__`，不看消息，也不重写“何时该抛”。正常返回算告警，因为这句把抛出写成了无条件义务。

返回值：动词只用 return、returns、equals、is、are、be。动词前的词只能是 the、a、an、this、it、value、result、output、return、returned、function、method、always、will、must、shall、then、also、still、call。动词和谓词之间只能是 a、an、the、value、result、output、of、to、always、number、string、str、int、integer、float、bool、boolean，以及 not、never，外加冒号和逗号。谓词是比较短语加数字、比较符加数字、质量词、True、False、None、引文字符串，或一个数字。数字后的句号不算小数点。质量词用冻结 `holds` 的同一套翻译；not 按同一套取反。谓词后除了一个类型词（integer、int、number、float、value、string、str、bool、boolean、object、result、output）和标点以外不得再有词。一句里有两个动词都配上谓词，或异常和返回值同时配上，就不产出。on success、on failure、on error 与 if 一样，整句不产出检查。

检查只作用在整个第一次返回值上，不取属性、不取字典键。类型对不上记 `cannot_apply`，不是告警，也不是通过。抛出异常时，返回值检查记 `no_return`。

### 分类

沿用契约绑定的标签，但检出更严：父侧告警且修复侧通过，才是 `hit`。契约绑定把修复侧任何非告警都算检出；本轮要求修复侧是 `clear`，因为问题写的是修复版本成立。普通输入任一侧告警是误报。修复侧告警而父侧不告警是方向相反。两侧都告警是双侧告警。两侧都通过是双侧通过。其余是无检查。多条检查合并时，方向相反优先于误报，然后是双侧告警、检出、双侧通过、无检查。

一组对该方法有可执行检查，当合并后的类属于检出、方向相反、双侧告警、双侧通过或误报。分离只指合并类为检出。

## 天花板

两道天花板单列，不进入方法排名。

完整第一次输出：父侧与修复侧的规范形不同，即观察天花板分离。规范形是返回值的 JSON，或异常类型加消息，或不可 JSON 化时的 `repr`。这不是抽取器。

`human_from_sentence`：纳入时写好、运行前冻结的表达式。它是这句话在冻结表达式语言里的上限，不是参与排名的算法。

## 指标与不可运行

计分分母是纳入组里两侧都安装成功、驱动没有 HarnessError，并且完整第一次输出确实不同的组。安装失败、HarnessError 为 `not_runnable`。输出相同为 `not_reproduced`。二者都留在日志里，不进入分离率。若因此少于 6 组，决定仍是 `insufficient_denominator`，不补案例。

每组报告每个方法是否产出可执行检查、是否分离，并报告 `status_only` 和两道天花板。主计数是可执行检查数和分离数，分母是上述可计分组。另给相对 `status_only` 的逐组增减。

## 不运行，也不排名

| 工具 | 原因 |
| --- | --- |
| Jdoctor 原程序 | 输入是 Java 源码，输出是 Java 表达式。`jdoctor_pattern` 只是 Toradocu 3.0 `simpleMatch` 的转写 |
| SPARK 形式契约生成 | 这些案例没有 SPARK/Ada 契约 |
| Gay 等 2015 的变异体预言选择 | 不制造变异体，不把期望值交给抽取器 |
| AGORA+ 原程序 | 面向 REST 与 Daikon，本轮不跑 |
| SpecFuzzer | 面向 Java 轨迹，本轮不跑 |
| Hypothesis 与已冻结合成器 | 会生成新输入，或重启已暂停的 ESWA 原型 |

结果里的 `ranking` 恒为 null。

## 决定

只在检索结束、并且需要计分时运行已经结束之后使用。顺序固定。

1. 检索后纳入少于 6，或可计分的复现组少于 6：`insufficient_denominator`。停止，不排名，不补案例。
2. `bind`、`jdoctor_pattern`、`sentence_grounded` 的分离数都是 0，而人写检查或完整输出至少分开一组：`extraction_loss`。人写检查有分离时理由是 `extraction_loss_human_separates`，否则是 `extraction_loss_observation_only`。停止，本轮不再打磨抽取器。完整输出在每个复现组上都分离，所以三个抽取器全为 0 时这条会先于“打平”成立。
3. 三个抽取器的可执行检查数相同，且分离数相同：`no_new_method`。不声称新方法。
4. `sentence_grounded` 的分离数严格多于 `bind` 且严格多于 `jdoctor_pattern`，并且它没有方向相反、也没有误报：`complement_positive`。报告相对 `status_only` 的计数。明文写出：这个样本不能替换 ISSRE 的 12 组，也不能替换正式封存的四项。
5. 其余：`no_gain`。不声称新方法。

## 预算与入口

不调用模型。检索最多考察 40 条 PR，最多纳入 10 组。计分时每组最多安装父版本和修复版本各一次，每次最多两次调用（差异输入，以及可选的普通输入）。安装超时 300 秒，调用超时 45 秒，顺序执行。共享的版本运行只做一次。

```bash
python3 research/release_drift_20261126/documented_predicate_binding/test_documented_predicate.py
python3 research/release_drift_20261126/documented_predicate_binding/screening.py
python3 research/release_drift_20261126/documented_predicate_binding/run.py
```

第二行只在本协议已经提交且工作区干净时检索。第三行只在 `cases.json` 与 `docs/` 已经提交、且与 `screening.json` 的纳入集合一致时计分。观察缓存在 `results/observations/`，汇总在 `results/summary.json`。`freeze_commit` 是本协议文件的最近一次提交。
