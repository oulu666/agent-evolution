# 2026-11-26 · 父版本文档为什么没有变成可执行谓词

定性分析，执行前冻结。本文件与 `analyze.py` 在写出 `results/analysis.json` 之前提交。分析器若发现这两个文件有未提交改动，拒绝写结果。

这不是计分协议，也不修改冻结研究。`research/release_drift_20261126/contract_binding/` 只读。不重算那里的检出，不加案例，不把 humanize #240 放进分母，不打开校准层来凑结论。含 `sealed` 的帧、`environment_receipts`、pandas、Pillow、SciPy 不打开。正式四项封存变化的分母、CPU 与每任务调用额度都不扩大。不重开 attrs 主动提问，不重启 XlsxWriter 列隐藏修复，不重启已暂停的 ESWA 原型。不调用模型，不重新执行被测库。

冻结研究的协议停在 `22a843467bfdc9d7b9663c0582f05f37cecd3a77`，结论是收窄，理由是 `catalog_gap`。本轮只回答那个收窄留下的问题：同一 12 组上，已经存档的父版本文档为什么没有译成可执行检查；若答案是更窄的目录或改写就能译出记录到的差异，才另写计分协议。本分析器本身不计分。它即使得出保留或收窄，也只把前件写进结果并停止；计分必须是此后另一份协议，先推送，再运行。

## 问题

12 组的完整输出都能把父边界和修复边界分开。状态和粗字段只分开其中 5 组抛异常的边界调用。另外 7 组调用成功，粗字段相同。父文档里有 Args、Returns、Arguments，或被冻结案例表纳进来的译文文件。冻结目录没有从这些文本译出可求值谓词。

本轮要分清两件事。一件是翻译器在哪一句停下。另一件是记录到的父/修复差异，父文本有没有把它写成可检查的谓词。

## 材料

分母仍是独立队列里已经公开、并且 `runs_independent_20261124/replay.json` 有配对输出的 12 组：humanize #273、#254、#250、#218、#216，PrettyTable #378、#356、#355、#345，more-itertools #1088、#1082，Rich #3718。

契约文本只用 `contract_binding/docs/` 里已经缓存的父版本摘录。回放只用 `replay.json` 里已经记录的 `input`、`actual`、`expected`。`expected` 只用来核对冻结摘要里的观察分类，不进入翻译。冻结摘要 `contract_binding/results/summary.json` 只读，用来核对文件哈希和已经发表的分类，不重写。

翻译器只调用冻结的 `binding.py` 与 `jdoctor_patterns.py`。后者是 Toradocu 3.0 `Matcher.simpleMatch` 的谓词转写，不是 Jdoctor 原程序。本轮不运行 Jdoctor 原程序、SPARK 形式契约生成、Gay 等 2015 的变异体预言选择、AGORA+ 原程序、SpecFuzzer、Hypothesis 或已冻结合成器。不产生工具排名。

## 组的划分

从回放直接划分，并与冻结摘要里的 `published_observer` 核对。不一致就停止，不改写任一边。

盲组：父边界和修复边界都成功，两侧粗字段相同，两侧完整值不同。冻结研究里这是状态双侧通过、粗观察双侧通过、完整值检出的那 7 组。

异常组：父边界调用失败，修复边界调用成功。冻结研究里状态基线已经在这 5 组上检出。

## 漂移类

每组恰好一类，按下面的顺序取第一件成立的事。

1. `exception_versus_value`。该组是异常组。记录到的分离是抛出的异常。返回值谓词在冻结规则下对抛错调用记为 `no_return`，不把异常本身当成契约违约。
2. `parent_doc_encodes_bug`。该组是盲组，并且父文本里同一条 gettext 条目的 `msgstr[0]` 与 `msgstr[1]` 都等于父边界完整值里的那个表面词，修复边界的表面词不在父文本中。执行父文本会放过父版本。
3. `implicit_visual_or_format`。该组是盲组，而且上一类不成立。父边界和修复边界的差别是单位写法、小数、进位、字形或颜色。判定这一类时，不把文档别处偶然出现的单词当成对这次调用的授权。

## 翻译停在哪里

对存档摘录重跑冻结的 `translate_document`。预期仍是零条已翻译检查。这个计数只核对冻结行为还在，不进入新的检出表。

逐句沿用冻结的切句、义务改写和 `simple_match`。每一句记录第一个停止点：

