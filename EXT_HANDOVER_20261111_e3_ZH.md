# E3 交接手册（2026-11-12）

- 撰写：2026-11-12 约 03:30（Asia/Shanghai，UTC+8）。正式结论见 `EXT_REPORT_20261111_e3_ZH.md`。

## 1. 本轮做了什么

- E3-A：3 档预算（5% / 10% / 20%）× 3 种定向比例（tf00 / tf25 / tf50），外加同预算、同优化步数的 Calendar-only 计算量对照（ctrl_cal05/10/20）。10% 档和 none 复用 E4。
- E3-B：10% 固定预算下的 Database 剂量 k = 0/1/2/3/4/6 条独立 target，File/Python 块固定，Database 复习 token 固定。
- 3 个种子（20261108/09/10），共 45 个新训练 + 45 次评测，**全部 rc=0，fails=0**。
- 时间：2026-11-11 20:21 启动；22:29 用户玩游戏暂停（STOP_REQUESTED）；之后续跑；2026-11-12 03:25:19 ALL_DONE（运行时间合计 11,332 秒）。
- 本轮只新增文件：没有改 `.venv`、已有 `runs*/`、`data*/`、Small Agent、conda `zxx`。

## 2. 结果在哪里

| 内容 | 路径 |
|---|---|
| 自动汇总（含全部配对比较与逐 run 分数） | `runs_ext_e3/report.md` |
| 结构化结果 | `runs_ext_e3/results.json` |
| 真实 token 账本 | `runs_ext_e3/token_ledger.{md,json}` |
| 各分支 checkpoint / 训练日志 | `runs_ext_e3/branches/` |
| 各分支评测 | `runs_ext_e3/evaluation/` |
| 共享前缀（从 E4 只读复制并核对 sha256） | `runs_ext_e3/prefixes/` |
| 链日志 / 状态 | `logs_ext/e3_20261111.log`、`logs_ext/e3_20261111.status` |
| 正式报告 | `EXT_REPORT_20261111_e3_ZH.md` |
| 给 GPT 的消息 / 回复 / 审稿整理 | `scripts/gpt_bridge/msg_20261111_e3.md`、`scripts/gpt_bridge/reply_20261111_e3.txt`、`GPT_REVIEW_20261111_e3_ZH.md`（后两个视发送情况而定） |
| 计划（预注册） | `EXT_PLAN_20261111_e3_ZH.md` |

注意：`logs_ext/e3_20261111.pid` 在续跑后不存在（runner pid 522 是由 launch 脚本重新拉起的）。看进度以 status 文件为准。

## 3. 关键数字（速查）

- 旧工具 nat v2 宏平均：
  - none 0.389
  - tf25：b05 0.548 / b10 0.719 / b20 0.896
  - tf50：b05 0.759 / b10 0.915 / b20 0.933
  - tf00：b05 0.489 / b10 0.474 / b20 0.863
  - Calendar-only 对照 0.35–0.39
- Calendar v3 overall：none 0.540；b20_tf25 0.473、b20_tf50 0.456（方向一致下降，非劣效未达）；其余 0.50–0.54。
- Database 剂量（DB nat v2）：k = 0/1/2/3/4/6 → 0.000 / 0.100 / 0.344 / 0.611 / 0.822 / 1.000。
- dose_db6：nat old 0.885，v3 −2.2pp，非劣效通过。

## 4. 复现与命令

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
# 只重出报告（CPU，几分钟）
.venv/bin/python -m fac_tinyagent.e3_run --phase report
# 复核数据计划（CPU）
.venv/bin/python scripts/test_e3_data.py
# 追加 E3-B2 第二套嵌套抽样（15 个分支，约 2 小时；已完成的会自动跳过）
E3_WITH_DRAW2=1 bash scripts/launch_e3_20261111.sh
# 停止
bash scripts/stop_e3.sh
```

PowerShell 用 `wsl.exe -d Ubuntu -- bash -lc '...'`（单引号）。

- 显卡：训练和评测前把奥创控制中心切到狂暴模式。安静模式只有约 33W，会非常慢。
- 空闲门：显存 < 3000MiB 且利用率 < 40%，连续 3 次，并且没有其他 fac_tinyagent python 进程。用户玩游戏时链会自动等待。
- 玩游戏前可以 `bash scripts/stop_e3.sh`。续跑：`rm -f logs_ext/e3_20261111.stop && bash scripts/launch_e3_20261111.sh`，已完成的分支会跳过。

## 5. 已知问题 / 待办

1. **评测是 batch-1，受生成速度限制**（每次约 190–220 秒，链墙钟的大头）。下一轮先实现 batched eval：
   - 在固定的一批已有 checkpoint（例如 E3 种子 08 的 none / b10_tf50 / dose_db3 / ctrl_cal10）上与 batch-1 结果逐题对比。
   - 贪心解码，注意 padding 方向与 attention mask。
   - 一致后再替换。新代码放新文件，不改 `e3_run.py`。
2. Calendar v3 的“标题计数”子技能所有臂都约 0.389，需要检查题目或判分。
3. dose_db1（DB 0.100）与 b10_tf25（DB 0.444）都只有 1 条 DB target，但结果差很多。建议跑 E3-B2 检验这是不是“抽到哪一条”的效应。
4. Database nat v2 与 target 模板高度对应，需要补一个非 target 模板的 Database 题集，避免“覆盖即满分”的质疑。
5. 关键臂扩到 5 个种子：需要先生成新种子的 phase2 stage_03 起点和 E4 前缀。

## 6. 建议的下一步（待用户确认后再启动 GPU 任务）

1. （CPU / 短 GPU）batched eval 实现并做一致性验证。
2. 预注册“按工具缺口分配”的新臂。在 10% 预算内：
   - Python 只留最少量；
   - Database 放约 4–6 条独立 target；
   - File 保持 tf50 的定向量。
   与 b10_tf50、dose_db6、none、ctrl_cal10 对比，主指标仍是旧工具 nat v2 + Calendar v3 非劣效。
3. 跑 E3-B2（已冻结，直接加 `E3_WITH_DRAW2=1`）。
4. 关键臂扩到 5 个种子；20% 预算只保留一个臂作为“代价”证据。
