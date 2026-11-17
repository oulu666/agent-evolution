# 扩展工作实验报告（2026-11-10）

更新日期：2026-11-10（Asia/Shanghai，UTC+8）  
范围：本日在 Qwen3-0.6B 上补做的通用能力评测、Qwen3-1.7B 流程冒烟，以及 1.7B / 4B 模型下载。  
本文不替代项目级汇总报告 [EXPERIMENT_REPORT_ZH.md](EXPERIMENT_REPORT_ZH.md)；工具学习主实验的结论仍以该报告为准。  
数字均从 `runs_ext_eval/*/results.json` 与 `runs_smoke_1p7b/` 下的原始文件重新核对，不以口头汇报的四舍五入为准。

## 摘要

在已有 Phase 2 结果之外，本日用 lm-eval 0.4.13、评测种子 1234，对 **Qwen3-0.6B 4-bit 基座** 与 **A 顺序、seed 20261108、学完四类工具后的 `stage_04_calendar` adapter** 做了三项全量通用能力评测：

- **ARC-Easy** 全量 2376 题（无 chat template）：准确率由 0.5699 降到 0.5438，差值约 1.81σ。按常规 2σ 标准，**不能算显著下降**。
- **IFEval** 全量 541 题（使用 chat template）：严格口径整题准确率由 0.4732 升到 0.4769，宽松口径由 0.5360 降到 0.5194，变化都远小于一个标准误，**看不出明显遗忘或提升**。
- **MMLU** 全量 14042 题、57 科（无 chat template）：准确率由 0.3431（se 0.0039）升到 0.3699（se 0.0040），约 4.75σ；理科、文科、社科、其他四大类全部上涨，社科涨幅最大（约 4.2 个百分点）。

这三项放在一起，不能支持“学完四类工具后通用能力整体被遗忘”的判断，也不能支持“模型学到了新的世界知识”。当前最需要解释的是 MMLU 上涨：它更像是**输出分布 / 答题格式变化带来的打分效应**，而不是知识增长。该判断尚未被直接验证。

此外，Qwen3-1.7B 已在本机用原流程跑通 A 顺序冒烟（墙钟 562 秒，整卡显存峰值 6256 MiB，每族只评 3 题），**只能证明流程可跑，不能解释能力结果**。Qwen3-1.7B（约 3.8G）和 Qwen3-4B（约 7.6G）均已下载到 `/home/egret/models/`。

以上全部是**单一种子、单一 adapter** 的结果，还不能写成稳定规律。

## 1. 实验目的

既有工作已经说明：0.6B 连续学习四类工具后，工具选择与联合成功率会随阶段变化，监测题还存在覆盖盲区。本日要补的是另一条必要证据：

> 在学完 File / Database / Python / Calendar 之后，模型在常用通用基准上是掉了、持平，还是表面上涨？

如果通用能力出现大幅、稳定的衰退，这个方向的论文叙事需要改写；如果没有整体衰退，则工具学习的主要问题仍在旧工具保留、监测覆盖和复习策略，而不是“小模型一学工具就变笨”。

## 2. 评测设置

| 项目 | 实际值 |
|---|---|
| 基座 | `/home/egret/models/Qwen3-0.6B`，4-bit NF4 + double quant，compute dtype `torch.bfloat16` |
| Adapter | `runs_phase2/A_seed20261108/checkpoints/stage_04_calendar`（只读加载，不 merge） |
| 加载方式 | 与训练评估路径一致：`device_map={"": 0}`，再 `PeftModel.from_pretrained` |
| 评测库 | lm-evaluation-harness **0.4.13**，环境 `/home/egret/venvs/fac-eval` |
| 评测脚本 | `scripts/eval_general.py` / `scripts/eval_general.sh` |
| 评测种子 | 1234（同时写入 `random_seed` / `numpy_random_seed` / `torch_random_seed` / `fewshot_random_seed`） |
| few-shot | 0（lm-eval 任务配置中的 `num_fewshot` 为 0） |
| GPU | RTX 4060 Laptop，物理显存 8188 MiB |
| 对比性质 | 同一基座、同一 adapter、同一评测种子的前后对比；不是多种子平均 |

