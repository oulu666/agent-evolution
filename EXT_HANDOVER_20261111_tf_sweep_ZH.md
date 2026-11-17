# 交接手册 · Monitor v2 验证 + Target Fraction 扫描链 · 2026-11-11

更新：2026-11-11 00:20（Asia/Shanghai，UTC+8）。通用环境（WSL、`.venv`、模型路径、功耗、PowerShell 坑）见 `HANDOVER_ENVIRONMENT_ZH.md` 与 `EXT_HANDOVER_20261110_ZH.md`。本轮结论见 `EXT_REPORT_20261111_monitor_ZH.md`，整体规划见 `RESEARCH_MATRIX_20261111_ZH.md`。

后续更新：2026-11-11 03:02（Asia/Shanghai，UTC+8）。链已正常结束（`ALL_DONE total=8111s`），全部任务 rc=0。**第 1–5 节保持 00:20 的原文**（当时链还在等显卡），第 6 节起补写完成状态、读结果的方法、以及下一步与风险。本轮结论见 `EXT_REPORT_20261111_tf_sweep_ZH.md` 与 `EXT_REPORT_20261111_monitor_ZH.md` 第 8 节。

## 1. 现状

- 链 `scripts/run_tf_sweep_20261111.sh` 已于 2026-11-10 23:59:41 启动（runner pid 476，用 setsid + nohup 运行，不依赖会话在线）。
- CPU 部分已完成：v2 探针集生成、File 标签重判分、旧探针的 monitor 指标。
- 启动时显卡被用户的游戏（r5apex_dx12）占用，约 7.3GB / 90%。链在 `WAIT_GPU` 门控处等待：显存 < 3000MiB 且利用率 < 40%，连续 3 次（间隔 20 秒）才开始下一个 GPU 任务。**每个 GPU 任务开始前都会重新检查**，所以用户中途再开游戏时，链会在任务之间停下来等。
- 只新增，不改已有 `runs*`、`.venv`、conda `zxx`、`oulu\Small Agent`。已有代码一行未改。

## 2. 链的步骤（全部跳过已完成的结果）

| 步 | 内容 | 输出 | 估时（显卡空闲后） |
|---|---|---|---|
| 1 | `monitor_v2_data`：生成 v2 探针（已存在就跳过） | `data_ext_monitor_v2/` | 秒级 |
| 2 | `monitor_v2_offline --phase report`（CPU） | `runs_ext_monitor/report.md`、`monitor_eval.json` | 5 秒 |
| 3 | `monitor_v2_offline --phase gpu`：v2 探针跑 A/C × 3 种子的起点、中点（从 Round 2 前缀恢复）、none 终点、习得参考点；参考点另测 natural final | `runs_ext_monitor/eval/` | ≈30 min |
| 4 | 烟测：seed108 的 tf00 和 tf50，16 条新样本、1 epoch、每工具 4 条探针、每套评测 3 题，然后自动检查；通过后写 `runs_ext_tf_smoke/SMOKE_OK`，失败则 `ABORT` 并且不启动正式扫描 | `runs_ext_tf_smoke/` | ≈8 min |
| 5 | 正式扫描：按种子优先，seed108 的 tf00/25/50/75 → seed109 → seed110；每个 run 先训练再评测；每个种子结束后更新报告 | `runs_ext_tf/branches/`、`evaluation/`、`report.md`、`results.json` | ≈20 min/种子 |
| 6 | 可选 none 对照（同一前缀），3 个种子 | 同上 | ≈15 min |
| 7 | 最终报告：TF 报告 + monitor 报告（含 v2） | `runs_ext_tf/report.md`、`runs_ext_monitor/report.md` | 秒级 |

**全链估时**：显卡空闲后约 2 小时，其中 monitor ≈30 min、烟测 ≈8 min、12 个 TF run ≈65 min、none 对照 ≈15 min。等待游戏结束的时间另算。

TF 设置与 Round 2 A 一致：A 顺序 stage 3→4（Calendar 新，File/Database/Python 旧），同一个 Round 2 复习池和 target_ids，10% 新数据输入 token 预算，batch 1 / 梯度累积 8 / 2 epoch / lr 1e-4，复习只在后半段，固定 target 族权重各 1/3，`mode=targeted`，`target_fraction ∈ {0, .25, .5, .75}`（tf00 等价于 uniform）。唯一的区别是探针换成 v2，所以生成了新的共享前缀 `runs_ext_tf/prefixes/A_seed*`。每个种子第一个 run（tf00）负责创建前缀，其余 run 复用。

每个 run 记录（`runs_ext_tf/results.json`）：
- natural final：修正判分和原判分两种口径
- 历史测试：4 个工具
- Calendar（新工具）
- v2 探针终点分
- 实际复习 token、实际 target 比例、target 样本数
- 分支实际耗时和参考耗时
- 起点/中点的探针分

