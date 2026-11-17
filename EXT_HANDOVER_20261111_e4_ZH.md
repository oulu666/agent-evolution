# 交接手册 · E4（干净 File 复习池 + 自然语言期末 v2）· 2026-11-11

更新：2026-11-11 11:40（Asia/Shanghai，UTC+8）。通用环境（WSL、`.venv`、模型路径、功耗、PowerShell 坑）见 `HANDOVER_ENVIRONMENT_ZH.md`、`EXT_HANDOVER_20261110_ZH.md`。上一轮见 `EXT_HANDOVER_20261111_tf_sweep_ZH.md`、`EXT_REPORT_20261111_tf_sweep_ZH.md`、`GPT_REVIEW_20261111_tf_sweep_ZH.md`。

## 1. 现状

- 链 `scripts/run_e4_20261111.sh` 于 2026-11-11 11:07:35 启动（runner pid 535，setsid + nohup，不依赖会话在线）。
- 已完成：数据构建与单元检查（ALL_PASS）→ 极小烟测（SMOKE_OK，11:17:42）→ 上轮 checkpoint 的 Calendar 自然语言补评（calnl_old，11:18–11:28，18 个 adapter 全部完成）→ 正式 E4 第一个 GPU 任务 `train_20261108_tf00` 正常完成（11:29:13–11:33:51，rc=0，新建前缀，复习 7494/7494 token，峰值显存 3.99GB），11:34:32 起在评测。
- 只新增：没改任何已有 `runs*`（含 `runs_ext_tf`，只读）、`.venv`、conda `zxx`、`oulu\Small Agent`，已有代码一行未改。
- 每个 GPU 任务前都有显卡空闲门（显存 < 3000MiB 且利用率 < 40%，连续 3 次、间隔 20 秒）。用户中途开 Apex，链会在任务之间停下等，不会杀任何非本链进程。

## 2. 数据（`data_ext_e4/`，由 `fac_tinyagent/e4_data.py` 生成，已存在时拒绝覆盖）

| 文件 | 内容 | 规模 |
|---|---|---|
| `pool/file.jsonl` | `data_round2` File 池去掉 16 条错标 last-match target，加 16 条新 target：金标准=执行 `file_search` 后的**最后一条匹配行原文**（answer_spec `match -1`），文件在新根目录 `e4_replay/log_XXX.txt`，生成器与期末同分布（6 行、2–3 个匹配、同词表），新种子 20261121 | 96 行（80 原始 + 16 新 target） |
| `pool/database.jsonl`、`pool/python.jsonl` | 与 `data_round2/pool` 字节级相同（哈希已核对） | 91 / 94 行（target 11 / 14） |
| `manifest.json` | `target_ids`（File 换成新 16 条；DB/Py 不变）、池哈希、改动记录 | |
| `final_v2/*.jsonl` + `FROZEN.json` | 自然语言期末 v2（见第 3 节） | 4 × 30 = 120 题 |
| `checks.json` | 单元检查与泄露检查的完整结果 | |

单元检查（`scripts/test_e4_data.py`，链开头自动跑，失败即 ABORT）：
- 检查器独立于 `project_answer`：按题意（“last/latest/final line”→最后一条、“first/earliest”→第一条、行数、词数、.txt 计数、字符数）+ 重新执行工具得到金标准。
- 对旧 `data_round2/pool/file.jsonl`：恰好抓出 16 条错标（就是那 16 个 target id）；对旧 final File：30/30 错标。→ 证明检查器能抓到这个 bug。
- 新 File 池 96/96、final_v2 File 30/30：0 错；注入“整列表标签”“第一条代替最后一条”都能被抓到。
- final_v2 全部 120 题 + 三个池全部执行复核：0 不一致。Calendar 30 题另用 fixture JSON 直接重算（不走工具代码）：0 不一致。

