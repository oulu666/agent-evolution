# P13 Phase0-B 同轮修复接续交接（非完成报告）

A在2026-11-19 01:25:51北京时间通过，B已实际进入。精确持久化恢复/NLL通过；同origin重跑梯度仍不同，不放宽epsilon。详见EXT_REPORT_20261119_p13_phase0b_engineering_A_ZH.md。

根目录runs_ext_p13_phase0b_persist_20261119；supervisor WSL365、worker470；active.json；日志logs/worker_20261119_012018.log，守卫logs/guard.jsonl，终端Windows PID68528。当前为用户明确授权的seed08 attempt03（其它种子原库存），不是新独立实验，不得失败后再开attempt。

只读检查active/progress、worker日志、guard末行、A_PASS/B_ENTERED、各seed COMPLETE、GPU_COMPLETE、supervisor_end；STOP粘性。若游戏/低功耗/新STOP，立即安全停止，不自动清。无新授权不续新中断。

全部结束且supervisor rc0/相关进程退出后，才在同一checkout执行：
.venv/bin/python -B -m fac_tinyagent.p13_phase0b_persist_20261119 final
该新增兼容final先CPU核对保存态文件/语义hash、A精确NLL、物理/逻辑步数和节点完整性，再用原冻结科学指标/gate，输出新增summary/独立报告/交接/COMPLETE；不能直接用旧final硬编码旧路径/10次物理更新。GPU运行时不要并行项目Python验收。父routine暂停，由父助手决定后续监测，不自行改routine/memory/todo。

工程A 2更新/16 backward/32 NLL/0 generate已单列。B上限新增29物理更新/232 backward/576 NLL/432 episodes，逻辑自然后缀仍30步，采用A theta_v只计一次。历史失败与校准成本保留单列。没有正式MIR/DG-MIR训练、不push、不发GPT。

## 最新已核实进度
2026-11-19 01:29:03北京时间：seed08 attempt03 prediction.json已锁定；新的Engine从A磁盘theta_v恢复后，固定8条NLL与A主预测逐值精确一致的跨模型加载断言已通过。01:29:34 node00已完成8/48；01:29:53守卫safe=true、90W、无Apex/竞争进程/STOP。尚无GPU_COMPLETE/最终科学结论，不执行final。不要根据这8条中间生成挑题或更改gate。
