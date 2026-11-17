# Calendar v3（未训练子技能）只读补评自动汇总

生成于 2026-11-11 19:39:27（Asia/Shanghai）。冻结合并哈希 `2b203ab5123620b9`。
判分 = joint success（工具、参数完全一致、在 v3 新日历上执行一致、答案精确相等）。overall = 5 个子技能等权宏平均。均值±样本标准差（n=种子数）。REF:start = stage_03（学 Calendar 前）；REF:p2cal = phase2 原始顺序学习的 stage_04_calendar（无复习）。

| 轮 | 臂 | n | overall | 最晚空档 | 地点去重 | 参会人数 | 标题计数 | 末场结束 | Calendar nat v2 | Calendar hist |
|---|---|---|---|---|---|---|---|---|---|---|
| REF | start | 3 | 0.162±0.017 | 0.033 | 0.000 | 0.667±0.033 | 0.111±0.069 | 0.000 | - | - |
| REF | p2cal | 3 | 0.462±0.045 | 0.589±0.069 | 0.322±0.019 | 0.856±0.019 | 0.333±0.058 | 0.211±0.192 | - | - |
| E4 | tf00 | 3 | 0.509±0.050 | 0.622±0.171 | 0.211±0.069 | 0.833±0.088 | 0.389±0.077 | 0.489±0.069 | 0.678 | 0.744 |
| E4 | tf25 | 3 | 0.527±0.059 | 0.567±0.208 | 0.344±0.019 | 0.822±0.069 | 0.389±0.077 | 0.511±0.051 | 0.689 | 0.689 |
| E4 | tf50 | 3 | 0.522±0.068 | 0.578±0.184 | 0.322±0.051 | 0.867±0.033 | 0.389±0.077 | 0.456±0.084 | 0.711 | 0.689 |
| E4 | none | 3 | 0.540±0.027 | 0.644±0.117 | 0.322±0.051 | 0.822±0.038 | 0.389±0.077 | 0.522±0.069 | 0.689 | 0.678 |
| E2 | tf00 | 3 | 0.509±0.041 | 0.567±0.145 | 0.256±0.051 | 0.833±0.033 | 0.389±0.077 | 0.500±0.088 | 0.700 | 0.644 |
| E2 | tf25 | 3 | 0.529±0.050 | 0.533±0.186 | 0.344±0.019 | 0.833±0.058 | 0.389±0.077 | 0.544±0.019 | 0.700 | 0.633 |
| E2 | tf50 | 3 | 0.507±0.052 | 0.500±0.153 | 0.256±0.069 | 0.867±0.033 | 0.389±0.077 | 0.522±0.038 | 0.711 | 0.456 |
| E2 | tf75 | 3 | 0.482±0.047 | 0.422±0.204 | 0.289±0.051 | 0.844±0.019 | 0.389±0.077 | 0.467±0.067 | 0.733 | 0.278 |
| E2 | none | 3 | 0.538±0.021 | 0.622±0.117 | 0.322±0.077 | 0.833±0.033 | 0.389±0.077 | 0.522±0.096 | 0.689 | 0.667 |

## 配对比较（同种子同题配对；overall 为子技能分层重抽）

95% CI：hier = 种子+题目两级 bootstrap；item = 种子固定只抽题目（2000 次）。n=3 种子，只描述方向，三个种子同号记为“方向一致”，不作显著性结论。

