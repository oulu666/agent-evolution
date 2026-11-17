# Calendar v3（未训练子技能）只读补评自动汇总

生成于 2026-11-11 13:22:14（Asia/Shanghai）。**pilot（候选题，未冻结）**
判分 = joint success（工具、参数完全一致、在 v3 新日历上执行一致、答案精确相等）。overall = 5 个子技能等权宏平均。均值±样本标准差（n=种子数）。REF:start = stage_03（学 Calendar 前）；REF:p2cal = phase2 原始顺序学习的 stage_04_calendar（无复习）。

| 轮 | 臂 | n | overall | 最晚空档 | 地点去重 | 参会人数 | 标题计数 | 末场结束 | Calendar nat v2 | Calendar hist |
|---|---|---|---|---|---|---|---|---|---|---|
| REF | start | 1 | 0.227 | 0.033 | 0.000 | 0.867 | 0.233 | 0.000 | - | - |
| E4 | tf50 | 1 | 0.480 | 0.567 | 0.033 | 0.933 | 0.300 | 0.567 | 0.711 | 0.689 |

## 配对比较（同种子同题配对；overall 为子技能分层重抽）

95% CI：hier = 种子+题目两级 bootstrap；item = 种子固定只抽题目（2000 次）。n=3 种子，只描述方向，三个种子同号记为“方向一致”，不作显著性结论。

| 比较 | 指标 | 均值差 | 种子差 sd | +/− 种子数 | 方向 | 95% CI (hier) | 95% CI (item) |
|---|---|---|---|---|---|---|---|

## 逐 run 明细与错误分解

- REF seed20261108 start: {"free_latest": 0.033, "locations": 0, "attendee_count": 0.867, "search_count": 0.233, "last_end": 0, "overall": 0.227}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 1, "answered_first_slot": 8}, "locations": {"n": 30, "tool_ok": 0, "args_ok": 0, "exec_ok": 0, "answer_ok": 0}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 26, "count_off_by": 10}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 7, "count_off_by": 8}, "last_end": {"n": 30, "tool_ok": 0, "args_ok": 0, "exec_ok": 0, "answer_ok": 2}}
- E4 seed20261108 tf50: {"free_latest": 0.567, "locations": 0.033, "attendee_count": 0.933, "search_count": 0.3, "last_end": 0.567, "overall": 0.48}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 17, "answered_first_slot": 12}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 1, "answered_with_duplicates": 2}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 28, "count_off_by": 2}, "search_count": {"n": 30, "tool_ok": 22, "args_ok": 22, "exec_ok": 22, "answer_ok": 9, "count_off_by": 46}, "last_end": {"n": 30, "tool_ok": 26, "args_ok": 26, "exec_ok": 26, "answer_ok": 17}}
