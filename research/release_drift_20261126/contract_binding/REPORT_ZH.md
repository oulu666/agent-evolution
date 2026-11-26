# 公开契约绑定的可行性

**2026 年 11 月 27 日。** 决定是**收窄**，理由是预登记的 `catalog_gap`。候选绑定和 Jdoctor 模式转写在全部分母上的检出都是 0。这不是方法排名，也不是进入论文规模评测的证据。下一份协议如果要写，只能先改一种表示并重新冻结；本拉取请求不改模式、不加案例、不重算。

冻结提交是 `22a843467bfdc9d7b9663c0582f05f37cecd3a77`。`protocol.md` 的 SHA-256 是 `4ec1f794fcc36155c1f9e2842f932d27467e251e8b27cd72e90cbafca97e5cba`。计分时这五份冻结文件没有未提交改动。

## 用了哪些公开案例

分母是独立队列里已有回放的 12 组：humanize #273、#254、#250、#218、#216，PrettyTable #378、#356、#355、#345，more-itertools #1088、#1082，Rich #3718。humanize #240 与 #250 同组，单独记分，不进入分母。

校准层不进入分母：XlsxWriter 列可见性、XlsxWriter 时长、Babel 周历年，以及归档的 attrs #1428。attrs 只读了 `boundary_gap/results/summary.json` 的 `observations`。父版 `docs/init.rst` 返回 404，文本用的是案例表里预写的回退页 [attrs 21.4.0 初始化文档](https://www.attrs.org/en/21.4.0/init.html)。Click、transitions、Blinker、pluggy 的目录含密封帧，没有打开。正式封存的 pandas、Pillow、SciPy 没有打开。已关闭的主动提问、列隐藏修复和边界缺口结果都没有改写。

契约文本只来自父提交或父发行标签上列出的文件。记录里的 `expected` 只进入单独的 `published_observer`，不进入抽取。

## 实际跑了什么

| 方法 | 是否执行 | 分母结果 |
| --- | --- | --- |
| `bind` | 执行 | 检出 0，方向相反 0，误报 0，12 组都是无检查 |
| `jdoctor_pattern` | 执行。只转写 Toradocu 3.0 `simpleMatch` 的谓词，并接到完整返回值 | 与 `bind` 相同，检出 0 |
| `status_only` | 执行 | 检出 5/12。五次都是边界调用抛异常，修复版不再抛 |
| `agora_restricted` | 执行。只从父版本已有行学习 | 检出 0。#216 与 #3718 方向相反 |
| Jdoctor 原程序 | 不运行 | Java 源码进、Java 表达式出。上表不是原程序的成绩 |
| SPARK 形式契约生成 | 不运行 | 这些案例没有 SPARK/Ada 契约 |
| Gay 等 2015 的变异体预言选择 | 不运行 | 没有变异体；期望值没有交给抽取器 |
| AGORA+ 原程序、SpecFuzzer | 不运行 | 分别面向 REST 和 Java 轨迹 |
| Hypothesis 与已冻结合成器 | 不运行 | 会生成新输入，或重启已暂停的 ESWA 原型 |

五个状态检出是 PrettyTable #378、#355、#345 和 more-itertools #1088、#1082。其余七组调用成功，状态检查双侧通过。

## 文档有没有绑上

父版本文档都取到了，符号也都找到了。两条翻译路径都没有产生可求值检查。

九个分母组被机械规则记为 `catalog_gap`，项目是 humanize、PrettyTable、Rich。这些文档里有 Args、Returns 或 Arguments 段，模式表却没有译出谓词。例如 humanize `intword` 的返回段是“str: Friendly text representation as a string, unless the value passed could not be coaxed into an int.” PrettyTable `add_rows` 写的是 “should be an iterable of lists”。冻结改写只把 must / will be 收成 is，不处理 should。XlsxWriter `set_column` 的返回段是 “0: Success. -1: Column number is out of worksheet bounds.” 这是行为句子，同样不在 `simpleMatch` 的 “is positive / returns true” 形式上。

另外三组是 `doctest_only`：humanize #254、more-itertools #1088 和 #1082。`exactly_n` 的首句是 “Return ``True`` if exactly ``n`` items in the iterable are ``True``”。反引号隔开了 return 和 true，模式没有译出。文档示例按冻结规则只计数、不套到别的输入上。#250 的示例给出过 `'3.0 MB'`，记录到的边界输出是 `'1.0 Byte'`，二者不是同一次调用。

