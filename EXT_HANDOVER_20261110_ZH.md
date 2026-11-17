# 扩展工作交接手册（2026-11-10）

更新日期：2026-11-10（Asia/Shanghai，UTC+8）  
适用对象：接手本日扩展工作的同学，或新的会话。  
项目根目录：`C:\Users\Egret\Desktop\oulu\Agent Self-Evolution\fac_tinyagent`  
WSL 路径：`/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent`（路径含空格，必须加引号）

本文补充、不替代既有环境文档 [HANDOVER_ENVIRONMENT_ZH.md](HANDOVER_ENVIRONMENT_ZH.md) 和项目级报告 [EXPERIMENT_REPORT_ZH.md](EXPERIMENT_REPORT_ZH.md)。本日实验结果见 [EXT_REPORT_20261110_ZH.md](EXT_REPORT_20261110_ZH.md)。仓库中**没有** `EXTENSION_ENV_ZH.md`，因此环境与两套虚拟环境的说明写在本文第 2–3 节，请不要回头去改旧文件。

## 1. 一句话现状

0.6B 的三项全量通用评测已经跑完（ARC-Easy 略降但不显著，IFEval 持平，MMLU 上升且待验证原因）；1.7B 冒烟流程已跑通；1.7B / 4B 权重已在本地。下一步优先查 MMLU 上涨原因，再做 1.7B 正式 A 顺序实验。显卡当前应为空闲。不要重跑已完成的 `runs_ext_eval/` 目录，不要改已有 `runs*`、`.venv` 或旧报告。

## 2. 机器与进入方式

| 项目 | 实际值 |
|---|---|
| 宿主机 | Windows 11，机器名 LAPTOP-GS5D6S47 |
| GPU | NVIDIA GeForce RTX 4060 Laptop，8188 MiB |
| 内存 | 约 32GB 物理内存 |
| WSL | Ubuntu 26.04 LTS（resolute），WSL2，用户 `egret` |
| **默认 WSL 发行版** | **`docker-desktop`，不是 Ubuntu** |
| 进入命令 | 必须使用 `wsl.exe -d Ubuntu -- bash -lc '...'` |
| 模型盘 | WSL 原生盘 `/home/egret/models/` |
| 项目盘 | `/mnt/c/...`（Windows 文件系统，比 `/home` 慢） |

核对时可见：`wsl.exe -l -v` 中带 `*` 的是 `docker-desktop`。如果漏写 `-d Ubuntu`，命令会进错发行版，表现为找不到 `/home/egret`、找不到项目 `.venv`，或根本没有 GPU 环境。

从 PowerShell 调用时注意：

- PowerShell 会展开 `$VAR`，也不把 `\"` 当作转义引号。长命令不要在 PowerShell 里手工拼复杂引号。
- 推荐：先把流程写成 `.sh`，再 `wsl.exe -d Ubuntu -- bash -lc 'cd ".../fac_tinyagent" && nohup bash scripts/xxx.sh > logs_ext/xxx.log 2>&1 &'`。
- 需要在 Windows 侧写文件时，优先用 `[System.IO.File]::WriteAllText(path, text, UTF8)` 或 here-string，不要用 `\"`。

本文撰写时磁盘大致为：C: 总量 927G，已用约 851G，剩余约 77G（92%）；WSL 根分区 `/dev/sdd` 剩余约 922G。当日上午的 [HANDOVER_ENVIRONMENT_ZH.md](HANDOVER_ENVIRONMENT_ZH.md) 曾记录 C: 仅剩约 16G，以当时文档为准，**新实验启动前仍应先 `df -h /mnt/c /home`**。

功耗：安静模式下 GPU 功耗会被压到大约 33W，评测/训练会明显变慢。需要在 **奥创控制中心（Armoury Crate）改到狂暴模式**，功率大约可以到 60–80W。这台机器上 `nvidia-smi -pl` **不受支持**，不要靠它改功耗上限。改模式不必停掉正在跑的评测。

其它程序常占 1–2GB 显存（Wallpaper Engine、Steam、Edge、NVIDIA Overlay 等）。Windows 小组件（WidgetService / WidgetBoard）、Windows Defender、Chrome 会占用较多 CPU。开跑前先看 `nvidia-smi` 和任务管理器。**一次只跑一个 GPU 任务。**

## 3. 三套 Python 环境（不要混用）

本日扩展引入了独立的评测环境，**没有改项目 `.venv`**。

### 3.1 训练 / 原流程：项目 `.venv`

