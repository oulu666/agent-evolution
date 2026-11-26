# 2026-11-26 · 文档里已经有可检查谓词时，现有抽取器能否给出可执行检查

开发研究，执行前冻结。本文件与 `outcomes.py`、`selection.py`、`run.py`、`test_documented_api_extraction.py` 在任何纳入或排除决定、以及任何分数之前提交。`selection.py` 若发现本文件、`selection.py` 或 `outcomes.py` 有未提交改动，或 `screening.json`、`cases.json` 已经存在，拒绝筛选。`run.py` 若发现本文件、`outcomes.py`、`selection.py`、`run.py`、`cases.json`、`screening.json` 或 `docs/` 有未提交改动，拒绝计分。

这不是 `documented_predicate_binding` 的续作，也不重开那次检索。那次研究（冻结 `f0805b3742c2c5c6de728e49dd1d849cda16567b`，压缩提交 `34940aa3169c20dbcc3e102f43094c42e6c47f5c`）问的是：父文档里的可检查句子是否说的就是某次历史修复。分母不足 6，决定是 `insufficient_denominator`。连接器不放宽，那次检索不重开，那次样本不重算。attrs 与 hypothesis 也不补进那次旧检索。

本轮只问另一件事：某个公开 API 的当前文档已经写下一句可检查谓词时，现有抽取器能否只凭这句文档，产出一条可执行检查，使它在预先登记的合法输入上成立，并在预先登记的违约输入上失败。两个输入都来自同一句。这是抽取器在已有文档上的可行性，不是静默漂移检测，不是抓历史修复，不能替换 ISSRE 的 12 组，也不能替换正式封存的四项。

不改写、不重算已归档的 `repair_gate`、`boundary_gap`、`contract_binding`、`catalog_gap_analysis`、`documented_predicate_binding`。那些目录只读，允许按原文件导入。不打开含 `sealed` 的帧、`environment_receipts`、pandas、Pillow 或 SciPy。不把 XlsxWriter 列隐藏再写成一条新结论。不重启已暂停的 ESWA 原型，也不做主动验证。不开始正式成对主比较，不提前揭盲，也不把 11 月 30 日方法冻结清单勾成已经开始。损失权重 0/1/5 本轮不使用。不调用模型。

## 问题与假设

公开库的当前文档已经用一句话写下可检查义务。`jdoctor_pattern`、`bind` 和 `sentence_grounded` 只看这句话及其所在 docstring，不看函数体，不看两个输入的标签，也不查金标表。它们能否给出一条检查，使合法输入的观察成立、违约输入的观察失败。

假设：若句子是无条件的具体值，`sentence_grounded` 能抽出检查；若两个输入必须靠 if、when、otherwise 或 raises-if 才能同时写出来，它按既有规则不产出检查。`bind` 与 `jdoctor_pattern` 仍是契约绑定研究里的原样，差别只在于后者只读带 Parameters、Returns、Raises 等标记的块。相对强基线，没有新的抽取算法。人写检查 `human_from_sentence` 是天花板，不进入排名。负结果保留。

能同时从一句里写出两个输入的句子，多数带条件。这不是为了让某个抽取器失败而挑的样本，而是纳入规则本身要求两个输入都由该句决定。抽取器规则本轮不改。

## 库池与版本

按这个顺序，到此为止。筛选开始后不加库：click、requests、httpx、pydantic、pytest、Jinja2、flask、werkzeug、marshmallow、jsonschema、python-dateutil、arrow、attrs、rich、hypothesis、lxml、beautifulsoup4、PyYAML、tomli。

导入根分别是 click、requests、httpx、pydantic、pytest、jinja2、flask、werkzeug、marshmallow、jsonschema、dateutil、arrow、attr 与 attrs、rich、hypothesis、lxml、bs4、yaml、tomli。attrs 这个发行版同时看 `attr` 和 `attrs` 两个包目录，仍算同一个库。

