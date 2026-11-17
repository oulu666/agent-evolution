# 交接手册 · Calendar v3 只读补评（未训练子技能自然语言期末）· 2026-11-11

更新：2026-11-11 19:39（Asia/Shanghai，UTC+8）。通用环境（WSL、`.venv`、模型路径、功耗、PowerShell 坑）见 `HANDOVER_ENVIRONMENT_ZH.md`、`EXT_HANDOVER_20261110_ZH.md`。上一轮见 `EXT_HANDOVER_20261111_e4_ZH.md`、`EXT_REPORT_20261111_e4_ZH.md`、`GPT_REVIEW_20261111_e4_ZH.md`。正式结论见 `EXT_REPORT_20261111_calv3_ZH.md`。

## 1. 现状（已完成，不必重启）

- 正式链 `scripts/run_calv3_20261111.sh` 第一次于 2026-11-11 13:32:14 启动（runner pid 470，setsid + nohup）。14:27:13 用户暂停游戏，`scripts/stop_calv3.sh` 写入停止旗标并结束进程组，当时做到 `eval_E2_20261109_tf50` 中途。
- 18:36:05 续跑（pid 501）。已完成的评测自动跳过（约 26–34 秒/组，只做存在性检查），被中断的 `eval_E2_20261109_tf50` 重做（166 秒）。19:39:27 正常结束：`ALL_DONE fails=0 total=3802s`（续跑段约 63 分钟），日志末行 `CALV3_FINISHED`。
- 33 组评测全部 `rc=0`：REF start / p2cal × 3 种子，E4 的 none / tf00 / tf25 / tf50 × 3，E2 的上述四臂再加 tf75 × 3。每个种子结束后有一次报告，最后还有 `final_report`（rc=0，15 秒）。
- 进程已退出，pid 501 不在。不要重跑已完成的链，不要改已有 `runs_ext_e4/`、`runs_ext_tf/`、`.venv`、conda `zxx`、`oulu\Small Agent`。`runs_ext_calv3/` 是本链写入的新目录，报告已写完，不要再往里训。
- 只新增：数据 `data_ext_cal_v3/`，代码 `fac_tinyagent/calv3_data.py`、`fac_tinyagent/calv3_run.py`，脚本 `scripts/{run,launch,stop}_calv3*.sh`，结果 `runs_ext_calv3/`，文档见第 7 节。已有代码一行未改。

一句话结论：v3 有余量（学完后 overall 0.48–0.54，start 0.162）；E4 干净池上 tf25 / tf50 相对 none 没有方向一致的 overall 代价（点估计略负，CI 穿过 0）；E2 脏池上 tf75 overall 以及最晚空档从 tf25 起相对 none 方向一致下降。下一步是 E3，不是 E5。

## 2. 数据与冻结哈希（`data_ext_cal_v3/`）

| 文件 | 内容 | 哈希 / 规模 |
|---|---|---|
| `final_v3/calendar_v3.jsonl` | 冻结的 150 道自然语言题 | sha256 `4cca511187606ece1ab90c0903dd81b9a2bcb8919cadf8882de77486b2244f64`，5 类 × 30 |
| `fixtures/calendar_v3.json` | 不规则新日历 | sha256 `3289868b4a22ccb2770f3a4a3b72723f30fb0a11c44b823fa6055f88d1f2b04d`；174 场、45 日、1–6 场/天、人数 2–10 |
| `final_v3/FROZEN.json` | 版本、哈希、种子、评分规则 | 合并哈希（combined_sha256）`2b203ab5123620b99fb64c06afb1e89a388596eade154012e331bb4a27b3633a`；版本字符串 `calendar_natural_final_v3`；冻结时间 2026-11-11 13:32:13 +0800 |
| `checks_frozen.json` | 泄露与金标准复核 | `ok: true`；与已有训练/复习/探针/v2 的签名、prompt、messages、Calendar 调用重叠为 0 |
| `PILOT.md` | 两轮试评（只用 seed 20261108 的 start 与 E4 tf50） | Pilot 分数不进入正式结果 |
| `candidate/`、`pilot1_candidate/` | 试评候选题存档 | 不要当正式题用 |

