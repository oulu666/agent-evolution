# 冻结前校准接线 · 另一臂补记

**2026-11-26 登记。** 本文件在新的校准试跑之前写入。它不改写 [protocol.md](protocol.md)、[PROTOCOL_ADDENDUM_ZH.md](PROTOCOL_ADDENDUM_ZH.md)、[REPORT_ZH.md](REPORT_ZH.md) 或 [GAPS_FOLLOWUP_ZH.md](GAPS_FOLLOWUP_ZH.md)。那四份仍是较早的协议或回执。11 月 30 日清单在 [OVERNIGHT_20261127_ZH.md](../OVERNIGHT_20261127_ZH.md) 和上级 [protocol.md](../protocol.md) 里保持未勾选。正式方法没有修改，也没有冻结。

这仍是校准，不是正式结果。试跑里的数字不能替换正式分母，也不能用来在看见密封结局之后修改已经预注册的正式方法。不给方法排名。每个实物的 `signoff_ready` 保持为假。

## 要处理的六项

只处理上一份缺口回执里仍然可以诚实关闭的事项。每一项只许记为关闭、部分关闭或仍然开放。做不到就保持开放。

1. 用同一预算脚本执行六个公开夹具的另一臂（发布案例的 `after`，slugify 的 `rev`）。
2. Unidecode 的版本必须来自公开夹具里的精确钉扎；夹具没有写明时，解析保持为环境缺口。
3. 结局先验和预期任务损失最小的静态序列。开发预排 `[2]` 仍然不得使用。
4. 案例行的处置和预期任务损失。证据不够时损失留空。
5. CPython 3.11 针脚。只允许仓库外、可逆、写进本文件的安装。
6. 周历年字符串、时长档案标量和跨字段不变量。没有既有结构就保持开放，不许新包一层。

## 明确不做

- 不开始正式四项配对主比较，不比较同一案例的 before 与 after、parent 与 rev 来计分，不给方法排名。
- 不打开密封的 pandas、Pillow、SciPy 标签、含 `sealed` 的文件、`environment_receipts`，不运行 `preflight.py`，不读取 `frame.json`。
- 不勾选过夜决定或上级协议里的 11 月 30 日清单，不修改那两个文件，不修改 `freeze_guards.py`。
- 不改写其他已归档研究目录，不重启已暂停的 ESWA 原型、主动验证或已停止的抽取线，不放宽纳入规则。
- 不把开发实验各臂的行、请求、结局或损失抄进回执，不读取 `dev_parallel/results/summary.json`。`results` 里的 `outcome` 和 `loss` 是开发臂的结果，不是本文件的先验。
- 不把 `detected_inputs` 重算成分数，不把存档或现场返回与 `expected` 的差异计成案例分数。
- 不把 `preplanned` 的值 `[2]` 当成规范化请求标识或静态序列。
- 不替换 python-slugify-3，不改用另一个案例或另一个 python-slugify 发行版。
- 不把 CPython 3.12 写成 3.11。不把解释器构建提交进仓库。
- 不覆盖 `results/calibration_receipt.json`、`results/calibration_log.txt`、`results/gaps_followup_receipt.json`、`results/gaps_followup_log.txt`。

## 数据、入口、预算和主指标

数据只使用 [protocol.md](protocol.md) 已经点名的公开夹具，以及本目录 `packs/` 里已经由那些夹具生成的六份资料包。六个案例仍是 `xlsx-column`、`xlsx-duration`、`babel-week`、`python-slugify-1`、`python-slugify-2`、`python-slugify-3`。没有训练划分，也没有留出划分。

before 与 parent 已经在 [results/gaps_followup_receipt.json](results/gaps_followup_receipt.json) 里执行过。本试跑不重跑那一臂。另一臂是资料包里的对手方：XlsxWriter 列 3.3.1、时长 1.3.8、Babel 2.17.0，以及三个 slugify 资料包写出的 `rev` 提交。版本以资料包为准。

预算仍是共享首请求不计次，此后在线调用至多三次。失败调用占一次。第四次在分派前拦截。脚本顺序不变：共享首请求使用输入 0；`probe` 使用输入 1；`verification` 使用未登记操作并占用一次；`reset` 再次执行输入 0；`restore` 在进入适配器之前被拦截。离线 Schema、离线备用和初态快照复位不在这三次里，本试跑不把它们重做成新结论。