每个名字取 PyPI JSON 在筛选当时报告的当前版本。优先用该版本的 sdist；没有 sdist 才用 wheel。超过 80MB 的包记 `sdist_too_large` 并跳过，不换别的版本。解压 tar 时使用 Python 的 `data` 过滤器；因此打不开的包记下错误并跳过，不换版本。文件 SHA-256 必须与 PyPI 摘要一致。版本、URL 和摘要写入 `screening.json`。之后重跑计分只用这份钉死的版本，不再查 “latest”。pandas、Pillow、SciPy 不在池内，产物 URL 里出现这三个名字就拒绝。

## 符号从哪里来

只看发行包里的公开 `.py`。跳过路径中的 tests、test、testing、docs、doc、examples、example、benchmarks、benchmark、vendor、vendored、`_vendor`、typings，以及文件名以 `test_` 开头、以 `_test.py` 结尾或名为 `conftest.py` 的文件。父目录或文件名以 `_` 开头的模块跳过，`__init__.py` 除外。`.pyi`、`.pyx` 不解析。

候选符号只有两类：

- 模块级公开函数。名字以 `_` 开头的不算。
- 公开类里手写的 `__init__`。`__init__` 自己有 docstring 就用它；没有才用类的 docstring。没有手写 `__init__` 的类整段跳过，不从字段注解猜构造参数。

类里的其他方法需要实例，句子往往写不出这个实例怎么来，所以不进入候选，只在 `skipped.methods` 里计数，不占 40 的名额。异步函数、名字在拒绝表里的函数、以及装饰器名为下面任一项或装饰器形状认不出的函数，同样只计数、不考察：property、cached_property、contextmanager、asynccontextmanager、overload、command、group、option、argument、pass_context、pass_obj、fixture、hookimpl、hookspec、route、get、post、put、delete、patch、head、before_request、errorhandler、endpoint、validator、field_validator、model_validator、given、example、settings、app_context、request_context。

函数名拒绝表：now、utcnow、today、sleep、urlopen、urlretrieve、time、random、randrange、uuid4、uuid1、uuid。这里的 hypothesis 包可以成为被测 API；Hypothesis 这个生成输入的工具不运行。

签名只用 AST 的参数名、是否有默认值、是否仅限位置。函数体不读，也不用来编谓词或输入。

## 什么算一句候选

docstring 先按 `documented_predicate_binding/sentence_grounded.py` 的 `split_sentences` 切开。围栏代码块和 `>>>` 示例在切开之前去掉，因此只出现在示例里的句子不是候选。一句在 `strip_markup` 之后使 `is_obligation` 为真，才是候选。这包括具体返回值或输出值、异常类型、比较、范围，以及冻结 `holds` 词汇里的质量词。空（empty）仍然不产生翻译。

清理后超过 400 个字符的句子不做模式匹配，若被考察则理由是 `inputs_not_determined_by_sentence`。

## 一句怎样同时给出两个输入

操作型定义在冻结的 `selection.py`。模式按下面的顺序，先命中者获胜。命中但两个分支无法区分，或异常类型不是恰好一个，理由是 `ambiguous_obligation`，不再改试更松的模式。

条件词到一对值的表在筛选前写死。`when_true` 是条件成立时的值，`when_false` 是条件不成立时的值。整数边界只在句子里的数是整数时加减 1。`none`、`null` 和引文没有冻结的另一侧，不能当条件。质量词 zero 只用来选输入；它不能单独写成 `return_holds ==0`，因为既有 `audit_human` 对 `==0` 要求句子里有数字。

| 条件 | 成立 | 不成立 |
| --- | --- | --- |
| positive、strictly positive | 1 | 0 |
| negative、strictly negative | -1 | 0 |
| zero | 0 | 1 |
| true | True | False |
| false | False | True |
| even | 0 | 1 |
| odd | 1 | 0 |
| non-negative、nonnegative | 0 | -1 |
| non-positive、nonpositive | 0 | 1 |
| greater than N、`> N` | N+1 | N |
| greater than or equal to N、at least N、`>= N` | N | N-1 |
| less than N、`< N` | N-1 | N |
| less than or equal to N、at most N、`<= N` | N | N+1 |
| equal to N、`== N` | N | N+1 |
| `!= N` | N+1 | N |

`is not` 与单独的 `not` 对调两列。