任务口径：

| 任务 | 题量 | chat template | 主要指标 | 结果目录 |
|---|---:|---|---|---|
| ARC-Easy | 2376（全量） | 否 | `acc`（同时记录 `acc_norm`） | `runs_ext_eval/q06b_base_arc_easy_full`、`q06b_A108_stage04_arc_easy_full` |
| IFEval | 541（全量） | 是（thinking 关闭） | prompt / inst × strict / loose | `runs_ext_eval/q06b_base_ifeval_full_chat`、`q06b_A108_stage04_ifeval_full_chat` |
| MMLU | 14042（57 科全量） | 否 | 选项对数概率打分的 `acc` | `runs_ext_eval/q06b_base_mmlu_full`、`q06b_A108_stage04_mmlu_full` |

MMLU 使用 `--batch-size 16`，并在缓存补全后以 `HF_HUB_OFFLINE=1`、`HF_DATASETS_OFFLINE=1` 离线评测，日志为 `logs_ext/eval_general_0p6b_mmlu_v2.log`。ARC-Easy 与 IFEval 的启动命令未单独存档，`eval_general.py` 默认批大小为 8，日志里没有打印实际批大小。

标准误均来自 lm-eval 输出。差值的 σ 按独立样本近似 \( |\Delta| / \sqrt{\mathrm{se}_1^2 + \mathrm{se}_2^2} \) 计算。两次评测用的是同一批题目，更严谨的做法是逐题配对检验，但本次 `log_samples=False`，没有保存逐题记录，因此下面的 σ 只是便于阅读的近似，不是正式假设检验。

## 3. 通用能力结果

### 3.1 ARC-Easy（全量 2376）

| 模型 | acc | acc se | acc_norm | acc_norm se | 墙钟 | 记录的 peak_gpu_gb |
|---|---:|---:|---:|---:|---:|---:|
| 基座 | 0.5699 | 0.0102 | 0.5324 | 0.0102 | 84.6 s | 2.359 |
| Adapter | 0.5438 | 0.0102 | 0.5034 | 0.0103 | 332.8 s | 2.378 |
| 差值 | −0.0261 | — | −0.0290 | — | — | — |

精确值：基座 `acc,none=0.5698653198653199`（se `0.01015913044517858`），adapter `0.5437710437710438`（se `0.0102203943837221`）。差值约 **1.81σ**（约 1.8σ）。按 2σ 标准，**不能称为显著下降**。方向是向下的，需要在多种子和更多阶段上再看是否稳定。

Adapter 墙钟明显长于基座，日志中出现过访问 Hugging Face / hf-mirror 超时重试，当时笔记本功耗模式也可能不同，不把墙钟差异解释成模型本身变慢。

曾做 100 题试跑（`q06b_base_arc_easy_l100`、`q06b_A108_stage04_arc_easy_l100`）：基座 acc 0.58、adapter 0.54，方向与全量一致，但样本量太小，不写入主结论。另有 5 题连通性检查 `_sanity_0p6b_arc5`，仅用于验证脚本。

### 3.2 IFEval（全量 541，chat template）

| 口径 | 基座 | 基座 se | Adapter | Adapter se | Δ | 约合 σ |
|---|---:|---:|---:|---:|---:|---:|
| prompt_strict（整题严格） | 0.4732 | 0.0215 | 0.4769 | 0.0215 | +0.0037 | 0.12 |
| inst_strict（指令严格） | 0.5875 | N/A | 0.5851 | N/A | −0.0024 | — |
| prompt_loose（整题宽松） | 0.5360 | 0.0215 | 0.5194 | 0.0215 | −0.0166 | 0.55 |
| inst_loose（指令宽松） | 0.6439 | N/A | 0.6259 | N/A | −0.0180 | — |