## 3. 查看、停止、续跑

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
tail -n 30 logs_ext/tf_sweep_20261111.status      # START/DONE/FAIL/WAIT_GPU/ALL_DONE
tail -n 50 logs_ext/tf_sweep_20261111.log
ps -p "$(cat logs_ext/tf_sweep_20261111.pid)" -o pid,etime,cmd
bash scripts/stop_tf_sweep.sh                       # 一键停止：写 stop 旗标并结束进程组
rm -f logs_ext/tf_sweep_20261111.stop && bash scripts/launch_tf_sweep_20261111.sh   # 续跑
```

在 PowerShell 里：

```powershell
wsl.exe -d Ubuntu -- bash -lc 'tail -n 30 "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/logs_ext/tf_sweep_20261111.status"'
wsl.exe -d Ubuntu -- bash -lc 'bash "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/scripts/stop_tf_sweep.sh"'
```

- 中断在训练中途：下次启动时，没写出 `train_summary.json` 的分支目录会被改名为 `*_partial_<时间戳>` 放到一边，然后重训；已完成的分支和评测会跳过。
- 门控参数可以用环境变量调整，例如 `GATE_MEM_MIB=3500`。只跑部分内容：`TF_SEEDS="20261108" TF_ARMS="tf00 tf50"`；跳过 none 对照：`TF_SKIP_NONE=1`；跳过 monitor：`TF_SKIP_MONITOR=1`。
- 单独重做报告（CPU）：`.venv/bin/python -m fac_tinyagent.ext_tf_sweep --phase report`，以及 `.venv/bin/python -m fac_tinyagent.monitor_v2_offline --phase report`。

## 4. 新增文件

- 代码：
  - `fac_tinyagent/monitor_v2.py`：判定规则
  - `fac_tinyagent/ext_rescore.py`：File 重判分
  - `fac_tinyagent/monitor_v2_data.py`：v2 探针生成
  - `fac_tinyagent/monitor_v2_offline.py`：离线验证
  - `fac_tinyagent/ext_tf_sweep.py`：TF 扫描的训练、评测、报告
- 脚本：`scripts/run_tf_sweep_20261111.sh`、`scripts/launch_tf_sweep_20261111.sh`、`scripts/stop_tf_sweep.sh`
- 数据和结果：`data_ext_monitor_v2/`、`runs_ext_monitor/`、`runs_ext_tf/`、`runs_ext_tf_smoke/`
- 日志：`logs_ext/tf_sweep_20261111.{log,status,pid}`、`logs_ext/ext_20261111_code.tgz`、`logs_ext/ext_20261111_patch1.tgz`（代码投放包）
- 文档：`RESEARCH_MATRIX_20261111_ZH.md`、`EXT_REPORT_20261111_monitor_ZH.md`、本文件

## 5. 已知问题与注意事项

1. TF 扫描沿用 Round 2 的 target 池，其中 16 条 File target 行带着“整列表”错误标签。tf 越大，File 修正分可能越低，这是已知混杂因素，由研究矩阵 E4 拆开。读结果时以修正口径的 Database/Python 为主，单独看 File。
2. 复习插入位置 `common_replay_positions` 取三种计划的最小样本数，因 tf 不同而可能略有差异。实际位置数记录在每个 run 的 `replay_positions` 字段。
3. 起点分直接引用 Round 2 的 start 评测（同一个 stage_03 adapter、同一评测协议，只读），不重测。
4. `replay_train.py` 的 adaptive 仍是 v1 规则；v2 自适应在 E5 中另写新模块实现，不改旧文件。
5. C 盘剩余约 73GB；本链新增约 0.5GB。

---

## 6. 链已完成（2026-11-11 03:02:19，Asia/Shanghai）

- 状态文件最后一行：`2026-11-11 03:02:19 ALL_DONE total=8111s`，日志末尾有 `TF_SWEEP_FINISHED`。全部 `START/DONE` 配对，rc 均为 0，没有 FAIL / ABORT。
- 计时从 00:47 的断点重启起算，约 2 小时 15 分。更早一次启动时显卡被游戏占用，用户要求停止；当时停在 GPU 任务开始之前，CPU 产物保留，重启后跳过已完成步骤。
- 烟测已写出 `runs_ext_tf_smoke/SMOKE_OK` 后才进入正式扫描。
- 15 个分支全部完成：3 种子 ×（tf00 / tf25 / tf50 / tf75 / none）。自动报告在 `runs_ext_tf/report.md` 与 `results.json`，主口径已用 File 修正判分。
- 监测 GPU 评测（v2 探针的起点、中点、none 终点、习得参考点）已完成，最终监测报告在 `runs_ext_monitor/report.md` 与 `monitor_eval.json`。人工整理见 `EXT_REPORT_20261111_tf_sweep_ZH.md`、`EXT_REPORT_20261111_monitor_ZH.md` 第 8 节。
- 评测峰值显存约 2–3 GB。结束后不应再留有训练或评测进程。不要在未得到用户允许时启动下一组 GPU 实验。

查看完成状态：

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
tail -n 20 logs_ext/tf_sweep_20261111.status
# 应看到 ALL_DONE，且 ps 里不应再有 run_tf_sweep / ext_tf_sweep / monitor_v2_offline 的训练进程
```

