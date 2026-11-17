# P7精确状态修复v2执行补充

2026-11-15，北京时间。延续P7_STATEFIX_AMEND_20261115_ZH.md，原研究方案和输入不变。

v1在18:03:52通过GPU完整状态往返，在18:04:08通过新File第1步测量；第2步18:04:14因KeyError state1退出。已精确定位新增wrapper的契约错误：本机bitsandbytes.optimizer.state_dict将state1/state2等包装在FSDP嵌套字典；其原生load_state_dict会解包。v1在原生load后手动覆写成序列化字典，导致运行态state1缺失。v2删掉这一多余覆写，完全交由原生loader处理8bit dtype与FSDP解包，并严格比较相同完整语义hash，没有放松校验。

CPU新增真实PagedAdamW8bit序列化/解包/prefetch_state回归（无GPU更新），另保留带dropout AdamW更新精确重演与磁盘完整状态往返测试，全部PASS。旧17:53数值hash漂移发生在未用该wrapper的旧resume，不能把两个不同故障混为同一原因；其不可唯一追溯边界仍见前修订。

新v2目录runs_ext_p7_statefix_v2_20261115，v1及旧目录/源码/产物全部只读保留。仍只复用原seed08完整5对与seed09完整DB filter配对和基线，不复制任何失败File剂量。新增9配对18更新；全设计逻辑30更新，144题B1，未扩大研究。

额外开销：原被游戏中断的File2更新+17:53失败重建1更新+v1第1剂量1更新，已知额外4次；v1第2剂量8次反传已完成，但首参数prefetch即失败，没有成功optimizer更新。新v2完成后累计物理更新至少34，包含额外失败/中断训练反传至少40对；未持久化的生成token未知，不记零。

v2每个新模型状态必须真实落盘→校验文件SHA→加载→原生完整恢复→完整语义hash相同；测量后再次恢复并相同。不能用hash相同替代B1结果，NLL与严格Joint分别记录。

入口scripts/run_p7_statefix_v2_20261115.py --phase queue（会启动GPU）。尊重旧P7及新v2 STOP，Apex/功率上限/进程检查不通过不启动，游戏再次出现停止后不自动恢复。无P8。
CPU收尾：PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B -m fac_tinyagent.p7_statefix_report_v2_20261115。
