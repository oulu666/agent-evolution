# 过夜决定 · 2026-11-27（Asia/Shanghai）

本稿只登记已经写进仓库的决定。没有新算法，没有新计分，没有新增案例，也没有重新执行库或模型。密封的 pandas、Pillow、SciPy 材料没有打开。`repair_gate`、`dev_parallel`、`boundary_gap`、`contract_binding`、`catalog_gap_analysis` 都没有改写。本稿只引用已有报告和提交；`dev_parallel` 保持原样，本稿不给它新的结论。

写稿时 `origin/main` 的顶端是 `6c0b769de2fdab7d4a9922d5010b757d3637cfe8`，即 PR #3 的 squash 合并。

## 今夜关闭的开发线

### XlsxWriter 列隐藏修复门

证据是 `809bf36121a1503a703ccb870d5ac01d7a63a75a`（2026-11-26 23:42 +0800）。该提交写入 [repair_gate/REPORT_ZH.md](repair_gate/REPORT_ZH.md)、`repair_gate/results/summary.json`，以及四份归档工作簿 `3.3.0-19-original.xlsx`、`3.3.0-19-repaired.xlsx`、`3.3.0-25-original.xlsx`、`3.3.0-25-repaired.xlsx`。汇总里的 `historical_changes` 是 1。

原动作集上，固定检查、A、B、C 都是正确 78、暂缓 2。允许这一次局部修复之后，四者都是正确 80。A、B、C 相对静态检查的新增检出是 0，额外探针是 0，交付列相同。[repair_gate/protocol.md](repair_gate/protocol.md) 把独立单位写成一项历史修复；80 是配对的输入—版本情形，用来逐项审计。这条开发优化结束。

### attrs #1427 / #1428 的主动验证

证据是 PR #1，squash 合并为 `7357c2ecac9be1bd04d9a09785eaf64032ef1a71`。结果产生之前，协议和 `run.py` 冻结于 `421c5b715ea3f1cfc049389a43722beea29fc2d4`。归档报告是 [boundary_gap/REPORT_ZH.md](boundary_gap/REPORT_ZH.md)。对象是一项历史修复：议题 [#1427](https://github.com/python-attrs/attrs/issues/1427)、拉取请求 [#1428](https://github.com/python-attrs/attrs/pull/1428)。它不进入正式四项分母。决定是停止。

只看返回对象时，直接检查是正确 3、错误 1、暂缓 0，损失 5。契约变形、反事实消除、反馈条件化选问和最优固定预排都是正确 3、错误 0、暂缓 1。后三种的额外调用是 2；契约变形的额外调用是 4。显式探针改变处置之后，记录的下一问是停止。继续条件所要求的两种真实后继请求没有出现。正确交付没有增加，仍是 3。

第一问可见公开回调时，五种方法都是正确 3、错误 0、暂缓 1，额外调用 0。直接检查已经给出裁决。

### 公开契约绑定：先收窄

证据是计分前的冻结提交 `22a843467bfdc9d7b9663c0582f05f37cecd3a77`。提交说明是 “Freeze public contract-binding feasibility before scoring.”，父提交是 `7357c2ec`。`contract_binding/results/summary.json` 的 `freeze_commit` 记录同一 SHA；`protocol.md` 的 SHA-256 是 `4ec1f794fcc36155c1f9e2842f932d27467e251e8b27cd72e90cbafca97e5cba`。该冻结提交可按完整 SHA 取到。squash 合并进 main 的是 PR #2，`62722cff5ad9e85261318ec1b0f87e27302f0bf0`。报告是 [contract_binding/REPORT_ZH.md](contract_binding/REPORT_ZH.md)。`decision` 为 `refine`，理由是 `catalog_gap`。

分母是 12 个独立公开组。`bind` 和 `jdoctor_pattern` 都是 0/12 可执行检查。`jdoctor_pattern` 只转写 Toradocu 3.0 的 `simpleMatch` 谓词，并接到完整返回值。`status_only` 是 5/12，五次都是边界调用抛异常、修复版不再抛。Jdoctor 原程序、SPARK 形式契约生成、Gay 等 2015 的变异体预言选择、AGORA+ 原程序、SpecFuzzer，以及 Hypothesis 与已冻结合成器，都列在 `not_run`。因此没有工具排名。

### 目录缺口分析：随后停止

