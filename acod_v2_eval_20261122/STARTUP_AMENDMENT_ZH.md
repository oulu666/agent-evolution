# 启动环境修正 01（首个模型响应前）

首次监督器于2026-11-22 00:11:11 Asia/Shanghai因ModuleNotFoundError: fac_tinyagent退出，发生在安全守卫import阶段；未创建worker，没有模型加载或生成attempt。原错误逐字保留在results/errors.jsonl与原生终端日志。

原因：以独立目录脚本启动Python时，sys.path含实验目录和v2目录，但未含项目根。修正仅是在后续启动命令显式设置PYTHONPATH为既有项目根，子进程继承；不更改任何锁定源码、模型消息、推理协议、数据、分析指标或生成预算。该环境修正不是权限/安全拒绝的绕过；原生本机工具批准与游戏/STOP/GPU守卫仍照常执行。锁定文件PROTOCOL_LOCK和四份源码仍逐一hash一致。

后续启动实际命令：
cd <原fac_tinyagent根> && PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B acod_v2_eval_20261122/runner.py supervise

本修正于任何模型响应可见前记录。模型attempt上限仍224，首次启动错误须与实际生成失败分别报告；不自动重试游戏/STOP或任何安全阻止。