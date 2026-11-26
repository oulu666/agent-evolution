# 冻结前校准接线

**2026-11-26 登记。** 今天仍在方法冻结窗口之前。正式窗口仍是 2026-11-30 至 12-02 冻结方法，12-03 至 12-07 做配对比较，12-08 至 12-10 揭盲。本文件与同一次提交中的接线代码在任何校准试跑之前写入。试跑产物不进入这次提交。

这是准备，不是正式结果。校准试跑里如果出现 0、1、5，那只是协议规定的三个点质量上的算术核对。它们不能替换正式分母，也不能用来在看见密封结局之后修改已经预注册的正式方法。这次试跑不读取密封结局。

## 范围

接线只问一件事：11 月 30 日要签收的实物，能不能在已经公开的校准夹具上被现有代码执行。现有代码指 `research/release_drift_20261126/freeze_guards.py` 里已经实现的预算、处置、预期任务损失、字段组重放和搜索设置核对，以及 `direction_gate.md` 里已经写明、但还没有对应实现的部分。缺实现就记缺口，不在试跑时补上。

公开校准库只使用这三个：XlsxWriter、Babel、python-slugify。XlsxWriter 用列可见性和时长两个已公开案例。Babel 用周历年。slugify 用合同合成门里已经公开的 `python-slugify-1`、`python-slugify-2`、`python-slugify-3`。

## 明确不做

- 不开始、也不模拟正式四项配对主比较。
- 不打开密封的 pandas、Pillow、SciPy 标签、含 `sealed` 的文件、`environment_receipts`，或正式静默漂移答案。不运行 `preflight.py`。不读取 `frame.json`。
- 不修改已归档研究目录，只允许按本文件点名的路径只读：`repair_gate`、`boundary_gap`、`contract_binding`、`catalog_gap_analysis`、`documented_predicate_binding`、`documented_api_extraction`、`dev_parallel`。本接线不读取前四个和两个 documented 目录。`dev_parallel` 只读下面点名的三个结果文件。
- 不改写 `OVERNIGHT_20261127_ZH.md`，不勾选那里或上级 `protocol.md` 的 11 月 30 日清单。
- 不重启已暂停的 ESWA 原型。不重开主动验证、目录收窄、把 XlsxWriter 列隐藏再写成新结论、`documented_predicate_binding`、`documented_api_extraction`。
- 不发明新算法，不新增候选机制，不放宽已有纳入规则。
- 不扩大三次额外在线调用的额度。复位、备用、恢复只要真的发起在线调用，就走同一个计数器。
- 不把开发实验各臂的结局重新汇总，不给方法排名。`dev_parallel` 的 `preplanned` 不是正式静态序列；试跑只记录这个键是否存在，不读取它的值。
- 不调用模型，不重新执行 XlsxWriter、Babel 或 slugify，不访问网络。

## 允许读取的公开夹具

路径相对于仓库根目录。读取函数拒绝这份名单以外的路径，也拒绝路径中含 `pandas`、`pillow`、`scipy`、`sealed` 或 `environment_receipts` 的文件。

- `runs_upstream_functional_20261124/paired_releases.json` 的 `column`、`duration`、`week`
- `research/release_drift_20261126/dev_parallel/results/column.json`
- `research/release_drift_20261126/dev_parallel/results/duration.json`
- `research/release_drift_20261126/dev_parallel/results/week.json`
- `runs_contract_synthesis_gate_20261125/sample.json` 里 `project` 为 `python-slugify` 的条目
- `runs_contract_synthesis_gate_20261125/tasks.json` 的 `python-slugify`
- `runs_contract_synthesis_gate_20261125/observations.json` 的三个 slugify 标识
- `runs_contract_synthesis_gate_20261125/checks.json` 的三个 slugify 标识
- `runs_contract_synthesis_gate_20261125/revealed_slugify.json`
- `runs_contract_synthesis_gate_20261125/python-slugify-1.txt`
- `runs_contract_synthesis_gate_20261125/python-slugify-2.txt`
- `runs_contract_synthesis_gate_20261125/python-slugify-3.txt`

`dev_parallel` 的三个结果文件只使用捕获的形状、版本、来源和轮子摘要，并查看 `results` 里是否存在 `static_info.preplanned` 这个键。不复制各臂的行、请求、结局或损失，不读取 `dev_parallel/results/summary.json`。`paired_releases.json` 里的 `detected_inputs` 不重算，也不把 `expected` 与 `actual` 的差异计成这次的分数。slugify 的载荷只用每个标识的 `parent` 一侧；不比较 `parent` 与 `rev`，因此不构成配对对照。回执可以记录条数，不记录通过条数。

## 五个实物

每个案例都给出 `ran` 或 `gap`，并另给 `signoff_ready`。`ran` 只表示现有函数被调用了。`signoff_ready` 在本文件中全部保持为假，因为下面写明的签收条件还没有齐。试跑不得把其中任何一项改成真。

### 共同资料包摘要装载器

`direction_gate.md` 要求两侧读取同一份带摘要的资料包。本文件不创建这份资料包。装载器只检查下列字段在允许的夹具里是完全缺失，还是仅仅散落在公开夹具中：

注册操作、用户要求、适用版本、旧 Schema、升级前公开文档、原回归输入、原回归预期、由这些材料导出的候选请求、判据、两侧共用的备用动作、材料版本、出处。

