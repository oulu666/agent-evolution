# 交接手册：target 插入位置单变量对照 + 插入时机审计（2026-11-13）

## 0. 状态（2026-11-13 22:30，北京时间）

- GPU 队列 19:43:07 开始，22:01:19 结束，rc=0，`QUEUE COMPLETE`。6 个训练、54 次 suite 评测全部完成，没有触发 watchdog。GPU 现在空闲，没有排队任务。
- H-timing（`E3B2_PREREG_AMEND_20261113_timing_ZH.md` §1）：**支持**，两组配对差三种子全部为正。
- 审计结论：Database 恢复跟着 target 模式的更新暴露走；剂量 S 曲线横轴要改成暴露量；「覆盖比预算更重要」保留，覆盖度量要算进插入时机。详见 `EXT_REPORT_20261113_timing_ZH.md` §6。
- 下一步候选写在报告 §7，未启动。

## 1. 新增文件

| 路径 | 内容 |
|---|---|
| `E3B2_PREREG_AMEND_20261113_timing_ZH.md` | 预注册修订（训练前写成） |
| `fac_tinyagent/p2_timing.py` | `--phase build`（冻结计划）/ `queue`（训练 + B1 评测，GPU）/ `summarize`（CPU）/ `show` |
| `scripts/run_timing_20261113.sh`、`scripts/launch_timing_20261113.sh`、`scripts/stop_timing.sh` | 运行 / 启动（带 preflight + watchdog）/ 停止 |
| `data_ext_e3b2_timing/plans/A_seed*_{target_other,dose_db1}_pos143.json` | 6 个冻结计划 |
| `data_ext_e3b2_timing/manifest.json` | 源计划哈希、T* 下标原→新、被换条目 |
| `runs_ext_e3b2_timing/prefixes/A_seed*/` | E4 midpoint prefix 的哈希校验副本 |
| `runs_ext_e3b2_timing/branches/A_seed*_<臂>/checkpoint/` | 适配器、`training_log.jsonl`、`train_summary.json`、`replay_plan.json` |
| `runs_ext_e3b2_timing/evaluation/A_seed*_<臂>/<suite>/` | B1 逐题结果 `results.jsonl`、`timing_meta.json`（含适配器哈希与 rows 哈希） |
| `runs_ext_e3b2_timing/summary.json`、`summary_tables_ZH.md` | 汇总、配对差、判定、答对题号 |
| `scripts/p2_timing_existing.py` → `runs_ext_e3b2_timing/analysis/existing_timing{.json,_ZH.md}` | 已有臂的插入位置清单（剂量 + 预算格子） |
| `scripts/p2_timing_audit.py` → `runs_ext_e3b2_timing/analysis/timing_audit{.json,_ZH.md}` | 审计：48 个 B1 点 + 27 个 B32 格子点，秩相关 / 偏秩相关 / 描述性 logistic / 暴露分箱 |
| `logs_ext/timing_20261113.log`（`.pid`、`.status`） | 运行日志 |
| `EXT_REPORT_20261113_timing_ZH.md` | 报告 |