| 比较 | 指标 | 均值差 | 种子差 sd | +/− 种子数 | 方向 | 95% CI (hier) | 95% CI (item) |
|---|---|---|---|---|---|---|---|
| E4:tf50 - E4:tf25 | overall | -0.004 | 0.025 | 2/1 | 不一致 | [-0.038, +0.024] | [-0.027, +0.018] |
| E4:tf50 - E4:tf25 | free_latest | +0.011 | 0.069 | 2/1 | 不一致 | [-0.078, +0.100] | [-0.044, +0.067] |
| E4:tf50 - E4:tf25 | locations | -0.022 | 0.051 | 1/2 | 不一致 | [-0.089, +0.044] | [-0.078, +0.033] |
| E4:tf50 - E4:tf25 | attendee_count | +0.044 | 0.051 | 2/0 | 不一致 | [+0.000, +0.122] | [+0.011, +0.089] |
| E4:tf50 - E4:tf25 | search_count | +0.000 | 0.000 | 0/0 | 不一致 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4:tf50 - E4:tf25 | last_end | -0.056 | 0.069 | 0/2 | 不一致 | [-0.156, +0.033] | [-0.122, +0.000] |
| E4:tf50 - E4:none | overall | -0.018 | 0.044 | 1/2 | 不一致 | [-0.062, +0.031] | [-0.042, +0.007] |
| E4:tf50 - E4:none | free_latest | -0.067 | 0.067 | 0/2 | 不一致 | [-0.156, +0.022] | [-0.133, +0.000] |
| E4:tf50 - E4:none | locations | +0.000 | 0.100 | 1/1 | 不一致 | [-0.111, +0.111] | [-0.056, +0.056] |
| E4:tf50 - E4:none | attendee_count | +0.044 | 0.019 | 3/0 | 方向一致(+) | [+0.011, +0.100] | [+0.011, +0.089] |
| E4:tf50 - E4:none | search_count | +0.000 | 0.000 | 0/0 | 不一致 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4:tf50 - E4:none | last_end | -0.067 | 0.088 | 1/2 | 不一致 | [-0.178, +0.056] | [-0.156, +0.011] |
| E4:tf25 - E4:none | overall | -0.013 | 0.044 | 1/2 | 不一致 | [-0.060, +0.031] | [-0.036, +0.009] |
| E4:tf25 - E4:none | free_latest | -0.078 | 0.107 | 0/2 | 不一致 | [-0.211, +0.000] | [-0.133, -0.033] |
| E4:tf25 - E4:none | locations | +0.022 | 0.051 | 2/1 | 不一致 | [-0.044, +0.089] | [-0.022, +0.067] |
| E4:tf25 - E4:none | attendee_count | +0.000 | 0.033 | 1/1 | 不一致 | [-0.056, +0.044] | [-0.044, +0.044] |
| E4:tf25 - E4:none | search_count | +0.000 | 0.000 | 0/0 | 不一致 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4:tf25 - E4:none | last_end | -0.011 | 0.107 | 2/1 | 不一致 | [-0.133, +0.111] | [-0.089, +0.067] |
| E4:tf00 - E4:none | overall | -0.031 | 0.042 | 0/3 | 方向一致(−) | [-0.080, +0.007] | [-0.053, -0.009] |
| E4:tf00 - E4:none | free_latest | -0.022 | 0.069 | 1/1 | 不一致 | [-0.111, +0.044] | [-0.067, +0.022] |
| E4:tf00 - E4:none | locations | -0.111 | 0.102 | 0/2 | 不一致 | [-0.233, +0.000] | [-0.178, -0.056] |
| E4:tf00 - E4:none | attendee_count | +0.011 | 0.084 | 1/1 | 不一致 | [-0.078, +0.111] | [-0.033, +0.067] |
| E4:tf00 - E4:none | search_count | +0.000 | 0.000 | 0/0 | 不一致 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4:tf00 - E4:none | last_end | -0.033 | 0.000 | 0/3 | 方向一致(−) | [-0.100, +0.033] | [-0.100, +0.033] |
| E4:tf50 - E4:tf00 | overall | +0.013 | 0.041 | 2/1 | 不一致 | [-0.036, +0.056] | [-0.011, +0.038] |
| E4:tf50 - E4:tf00 | free_latest | -0.044 | 0.051 | 0/2 | 不一致 | [-0.122, +0.033] | [-0.100, +0.011] |
| E4:tf50 - E4:tf00 | locations | +0.111 | 0.084 | 3/0 | 方向一致(+) | [+0.022, +0.222] | [+0.056, +0.178] |
| E4:tf50 - E4:tf00 | attendee_count | +0.033 | 0.067 | 2/1 | 不一致 | [-0.044, +0.111] | [-0.011, +0.078] |
| E4:tf50 - E4:tf00 | search_count | +0.000 | 0.000 | 0/0 | 不一致 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4:tf50 - E4:tf00 | last_end | -0.033 | 0.088 | 1/2 | 不一致 | [-0.144, +0.078] | [-0.122, +0.056] |
| E2:tf75 - E2:tf50 | overall | -0.024 | 0.021 | 0/2 | 不一致 | [-0.053, +0.002] | [-0.049, -0.002] |
| E2:tf75 - E2:tf50 | free_latest | -0.078 | 0.084 | 0/2 | 不一致 | [-0.178, +0.000] | [-0.133, -0.033] |
| E2:tf75 - E2:tf50 | locations | +0.033 | 0.088 | 1/1 | 不一致 | [-0.044, +0.167] | [-0.033, +0.100] |
| E2:tf75 - E2:tf50 | attendee_count | -0.022 | 0.019 | 0/2 | 不一致 | [-0.078, +0.022] | [-0.067, +0.022] |
| E2:tf75 - E2:tf50 | search_count | +0.000 | 0.000 | 0/0 | 不一致 | [+0.000, +0.000] | [+0.000, +0.000] |
| E2:tf75 - E2:tf50 | last_end | -0.056 | 0.102 | 1/2 | 不一致 | [-0.178, +0.056] | [-0.122, +0.011] |
| E2:tf50 - E2:tf25 | overall | -0.022 | 0.010 | 0/3 | 方向一致(−) | [-0.049, +0.002] | [-0.047, +0.002] |
| E2:tf50 - E2:tf25 | free_latest | -0.033 | 0.067 | 1/2 | 不一致 | [-0.122, +0.056] | [-0.100, +0.033] |
| E2:tf50 - E2:tf25 | locations | -0.089 | 0.051 | 0/3 | 方向一致(−) | [-0.178, -0.022] | [-0.156, -0.033] |
| E2:tf50 - E2:tf25 | attendee_count | +0.033 | 0.033 | 2/0 | 不一致 | [-0.011, +0.100] | [-0.011, +0.089] |
| E2:tf50 - E2:tf25 | search_count | +0.000 | 0.000 | 0/0 | 不一致 | [+0.000, +0.000] | [+0.000, +0.000] |
| E2:tf50 - E2:tf25 | last_end | -0.022 | 0.019 | 0/2 | 不一致 | [-0.089, +0.044] | [-0.089, +0.033] |
| E2:tf50 - E2:none | overall | -0.031 | 0.047 | 1/2 | 不一致 | [-0.080, +0.020] | [-0.060, -0.004] |
| E2:tf50 - E2:none | free_latest | -0.122 | 0.051 | 0/3 | 方向一致(−) | [-0.211, -0.022] | [-0.200, -0.044] |
| E2:tf50 - E2:none | locations | -0.067 | 0.145 | 1/2 | 不一致 | [-0.211, +0.089] | [-0.133, +0.011] |
| E2:tf50 - E2:none | attendee_count | +0.033 | 0.033 | 2/0 | 不一致 | [-0.011, +0.100] | [-0.011, +0.089] |
| E2:tf50 - E2:none | search_count | +0.000 | 0.000 | 0/0 | 不一致 | [+0.000, +0.000] | [+0.000, +0.000] |
| E2:tf50 - E2:none | last_end | +0.000 | 0.058 | 2/1 | 不一致 | [-0.089, +0.089] | [-0.067, +0.067] |
| E2:tf25 - E2:none | overall | -0.009 | 0.050 | 1/2 | 不一致 | [-0.060, +0.042] | [-0.031, +0.013] |
| E2:tf25 - E2:none | free_latest | -0.089 | 0.069 | 0/3 | 方向一致(−) | [-0.189, -0.022] | [-0.156, -0.033] |
| E2:tf25 - E2:none | locations | +0.022 | 0.096 | 1/2 | 不一致 | [-0.067, +0.133] | [-0.022, +0.078] |
| E2:tf25 - E2:none | attendee_count | +0.000 | 0.033 | 1/1 | 不一致 | [-0.056, +0.056] | [-0.044, +0.044] |
| E2:tf25 - E2:none | search_count | +0.000 | 0.000 | 0/0 | 不一致 | [+0.000, +0.000] | [+0.000, +0.000] |
| E2:tf25 - E2:none | last_end | +0.022 | 0.077 | 2/1 | 不一致 | [-0.067, +0.122] | [-0.044, +0.089] |
| E2:tf75 - E2:none | overall | -0.056 | 0.052 | 0/3 | 方向一致(−) | [-0.113, -0.004] | [-0.087, -0.027] |
| E2:tf75 - E2:none | free_latest | -0.200 | 0.088 | 0/3 | 方向一致(−) | [-0.333, -0.078] | [-0.289, -0.111] |
| E2:tf75 - E2:none | locations | -0.033 | 0.100 | 1/2 | 不一致 | [-0.156, +0.078] | [-0.100, +0.033] |
| E2:tf75 - E2:none | attendee_count | +0.011 | 0.019 | 1/0 | 不一致 | [-0.033, +0.056] | [-0.022, +0.056] |
| E2:tf75 - E2:none | search_count | +0.000 | 0.000 | 0/0 | 不一致 | [+0.000, +0.000] | [+0.000, +0.000] |
| E2:tf75 - E2:none | last_end | -0.056 | 0.158 | 1/1 | 不一致 | [-0.222, +0.100] | [-0.144, +0.033] |
| E4:tf50 - E2:tf50 | overall | +0.016 | 0.017 | 3/0 | 方向一致(+) | [-0.009, +0.040] | [-0.004, +0.036] |
| E4:tf50 - E2:tf50 | free_latest | +0.078 | 0.038 | 3/0 | 方向一致(+) | [+0.022, +0.144] | [+0.033, +0.133] |
| E4:tf50 - E2:tf50 | locations | +0.067 | 0.058 | 3/0 | 方向一致(+) | [+0.011, +0.156] | [+0.022, +0.122] |
| E4:tf50 - E2:tf50 | attendee_count | +0.000 | 0.000 | 0/0 | 不一致 | [-0.033, +0.033] | [-0.033, +0.033] |
| E4:tf50 - E2:tf50 | search_count | +0.000 | 0.000 | 0/0 | 不一致 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4:tf50 - E2:tf50 | last_end | -0.067 | 0.088 | 1/2 | 不一致 | [-0.178, +0.033] | [-0.133, +0.000] |
| E4:tf25 - E2:tf25 | overall | -0.002 | 0.010 | 1/1 | 不一致 | [-0.020, +0.016] | [-0.018, +0.013] |
| E4:tf25 - E2:tf25 | free_latest | +0.033 | 0.033 | 2/0 | 不一致 | [+0.000, +0.089] | [+0.000, +0.078] |
| E4:tf25 - E2:tf25 | locations | +0.000 | 0.033 | 1/1 | 不一致 | [-0.044, +0.044] | [-0.033, +0.033] |
| E4:tf25 - E2:tf25 | attendee_count | -0.011 | 0.019 | 0/1 | 不一致 | [-0.067, +0.022] | [-0.056, +0.022] |
| E4:tf25 - E2:tf25 | search_count | +0.000 | 0.000 | 0/0 | 不一致 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4:tf25 - E2:tf25 | last_end | -0.033 | 0.067 | 1/2 | 不一致 | [-0.122, +0.044] | [-0.078, +0.011] |
| E4:none - E2:none | overall | +0.002 | 0.017 | 1/1 | 不一致 | [-0.018, +0.022] | [-0.013, +0.016] |
| E4:none - E2:none | free_latest | +0.022 | 0.019 | 2/0 | 不一致 | [+0.000, +0.067] | [+0.000, +0.056] |
| E4:none - E2:none | locations | +0.000 | 0.033 | 1/1 | 不一致 | [-0.044, +0.044] | [-0.033, +0.033] |
| E4:none - E2:none | attendee_count | -0.011 | 0.019 | 0/1 | 不一致 | [-0.067, +0.044] | [-0.056, +0.033] |
| E4:none - E2:none | search_count | +0.000 | 0.000 | 0/0 | 不一致 | [+0.000, +0.000] | [+0.000, +0.000] |
| E4:none - E2:none | last_end | +0.000 | 0.033 | 1/1 | 不一致 | [-0.044, +0.044] | [-0.033, +0.033] |
| E4:none - REF:start | overall | +0.378 | 0.037 | 3/0 | 方向一致(+) | [+0.324, +0.433] | [+0.331, +0.420] |
| E4:none - REF:start | free_latest | +0.611 | 0.117 | 3/0 | 方向一致(+) | [+0.467, +0.756] | [+0.511, +0.711] |
| E4:none - REF:start | locations | +0.322 | 0.051 | 3/0 | 方向一致(+) | [+0.211, +0.433] | [+0.233, +0.411] |
| E4:none - REF:start | attendee_count | +0.156 | 0.051 | 3/0 | 方向一致(+) | [+0.044, +0.267] | [+0.044, +0.267] |
| E4:none - REF:start | search_count | +0.278 | 0.117 | 3/0 | 方向一致(+) | [+0.144, +0.422] | [+0.189, +0.367] |
| E4:none - REF:start | last_end | +0.522 | 0.069 | 3/0 | 方向一致(+) | [+0.411, +0.644] | [+0.422, +0.622] |
| E4:none - REF:p2cal | overall | +0.078 | 0.047 | 3/0 | 方向一致(+) | [+0.024, +0.131] | [+0.044, +0.109] |
| E4:none - REF:p2cal | free_latest | +0.056 | 0.051 | 2/0 | 不一致 | [-0.011, +0.133] | [-0.011, +0.122] |
| E4:none - REF:p2cal | locations | +0.000 | 0.067 | 1/1 | 不一致 | [-0.078, +0.078] | [-0.056, +0.056] |
| E4:none - REF:p2cal | attendee_count | -0.033 | 0.058 | 1/2 | 不一致 | [-0.111, +0.056] | [-0.100, +0.022] |
| E4:none - REF:p2cal | search_count | +0.056 | 0.069 | 2/0 | 不一致 | [+0.000, +0.144] | [+0.011, +0.100] |
| E4:none - REF:p2cal | last_end | +0.311 | 0.126 | 3/0 | 方向一致(+) | [+0.156, +0.456] | [+0.211, +0.422] |

