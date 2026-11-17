# P2 交接手册：经验价值梯度打分 pilot（2026-11-13）

## 0. 状态（2026-11-13 18:45，北京时间）

- GPU 打分已完成：18:28:47–18:40:17，共 689.9 秒，6 次（prefix / stage04 × 种子 08/09/10），没有触发游戏检查。GPU 现在空闲。
- 结论：有条件的 Go，只做「同模式 / 同说法经验检索器」的起点；作为跨模式价值估计器是 No-go。详见 `EXT_REPORT_20261113_p2_grad_pilot_ZH.md` §4。

## 1. 新增文件

| 路径 | 内容 |
|---|---|
| `scripts/p2_grad_utility_pilot.py` | 打分（`--phase score`，GPU）/ 分析（`--phase analyze`，CPU）/ 清点（`--phase inventory`，CPU） |
| `runs_ext_p2_grad_pilot/scores_prefix_seed2026110{8,9,10}.json` | prefix 打分点：327 条候选 × 4 个探针的 loss、grad_norm、cos_*、dot_*；探针 / 留出题号；checkpoint 哈希 |
| `runs_ext_p2_grad_pilot/scores_stage04_seed2026110{8,9,10}.json` | stage04 打分点，结构同上 |
| `runs_ext_p2_grad_pilot/results.json` | 三项检验与合理性检查的全部数字 |
| `runs_ext_p2_grad_pilot/tables_ZH.md` | 中文结果表 |
| `runs_ext_p2_grad_pilot/score_run_*.json` | 开跑前检查记录与每次用时 |
| `logs_ext/p2_grad_pilot_20261113.log` | 运行日志 |
| `EXT_REPORT_20261113_p2_grad_pilot_ZH.md` | 报告 |

## 2. 复现（WSL，项目根目录，项目 `.venv`）

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
.venv/bin/python scripts/p2_grad_utility_pilot.py --phase inventory          # CPU：候选/探针清点
# GPU（约 12 分钟）。脚本自带检查：r5apex 在跑 / tasklist 失败 / 功耗上限 <60W 都拒绝启动；每 50 条复查游戏
# 已有的 scores_*.json 会跳过；重算加 --force；只算一个打分点：--ckpts prefix
setsid nohup .venv/bin/python scripts/p2_grad_utility_pilot.py --phase score > logs_ext/p2_grad_pilot_<日期>.log 2>&1 < /dev/null &
.venv/bin/python scripts/p2_grad_utility_pilot.py --phase analyze            # CPU：写 results.json / tables_ZH.md
```

停止：`pkill -f p2_grad_utility_pilot.py`（不写模型，中断只会少几个 scores 文件，下次跳过已完成的）。

## 3. 关键约定

- **打分点**：prefix = `stage_03_python` 适配器 + `runs_ext_e4/prefixes/A_seed*/training_state.pt` 参数（载入后校验 parameter_hash）。这是所有复习臂和 none 臂的真实分支点。stage04 = `runs_phase2/.../stage_04_calendar`，只作稳健性对照。不要把 stage04 当成 none 臂的起点。
- **探针**：fct = nat v2 Database 偶数题号 15 题；奇数 15 题是留出半，只用于外部检验，**不要拿来算梯度**。
- **近邻规则**写在脚本顶部（`NEAR_SORT`、`NEAR_FILTER`）。改规则只需重跑 `--phase analyze`，不需要 GPU。
- 只读：P1 B1 逐题结果、`replay_plan.json`、E4 池、prefix 状态、phase2 适配器。不写任何已有 runs*/data* 文件。

## 4. 下一步候选（未启动，等用户决定）

1. 决定性 token 版探针损失：只在模型出错的分叉 token 上算探针梯度（CPU 改分析 + 约 12 分钟 GPU），看能否解释 tf25 和同 T* 下的差异。
2. 如果要做近邻消融：先把梯度给出的预测（`db.top_n` ≈ 0、`db.filter_eq_count` 略正、`db.group_count` 最高）写进预注册修订，再开训。
3. tf25 差距的另一候选：09/10 的 tf25 target 条目（T-005、T-008）与 A 组（T-001）不同。要分开这两个因素，需要另立预注册设计。
4. 真正遗忘模式的扩充探针题（只评测，约 30 分钟 GPU）仍在待办里。

## 5. 追加：v2 分叉 token 版（2026-11-13 晚，北京时间）

- GPU 打分已完成：18:51:20–19:32:59，共 2498.9 秒，6 次（prefix / stage04 × 种子 08/09/10），没有触发游戏检查。分析在 19:35 用 CPU 重新生成，已纳入全部 6 个 scores。GPU 现在空闲。
- 报告：`EXT_REPORT_20261113_p2_grad_pilot_ZH.md` §6。

| 路径 | 内容 |
|---|---|
| `scripts/p2_grad_utility_pilot_v2.py` | v2：分叉 token 探针。`--phase score`（GPU）/ `--phase analyze`（只用 CPU，读已有 scores，不覆盖）/ `--phase smoke`（GPU，只打印种子 08 prefix 的探针分叉诊断，不写正式输出） |
| `scripts/p2_target_timing_check.py` | CPU：从训练日志读出 target 插入位置和之后的 optimizer 更新次数 |
| `runs_ext_p2_grad_pilot/v2/scores_{prefix,stage04}_seed2026110{8,9,10}.json` | 327 条候选 × 12 个探针向量（4 个探针 × d1/d0/dall）的 cos / dot，以及逐题分叉诊断 `probe_info` |
| `runs_ext_p2_grad_pilot/v2/results.json`、`tables_ZH.md` | 三项检验、偏 Spearman、1-target 排序、11 条 target 条目的打分 |
| `runs_ext_p2_grad_pilot/v2/target_timing.json`、`target_timing_ZH.md` | 插入位置检查 |
| `runs_ext_p2_grad_pilot/v2/score_run_20261113_193259.json` | 开跑前检查与每次用时 |
| `logs_ext/p2_grad_pilot_v2_20261113.log` | 运行日志 |

复现（WSL 项目根目录）：

```bash
.venv/bin/python scripts/p2_grad_utility_pilot_v2.py --phase analyze   # CPU，只读 v2/scores_*.json
.venv/bin/python scripts/p2_target_timing_check.py                     # CPU
# 重新打分（GPU 约 42 分钟，自带游戏 / 功耗检查；已有 scores 会跳过，加 --force 才重算）
setsid nohup .venv/bin/python scripts/p2_grad_utility_pilot_v2.py --phase score > logs_ext/p2_grad_pilot_v2_<日期>.log 2>&1 < /dev/null &
```

要点：

- v2 d1 去掉 target 条数后的偏 Spearman：prefix 0.357，stage04 0.515（v1 为 0.151 / 0.245）。
- 1-target 子集里 tf25 同时高于两臂只有 1/3 个种子。
- `db.top_n` 在 d1 下余弦为负。
- T-005/T-008 的打分低于 T-001。
- **新发现的混杂因素：tf25 的 target 在第 143 位插入（之后 3–4 次更新），dose_db1 / A 两臂都在第 159 位（只有 1 次更新）。**
- 新的 go/no-go 见报告 §6.7。

待决定（未启动）：

1. 插入位置的单变量对照：同一条 T-001、同样的背景，target 放在第 143 位对第 159 位。需要先写预注册修订，三种子不到 1 小时 GPU。
2. 原有待办：真正遗忘模式的扩充探针题（只评测）。
