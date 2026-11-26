# 父版本文档为什么没有变成可执行谓词

**2026 年 11 月 26 日。** 决定是**停止**。没有新的计分运行，也没有工具排名。同一 12 组上，冻结翻译器仍然给出 0 条可执行检查。状态和粗字段看不见的 7 组里，6 组的父/修复差异是父文本没有写成谓词的格式或视觉约定；humanize #216 的父译文把缺陷形式写进了两个复数槽。保留和收窄的前件都不成立。

分析协议提交是 `f40de3285593d246fa03e969826e6375c654d426`。`protocol.md` 的 SHA-256 是 `5a779742ab6cb01b853f17a69c3f7a9ef295604059be1beedd91b75bef5870c9`。写 `results/analysis.json` 时，协议和 `analyze.py` 没有未提交改动。冻结研究的协议提交仍是 `22a843467bfdc9d7b9663c0582f05f37cecd3a77`，五份冻结文件的哈希与当时的 `summary.json` 一致。

## 本轮做了什么

冻结研究已经判定收窄，理由是 `catalog_gap`。本轮只回答那个收窄留下的问题：存档的 Args、Returns 和案例表已经纳入的父文本，为什么没有变成可执行谓词；更窄的目录或改写是否值得另写一份计分协议。

材料只来自已经存下来的回放和文档缓存。分母仍是 humanize #273、#254、#250、#218、#216，PrettyTable #378、#356、#355、#345，more-itertools #1088、#1082，Rich #3718。`expected` 没有进入翻译。翻译器是冻结的 Toradocu 3.0 `simpleMatch` 转写，用来标出它在哪一句停下。Jdoctor 原程序、SPARK、Gay 等 2015 的变异体预言选择、AGORA+ 原程序、SpecFuzzer、Hypothesis 和已冻结合成器都没有运行。

`contract_binding/` 没有改。没有把 #240 放进分母，没有打开校准层、密封帧、pandas、Pillow 或 SciPy，没有重开主动提问、列隐藏修复或已暂停的 ESWA 原型。没有调用模型，也没有重新执行这些库。

## 12 组里哪 7 组看不见

回放把 12 组分成两类，并与冻结摘要里的 `published_observer` 一致。

异常组 5 个：PrettyTable #378、#355、#345，more-itertools #1088、#1082。父边界抛异常，修复边界成功。冻结的 `status_only` 已经在这 5 组上检出。

盲组 7 个：humanize 的五个分母组、PrettyTable #356、Rich #3718。两侧调用都成功，粗字段相同，完整字符串或颜色不同。

| 组 | 边界输入 | 父边界完整值 | 修复边界完整值 | 粗字段 |
| --- | --- | --- | --- | --- |
| humanize #273 | fr_FR 1010000，一位小数 | `1.0 millions` | `1.0 million` | 都是 1.0 |
| humanize #254 | 59.5 秒，零位小数 | `60 seconds` | `1 minute` | 都是 60.0 |
| humanize #250 | 浮点 1 | `1.0 Byte` | `1 Byte` | 都是 1 |
| humanize #218 | numpy.int32 的 3000000 | `-1.3 MB` | `3.0 MB` | 都是 MB |
| humanize #216 | pt_BR 2000000000 | `2.0 bilhão` | `2.0 bilhões` | 都是 2.0 |
| PrettyTable #356 | 单线边框，同样两行 | `└` | `├` | 都是 X、Y |
| Rich #3718 | 蓝底、红标题 | 标题背景空 | 标题背景 `blue` | 标题文字都是 title |

## 目录在哪一句停下

冻结切句之后，12 组的 `bind` 和 `jdoctor_pattern` 都是 0 条翻译。停止点是下面几类。Returns 段在 humanize #273 和 #216 上没有被后续标题关上，后面的 gettext 文件整段落在返回块里；那些译文行同样没有译出谓词。

**风格句式。** 目录动词只有 is、are、be、return、returns。质量词只有 true、false、null、empty、zero、正负和数字，而且动词和质量词之间最多一个空格。empty 即使贴着动词，冻结的 `_quality` 也不给翻译。

