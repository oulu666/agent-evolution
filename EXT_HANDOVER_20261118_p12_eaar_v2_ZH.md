# P12 EAAR-v2 交接手册

完成时刻：2026-11-18 14:27:20（北京时间）。目录 `runs_ext_p12_eaar_v2`，队列 `rc=0`，GPU 训练/评测进程已退出。

## 已落盘

- 运行产物：`runs_ext_p12_eaar_v2/`（5 训练分支、12 逻辑评测目录、`summary.json`、`COMPLETE.json`、`logs/`）
- 冻结与预注册：`P12_PREREG_20261118_ZH.md`、`P12_START_20261118_ZH.md`、`data_ext_p12_eaar_v2/`、`analysis_ext_p12_cpu_20261118/final_freeze_receipt.json`
- 自动短报告（完成瞬间写入，未改）：`EXT_REPORT_20261118_p12_eaar_v2_ZH.md`
- 本轮独立核齐报告（新增）：`EXT_REPORT_20261118_p12_eaar_v2_independent_ZH.md`
- 本交接（新增）：`EXT_HANDOVER_20261118_p12_eaar_v2_ZH.md`

## 核齐结论（供决策，不展开数字以外的新解释）

- 预算与冻结均兑现：五分支精确 7494 复习输入 tokens、22 条、累计 23 次更新；manifest / 盲卷哈希与冻结一致。
- 主判据未过：A 与 B 旧组合计 42/72，未达到预注册要求的 v1+3（43/72），差 1 题；新组 94≥91、每种子旧组不低于 T0−1、旧组不低于 T0 均已满足。决策为不采用、不自动开下一轮。
- A 与 B 在三种子上的严格 Joint 对错完全一致（含覆盖分不同的 seed10）。不能把本轮写成排序增益实验成功或失败，只能说没有测到差异。
- 相对 v1：旧组 +2（全部来自 list_locations），新组 +3（全部来自 seed08 list_tables）；count_date 停留在 v1 的 24/36，低于 T0 的 29/36；filter 仍为 0。

## 明确不要做

- 不 push GitHub，不发 GPT，不自动跑 filter 或下一轮。
- 不改预注册门槛，不覆盖已有 P12/P11 报告，不动旧 runs、E4 前缀、.venv。
- 不清 STOP，不删 `BLOCKED.json`。
- 完成检查 routine 应在本次报告后删除，不必继续轮询。

## 若后续人工讨论

本轮是探索性结果。若要继续，需要新的预注册，而不是在本目录上补训或改门槛。GPU 现已空闲，是否开新实验由用户决定。
