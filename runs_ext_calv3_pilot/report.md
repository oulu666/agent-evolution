# Calendar v3（未训练子技能）只读补评自动汇总

生成于 2026-11-11 13:31:02（Asia/Shanghai）。**pilot（候选题，未冻结）**
判分 = joint success（工具、参数完全一致、在 v3 新日历上执行一致、答案精确相等）。overall = 5 个子技能等权宏平均。均值±样本标准差（n=种子数）。REF:start = stage_03（学 Calendar 前）；REF:p2cal = phase2 原始顺序学习的 stage_04_calendar（无复习）。

| 轮 | 臂 | n | overall | 最晚空档 | 地点去重 | 参会人数 | 标题计数 | 末场结束 | Calendar nat v2 | Calendar hist |
|---|---|---|---|---|---|---|---|---|---|---|
| REF | start | 1 | 0.180 | 0.033 | 0.000 | 0.700 | 0.167 | 0.000 | - | - |
| E4 | tf50 | 1 | 0.493 | 0.400 | 0.333 | 0.833 | 0.433 | 0.467 | 0.711 | 0.689 |

## 配对比较（同种子同题配对；overall 为子技能分层重抽）

95% CI：hier = 种子+题目两级 bootstrap；item = 种子固定只抽题目（2000 次）。n=3 种子，只描述方向，三个种子同号记为“方向一致”，不作显著性结论。

| 比较 | 指标 | 均值差 | 种子差 sd | +/− 种子数 | 方向 | 95% CI (hier) | 95% CI (item) |
|---|---|---|---|---|---|---|---|

## 逐 run 明细与错误分解

- REF seed20261108 start: {"free_latest": 0.033, "locations": 0, "attendee_count": 0.7, "search_count": 0.167, "last_end": 0, "overall": 0.18}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 1, "answered_first_slot": 8}, "locations": {"n": 30, "tool_ok": 0, "args_ok": 0, "exec_ok": 0, "answer_ok": 0}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 29, "exec_ok": 29, "answer_ok": 21, "count_off_by": 6}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 5, "count_off_by": 24}, "last_end": {"n": 30, "tool_ok": 0, "args_ok": 0, "exec_ok": 0, "answer_ok": 0}}
- E4 seed20261108 tf50: {"free_latest": 0.4, "locations": 0.333, "attendee_count": 0.833, "search_count": 0.433, "last_end": 0.467, "overall": 0.493}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 12, "answered_first_slot": 17}, "locations": {"n": 30, "tool_ok": 29, "args_ok": 29, "exec_ok": 29, "answer_ok": 10, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 25, "count_off_by": 5}, "search_count": {"n": 30, "tool_ok": 23, "args_ok": 23, "exec_ok": 23, "answer_ok": 13, "count_off_by": 17}, "last_end": {"n": 30, "tool_ok": 26, "args_ok": 26, "exec_ok": 26, "answer_ok": 14, "answered_last_start": 2}}