- humanize #273 的说明句被小数点切开。原文是 `1_000_000 becomes "1.0 million"`。进入谓词表的片段是 `For example, 1_000_000 becomes "1`。becomes 不在动词表里。
- 同一函数的 Returns 被换行切成两句。第一句是 “str: Friendly text representation as a string, unless the value passed could not”。第二句以 be coaxed into an 开头，int 由反引号包住。动词是 be，后面的词不是目录里的质量词。
- humanize #250 和 #218 的 Returns 是 `str: Human readable representation of a filesize`。这句没有目录动词。参数句 `If True, uses binary suffixes` 里有 True，前面的词是 If，不是 is 或 return。
- humanize #254 的首句是 `Return a precise representation of a timedelta`。return 后面是 a precise representation，不是 true 或数字。后文 `a value of zero will be returned` 经冻结改写变成 `a value of zero is returned`。zero 留在动词前面。
- PrettyTable #378 写的是 `rows - rows of data, should be an iterable of lists`。肯定式 should be 不在冻结义务表里，表里只有 should not be。留下的 be an iterable 没有质量词。
- PrettyTable #356 的 `header - print a header showing field names (True or False)` 把 True 放在括号里，前面没有目录动词。`if False return an empty string` 在 return 和 empty 之间隔着 an。empty 本身在冻结表里也不产出检查。
- Rich #3718 的 `Defaults to None` 没有目录动词。目录里的空值词是 Java 的 null，不是 Python 的 None。`Defaults to False` 同样没有目录动词。

**反引号和异常句。** more-itertools #1088 的首句以 Return 开头，True 被双反引号包住，后面是 if exactly n items are True，第二个 True 同样被双反引号包住。反引号使 `simpleMatch` 配不上 True。#1082 的 “ValueError will be raised” 被改写成 “ValueError is raised”。raised 不是质量词。

**示例先被删掉。** humanize #218 的文档示例含有 `'3.0 MB'`。冻结规则先删除 `>>>` 示例，并且不把示例套到另一次调用上。剩下的 Returns 仍是上面那句类型说明。

## 7 组的差异父文本写成了什么

这 7 组的完整值确实不同。父文本写的是类型、参数角色、默认值，或者另一条条件下的句子。记录到的那个返回值没有成为其中一句的谓词。

humanize #273。英文 Returns 只要求一个能读的字符串，并说明无法变成 int 时的退路。法文 gettext 同时给出 `msgstr[0] "million"` 和 `msgstr[1] "millions"`，文件头有 `Plural-Forms: nplurals=2; plural=(n > 1)`。公式里没有目录动词，文件也没有写明这次打印出来的 1.0 就是公式里的 n。两个槽都在，单看其中一个槽不能当成整句返回值的谓词。按本轮已经推送的协议，这一组不构成计分前件。

humanize #254。记录到的是 59.5 秒、零位小数，父边界 `60 seconds`，修复边界 `1 minute`。文档里和零有关的句子是另一条条件：`If the delta is too small to be represented with the minimum unit, a value of zero will be returned`。两次存储的返回值都不是零。文档别处的示例用过 seconds 和 minutes，那些示例是别的 timedelta。

humanize #250。Returns 只写了 `str: Human readable representation of a filesize`。存档文本里没有 `1.0 Byte`，也没有 `1 Byte`。两侧都是可读的大小字符串，差别在系数字面。

humanize #218。示例 `naturalsize(3000000)` 的期望输出是 `3.0 MB`，对应的是普通的 Python 整数那一行，父版本和修复版本在那一行都已经是 `3.0 MB`。边界输入是 `3000000 as numpy.int32`。父文本里没有 numpy。`-1.3 MB` 也没有出现。示例覆盖的是另一行。

humanize #216。英文 Returns 与 #273 相同，不写葡萄牙语复数。父文本的 billion 条目是：

```
msgid "billion"
msgstr[0] "bilhão"
msgstr[1] "bilhão"
```

父边界的表面词是 bilhão，修复边界的 `bilhões` 不在这份父文本里。两个槽都写成父版本的形式。按协议，这种情况记为父文本把缺陷形式写成了译文，gettext 槽没有执行。执行父文本会把修复版的 `bilhões` 当成离开父文本的一方。

PrettyTable #356。粗字段两侧都是 X、Y。完整值是底角字符 `└` 和 `├`。参数段写的是角色：`bottom_left_junction_char` 以及 `single character string used to draw bottom-left line junctions`。这两个字形都不在父文本里。`if False return an empty string` 说的是空表，这次记录的表有两行。