因此，`catalog_gap` 里混有两类文本：只有类型说明的 Args 段，以及模式表确实读不懂的行为句。规则在运行前已经把“有标签段且零翻译”定成收窄条件，这里照该规则执行，不在事后把类型段改判成文档沉默。

## 已有期望下的观察差距

`published_observer` 使用回放里已经写好的期望，用来核对台账里的现象，不算抽取成绩。12 组的完整值全部形成父边界失败、修复边界通过。状态和粗字段只在上述 5 个异常组上检出，另外 7 组粗字段双侧通过、完整值检出。这 7 组是 humanize 五个分母组和 PrettyTable #356、Rich #3718。

#250 的粗字段在父边界和修复边界都是 1，完整字符串分别是 `1.0 Byte` 和 `1 Byte`。#356 的行内容都是 X、Y，分隔符分别是 `└` 和 `├`。#3718 的标题文字都是 `title`，标题背景在父边界是空、修复边界是 `blue`。attrs 的最终字段在显式 200 上两端都是 200，回调分别是 `[100]` 和 `[200]`。这些差距都靠已有期望才显现。本次从父版本文档绑出的检查是 0 条，所以完整输出并没有被一个新抽出的契约用上。`full_hit_coarse_miss` 为 0。

## 轨迹不变量

父版本上恒成立的不变量不能把父版本记成违约。它只会在修复版离开该常数时告警，分类是方向相反。分母内出现两次：

- humanize #216：父边界 `2.0 bilhão` 与普通输入 `1.0 milhão` 共享骨架，修复边界 `2.0 bilhões` 不再共享。不变量把修复版当成偏离。
- Rich #3718：父版本两次的背景都是空，包括已经出错的蓝色面板。不变量把“背景为空”当成规律，修复版的 `blue` 触发告警。

attrs 校准同样如此：父版本两次回调都是 `[100]`，修复版显式调用的 `[200]` 被当成偏离。三次都不是检出。

## 校准层

| 案例 | 状态 | 粗观察相对已有期望 | 完整值相对已有期望 | 文档翻译 |
| --- | --- | --- | --- | --- |
| XlsxWriter 列 | 双侧通过 | 检出 | 检出 | 无检查，`catalog_gap` |
| XlsxWriter 时长 | 双侧通过 | 检出 | 检出 | 无检查，`catalog_gap` |
| Babel 周历年 | 双侧通过 | 检出 | 检出 | 无检查，`catalog_gap` |
| attrs #1428 | 双侧通过 | 双侧通过 | 检出 | 无检查，`doctest_only` |
| humanize #240 | 双侧通过 | 双侧通过 | 检出 | 与 #250 相同，不进分母 |

列可见性的差异落在布尔字段上。冻结规则把字典里的布尔字段当作粗观察，所以已有期望下的粗观察已经能看见它。时长和周历年的记录值本身是数或字符串，粗观察与完整值是同一个值，状态检查看不见，父版本文档也没有译出对应谓词。attrs 复现了“最终字段放行、回调能分开”。这些结果都不进入保留条件。

## 决定

保留需要 `bind` 在至少两个项目上给出状态基线没有的检出，且其中至少一次不是 Jdoctor 模式转写的检出，同时没有方向相反和误报。实际检出为 0，保留不成立。

没有方向相反，也没有误报，所以不是因不安全而停止。没有被基线覆盖的检出。`catalog_gap` 分布在 humanize、PrettyTable、Rich 三个项目，达到预登记的两个项目门槛。机械决定是**收窄**。

收窄只表示：若还要做下一轮，先把“类型段”和“行为句没有落入谓词表”分开，再冻结一种表示。候选包括带反引号的 `Return True if`，以及返回码句子。文档示例仍然只在调用字面量与记录输入相同的时候才能执行。本轮不实现这些表示，也不用它们重算。停止条件里的“不要为了正结果追加案例”仍然有效。

主动提问、固定预排和列隐藏修复的已有结论不变。正式四项变化的分母、调用额度和密封标签都没有进入本轮。

## 复现

```bash
python3 research/release_drift_20261126/contract_binding/test_contract_binding.py
python3 research/release_drift_20261126/contract_binding/run.py
```

第二行在冻结文件有未提交改动时拒绝计分。父版本文档缓存在 `docs/`，逐项分类和观察在 `results/summary.json`。运行只读已有回放和归档观察，不重新执行库，不调用模型。