1. `return_if`。句子是“returns / is / equals 甲 if 或 when 参数 条件，and 或逗号，乙 otherwise 或 else”。也接受 “甲 if 参数 条件 else 乙”。合法输入是条件成立的值，违约输入是条件不成立的值。人写检查是甲的 `return_equals` 或 `return_holds`。甲和乙必须都能译出，并且译文不同。一句里有两个 if，视为含糊。
2. `return_and_raise`。同一句里既有不带 if、when、unless 的 return 谓词，又有下面的 raise 条件。合法与违约输入跟着 raise。人写检查用 return 谓词，不用异常。
3. `raise_if`。下面三种形状之一，且整句只有一个异常类型：`raises/raise EXC if/when/unless 参数 条件`；`if 参数 条件, raise EXC` 或 `if 参数 条件, a EXC is raised`；`EXC is raised if/when/unless 参数 条件`。if 与 when 下，合法输入是条件不成立的值，违约输入是条件成立的值，也就是句子写明的非法值。unless 对调。人写检查是 `{"op": "raises", "type": EXC}`。这条检查在文档行为成立时会在违约输入上成立、在合法输入上失败，标签是 `inverted`，不是 `full_success`。不把极性反过来凑成功。

参数名必须出现在签名里。句子只说 the value、input、obj、object、number、item、data、text、string、arg 或 argument，而必填参数恰好一个时，才绑定到那一个参数。其他必填参数没有默认值，理由是 `needs_extra_arguments`。仅限位置的参数只有在它是第一个位置参数时才用位置传参，否则同样是 `needs_extra_arguments`。

人写检查必须通过既有的 `audit_human`，字面量都要能在该句里找到。通不过则 `not_in_expression_language`。不发明谓词，也不为了让检查可写而改句子。

同一函数、同一参数、同一人写检查再出现，是 `duplicate_obligation`。每个函数最多纳入 2 条，每个库最多 4 条，超出的考察记录为 `function_cap` 或 `library_cap`。历史缺陷报告不是纳入证据。本轮不读 PR、议题或修复提交。

## 考察顺序与上限

每个库先把候选按优先级排好：`return_if`，然后 `return_and_raise`，然后 `raise_if` 与含糊句，然后其余义务句。同级按路径、行号、句序。库与库之间轮转：每一轮按库池顺序各取该库队列的下一句。

停在考察满 40 句或纳入满 12 条，谁先到停谁。队列先空则 `pool_exhausted`。40 句里每一句都写入 `screening.json`，带 include 或 exclude 和理由。没轮到的候选只计数，不逐句补录。跳过的方法、私有模块和装饰器只计数，不占 40。

原句必须在钉死的源文件和 docstring 里，空白折叠后是子串。源文件按 SHA-256 存到 `docs/sources/`，纳入句的 docstring 存到 `docs/{id}.docstring.txt`。对不上则 `quote_not_in_file` 或 `quote_not_in_docstring`。

## 计分前的第二次冻结

筛选写完就停。先提交 `screening.json`、`cases.json` 和 `docs/`，再运行库。纳入少于 8，或纳入库少于 3，`run.py` 不安装、不调用抽取器，决定是 `insufficient_denominator`。不补案例，不放宽模式。

纳入达到 8 且至少 3 个库时才安装、才调用。每个库在独立 venv 里安装钉死的版本一次，安装超时 300 秒。每条义务调用两次，一次合法输入，一次违约输入，调用超时 45 秒，套接字超时 2 秒。输入只有冻结表里的整数或布尔值。驱动由 `build_driver` 生成，只读 `inputs['value']`，不超过 40 行，不写 assert，不写 oracle。

## 方法

抽取器的输入是冻结的 docstring。只把来源句对得上纳入句的检查算进这条义务。对得上是指空白和标记去掉之后两句相同，或较短的一句占较长一句的至少 80%，并且在 `binding.preprocess` 之后也允许再比一次。docstring 里其他句子产出的检查记在明细里也不算这条义务的成功。

