# MMLU 上涨排查交接手册（2026-11-10）

更新日期：2026-11-10（Asia/Shanghai，UTC+8）  
适用对象：接手本轮 MMLU 排查的同学，或新的会话。  
项目根目录：`C:\Users\Egret\Desktop\oulu\Agent Self-Evolution\fac_tinyagent`  
WSL 路径：`/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent`（路径含空格，必须加引号）

本文只补充本轮排查链的运行、续跑、停止与结果位置。机器、三套 Python 环境、模型路径、磁盘和功耗等通用说明，仍以 [EXT_HANDOVER_20261110_ZH.md](EXT_HANDOVER_20261110_ZH.md) 和 [HANDOVER_ENVIRONMENT_ZH.md](HANDOVER_ENVIRONMENT_ZH.md) 为准。本轮结论见 [EXT_REPORT_20261110_mmlu_probe_ZH.md](EXT_REPORT_20261110_mmlu_probe_ZH.md)。

## 1. 一句话现状

MMLU 排查链已经在 2026-11-10 20:56:38（Asia/Shanghai）正常结束，日志中有 `ALL_DONE` 和 `PROBE_FINISHED`。计划中的阶段轨迹、chat / continuation / generative 对照、以及 A109 / B108 / A110 三个最终 adapter 的默认全量 MMLU **全部跑完，没有因 4 小时预算跳过任务**。显卡当前应为空闲。不要重跑或覆盖已有 `runs_ext_eval/` 目录，不要改已有 `runs*`、`.venv`、conda `zxx`，也不要动桌面 `oulu\Small Agent`。

## 2. 机器与进入方式（摘要）

必须使用 `wsl.exe -d Ubuntu -- bash -lc '...'`。默认 WSL 发行版是 `docker-desktop`，漏写 `-d Ubuntu` 会进错环境。PowerShell 会展开 `$VAR`，也不把 `\"` 当作转义引号；长流程写成 `.sh` 再在 Ubuntu 里跑。需要在 Windows 侧写文件时，用 `[System.IO.File]::WriteAllText(path, text, UTF8)`。一次只跑一个 GPU 任务。功耗仍由奥创控制中心管理，不要用 `nvidia-smi -pl`。

## 3. 本轮脚本、日志与状态文件

均在项目内，本轮新增脚本不要改，除非有明确需要并先备份。

| 文件 | 作用 |
|---|---|
| `scripts/run_mmlu_probe_20261110.sh` | 排查主链。可续跑：若 `$OUT/results.json` 已有对应任务的 acc / exact_match，会 `SKIP_EXISTS`。 |
| `scripts/stop_mmlu_probe.sh` | 停止：写入 stop flag，并结束 runner 进程组。已完成的 `results.json` / `samples.json` 不会删除。 |
| `scripts/wait_mmlu_probe.sh` | 等待 pid 退出后打印 status 和日志尾。本轮已结束，不必再跑。 |
| `scripts/eval_general.sh` / `scripts/eval_general.py` | 实际评测入口，环境为 `/home/egret/venvs/fac-eval`。 |
| `logs_ext/mmlu_probe_20261110.log` | 主链标准输出（含 lm-eval 进度）。 |
| `logs_ext/mmlu_probe_20261110.status` | 一行一条的 START / DONE / SKIP / FAIL / PHASE / ALL_DONE。 |
| `logs_ext/mmlu_probe_20261110.pid` | 启动时写入的 runner pid。结束时文件还在，但进程已不存在；当前记录的是成功那一轮的 pid 498。 |
| `logs_ext/mmlu_probe_20261110.stop` | 停止旗标。正常结束时不应依赖它；若存在，重新开跑前先删掉，否则脚本会在任务之间直接退出。 |

评测本身在 `HF_HUB_OFFLINE=1`、`HF_DATASETS_OFFLINE=1` 下离线进行。脚本在个别任务失败时会临时联网预取 `cais/mmlu`，本轮成功重启后未再需要预取。

## 4. 如何查看、续跑和停止

