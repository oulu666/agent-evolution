# P1 交接手册（2026-11-12）

- 撰写：2026-11-12 约 16:35（Asia/Shanghai，UTC+8）；2026-11-13 约 13:00 队列完成后更新（新增 §0、§5–§7）。正式结论见 `EXT_REPORT_20261112_p1_ZH.md`；自动数字表见 `runs_ext_p1_b1/summary_tables_ZH.md`。
- 本轮只新增文件。没有改 `.venv`、已有 `runs*/`、`data*/`、Small Agent、conda `zxx`，也没有改冻结的 Calendar v3、nat v2 和 P0 题集。没有向 ChatGPT 发送消息（未使用 gpt_bridge）。没有用 nvidia-smi 改功耗。

## 0. 当前状态（2026-11-13，北京时间）

- **P1 队列已完整跑完**：11-12 16:12:27 启动，中途因打游戏手动停一次，11-13 00:15:36 续跑，11-13 11:53:39 `END queue rc=0`，11:53:50 `summary written: 50 labels`。现在没有 GPU 任务在跑。
- 完成内容：第 1 步 batch 诊断；三种子的协议桥接、T0/T1/T2、v3fix（B1）；dose_db2/3/4 短评；tf00；实验 A 种子 08 两臂（训练 + B1 评测）。
- 未做：实验 A 种子 09/10（计划已冻结，未训练，见 §7）。
- 报告第 4–6 节已补写：`EXT_REPORT_20261112_p1_ZH.md`。

## 1. 新增文件

| 内容 | 路径（相对项目根 `fac_tinyagent`） |
|---|---|
| 第 1 步诊断脚本 | `fac_tinyagent/p1_batchdiag.py` |
| E3-B2 实验 A 计划构建 + 训练 | `fac_tinyagent/p1_e3b2.py` |
| B1 队列 + 汇总 | `fac_tinyagent/p1_run.py` |
| 启动 / 运行 / 停止 | `scripts/launch_p1_20261112.sh`、`scripts/run_p1_20261112.sh`、`scripts/stop_p1.sh` |
| 第 1 步输出 | `runs_ext_p1_batchdiag/{diag_results.jsonl,summary.json,DONE}` |
| 实验 A 冻结计划 | `data_ext_e3b2/{manifest.json,plans/A_seed*_e3b2_A_target_{other,dbbg}.json}` |
| 实验 A 训练输出 | `runs_ext_e3b2/prefixes/A_seed20261108/`、`runs_ext_e3b2/branches/A_seed20261108_e3b2_A_{target_other,target_dbbg}/{e3b2_meta.json,checkpoint/}`（checkpoint 内含 `train_summary.json`、`replay_plan.json`、`training_log.jsonl`、adapter） |
| B1 评测输出 | `runs_ext_p1_b1/evaluation/A_seed<s>_<arm>/<suite>/{results.jsonl,stage_report.json,metrics.*,p1_meta.json}` |
| 汇总 | `runs_ext_p1_b1/{summary.json,summary_tables_ZH.md,queue.json}` |
| 第 4 节补充分析（新） | `scripts/p1_section4_analysis.py` → `runs_ext_p1_b1/analysis/{section4_tables_ZH.md,section4_analysis.json}` |
| 日志 / 状态 / PID / 停止标志 | `logs_ext/p1_20261112.{log,status,pid,stop}` |