| 名称 | 做什么 |
| --- | --- |
| `jdoctor_pattern` | 原样导入 `contract_binding/jdoctor_patterns.py` 与 `binding.translate_document(..., "jdoctor")`。这是 Toradocu 3.0 `simpleMatch` 的谓词转写，接到完整返回值。不是 Jdoctor 原程序 |
| `bind` | 原样导入 `binding.translate_document(..., "bind")`。证据约束绑定，规则不改 |
| `sentence_grounded` | 原样导入 `documented_predicate_binding/sentence_grounded.py` 的 `extract` 与 `apply_grounded`。条件句和含 should、could、might、may、can 的句子不产出检查 |

`human_from_sentence` 是筛选时写好、运行前冻结的表达式，用既有的 `eval_human`。它不进入排名。

一条检查在一次观察上：`clear` 为成立，`alarm` 与 `no_return` 为失败，其余为错误。两个观察合成一个标签，优先级是 `full_success`、`inverted`、`hold_only`、`fail_only`、`error`、`no_check`。

- `full_success`：合法观察上成立，且违约观察上失败。
- `inverted`：合法观察上失败，违约观察上成立。
- `hold_only`：合法观察上成立，违约观察上并不失败。
- `fail_only`：两次都失败。
- `error`：检查无法套用，或安装、驱动、超时失败。安装失败时仍可报告有没有产出检查，但标签是 error，不算可执行。
- `no_check`：没有对得上纳入句的检查。

多个对得上的检查里，只要有一条是 `full_success`，该方法在这条义务上就是 `full_success`。若同时还有一条 `inverted`，明细里的 `contradicts` 为真，但不取消这条成功。可执行指标签属于 `full_success`、`inverted`、`hold_only`、`fail_only`。

主计数是纳入义务上的可执行检查率和 `full_success` 率。分母是全部纳入义务，安装失败不剔出。另报 hold-only、fail-only、no-check、error，以及 inverted。

## 不运行，也不排名

| 工具 | 原因 |
| --- | --- |
| Jdoctor | 输入是 Java 源码，输出是 Java 表达式。`jdoctor_pattern` 只是 Toradocu 3.0 `simpleMatch` 的转写 |
| SPARK | 这些案例没有 SPARK/Ada 契约 |
| Gay et al. 2015 | 不制造变异体，不把期望值交给抽取器 |
| AGORA+ | 面向 REST 与 Daikon，本轮不跑 |
| SpecFuzzer | 面向 Java 轨迹，本轮不跑 |
| Hypothesis | 会生成新输入。hypothesis 库可以作为被测 API，Hypothesis 工具不运行 |

`ranking` 恒为 null。

## 决定

只在筛选结束之后使用。需要计分时，还要等计分结束。顺序固定。

1. 纳入少于 8，或库少于 3：`insufficient_denominator`。停止，不排名，不补案例。
2. 三个抽取器的 `full_success` 都严格小于纳入数的四分之一，而 `human_from_sentence` 的 `full_success` 至少占一半：`extraction_loss`，理由 `extractors_near_zero_human_succeeds`。损失在自动抽取。本轮不偷看观察再改抽取器。
3. 三个抽取器的可执行数相同，且 `full_success` 数相同：`no_new_method`。不声称新方法。
4. 至少一个抽取器的 `full_success` 至少为 1：`counts_reported`，理由 `extractor_full_success_is_not_drift_detection`。报告相对人写天花板的计数。明文写出：这不是漂移检测，不能替换 ISSRE 的 12 组，也不能替换正式封存的四项。
5. 其余：`no_gain`。不声称新方法。

“接近 0”就是严格小于四分之一。8 条里的 1 条算接近 0，2 条不算。人写检查至少一半，8 条里是至少 4 条。

## 预算与入口

不调用模型。筛选最多考察 40 句，最多纳入 12 条。计分时每个纳入库安装一次，每条义务两次调用。共享的安装只做一次。

```bash
python3 research/release_drift_20261126/documented_api_extraction/test_documented_api_extraction.py
python3 research/release_drift_20261126/documented_api_extraction/selection.py
python3 research/release_drift_20261126/documented_api_extraction/run.py
```

第二行只在本协议已经提交且工作区干净时筛选，并且不调用被测函数。第三行只在案例表和 `docs/` 已经提交、且与 `screening.json` 的纳入集合一致时运行。观察缓存在 `results/observations/`，汇总在 `results/summary.json`。`freeze_commit` 是本协议文件的最近一次提交。