证据是分析协议提交 `f40de3285593d246fa03e969826e6375c654d426`。提交说明是 “Register the catalog-gap analysis rule before classification.”，父提交是 `62722cff`。分类写在这次冻结之后。squash 合并进 main 的是 PR #3，`6c0b769de`。报告是 [catalog_gap_analysis/REPORT_ZH.md](catalog_gap_analysis/REPORT_ZH.md)。`results/analysis.json` 里 `new_scoring_run` 为 false，`ranking` 为 null，`decision` 为 `drop`，理由是 `recorded_drift_not_stated_as_predicate`。

状态和粗字段看不见的 7 组，父文档没有把记录到的那个差异写成可检查谓词。其中 Rich #3718 的差异是标题背景，PrettyTable #356 的差异是底角字形 `└` 与 `├`。协议事先写下的三种更窄改写只做走查：去掉反引号后再跑 `simpleMatch`、执行 gettext 复数槽、把肯定式 should be 改写成 is。四处走查记录的 `separates_blind_group` 都是 false，没有分开盲组，也不记成方法分数。

契约绑定原来的收窄结论保持原样，不重算。分析之后的决定是停止，不另开计分协议。

重启这一方向所需要的新证据，写在 [catalog_gap_analysis/protocol.md](catalog_gap_analysis/protocol.md)：某一盲组的父文本里，有一句写明了这次记录的修复边界返回值，或写明了一个能用冻结 `holds` 分开两侧、且不误伤普通输入的质量词。

## 仍然有效，且不得提前启动

[protocol.md](protocol.md) 的有效期仍是北京时间 2026-11-26 至 2026-12-10。方法冻结是 11 月 30 日至 12 月 2 日，成对执行是 12 月 3 日至 7 日，揭盲是 12 月 8 日至 10 日。在这个窗口之前，不开始成对主比较。

公开必要性审计的口径提交是 `0999871b8e8cbb796d7d527cd265ed60203d0bcd`，公开计数在 [NECESSITY_AUDIT_ZH.md](NECESSITY_AUDIT_ZH.md)：4/4 项在首次请求后可判定，0/4 项已绑定为当时允许的可执行判据，进入中间反馈分支审计的是 0 项。密封标签保持关闭。正式四项变化的分母保持为筛查登记的分母；开发侧的成功次数不替换它。三次额外调用的额度不扩大。已暂停的 ESWA 原型不重启。ISSRE 已冻结的样本、答卷和论文分母沿用各自协议。

已经识别出的失败，恢复仍是能力问题。列隐藏报告写明，那次修复依据已知公开故障人工设计，收益归在共享的局部修复，不能归为自动合成修复或跨项目泛化。以后若出现可泛化的自动修复，再另行按新证据登记。

ISSRE 的实证叙述可以把这些负结果，以及“父文档没有把记录到的差异写成可检查谓词”，用作机制证据。契约绑定和目录缺口分析都没有产生方法排名。

## 11 月 30 日方法冻结清单

窗口按协议为 2026-11-30 至 2026-12-02。下列各项只转写 [protocol.md](protocol.md)「11 月 30 日–12 月 2 日 · 冻结方法」和仓库根目录 [AGENTS.md](../../AGENTS.md) 里开跑前已经写明的义务。方向判别的种子、损失权重和字段组仍以 [direction_gate.md](direction_gate.md) 原文为准。清单不含密封案例。本过夜决定不勾选这些项；勾选属于冻结窗口里的动作。

### 协议点名的冻结项

- [ ] 共同资料包
- [ ] 静态序列
- [ ] 逐字段反事实
- [ ] 共同处置和风险计分
- [ ] 成对运行前，对所有可部署参数、具体任务注册表、每项合理预期和处置规则做哈希冻结
- [ ] 主比较受 11 月 26 日登记的方向判别、预算和反事实归因细则约束
- [ ] 共享首问之后，每个方法的全部在线工具操作受同一个三次额度约束；另列成本的复位、备用和恢复如包含在线工具调用，也占用该额度

### AGENTS.md 要求在开跑前完成的登记

- [ ] 本轮假设、运行入口、配置、数据划分、主指标与预算已提交并推送到 GitHub，提交号已记录
- [ ] 能共享的基线只运行一次；各候选使用相同的评测条件、独立输出目录
- [ ] 其他 ESWA 原型保持暂停；ISSRE 已冻结的样本、答卷和论文分母沿用各自协议
- [ ] 已冻结方向若要重启，写明出现了什么新证据
