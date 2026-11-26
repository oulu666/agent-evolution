# 当前文档已经写明谓词时，抽取器能否给出可执行检查

**2026 年 11 月 26 日。** 决定是**分母不足**（`insufficient_denominator`）。有界筛选考察了 40 句义务，纳入 0 条。没有安装被测库来计分，没有方法分数，没有工具排名。

协议冻结提交是 `68580782313e84ffedd6a29572f8bd81366e3518`。`protocol.md` 的 SHA-256 是 `7f504b41b62644f22e0f4c7acacca169b5710ea3c8fb357459469254e5e21f5c`。案例提交、也是 `run.py` 写下决定时的提交，是 `d22f69ca568eeb79ade1170af68cf991170da86a`。

冻结之后、任何句子被考察之前，`selection.py` 有一次只修下载目录的提交 `e67f8616cf6eb6a305de795197b240499dc6cebf`。第一次运行没有把发行包写到磁盘，考察数是 0，那份空日志没有保留。模式、上限和库池没有改。下面的 40 句是这次修复之后的筛选。

## 本轮问的是什么

父文档谓词绑定（冻结 `f0805b3742c2c5c6de728e49dd1d849cda16567b`，压缩 `34940aa3169c20dbcc3e102f43094c42e6c47f5c`）停在分母不足：历史修复里，父文档已经写明且说的就是该次修复的句子，机械纳入只有 4，不到 6。那次检索不重开，连接器不放宽，样本不重算。attrs 和 hypothesis 也没有补进那次旧检索。

那次结果没有回答另一件事：文档里已经有可检查谓词时，现有抽取器能不能抽出一条可执行检查。本轮只问这个。它不是静默漂移检测，不是抓修复，不能替换 ISSRE 的 12 组，也不能替换正式封存的四项。

`jdoctor_pattern` 仍然只是 Toradocu 3.0 `simpleMatch` 的转写，不是 Jdoctor 原程序。Jdoctor 原程序、SPARK、Gay 等 2015、AGORA+、SpecFuzzer 和 Hypothesis 工具都没有运行，也不排名。hypothesis 这个库在库池里，但没有被调用。

## 筛选

库池、轮转、40 句或 12 条的上限、每个函数至多 2 条、每个库至多 4 条，都写在冻结协议里。实际停在 40 句，`stopped_because` 是 `40_examined`。版本是筛选当时 PyPI 报告的当前发行，sdist 摘要与页面一致。

候选只来自公开 `.py` 里的模块级函数，以及手写了 `__init__` 的公开类。方法、私有模块和列在协议里的装饰器只计数，不占这 40 个名额。两个输入只由冻结的三种句式给出：`return_if`、`return_and_raise`、`raise_if`。对不上这些句式，就不是纳入。

整份枚举共 880 句义务。其中 `return_if`、`return_and_raise`、`raise_if` 都是 0。含糊 2 句，其余 878 句是 `none`。优先级把含糊句和那三种句式排在前面，所以先停在 40 并没有把后面的可纳入句留在队列里。队列里剩下的 840 句，冻结模式同样对不上。

| 结果 | 数量 |
| --- | --- |
| 枚举到的义务句 | 880 |
| 考察 | 40 |
| 纳入 | 0 |
| 排除 | 40 |
| 没轮到的义务句 | 840 |

排除理由是 `inputs_not_determined_by_sentence` 38、`ambiguous_obligation` 2。考察覆盖了 16 个库。httpx 0.29.0、pytest 9.2.0、tomli 2.5.0 的公开包目录里没有模块级函数候选：httpx 跳过 22 个私有模块，pytest 1 个，tomli 3 个。它们的队列是空的，所以没有进入这 40 句。

方法被跳过的数量很大，例如 werkzeug 729、pydantic 651、hypothesis 595、rich 579、Jinja2 485。这是冻结规则，不是考察之后的剔除。

两句含糊都进了考察。attrs `attr.validators.not_` 的句子同时写了 `ValueError` 和 `TypeError`。hypothesis `hypothesis.internal.compat.get_type_hints` 同时写了 `TypeError` 和 `NameError`。冻结规则要求恰好一个异常类型，所以排除。

其余句子是义务句，但写不出协议表里的那一对输入。例如 arrow `arrow.util.next_weekday` 写的是 “Can be a value between 0 (Monday) and 6 (Sunday).” 表里没有 between，也没有把 can 收成无条件义务。pydantic `pydantic.color.parse_tuple` 写的是 “Raises: PydanticCustomError: If tuple is not valid.” 条件和异常不在冻结的 raise-if 形状里，not valid 也不是表里的质量词。PyYAML `yaml.emit` 写的是 “If stream is None, return the produced string instead.” 另一侧不是表里的字面量。逐句引文、路径和源文件 SHA-256 在 `screening.json`，源文件在 `docs/sources/`。

## 决定

计分需要至少 8 条独立义务，并且至少来自 3 个库。这里一条都没有。决定是 `insufficient_denominator`，理由是 `fewer_than_8_or_fewer_than_3_libraries`。`jdoctor_pattern`、`bind`、`sentence_grounded` 和人写天花板都没有在这个样本上跑。`ranking` 是 null。`results/summary.json` 的 `scored` 是 false，`counts` 是 null。

这个空缺不能解释成“抽取器失败”或“抽取器成功”，也不能解释成“这些库的文档里没有可检查句子”。考察到的 40 句已经是义务句。它们只是没有同时给出冻结表里的合法输入和违约输入。方法上的文档本轮根本没有进入候选。

没有安装被测库，没有调用。成本是 PyPI 的 sdist 下载，用来读 docstring。没有模型调用。

已归档的列隐藏修复、attrs 主动验证、12 组契约绑定、目录缺口分析和父文档谓词绑定都没有改写，也没有重算。正式四项封存分母、三次额外调用额度和 11 月 30 日方法冻结清单都没有提前启动。负结果留在 `screening.json`。

若要重启这一问，新证据得是另一份先冻结的筛选：在同样的考察上限之内，已经有至少 8 条独立义务、至少 3 个库，每条都能从钉死的源文件引用原句，并且合法输入和违约输入都由那一句决定。看完这 40 句再放宽句式或补进方法，不算这种证据。把历史修复重新检索一遍，也不算。

## 复现

```bash
python3 research/release_drift_20261126/documented_api_extraction/test_documented_api_extraction.py
python3 research/release_drift_20261126/documented_api_extraction/run.py
```

第二行只在案例表和 `docs/` 已经提交、且与 `screening.json` 的纳入集合一致时运行。纳入为 0 时它不安装、不调用抽取器，只写下分母不足。`selection.py` 在 `screening.json` 已存在时拒绝重跑，因此不会改写已经记下的排除。
