# P14 Calendar 协议与数据冻结交接

完成：2026-11-19 10:59（北京时间，Asia/Shanghai）。本轮是协议/数据冻结，不是方法训练实验。

## 结论

- 在用户笔记本 WSL Ubuntu 本地 fac_tinyagent checkout 完成，未使用 CloudAgent、未 clone、未 git add/commit/push。
- 1392 题：train/dev/test = 696/348/348；29 个最小可行分层格，每格 24/12/12，且各格各拆分均有 3 个模板、多个不同日期/实体。
- CPU 全量验收 PASS，随后相同命令再运行 PASS，manifest 不变。1392 题均通过原日历工具 schema/执行/observation/标注核对，并通过从原始夹具独立计算答案的第二个 oracle。
- train/dev/test 题干、真实模板文本、模板 ID、日期、月份、事件 ID、标题、地点、参与者两两交叉均为 0；三个 split 使用独立夹具。
- 原有 517 个受保护文件（Python/根报告及历史 data_ext_p* JSON/JSONL/SQLite）前后 SHA256 不变。未修改 e3_train.py、旧 P4–P13 数据/报告/运行文件、旧冻结夹具、.venv 或 conda。没有对所有旧 runs 权重逐一哈希；不夸大为整台电脑审计。
- GPU 只执行只读进程查询，验收前后 compute 进程均为空；无模型、无 tokenizer、无 GPU 训练或推理。

## 协议要点

详见 `P14_EVAL_PROTOCOL_20261119_ZH.md`。主协议保持 B1 strict Joint = tool & args & execution & final，调用 core(tool&args) 与 final 分开，逐阶段逐技能同时报告旧技能保持、新技能获取、正确→错误和错误→正确。未学会的能力缺口（例如 filter_cmp_top）不能称遗忘。

废止仅4条开发探针判掌握、以及必须若干工具调用退化才继续的方法晋级门槛；小测试只检工程正确性。本轮只做数据/CPU逻辑，没有梯度/模型状态恢复测试。若完整合理多种子等预算对照仍无优势，接受负面结论；不得为正结果改题。P11 仍为基线、P13 仍为机制证据。

## 核对历史现象

P11 实际 dev 的 cal.count_date=4；8 条地点 Replay 候选逐题执行后，全部为2事件/1不同地点，见 `runs_ext_p14_eval_protocol/historical_audit.json`。P12 原码明确 day_as_month 错误：完整日期传 calendar_count(month=...)；正确的按日计数为 calendar_list(date=...)+length。P13 只读核对历史独立报告，core 无退化但 Joint 配对损失4/4/2；没有重新跑历史模型，亦不宣称 MIR 有效。

## 覆盖矩阵（不是模型成绩）

|分层|train|dev|test|
|---|---:|---:|---:|
|日期计数表述: day_month_contrast|24|12|12|
|日期计数表述: literal_count|24|12|12|
|日期计数表述: no_count_question|24|12|12|
|日期计数表述: synonym_total|24|12|12|
|不同地点数: 0|24|12|12|
|不同地点数: 1|48|24|24|
|不同地点数: 2|120|60|60|
|不同地点数: 3plus|288|144|144|
|重复程度: all|24|12|12|
|重复程度: none|240|120|120|
|重复程度: partial|216|108|108|
|地点输入顺序: constant|48|24|24|
|地点输入顺序: not_applicable|24|12|12|
|地点输入顺序: random|120|60|60|
|地点输入顺序: reverse|144|72|72|
|地点输入顺序: sorted|144|72|72|
|字段提取: id|24|12|12|
|字段提取: location|24|12|12|
|字段提取: start|24|12|12|
|字段提取: title|24|12|12|

整月计数对照另有24/12/12题。地点3plus包含3和4个不同地点。去重none含空日；空日不涉及非平凡排序，常量和不可行格不冒充排序覆盖。

### 每个最小可行格

