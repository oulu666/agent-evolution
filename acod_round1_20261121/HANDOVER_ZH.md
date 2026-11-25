# ACOD 首轮交接
时间：2026-11-21 14:03:01 +0800（Asia/Shanghai）
Windows：C:\Users\Egret\Desktop\oulu\Agent Self-Evolution\fac_tinyagent\acod_round1_20261121
WSL：/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/acod_round1_20261121
执行命令（项目根）：
.venv/bin/python -B acod_round1_20261121/protocol.py init
.venv/bin/python -B acod_round1_20261121/protocol.py test
.venv/bin/python -B acod_round1_20261121/runner.py supervise
.venv/bin/python -B acod_round1_20261121/analyze.py
状态：complete=True；已完成224次生成；0训练。
不要重跑init或覆盖冻结文件；COMPLETE存在时runner不再生成。未完成时只可在STOP原因核清后从同表续跑，绝不自动删除用户STOP；失败尝试仍占224总上限。
模型身份、时钟、进程PID、rc：results/events.jsonl；逐条调用results/calls_started.jsonl、responses.jsonl；守卫results/logs/guard.jsonl。
结果仅开发/工程证据；没有自然根因gold，没有blind正式卷，没有新工具验证，没有新增ACOD算法。下一步先分析unknown与跨视图预测失败，不能按本轮结果改假设/提示再冒称同一冻结实验。