fixture 种子 20261131，题目种子 20261132。任何改题或改日历必须换版本号和哈希，另开新目录评测，不能覆盖 `final_v3/`。构建脚本在冻结后应拒绝覆盖。

五类题都不是训练模板：最晚空档、地点去重、参会人数、标题计数、末场结束。判分 = joint success（工具、参数、在 v3 日历上执行、答案精确相等）。overall = 五类等权宏平均。

## 3. 评测产物（`runs_ext_calv3/`）

- `evaluation/`：33 个子目录，命名 `E4_A_seed{种子}_{臂}`、`E2_A_seed{种子}_{臂}`、`REF_A_seed{种子}_{start|p2cal}`，全部齐全。
- `report.md`、`results.json`：mtime 2026-11-11 19:39:27（Asia/Shanghai）。`results.json` 的 `frozen` 字段等于上面的合并哈希；`generated` 为 `2026-11-11 19:39:27`；含 `runs`（33）、`aggregates`（11）、`comparisons`（配对差与两种 CI）。
- 日志：`logs_ext/calv3_20261111.{log,status,pid,targets}`。status 里早期的 `STOP_REQUESTED`（14:27:13）是游戏暂停，不是失败；以最后一行 `ALL_DONE fails=0 total=3802s` 为准。

Checkpoint 来源（只读，不要改）：

- E4 最终 adapter：`runs_ext_e4/branches/`（或该轮评测所用的已有路径，由 `calv3_run` 解析）
- E2 最终 adapter：`runs_ext_tf/`
- REF start：各种子 stage_03；REF p2cal：phase2 原始顺序的 stage_04_calendar

## 4. 查看、停止、续跑、只出报告

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
tail -n 30 logs_ext/calv3_20261111.status      # START/DONE/FAIL/WAIT_GPU/STOP_REQUESTED/ALL_DONE
tail -n 50 logs_ext/calv3_20261111.log
bash scripts/stop_calv3.sh                      # 写 stop 旗标，只结束本链进程组 / calv3_run，不碰游戏或其他任务
# 续跑（跳过已完成的评测；若正式链已 ALL_DONE，不要再启动）：
rm -f logs_ext/calv3_20261111.stop && bash scripts/launch_calv3_20261111.sh
.venv/bin/python -m fac_tinyagent.calv3_run --phase report     # 单独重出报告（CPU，不占 GPU）
.venv/bin/python -m fac_tinyagent.calv3_run --phase list       # 列出 33 个目标
```

PowerShell：

```powershell
wsl.exe -d Ubuntu -- bash -lc 'tail -n 30 "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/logs_ext/calv3_20261111.status"'
wsl.exe -d Ubuntu -- bash -lc 'bash "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/scripts/stop_calv3.sh"'
```

- 每个 GPU 任务前有显卡空闲门（显存 < 3000MiB 且利用率 < 40%，连续 3 次、间隔 20 秒）。失败的 GPU 评测会自动重试一次。
- 环境变量：`CALV3_MODE=formal|pilot`（正式结果必须用 formal；pilot 只用于冻结前试评），`GATE_MEM_MIB`、`GATE_UTIL`。
- 单组补评（一般不需要）：`.venv/bin/python -m fac_tinyagent.calv3_run --phase eval --round E4 --seed 20261108 --arm tf50`
- 已完成的评测有输出就会跳过。中途被杀的那一组没有完整输出，续跑会重做。不要手工改 `runs_ext_calv3/evaluation/`。

## 5. 复核（CPU，不重评）

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
.venv/bin/python -m fac_tinyagent.calv3_run --phase report
python3 -c "import json; d=json.load(open('runs_ext_calv3/results.json',encoding='utf-8')); print(d['frozen']); print(d['generated']); print(len(d['runs']))"
```

