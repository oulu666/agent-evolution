# 父文档已经写明谓词时，抽取器能否绑成可执行检查

**2026 年 11 月 26 日。** 决定是**分母不足**（`insufficient_denominator`）。有界检索考察了 40 条合并的修复 PR，机械规则纳入 4 条，独立修复不足 6 组。没有安装父版本或修复版本，没有方法计分，没有工具排名。

冻结提交是 `f0805b3742c2c5c6de728e49dd1d849cda16567b`。`protocol.md` 的 SHA-256 是 `9d78ae6bb3d790576deb83486166db8b284c73898a98e1520db89d9979089dd3`。检索在这次冻结之后进行。协议、`sentence_grounded.py` 和 `screening.py` 在检索时没有未提交改动。`run.py` 没有执行。

## 本轮问的是什么

契约绑定在 12 组上的 `bind` 和 `jdoctor_pattern` 都是 0/12 可执行检查。目录缺口分析接着停止：状态和粗字段看不见的 7 组里，父文档没有把记录到的修复值写成可检查谓词。那两份结果分不清文档没写和写了但抽不出来。本轮只在父文档已经有可检查句子的历史修复上问抽取。它是补充分母，不替换 ISSRE 的 12 组，也不替换正式封存的四项。

`jdoctor_pattern` 仍然只是 Toradocu 3.0 `simpleMatch` 的转写，不是 Jdoctor 原程序。Jdoctor 原程序、SPARK、Gay 等 2015 的变异体预言选择、AGORA+ 原程序、SpecFuzzer、Hypothesis 和已冻结合成器都没有运行，也不排名。

## 检索

库池、查询、30 条一页、相关度轮转、40 条考察或 10 条纳入的上限都写在冻结协议里。实际停在 40 条考察，`stopped_because` 是 `40_examined`。另有 48 条标题被预登记的依赖升级、变更日志、错别字或空白过滤掉，不占这 40 个名额。

| 结果 | 数量 |
| --- | --- |
| 考察 | 40 |
| 机械纳入 | 4 |
| 排除 | 36 |
| 标题过滤，不占名额 | 48 |
| 没进入队列的库 | attrs、hypothesis、beautifulsoup4 |

排除理由是 `no_parent_sentence` 16、`ambiguous_obligation` 12、`not_a_behavior_repair` 5、`predicate_not_about_recorded_difference` 2、`parent_sentence_absent_from_fix` 1。逐条 PR、父提交和理由在 [SCREENING_ZH.md](SCREENING_ZH.md) 和 `screening.json`。

attrs 的 GitHub 地址在 PyPI 的 `GitHub` 字段，hypothesis 的在小写 `source`。冻结字段表没有这两个名字，所以两个库没有被检索。beautifulsoup4 的 Homepage 是 crummy.com，注册字段里没有 GitHub。发现这一点之后没有把字段表加宽再搜，也没有把这两个库补进分母。

## 四条机械纳入为什么不够六组

四句都从父提交的文件里重新取过，文件哈希与日志一致。

httpx [#2669](https://github.com/encode/httpx/pull/2669) 的父句是 “Can be set to `False` for use cases such as testing the content of a client 500 response.” 它和 `raise_app_exceptions=False` 仍会抛异常是同一开关上的事。句子本身是用途说明，带 can，不是无条件义务。

marshmallow [#2792](https://github.com/marshmallow-code/marshmallow/pull/2792) 的父句是 “If `None`, the value for `self.many` is used.” 强记号 `none` 对上的是 PR 正文里 `-> None` 的注解。PR 标题说的是校验错误中的 `data_key`。这不是同一条义务，不把它算成可计分组。

arrow [#1242](https://github.com/arrow-py/arrow/pull/1242) 和它的回退 [#1264](https://github.com/arrow-py/arrow/pull/1264) 用的是同一句 `only_distance` 文档，强记号是引文 `in`。冻结实现把引文按子串去对 PR 文本，`in` 会落进普通英文。记录到的差异是 16 天被说成 “a month”。回退和原修复按“一次独立修复一组”也只算一件事，而且这件事并不是这句文档。

因此，机械纳入 4 不等于 4 个可计分的独立组。即便不把误连的句子剔掉，4 也小于预登记的 6。没有为了凑满 6 而放宽记号、加库或再开一页。

## 决定

计分需要至少 6 个独立纳入组。这里没有。决定是 `insufficient_denominator`。`sentence_grounded`、`bind`、`jdoctor_pattern` 和 `status_only` 都没有在这个样本上跑出可执行检查数或分离数。两道天花板也没有跑。`ranking` 是 null。

这个空缺不能解释成“抽取器失败”或“抽取器成功”。分母不够，两种说法都没有依据。相对 `status_only` 没有逐组增减，因为没有一次父版本对修复版本的运行。成本是 PyPI 和 GitHub 的只读请求，没有模型调用，没有安装被测库。

已归档的列隐藏修复、attrs 主动验证、12 组契约绑定和目录缺口分析都没有改写，也没有重算。正式四项封存分母、三次额外调用额度和 11 月 30 日方法冻结清单都没有提前启动。负结果留在 `screening.json`。

若要重启这一问，新证据得是另一份先冻结的检索：在考察上限之内已经有至少 6 个独立修复，每组都能从父树引用一句，而这句说的就是该组记录到的行为差。用短引文的子串或注解里的 `None` 去连无关 PR，不算这种证据。

## 复现

```bash
python3 research/release_drift_20261126/documented_predicate_binding/test_documented_predicate.py
python3 research/release_drift_20261126/documented_predicate_binding/screening.py
```

第二行在协议或抽取器有未提交改动时拒绝检索。已有 `screening.json` 时它只续跑未完成的队列，不重判已经写下的决定。`run.py` 在没有与纳入集合一致的 `cases.json` 时拒绝计分；本轮没有生成那份案例表。
