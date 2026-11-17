# P0 交接手册（2026-11-12）

- 撰写：2026-11-12 约 10:40（Asia/Shanghai，UTC+8）。正式结论见 `EXT_REPORT_20261112_p0_ZH.md`。
- 本轮只新增文件，未改 `.venv`、已有 `runs*/`、`data*/`（新的 `data_ext_p0_*` / `runs_ext_p0_*` 除外）、Small Agent、conda `zxx`。未改冻结的 Calendar v3 和自然语言期末 v2。未向 ChatGPT 发送消息。

## 1. 本轮做了什么

1. 批量评测一致性：44 题探针，E4 种子 08 的 tf50，batch=1/2/4/32 逐题对照文本和得分。
2. Database 非 target 题集（40 题，5 个模板）冻结后，在 E3-B dose 臂 + none 的 3 个种子上短评测（21 个评测，全部 rc 正常）。
3. 诊断 v3「标题计数」全臂 0.389 的原因；另出 `calendar_title_count_v3fix`（30 题），用 start / none / ctrl_cal20 做短验证。不是多实例 v4。

## 2. 结果在哪里

| 内容 | 路径 |
|---|---|
| 代码 | `fac_tinyagent/p0_cal_titlecount.py`、`p0_db_nontarget.py`、`p0_run.py` |
| 启动 / CPU 测试 | `scripts/run_p0_20261112.sh`、`scripts/test_p0_data.py` |
| 批量探针 | `data_ext_p0_batched/{probe.jsonl,FROZEN.json}` |
| 批量评测 | `runs_ext_p0_batched/bs{1,2,4,32}/`，对照 `runs_ext_p0_batched/comparison.json` |
| DB 非 target 题集 | `data_ext_p0_db_nontarget/final/{database_nontarget.jsonl,FROZEN.json}` |
| DB 非 target 评测 | `runs_ext_p0_db_nontarget/evaluation/`、`runs_ext_p0_db_nontarget/summary.json` |
| 标题计数新版题集 | `data_ext_p0_cal_titlecount/final/{title_count_v3fix.jsonl,FROZEN.json}` |
| 标题计数新版评测 | `runs_ext_p0_cal_titlecount/evaluation/`、`runs_ext_p0_cal_titlecount/summary.json` |
| 日志 | `logs_ext/p0_20261112.log` |
| 正式报告 / 给 GPT 的草稿 | `EXT_REPORT_20261112_p0_ZH.md`、`scripts/gpt_bridge/msg_20261112_p0.md`（未发送） |
| 标题计数诊断脚本（临时） | `scripts/_tmp_analyze_title_count.py`、`scripts/_tmp_analyze_title_count2.py` |

## 3. 关键数字（速查）

- 批量：bs2 与 bs1 完全一致（44/44）；bs4 / bs32 各有 1 道 Calendar「末场结束」翻转；新 bs1 与历史 E4 tf50 差这 2 题。耗时 236.8 s / 109.0 s / 51.6 s / 40.5 s。
- DB 非 target 三种子均值：none 0.708，db0 0.717，db1 0.667，db2 0.642，db3 0.667，db4 0.708，db6 0.692。不随 k 上升。对照 target 期末 0.00→1.00。
- 标题计数 v3fix（种子 08）：start 0.000，none 0.267，ctrl_cal20 0.300。
- 冻结哈希：
  - `calendar_title_count_v3fix` combined `944be6ce5a5eb8801957b074dc17430982a4ef9f8bc3a44109ffe8cc00ce5e9f`
  - `database_nontarget_v1` combined `9c3b7ea0effa2e88d4e3c882206ecb6d9040c931763c494836cab90eec2aa58d`

## 4. 复现与命令

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
PYTHONPATH=. .venv/bin/python scripts/test_p0_data.py
# 已冻结的题集不要再 build；若目录里已有 FROZEN.json，构建脚本会拒绝覆盖
# 评测已完成的分支会跳过（看 EVAL_DONE）
bash scripts/run_p0_20261112.sh batched
bash scripts/run_p0_20261112.sh cal --batch-size 1
bash scripts/run_p0_20261112.sh db --batch-size 1
```

PowerShell 用 `wsl.exe -d Ubuntu -- bash -lc '...'`（单引号）。

不要向已有 `runs_ext_e3` / `runs_ext_e4` / `runs_ext_calv3` 写入。游戏在跑时不要启动 GPU。不要用 nvidia-smi 改功耗。

## 5. 已知问题

1. `p0_run.game_running()` 用 utf-8 解码 Windows `tasklist` 会失败（日志里有 WARN），当前是失败则当作没有游戏。外壳脚本启动前的检查仍然有效。以后应改成 `errors=ignore` 或 gbk，但本轮不再动代码。
2. 日志里 start 臂的 `day=-1.000 tool=-1.000` 是打印时把 0.0 写成了 `x or -1`，`summary.json` 里是正确的 0.0。
3. E3/E4/v3 实际使用的是 batch=32，不是以往报告里写的 batch-1。
4. 临时诊断脚本 `_tmp_analyze_title_count*.py` 可以保留作附录，不是评测依赖。

## 6. 建议的下一步（待用户确认后再启动 GPU）

1. 把「模板覆盖」写进后续预注册和论文口径。
2. 新官方评测默认 batch=1；若改用 batch=2，需要预注册并注明与历史 batch=32 的 Calendar 临界题不可对打。
3. 标题计数 v3fix 作附加指标；多实例 v4、E3-B2、5 个种子、按缺口分配的新臂，等确认后再跑。