- 位置：`fac_tinyagent/.venv`（WSL：项目根下 `.venv/bin/python`）
- Python 3.12.16，torch 2.15.0+cu132，transformers 5.22.2，peft 0.21.2，bitsandbytes 0.50.2，accelerate 1.15.0
- 用途：`fac_tinyagent.ext_sweep`、原 Phase 2 / replay / Round 2 训练与工具评估、1.7B 冒烟
- 不要在这个环境里 `pip install lm-eval` 或升级 torch / transformers
- 完整锁定仍见 `requirements.lock.txt`；细节见旧交接文档第 3 节

### 3.2 通用能力评测：`/home/egret/venvs/fac-eval`

- 位置：WSL 原生盘 `/home/egret/venvs/fac-eval`
- 由 `scripts/setup_fac_eval.sh` 创建，核心包版本与 `.venv` 对齐，并安装 **lm-eval 0.4.13**（`datasets` 5.2.0 等）
- 入口：`scripts/eval_general.sh` 默认调用 `/home/egret/venvs/fac-eval/bin/python`
- 冻结清单：`/home/egret/venvs/fac-eval/requirements.freeze.txt`
- IFEval 依赖 nltk `punkt_tab`。脚本会尝试安装；若官方 `nltk.download` 报 “Security Violation”，需按 `setup_fac_eval.sh` 把官方 zip 解到 `$HOME/nltk_data/tokenizers/`。早期 `q06b_base_ifeval_l100_chat` 就因此失败，后来已补好，全量 IFEval 已跑通。

### 3.3 BFCL：`/home/egret/venvs/bfcl-eval`

- 位置：`/home/egret/venvs/bfcl-eval`
- 版本：`bfcl-eval==2026.3.23`，`numpy==1.26.4`，`torch==2.15.0`
- 单独建环境的原因：bfcl-eval 钉死 numpy 1.26.4，会破坏 fac-eval 所需的 pyarrow / datasets
- **本日通用评测没有使用这个环境**；若以后做 Berkeley Function Calling 评测，只用这一套，不要装回 fac-eval 或项目 `.venv`
- 冻结清单：`/home/egret/venvs/bfcl-eval/requirements.freeze.txt`

另外，用户机器上还有名为 `zxx` 的 conda 环境。约束：**不要改 conda `zxx`，不要改项目 `.venv`，不要改已有 `runs*`。** 也不要在桌面 `oulu\Small Agent` 目录里做任何事。

## 4. 模型

| 模型 | WSL 路径 | 大小 | 状态 |
|---|---|---:|---|
| Qwen3-0.6B | `/home/egret/models/Qwen3-0.6B` | 1.5G | 先前已有，评测在用 |
| Qwen3-1.7B | `/home/egret/models/Qwen3-1.7B` | 3.8G | 本日下载，冒烟已用 |
| Qwen3-4B | `/home/egret/models/Qwen3-4B` | 7.6G | 本日下载，尚未训练/评测 |

下载脚本：`setup/download_model_ext.sh`（ModelScope，校验大小与 SHA256；失败时可回退 hf-mirror）。本地已齐，不要无故重下。检查 tokenizer / chat template：

```bash
.venv/bin/python setup/check_tokenizer.py --model /home/egret/models/Qwen3-1.7B
```

说明：`setup/check_tokenizer.py` 在本日扩展安装时被改过，仅增加了可选参数 `--model`、`--max-length`，默认值与原来相同。改前副本在 `backup_before_ext_20261110/setup/check_tokenizer.py`。不要再改这个文件，除非有明确需要并先备份。

## 5. 目录地图

### 5.1 旧内容（只读，不要改、不要重跑覆盖）

- 报告与协议：`EXPERIMENT_REPORT_ZH.md`、`HANDOVER_ENVIRONMENT_ZH.md`、`REPLAY_STUDY_PROTOCOL.md`
- 环境：`.venv/`、`requirements.lock.txt`、`environment_report.json`、`environment_report.txt`
- 数据：`data/`、`data_phase2/`、`data_phase2_smoke/`、`data_replay_study/`、`data_round2/`、`data_smoke/` 等
- 已有运行产物：`runs/`、`runs_phase2/`、`runs_phase2_full/`、`runs_phase2_smoke/`、`runs_smoke/`、`runs_replay_study_*`、`runs_round2/`、`runs_round2_c/`、`runs_monitor_experiments/`、`runs_overnight_diagnosis_*`、`runs_round2_smoke_v1/`、`data_round2_failed_001/`
- 旧配置：`configs/phase1.json`、`configs/phase2_base.json`、`configs/phase2_smoke.json`、`configs/local_full.json`、`configs/smoke.json`、`configs/phase2/*.json`
- 旧源码：`fac_tinyagent/` 下除 **`ext_sweep.py`** 以外的模块（`phase2_sweep.py` 等保持原默认行为）
- 本日评测读取但不准改写的 adapter：`runs_phase2/A_seed20261108/checkpoints/stage_04_calendar`