应看到合并哈希 `2b203ab5123620b99fb64c06afb1e89a388596eade154012e331bb4a27b3633a`，33 条 run，生成时间 2026-11-11 19:39:27。不要重跑 33 组 GPU 评测，除非结果文件损坏或哈希对不上。

## 6. 已知问题

1. 标题计数在所有训练后臂上按种子锁死（0.433 / 0.300 / 0.433），对复习比例无信息；参会人数起点就高（start 0.667），区分弱。读 overall 时要同时看最晚空档和地点去重。
2. 最晚空档方差大，模型常把它做成最早空档（训练技能迁移）。末场结束常和“最后一场的开始时刻”混淆。
3. 只有 3 个种子、只做了 A 场景。配对 CI 只作描述，三个种子同号才能写“方向一致”，不能写显著。
4. E4 与 E2 前缀不是同一份，跨轮差值混有非确定性。臂内配对是干净的。
5. E4 的 tf00 不是严格零 target：种子 20261109 / 20261110 均匀抽样抽到了 File target（见 `runs_ext_e4/token_ledger.md`）。
6. 复习臂比 none 多约 10% 训练 token（约 82,438 对 74,944）。本轮即使看到复习 vs none 的差异，也混有额外计算量；E3 必须加计算量匹配对照。
7. Monitor 校准的外部复核与离线单元同起点、同种子，不是独立种子。G_cum 样本只有 4 个阳性，不可靠。
8. 链的 status 文件里保留了 14:27:13 的 `STOP_REQUESTED`，后面才是续跑和 `ALL_DONE`。不要只 grep 到 STOP 就以为还停着。

## 7. 新增文件

- 代码：`fac_tinyagent/calv3_data.py`、`fac_tinyagent/calv3_run.py`
- 脚本：`scripts/run_calv3_20261111.sh`、`scripts/launch_calv3_20261111.sh`、`scripts/stop_calv3.sh`
- 数据：`data_ext_cal_v3/`
- 结果：`runs_ext_calv3/`
- 日志：`logs_ext/calv3_20261111.{log,status,pid,targets}`
- 文档：本文件，`EXT_REPORT_20261111_calv3_ZH.md`，`scripts/gpt_bridge/msg_20261111_calv3.md`（草稿，**尚未发给 ChatGPT**）
- 并行产物（本轮之前已写好，不要覆盖）：`runs_ext_monitor_calib/report.md`、`runs_ext_e4/token_ledger.md`

## 8. 下一步：E3（尚未启动，先等 GPT 回复后再开）

按 E4 审稿后已商量好的方案，**先不要改、也不要先开训**：

- 预算扫描：5% / 10% / 20%。工作点 tf25 与 tf50；对照 none 与均匀（tf00）。10% 直接复用已有 E4 checkpoint（已有 v2、v3、历史测试），不必重训。
- 计算量匹配的 Calendar-only 对照：额外约 7,494 输入 token 继续练 Calendar 新数据（或把复习位填成 Calendar 样本），用来拆开“定向经验”和“多训了 10% token”。
- Database 剂量：固定 10% 总预算，Database 定向样本精确控制为 0/1/2/3/4/6 条，其余用均匀样本补齐，同时记 token 数和样本长度。
- 评测同时报自然语言期末 v2、v3 和历史测试。两套期末都已冻结，不能改题。
- **不要启动 E5。** Monitor 对 G_need 只是初步可用，G_cum 不可靠，阈值也不能再用期末刻度的 0.8。
- 约束不变：只在 `fac_tinyagent` 里新增；一次只跑一个 GPU 任务；有空闲门；用户说暂停就停；正式 8B / RL 不上这台笔记本。

给 GPT 的消息草稿在 `scripts/gpt_bridge/msg_20261111_calv3.md`。发送前须确认没有 `r5apex`，并用已有的 `send_message_v2.ps1`，对话仍是「智能体自进化实验规模」。本手册撰写时**尚未发送**。
