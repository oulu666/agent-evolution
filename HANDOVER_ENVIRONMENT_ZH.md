# FAC-TinyAgent 实验环境交接文档

更新日期：2026-11-10  
适用对象：接手本项目的同学、新的 Claude Code 会话、或需要复现/继续实验的协作者。  
项目根目录：`C:\Users\Egret\Desktop\oulu\Agent Self-Evolution\fac_tinyagent`（WSL 内为 `/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent`）。

## 0. 一句话结论

实验运行在 **Windows 11 + WSL2 Ubuntu 26.04** 上，使用项目内 `.venv` 的 Python 3.12.16、torch 2.15.0+cu132、transformers 5.22.2、peft 0.21.2、bitsandbytes 0.50.2；模型为本地 `/home/egret/models/Qwen3-0.6B`；GPU 为 RTX 4060 Laptop 8GB，BF16 可用；当前瓶颈是 **C: 磁盘空间**，不是 RAM。

## 1. 宿主机与硬件

| 项目 | 实际值 |
|---|---|
| 宿主机 | Windows 11 Home China，10.0.26200 |
| CPU | WSL 可见 32 个逻辑处理器 |
| 物理内存 | 31.2GB 总量；交接时约 12.4GB 空闲 |
| WSL 内存 | 15GiB 总量；交接时约 1GiB 使用、13GiB 空闲 |
| WSL swap | 4GiB |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU，8188MiB |
| NVIDIA 驱动 | 621.01 |
| GPU 当前占用 | 约 1.8GB（空闲，可继续训练） |
| C: 磁盘 | 927GB 总量，约 911GB 已用，**仅约 16GB 空闲（99%）** |

### 磁盘现状

项目自身约 **8.2GB**：

| 内容 | 大小 |
|---|---:|
| `.venv`（58 个锁定包） | 5.5GB |
| `runs_phase2`（9 个 run 的 checkpoints/评估） | 1.1GB |
| `runs_round2` / `runs_round2_c` | 约 0.9GB |
| `runs_replay_study_v2` | 369MB |
| `runs_replay_study_20261109`（已作废 v1） | 66MB |
| `runs_round2_smoke_v1` / `runs_smoke` | 约 184MB |
| Qwen3-0.6B 模型（WSL `/home`） | 1.5GB |

C: 剩余空间主要被其他 Windows 数据占用。**不要在没有确认的情况下删除 `runs_phase2`、`runs_replay_study_v2`、`runs_round2`、`runs_round2_c` 或 `.venv`**；这些是复现实验和二次分析所需。可安全清理的候选：作废的 v1、旧 smoke、pip/HuggingFace 缓存（约 0.6GB）。

## 2. WSL2 环境

| 项目 | 实际值 |
|---|---|
| 发行版 | Ubuntu 26.04 LTS（resolute） |
| 内核 | 6.18.33.2-microsoft-standard-WSL2 |
| 架构 | x86_64 |
| 进入方式 | `wsl.exe -d Ubuntu -- bash -lc '...'` |
| WSL 项目路径 | `/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent` |
| WSL 用户 | `egret`（项目文件在 `/mnt/c`，模型在 `/home/egret`） |

注意：

- WSL 通过 Windows 的 NVIDIA 驱动使用 GPU，**没有在 WSL 内单独安装系统 CUDA**；`torch 2.15.0+cu132` 的 wheel 自带 CUDA 13.2 运行时。
- 路径含空格，所有 `cd` 和文件参数都要加引号。
- 从 Windows 侧调用 WSL 时，优先使用：
  ```bash
  wsl.exe -d Ubuntu -- bash -lc 'cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent" && .venv/bin/python -m <module>'
  ```

## 3. Python 与依赖

### 3.1 虚拟环境

- 位置：`fac_tinyagent/.venv`
- Python：3.12.16
- 激活：
  ```bash
  cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
  source .venv/bin/activate
  ```
- 直接调用（推荐脚本/后台任务）：
  ```bash
  .venv/bin/python -m fac_tinyagent.<module>
  ```

### 3.2 关键版本

| 包 | 版本 |
|---|---|
| torch | 2.15.0+cu132（CUDA build 13.2） |
| transformers | 5.22.2 |
| peft | 0.21.2 |
| bitsandbytes | 0.50.2 |
| accelerate | 1.15.0 |
| numpy | 2.5.4 |
| huggingface_hub | 2.4.0 |
| tokenizers | 0.23.3 |
| sentencepiece | 0.2.3 |
| safetensors | 0.8.0 |