| 停止点 | 含义 |
| --- | --- |
| `removed_before_match` | 引语在 `>>>` 示例里，冻结规则先删掉示例，不套到别的调用上 |
| `period_splits_illustration` | 小数点被当成句号，例证在进入谓词表之前被切开 |
| `verb_outside_catalog` | 句中有 becomes 一类动词，目录里的动词只有 is、are、be、return、returns |
| `no_catalog_verb` | 切句后没有目录动词 |
| `quality_without_catalog_verb` | 出现 true、false、none、zero 等词，前面没有目录动词 |
| `python_none_without_catalog_verb` | 词是 Python 的 None，目录里对应的是 null，且前面没有目录动词 |
| `tokens_between_verb_and_quality` | 目录动词和质量词之间隔了反引号或其他词；`simpleMatch` 只允许最多一个空格 |
| `quantity_before_verb` | 数量词在动词前面，谓词一侧没有可译的质量词 |
| `verb_without_quality` | 有目录动词，宾语不是 true、false、null、empty、数字或正负 |
| `translated` | 冻结目录给出了翻译。12 组上不应出现 |

肯定式的 should be 不在冻结义务表里。表里只有 should not be。出现 should be 时另记 `positive_should_not_rewritten`。

这些停止点再归到四类缺口，供报告使用。句式、标点、None 与 null、动词不在表内、数量词在动词前，记为风格句式。gettext 复数公式、以及参数只写了“用来绘制的字符”却没有写出字符本身，记为谓词族在文本里没有落到这次调用。盲组的记录差异记为隐含视觉或格式约定。异常组记为例外对返回值。后两类可以同时出现在同一组的不同字段上：停止点描述句子，漂移类描述记录到的差异。

## 保留、收窄或停止

只看本轮是否值得另开计分协议。不改冻结研究的收窄结论。

一组 `justifies_scoring_protocol` 为真，当且仅当它是盲组，并且删掉文档示例之后的文本里存在一句，同时满足：

- 冻结的 `simple_match` 没有把它译成检查；
- 这一句含有修复边界的完整返回字符串，或者含有一个目录质量词，冻结的 `holds` 对修复边界的完整值为真、对父边界的完整值为假、对两侧普通输入都不为假；
- 这一句不是 gettext 的 `msgid` 或 `msgstr` 行。单侧译文槽不等于对整句返回值的谓词。

三个局部改写只做走查，每个走查记录 `separates_blind_group`。走查结果不写成方法检出，也不与冻结的 `bind` 或 `status_only` 排成名次。

| 候选 | 它针对什么 | 相对哪条基线才算增益 | 停止条件 |
| --- | --- | --- | --- |
| 去掉反引号后再跑 `simpleMatch` | more-itertools #1088 的 `Return ``True``` | 必须在盲组上分开父边界和修复边界，并且不能只重复 `status_only` 已经分开的异常组 | 无条件的 `==true` 在修复边界的已存储返回值上为假，或该组不是盲组 |
| 执行父文本里的 gettext 复数槽 | humanize #273 与 #216 的单位词 | 必须在盲组上把父边界判为违约、修复边界判为通过，而且父文本写明了这次打印出来的系数就是公式里的 n | `msgstr[0]` 与 `msgstr[1]` 都是父边界的表面词，或文本没有把 n 绑到已记录的返回值。出现前者就停止，因为执行父文本会放过父版本 |
| 把肯定式 should be 改写成 is | PrettyTable #378 的 “should be an iterable of lists” | 必须在盲组上产生可求值检查 | 改写后 `simpleMatch` 仍然没有质量词，或该组是异常组，或记录里没有结构化实参 |

决定：

- 任一盲组 `justifies_scoring_protocol` 为真：保留。表示此后可以另写计分协议。本分析器仍不计分。
- 否则任一走查的 `separates_blind_group` 为真：收窄。表示此后只允许把那一种已经走查通过的局部改写写成新协议，先推送再计分。
- 其余：停止。登记限制，不另开计分协议，不加案例，不补写文档，不把粗字段换成更细的字段。

停止之后，若要重启这一方向，新证据必须是：某一盲组的父文本里，有一句写明了这次记录的修复边界返回值，或写明了一个能用冻结 `holds` 分开两侧、且不误伤普通输入的质量词。父文本把缺陷形式写成唯一译文、示例属于另一次调用、或只有类型与参数角色，都不构成这种证据。
