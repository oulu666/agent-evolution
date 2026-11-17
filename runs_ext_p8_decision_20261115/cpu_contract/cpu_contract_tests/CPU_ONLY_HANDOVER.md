P8输出runs_ext_p8_decision_20261115；方案P8_PREREG_20261115_decision_ZH.md；输入与代码manifest在data_ext_p8_decision_20261115/manifest.json。
完整为QUEUE COMPLETE + END queue rc=0 + summary.complete=true + 42套B1；首关e2e_gate.json。
监测logs/status.log、queue.log、STOP、runner.pid、gpu_child.pid。安全STOP不自动清除或恢复。
CPU收尾：PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B -m fac_tinyagent.p8_decision_20261115 --phase finalize
没有自动C/P9，无外部GPT发送。
