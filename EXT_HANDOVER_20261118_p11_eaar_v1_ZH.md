# P11 EAAR-v1 交接手册

更新时间：2026-11-18 10:00:56 +0800（北京时间）。本文件为新增，不覆盖旧交接。

## 状态

本轮重跑已正常结束，不是中断。目录 `runs_ext_p11_eaar_v1`。队列 `END rc=0`，`COMPLETE.complete=true`，`SUMMARY complete=True`，`QUEUE COMPLETE; NO ONLINE REALLOCATION`。监督器 PID 514、worker PID 522 已退出。9 个训练分支全部 PASS，12 个正式状态（9 训练+3 个 T0）×72 题 B1=864，独立重计与 summary 一致。T0 开发探针 3/3。失败首次运行在 `runs_ext_p11_eaar_v1_failed_20261118_025333`，不要当成本轮结果。

检查时 GPU 空闲（约 22.73 W，1%，1383 MiB），无项目训练进程，根目录无 STOP。守卫全程无游戏、无 STOP、无功耗中断。不要清除 STOP，不要自动恢复或续跑（本轮也已结束，无须接续）。不要向 ChatGPT 发消息，不要推送 GitHub，不要开始新的 GPU 实验，除非用户明确要求。

## 关键合同

- 预算：九分支 replay 输入 tokens 均为精确 7494、未用残差 0；累计更新 23=前缀 10+后缀 13。新技能输入 tokens 均为 74944，新技能监督 tokens 均为 8542。replay 监督 tokens 随臂为 1001–1147，不可冒称监督量相同。
- 冻结：Uniform/Fixed Early 计划 02:50:58–02:50:59 写出；EAAR 计划与 `plans_manifest.json` 在三种子开发探针完成后的 08:52:52 写出，`frozen_before_formal=true`；9 个 sha256 与分支回执一致。EAAR 三种子均为 scattered。
- 预注册主判据未达到：eaar_v1−uniform 均值为 +0.0556，但种子 20261109 为 −0.0278，三种子未同正。对 fixed_early 的强挑战同样因 09 为负未达到。不能声称本轮冻结规则已胜出。

## 主数字（严格 Joint）

三种子宏平均均值：t0 0.2130，uniform 0.2639，fixed_early 0.2685，eaar_v1 0.3194。

eaar−uniform 逐种子：+0.1250、−0.0278、+0.0694。eaar−fixed_early：+0.0694、−0.0139、+0.0972。

相对 T0：EAAR 宏平均三种子均上升（均值 +0.1065）；新组获得均值 +0.1944 且三种子为正，几乎全部来自 `db.list_tables`（0→10/8/9）。`db.filter_cmp_top` 全 0；`py.median` 除 fixed_early 种子 08 的 3/12 外为 0；`file.search_last` 基本停在 1/12。旧组 EAAR 均值 0.5417，低于 T0 0.6111 与 uniform 0.5972；种子 08 旧组遗忘最大（18/24→13/24），种子 09 相对 uniform 旧组 −0.0833（未过 0.10，但需记录）。

## 主要路径

- 预注册：`P11_PREREG_20261118_EAAR_V1_ZH.md`
- 数据与计划：`data_ext_p11_eaar_v1/`
- 运行：`runs_ext_p11_eaar_v1/{summary.json,COMPLETE.json,supervisor_end.json,e2e_gate.json,branches,evaluation,probes,logs}`
- 报告：`EXT_REPORT_20261118_p11_eaar_v1_ZH.md`

## 未做事项

未开下一轮训练或评测；未改卷、未改冻结规则、未加臂；未发 GPT、未 push。P11 完成检查 routine 应在交付本交接后删除。游戏退出后的自动接续不适用于已正常结束的本轮。

后续方向需用户决定。若继续 EAAR，应正视 v1 规则未过预注册门、收益集中在 list_tables、以及旧组代价，而不是再堆 File 提示或局部格式修复。