主指标不是损失分数。主指标是上面六项各自的关闭、部分关闭或仍然开放，以及版本和证据。点质量 `(1,0,0)`、`(0,1,0)`、`(0,0,1)` 上的 0、1、5 仍只是算术核对，并且标明 `calibration`。

实现完成后、试跑之前，工作区必须干净。本文件的提交必须是试跑当时 `HEAD` 的祖先。试跑入口是：

```
python3 research/release_drift_20261126/freeze_prep_20261130/test_after_arm.py
python3 research/release_drift_20261126/freeze_prep_20261130/run_after_arm.py
```

`test_followup.py`、`test_harness.py` 与 `test_freeze_guards.py` 仍须通过。单元测试不读取公开语料和密封语料。试跑只写入：

- `results/after_arm_receipt.json`
- `results/after_arm_log.txt`

试跑之后另写 `AFTER_ARM_ZH.md`。不根据试跑结果修改本文件。

## 1. 另一臂

适配器只在 `calibration_call.py` 里接触这三个库。请求里的 `arm` 必须是该资料包 `arms` 的键。发布案例允许 `before` 和 `after`，slugify 允许 `parent` 和 `rev`。其他名字在下载或检出之前拒绝。轮子仍按资料包的 URL 下载并核对 SHA-256。slugify 只检出资料包里的那个提交；提交不在公开远程仓库里时记下异常，不另找提交。

现场调用的版本必须记两处：资料包写出的版本或完整提交，以及库自己报告的版本。slugify 还用检出目录的 `git rev-parse HEAD` 核对。两处不一致时记下不一致，不得把该调用说成资料包命名的那一版。返回值可以记入回执作为调用证据，`compared_to_expected` 保持为假，不计通过或失败分数。

某一臂下载、检出或导入失败时，记下异常并继续其余案例。不得用另一个案例或另一个发行版顶替。python-slugify-3 的 rev 如果也失败，失败本身就是记录，不换成别的项目。

关闭：六个另一臂都走完预算脚本，成功调用进入资料包命名的版本，失败调用占用额度，第四次没有进入适配器。部分关闭：发布库做到了，slugify 的 rev 已分派但因检出失败、导入错误或下面的依赖缺口而没有库行为。开放：另一臂没有分派，或分派的不是资料包里的那一臂。

## 2. Unidecode

精确钉扎只承认公开夹具文本里的 `Unidecode==` 加数字版本，大小写不敏感，版本至少有两段数字。搜索范围只包括六份资料包和 [protocol.md](protocol.md) 的允许名单。叙述报告、本文件和上一份回执不在搜索范围内，避免把已经写过的 “1.4.0” 误当成夹具钉扎。

`Unidecode>=0.04.16` 这类范围不是钉扎。检出目录里的 `setup.py`、`setup.cfg` 或 `pyproject.toml` 可以记成库声明，但库声明不是公开夹具。夹具没有精确钉扎时：不安装 Unidecode，不往仓库写入依赖钉扎，回执把解析记为仍然开放的环境缺口。此时 slugify 的现场返回即使存在，也不是签收质量回执，`signoff_quality_receipt` 为假。

若允许的搜索范围内恰好有一个精确版本，才安装那个版本并记下安装命令。多于一个互不相同的精确版本时不挑选，缺口保持开放。

关闭：夹具写明了一个精确版本，试跑安装并记录的就是它。仍然开放：夹具没有精确版本，或版本互相冲突。不得把未钉扎的已安装版本写成关闭。

## 3. 结局先验

方向判别要求从长度不超过 3 的合法序列里，按同一注册先验最小化 `expected_task_loss`。损失权重仍是正确 0、暂缓 1、错误 5。平局先取预期在线调用更少的序列，再按规范化请求标识组成的序列标识排序。两臂设置相同，深度为整数 3，不剪枝。

本文件承认的先验只有一种形状，并且必须已经出现在资料包或允许名单 JSON 的顶层键 `outcome_prior` 上：

- `applies_to` 等于 `every-legal-sequence`。
- `masses` 恰好含 `correct`、`deferred`、`wrong`，三个数非负且和为 1。

该对象表示每一条合法序列共用这一组质量。此时才可以对序列调用 `expected_task_loss`。质量相同的序列按上面的平局规则选择。开发结果里的行级 `outcome` 和 `loss` 不是这个对象。`expected` 是库输出，不是这三元质量。`preplanned` 的 `[2]` 不是规范化请求标识。这三处都不得转写成先验。