## 2. 怎么接着跑 / 复现

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
# 看进度
tail -n 20 logs_ext/p1_20261112.status
grep -v "Loading weights" logs_ext/p1_20261112.log | tail -n 30
# 停止（保留已完成的 suite；未完成的 suite 下次从头重评）
bash scripts/stop_p1.sh
# 续跑（先删停止标志）；已完成的 suite / 训练都会跳过
rm -f logs_ext/p1_20261112.stop && bash scripts/launch_p1_20261112.sh queue
# 只刷新汇总（CPU，可随时跑）
bash scripts/run_p1_20261112.sh summarize
# 第 1 步重跑（会覆盖 runs_ext_p1_batchdiag，需 --force）
bash scripts/launch_p1_20261112.sh diag --force
# 列出队列
.venv/bin/python -m fac_tinyagent.p1_run --phase list
```

PowerShell 用 `wsl.exe -d Ubuntu bash -lc '...'`（单引号）。

**安全机制。** `run_p1_20261112.sh` 启动前检查 `tasklist`：发现 r5apex 或检查本身失败都拒绝启动；功耗上限读数 < 60 W（安静模式约 33 W）也拒绝。运行中看门狗每 30 秒查一次：发现 r5apex、连续 3 次 tasklist 失败或功耗上限掉到 60 W 以下，就会写 `logs_ext/p1_20261112.stop` 并结束 GPU 进程。Python 在每个 suite 前也会检查停止标志并调用 `p0_run.refuse_if_game()`（fail-closed）。被游戏打断后不会自己恢复，要人工删停止标志再续跑。

## 3. 冻结与哈希

- nat v2 combined `5dcc7d786fd60556e97d4e2ebefe143fdd9e96e9aa9052877a1317758b15a8f6`（逐文件运行时校验）
- Calendar v3 combined `2b203ab5123620b99fb64c06afb1e89a388596eade154012e331bb4a27b3633a`（rows `4cca5111…4f64`，fixture `3289868b…d73b04d` 由 `calv3_run.frozen_rows()` 校验）
- Database 非 target v1 combined `9c3b7ea0effa2e88d4e3c882206ecb6d9040c931763c494836cab90eec2aa58d`
- v3fix combined `944be6ce5a5eb8801957b074dc17430982a4ef9f8bc3a44109ffe8cc00ce5e9f`
- 每个 suite 的 `p1_meta.json` 记录行文件 sha256、adapter sha256、协议与耗时。
- E3-B2 计划文件哈希见 `data_ext_e3b2/manifest.json` 的 `plan_files`；训练前逐个校验，不一致就拒绝训练。共享 prefix 是 `runs_ext_e4/prefixes/A_seed*` 经哈希校验后复制到 `runs_ext_e3b2/prefixes/`（种子 08 `state_sha256=5702cc7e…6d9`）。
- `sft/evaluate.py` 的 sha256 写在 `summary.json` 的 `evaluate_py_sha256`。

## 4. 不要改什么

- 不要改 `data_ext_e3b2/plans/*` 与 manifest（已冻结；改清单必须先改预注册）。
- 不要往 `runs_ext_e3`、`runs_ext_e4`、`runs_ext_calv3`、`runs_ext_p0_*` 写入。P1 只读它们。
- 不要把 B1 与历史 B32 的绝对分直接比高低；`summary_tables_ZH.md` 第 3 节只是桥接。
- 不要把 `stage_04_calendar` 当 T1；T1 = E4 `none`。
- v3fix 是附加指标，三项都报，不替代 v3。

## 5. 结果文件位置（队列完成后）

| 内容 | 路径 |
|---|---|
| 报告（含第 4 节结论） | `EXT_REPORT_20261112_p1_ZH.md` |
| 自动汇总（总分、逐模式、桥接、实验 A、剂量、T0/T1/T2、Coverage） | `runs_ext_p1_b1/summary.json`、`runs_ext_p1_b1/summary_tables_ZH.md` |
| 第 4 节补充表（桥接翻转汇总、nat v2 DB 逐环节分解、T0–T1 逐模式、v3fix、实验 A 副指标、File/Python 旁证） | `runs_ext_p1_b1/analysis/section4_tables_ZH.md`、`section4_analysis.json` |
| 队列定义 | `runs_ext_p1_b1/queue.json` |
| 逐题结果 | `runs_ext_p1_b1/evaluation/A_seed<种子>_<臂>/<suite>/results.jsonl`（50 个 label） |
| batch 诊断 | `runs_ext_p1_batchdiag/{summary.json,diag_results.jsonl}` |
| 实验 A 冻结计划 | `data_ext_e3b2/manifest.json`、`data_ext_e3b2/plans/` |
| 实验 A 种子 08 训练输出 | `runs_ext_e3b2/branches/A_seed20261108_e3b2_A_{target_other,target_dbbg}/` |
| 日志 | `logs_ext/p1_20261112.log`、`logs_ext/p1_20261112.status` |

## 6. 如何复现汇总（CPU，不占 GPU）

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
# 1) 从 results.jsonl 重建 summary.json 与 summary_tables_ZH.md
bash scripts/run_p1_20261112.sh summarize
#    等价于：.venv/bin/python -m fac_tinyagent.p1_run --phase summarize
# 2) 重建第 4 节补充表（只读 summary.json 与 results.jsonl）
.venv/bin/python scripts/p1_section4_analysis.py
```

PowerShell：`wsl.exe -d Ubuntu -e bash -lc 'cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent" && .venv/bin/python scripts/p1_section4_analysis.py'`。

## 7. 待决定事项

1. **实验 A 种子 09/10 是否补跑。** 报告 §4.7 建议原样补跑：种子 08 两臂主指标都是 0.100（同一组 3 题），对 ctrl_cal10 / dose_db0 均 +0.100，dbbg−other = 0.000。按预注册，主结论以三种子为准。计划已冻结（09、10 的 \(T^\star\) 均为 `target_db_filter_top-001`），4 臂约 2 小时 GPU。启动（同一安全外壳，已完成项自动跳过）：
   `bash scripts/launch_p1_20261112.sh queue --e3b2-seeds 20261109,20261110`
   启动前照常确认没在打游戏、奥创为狂暴模式。
2. **论文口径**：Database 和 File 目标模式写「能力缺口及其恢复」（T0 = 0，三种子）；forgetting 只用于 phase2 `db.list_tables`、phase2 `py.median` 这类 T0 会、T1 下降的模式。是否采纳，由用户 / GPT 审阅确认。
3. **近邻模式问题**（`db.top_n` / `db.filter_eq_count` → `filter_cmp_top`，`file.search_first` → `search_last`）：目前只是探索性线索（tf25 0.400 对 A 组 0.100；种子 08 tf00 的 nat File 0.533）。若要正式检验，需要先按预注册 §8 写修订再开训；本轮不做。
4. 实验 C、Adaptive Replay、`dose2_*` 仍不在队列里（预注册冻结）。

## 8. 追加（2026-11-13 傍晚，北京时间）：实验 A 三种子已完成

- 实验 A 种子 09/10：2026-11-13 15:30 开跑，17:09 完成，rc=0（北京时间）。命令为 `bash scripts/launch_p1_20261112.sh queue --e3b2-seeds 20261109,20261110`；checkpoint 在 `runs_ext_e3b2/branches/A_seed2026110{9,10}_e3b2_A_target_{other,dbbg}/checkpoint`，B1 评测在 `runs_ext_p1_b1/evaluation/A_seed2026110{9,10}_e3b2_A_*`。
- 报告：`EXT_REPORT_20261112_p1_ZH.md` §7（实验 A 三种子 + 真正遗忘模式恢复分析）。
- 新增脚本（只读，CPU）：`scripts/p2_e3b2_three_seed.py` → `runs_ext_p1_b1/analysis/e3b2_three_seed.json`、`e3b2_three_seed_ZH.md`。
- 重跑（只读，CPU）：`scripts/p2_true_forgetting_analysis.py` → `runs_ext_p1_b1/analysis/true_forgetting_analysis.json`、`true_forgetting_tables_ZH.md`（已纳入 09/10 实验 A）。
- 复现（WSL 项目根目录）：

```bash
.venv/bin/python -m fac_tinyagent.p1_run --phase summarize   # 刷新 summary（如需要）
.venv/bin/python scripts/p2_true_forgetting_analysis.py
.venv/bin/python scripts/p2_e3b2_three_seed.py
```

- 要点：主指标三种子均值 target_other 0.122、target_dbbg 0.111、dose_db1 0.100、dose_db0 0.022、ctrl_cal10 0.000、tf25 0.433。H-background、H-tool 三种子不支持；单条 target 加任何背景 ≈ dose_db1；tf25 差距未解释。**注意：种子 09/10 的 tf25 用的 target 条目（`-005`、`-008`）与 A 组（`-001`）不同，只有种子 08 是同一 \(T^\star\)。** 种子 10 dbbg 非 target 0.375（`filter_cmp_count` 0.125）只作探索记录。
- §7「待决定事项」中「是否补跑 09/10」已完成，不再待决。
- 下一项：经验价值梯度打分 pilot，见 `EXT_HANDOVER_20261113_p2_grad_pilot_ZH.md`。