单独重做报告（只读，CPU）：

```bash
.venv/bin/python -m fac_tinyagent.ext_tf_sweep --phase report
.venv/bin/python -m fac_tinyagent.monitor_v2_offline --phase report
```

## 7. 如何读本轮数字

- **主口径**：独立自然语言最终考试的旧工具宏平均，File last-match 按“最后一行”重判分（`nat_fix_*`）。原标签 `nat_raw_*` 只并列，不作为结论依据——本扫描全部 15 个 run 的 `nat_raw_file` 都是 0。
- **新工具**：只有历史测试口径的 Calendar（`calendar_hist`）。没有自然语言 Calendar。
- **历史测试**（`hist_*`）旧工具宏平均在各臂之间几乎走平（0.600–0.637），不能用来比较复习比例。
- **File 必须单独看**：复习池里 16 条 File target 仍带“整列表”错误标签。tf 越高，File 修正分越可能被拉低。这是已知混杂，不是干净的方法效应。读宏平均时要把 File 拆开，并以 Database / Python 为更干净的证据。
- **实际定向比例低于设定值**：tf25 实际 0.232±0.029，tf50 实际 0.416±0.024，tf75 实际 0.642±0.069（seed 20261109 的 tf75 只有 0.566）。比较臂的时候两列都要报。
- **tf00 的墙钟不可直接和其他臂比**：它包含共享前缀的创建（约 200–230 秒）；其他臂复用前缀，分支本身约 50 秒。看 `actual_elapsed_seconds`。
- **不要用 `mv2end_*` 代替最终考试来选比例**：v2 File 与自然语言 File 几乎不相关，见监测报告第 8 节。

## 8. 本轮结论摘要（详情见正式报告）

- 旧工具自然语言保留：none 0.344 → tf00 0.374 → tf25 0.633 → tf50 0.830 → tf75 0.737。均匀复习几乎无增益。
- 新工具 Calendar：none 0.667，tf00 0.644，tf25 0.633，tf50 0.456，tf75 0.278。
- E2 双门槛没有单一点同时满足。Pareto 前沿是 tf25 与 tf50；tf75 被 tf50 支配。
- Database 在 tf00 / none 接近 0，定向样本 ≥3（约 tf50）才跃升到 0.87–1.00。Python 在 seed 20261108 的 tf00 崩到 0.033，1 条定向样本即可拉回。File 在 tf25 最好（0.700），tf75 最差（0.222），受错误标签污染。
- 监测：旧探针 + rule2 的方向仍成立；v2 探针在 τ=0.8 下把 15 个单元全部标成不足，误报率 1.00。τ 必须先离线重校准，才能做 E5。

## 9. 下一步与风险

**在用户明确说继续之前，不要启动新的 GPU 任务。**

建议的优先级（与正式报告一致，供下一轮启动时用）：

1. **CPU，可先做**：用已有的 15 个单元 v2 分数，离线重校准 τ（或按工具 / 子题型设线），报告新门槛下的召回、误报和 IE。不改原始 `monitor_eval.json` 的判定表，另存校准结果。
2. **E4，需要 GPU**：重建 File target 池（标签按题意，文件和路径与最终考试同分布但不重叠），在 tf25 / tf50（必要时加 tf75）上对照旧池。不拆开这件事，高比例臂的 File 和宏平均写不干净。
3. **E3，需要 GPU**：预算 5% / 20%，在 tf25 和 tf50 两个工作点上做，不要先“只定一个比例”。
4. **E5 必须等第 1 步（必要时再等 E4）**：不要用 τ=0.8 的 v2 规则直接做自适应训练，否则会变成“对所有旧工具都定向”。
5. **可插空的**：给 Calendar 补自然语言最终考试；E7 的 MMLU 收尾仍放空闲夜间；C 场景确认是 E6，放在 A 的工作点和 File 池稳定之后。

主要风险：

- File 错误标签仍在池中，会污染任何继续使用旧池的高 tf 实验。
- 3 个种子、只有 A 场景，方差大，不能把 0.830 或 0.456 写成精确最优值。
- 实际 token 打包使高设定比例达不到名义值。
- ChatGPT 桌面桥接脚本 `scripts/gpt_bridge/send_message.ps1` 在 2026-11-10 尚未自动发送成功过（上一轮由用户手动发）。发送前必须确认对话标题是「智能体自进化实验规模」、输入框为空、游戏进程未在运行；对不上就停，只发一次。
- C 盘当时剩余约 73GB，本链增量不大；若再开 E3/E4，注意 checkpoints 的磁盘占用。

## 10. 新增的本轮文档

- `EXT_REPORT_20261111_tf_sweep_ZH.md`：本扫描的正式实验报告
- `EXT_REPORT_20261111_monitor_ZH.md` 第 8 节：v2 探针 GPU 实测补全
- 本文件第 6–10 节
- 若本轮已把材料发到 ChatGPT 并取回审阅：`GPT_REVIEW_20261111_tf_sweep_ZH.md`
