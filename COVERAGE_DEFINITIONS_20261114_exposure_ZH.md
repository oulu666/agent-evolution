# Coverage 定义补充（2026-11-14）：把「插入时机」算进覆盖——技能级更新暴露

- 撰写：2026-11-14（Asia/Shanghai，UTC+8）。**只追加**，不改 `COVERAGE_DEFINITIONS_20261112_ZH.md`。该文件的操作模式分类、Pattern Coverage / Experience Diversity / Skill Deficit 三个指标与 monitor 的区分全部保留；本文件只在 Pattern Coverage 之外，增加三个带时间信息的复习计划指标。
- 依据：`EXT_REPORT_20261113_timing_ZH.md`、`runs_ext_e3b2_timing/analysis/timing_audit_ZH.md`。B1、n≥1 的 36 个点上，主指标与 Σafter 的秩相关为 0.936，与 target 条数为 0.811。控制 Σafter 后条数的偏秩相关是 −0.086。条数与暴露在 2→6 条的剂量臂里是共线的，P3（`E3B2_PREREG_AMEND_20261114_p3_count_timing_ZH.md`）专门拆这一点。在 P3 之前，下面三个指标都是**描述性定义**，不说哪一个是因果机制。
- 仍要分开的事：coverage（复习计划里放了什么、什么时候放）与 monitor（模型现在会什么）是两类东西，本文件只讲前者。`db.filter_cmp_top` 在 T0 就是 0，相应结果是「能力缺口及其恢复」，不叫遗忘。

## 1. 记号

- 一次分支训练共有 \(S\) 次 optimizer 更新（当前 Database 剂量 / 定向臂 \(S=23\)，b20 预算 \(S=26\)），梯度累积 \(A=8\) 个 microstep 为一次更新。
- 复习计划中的条目 \(i\) 在第 \(m_i\) 个 microstep 被训练，所在累积窗口序号 \(w_i=\lfloor (m_i-1)/A\rfloor+1\)。
- **之后更新次数** \(a_i = S - w_i + 1\)，包含条目所在窗口那一次更新。条目在最后一个窗口时 \(a_i=1\)。
- 技能 \(s\)：`COVERAGE_DEFINITIONS_20261112_ZH.md` §2 里的细粒度操作模式（例如 `db.filter_cmp_top`）。\(I_s\) 是计划中属于 \(s\) 的条目集合。当前实现按 episode_id 中的模式名归类，例如 `target_db_filter_top` → `db.filter_cmp_top`。
- 口径与 `scripts/p2_target_timing_check.py`、`fac_tinyagent/p2_timing.py`、`scripts/p2_timing_audit.py`、`fac_tinyagent/p3_count_timing.py` 完全一致，\(a_i\) 一律从实际 `training_log.jsonl` 的 microstep 算，不从计划推算。P3 的 build 阶段按源臂日志预测，训练后再核对。

## 2. 三个技能级指标

| 指标 | 定义 | 角色 | 解释 |
|---|---|---|---|
| target 条数 \(n_s\) | \(\lvert I_s\rvert\)（重复抽到的同一条按次数计；另报去重条数 \(n_s^{\text{uniq}}\)） | 旧口径，保留作对照 | 复习里放了几条该技能的经验，不管什么时候放 |
| **Σafter**（更新暴露）\(E_s\) | \(E_s=\sum_{i\in I_s} a_i\) | **主暴露指标** | 该技能的经验在其后一共经历了多少次参数更新，等于「条数 × 平均之后更新次数」 |
| mom（动量加权暴露）\(M_s\) | \(M_s=\sum_{i\in I_s}\bigl(1-\beta_1^{\,a_i}\bigr)\)，\(\beta_1=0.9\) | 敏感性指标 | AdamW-inspired momentum-weighted exposure proxy（受 AdamW 一阶动量启发的加权暴露代理指标） |

关于 mom 的说明：

- **来由。** 在 AdamW 里，某个 microstep 的梯度进入一阶矩后，第 k 次更新时的权重按 \((1-\beta_1)\beta_1^{k-1}\) 衰减。它在之后 \(a\) 次更新里累计贡献的系数是 \((1-\beta_1)\sum_{k=1}^{a}\beta_1^{k-1}=1-\beta_1^{a}\)。所以 mom 是「这条经验的梯度通过一阶矩还能推动参数多少」的归一化代理。它随 \(a\) 单调增加，并在 1 处饱和。Σafter 是线性的，不饱和。
- **限制。** mom 只是代理量，不是测得的参数变化。真实的更新还受梯度大小与方向、二阶矩 \(v\) 的归一化、偏差校正、学习率调度、权重衰减和后续 Calendar 梯度的干扰影响。论文里只能写「proxy」，不能写成「有效梯度贡献」。
- **为什么 Σafter 当主指标。** 定义简单，不依赖优化器超参。两者在现有 36 点上的秩相关几乎相同（0.936 / 0.928）。mom 在描述性 logistic 里偏差略小（65.3 vs 71.0），所以作为敏感性分析一起报。

