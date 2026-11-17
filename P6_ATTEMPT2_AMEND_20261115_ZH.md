# P6 attempt2 开跑前修复补充（不改变科学算法或实验设计）

2026-11-15，北京时间。用户明确批准“修复接口和步数问题后自动续跑P6”。修复只新增文件与独立attempt，旧P6计划/校准/失败adapter/日志、旧P4/P5、环境全部只读保留。

## 1. 已查清原因，不是只补一个键重试
首生产臂在e3_train组装summary时读取`quota_error_tokens_by_family`，P6规划器删除了该历史必需字段，导致KeyError。模型虽已保存，但无完整训练summary与正式评测，因此旧attempt不计完成，也不复用其adapter。
新增`p6_attempt2.adapt_plan`在真实trainer源码AST提取所有plan直接必需键并开跑前验证。本版本5项为items、actual_input_tokens、actual_tokens_by_family、quota_error_tokens_by_family、within_one_percent_of_budget。缺失quota项按legacy nominal family weights计算诊断残差；明确不是P6强制家族quota，也不参与梯度、选择或训练损失。其它科学字段及items逐项不变，9新计划保存源hash及items hash。

## 2. “日志22步”的真实含义
原训练循环每microstep写日志，完整8条窗口时更新一次。共享prefix已80 microsteps/10 optimizer steps；后缀80 Calendar+22 replay=102 microsteps，即12个完整8条窗口+尾部6条。最后一条microstep182的日志因此记录22；循环之后执行尾部6条梯度乘8/6的flush，再发生第23次总更新，随后保存adapter，最后组装summary。
所以单看最后一条microstep日志的22不能断言漏了一步。旧P4/P5同型分支也都是日志最后22、正式summary23、tail=6。原共享代码已含尾步，本次不凭空加样本、加更新、改计数或改超参，不改变跨轮训练预算协议。
新增只读逻辑等价的训练副本`p6_e3_train_attempt2.py`：跟随模型device以便CPU微型模型验收，并对真正执行的optimizer.step写独立凭据。每个新GPU分支必须实测prefix10+suffix13=23，尾步凭据1次、microstep182、tail6，且7494 tokens和全部target位置/after与原计划一致。若GradScaler实际跳过更新而计数仍增加，新审计会拒绝放行。

## 3. 已完成的低成本CPU端到端验收
不是仅模拟计划或语法检查：实际调用新runner.train→计划override→真实instrumented trainer→尾部flush→checkpoint及train_summary。模型替换成1参数CPU模型，optimizer为真实CPU SGD；不调用GPU，不把这些输出当实验结果。
结果：13次实际suffix optimizer.step；prefix10，总23；尾部6条被正确归一化。参数最终0.9974032044，与解析13步结果0.9974031177相符（误差<1e-6），能区分漏步、加步和尾部未归一化。
checkpoint→B1 evaluator接口→partial/complete finalize也已覆盖：该部分用明确标为synthetic_cpu_contract的评测桩，CPU专用输出目录，绝不混入正式P6指标。
证据：`runs_ext_p6_devplan_attempt2_cpu/acceptance.json`及其`cpu_contract_tests/`；退出rc=0。进程退出有第三方nanobind引用泄漏警告，但验收断言通过、无GPU训练或环境改动。
所有9份计划完整契约和预算会在新manifest中冻结后再开GPU。校准3种子hash、0 optimizer更新、参数不变及独立dev/holdout均复用原冻结版本，不重新花GPU校准。

## 4. 新attempt及端到端GPU放行
- 数据兼容副本：data_ext_p6_devplan_attempt2/plans与manifest.json。只补诊断契约元数据，items、分配、科学参数、正式holdout不变。
- 正式输出：runs_ext_p6_devplan_attempt2/。旧runs_ext_p6_devplan/失败现场不移动、不覆盖。
- 科学设计仍balanced_uniform/balanced_early/devgrad_uniform×20261108/09/10，共9分支。全部7494 replay input tokens、22 replay条目、23总optimizer steps。
- 首分支seed08 balanced_uniform是本来应跑的正式分支，不增加额外训练。它必须通过完整train_summary、13次实际suffix调用审计以及首套新holdout Database 24题B1接口，再写e2e_gate.json并放行其它8分支。放行只检查执行契约/题数/协议，不看正确率，不按holdout调参。
- 全部9分支从原E4 step80参数/优化器/RNG重新开始，绝不混用旧失败adapter。

## 5. 安全与命令
新attempt保留同等单GPU守卫、功耗>=60W、r5apex检测、三次检查失败停止；同时拒绝旧P6或新attempt任何STOP。没有清STOP。启动握手核对当前supervisor PID，避免旧child文件误报。
启动：`bash scripts/launch_p6_attempt2_20261115.sh`。
监测：runs_ext_p6_devplan_attempt2/logs/status.log、queue.log、runner.pid、gpu_child.pid；首关e2e_gate.json；每checkpoint optimizer_update_log.jsonl和optimizer_step_audit.json。
预计GPU首端到端关卡约4–8分钟，全部9分支约1.5–3小时；实际以日志更新。完成为QUEUE COMPLETE + END queue rc=0 + 9训练和45套B1齐全。STOP不得自动删除或恢复；不自动下一轮。
CPU收尾：`PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B -m fac_tinyagent.p6_attempt2 --phase finalize`。
中文结果/交接使用新文件EXT_REPORT_20261115_p6_attempt2_ZH.md、EXT_HANDOVER_20261115_p6_attempt2_ZH.md，不覆盖旧启动记录。