在 Ubuntu WSL、项目根目录下：

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
tail -n 30 logs_ext/mmlu_probe_20261110.status
ps -p "$(tr -d ' \n' < logs_ext/mmlu_probe_20261110.pid)" -o pid,etime,cmd || echo "runner not running"
nvidia-smi
```

从 PowerShell：

```powershell
wsl.exe -d Ubuntu -- bash -lc 'tail -n 30 "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/logs_ext/mmlu_probe_20261110.status"'
```

**本轮已经结束，默认不要再启动这条链。** 若将来因新需求续跑（脚本会跳过已有完整 `results.json`）：

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
rm -f logs_ext/mmlu_probe_20261110.stop
# 确认没有其它 GPU 任务后再启动
nohup bash scripts/run_mmlu_probe_20261110.sh >> logs_ext/mmlu_probe_20261110.log 2>&1 &
```

注意：

- 不要把 `--output` 指回已有目录来“重跑一遍”，以免覆盖本日结果。若必须重做某一项，换新的输出目录名，或先备份再删该目录的 `results.json`。
- 环境变量 `PROBE_BUDGET_SECS` 默认 14400；`PROBE_GEN_LIMIT` 可强制指定生成口径的每科题量。
- 脚本会用刚完成任务的墙钟更新后续估计。本轮在生成口径（实际约 106–116 秒）之后，把全量 MMLU 的估计误写成了 116 秒（status 末尾 `est_full_ll=116s`）。因为当时剩余预算很充裕，没有造成跳过；以后若预算变紧，这个估计可能让脚本误以为来得及、或反过来用过小的 estimate 去比较。必要时在续跑前把估计逻辑改得更保守，或手动设一个较大的剩余预算。
- 生成口径的每科题量是脚本按剩余时间算的，本轮为 15，不是全量。

只有用户或负责人明确要求停止时才执行：

```bash
bash scripts/stop_mmlu_probe.sh
```

正在跑的那一个任务可能不完整，已经写好的结果会保留；再启动主链时会重试没有完整 `results.json` 的目录。

## 5. 本轮时间线与运行问题

- **19:33:02** 第一次启动。当时 GPU 上可能还有其它评测，`eval_general.sh` 的占用守卫返回 rc=3，stage_01/02/03 和 `q06b_base_mmlu_full_chat` 在 status 里记为 `FAIL ... rc=3 wall=0s`，并触发了一次 `cais/mmlu` 预取。这些失败没有写出有效 `results.json`。
- **19:34:30** 重新启动（日志中的 `===== LAUNCH ... =====`），runner pid 498，之后全部成功。
- **19:34:30–19:55:48** PHASE 1：A108 stage_01/02/03 默认全量 MMLU。
- **19:55:48–20:09:06** PHASE 3a：基座与 A108 stage_04 的 chat-template MMLU。
- **20:09:06–20:32:41** PHASE 3b：`mmlu_continuation` 全量，基座墙钟 631 秒，stage_04 为 783 秒。
- **20:32:41–20:36:44** PHASE 3c：先跑 `limit=1` 估时（墙钟 21 秒，`TIME_L1=18s`，小于脚本里的 30 秒阈值，因此 `GEN_LIMIT` 按剩余时间落到 15），再跑基座与 stage_04 的 `l15`。
- **20:36:44–20:56:38** PHASE 2：A109、B108、A110 最终 adapter 的默认全量 MMLU，各约 397–399 秒。
- **20:56:38** `ALL_DONE rem=9472s`，`PROBE_FINISHED`。整链约 82 分钟，预算未用完。

其它注意点：

- 没有 `SKIP_BUDGET`，成功重启后也没有 `SKIP_EXISTS`（沿用的基座 / A108 stage_04 默认全量不在这条链里重跑）。
- `results.json` 里的 `peak_gpu_gb` 仍可能超过 11，与 8GB 物理显存不符，不要当真实占用。
- Chat 口径的样本 prompt 在 assistant 侧带有 `<think>` 前缀，属于评测协议问题，不是训练代码改出来的；以后若要重做 chat 对照，应先确认关闭 thinking、并且字母打分发生在正常的 assistant 回复位置。
- 基座与 A108 stage_04 的默认全量目录是本日稍早留下的，没有 `samples.json`。本轮新目录都有样本。不要为了补样本去覆盖这两个目录。
- 不要启动第二路 GPU 任务，不要改项目 `.venv` 或 conda `zxx`。