精确值：

- 基座：prompt_strict 0.4731977818853974，inst_strict 0.5875299760191847，prompt_loose 0.5360443622920518，inst_loose 0.6438848920863309
- Adapter：0.47689463955637706，0.5851318944844125，0.5194085027726433，0.6258992805755396

lm-eval 对 inst 级指标不提供 stderr。prompt 级两条变化都远小于 1σ，**应视为无明显变化**。墙钟：基座 4506.3 s，adapter 4936.2 s；记录的 peak_gpu_gb 分别为 3.538 与 3.557。

早期 100 题 IFEval 试跑目录 `q06b_base_ifeval_l100_chat` 只有 `eval.log`、没有 `results.json`，因当时 nltk `punkt_tab` 下载触发 “Security Violation” 失败；后来在 fac-eval 环境中手动解压了官方数据包，全量评测已成功。该失败试跑不进入结果表。

### 3.3 MMLU（全量 14042，无 chat template）

| 聚合 | n | 基座 acc | 基座 se | Adapter acc | Adapter se | Δ（百分点） |
|---|---:|---:|---:|---:|---:|---:|
| 总体 mmlu | 14042 | 0.3431 | 0.0039 | 0.3699 | 0.0040 | +2.68 |
| 理科 STEM | 3153 | 0.3029 | 0.0081 | 0.3283 | 0.0083 | +2.54 |
| 文科 Humanities | 4705 | 0.3171 | 0.0067 | 0.3309 | 0.0068 | +1.38 |
| 社科 Social Sciences | 3077 | 0.3968 | 0.0087 | 0.4391 | 0.0088 | +4.22 |
| 其他 Other | 3107 | 0.3701 | 0.0086 | 0.4026 | 0.0087 | +3.25 |

精确值：基座总体 `0.3431135165930779`（se `0.003948945370552919`），adapter `0.3698903290129611`（se `0.004017490118671915`）。差值约 **4.75σ**（约 4.8σ）。四大类全部上涨，社科最大。57 个学科的样本量与官方 MMLU 测试集一致，加权汇总与 lm-eval 的 `mmlu` 聚合键一致。

墙钟：基座 324.1 s，adapter 439.4 s。`results.json` 记录的 `peak_gpu_gb` 分别为 **10.999** 与 **11.018**，超过本机 8GB 物理显存。该字段来自 `torch.cuda.max_memory_allocated() / 1024**3`，可能包含共享内存、统一内存或统计口径问题，**记为待查**，不能据此认为评测实际占用了 11GB 独显显存。

MMLU 第一次全量尝试失败，原因是 `college_computer_science` 的 datasets 缓存停在 `.incomplete` 目录（`logs_ext/eval_general_0p6b_mmlu.log`，2026-11-10 16:55:49–16:56:18 CST）。随后用 `scripts/build_mmlu_cache.py` 从已下载的 hub 缓存补全 57 科（`SUBJECTS 57 BAD []`，见 `logs_ext/eval_general_0p6b_mmlu_v2.log`），再离线重跑，基座与 adapter 均成功。独立文件 `logs_ext/build_mmlu_cache.log` 只记录了较早一次不完整的补全（13 科），完整 57 科记录在 `eval_general_0p6b_mmlu_v2.log` 开头，不要只看前者。

## 4. 对结果的解释（需保持克制）

1. **不能据此否定这个方向。** ARC-Easy 有下降但达不到显著标准，IFEval 基本持平，MMLU 反而上升。这与“工具训练造成全面灾难性遗忘”的简单叙事不符。
2. **也不能把 MMLU 上涨写成知识增益。** 训练数据是四类确定性工具调用，几乎不可能提供 MMLU 所需的世界知识。MMLU 按选项的概率打分，微调后模型更习惯给出简短、直接的答案，就可能抬高分数。要先排除这种格式 / 输出分布效应，再讨论能力变化。
3. **单一种子、单一最终 adapter。** 目前只有 A 顺序、seed 20261108、stage_04 这一个点。没有 stage_01–stage_04 轨迹，没有 20261109 / 20261110，也没有“只用旧工具数据”的对照 adapter，规律是否稳定还不知道。
4. **评测口径本身也会影响结论。** ARC-Easy 与 MMLU 未使用 chat template，IFEval 使用了；MMLU 是选项打分而不是生成后再抽取答案。换口径后数字可能改变，这也是下一步必须做的验证。

