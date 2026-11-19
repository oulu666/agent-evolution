# P14 v2 元数据修订与六项审查核实

2026-11-19，北京时间。保留P14 v1原封不动；v2不是新方法效果实验，也不扩充模板/改题求正结果。

## 核实结论

1. **不平衡属实**：train counts=120（日期96+月份24）、locations=480、fields=96；dev/test各60/240/48。不能以相同epoch直接比较。真实Qwen3-0.6B tokenizer和旧assistant-only mask已计数，完整新数据流与双token上限/更新账本见 `runs_ext_p15_stageaware_20261119/{new_streams,budget_ledger,diagnostic_budget_detail}.json`。同order×seed不同方法的新数据与更新次数完全一致；跨组输入token近似接近，但监督token明显不同，**不声称两者同时精确相等**，不将跨组差异解释为纯语义干扰。
2. **干扰标签只是eligible属实**：v1所有题的`interference_eligible=[low,medium,high]`不是测量结果。v2改成操作对资格说明，`operation_matrix.json`逐项定义month↔extract（不同工具）、date↔extract（list+length vs pluck）、unique↔retain-location（同字段去重差异）和日/月路由（单列）。等级仅为假设。精确候选ID、两个方向、双cap与128更新见运行目录`operation_pair_conditions.json`；`core.pair_stream`及24个CPU侧队列账本可执行。**未启动GPU操作配对实验**，六个粗stage顺序不足以识别纯干扰因果，不作因果验证主张。实际纯配对若以后运行，还须报告真实I/S利用率与剩余混杂。
3. **每split确实21个真实模板文本**：4种count表述×3 + month×3 + locations×3 + fields×3；20个地点结构格共用3模板，4字段也共用3模板。不是泄漏，却不能据此宣称自然语言覆盖充分。保留主研究受控模板，本轮不扩题；自然口语/真实请求作为后置外部验证，不占用本轮所有条件。
4. **合成局限成立**：前缀化实体、固定时间、无缺失/null/时区等适合控制研究，不代表现实部署有效性。用户提到的ACL 2024文献及50 API/四批次等细节本轮**未核实**，不直接作为已核实文献依据，不背书论文级创新或外部有效性。
5. **旧训练器工程冲突成立**：`replay_train._load_checked_rows`按tool_family校验，`train_replay_stage`排斥new family已在old池出现；不能将counts等伪装成工具家族。v2保留`tool_family=calendar`并新增独立`continual_group`，新模块按group组织流/旧池，按七skill评测，注册仍Calendar。旧`sft/evaluate.py`只接一个calendar_path，不读每行fixture_path；新增`BoundCalendar`显式绑定split/路径/hash，并对传错路径、把错split行交给另一个合法registry均报错（含空结果情形），不修改旧API。
6. **月份辅助字段错误属实，gold无误**：48道月份题都在目标日期外多出一个邻日事件。v2移除含糊的`strata.event_count`，改为`target_date_event_count`与`month_total_event_count`；补`target_date`和按调用范围闭包的实体集。日期题闭包为当天，月题闭包为整月，保留空目标日期作为实体。所有1392题的题干/模板/system/messages/tool/args/observation/final/spec/signature逐字段相等；fixtures字节也与v1相等。详见`gold_reconciliation.json`逐题双hash、`month_metadata_changes.json`新增实体ID。

## 版本与边界

- 原v1 manifest SHA256：`944b8e3d9b254e928559a55623aef3c41060234a8b04f010b9f1919f0f0b3881`。
- v2 manifest SHA256：`da99ed3b8a7fa74b1d9fdcb25a6245d6c086358caf341588baff00f5a6fd4bb8`。
- v2目录：`data_ext_p14_eval_protocol_v2/`，仍696/348/348题、相同难度与gold，不按任何模型test成绩修题。
- 新实现全部在`p15_stageaware_20261119/`；CPU证据在`runs_ext_p15_stageaware_20261119/`；原P14 v1、旧科学代码、e3_train.py、旧runs、.venv/conda均不修改。
- CPU原工具执行、实体闭包、跨拆分隔离、真实mask、错误夹具负例、预算/算法/统计/梯度引擎恢复检查均有可重复脚本；PASS仅代表工程正确性，不是算法有效性。基础权重仅CPU流式hash，不实例化预训练模型，更无推理/GPU使用。