### 5.2 本日新增或本日产生（已核对存在）

注意：任务简述里的 `fac_tinyagent/ext_sweep` 实际是**模块文件** `fac_tinyagent/ext_sweep.py`，不是目录。

```text
configs/ext/
  qwen3_1p7b_phase2_smoke.json    # 已用于冒烟
  qwen3_1p7b_phase2.json          # 正式 1.7B（尚未跑，输出将到 runs_ext_phase2_1p7b）
  qwen3_4b_phase2_smoke.json      # 4B 冒烟配置（尚未跑）
  qwen3_4b_phase2.json            # 正式 4B（尚未跑，输出将到 runs_ext_phase2_4b）
fac_tinyagent/ext_sweep.py        # 不改写 data*/、不覆盖 configs/phase2/
scripts/
  eval_general.py / eval_general.sh
  build_mmlu_cache.py
  run_mmlu_after_cache.sh
  run_smoke_ext.sh
  setup_fac_eval.sh
  prefetch_eval_data.py           # 把 MMLU/ARC/IFEval 预取到 HF hub 缓存
setup/download_model_ext.sh
logs_ext/                         # 下载、环境安装、评测与缓存日志
runs_smoke_1p7b/                  # 1.7B 冒烟产物
runs_ext_eval/                    # 0.6B 通用评测产物
backup_before_ext_20261110/       # 安装前备份与扩展包
  ext_bundle_20261110.tgz
  install_ext.sh
  setup/check_tokenizer.py        # 改前副本
```

`scripts/` 整个目录是本日新建的。尚未出现、计划中的输出目录：`runs_ext_phase2_1p7b`、`runs_ext_phase2_4b`、`runs_smoke_4b`。

`runs_ext_eval/` 中与正式结论相关的目录见实验报告第 9 节。此外还有试跑或未完成目录，不要覆盖、也不要误当成全量结果：

- `_sanity_0p6b_arc5`：5 题连通性检查
- `q06b_*_arc_easy_l100`：100 题试跑
- `q06b_base_ifeval_l100_chat`：失败，无 `results.json`
- `q06b_base_arc_mmlu_full`：中途因网络超时停下，只有 `eval.log`

日志对应关系：

| 日志 | 含义 |
|---|---|
| `logs_ext/eval_general_0p6b_full_v2.log` | 成功的 ARC-Easy / IFEval 全量包装日志（14:10:43–16:55:21 CST） |
| `logs_ext/eval_general_0p6b_mmlu.log` | 失败的 MMLU（`.incomplete` 缓存） |
| `logs_ext/eval_general_0p6b_mmlu_v2.log` | 成功的缓存补全 + MMLU 全量（17:38:06–18:53:41 CST），含 `SUBJECTS 57 BAD []` |
| `logs_ext/build_mmlu_cache.log` | 较早一次不完整的缓存补全（仅 13 科），不要当成最终记录 |
| `logs_ext/smoke_1p7b.log` | 1.7B 冒烟过程日志 |

## 6. 运行问题与处理（本日踩过的坑）

1. **必须 `wsl.exe -d Ubuntu`。** 默认发行版是 `docker-desktop`。
2. **PowerShell 引号与变量展开。** 长流程写成 `.sh`，用 `nohup` 在 Ubuntu 里跑。
3. **hf-mirror / huggingface 经常超时。** 预取脚本是 `scripts/prefetch_eval_data.py`（已成功写入 hub 缓存：`cais/mmlu`、`allenai/ai2_arc`、`google/IFEval`）。即使 hub 缓存在，`datasets` 仍可能对每一科打 API，并在失败后留下 `.incomplete` 目录。
4. **MMLU 曾因 `college_computer_science` 缓存不完整失败。** 报错路径形如：
   `/home/egret/.cache/huggingface/datasets/cais___mmlu/college_computer_science/0.0.0/<rev>.incomplete/dataset_info.json`
   处理：先跑 `scripts/build_mmlu_cache.py`（从已有 hub 缓存把 57 科 load 到 datasets 缓存），再 `HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1` 离线评测。现成封装是 `scripts/run_mmlu_after_cache.sh`，但它会写入已有的 `q06b_base_mmlu_full` / `q06b_A108_stage04_mmlu_full`，**不要原样再跑**，以免覆盖本日结果。新的评测请换新的 `--output` 目录。