建议在论文或对外叙述中使用如下表述：

> 在这一次 0.6B、单种子、单一最终 adapter 的评测中，ARC-Easy 下降约 1.8σ（不可称为显著），IFEval 无明显变化，MMLU 上升约 4.8σ。MMLU 的上升需要优先验证是否来自格式或输出分布，而不能直接解释为知识或推理能力提高。

## 5. Qwen3-1.7B 冒烟

目的：确认把原 Phase 2 流程换到 1.7B 后，在本机 8GB 显存上能否跑通，而不是看工具学习分数。

| 项目 | 实际值 |
|---|---|
| 配置 | `configs/ext/qwen3_1p7b_phase2_smoke.json` |
| 入口 | `scripts/run_smoke_ext.sh` → `.venv` 中的 `python -m fac_tinyagent.ext_sweep` |
| 模型 | `/home/egret/models/Qwen3-1.7B`，4-bit QLoRA |
| 顺序 / 种子 | A，20261108 |
| 数据 | 只读使用已有 `data_phase2_smoke`（每族 train/val/test = 8/2/6） |
| 评估题量 | `evaluation.test_limit=3`，即每族 3 题，不是测试集全部 6 题 |
| 输出 | `runs_smoke_1p7b/A_seed20261108/` |
| 完成时间 | 2026-11-10 13:42:53（Asia/Shanghai，见 `ext_meta.json`） |
| 墙钟 | 包装脚本记录 **562 s**（`smoke_summary.txt`）；流程内部 `ext_meta.json` 为 557.9 s |
| 整卡显存峰值 | **6256 MiB**（`nvidia-smi` 轨迹，含基线 1416 MiB；轨迹最大值为 6256，已复核） |
| 训练侧记录的峰值 | `ext_meta.json` 中 `train_peak_gpu_gb_max=4.013`（PyTorch 分配口径，小于整卡占用） |

四阶段均写出了 checkpoint 与评估摘要，退出码 0。因为每族只有 3 道测试题，**任何准确率、遗忘量或“学会了某工具”的数字都不可解释，也不应写入主结论或论文表格**。它只说明：1.7B + 4-bit QLoRA + 原顺序训练/评估流程在这台笔记本上可以跑完，显存还有余量，具备后续扩大测试集正式实验的条件。

本日没有跑 4B 冒烟，也没有创建 `runs_ext_phase2_1p7b` / `runs_ext_phase2_4b`。对应配置已放在 `configs/ext/`。

## 6. 模型下载

均位于 WSL 本地 `/home/egret/models/`，由 `setup/download_model_ext.sh` 从 ModelScope 下载（Hugging Face CDN 不稳定时回退 hf-mirror，并做大小 / SHA256 校验）。

| 模型 | 路径 | 目录大小 | 权重文件 |
|---|---|---:|---|
| Qwen3-0.6B | `/home/egret/models/Qwen3-0.6B` | 1.5G | `model.safetensors`（1.5G），此前已存在 |
| Qwen3-1.7B | `/home/egret/models/Qwen3-1.7B` | 3.8G | `model-00001-of-00002.safetensors`（3.3G）+ `model-00002-of-00002.safetensors`（594M） |
| Qwen3-4B | `/home/egret/models/Qwen3-4B` | 7.6G | 三个分片：3.7G + 3.8G + 96M |

1.7B 与 4B 目录中有 `.modelscope_files.json` / `.modelscope_files.tsv`，可据此核验文件列表。本地已齐，不必重复下载。