完整锁定版本：`requirements.lock.txt`（58 个包；`pip list` 当前 59 项，包含 pip 等工具项）。

### 3.3 环境验证

已保存的环境报告：

- `environment_report.json`
- `environment_report.txt`
- Phase 2 每个 run 的 `environment_report.json/txt`，例如：
  `runs_phase2/A_seed20261108/environment_report.json`

关键结果：`pass: true`，CUDA available，BF16 supported，VRAM 8.0GB。

### 3.4 安装方式

已有脚本：

- `setup/bootstrap_wsl.sh`：安装 `uv` 与 Python 3.12。
- `setup/setup_wsl.sh`：创建 `.venv`、安装 torch/transformers/peft/bitsandbytes/accelerate/sentencepiece，并生成 `requirements.lock.txt`。
- `setup/check_tokenizer.py`：检查 Qwen chat template 与 assistant-only 标签。
- `setup/download_model.sh`：从 ModelScope 下载 Qwen3-0.6B 到 `/home/egret/models/Qwen3-0.6B`。

一般不需要重新安装；如果必须重建，请先确认 C: 磁盘空间。不要运行会升级 `torch`/`transformers` 的裸 `pip install`，否则可能破坏已跑结果的可复现性。

## 4. 模型

| 项目 | 实际值 |
|---|---|
| 模型 | Qwen3-0.6B |
| 本地路径 | `/home/egret/models/Qwen3-0.6B` |
| 主要文件 | `model.safetensors`（1.5GB）、`config.json`、`tokenizer.json`、`tokenizer_config.json`、`vocab.json`、`merges.txt`、`generation_config.json` |
| 下载来源 | ModelScope（Hugging Face CDN 曾超时） |
| 运行时网络 | 不需要联网；全部本地加载 |
| 量化 | 4-bit NF4，double quantization，compute dtype auto/BF16 |
| tokenizer | `trust_remote_code=True`，chat template 已开启；`<|im_start|>` / `<|im_end|>` 已用于 assistant span 检查 |

换模型时必须同步修改：

- `configs/*.json` 的 `model_name_or_path`
- 训练/评估的 `max_seq_length`（当前 1024）
- tokenizer/chat template 检查（`setup/check_tokenizer.py`）
- 依赖版本与显存预算

## 5. 训练与评估设置

### 5.1 QLoRA

| 参数 | 值 |
|---|---|
| 量化 | 4-bit NF4 + double quant |
| LoRA r | 8 |
| LoRA alpha | 16 |
| LoRA dropout | 0.05 |
| LoRA target modules | q/k/v/o/gate/up/down proj |
| learning rate | 1e-4 |
| batch size | 1 |
| gradient accumulation | 8 |
| epochs | 2 |
| max sequence length | 1024 |
| gradient checkpointing | true |
| optimizer | PagedAdamW 8-bit |
| loss | assistant-only；每个 episode 两个 assistant span |

### 5.2 评估

- 生成：greedy，`do_sample=false`。
- 批量：`evaluation.batch_size=32`（最终复核、夜间诊断、Round 2）；早期单题评估保留为独立记录。
- 每道题两次生成：先工具调用，后最终答案。
- 指标：工具选择、参数、执行、答案、联合成功率；答案与联合指标分开。
- 最大新 token：工具/答案各 128。

### 5.3 数据与隔离

| 数据 | 规模/位置 |
|---|---|
| Phase 1 | 3 族 × 80/20/30，`data/` |
| Phase 2 | 4 族 × 80/20/30，`data_phase2/` |
| Replay study | 每族 24 monitor + 60 sealed_test，`data_replay_study/` |
| Round 2 | 共同池 240 原始 + 41 定向；monitor 72；final 90，`data_round2/` |

原则：

- 最终测试不参与训练/选策略；`sealed_test` 不参与策略选择。
- Round 2 的 target pool、monitor、final 三者由 `data_round2/manifest.json` 记录哈希与隔离关系。
- 训练/验证/测试模板与实体尽量隔离；Phase 2 完整复核说明 6 题子集可能有抽样偏差。

## 6. 目录与关键产物