## 6. 结果目录清单

均在 `runs_ext_eval/` 下。不要删除或覆盖。

| 目录 | 口径 | 题量 | 主要结果 |
|---|---|---:|---|
| `q06b_base_mmlu_full` | 默认字母 | 14042 | acc 0.3431 |
| `q06b_A108_stage01_mmlu_full` | 默认字母 | 14042 | acc 0.3494 |
| `q06b_A108_stage02_mmlu_full` | 默认字母 | 14042 | acc 0.3683 |
| `q06b_A108_stage03_mmlu_full` | 默认字母 | 14042 | acc 0.3645 |
| `q06b_A108_stage04_mmlu_full` | 默认字母 | 14042 | acc 0.3699 |
| `q06b_base_mmlu_full_chat` | chat 字母 | 14042 | acc 0.3165 |
| `q06b_A108_stage04_mmlu_full_chat` | chat 字母 | 14042 | acc 0.3011 |
| `q06b_base_mmlu_continuation_full` | 选项正文 | 14042 | acc 0.2847 |
| `q06b_A108_stage04_mmlu_continuation_full` | 选项正文 | 14042 | acc 0.2835 |
| `q06b_base_mmlu_generative_l1` | 生成，仅估时 | 57 | exact_match 0.2456，无标准误 |
| `q06b_base_mmlu_generative_l15` | 生成 | 855 | exact_match 0.2398 |
| `q06b_A108_stage04_mmlu_generative_l15` | 生成 | 855 | exact_match 0.3322 |
| `q06b_A109_stage04_mmlu_full` | 默认字母 | 14042 | acc 0.3585 |
| `q06b_B108_stage04_mmlu_full` | 默认字母 | 14042 | acc 0.3577 |
| `q06b_A110_stage04_mmlu_full` | 默认字母 | 14042 | acc 0.3616 |

每个目录通常还有 `eval.log`；除两个较早的默认全量目录外，都有 `samples.json`。无关的旧目录（如 `q06b_base_arc_mmlu_full`，只有失败日志）不要误当成这轮结果。

## 7. 建议的下一步（且不要覆盖本轮结果）

本轮已经足以把“默认 MMLU 上涨”从知识增益里拆出来，不必为了同一问题再占一整晚 GPU。若还要补证据，优先换新目录：

1. **如需补默认口径最关键一对的逐题样本**，把基座和 A108 stage_04 的默认 MMLU 再跑一遍并打开 `--log-samples`，输出到新目录（例如 `q06b_base_mmlu_full_s`），不要写回 `q06b_base_mmlu_full`。用于核对字母偏好和改对 / 改错。
2. **若做 chat 对照，先修好模板**（关闭 thinking，避免在 `<think>` 后对字母计分），再比较。
3. 生成口径若要写进主表，需要全量或至少明显大于 855 题，并同时报告官方过滤器与宽松字母抽取。
4. 按原计划把 1.7B 正式跑起来，并把工具测试集扩大；通用能力评测不要和训练抢同一张显卡。
5. 监测集改为自然表述、补 KL / 自生成回放 / 权值插值等对比，属于论文方法主线，与本轮排查分开排期。

## 8. 不要动什么

- 不要改、不要重跑覆盖已有 `runs*`（包括 `runs_phase2/`、`runs_ext_eval/`、`runs_smoke_1p7b/` 等）。
- 不要改项目 `.venv`，不要改 conda `zxx`，不要在 `oulu\Small Agent` 里做任何事。
- 不要修改旧报告 `EXPERIMENT_REPORT_ZH.md`、`EXT_REPORT_20261110_ZH.md` 和上一份交接手册，除非有单独安排。本轮只新增了：
  - `EXT_REPORT_20261110_mmlu_probe_ZH.md`
  - `EXT_HANDOVER_20261110_mmlu_probe_ZH.md`