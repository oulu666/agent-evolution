# P6 CPU验收与开跑交接（尚无P6实验结果）

北京时间2026-11-15。仅新增P6实现及数据，没有改旧实验或环境。

## 已做的客观修正
不重复P5，不按三状态名字硬分Early/Late，不拿已知P4/P5正式分数选权重；不加Random与四模块大消融。
首版只验证跨四技能共同预算的开发梯度分配机制，时机默认分散。没有独立恢复时序证据，就不伪称测过恢复速度、自动判断未来更新需求。方法准确称“开发信号驱动一次规划”，不是在线EAAR。

## 方法和实验
独立dev16题计算四技能等权宏平均梯度g；每组去重训练经验均值梯度h_s。B_s=max(0,g·h_s/(||h_s||+1e-12))。每组先1条，再把6个名额按B_s/[(n_s+1)×下一经验input tokens]贪心分配；每组组内顺序种子固定，不按梯度挑有利示例。10条目标+12条背景，共22条replay；背景每家族4条，以同一DP补足token残差。
三臂：均衡分散、同集合均衡前置、开发梯度分配+分散。三种子，共9生产分支。均衡分散同时是去开发效用的核心消融。固定7494±1% input token，23总optimizer steps；所有实际成本入账。

## 独立数据与防测试选择
新dev4×4=16；新holdout4×12=48。新DB dev/test表名、行实体分开；File路径/关键词/内容分开；Python数值集合分开；dev/test题面模板分开。CPU已经执行工具并核对金标准，但没有模型正式holdout输出。
发现LT旧池11条只有1个独立完整对话，已去重为1；其它组各8个候选。LT可重复复习，但不能冒充内容覆盖。校准每种子共16+25=41对forward/backward，0 optimizer.step，参数hash不变；三臂共同计入同等诊断成本。生产训练重新加载原step80模型/优化器/RNG。
新主指标是四技能各12题Joint宏平均；主要比较开发分配−均衡分散：均值>=0.05且三种子都正。FixedEarly另作强挑战。旧P4/P5不再是独立主指标。Calendar v3fix30、File非目标22保留副作用观察，正式每分支运行5套B1共108题。

## 实测CPU验收
- 03:59:34，45个合成分配/预算情景PASS，全部22样本且偏差<=1%。三个均衡基线实际均精确7494 token。
- 04:00:55前，12个单组高效用极端测试全部输出该组7条/其余各1条；3个全零效用fallback与均衡分配一致；64道dev/holdout工具金标准与文件末行/中位数/SQL投影一致；Python AST、bash语法通过。
- 7项守卫单测通过。04:00:55实机preflight：无r5apex，无GPU计算进程，power_cap=133.67W，STOP不存在；显存1394MiB为桌面占用。未改功耗设置。
- 所有这些分配结果是人工合成信号的CPU测试，不是模型测得B或实验成功结论。

## 阶段与命令
第一阶段（必要GPU校准，预计5–10分钟）：
`bash scripts/launch_p6_20261115.sh`
该入口只计算开发/训练候选梯度，不更新模型参数，不读正式模型测试输出；结束后自动生成9计划及data_ext_p6_devplan/plans_manifest.json。不会自动启动生产训练。成功标志queue.log的CALIBRATION COMPLETE和status.log的END calibrate rc=0。
按用户“修改完自动运行”，本轮在CPU验收后直接启动此必要阶段，不再等用户确认。协调者之后可沿同一授权自动续接已冻结9分支，不需要新问用户。
第二阶段（计划已冻结后，预计1.5–3小时）：
`bash scripts/launch_p6_queue_20261115.sh`
它串行训练9分支并在每分支后自动更新中文报告/交接，结束后不自动下一轮。成功标志QUEUE COMPLETE和END queue rc=0，45套B1齐全。
CPU收尾命令：
`PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B -m fac_tinyagent.p6_trainqueue --phase finalize`

## 路径与安全
WSL根：/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent。
日志：runs_ext_p6_devplan/logs/status.log、queue.log、launcher.log、runner.pid、gpu_child.pid。
校准：runs_ext_p6_devplan/calibration/A_seed*.json。停止：runs_ext_p6_devplan/logs/STOP；游戏后粘性STOP不得自动删除，需用户允许再恢复。
新监督器保留单队列flock、进程/r5apex/60W预检、10秒watchdog、连续3次失败fail closed；增加启动握手避免仅打印PID便误报成功。
正式训练只在内存重绑定P5已有训练函数到P6目录，不改P5磁盘文件；兼容审计文件p5_meta.json实际位于P6 branches内。

## 文献定位的实际阻塞
parallel-cli未安装，极简文献搜索未执行成功；按技能停止该搜索渠道，没有换工具绕过。方法用工作名DevGrad，不声称梯度Replay首创或论文新颖性已经建立。此不阻塞可证伪原型实验。
