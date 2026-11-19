# P13 Phase0B交接（已冻结、待运行/运行中）

2026-11-18 22:53:16 +0800 北京时间

仅本轮有上限诊断获授权，未授权后续正式pilot。CPU输入、分段token与metric测试通过。协议P13_PHASE0B_PREREG_20261118_ZH.md；数据data_ext_p13_phase0b/manifest.json。执行命令 .venv/bin/python -B -m fac_tinyagent.p13_phase0b_20261118 supervise，必须经守卫；不清STOP。

状态看runs_ext_p13_phase0b/active.json、progress.jsonl、logs/worker_*.log；最终看COMPLETE.json与supervisor_end.json及summary.json。若已COMPLETE则禁止再运行。若BLOCKED且无STOP，游戏退出后可同命令继续本轮；若STOP粘性保留，不绕过。意外中断每种子最多2attempt，从原前缀确定性重建并额外记成本。

正常上限3种子×10自然更新+3预测虚拟步，456两回合episodes/912generate；主分数在前缀预测虚拟一步后即冻结，主终点0→10，0/5/10生成。未授权5种子三臂正式训练，不push不发GPT。
