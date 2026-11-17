# P9独立阶段审查交接（未完成）

北京时间：2026-11-17 15:33:24 +0800。完整报告：`EXT_REPORT_20261117_p9_independent_review_ZH.md`。

- 当前训练6/6、诊断72/72；评测完整模型6/9；实时分支数见下表。原summary为15:11的旧中途稿，不能当当前进度。
- 最新队列记录：`2026-11-17 15:33:20 +0800 EVAL 20261110 baseline 40/56`；STOP=False；queue_complete存在=False。
- 本次仅CPU读取+新增独立中文材料/快照，不触发任何GPU进程，不改旧数据、run、环境、评分、STOP或Git。

|种子|组|已落盘题/56|完成回执|
|---|---|---:|---|
|20261108|baseline|56|True|
|20261108|normal|56|True|
|20261108|counter|56|True|
|20261109|baseline|56|True|
|20261109|normal|56|True|
|20261109|counter|56|True|
|20261110|baseline|42|False|
|20261110|normal|0|False|
|20261110|counter|0|False|

## 最关键独立判断

- P8主指标均值+1.39个百分点、不达预注册；P8.1证实训练题能学会，泛化/组合不稳。
- P9普通SFT与counter才是公平的增强比较；不得拿P9新卷分数减P8旧卷0分。已完整种子08 normal last11/12、counter5/12、baseline8/12；反事实逆序收益伴随正常last损失，四项全对都0/12。三种子没齐前不下最终胜负。
- 精确控制通过：34冻结hash、3对完整起点、18真实新增更新/臂、输入监督精确同。26,867/3,743是单epoch；真实每臂53,734/7,486，六臂108更新。
- P9终点SQL保持只有list_tables，不含filter_cmp_top；训练前SQL提示诊断不是训练后保持证据。
- 下一候选为normal重复单视图 vs同一题正常/逆序双视图（3旧A只读复用+3新B）；不叠加课程/同义改写/SimPO。先用独立dev触发，主指标仍正常B1 last，新正式卷独立冻结，不使用已看P9 holdout选择超参。详见报告，尚未预注册/实施。

## 给主助手的下一步（本阶段到此停止）

1. 不启动/恢复/终止P9或下一轮。当前GPT队列PID 553/563在跑。按已完成模型间隔193/184/210/209秒，剩余每模型约3—3.5分钟；不无限轮询，正常无中断预估原15:28快照之后约9—16分钟，即15:37—15:44北京时间完成。
2. 完成时只读核齐queue_complete.json、9个eval_*_complete.json及56条唯一题、6训练回执，再读取新正式summary。若summary仍旧，检查GPT是否正CPU收尾；别并发改写其报告。
3. 如需CPU官方收尾，命令是 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/analyze_p9_20261117.py`。此命令会写原run汇总及GPT主报告，本文未执行。
4. 只有主助手看完整结果后再次给实施授权，才冻结新一轮dev触发/数据/代码与安全入口。GPU闲置、Apex关闭、enforced power limit≥60W、无STOP/无其他GPU进程才开；游戏STOP不自动清理恢复。

## 文件位置

- 项目Windows根：`C:\Users\Egret\Desktop\oulu\Agent Self-Evolution\fac_tinyagent`。
- WSL根：`/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent`。
- 本阶段新增：`EXT_REPORT_20261117_p9_independent_review_ZH.md`、`EXT_HANDOVER_20261117_p9_independent_review_ZH.md`、`analysis_p9_independent_review_20261117/`（3份只读分析快照）。
- 现有监控：`runs_ext_p9_counterfactual_20261117/logs/queue.log`、`logs/supervisor.log`；完成标志`queue_complete.json`。无新增脚本、GPU训练或外部操作。