## 7. 局限与当日过程要点

- 评测只覆盖一个 adapter，没有阶段轨迹、没有多种子、没有“仅旧工具数据”对照。
- 没有生成式 MMLU，也没有给 MMLU / ARC-Easy 加上 chat template 的对照。
- 通用评测与工具评测使用不同虚拟环境，加载方式刻意与训练路径对齐，但 lm-eval 任务模板与项目内工具题模板不同。
- 网络不稳定多次打断数据集缓存；MMLU 曾因单科 `.incomplete` 失败，修复后离线重跑才得到第 3 节数字。
- 笔记本在安静模式下 GPU 功耗会被压到约 30W 量级，评测速度明显变慢；本日后半段已改到奥创控制中心的狂暴模式。这影响墙钟，不改变已写出的准确率文件。

更完整的环境、命令和排错见同日交接手册 [EXT_HANDOVER_20261110_ZH.md](EXT_HANDOVER_20261110_ZH.md)。

## 8. 下一步

1. **先查清 MMLU 上涨的原因**（优先于扩大模型规模）：
   - 对同一 run 的 `stage_01`–`stage_04` 画 MMLU / ARC-Easy / IFEval 轨迹，看上涨是出现在早期还是只出现在最终 adapter；
   - 至少再跑 seed 20261109、20261110，以及其它学习顺序；
   - 增加 chat template 版本，以及生成式（先生成再解析选项）口径的 MMLU；
   - 如有可能，增加一个只用旧工具数据、不做四阶段连续学习的 adapter 作为对照。
2. **1.7B 正式实验**：用 `configs/ext/qwen3_1p7b_phase2.json` 跑 A 顺序，并把测试集从冒烟的每族 3 题扩大（配置里当前是 `test_limit=10`，正式结论前应再评估是否提高到全量 30 题）。随后再考虑 4B；本机 8GB 上 4B 可能紧张，必要时改到云端。
3. **加强基线，而不是只报遗忘**：在连续学习中加入 KL 正则、自生成回放、权重插值 / 模型合并等对照，使“工具学习是否伤害通用能力”有可比较的缓解手段。
4. **修补监测盲区**：监测集改用自然表述，而不是与训练同模板的题目，避免再次出现“历史题掉分、监测题不掉”的假阴性。
5. **把通用能力评测纳入每轮正式实验**，与工具指标一起出报告，而不是事后补测一次。

## 9. 产物索引

| 内容 | 路径 |
|---|---|
| 本报告 | `EXT_REPORT_20261110_ZH.md` |
| 交接手册 | `EXT_HANDOVER_20261110_ZH.md` |
| ARC-Easy 全量结果 | `runs_ext_eval/q06b_base_arc_easy_full/results.json`、`runs_ext_eval/q06b_A108_stage04_arc_easy_full/results.json` |
| IFEval 全量结果 | `runs_ext_eval/q06b_base_ifeval_full_chat/results.json`、`runs_ext_eval/q06b_A108_stage04_ifeval_full_chat/results.json` |
| MMLU 全量结果 | `runs_ext_eval/q06b_base_mmlu_full/results.json`、`runs_ext_eval/q06b_A108_stage04_mmlu_full/results.json` |
| 成功的 MMLU 日志 | `logs_ext/eval_general_0p6b_mmlu_v2.log` |
| 失败的 MMLU 日志 | `logs_ext/eval_general_0p6b_mmlu.log` |
| ARC / IFEval 包装日志 | `logs_ext/eval_general_0p6b_full_v2.log` |
| 1.7B 冒烟摘要 | `runs_smoke_1p7b/smoke_summary.txt`、`runs_smoke_1p7b/A_seed20261108/ext_meta.json` |
| 被测 adapter（只读） | `runs_phase2/A_seed20261108/checkpoints/stage_04_calendar` |
| 项目级既有报告（只读） | `EXPERIMENT_REPORT_ZH.md`、`HANDOVER_ENVIRONMENT_ZH.md` |
