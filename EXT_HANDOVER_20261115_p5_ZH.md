# P5 交接手册
更新时间：2026-11-15 03:26:51 +0800（北京时间）。
状态：complete=True；未完成时请看logs，不要据此报告实验胜负。
## 已冻结设计
见P5_PREREG_20261115_file_timing_ZH.md、P5_PLAN_READY_20261115_ZH.md及data_ext_p5_file_timing/manifest.json。
## 启动（WSL项目根）
```bash
bash scripts/launch_p5_20261115.sh
```
启动前launcher调用监督器，检查r5apex、其它GPU进程、功耗>=60W。STOP粘性，检测游戏后只能经用户明确批准再恢复，不得自动删STOP。
## 监测与停止
runs_ext_p5_file_timing/logs/status.log、queue.log、runner.pid、gpu_child.pid；CPU dry_run.json、preflight.json。写runs_ext_p5_file_timing/logs/STOP可以终止本轮，监督器10秒内处理。
## CPU收尾
```bash
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B scripts/finalize_p5_20261115.py
```
这会重算本轮summary并生成本报告与交接；不启动模型/GPU。
## 资产边界
只新增P5文件；前缀直接只读复用runs_ext_e4/prefixes，加载路径已核对为只读。旧data/runs/冻结卷/环境一律不改。新模型adapter和训练日志在runs_ext_p5_file_timing/branches，新B1结果在evaluation。
## 未自动做
未给GPT发送材料；没有teacher/RL/多智能体；没有更大模型；完成后不启动P6。

## 最终交付状态（2026-11-15 03:28，北京时间）
队列03:10:04 COMPLETE、03:10:06 rc=0；9训练、45套B1均核齐。03:26:51 CPU finalize完成，另做原始joint与训练预算CPU核验，结果在runs_ext_p5_file_timing/completion_audit.json。检查时GPU无计算进程、STOP不存在。本轮已结束，不要执行本文件前面的启动示例；下一轮须另获批准。
主结论：early/uniform/late主Joint均值0.8889/0.8444/0.7889；early相对两基线都非三种子同正，主判据未成立；uniform−late方向一致。完整独立解释与副指标已追加本轮中文实验报告，不能将本轮写成自适应Agent成功。
