# P8启动与交接记录（尚非最终结果）
核实：2026-11-16 00:04:36 +0800（北京时间）。正式队列2026-11-15 23:59:20安全启动，首B08训练2026-11-16 00:01:18审计通过、00:03:16首24题真实B1完成并放行余比较。当前新训练1/3、旧A复用3、正式B1 1/42。Windows持久宿主134776，监督器455，GPU子进程463，STOP=False。

## 独立研究判断
不拟合五特征回归，不跑五组重复基线。当前只比较A原经验均衡分散与B合法决策对照经验均衡分散，优先回答内容能否改善strict Joint；C没有已证实任务信号会退为均衡，本轮不跑重复C。此为经验包实验，不是EAAR分配方法已成功。
补查旧训练输入：File旧目标7/7已经有多个不同匹配、gold最后一条；旧Median8/8也已经使用正确stats_median。不能把失败直接解释成旧池完全缺少正确信息。本轮真正新增的是first/last成对意图区分、SQL zero/few+tie反例覆盖和明确中央值措辞等组合包。这个边界只限制结论，不改变冻结计划/数据/判据；原始只读核验见old_experience_scope_audit.json。

## 真实设计与预算
仅3个新B训练，A三个历史最终模型经hash/前缀/配置/23累计更新核实后只读复用，统一在新题B1评测。12条背景经验与22条packing/时机/Calendar序列逐行保持，10个目标槽内容替换。每分支23累计更新=复用前缀10+新增13，尾部6条真实flush；本轮新训练39更新、无GPU诊断/额外校准。A输入7494，B7521/7538/7556，偏差+0.3603%/+0.5871%/+0.8273%，无padding。监督token A1202/1187/1184，B1238/1223/1234，不能称监督量也完全相同。
候选组合算法：固定原每技能数量与时机，满足File成对、SQL zero与few+tie覆盖，按固定种子有限枚举，最小化真实input token总差；不看dev或holdout成绩。
训练44、dev16（4/技能）、新正式56（主48=12/技能，另first/mean控制8），模板家族/数据库/File实体/完整数值输入集合分开，median都匹配A的7个11..40两位数。gold116与单独WHERE/tie/first-last/参数反例CPU验证。Calendar30+非目标三族各4；6终点共42套B1、588题状态评测，非独立588样本。

## 真正验收证据
CPU实际P8 runner→trainer→summary/尾flush→完整状态原生落盘恢复均PASS：13次真实CPU SGD后参数与解析值误差<1e-6。B1/finalize部分用真实结果字段schema的显式CPU桩，绝不混入正式成绩。复用P7 v2原生bnb FSDP解包契约。
首GPU分支真实summary completed、23累计/13新增、7521 tokens、1238 supervised tokens；Calendar序列和每行packing/更新相位与A完全一致，prefix和终点参数/optimizer/scaler/RNG/模块模式精确落盘恢复。首24题真实B1完成，gate只检查执行/题数，不按正确率放行。

## 监测与收尾
logs/status.log、queue.log、runner.pid、gpu_child.pid、STOP，首关e2e_gate.json。开跑game=false，无其它GPU任务，功率上限129.47W；保留单GPU与游戏/功率/连续检查失败守卫，STOP不清除、不自动恢复。
预计总50–100分钟（起点23:59北京时间），以实际日志为准。当前不等待整队列。完成必须QUEUE COMPLETE + END queue rc=0 + summary.complete=true + 42套B1齐全。
runner每终点后自动CPU finalize；必要CPU收尾：PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B -m fac_tinyagent.p8_decision_20261115 --phase finalize。
正式报告/交接EXT_REPORT_20261115_p8_decision_ZH.md、EXT_HANDOVER_20261115_p8_decision_ZH.md将由runner更新；本启动记录保留。预注册P8_PREREG_20261115_decision_ZH.md；冻结data_ext_p8_decision_20261115/manifest.json。无自动C/P9，无外部GPT消息。