```text
fac_tinyagent/
├── .venv/                         # Python 环境（5.5GB）
├── configs/                       # Phase 1/2 配置
├── data/ data_phase2/             # 训练/验证/测试
├── data_replay_study/             # replay monitor + sealed test
├── data_round2/                   # Round 2 共同池 + monitor + final
├── fac_tinyagent/                 # 源码
│   ├── phase2_sweep.py            # 三顺序三种子扫参
│   ├── phase2_full_eval.py        # 最终 adapter 30 题复核
│   ├── replay_study.py            # v2 三臂研究与报告
│   ├── replay_train.py            # 共享前缀训练、targeted/adaptive plan
│   ├── overnight_diagnosis.py     # 夜间可续跑评估队列
│   ├── monitor_check.py           # probe start/mid/end 诊断
│   ├── experiment_a_cross_eval.py # 历史题 vs probe 交叉评估
│   ├── experiment_b_median_pairs.py
│   ├── round2_data.py             # 共同池/monitor/final 生成
│   ├── round2_study.py            # Round 2 A
│   └── round2_study_c.py          # Round 2 C
├── runs/                          # Phase 1
├── runs_phase2/                   # Phase 2 9 runs
├── runs_phase2_full/              # 30 题完整复核
├── runs_replay_study_v2_20261109/ # 预算复习 v2
├── runs_overnight_diagnosis_20261110/
├── runs_monitor_experiments/      # 交叉评估/中位数成对
├── runs_round2/                   # A 场景 12 分支
├── runs_round2_c/                 # C 场景 12 分支
├── setup/                         # 环境/模型/启动脚本
├── EXPERIMENT_REPORT_ZH.md        # 项目级完整报告
├── REPLAY_STUDY_PROTOCOL.md
└── requirements.lock.txt
```

## 7. 常用命令

以下命令均在项目根目录执行。

### 7.1 环境检查

```bash
.venv/bin/python -m fac_tinyagent.run env --output environment_report.txt
```

### 7.2 Phase 2 扫参

```bash
.venv/bin/python -m fac_tinyagent.phase2_sweep \
  --orders A B C \
  --seeds 20261108 20261109 20261110 \
  --test-limit 6
.venv/bin/python -m fac_tinyagent.phase2_report
```

### 7.3 Phase 2 最终 adapter 30 题完整复核

```bash
.venv/bin/python -m fac_tinyagent.phase2_full_eval
```

### 7.4 预算复习 v2

```bash
# 完整流程（已有产物会跳过）
.venv/bin/python -m fac_tinyagent.replay_study all

# 只重生成报告
.venv/bin/python -m fac_tinyagent.replay_study report
```

### 7.5 监测诊断

```bash
.venv/bin/python -m fac_tinyagent.monitor_check --order A
```

### 7.6 夜间诊断队列

```bash
# 完整队列（42 states / 216 units / 8208 evaluations，约 71 分钟）
.venv/bin/python -u -m fac_tinyagent.overnight_diagnosis \
  --profile full --pairs 96 \
  --output-root runs_overnight_diagnosis_20261110
```

- 中断后重复同一命令会跳过已校验完成的单元。
- `status.json` 中 `completed_units` 到 216 即完成。
- 小规模 smoke 建议使用单独目录，例如 `runs_overnight_diagnosis_smoke`。
- Windows 启动器：`START_OVERNIGHT_DIAGNOSIS.cmd` 或 `setup/start_overnight_diagnosis.ps1`。

### 7.7 Round 2 数据与 A/C 实验

```bash
# 生成共同池/独立 monitor/final；若 data_round2 已存在会拒绝覆盖
.venv/bin/python -m fac_tinyagent.round2_data
.venv/bin/python -m fac_tinyagent.round2_data --verify-only

# A 场景：12 分支
.venv/bin/python -u -m fac_tinyagent.round2_study \
  --seeds 20261108 20261109 20261110

# 只重生成 A 报告
.venv/bin/python -m fac_tinyagent.round2_study \
  --seeds 20261108 20261109 20261110 --report-only

# C 场景：12 分支
.venv/bin/python -u -m fac_tinyagent.round2_study_c \
  --seeds 20261108 20261109 20261110
```

### 7.8 CPU 测试

```bash
.venv/bin/python -m unittest discover -s tests -p "test_cpu.py" -v
```

注意：`.venv` 没有安装 `pytest`，不要用 `pytest` 命令。

## 8. 显存/进程注意事项

- 8GB 显存同时运行训练/多进程评估可能 OOM；训练峰值约 2–3GB，评估约 0.6–3.6GB。
- 如果 `nvidia-smi` 显示 Wallpaper Engine、Steam、Edge、NVIDIA Overlay 等占用显存，先关闭再跑。
- 不要同时启动两个训练/大评估任务；先确认：
  ```bash
  nvidia-smi
  ps -eo pid,etime,pcpu,cmd | grep -E "fac_tinyagent|python" | grep -v grep
  ```