|case|train|dev|test|
|---|---:|---:|---:|
|count_day_month_contrast|24|12|12|
|count_literal_count|24|12|12|
|count_no_count_question|24|12|12|
|count_synonym_total|24|12|12|
|empty|24|12|12|
|extract_id|24|12|12|
|extract_location|24|12|12|
|extract_start|24|12|12|
|extract_title|24|12|12|
|month_contrast|24|12|12|
|one_repeated|24|12|12|
|one_single|24|12|12|
|u2_none_reverse|24|12|12|
|u2_none_sorted|24|12|12|
|u2_partial_random|24|12|12|
|u2_partial_reverse|24|12|12|
|u2_partial_sorted|24|12|12|
|u3_none_random|24|12|12|
|u3_none_reverse|24|12|12|
|u3_none_sorted|24|12|12|
|u3_partial_random|24|12|12|
|u3_partial_reverse|24|12|12|
|u3_partial_sorted|24|12|12|
|u4_none_random|24|12|12|
|u4_none_reverse|24|12|12|
|u4_none_sorted|24|12|12|
|u4_partial_random|24|12|12|
|u4_partial_reverse|24|12|12|
|u4_partial_sorted|24|12|12|

## 文件与执行入口

项目 Windows 根目录：`C:\Users\Egret\Desktop\oulu\Agent Self-Evolution\fac_tinyagent`。WSL：`/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent`。

- `P14_EVAL_PROTOCOL_20261119_ZH.md`：冻结协议。
- `data_ext_p14_eval_protocol/{train,dev,test}/rows.jsonl`：逐题 gold、消息、分层、实体和夹具路径。
- `data_ext_p14_eval_protocol/fixtures/{train,dev,test}.json`：独立专用夹具，不动旧夹具。
- `data_ext_p14_eval_protocol/replay_candidates.json`：仅索引全部696条 train 经验，包含多地点/去重/随机与逆序排序，禁止 dev/test。
- `data_ext_p14_eval_protocol/{template_bank,coverage_expected,continual_factors}.json`：真实模板、覆盖矩阵、6个顺序及新旧/干扰组装规范。
- `data_ext_p14_eval_protocol/p14_cpu_freeze.py`：确定性生成+验收；已存在文件不同即拒绝覆盖。
- `data_ext_p14_eval_protocol/{manifest.json,manifest.sha256}`：冻结内容及自校验。
- `runs_ext_p14_eval_protocol/{cpu_acceptance,b1_metric_truth_table,historical_audit,protected_sources_before,protected_sources_after}.json`：CPU证据。
- `runs_ext_p14_eval_protocol/{freeze_pass_01,freeze_pass_02}.log`：两次成功执行日志。

