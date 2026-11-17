# 交接手册：P3「条数 vs 时机」拆分（2026-11-14）

## 0. 状态（2026-11-14 06:05，北京时间）

- GPU 队列 01:39:02 开始，05:40:22 结束，rc=0，`QUEUE COMPLETE`。9 个训练（3 臂 × 3 种子）和 81 次 suite 评测全部完成，没有触发 watchdog，也没有暂停。GPU 现在空闲，没有排队任务，本轮收尾没有启动新的 GPU 实验。
- 05:58 又跑了一次 `bash scripts/run_p3_20261114.sh summarize`（rc=0），数字与队列结束时一致。
- 预注册判定（`E3B2_PREREG_AMEND_20261114_p3_count_timing_ZH.md` §3）：
  - pos127 − db4_late：**≈**（+0.033 / −0.233 / −0.067，均值 −0.089）→ 暴露量是主要驱动；注意 db4_late 的 mom 偏高 0.11（0.580 vs 0.469），Σafter 同为 6。
  - pos95 − pos127：**≈**（−0.100 / +0.033 / −0.067，均值 −0.044）→ Σafter≈6 之后饱和，不是被覆盖。
- 本轮最重要的新信息：单条 target 的暴露会饱和，pos95（1 条，Σafter 11）0.567，比 dose_db4（4 条）0.800 低，三种子方向一致。详见报告 §1、§7。
- 下一步候选写在报告 §8，都没有启动。

## 1. 新增文件

| 路径 | 内容 |
|---|---|
| `E3B2_PREREG_AMEND_20261114_p3_count_timing_ZH.md` | 预注册修订（训练前写成） |
| `fac_tinyagent/p3_count_timing.py` | `--phase build / show / dry / queue / summarize` |
| `scripts/run_p3_20261114.sh`、`scripts/launch_p3_20261114.sh`、`scripts/stop_p3.sh` | 运行 / 启动（preflight + watchdog）/ 停止 |
| `data_ext_p3_count_timing/`（plans + `manifest.json`） | 9 个冻结计划、交换记录 `swaps`、sha256 |
| `runs_ext_p3_count_timing/prefixes/A_seed*/` | E4 Calendar step-80 prefix 的哈希校验副本 |
| `runs_ext_p3_count_timing/branches/A_seed*_<臂>/` | 适配器与训练日志 |
| `runs_ext_p3_count_timing/evaluation/A_seed*_<臂>/<suite>/` | B1 逐题结果 |
| `runs_ext_p3_count_timing/summary.json`、`summary_tables_ZH.md` | 汇总、配对差、判定、答对题号及交并 |
| `runs_ext_p3_count_timing/analysis/figures_p3/fig_dose_B1_exposure.png`、`fig_dose_B1_mom.png` | **本轮新增**：剂量曲线叠加 P3 三臂（横轴 n / Σafter / mom） |
| `runs_ext_p3_count_timing/analysis/figures/*.png` | 01:40 的旧图（P3 之前），保留未动 |
| `logs_ext/p3_20261114.{log,status,pid}` | 运行日志 |
| `EXT_REPORT_20261114_p3_ZH.md` | 报告 |
| `EXT_HANDOVER_20261114_p3_ZH.md` | 本文件 |

## 2. 复现（WSL，项目根目录，项目 `.venv`）

```bash
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
.venv/bin/python -m fac_tinyagent.p3_count_timing --phase build      # CPU：冻结计划（已存在则校验）
.venv/bin/python -m fac_tinyagent.p3_count_timing --phase show       # CPU：打印 target 位置 / Σafter / mom
bash scripts/launch_p3_20261114.sh queue                             # GPU：preflight + watchdog；已完成的训练与 suite 会跳过
bash scripts/stop_p3.sh                                              # 停止（写 logs_ext/p3_20261114.stop）
bash scripts/run_p3_20261114.sh summarize                            # CPU：summary.json / summary_tables_ZH.md
python scripts/p3_exposure_figures.py --root <项目根目录>             # CPU：需要 matplotlib，.venv 里没有，也不要往 .venv 装
```

作图这次是在另一台机器上用独立的虚拟环境跑的：把 `scripts/p3_exposure_figures.py`、`runs_ext_e3b2_timing/analysis/timing_audit.json`、`runs_ext_p3_count_timing/summary.json` 按原相对路径复制过去，`--root` 指向那个目录，生成后只把两张剂量图拷回 `analysis/figures_p3/`（预算图与旧图逐字节相同）。

## 3. 关键约定

- 换位规则：target 与目标槽上的条目交换，其它不动；各段条目数、token 预算、optimizer 步数（23）不变。不设 sham 臂。
- 「之后更新次数」= optimizer_steps − 所在累积窗口序号 + 1（累积 8 microstep）；Σafter = 各条 target 之和；mom = Σ(1 − 0.9^after)，只作敏感性分析。训练日志核对：9 个训练 steps=23，Σafter / mom 与冻结值一致，replay token 7,490–7,494，新数据 token 74,944。
- 配对对象：dose_db1 / dose_db1_pos143 / dose_db4 的 B1 结果来自已有 runs（summarize 自动读取），dose_db4 没有副作用套件。
- 判定写法：「方向一致」= 三种子同号；「≈」= 方向不一致且 |均值| ≤ 0.10。不说「显著」。主指标模式 T0=0，写「能力缺口及其恢复」。

## 4. 注意事项

- 两条主判定的均值（−0.089、−0.044）都不大，主指标单题 0.033；分项 arguments / final 方向相反（报告 §4），写论文时要连分项一起报。
- db4_late 的交换把几条 File / Python target 条目换到了更早的位置，nat v2 File 上升（主要是种子 08）不能算 Database 复习的副作用。
- 种子 10 pos95 的非 target Database 40 题 0.450 是单种子下降。
- 不要修改已有 runs / data；新分析一律新增文件。

## 5. 下一步（报告 §8）

1. CPU：用 57 个 B1 点拟合「饱和暴露覆盖」Σ_i(1 − γ^after_i) / 每条上限，检验能否同时解释 pos95 < dose_db4 与 pos127 ≈ db4_late。
2. 把报告与交接发给 GPT（「智能体自进化实验规模」对话）。
3. 真遗忘探针集（`db.list_tables`、`py.median`），只评测、约 30 分钟 GPU，需彦哲确认后再启动。
