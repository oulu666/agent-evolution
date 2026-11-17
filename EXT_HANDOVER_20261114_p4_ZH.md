# 交接手册：P4 真遗忘时机 + 饱和模型预测验证臂（2026-11-14）

## 0. 状态（2026-11-14 21:16，北京时间）

- GPU 队列 13:53:41 开始，17:23 笔记本强制重启后中断，20:19:46 续跑（runner PID 464），跳过已完成的 14 个分支，补完种子 10 的 db2_early 评测和 3 个 db4_early。20:56:40 结束，rc=0，`QUEUE COMPLETE`。开跑与续跑的 preflight 都是 game=no、无其它 GPU 进程（功耗上限分别为 90W 和 123W），watchdog 未因游戏或功耗过低而暂停。
- 种子 10 重启前有几个分支训练或评测异常慢，是当时系统卡顿，不影响结果。
- 21:13:03 跑了 `bash scripts/run_p4_20261114.sh summarize`（CPU，rc=0，21:13:04 写完 `summary.json` / `summary_tables_ZH.md`）。GPU 现在空闲，本轮收尾没有启动新的 GPU 实验。
- 预注册判定（`E3B2_PREREG_AMEND_20261114_p4_forget_timing_ZH.md` §3–§4），详见报告 §1、§4：
  - list_tables 时机：没有完整落在第一行或第二行。late 三种子都不恢复；early − late 方向一致（+0.042 / +1.000 / +0.750，均值 +0.597）。种子 10 落在第二行，种子 09 接近第一行，种子 08 落在第三行「单条不足」。
  - 条数 vs 暴露：三行都不完整成立。LT2mid 三种子都恢复、都高于 mid；种子 08 上 early（1 条，Σ11）未恢复、LT2mid（2 条，Σ12）恢复，第二条同模式经验有暴露量之外的作用。
  - median（种子 08、10）：落在第一行，成立。late − early 都是 −0.067（≥ −0.10）。
  - db4_early：三种子都是 1.000，都高于 dose_db4，「早而广」可以叠加，方向一致。
  - db2_early：0.933 / 0.933 / 0.633，均值 0.833。纯饱和与按表模型的预注册胜出条件都不成立，MAE 几乎打平（0.125 vs 0.121）。
- 下一步候选写在报告 §8，都没有启动。

## 1. 新增文件

| 路径 | 内容 |
|---|---|
| `E3B2_PREREG_AMEND_20261114_p4_forget_timing_ZH.md` | 预注册补充（任何 P4 训练之前写成） |
| `P4_TRUE_FORGETTING_DRAFT_20261114_ZH.md` | 开跑前的盘点草稿 |
| `fac_tinyagent/p4_forget_timing.py` | `--phase build / show / dry / queue / summarize` |
| `scripts/run_p4_20261114.sh`、`scripts/launch_p4_20261114.sh`、`scripts/stop_p4.sh`、`scripts/p4_preflight.sh` | 运行 / 启动（preflight + watchdog）/ 停止 / 开跑前检查 |
| `data_ext_p4_forget_timing/`（plans + probe + manifest） | 冻结计划、24 题 list_tables 探针、sha256 与预算偏差 |
| `runs_ext_p4_forget_timing/prefixes/A_seed*/` | E4 Calendar step-80 prefix 的哈希校验副本 |
| `runs_ext_p4_forget_timing/branches/A_seed*_<臂>/` | 适配器与训练日志 |
| `runs_ext_p4_forget_timing/evaluation/A_seed*_<臂>/` | B1 逐题结果（含 T0 / prefix 探针基线） |
| `runs_ext_p4_forget_timing/summary.json`、`summary_tables_ZH.md` | 汇总、配对差、判定、预测核对 |
| `logs_ext/p4_20261114.{log,status,pid}` | 运行日志（以 20:19 之后的续跑与 20:56 的 `END queue rc=0` 为准） |
| `EXT_REPORT_20261114_p4_ZH.md` | 报告 |
| `EXT_HANDOVER_20261114_p4_ZH.md` | 本文件 |

不要修改已有 runs / data；本轮只新增文件。

## 2. 复现（WSL，项目根目录，项目 `.venv`）

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
.venv/bin/python -m fac_tinyagent.p4_forget_timing --phase build      # CPU：冻结计划（已存在则校验）
.venv/bin/python -m fac_tinyagent.p4_forget_timing --phase show       # CPU：打印 target 位置 / Σafter
bash scripts/launch_p4_20261114.sh queue                             # GPU：preflight + watchdog；已完成的训练与 suite 会跳过
bash scripts/stop_p4.sh                                              # 停止（写 logs_ext/p4_20261114.stop）
bash scripts/run_p4_20261114.sh summarize                            # CPU：summary.json / summary_tables_ZH.md
```

## 3. 关键约定

- 换位规则：target 与目标槽上的条目交换，其它不动；各段条目数、token 预算、optimizer 步数（23）不变。不设 sham 或无复习对照。
- 「之后更新次数」口径与 P3 相同。P4 四臂还固定换入 1 条（LT2mid 为 2 条）`db_list_tables`，并把 target_median_natural 收成编号最小的一条。db2_early / db4_early 只换位置，条目集合和 token 与源计划相同。
- 「恢复」= 探针 24 题 Joint ≥ 0.5，且 p2 list_tables 6/6。median 只用种子 08、10。`db.filter_cmp_top` 是能力缺口，不叫遗忘。
- 判定写法：「方向一致」= 三种子同号。不说「显著」。dose_db2 / dose_db4 的 B1 数字来自已有 runs（预注册抄录，summarize 的预测核对写在 `verdicts.prediction_check`）。
- 续跑段 3 个 db4_early：steps=23，replay token 7,494 / 7,494 / 7,490，filter Σafter=22，与冻结值一致。

## 4. 注意事项

- 种子 08 的 P4_early 探针 Joint 只有 0.042，但 final 是 1.000、args 是 0.042：未恢复时主要是 arguments 写错，不是完全不会答。写论文时要连分项一起报。
- 种子 08 的 db2_early 源计划自带 2 条 list_tables，探针 1.000 不进入时机判定。
- 种子 10 的 db2_early filter 0.633、以及 LT2mid 上 filter 0.767，都是单种子偏低；前者 eval 在续跑后重做，结果可用。
- 非 target Database 这轮没有单独的 40 题套件，是从 p2 Database 30 题中扣除 6 道 list_tables 得到的 24 题。
- 不要修改已有 runs / data；新分析一律新增文件。

## 5. 下一步（报告 §8）

1. 把报告与交接发给 GPT（「智能体自进化实验规模」对话），请看判定表落点和规则表述。
2. 在第二个能力缺口 `file.search_last` 上做 EAAR 固定规则版：真遗忘早插且同模式至少两条，重新激活型不占早槽，能力缺口早插并覆盖不同答案结构。需彦哲确认后再启动 GPU。