在 WSL 项目根目录重现：

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' .venv/bin/python -B data_ext_p14_eval_protocol/p14_cpu_freeze.py
```

本次两次成功运行：2026-11-19 10:58:57–10:59:06、10:59:17–10:59:24（均北京时间）；耗时约9.6秒和7.0秒，均CPU数据检查，不是训练或推理计时。B1 全16种布尔组合已检查，包含工具/参数全对但最终答案错时 Joint 必须失败。

## 冻结 hash

manifest SHA256：`944b8e3d9b254e928559a55623aef3c41060234a8b04f010b9f1919f0f0b3881`。

|文件|SHA256|
|---|---|
|`P14_EVAL_PROTOCOL_20261119_ZH.md`|`b796f25c2452467f4933fc6ef4e8aedad1436f52fd3c361adf385f801c1ba55f`|
|`data_ext_p14_eval_protocol/continual_factors.json`|`af9d36b7896806a46b5a1fbda8da2f16ef67a40e267a7362d61308783843f7ea`|
|`data_ext_p14_eval_protocol/coverage_expected.json`|`7c7b56274e991870a0e56b3243a8e13f5e78add85cd405c8d835e2670ce5b886`|
|`data_ext_p14_eval_protocol/dev/rows.jsonl`|`f4d910db5a23aa729e0c3033f738f0651043477d0acbeb8e6d349f04f8cad3cb`|
|`data_ext_p14_eval_protocol/fixtures/dev.json`|`4215882395d67b8389f7ef07b802e02b9ae156858c19829a736887585d0dc871`|
|`data_ext_p14_eval_protocol/fixtures/test.json`|`748e7778f203f6493a9d81912661b06aca73d2c4965b762181f72ea7b57eaa8e`|
|`data_ext_p14_eval_protocol/fixtures/train.json`|`b442fe71d7bc3004099408ba248249b93f5cc7ae505ae4b04c2404bd32862ef2`|
|`data_ext_p14_eval_protocol/p14_cpu_freeze.py`|`fff29b1ccff395eb68f6f1fdc2b7e724efa66e15846f53fa8c2f04f931af2b78`|
|`data_ext_p14_eval_protocol/replay_candidates.json`|`b014945e2712bdee9091527b91b877edffe2ecfaf9b3c8821b4efb664ab0c72e`|
|`data_ext_p14_eval_protocol/source_reference.zip`|`533dfa0f8b307bfb149fa986ffbd32ffe2980bcad519b3dca28f8e7b6cd05b4a`|
|`data_ext_p14_eval_protocol/template_bank.json`|`10f852fd6285a31eff8431cc1dff7108b2c9025e2326295d767962eb1765116b`|
|`data_ext_p14_eval_protocol/test/rows.jsonl`|`7600738bbf0cbe1d50eedc423286b27330af9c6ec12abc691ef024aa35276f87`|
|`data_ext_p14_eval_protocol/train/rows.jsonl`|`e6b55b256f9c79db783168dd9710639c98390d649ae43ce0f66e1b7370fdcf89`|

受保护旧文件列表 SHA256：`09501dc03eb92ad7c856c21860133dc4ee0863fc2c185f99f1815ad820623b7d`。完整517个路径及各自 hash 见 before/after 文件。

## 工程问题与明确限制

- 冻结成功前，CPU检查发现同月计数题干重复，改为每道月题使用独立月份后通过；随后发现旧 P11 calendar_extra 是 messages-only 精简行，审计适配后通过。失败日志/草稿保留在本轮 `runs_ext_p14_eval_protocol/draft_failure_01/` 与 `draft_failure_02/`，不混入正式冻结数据。只修工程构造/审计，不依据模型结果改题。
- 0个地点定义为空日；不包含非空事件缺失/null地点。time映射真实start字段，事件返回同时包含title/location/id/start/end；不虚构time工具参数。
- 不可行组合（如2个不同值且无重复的非单调排列、全部重复同时2+地点等）明示为结构不可能，未造假补满。
- 合成数据限定Calendar的count/list后处理，不覆盖search/free_slots/attendees和其他家族、真实世界复杂时区、多步链。
- test 是流程盲测，并非加密存储；本轮只程序验证gold，未看任何方法test成绩。后续开发不得据此test调方法/阈值。
- split年份/实体命名空间隔离属于受控holdout，不宣称现实OOD；未做tokenizer截断、可学性、统计功效、模型训练长度或8GB显存实测。各格dev/test=12是覆盖下限，不是功效保证。
- 现有evaluator接受单一calendar_path，后续必须按split传本轮独立夹具；本轮未改核心。初始git status只读调用挂起后已停止，未用git全盘状态冒充完整旧文件不变证据，依据为限定517文件hash和仅新增本轮路径的操作范围。

## 下一步（未启动，须用户批准）

先审阅该冻结包及局限；批准后再单独冻结多种子/阶段顺序/新旧组合/干扰装配、初始状态、回放input与supervised token双预算、训练时长、评价节点与完整对照/消融规则，再启动 Uniform / P11适配基线 / 新方法。六个顺序及低中高干扰现仅为规范与可组装标注，未运行任何持续学习序列。不得自动开训或自作主张设计全套新算法。