5. **安静模式功耗过低。** 到奥创控制中心切狂暴；不要用 `nvidia-smi -pl`。
6. **CPU / 显存被其它程序占用。** 关掉小组件、不用的 Chrome、NVIDIA Overlay 等。
7. **一次一个 GPU 任务。** `eval_general.sh` 和 `run_smoke_ext.sh` 若发现已有 `fac_tinyagent` / `eval_general` 进程会拒绝启动。
8. **ext_sweep 不会改写 `data*`。** 校验报告写到输出目录的 `data_verification.json`；解析后的 run 配置写到输出目录的 `_configs/`，不覆盖 `configs/phase2/`。若输出目录里已有未完成的同名 run，脚本会拒绝覆盖，需换 `--run-id-prefix` 或换输出根目录。
9. **正式 1.7B / 4B 配置是与 `fac_tinyagent.config.defaults()` 做 deep merge**，并不是完整复制 `configs/phase2_base.json`。因此 `evaluation.batch_size` 默认为 1。若希望接近 Phase 2 正式评估常用的较大 batch，需在配置里显式写出。`qwen3_1p7b_phase2.json` 当前 `test_limit=10`（测试集本身每族 30 题）。

## 7. 可直接复制的命令

以下均在项目根目录、Ubuntu WSL 内执行。先确认没有其它 GPU 任务：

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
nvidia-smi
ps -eo pid,etime,pcpu,cmd | grep -E "fac_tinyagent|eval_general" | grep -v grep || true
```

从 Windows PowerShell 进入同一目录：

```powershell
wsl.exe -d Ubuntu -- bash -lc 'cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent" && nvidia-smi'
```

### 7.1 评测一个已有 adapter 的通用能力

ARC-Easy（无 chat template，全量）：

```bash
bash scripts/eval_general.sh \
  --model /home/egret/models/Qwen3-0.6B \
  --adapter runs_phase2/A_seed20261108/checkpoints/stage_04_calendar \
  --tasks arc_easy \
  --batch-size 8 \
  --output runs_ext_eval/<新目录名>
```

IFEval（需要 `--chat-template`）：

```bash
bash scripts/eval_general.sh \
  --model /home/egret/models/Qwen3-0.6B \
  --adapter runs_phase2/A_seed20261108/checkpoints/stage_04_calendar \
  --tasks ifeval \
  --chat-template \
  --batch-size 8 \
  --output runs_ext_eval/<新目录名>
```

只评基座时去掉 `--adapter`。MMLU 建议先确保缓存完整，再离线跑，并换新的输出目录：

```bash
/home/egret/venvs/fac-eval/bin/python scripts/build_mmlu_cache.py
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
export HF_ENDPOINT=https://hf-mirror.com
bash scripts/eval_general.sh \
  --model /home/egret/models/Qwen3-0.6B \
  --adapter runs_phase2/A_seed20261108/checkpoints/stage_01_file \
  --tasks mmlu \
  --batch-size 16 \
  --output runs_ext_eval/<新目录名>
```

查结果：

```bash
python3 - <<'PY'
import json
p = "runs_ext_eval/<新目录名>/results.json"
d = json.load(open(p, encoding="utf-8"))
print("adapter", d["adapter"], "chat", d["chat_template"], "peak", d["peak_gpu_gb"])
print(json.dumps(d["results"], indent=2, ensure_ascii=False)[:2000])
PY
```

评测 stage 轨迹时，把 `--adapter` 依次换成：

- `runs_phase2/A_seed20261108/checkpoints/stage_01_file`
- `runs_phase2/A_seed20261108/checkpoints/stage_02_database`
- `runs_phase2/A_seed20261108/checkpoints/stage_03_python`
- `runs_phase2/A_seed20261108/checkpoints/stage_04_calendar`

其它 seed 的路径是 `runs_phase2/A_seed20261109/...`、`runs_phase2/B_seed20261108/...` 等。输出目录必须是新名字，不要写回本日已经完成的 `q06b_*_full*`。

### 7.2 再跑一次 1.7B 冒烟（一般不必）

已完成的结果在 `runs_smoke_1p7b/`。若只是复查，直接读 `smoke_summary.txt` 和 `A_seed20261108/ext_meta.json`。若要重跑，**换一个新的输出目录**，例如：

```bash
bash scripts/run_smoke_ext.sh \
  configs/ext/qwen3_1p7b_phase2_smoke.json \
  runs_smoke_1p7b_rerun \
  A 20261108 3
