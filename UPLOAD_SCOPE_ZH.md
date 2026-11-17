# fac_tinyagent 上传范围说明

生成时间：2026-11-17 14:03（Asia/Shanghai）盘点，2026-11-17 14:08（Asia/Shanghai）完成本说明。  
项目路径：`C:\Users\Egret\Desktop\oulu\Agent Self-Evolution\fac_tinyagent`

## 结论：尚未上传

本地项目与父目录都还不是 Git 仓库，GitHub 上也没有已确认、可写的对应远程。  
因此本次**没有**执行 `git init`、commit 或 push，也没有创建仓库。  
要真正上传，需要主助手先请用户给出明确的目标仓库地址（由用户创建空仓库后提供 URL）。在此之前不宜初始化，以免默认分支或远程选择冲突。

## 推荐上传范围（已纳入清单）

- 文件数：**18,313**
- 体积：**247,000,124 字节（235.56 MB）**
- 清单文件：`UPLOAD_MANIFEST_RECOMMENDED.csv`

其中大致包括：

- 源码 / 脚本 / 测试 / 配置 / 顶层中文报告与 P81 文档等核心文件：约 355 个，约 3.6 MB
- 训练与评测数据（含下面补回的 SQLite/DB 夹具）：268 个，约 12.34 MB
- 轻量实验结果（JSON / JSONL / CSV / log / 小图 / 状态文件等，不含权重与超大转储）：其余约 17,690 个，约 219.6 MB

P81 已完整纳入，包括：

- `P81_CORE_ALGORITHM_20261116_ZH.md`、`P81_PREREG_20261116_ZH.md`
- `EXT_REPORT_20261116_p81_diagnosis_ZH.md`、`EXT_HANDOVER_20261116_p81_diagnosis_ZH.md`
- `analysis_p81_special_cases_20261116/`
- `data_ext_p81_diagnosis_20261116/`（含 `probe.sqlite`）
- `runs_ext_p81_diagnosis_20261116/` 中的轻量结果
- 相关源码与脚本（如 `fac_tinyagent/p81_diagnosis_20261116.py`、`scripts/run_p81_diagnosis_20261116.py`）

P8 决策实验同样保留，没有按过时的 P8 截断。

## 首轮粗扫描与收紧说明

首轮按“源码、配置、脚本、测试、依赖、中文报告/预注册/交接、训练数据、轻量 JSON/CSV/log”收集到的宽候选为：

- **18,770 个文件，3,176,012,761 字节（2.96 GB）**

其中不适合直接作为 GitHub 推荐集的部分已从推荐清单中拿掉，主要包括：

- 224 个检查点 `tokenizer.json`，约 2,440.14 MB（可从模型恢复的分词器副本）
- 8 个超过 10 MB 的 `runs_ext_eval/**/samples.json`，约 345.02 MB
- 检查点中重复的 `tokenizer_config.json` / `config.json` / `generation_config.json`
- `scripts/**/_tmp*` 临时脚本、日志、抓取文本，以及 `scripts/gpt_bridge/_tmp_chatgpt_win.png`（约 8.16 MB）
- 空的运行锁文件（`*.lock` / `.run.lock`）

另有 2 个超过 GitHub 50 MB 警告线、未进入任何候选集的文件（约 101.43 MB）：

- `runs_ext_eval/q06b_A108_stage04_mmlu_full_chat/samples.json`
- `runs_ext_eval/q06b_base_mmlu_full_chat/samples.json`

同目录下较小的评测摘要与不超过约 1.2 MB 的 samples 仍留在推荐清单中。

## 排除项（不进入推荐上传）

首轮排除 **28,751 个文件，12,419,775,622 字节（11.57 GB）**，主要是：

| 原因 | 文件数 | 体积 |
| --- | ---: | ---: |
| 模型权重 / 优化器与状态（`.safetensors` / `.bin` / `.pt` / `.pth` 等） | 321 | 6.13 GB |
| `.venv` 虚拟环境 | 28,022 | 5.43 GB |
| `__pycache__` 等缓存 | 97 | 1.55 MB |
| 被标为 unknown_or_binary 的文件（见下一节，部分已纠正） | 282 | 1.21 MB |
| 重复备份（`backup_before_ext_20261110`、`data_ext_e3_superseded_v1_20261111`、`data_round2_failed_001`） | 29 | 1.00 MB |

被剪枝的备份与缓存目录均未删除，只是不纳入上传。

## SQLite / 训练环境资产：误排除及纠正

首轮把未登记扩展名的小文件一律标成 `unknown_or_binary`，因而**误排除了 12 个 SQLite/DB 训练夹具，共 245,760 字节（240 KB）**。这些是实验可复现所需的环境资产，已全部补回推荐清单，`.gitignore` 也不会忽略它们：