Rich #3718。粗字段两侧都是标题文字 title。完整值是标题背景：父边界为空，修复边界为 blue。父文本写的是 `Optional title displayed in panel header. Defaults to None`，以及 `The style of the panel (border and contents). Defaults to "none"`。存档文档里没有 blue，也没有“标题背景等于面板背景”这样的句子。Defaults to None 说的是标题参数的默认值，这次调用带的是红标题。

## 三个局部改写为什么没有另开协议

协议在出结果之前列出了三个机制不同的候选。它们都做了走查，走查不记成方法分数，`separates_blind_group` 都是假。

去掉反引号后再跑 `simpleMatch`，针对的是 #1088。走查句变成 `Return True if exactly n items in the iterable are True`，翻译是 `==true`。这里使用的是 Toradocu 3.0 谓词转写，并删去反引号。Jdoctor 原程序没有运行。普通输入两侧都返回 True，谓词通过。父边界抛 ValueError，冻结规则记为 `no_return`。修复边界的已存储返回值是 False，`holds` 为假，记为告警。走查分类是方向相反。这一组又是异常组，状态基线已经分开它。它分不开任何盲组。原句还是条件句：恰好 n 个为真时才返回 True。这次边界的正确答案就是 False。

执行 gettext 复数槽，针对的是 #273 和 #216。#216 的两个槽都是 bilhão，协议的停止条件已经出现在父文本里，槽没有执行。#273 的两个槽不同，文本没有把打印出的系数绑到 n，槽也没有执行。

把肯定式 should be 改写成 is，针对的是 #378。改写后的片段是 `is an iterable of lists`，`simpleMatch` 仍然没有质量词。这一组父边界是 IndexError，记录里没有结构化实参。空批次是否算“iterable of lists”，文档没有写成返回值谓词。

## 缺口怎么归类

| 缺口 | 落在哪些组 | 对计分协议意味着什么 |
| --- | --- | --- |
| 风格句式 | 12 组的 Args、Returns 或首句都在动词、标点、None 与 null、should、数量词位置上停下 | 句子形状和 `simpleMatch` 不一致 |
| 谓词族没有落到这次调用 | #273 的复数公式没有绑到打印出的 1.0；#356 只写了字符的角色 | 族可以命名，文本里没有这次调用的实例 |
| 父文本写成缺陷形式 | #216 的两个复数槽都是 bilhão | 执行父文本会放过父版本 |
| 隐含视觉或格式约定 | #273、#254、#250、#218、#356、#3718 | 单位、小数、进位、字形、标题背景没有写成谓词 |
| 异常与返回值 | #378、#355、#345、#1088、#1082 | 状态基线已经分开；返回值谓词在抛错时没有返回值可用 |

#216 同时有一条类型式的 Returns，它的主类是父文本写成缺陷形式。#273 同时有未绑定的复数公式，它的主类仍是隐含格式：公式没有写成这次返回值的谓词。

## 决定

保留需要至少一组盲组的存档句子写出修复边界的完整返回值，或写出一个冻结 `holds` 能分开两侧边界、且两侧普通输入都通过的质量词。这样的句子是 0 句。

收窄需要三种局部改写里至少一种在盲组上分开父边界和修复边界。三种走查都没有。

因此决定是**停止**。限制登记为：这 7 组里，父文档没有把记录到的那个差异写成可检查谓词。#216 更进一步，父译文写的是父版本自己的表面形式。本轮不补写文档，不把粗字段换成更细的字段，不加案例，也不另开计分协议。

冻结研究原来的收窄结论保持原样，不重算。相对 `status_only`、`jdoctor_pattern` 和 `bind` 没有新的逐组增减，因为没有新的方法分数。引用冻结结果只为核对：那一轮 `bind` 和 `jdoctor_pattern` 是 12 组无检查，`status_only` 是 5/12。本轮复核翻译器，12 组仍是 0 条翻译。

若要重启，新证据得是某一盲组的父文本里出现了这次修复边界的返回值，或出现了能用冻结 `holds` 分开两侧且不误伤普通输入的质量词。类型段、参数角色、另一条调用的示例，以及把缺陷形式写成唯一译文，都不算这种证据。

成本是一次本地读取。没有模型调用，没有库的重新执行。

## 复现

```bash
python3 research/release_drift_20261126/catalog_gap_analysis/test_catalog_gap.py
python3 research/release_drift_20261126/catalog_gap_analysis/analyze.py
```

第二行在 `protocol.md` 或 `analyze.py` 有未提交改动时拒绝写结果。分类和走查在 `results/analysis.json`。