```

该脚本会用项目 `.venv` 调用 `python -m fac_tinyagent.ext_sweep`，并每 2 秒记录整卡显存。默认时间预算 2400 秒。

### 7.3 1.7B 正式 A 顺序（尚未跑）

建议先写成脚本并用 `nohup` 启动，输出放到新目录 `runs_ext_phase2_1p7b`（目前不存在）：

```bash
.venv/bin/python -u -m fac_tinyagent.ext_sweep \
  --config configs/ext/qwen3_1p7b_phase2.json \
  --output-root runs_ext_phase2_1p7b \
  --orders A \
  --seeds 20261108 \
  --test-limit 10
```

`--test-limit 10` 与当前配置一致，是扩大后的评测，但仍不是每族 30 题全量。若要全量，需明确改 `test_limit` 并评估时间。跑之前确认奥创为狂暴模式、磁盘空间足够、没有其它 GPU 任务。

4B 可先尝试 `configs/ext/qwen3_4b_phase2_smoke.json` 输出到新目录（如 `runs_smoke_4b`）。若显存不够或过慢，改到云端，不要反复在本机硬跑覆盖其它产物。

### 7.4 后台启动模板

```bash
mkdir -p logs_ext
nohup bash scripts/<your_script>.sh > logs_ext/<name>.log 2>&1 &
echo $!
tail -f logs_ext/<name>.log
```

## 8. 本日结果速查

详细数字、σ 计算和解释见 [EXT_REPORT_20261110_ZH.md](EXT_REPORT_20261110_ZH.md)。这里只列正式全量结果，避免和试跑混淆：

| 任务 | 基座 | Adapter（A / seed 20261108 / stage_04） | 简评 |
|---|---|---|---|
| ARC-Easy acc（2376） | 0.5699 | 0.5438 | 下降约 1.8σ，不可算显著 |
| IFEval prompt_strict / loose（541，chat） | 0.4732 / 0.5360 | 0.4769 / 0.5194 | 无明显变化 |
| MMLU acc（14042，无 chat） | 0.3431（se 0.0039） | 0.3699（se 0.0040） | 上升约 4.8σ，四大类全涨；优先怀疑格式效应 |
| 1.7B smoke | 流程成功，WALL 562 s，整卡峰值 6256 MiB，每族 3 题 | 不可解释能力 |

MMLU 的 `peak_gpu_gb` 记录约为 11GB，超过 8GB 物理显存，统计口径待查。

## 9. 约束与红线

- 不修改、不删除、不覆盖：项目 `.venv`、conda `zxx`、已有 `runs*`（含本日已经写完的 `runs_ext_eval` 与 `runs_smoke_1p7b`）、已有报告。
- 不在桌面 `oulu\Small Agent` 里做任何事。
- 一次只跑一个 GPU 任务。
- 新评测、新训练一律使用新的输出目录。
- 1.7B 冒烟的每族 3 题分数不得写入论文或当成正式结论。
- 不要把 MMLU 上涨直接写成“知识提升”。

## 10. 下一步清单

1. **先查 MMLU 上涨的原因**：测同一 run 的 stage_01–stage_04 轨迹；补多种子；增加 chat template 与生成式口径。必要时加“仅旧工具数据”的对照 adapter。
2. **1.7B 正式跑 A 顺序**（扩大测试集，至少按当前配置的每族 10 题，再决定是否上到 30 题）；然后再跑 4B（本机可能不够，准备云端方案）。
3. **加强基线**：KL 正则、自生成回放、权重插值 / 模型合并。
4. **修监测盲区**：监测集改用自然表述，而不是模板题。
5. **把通用能力评测纳入每轮正式实验**，与工具指标一起出报告，并继续“每轮运行完毕后写实验报告和交接手册”。

## 11. 接手检查清单

1. `wsl.exe -d Ubuntu` 进入项目根目录，而不是默认的 docker-desktop。
2. `nvidia-smi` 确认显卡空闲；需要跑长时间任务时先把奥创调到狂暴模式。
3. `df -h /mnt/c /home` 确认磁盘。
4. 确认三套环境还在：项目 `.venv`、`/home/egret/venvs/fac-eval`、`/home/egret/venvs/bfcl-eval`。
5. 先读 `EXT_REPORT_20261110_ZH.md` 与本手册，再读旧的 `EXPERIMENT_REPORT_ZH.md`。需要数字时打开 `results.json`，不要凭记忆。
6. 新实验先写脚本和输出目录名，再用 `nohup` 启动；不要在已有正式结果目录上重跑。
