# P6 attempt2交接手册
更新时间：2026-11-15 11:17:44 +0800（北京时间），complete=True。
方案：P6_PREREG_20261115_devplan_ZH.md；设计/数据先冻结manifest.json，GPU只读梯度后另冻结plans_manifest.json；实现补充锁runtime_lock.json。
正式队列：bash scripts/launch_p6_attempt2_20261115.sh；仅在校准完成、9计划已冻结且协调者审核后启动。
监测：runs_ext_p6_devplan_attempt2/logs/status.log、queue.log、runner.pid、gpu_child.pid；STOP粘性，不自动恢复。
CPU收尾：PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B -m fac_tinyagent.p6_attempt2 --phase finalize
完整结果：runs_ext_p6_devplan_attempt2/summary.json。新增带实际optimizer.step调用凭据的训练副本；旧失败现场不改。旧microstep日志最后22不含尾部flush，新attempt用13次实际调用证明10+13=23，不能凭空添加训练。
不得重跑已完成P5、修改冻结数据/旧实验/.venv/zxx/Small Agent；不发GPT，完成后不自动P7。