没有该对象时：不构造质量，不对任何序列调用 `expected_task_loss`，`sequence_selected` 为假，`development_preplanned_used` 为假。选择器可以在单元测试的内联对象上运行，公共试跑不得喂入内联对象。

关闭：公共夹具里存在上述对象，并且选出的序列就是该先验下的最小损失序列，核对通过。部分关闭：深度 3 的枚举和 `check_search_parity` 仍然通过，开发键被拒绝，但因为没有承认的先验而没有选出序列。开放：开发键被拿来使用，或在没有上述对象时选出了序列。

## 4. 案例行

一行只有同时满足下面四条才计算 `expected_task_loss`：

- before 或 parent 在上一份回执里已经走完预算脚本，且本试跑已经把 after 或 rev 分派进同一个脚本。
- 表达式表非空，而且表内表达式仍只使用已有的整数取值、序列长度和非零整数倍。
- 裁决来自已登记的契约规则，取值只许是违约、满足或未定。空规则表不是这样的裁决来源。
- 该行另有第 3 节的三元质量。

缺任何一条，该行的 `expected_task_loss` 保持为 `null`。不得用现场返回是否等于 `expected` 来填裁决，也不得把未定猜成暂缓或错误。

空规则表仍按方向判别保留未定，动作为交付当前。这不是一行分数。凡是写出来的 0、1、5，标签都是 `calibration`，`formal_score` 为假，`case_rows_used` 只有在上一节的四条都成立时才为真。

关闭：六行都有充分证据并算出了标明校准的预期损失。部分关闭：预算脚本已经作用到行上，但损失因证据不足而留空。开放：行仍不进入处置。

## 5. CPython 3.11

方向判别把随机对照钉在 CPython 3.11，种子 `20261126`，候选使用规范化顺序，每任务独立用同一种子初始化，运行一次。本试跑不运行那次正式随机对照，也不开始四项配对比较。

允许的安装只有这一条，并且必须在仓库之外：

1. 若没有 `uv`，用 `https://astral.sh/uv/install.sh` 把 `uv` 装进用户主目录。设置 `UV_NO_MODIFY_PATH=1`。不把安装程序提交进仓库。
2. 执行 `uv python install 3.11`。解释器留在 uv 的用户 Python 目录。
3. 用 `uv python find 3.11` 取得绝对路径。该路径不得位于本仓库内。
4. 不执行 `apt-get install python3.11`，不把 `python3.11` 放到默认 `PATH` 上。若安装器留下了 PATH 上的同名可执行文件，只去掉那个链接，保留 uv 目录里的解释器。
5. 逆操作是 `uv python uninstall 3.11`。回执写下实际使用的命令和是否成功。

针脚检查只用第 3 步的那个解释器执行。检查进程必须自报 `CPython` 且 `version_info` 的前两段是 `(3, 11)`，并写下 `sys.executable` 与 `sys.version`。它可以为六个案例分别构造 `random.Random(20261126)`，但不抽取请求，不调用 XlsxWriter、Babel 或 slugify。父进程即使是 3.12，也不满足针脚。

检查成功时，`cpython_3_11_pin` 为 `satisfied`，并记下路径和版本。安装或版本检查失败时，针脚为 `unset`。两种情况下 `random_arm_comparison_ran` 都为假，`formal_paired_comparison_started` 都为假。

关闭：检查进程是 CPython 3.11，回执有它的绝对路径和版本，并且没有把 3.12 写成满足针脚。仍然开放：没有这样的进程。部分关闭不使用；路径或版本缺失就保持未设置。

## 6. 字段与不变量

不新增跨字段不变量。不把字符串或标量包进新的字典或列表。

周历年捕获和档案返回若仍是字符串，保持不可寻址。时长档案 `actual` 若仍是标量，保持不可寻址，也不把开发捕获的二元列表回写成该标量。slugify 只沿用上一份回执已经能读的现成键。试跑可以再次调用既有的寻址函数，确认类型没有变化；确认本身不关闭本项。

关闭：三类都能在不新增结构的前提下寻址，且不变量来自夹具里已经写下的联动关系。部分关闭：只有既有字典可以寻址，字符串和标量仍开放且未被包裹。开放：出现了新的包裹，或把没有联动条款的字段写成了不变量。

## 停止

一个案例失败时记下异常并继续。不改用密封样本，不另找案例，不根据试跑修改本文件的臂、钉扎、先验形状、空表规则或额度。不勾选正式清单，不宣布方法已经冻结，不给方法排名。