散落在公开夹具里的版本、出处、轮子或提交摘要、校准输入和存档 expected，记为 `public_fixture_only`。这不等于资料包字段已经齐备。校准输入不是正式任务的升级前回归集。存档 expected 不是 `freeze_guards.contract_value` 的已登记表达式。slugify 的 readme 文本只做摘要，不把它当成升级前公开文档。开发探针库即使存在，也不升格为候选请求。没有共同资料包文件时，装载器的状态是 `ran`，签收就绪为假。

### 静态序列

不枚举长度不超过三的请求序列，不按先验选择预期任务损失最小的序列，不调用开发实验里的预排函数。对每个案例用同一组不含案例内容的残缺设置调用 `check_search_parity`：深度为整数 3，评分上限为空，八个字符串设置为空串。它应当拒绝。拒绝被记录下来，状态仍是 `gap`。`preplanned` 的值不进入回执。

### 字段组反事实

正式入口只用 `replay_group`。不调用 `replay_choice`。

只承认两种已经在公开捕获里出现的形状，并且只取每个开发捕获第一个端点的第一条 initial 返回：

- 列：字典，`visible` 为布尔，`cell_text` 为字符串。
- 时长：长度为 2 的列表，第一项为浮点，第二项为字符串。

其他形状，包括周历年的字符串、slugify 的交付记录和导入错误，都记为 `gap`。不把字符串或未登记的字典包进新结构，也不临时挑选另一行来凑形状。

可行性也事先写死。列的返回在 `visible` 为布尔且 `cell_text` 为字符串时可接受。时长的返回在长度为 2、第一项为浮点、第二项为字符串时可接受。不另加耦合不变量。

占位驱动不是候选方法，也不参与归因。它读登记字段：字段仍等于记录值时返回 `{"role": "calibration-witness"}`，否则返回 `{"role": "calibration-witness-alt"}`。意图字符串固定为 `calibration-witness`。合法的单字段替换把该字段换成常量 `calibration-alt`。这个常量不是登记过的正常值。若它恰好等于原字段，记下 `no field changed`，不另选常量。

每个可寻址案例还做四次非法替换，预期被拒绝：重复路径、把字段换成类型不合法的值、替换值等于原值、以及两个都可行的字段一起替换。拒绝包括 `replay_group` 抛出的 `ValueError`、`KeyError`、`IndexError`，以及返回 `unauditable`。这次返回的 `effect` 只说明函数执行了，不能当作主动选问的证据。

`paired_releases.json` 里时长的 `actual` 若是标量，只记录它不可按字段寻址，不把开发捕获的二元列表回写成档案格式。

### 共同处置和预期任务损失

每个案例都调用一次 `expected_task_loss` 和 `disposition`。输入只有三个点质量 `(1, 0, 0)`、`(0, 1, 0)`、`(0, 0, 1)`，以及违约且已验证、违约且未验证、满足、未定这四种处置。预期损失是 0、1、5。处置依次是交付替代、暂缓、交付当前、交付当前。案例行不进入这两个函数。各案例重复出现同一组数字时，那是同一次算术核对，不是该库的分数。

不把存档结局翻译成 `violated`、`satisfied` 或 `undetermined`。这些案例没有登记的任务裁决，因此处置没有作用到案例上，签收就绪为假。

### 预算

`SharedBudget` 在共享首请求之后持有一个 `ExtraCalls`。首请求不进入这三次额度；首请求失败也不改记成一次额外调用。此后的在线目的 `probe`、`verification`、`replay`、`compare`、`reset`、`backup`、`restore`、`recovery` 共用这个计数器。未登记目的在扣次之前拒绝。第四次在线调用在分派前抛出 `BudgetExhausted`。分派函数抛出的异常仍占用一次，`completed` 为假。

试跑的分派函数不导入、不调用三个库。它只按请求中的下标返回已经存好的载荷的类型名。脚本顺序对每个案例相同：共享首请求使用下标 0；然后 `probe` 使用下标 1；`verification` 使用角色 `unavailable`，分派函数抛出 `OSError`；`reset` 使用下标 0；最后 `restore` 应被拦截且不再进入分派函数。下标越界同样抛出 `OSError` 并占用额度。slugify 没有第二条存档载荷时，仍按这个顺序执行，不另造载荷。

因此预算状态可以是 `ran`，同时签收就绪为假：正式工具适配器还没有接到这个计数器后面。离线 Schema、离线备用和初态快照复位的另计次数，本接线也没有实现。

## 摘要

试跑可以计算所读文件的 SHA-256。这些摘要只标识校准输入和本协议文本。它们不是 11 月 30 日要求的那次哈希冻结。那次冻结要覆盖可部署参数、具体任务注册表、每项合理预期和处置规则。这样的辅助函数现在不存在，试跑不新建一个来代替它。

## 停止

一个库或一个案例无法读完时，记下异常并继续其余案例。不改用密封样本，也不另找非正式案例补上。不根据试跑结果修改本文件的纳入范围、形状规则、占位符或额度。五个实物的签收就绪都保持为假。不勾选正式清单，不宣布方法已经冻结，不给方法排名。

## 入口

单元测试只使用内联小夹具，不读取上面的公开语料：

```
python3 research/release_drift_20261126/freeze_prep_20261130/test_harness.py
```

校准试跑在本文件所在提交之后执行：

```
python3 research/release_drift_20261126/freeze_prep_20261130/run.py
```

输出写到本目录的 `results/calibration_receipt.json` 和 `results/calibration_log.txt`。两份文件都标明 `calibration`。
