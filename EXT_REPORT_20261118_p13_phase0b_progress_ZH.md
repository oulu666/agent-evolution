# P13 Phase0-B：修正完成与启动记录（非结果报告）

2026-11-18 北京时间。CPU冻结22:53:16，独立CPU验收22:54:23，监督器启动22:54:34。尚无完整结果，不提前作有效/无效判断。

## 客观取舍
GPT建议中有必要的是：延长到完整自然后缀、增加有限开发覆盖、修复预测时序与观测单位、拆分工具调用和最终输出损失。不必要的是：再做GSS/SQL/提示矩阵或直接三臂训练。诊断流程变复杂不是论文贡献；是否能发展成方法，仍取决于提前分数是否确实预报能力退化，随后才是等预算replay的因果比较。

本轮修正了两个关键问题：候选和探针不是同一单位，所以主检验明确是探针自身的早期ΔNLL→同一探针未来错误；候选→结构匹配探针风险单列次分析，不当作已证明记忆选择泛化。分数用前缀的一步虚拟更新，恢复前缀后才开始真实自然后缀；不拿终点累计loss解释同一终点当“提前预测”。

## 已冻结
三原种子；每种子真实自然Calendar后缀80条/10更新，不插回放、不升LR。校准8条/种子；独立探针48条（每技能24）、候选48条（每技能24）；候选/探针一一结构匹配但不同实体。6种明确日期表达×4复杂度（0/1/3/5事件），地点含重复和未排序多地点。新年份2033/34/35。104条token mask分区和加权分母、ties/AP/TopK/bootstrap缺失簇零权重测试通过，4241条历史数据实体冲突0。

校准只报告掌握度，不筛题、不改内容；三种子校准完成后会写formal_freeze.json，再进入正式开发探针和后缀。主指标为tool+args正确→错误；at-risk固定为每个种子前缀正确集合，全体得分仍保留。主终点0→10，中点5只作次分析。

主gate：至少两个种子各>=5退化、>=5未退化，within-seed AUROC宏平均>=0.65且优于初始NLL/token成本，双向种子×探针聚类bootstrap差值区间下界>0；三种子限制公开，不等于强总体证据。事件不足不换种子、不扩批救结果。任何结果均无后续正式pilot启动授权。

## 实际状态及成本上限
监督器PID 476、worker PID 495。首个种子校准于22:55:51完成8/8，随后已加载第二种子；GPU训练/推理受3秒守卫持续监督。正常规模33个临时optimizer步骤（30自然+3预测）、264个backward样本、576个NLL forward样本、456条两回合episodes/912次generate；全部额外诊断，不称“纯评测不训练”。意外重建最多每种子2attempt，额外成本单列；STOP保持粘性。

## 查验
- 冻结协议：P13_PHASE0B_PREREG_20261118_ZH.md
- 输入manifest：data_ext_p13_phase0b/manifest.json
- 独立CPU验收：runs_ext_p13_phase0b/independent_cpu_acceptance.json
- PID与日志路径：runs_ext_p13_phase0b/active.json
- worker日志：runs_ext_p13_phase0b/logs/worker_20261118_225434.log
- 进度：runs_ext_p13_phase0b/progress.jsonl
- 安全：runs_ext_p13_phase0b/logs/guard.jsonl
- 完成后：COMPLETE.json、supervisor_end.json、summary.json及EXT_REPORT_20261118_p13_phase0b_independent_ZH.md
- 完成且rc=0后独立终验命令：.venv/bin/python -B -m fac_tinyagent.p13_phase0b_acceptance_20261118 final

未push，未发GPT，未改任何旧报告、旧数据、盲卷、e3_train.py或.venv。