泄露检查（训练输入 = 三个池 + Calendar 训练集；评测 = final_v2 + 历史 test/val + replay_study + round2 monitor/final + monitor v2 探针）：
- 任务签名重叠 0，整段 messages 重叠 0。
- File：池 vs final_v2 路径重叠 0、文件内容重叠 0、(pattern, 内容) 重叠 0；池 vs 任一评测集路径重叠 0、内容重叠 0。新 target 根目录 `e4_replay/`，期末根目录 `round2_final/`。
- 行级：新 target 的 96 行里有 35 行与期末文件中的某一行相同（模板行 `line N: <词> appears in this line` 按设计会重复；整文件从不重复）。如实记录，不算泄露。
- 探针 vs final_v2 重叠 0；final_v2 内部无重复。
- E4 训练入口 `e4_run.train` 在加载模型前再做一次：final_v2 哈希必须一致、final_v2 不得出现在新数据/池/探针里，否则直接退出。

## 3. 自然语言期末 v2（冻结）

- 版本 `natural_final_v2`，合并哈希 `5dcc7d786fd60556e97d4e2ebefe143fdd9e96e9aa9052877a1317758b15a8f6`（= 四个文件 sha256 的规范 JSON 再取 sha256），每个文件哈希见 `data_ext_e4/final_v2/FROZEN.json`。任何改动必须换版本号。
- Database、Python：`data_round2/final` 原样拷贝（字节相同），与上轮直接可比。
- File：同样的 30 个 round2_final 实例，只把金标准改成最后一条匹配行，episode_id 前缀 `nf2-`。
  - **官方判分**：工具、参数、执行都对，且答案满足上轮 `ext_rescore` 的宽松规则：最后一行原文；或去掉 `line N: ` 的正文；或 `{line, text}` 且行号对。这和上轮主口径 `nat_fix` 完全一致。
  - 另报 strict（精确字符串）。上轮模型常答 `{line, text: 正文}`，所以 strict 明显偏低，只并列。
- Calendar（新）：6 种已训练技能 × 5 题 = 30 题，种子 20261122。技能：当日计数、月计数、当日标题排序、按标题片段找日期、参会人、最早空档。每种 3 套自然语言说法，不出现训练模板句式，答案格式在题面写清。判分与旧工具一样严：joint success + `answers_equal` 精确比较。
  - 优先选训练里没出现过的调用：search_dates、attendees、free_first 的调用与 Calendar 训练集 0 重叠；count_date、list_titles 各 1/5 重叠；count_month 只有 3 个月，5/5 重叠（fixture 限制）。
  - fixture 限制：每天都是 4 个会、时段一样，所以当日计数恒为 4、月计数恒为 20、最早空档恒为 10:00–11:00。这些题只在工具和参数选对时才算对，但答案本身可猜，已在报告中注明。
- 方法不可见：训练、复习、探针、选比例都不读 final_v2；每个完成的 run 只评一次。

## 3b. 补评结果：上轮 15 个 run 的 Calendar 自然语言 v2（只读评测，统一口径）

| 臂（E2，旧池） | 旧工具 nat old（官方，=上轮 nat_fix） | Calendar nat v2 | Calendar hist |
|---|---|---|---|
| none | 0.344±0.212 | 0.689±0.051 | 0.667±0.088 |
| tf00 | 0.374±0.210 | 0.700±0.033 | 0.644±0.102 |
| tf25 | 0.633±0.078 | 0.700±0.033 | 0.633±0.176 |
| tf50 | 0.830±0.080 | 0.711±0.019 | 0.456±0.158 |
| tf75 | 0.737±0.061 | 0.733±0.033 | 0.278±0.195 |
| 起点 stage_03（未学 Calendar） | – | 0.367±0.033 | – |