- 复用已有模型时，模型加载/释放会占用数秒；后台任务完成后确认进程退出，再启动下一个。

## 9. 已知坑

1. **Hugging Face 下载超时**：曾改用 ModelScope；本地模型已完整，不要重复下载。
2. **WSL 路径/引号**：路径含空格，必须加引号；从 Windows 调用 WSL 时优先 `wsl.exe -d Ubuntu -- bash -lc '...'`。
3. **`.venv` 在 `/mnt/c`**：文件系统较慢，安装/加载模型比 WSL 原生盘慢；不要把它移到 `/home` 后忘记改命令。
4. **C: 磁盘接近满**：当前仅约 16GB；新增训练/检查点前先检查空间。`.venv` 5.5GB 是最大单项目；不要随意删除。
5. **旧 v1 已作废**：`runs_replay_study_20261109` 仅保留调试记录，三臂中点参数不同，不能用于功效结论。
6. **Phase 2 子集**：阶段矩阵是每族 6 题子集；只有最终 adapter 做了 30 题完整复核。
7. **第四个学习的族没有遗忘估计**：最后学习的工具没有后续再测，不能计算 peak→final 遗忘。
8. **probe 覆盖问题**：原 `study_*` probe 与历史掉分模板零重叠；不能把 probe 无下降解释为能力保留。
9. **sealed/final 使用限制**：sealed_test/final 不参与策略选择；Round 2 的 monitor、final、target pool 必须保持隔离。
10. **后台任务**：长任务用 `run_in_background`；完成后先看 `status.json`/日志，再启动新 GPU 任务。

## 10. 当前实验状态（交接时）

- Phase 1：完成。
- Phase 2：9 个 run + 30 题完整复核，完成。
- 预算复习 v2：9 个分支，完成；adaptive 0/3 触发。
- 监测诊断/夜间队列：完成（216/216）。
- Round 2 A：12 个分支、105 个评估单元，完成。
- Round 2 C：12 个分支、75 个评估单元，完成；adaptive 0/3 触发。
- 项目级报告：`EXPERIMENT_REPORT_ZH.md`。

## 11. 接手检查清单

1. 进入 WSL，`cd` 到项目根目录并激活 `.venv`。
2. 跑一次 CPU 测试，确认代码与数据可读。
3. 跑 `.venv/bin/python -m fac_tinyagent.run env`，确认 CUDA/BF16/显存。
4. 检查 `nvidia-smi` 与 `ps`，确认没有残留训练进程。
5. 检查 C: 剩余空间；不要在没有备份的情况下删除 runs/checkpoints。
6. 从 `EXPERIMENT_REPORT_ZH.md` 和各目录 `report.md` 读取结果；需要复现时优先用 `--report-only`，不要盲目重训。
7. 新实验先写协议/数据哈希/共享前缀校验，再启动长任务。

## 12. 关键文件索引

- 项目级报告：[EXPERIMENT_REPORT_ZH.md](EXPERIMENT_REPORT_ZH.md)
- Phase 2：[runs_phase2/reports/phase2_report.md](runs_phase2/reports/phase2_report.md)
- Phase 2 完整复核：[runs_phase2_full/report.md](runs_phase2_full/report.md)
- 预算复习 v2：[runs_replay_study_v2_20261109/report.md](runs_replay_study_v2_20261109/report.md)
- 监测诊断：[runs_replay_study_v2_20261109/monitor_probe_report.md](runs_replay_study_v2_20261109/monitor_probe_report.md)
- 交叉评估：[runs_monitor_experiments/cross_eval/report.md](runs_monitor_experiments/cross_eval/report.md)
- 中位数成对：[runs_monitor_experiments/median/report.md](runs_monitor_experiments/median/report.md)
- 夜间队列：[runs_overnight_diagnosis_20261110/analysis.md](runs_overnight_diagnosis_20261110/analysis.md)
- Round 2 A：[runs_round2/EXPERIMENT_REPORT_ZH.md](runs_round2/EXPERIMENT_REPORT_ZH.md)
- Round 2 C：[runs_round2_c/report.md](runs_round2_c/report.md)
- 环境报告：[environment_report.json](environment_report.json)、[environment_report.txt](environment_report.txt)
- 依赖锁定：[requirements.lock.txt](requirements.lock.txt)
