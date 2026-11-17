# P6 attempt2实验报告：开发梯度驱动的一次预算规划

更新：2026-11-15 12:37:30 +0800（北京时间）；complete=True；B1套件45/45。
这是开发梯度代理驱动的单次预算规划，不是在线状态分类器或已测恢复速度。不存在按技能名字硬编码早槽偏好。
四组新holdout各12题，预注册主指标为四技能Joint宏平均；旧P4/P5卷不作新主指标。

|种子|臂|macro Joint|Calendar|非目标File|分配|tokens|
|---|---|---|---|---|---|---|
|20261108|balanced_uniform|0.208|0.300|0.636|{'py.median': 3, 'db.list_tables': 3, 'db.filter_cmp_top': 2, 'file.search_last': 2}|7494|
|20261108|balanced_early|0.375|0.300|0.636|{'py.median': 3, 'db.list_tables': 3, 'db.filter_cmp_top': 2, 'file.search_last': 2}|7494|
|20261108|devgrad_uniform|0.208|0.267|0.636|{'py.median': 1, 'db.list_tables': 5, 'db.filter_cmp_top': 1, 'file.search_last': 3}|7494|
|20261109|balanced_uniform|0.167|0.333|0.636|{'file.search_last': 3, 'py.median': 3, 'db.list_tables': 2, 'db.filter_cmp_top': 2}|7494|
|20261109|balanced_early|0.208|0.300|0.636|{'file.search_last': 3, 'py.median': 3, 'db.list_tables': 2, 'db.filter_cmp_top': 2}|7494|
|20261109|devgrad_uniform|0.188|0.333|0.636|{'file.search_last': 4, 'py.median': 2, 'db.list_tables': 3, 'db.filter_cmp_top': 1}|7494|
|20261110|balanced_uniform|0.271|0.367|0.636|{'db.filter_cmp_top': 3, 'db.list_tables': 3, 'py.median': 2, 'file.search_last': 2}|7494|
|20261110|balanced_early|0.271|0.367|0.636|{'db.filter_cmp_top': 3, 'db.list_tables': 3, 'py.median': 2, 'file.search_last': 2}|7494|
|20261110|devgrad_uniform|0.250|0.333|0.636|{'db.filter_cmp_top': 1, 'db.list_tables': 6, 'py.median': 1, 'file.search_last': 2}|7494|

## 修复与公平性
旧attempt缺摘要必需quota字段而失败；新attempt只补接口诊断元数据，计划items/分配/7494 tokens/超参/holdout全部不变。校准hash核验后复用，不重复GPU校准。实际optimizer事件13次加prefix10次为23；日志最后microstep182的22是尾部6条flush之前，不是漏一步。失败adapter不复用。

## 配对判定
{
  "devgrad_uniform-balanced_uniform": {
    "per_seed": [
      0.0,
      0.020833333333333343,
      -0.020833333333333315
    ],
    "mean": 9.25185853854297e-18
  },
  "devgrad_uniform-balanced_early": {
    "per_seed": [
      -0.16666666666666666,
      -0.020833333333333343,
      -0.020833333333333315
    ],
    "mean": -0.06944444444444443
  }
}

主要分配机制判据：未达到。
FixedEarly挑战：未达到；不能声称优于两固定策略。
- 20261108 calendar配对差-0.033。
- 20261108 file_nontarget配对差+0.000。
- 20261109 calendar配对差+0.000。
- 20261109 file_nontarget配对差+0.000。
- 20261110 calendar配对差-0.033。
- 20261110 file_nontarget配对差+0.000。

## 成本与边界
校准每种子41个forward/backward，0 optimizer steps；三臂共同计入同等诊断成本。生产分支23 optimizer steps，实际tokens逐臂报告。背景按同一DP匹配残余token，背景内容可变化，所以不能声称纯目标条数独立因果。
未达到判据时不自动加实验，不修改holdout，不启动下一轮。