辅助描述量（只描述，不作主指标）：first（最早一条的 \(a\)）、last（最晚一条的 \(a\)）。审计中 last 在 n≥1 时与主指标的秩相关只有 0.075，说明起作用的是总暴露，不是「最后一次看见」。

## 3. 与原 Pattern Coverage 的关系

- 原 Pattern Coverage 只问「经验池或复习计划里有没有、有几条 \(s\)」，对应 \(n_s>0\) 与 \(n_s\)。它仍然有用，因为没有覆盖（\(n_s=0\)）就没有暴露：ctrl_cal、b05_tf00/tf25、b10_tf00 都在 0 附近。但它不足以预测恢复量：同样 1 条，放在第 159 位（\(E=1\)）主指标约 0.10，放在第 143 位（\(E=3\text{–}4\)）约 0.39–0.47。
- 新口径：**Exposure Coverage** \(=(n_s, E_s, M_s)\) 三元组一起报。论文主张从「覆盖比预算更重要」改为「复习什么、在何时复习，比复习多少更重要」。预算只通过它带进来多少 target 暴露起作用：B32 格子里控制 mom 后，预算的偏秩相关是 −0.033。
- 这些都是**计划层面**的量，在训练前就能从冻结计划和插入位置算出来（训练后再用日志核对）。因此可以直接拿来做调度的目标函数。它们和 monitor（模型当前会不会）分开记录。

## 4. 计算方法与对应代码

- 已有训练：`scripts/p2_timing_audit.py` 的 `timing()` 读 `training_log.jsonl` 和 `train_summary.json`，输出逐条 \(a_i\)、Σafter、first、last、mom。结果在 `runs_ext_e3b2_timing/analysis/timing_audit.json` 的 `rows` 与 `grid_rows` 中。
- P3：`fac_tinyagent/p3_count_timing.py` 的 `target_timing()` 用同一口径，在 summarize 里逐种子输出 n、Σafter、mom。build 阶段的预测值写在 `data_ext_p3_count_timing/manifest.json` 的 `targets_predicted` / `sum_after_pred` / `mom_pred`。
- 作图：`scripts/p3_exposure_figures.py`。输出在 `runs_ext_p3_count_timing/analysis/figures/`：
  - `fig_dose_B1_exposure.png`：B1 剂量曲线，左图横轴是条数，右图是 Σafter；
  - `fig_dose_B1_mom.png`：同上，右图横轴换成 mom；
  - `fig_budget_B32_exposure.png`：预算格子，只用 B32，27 点，横轴依次为预算、Σafter、mom；
  - `fig_budget_B1_exposure.png`：预算格子中有 B1 的 12 点。
  
  B1 与 B32 分图，不混算，正式口径是 B1。P3 完成后重跑该脚本，P3 三个臂会以空心星号叠加在剂量图上。项目 `.venv` 没有 matplotlib，也不往里装，脚本用任意带 matplotlib 的 Python 运行：`python scripts/p3_exposure_figures.py --root <项目根>`。

## 5. 目前数值（B1，来自 timing_audit，只描述）

| 臂（三种子） | n | Σafter 均值 | mom 均值 | B1 主指标均值 |
|---|---|---|---|---|
| dose_db1 | 1 | 1.0 | 0.100 | 0.100 |
| dose_db1_pos143 | 1 | 3.3 | 0.295 | 0.389 |
| target_other_pos143 | 1 | 4.0 | 0.344 | 0.467 |
| dose_db2 | 2 | 3.3 | 0.320 | 0.400 |
| dose_db3 | 3 | 5.3 | 0.501 | 0.578 |
| dose_db4 | 4 | 9.0 | 0.815 | 0.800 |
| dose_db6 | 6 | 15.7 | 1.385 | 1.000 |

P3 的计划值：dose_db1_pos127 为 n=1、Σafter=6、mom=0.469；dose_db4_late 为 n=4、Σafter=6、mom=0.580；dose_db1_pos95 为 n=1、Σafter=11、mom=0.686。三个种子相同。

## 6. 待 P3 结果后再定的事

- 如果 pos127 ≈ db4_late，主文用 Σafter（或 mom）单一暴露量，条数降为附表。
- 如果 db4_late 更高，Exposure Coverage 要加一个多样性项，例如 \(E_s\) 加上 \(n_s^{\text{uniq}}\) 的交互，或按不同条目分别求和后取凹函数。
- 如果 pos127 更高，mom 这类偏向「少而早」的度量会比 Σafter 更贴近。
- pos95 与 pos127 的比较决定暴露是单调、饱和还是会被覆盖。如果是饱和或被覆盖，要加一个饱和形式，或者加一个关于后续新任务更新干扰的项。