## 逐 run 明细与错误分解

- REF seed20261108 start: {"free_latest": 0.033, "locations": 0, "attendee_count": 0.7, "search_count": 0.167, "last_end": 0, "overall": 0.18}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 1, "answered_first_slot": 8}, "locations": {"n": 30, "tool_ok": 0, "args_ok": 0, "exec_ok": 0, "answer_ok": 0}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 29, "exec_ok": 29, "answer_ok": 21, "count_off_by": 6}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 5, "count_off_by": 24}, "last_end": {"n": 30, "tool_ok": 0, "args_ok": 0, "exec_ok": 0, "answer_ok": 0}}
- REF seed20261108 p2cal: {"free_latest": 0.533, "locations": 0.333, "attendee_count": 0.867, "search_count": 0.4, "last_end": 0.433, "overall": 0.513}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 16, "answered_first_slot": 12}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 10, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 26, "count_off_by": 4}, "search_count": {"n": 30, "tool_ok": 20, "args_ok": 20, "exec_ok": 20, "answer_ok": 12, "count_off_by": 14}, "last_end": {"n": 30, "tool_ok": 23, "args_ok": 23, "exec_ok": 23, "answer_ok": 13, "answered_last_start": 2}}
- E4 seed20261108 tf00: {"free_latest": 0.433, "locations": 0.133, "attendee_count": 0.733, "search_count": 0.433, "last_end": 0.567, "overall": 0.46}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 13, "answered_first_slot": 16}, "locations": {"n": 30, "tool_ok": 22, "args_ok": 22, "exec_ok": 22, "answer_ok": 4, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 27, "exec_ok": 27, "answer_ok": 22, "count_off_by": 5}, "search_count": {"n": 30, "tool_ok": 22, "args_ok": 22, "exec_ok": 22, "answer_ok": 13, "count_off_by": 18}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 17, "answered_last_start": 2}}
- E4 seed20261108 tf25: {"free_latest": 0.333, "locations": 0.367, "attendee_count": 0.8, "search_count": 0.433, "last_end": 0.467, "overall": 0.48}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 10, "answered_first_slot": 19}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 11, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 29, "exec_ok": 29, "answer_ok": 24, "count_off_by": 5}, "search_count": {"n": 30, "tool_ok": 22, "args_ok": 22, "exec_ok": 22, "answer_ok": 13, "count_off_by": 16}, "last_end": {"n": 30, "tool_ok": 28, "args_ok": 28, "exec_ok": 28, "answer_ok": 14, "answered_last_start": 2}}
- E4 seed20261108 tf50: {"free_latest": 0.4, "locations": 0.333, "attendee_count": 0.833, "search_count": 0.433, "last_end": 0.467, "overall": 0.493}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 12, "answered_first_slot": 17}, "locations": {"n": 30, "tool_ok": 29, "args_ok": 29, "exec_ok": 29, "answer_ok": 10, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 25, "count_off_by": 5}, "search_count": {"n": 30, "tool_ok": 23, "args_ok": 23, "exec_ok": 23, "answer_ok": 13, "count_off_by": 17}, "last_end": {"n": 30, "tool_ok": 26, "args_ok": 26, "exec_ok": 26, "answer_ok": 14, "answered_last_start": 2}}
- E4 seed20261108 none: {"free_latest": 0.533, "locations": 0.333, "attendee_count": 0.8, "search_count": 0.433, "last_end": 0.6, "overall": 0.54}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 16, "answered_first_slot": 13}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 10, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 29, "exec_ok": 29, "answer_ok": 24, "count_off_by": 5}, "search_count": {"n": 30, "tool_ok": 22, "args_ok": 22, "exec_ok": 22, "answer_ok": 13, "count_off_by": 18}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 18, "answered_last_start": 2}}
- E2 seed20261108 tf00: {"free_latest": 0.467, "locations": 0.2, "attendee_count": 0.8, "search_count": 0.433, "last_end": 0.6, "overall": 0.5}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 14, "answered_first_slot": 14}, "locations": {"n": 30, "tool_ok": 25, "args_ok": 25, "exec_ok": 25, "answer_ok": 6, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 29, "exec_ok": 29, "answer_ok": 24, "count_off_by": 5}, "search_count": {"n": 30, "tool_ok": 22, "args_ok": 22, "exec_ok": 22, "answer_ok": 13, "count_off_by": 18}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 18, "answered_last_start": 2}}
- E2 seed20261108 tf25: {"free_latest": 0.333, "locations": 0.333, "attendee_count": 0.8, "search_count": 0.433, "last_end": 0.567, "overall": 0.493}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 10, "answered_first_slot": 19}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 10, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 29, "exec_ok": 29, "answer_ok": 24, "count_off_by": 5}, "search_count": {"n": 30, "tool_ok": 23, "args_ok": 23, "exec_ok": 23, "answer_ok": 13, "count_off_by": 17}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 17, "answered_last_start": 2}}
- E2 seed20261108 tf50: {"free_latest": 0.367, "locations": 0.2, "attendee_count": 0.833, "search_count": 0.433, "last_end": 0.567, "overall": 0.48}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 11, "answered_first_slot": 19}, "locations": {"n": 30, "tool_ok": 23, "args_ok": 23, "exec_ok": 23, "answer_ok": 6, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 25, "count_off_by": 5}, "search_count": {"n": 30, "tool_ok": 22, "args_ok": 22, "exec_ok": 22, "answer_ok": 13, "count_off_by": 18}, "last_end": {"n": 30, "tool_ok": 29, "args_ok": 29, "exec_ok": 29, "answer_ok": 17, "answered_last_start": 2}}
- E2 seed20261108 tf75: {"free_latest": 0.2, "locations": 0.333, "attendee_count": 0.833, "search_count": 0.433, "last_end": 0.4, "overall": 0.44}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 6, "answered_first_slot": 24}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 10, "answered_with_duplicates": 2}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 25, "count_off_by": 5}, "search_count": {"n": 30, "tool_ok": 22, "args_ok": 22, "exec_ok": 22, "answer_ok": 13, "count_off_by": 18}, "last_end": {"n": 30, "tool_ok": 29, "args_ok": 29, "exec_ok": 29, "answer_ok": 12, "answered_last_start": 2}}
- E2 seed20261108 none: {"free_latest": 0.5, "locations": 0.367, "attendee_count": 0.833, "search_count": 0.433, "last_end": 0.633, "overall": 0.553}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 15, "answered_first_slot": 14}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 11, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 25, "count_off_by": 5}, "search_count": {"n": 30, "tool_ok": 22, "args_ok": 22, "exec_ok": 22, "answer_ok": 13, "count_off_by": 18}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 19, "answered_last_start": 2}}
- REF seed20261109 start: {"free_latest": 0.033, "locations": 0, "attendee_count": 0.633, "search_count": 0.133, "last_end": 0, "overall": 0.16}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 1, "answered_first_slot": 9}, "locations": {"n": 30, "tool_ok": 0, "args_ok": 0, "exec_ok": 0, "answer_ok": 0}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 29, "exec_ok": 29, "answer_ok": 19, "count_off_by": 26}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 4, "count_off_by": 23}, "last_end": {"n": 30, "tool_ok": 0, "args_ok": 0, "exec_ok": 0, "answer_ok": 5}}
- REF seed20261109 p2cal: {"free_latest": 0.567, "locations": 0.3, "attendee_count": 0.867, "search_count": 0.3, "last_end": 0.1, "overall": 0.427}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 17, "answered_first_slot": 11}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 9, "answered_with_duplicates": 4}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 26, "count_off_by": 4}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 9, "count_off_by": 11}, "last_end": {"n": 30, "tool_ok": 16, "args_ok": 16, "exec_ok": 16, "answer_ok": 3}}
- E4 seed20261109 tf00: {"free_latest": 0.667, "locations": 0.233, "attendee_count": 0.9, "search_count": 0.3, "last_end": 0.433, "overall": 0.507}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 20, "answered_first_slot": 6}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 7, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 27, "count_off_by": 3}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 9, "count_off_by": 12}, "last_end": {"n": 30, "tool_ok": 28, "args_ok": 28, "exec_ok": 28, "answer_ok": 13, "answered_last_start": 1}}
- E4 seed20261109 tf25: {"free_latest": 0.633, "locations": 0.333, "attendee_count": 0.767, "search_count": 0.3, "last_end": 0.5, "overall": 0.507}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 19, "answered_first_slot": 7}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 10, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 27, "exec_ok": 27, "answer_ok": 23, "count_off_by": 4}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 9, "count_off_by": 12}, "last_end": {"n": 30, "tool_ok": 28, "args_ok": 28, "exec_ok": 28, "answer_ok": 15, "answered_last_start": 1}}
- E4 seed20261109 tf50: {"free_latest": 0.567, "locations": 0.267, "attendee_count": 0.867, "search_count": 0.3, "last_end": 0.367, "overall": 0.473}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 17, "answered_first_slot": 11}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 8, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 29, "exec_ok": 29, "answer_ok": 26, "count_off_by": 3}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 9, "count_off_by": 12}, "last_end": {"n": 30, "tool_ok": 28, "args_ok": 28, "exec_ok": 28, "answer_ok": 11, "answered_last_start": 1}}
- E4 seed20261109 none: {"free_latest": 0.633, "locations": 0.367, "attendee_count": 0.8, "search_count": 0.3, "last_end": 0.467, "overall": 0.513}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 19, "answered_first_slot": 7}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 11, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 29, "exec_ok": 29, "answer_ok": 24, "count_off_by": 5}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 9, "count_off_by": 12}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 14}}
- E2 seed20261109 tf00: {"free_latest": 0.5, "locations": 0.3, "attendee_count": 0.833, "search_count": 0.3, "last_end": 0.433, "overall": 0.473}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 15, "answered_first_slot": 14}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 9, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 29, "exec_ok": 29, "answer_ok": 25, "count_off_by": 4}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 9, "count_off_by": 12}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 13, "answered_last_start": 1}}
- E2 seed20261109 tf25: {"free_latest": 0.567, "locations": 0.333, "attendee_count": 0.8, "search_count": 0.3, "last_end": 0.533, "overall": 0.507}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 17, "answered_first_slot": 10}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 10, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 28, "exec_ok": 28, "answer_ok": 24, "count_off_by": 4}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 9, "count_off_by": 12}, "last_end": {"n": 30, "tool_ok": 29, "args_ok": 29, "exec_ok": 29, "answer_ok": 16, "answered_last_start": 1}}
- E2 seed20261109 tf50: {"free_latest": 0.467, "locations": 0.233, "attendee_count": 0.867, "search_count": 0.3, "last_end": 0.5, "overall": 0.473}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 14, "answered_first_slot": 15}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 7, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 26, "count_off_by": 4}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 9, "count_off_by": 12}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 15, "answered_last_start": 1}}
- E2 seed20261109 tf75: {"free_latest": 0.467, "locations": 0.233, "attendee_count": 0.833, "search_count": 0.3, "last_end": 0.533, "overall": 0.473}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 14, "answered_first_slot": 15}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 7, "answered_with_duplicates": 2}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 28, "exec_ok": 28, "answer_ok": 25, "count_off_by": 3}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 9, "count_off_by": 12}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 16, "answered_last_start": 1}}
- E2 seed20261109 none: {"free_latest": 0.633, "locations": 0.367, "attendee_count": 0.8, "search_count": 0.3, "last_end": 0.467, "overall": 0.513}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 19, "answered_first_slot": 7}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 11, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 27, "exec_ok": 27, "answer_ok": 24, "count_off_by": 3}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 9, "count_off_by": 12}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 14}}
- REF seed20261110 start: {"free_latest": 0.033, "locations": 0, "attendee_count": 0.667, "search_count": 0.033, "last_end": 0, "overall": 0.147}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 1, "answered_first_slot": 8}, "locations": {"n": 30, "tool_ok": 0, "args_ok": 0, "exec_ok": 0, "answer_ok": 0}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 20, "count_off_by": 25}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 1, "count_off_by": 23}, "last_end": {"n": 30, "tool_ok": 0, "args_ok": 0, "exec_ok": 0, "answer_ok": 0}}
- REF seed20261110 p2cal: {"free_latest": 0.667, "locations": 0.333, "attendee_count": 0.833, "search_count": 0.3, "last_end": 0.1, "overall": 0.447}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 20, "answered_first_slot": 6}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 10, "answered_with_duplicates": 2}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 25, "count_off_by": 4, "answered_list_not_count": 1}, "search_count": {"n": 30, "tool_ok": 15, "args_ok": 15, "exec_ok": 15, "answer_ok": 9, "count_off_by": 13}, "last_end": {"n": 30, "tool_ok": 25, "args_ok": 25, "exec_ok": 25, "answer_ok": 3, "answered_last_start": 1}}
- E4 seed20261110 tf00: {"free_latest": 0.767, "locations": 0.267, "attendee_count": 0.867, "search_count": 0.433, "last_end": 0.467, "overall": 0.56}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 23, "answered_first_slot": 5}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 8}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 29, "exec_ok": 29, "answer_ok": 26, "count_off_by": 3}, "search_count": {"n": 30, "tool_ok": 23, "args_ok": 23, "exec_ok": 23, "answer_ok": 13, "count_off_by": 17}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 14, "answered_last_start": 1}}
- E4 seed20261110 tf25: {"free_latest": 0.733, "locations": 0.333, "attendee_count": 0.9, "search_count": 0.433, "last_end": 0.567, "overall": 0.593}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 22, "answered_first_slot": 6}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 10}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 27, "count_off_by": 3}, "search_count": {"n": 30, "tool_ok": 22, "args_ok": 22, "exec_ok": 22, "answer_ok": 13, "count_off_by": 17}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 17, "answered_last_start": 1}}
- E4 seed20261110 tf50: {"free_latest": 0.767, "locations": 0.367, "attendee_count": 0.9, "search_count": 0.433, "last_end": 0.533, "overall": 0.6}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 23, "answered_first_slot": 7}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 11, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 27, "count_off_by": 3}, "search_count": {"n": 30, "tool_ok": 22, "args_ok": 22, "exec_ok": 22, "answer_ok": 13, "count_off_by": 16}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 16, "answered_last_start": 1}}
- E4 seed20261110 none: {"free_latest": 0.767, "locations": 0.267, "attendee_count": 0.867, "search_count": 0.433, "last_end": 0.5, "overall": 0.567}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 23, "answered_first_slot": 5}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 8}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 29, "exec_ok": 29, "answer_ok": 26, "count_off_by": 3}, "search_count": {"n": 30, "tool_ok": 23, "args_ok": 23, "exec_ok": 23, "answer_ok": 14, "count_off_by": 16}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 15, "answered_last_start": 1}}
- E2 seed20261110 tf00: {"free_latest": 0.733, "locations": 0.267, "attendee_count": 0.867, "search_count": 0.433, "last_end": 0.467, "overall": 0.553}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 22, "answered_first_slot": 6}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 8, "answered_with_duplicates": 2}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 26, "count_off_by": 3, "answered_list_not_count": 1}, "search_count": {"n": 30, "tool_ok": 23, "args_ok": 23, "exec_ok": 23, "answer_ok": 13, "count_off_by": 17}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 14, "answered_last_start": 1}}
- E2 seed20261110 tf25: {"free_latest": 0.7, "locations": 0.367, "attendee_count": 0.9, "search_count": 0.433, "last_end": 0.533, "overall": 0.587}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 21, "answered_first_slot": 7}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 11, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 27, "count_off_by": 3}, "search_count": {"n": 30, "tool_ok": 23, "args_ok": 23, "exec_ok": 23, "answer_ok": 13, "count_off_by": 17}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 16, "answered_last_start": 1}}
- E2 seed20261110 tf50: {"free_latest": 0.667, "locations": 0.333, "attendee_count": 0.9, "search_count": 0.433, "last_end": 0.5, "overall": 0.567}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 20, "answered_first_slot": 10}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 10, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 27, "count_off_by": 3}, "search_count": {"n": 30, "tool_ok": 22, "args_ok": 22, "exec_ok": 22, "answer_ok": 13, "count_off_by": 16}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 15, "answered_last_start": 1}}
- E2 seed20261110 tf75: {"free_latest": 0.6, "locations": 0.3, "attendee_count": 0.867, "search_count": 0.433, "last_end": 0.467, "overall": 0.533}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 18, "answered_first_slot": 12}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 9, "answered_with_duplicates": 3}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 26, "count_off_by": 3, "answered_list_not_count": 1}, "search_count": {"n": 30, "tool_ok": 22, "args_ok": 22, "exec_ok": 22, "answer_ok": 13, "count_off_by": 16}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 14, "answered_last_start": 1}}
- E2 seed20261110 none: {"free_latest": 0.733, "locations": 0.233, "attendee_count": 0.867, "search_count": 0.433, "last_end": 0.467, "overall": 0.547}
  - diag: {"free_latest": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 22, "answered_first_slot": 6}, "locations": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 7, "answered_with_duplicates": 1}, "attendee_count": {"n": 30, "tool_ok": 30, "args_ok": 29, "exec_ok": 29, "answer_ok": 26, "count_off_by": 3}, "search_count": {"n": 30, "tool_ok": 23, "args_ok": 23, "exec_ok": 23, "answer_ok": 13, "count_off_by": 15}, "last_end": {"n": 30, "tool_ok": 30, "args_ok": 30, "exec_ok": 30, "answer_ok": 14, "answered_last_start": 1}}