## 2. 复现（WSL，项目根目录，项目 `.venv`）

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
.venv/bin/python -m fac_tinyagent.p2_timing --phase build       # CPU：从源计划生成并冻结 6 个计划（已存在则校验）
.venv/bin/python -m fac_tinyagent.p2_timing --phase show        # CPU：打印每个计划的换位信息
bash scripts/launch_timing_20261113.sh queue                     # GPU：preflight（无 r5apex / 功耗上限 ≥60W / 无其它 GPU 进程）+ watchdog，已完成的训练和 suite 会跳过
bash scripts/stop_timing.sh                                      # 停止（写 logs_ext/timing_20261113.stop）
.venv/bin/python -m fac_tinyagent.p2_timing --phase summarize   # CPU：summary.json / summary_tables_ZH.md
.venv/bin/python scripts/p2_timing_existing.py                   # CPU：existing_timing
.venv/bin/python scripts/p2_timing_audit.py                      # CPU：timing_audit
```

## 3. 关键约定

- 换位规则：\(T^\star\) 与「第 143 位那一段（段下标 7，条目下标 `[7n/10, 8n/10)`）的最后一个条目」交换，其它顺序不变；总 optimizer 步数断言为 23。
- 「之后更新次数」= optimizer_steps − ((microstep − 1) // 8 + 1) + 1。`p2_timing.py`、`p2_target_timing_check.py`、`p2_timing_existing.py`、`p2_timing_audit.py` 四处口径相同。Σafter = 各条 target 之和；mom = Σ(1 − 0.9^之后更新次数)。
- 配对对象：target_other_pos143 ↔ `runs_ext_e3b2` 的 e3b2_A_target_other；dose_db1_pos143 ↔ `runs_ext_e3` 的 dose_db1。两者的 B1 结果都在 `runs_ext_p1_b1/evaluation`。tf25 只作参照。
- 主指标是 B1 nat v2 `db.filter_cmp_top`，写作能力缺口；B32 只在预算格子里单列。
- 只读：所有已有 runs*/data*、冻结测试集、原预注册。本轮只新增文件。

## 4. 哈希（sha256）

| 文件 | sha256 |
|---|---|
| `E3B2_PREREG_AMEND_20261113_timing_ZH.md` | `3b423da2ccbf7dead459f26ad6e1511a02a712a314336640ed35786c04654e10` |
| `data_ext_e3b2_timing/manifest.json` | `01919025d67f860e7fb0b5806b8d81eb563db154e8c190f3453edf4bb4b5791c` |
| plans/A_seed20261108_target_other_pos143.json | `2e35c3daa01607a08da39c9028c115410bd4f33d0a0f1720aff5b7dc34fd143b` |
| plans/A_seed20261108_dose_db1_pos143.json | `949beee4b3e6a1470c97ecb96e830925353937dfac5781d58deb34ad71fac326` |
| plans/A_seed20261109_target_other_pos143.json | `2619f9254031940b2e91b032fd1e4977b8b6f28961c515d91b5069bb78eab49c` |
| plans/A_seed20261109_dose_db1_pos143.json | `c6b6ce97d37296d644c7b04d81a42a6908c07bc527d59597718d8b5c22c86ffd` |
| plans/A_seed20261110_target_other_pos143.json | `31803b3e7d74a28b2558a298efe5bb2231964fb5a753616a7c9da8361b08cdec` |
| plans/A_seed20261110_dose_db1_pos143.json | `c14806a9eac9756da830e7e18d08faf9155422549e9d73d2373c54e855d2dd9f` |
| 适配器 08 target_other_pos143 | `0e650bacea3c6cd7ad8e051e09b489504d78fc330cea4846efb42d13c7ff59e4` |
| 适配器 08 dose_db1_pos143 | `000405fec8345c3b91e69f38f379e80b4cf7d0d7cb04feba50b59e29e27244e0` |
| 适配器 09 target_other_pos143 | `094a46f461e48df1161ff40cd6d6f66430a20797b17014824f7324632ff734d9` |
| 适配器 09 dose_db1_pos143 | `423ce359811e1984cc0eb4ca387d655b14d7e95c389f0c723daa27e7da1f694f` |
| 适配器 10 target_other_pos143 | `38c3be0e08e01e199af983a986178cd5c19f8c99b3ffa564d7d487d59a3aeb50` |
| 适配器 10 dose_db1_pos143 | `5acde96ba75dc4fc5ae02e38651c62591a380fbfee1ee8b6575d909a1509edcb` |
| `fac_tinyagent/p2_timing.py` | `12f05b199a2b98578623ea8520cc056fe0a85c8c8e059639e7ca0de55529d704` |
| `scripts/p2_timing_existing.py` | `f092cbc0d4c574ba423c79055a47bad8be2fe387d2bb54928dbe863fff116e66` |
| `scripts/p2_timing_audit.py` | `cb47a8797a5df3c6b36a8bd7f158be7e1953f4650849d07a6d2416138f6d1869` |

## 5. 运行记录（北京时间）

| 种子 | 臂 | 训练开始 | 训练结束 | 训练秒数（日志） | 评测结束 |
|---|---|---|---|---|---|
| 08 | target_other_pos143 | 19:43:10 | 19:44:51 | 196.2 | 约 20:08 |
| 08 | dose_db1_pos143 | 20:08:50 | 20:09:37 | 196.2 | 约 20:33 |
| 09 | target_other_pos143 | 20:33:02 | 20:33:44 | 208.2 | 约 20:55 |
| 09 | dose_db1_pos143 | 20:54:57 | 20:55:38 | 207.9 | 约 21:17 |
| 10 | target_other_pos143 | 21:17:06 | 21:17:49 | 278.2 | 约 21:39 |
| 10 | dose_db1_pos143 | 21:39:18 | 21:40:01 | 277.9 | 22:01:16 |

「训练秒数」照抄日志里 `replay train done` 行的数字；「评测结束」取下一个任务开始时间或日志里的 `EVAL done`。

## 6. 下一步候选（未启动，等用户决定）

见报告 §7：(1) 条数 × 时机拆分（`dose_db1_pos127`、`dose_db4_late`，约 2.5 小时 GPU，先写预注册修订）；(2) 新增基于暴露的覆盖度量文档并重画 E3 图表（CPU）；(3) 真遗忘探针集（约 30 分钟 GPU）。
