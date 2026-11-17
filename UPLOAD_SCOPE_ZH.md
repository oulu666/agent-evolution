# fac_tinyagent 上传范围说明

更新时间：2026-11-17 17:50（Asia/Shanghai）同步准备。  
项目路径：`C:\Users\Egret\Desktop\oulu\Agent Self-Evolution\fac_tinyagent`  
远程仓库：https://github.com/oulu666/agent-evolution （私有，`main`）

## 当前同步原则

上传源码、配置、脚本、测试、依赖、中文报告/预注册/交接、训练与评测数据（含 SQLite 夹具），以及轻量实验结果（JSON / JSONL / CSV / log / 小图 / 摘要）。

本次起明确纳入：

- P9、P10 各轮的新增代码、数据夹具、预注册、报告、交接和轻量结果/日志
- `optimizer_step_audit.json` 与 `optimizer_update_log.jsonl`（轻量审计，不是模型或 optimizer 权重）
- SQLite/DB 训练、开发、测试夹具（不得因扩展名未登记而排除）

排除且仍只留在本地：

- `.venv` 虚拟环境
- 模型权重与真正的优化器/训练状态（`.safetensors` / `.bin` / `.pt` / `.pth` 等）
- 检查点中可恢复的重复分词器与附属文件（如 `tokenizer.json`）
- 超大 MMLU `samples.json` 转储
- 缓存、重复备份、运行锁、`*.pid`
- `_tmp*` 临时文件、屏幕截图与网页 dump
- 本地 STOP 标记（不删除，也不提交）
- 凭据、私钥、`.env`

不使用 `git add -A`，按明确文件清单暂存，避免大权重入库。

## 本次（2026-11-17 下午）新增拟同步内容

在此前已推送快照之外，新增约 201 个文件、约 4.05 MB，主要包括：

- P9：`P9_PREREG_20261117_ZH.md`，`EXT_REPORT_20261117_p9_independent_final_ZH.md`，`EXT_REPORT_20261117_p9_independent_review_ZH.md`，以及对应 HANDOVER、分析目录、数据 `data_ext_p9_counterfactual_20261117/`、结果 `runs_ext_p9_counterfactual_20261117/`（含 `summary.json`）、源码与脚本
- P10：`EXT_REPORT_20261117_p10_dev72_ZH.md`，`EXT_REPORT_20261117_p10_unitclarify48_ZH.md`，`EXT_REPORT_20261117_p10_formal_prompt_ZH.md` 及其 HANDOVER 与预注册；数据 `data_ext_p10_twoview_cpu_20261117/`（含 `retention.sqlite`）；结果目录 `runs_ext_p10_devdiagnosis_20261117/`、`runs_ext_p10_unitclarify48_20261117/`、`runs_ext_p10_formal_prompt_20261117/`（均含 `summary.json`）；相关源码与分析脚本
- 其余：`research/TOPCONF_FUSION_20261117_ZH.md`，以及此前未入库的轻量 optimizer 审计日志

完整清单见 `UPLOAD_MANIFEST_RECOMMENDED.csv`。本次变更文件列表另见同步记录。

## 排除体积（本地保留，未删除）

新增未跟踪内容中仍排除的主要部分约为 9.22 GB：模型权重约 6.42 GB、重复 tokenizer 约 2.45 GB、超大 MMLU samples 约 345 MB，以及临时文件、检查点附属文件、锁/PID 和 STOP 标记。既有冻结数据、runs 与权重不被改动。