- Calendar 自然语言期末在各臂之间几乎走平（0.69–0.73），没有复现历史测试里“tf 越高 Calendar 越低”的下降。
- 按题型看（3 种子合并，joint）：count_date、free_first、attendees 在所有训练后臂上接近 1.0，起点分别是 0、0.60、1.00。list_titles 各臂都是 0.60，工具参数全对，错在答案。count_month 0.40–0.53，search_dates 0.27，各臂相同。说明 v2 Calendar 测的“已训练技能换说法”在 Calendar 学完后基本饱和，对复习比例不敏感。
- 历史 Calendar test 是 3 个**训练里没有的模板**（locations、attendees_count、free_slot_latest），下降集中在这里。所以更准确的说法是：高定向比例伤的是新工具向未训练子技能的泛化，不是已训练技能的自然语言执行。这需要 E4 干净池的结果再确认。
- 数据：`runs_ext_e4/e2_calnl/`；汇总在 `runs_ext_e4/report.md` 的 E2 行（链每个种子结束后会刷新）。

## 4. 链的步骤（全部跳过已完成）

| 步 | 内容 | 输出 | 估时（显卡空闲） |
|---|---|---|---|
| 0 | 数据不存在则构建；`scripts/test_e4_data.py` 单元+泄露检查 | `data_ext_e4/` | 秒级 |
| 1 | 烟测：seed108 tf00/tf50，16 条新样本、1 epoch、探针每工具 4 条、每套评测 3 题；`check-smoke` 通过写 `runs_ext_e4_smoke/SMOKE_OK`，否则 ABORT | `runs_ext_e4_smoke/` | ≈10 min（已完成） |
| 2 | calnl_old：Calendar 自然语言 v2 补评上轮 `runs_ext_tf` 15 个最终 checkpoint（只读）+ 3 个 stage_03 起点；每种子一个 GPU 任务；之后出一次报告 | `runs_ext_e4/e2_calnl/` | ≈12–15 min |
| 3 | 正式 E4：按种子优先，108 的 tf00→tf25→tf50→none → 109 → 110。每个 run 先训练再评测（历史 4 工具 + natural final v2 4 工具）。每个种子的 tf00 负责建新的共享前缀 `runs_ext_e4/prefixes/A_seed*`，其余臂复用。每个种子结束后更新报告 | `runs_ext_e4/branches/`、`evaluation/` | ≈20–25 min/种子 |
| 4 | 最终报告 | `runs_ext_e4/report.md`、`results.json` | 秒级 |

**全链估时**：显卡空闲时约 1 小时 50 分（11:07 启动，正式 E4 从 11:29 开始，每种子约 28 分钟，预计 13:00 前后结束，北京时间），每个 GPU 任务另有约 40 秒空闲门检查。用户玩游戏的等待时间另算。

设置与上轮 TF 扫描一致：A 顺序 stage 3→4（Calendar 新），batch 1、梯度累积 8、2 epoch、lr 1e-4，复习只在后半段，预算 = 新数据输入 token 的 10%，target 族权重各 1/3，探针 = monitor v2。唯一的区别是旧复习池 / target_ids 换成 `data_ext_e4`。因为池哈希变了，前缀要重建，不能复用 `runs_ext_tf/prefixes`。前缀本身只训练新数据，与池无关，所以和上轮前缀应几乎相同，但不保证逐位一致。

## 5. 每个 run 记录什么（`runs_ext_e4/results.json` → `rows`）

- 名义比例 `nominal_target_fraction`；实际比例三种：`actual_target_fraction_tokens`（输入 token）、`_supervised`（监督 token）、`_samples`（样本）。
- `replay_samples` / `replay_unique` / `replay_repeats`，`replay_input_tokens` / `replay_supervised_tokens`，`budget_input_tokens`，新数据 `new_input_tokens` / `new_supervised_tokens`。
- `by_family`：每技能的样本数、独立样本、重复、target 样本、target 独立样本，以及输入、监督、target 两种 token。
- `exposure_by_template`：每个“家族/模板”（例如 `file/e4_target_file_last_match`）的样本数、输入 token、监督 token，即每技能曝光量。
- 分数：`nat_file`（官方）、`nat_file_strict`、`nat_database`、`nat_python`、`nat_calendar`、`nat_old_macro`（主口径）、`nat_old_macro_strict`，`hist_*` 4 工具、`hist_old_macro`。
- 起点和中点的探针分、墙钟。
- 上轮 15 个 run（`round=E2`）用同一套函数补算。Calendar nat 来自补评；File 官方分 = 上轮 `nat_fix`；DB/Py 是同一份结果。