- `data/fixtures/toolbench.db`
- `data_phase2/fixtures/toolbench.db`
- `data_phase2_smoke/fixtures/toolbench.db`
- `data_replay_study/fixtures/toolbench.db`
- `data_smoke/fixtures/toolbench.db`
- `data_ext_p6_devplan/fixtures/dev.sqlite`
- `data_ext_p6_devplan/fixtures/holdout.sqlite`
- `data_ext_p7_response/fixtures/check.sqlite`
- `data_ext_p8_decision_20261115/fixtures/dev.sqlite`
- `data_ext_p8_decision_20261115/fixtures/holdout.sqlite`
- `data_ext_p8_decision_20261115/fixtures/train.sqlite`
- `data_ext_p81_diagnosis_20261116/probe.sqlite`

同时从同一误分类中补回的轻量运行记录（非数据库，但同属实验环境痕迹）：

- `logs_ext/*.status` 共 10 个，约 56.1 KB
- `logs_ext/calv3_20261111.targets`，573 B
- `logs_ext/ext_20261111_{code,docs,patch1}.tgz` 共 3 个，约 33.1 KB

仍不纳入推荐清单、但已标明以免被静默丢掉的同类误分类项：

- 224 个检查点 `chat_template.jinja`（约 911.8 KB）：与 tokenizer 配置一样，属于可从模型恢复的重复附属文件
- 31 个 `*.pid`（116 B）：进程号，无科研保留价值
- `runs_ext_p7_response/logs/STOP.game_20261115_174742`（59 B）：临时停止标记

**影响：** 若按首轮宽候选的排除规则直接上传，P6/P7/P8/P81 与 toolbench 相关实验会缺少本地 SQLite/DB 夹具，复现训练/探针环境会不完整。当前推荐清单已纠正；这些文件都很小，不影响 GitHub 体积。

## 秘密检查

对推荐范围内的文本文件做了模式扫描（只记录路径与类型，不打印内容）：

- 未发现 `.env`、私钥、凭据类文件名
- 未发现私钥块、GitHub/OpenAI/Hugging Face/AWS/Slack 等常见令牌模式命中

未扫描 `.venv` 与模型权重内容。未读取任何凭据文件或系统凭据库中的值。

## 仓库与认证状态（仅事实，未绕行）

- 项目、`Agent Self-Evolution` 父目录、`oulu` 目录均不是 Git 仓库，也没有嵌套 `.git`
- 已连接的 GitHub 账号登录名为 `oulu666`；该账号公开仓库数为 0
- `list_my_repositories` 第 1、2 页均为空；按名称搜索 `fac_tinyagent` 无结果
- `user:oulu666` 的仓库搜索返回 422（连接器对 `user:oulu666` 不可见）。这不能单独证明账号下绝对没有私有仓库，只说明当前连接器看不到
- 对 `oulu666/fac_tinyagent`、`oulu666/tinyagent`、`oulu666/Agent-Self-Evolution` 的仓库查询均不可访问（可能不存在、是私有且未授权给 Cursor GitHub App，或名称不符）
- **没有已确认可推送的目标远程**

本机 Git：

- Windows Git 2.52.0；系统 `credential.helper=manager`；已安装 Git Credential Manager
- 全局配置目前只有 `safe.directory=*`
- 未安装 `gh`；环境中未见 `GITHUB_TOKEN` / `GH_TOKEN`
- 不存在 `~/.git-credentials` 或 SSH 私钥文件；存在 `~/.ssh/config` 与 `known_hosts`
- **未**探测或绕过凭据，也**未**验证 GCM 是否已登录 GitHub。有目标仓库后再用现有 Git/GCM 走正常 HTTPS 推送即可

WSL 的 Ubuntu 发行版当时为 Stopped，默认发行版无法直接起 bash；本次盘点使用 Windows 上的 Python 3.13 与 Windows Git，不依赖 WSL。

## 本次在项目中新增的准备文件

只新增，不修改、不删除既有源码、runs、data 或 `.venv`：

- `.gitignore`
- `UPLOAD_SCOPE_ZH.md`（本说明）
- `UPLOAD_MANIFEST_RECOMMENDED.csv`（推荐文件清单）

完整扫描摘要另外写在本机临时目录，未放入项目：

- `C:\Users\Egret\AppData\Local\Temp\fac_upload_scan\scan_summary.md`
- `C:\Users\Egret\AppData\Local\Temp\fac_upload_scan\scan_summary.json`

## 后续上传还缺什么

1. 用户创建空的 GitHub 仓库（建议先私有），并把完整 URL 交给主助手。在获得明确批准前，不要由助手创建或改成公开仓库。
2. 确认推送身份：本机已有 Git Credential Manager，登录状态需在有目标远程后由用户完成或确认。
3. 拿到仓库 URL 后，再在项目目录初始化 Git、按本推荐清单提交并正常 push。禁止强推，禁止覆盖远程，禁止 reset 或删除本地科研文件。