汇总（`report.md`）：
- 均值 ± 样本标准差。
- E4 臂内配对差：tf25−tf00、tf50−tf00、tf25−none、tf50−none、tf50−tf25、tf00−none。
- E4−E2 同臂同种子配对差：干净池与旧池对比。
- 配对 bootstrap 95% 区间（2000 次）给两种：种子+题目两级重抽，以及种子固定只抽题目。
- 全部臂在均值层面的非支配点（含 none/tf00，不偷偷排除基线）。
- 措辞不写“显著”。

## 6. 查看、停止、续跑

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
tail -n 30 logs_ext/e4_20261111.status      # START/DONE/FAIL/WAIT_GPU/ABORT/ALL_DONE
tail -n 50 logs_ext/e4_20261111.log
ps -p "$(cat logs_ext/e4_20261111.pid)" -o pid,etime,cmd
bash scripts/stop_e4.sh                      # 一键停止：写 stop 旗标并结束本链进程组
rm -f logs_ext/e4_20261111.stop && bash scripts/launch_e4_20261111.sh   # 续跑（跳过已完成）
.venv/bin/python -m fac_tinyagent.e4_run --phase report                  # 单独重出报告（CPU）
.venv/bin/python scripts/test_e4_data.py                                 # 单独复核数据（CPU）
```

PowerShell：

```powershell
wsl.exe -d Ubuntu -- bash -lc 'tail -n 30 "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/logs_ext/e4_20261111.status"'
wsl.exe -d Ubuntu -- bash -lc 'bash "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/scripts/stop_e4.sh"'
```

- 在训练中途中断：下次启动时，没有 `train_summary.json` 的分支会被改名为 `*_partial_<时间戳>` 放到一边再重训；已完成的分支和评测会跳过。
- 环境变量：`E4_SEEDS="20261108"`、`E4_ARMS="tf25 tf50"`、`E4_SKIP_CALNL_OLD=1`、`GATE_MEM_MIB=3500`。
- `stop_e4.sh` 只结束本链进程组和 `fac_tinyagent.e4_run` 进程，不碰游戏或其他任务。

## 7. 新增文件

- 代码：`fac_tinyagent/e4_data.py`（数据构建、检查器、verify）、`fac_tinyagent/e4_run.py`（train / eval / calnl-old / check-smoke / report、配对 bootstrap）
- 脚本：`scripts/run_e4_20261111.sh`、`scripts/launch_e4_20261111.sh`、`scripts/stop_e4.sh`、`scripts/test_e4_data.py`
- 数据和结果：`data_ext_e4/`、`runs_ext_e4/`、`runs_ext_e4_smoke/`
- 日志：`logs_ext/e4_20261111.{log,status,pid}`
- 文档：本文件

## 8. 已知问题与风险

1. Calendar fixture 太规整：3 类题的答案是常数，Calendar nat 会高估“答案层面”的掌握。主要区分度来自工具和参数选择、列表类答案。下一版若扩 fixture，必须换版本号。
2. File 官方判分沿用宽松规则，是为了与上轮主口径连续。干净池 target 教的是“原文整行”，所以 E4 的 strict 可能比 E2 涨得多，这部分是格式效应，读结果时要分开看官方和 strict。
3. 新前缀与上轮不是同一份文件。seed108 实测中点权重哈希与上轮不同，中点探针也略有差异：File 0.031 对 0.063，Python 0.688 对 0.656，是 GPU 非确定性造成的。E4−E2 差值里混着这部分前缀差异；E4 内部各臂共用同一前缀，臂间配对是干净的。
4. 烟测预算极小，16 条新样本只抽到 1 条 target（Python），没覆盖到 File target。正式 run 要看 `target_samples_by_family.file` 是否 > 0，并确认 plan 里没有旧 target id（check-smoke 已验证旧 id 不会出现）。
5. 只有 A 场景、3 个种子，bootstrap 区间只作描述。
6. Calendar nat v2 接近饱和（见 3b），对复习比例几乎不敏感。若要让新工具轴有区分度，应另建 v3：自然语言形式的未训练 Calendar 子技能，例如最晚空档、地点去重、参会人数。v2 已冻结，不能改。
7. 磁盘：C 盘剩约 73GB，本链新增预计 < 0.5GB。


## 9. 完成状态（2026-11-11 12:55，Asia/Shanghai，UTC+8）

链已正常结束，不必重启。

- 启动：2026-11-11 11:07:35，runner pid 535（`scripts/run_e4_20261111.sh`，setsid + nohup）
- 结束：2026-11-11 12:55:19，`ALL_DONE total=6464s`（约 1 小时 48 分），日志末行 `E4_FINISHED`
- 全部步骤 `rc=0`：数据检查、两组冒烟、`calnl_old` 三个种子、正式 12 个训练+评测（种子 20261108 / 20261109 / 20261110 × 臂 tf00 / tf25 / tf50 / none）、以及最终报告。本轮没有因游戏触发长时间 GPU 等待，任务之间只有常规的约 40 秒空闲门。
- 进程已退出，pid 535 不在。显卡在结束时空闲（约 3%，398 MiB）。
- 正式评测目录 12/12 齐全：`runs_ext_e4/evaluation/A_seed{20261108,20261109,20261110}_{tf00,tf25,tf50,none}/`
- 自动汇总已写好：`runs_ext_e4/report.md`、`runs_ext_e4/results.json`（mtime 12:55）
- 正式中文报告：`EXT_REPORT_20261111_e4_ZH.md`（数字从 JSON 复核）
- 给 ChatGPT 的草稿（未发送）：`scripts/gpt_bridge/msg_20261111_e4.md`

主口径结论见正式报告。一句话对照：旧工具 nat 官方 none 0.389±0.156、tf00 0.474±0.210、tf25 0.719±0.072、tf50 0.915±0.017；Calendar nat v2 各臂 0.678–0.711 走平；修好 File 后 tf50 的 File 为 0.789±0.019，不再随比例下降；E4 的历史 Calendar 在 tf50 为 0.689，不再出现 E2 的系统性下跌。tf25 / tf50 全部定向 run 的 `target_samples_by_family.file` 均大于 0。

注意：tf00 有两个种子（20261109、20261110）因均匀抽样抽到了 File target（各 2 条），均匀对照不是严格的“零 target”。seed 20261108 的历史 Calendar 在 tf25 仍从 0.800 掉到 0.467，不要写成新工具完全免疫。

## 10. 完成后如何复现与复核（CPU，不重训）

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
.venv/bin/python scripts/test_e4_data.py                    # 数据与泄露检查，应 ALL_PASS
.venv/bin/python -m fac_tinyagent.e4_run --phase report     # 仅重出报告，不占 GPU
# 若只想核对数字：
python3 -c "import json; d=json.load(open('runs_ext_e4/results.json',encoding='utf-8')); print(d['final_v2']); print(len(d['rows']))"
```

不要重跑已完成的链。若将来必须续跑，先确认没有健康的 runner，再：

```bash
rm -f logs_ext/e4_20261111.stop && bash scripts/launch_e4_20261111.sh
```

它会跳过已有 `train_summary.json` 的分支和已完成的评测。不要改已有 `runs_ext_tf/`、`.venv`，也不要覆盖 `data_ext_e4/`（构建脚本在数据已存在时会拒绝覆盖）。期末 v2 已冻结，改题必须换版本号。

下一步建议（详见正式报告第 10 节，尚未启动）：先建 Calendar v3 并只读补评本轮 / 上轮 checkpoint，同时离线校准 Monitor v2；然后再在 tf25 与 tf50 上做 E3 预算扫描 5/10/20%。
