# agent-evolution

本仓库记录从小模型工具使用、自进化与修复实验，到工具契约验证和工程诊断评阅的研究过程。按研究问题查找报告、实现和结果时，可从下表进入。

后续实验采用[云电脑并行验证与 GitHub 同步约定](AGENTS.md)。

| 研究阶段 | 入口 |
|---|---|
| 早期推箱子实验：教师指导、撤回计划与记忆迁移 | [实验脚本与运行记录](pilot/) |
| TinyAgent 旧工具保持、新工具学习与 EAAR | [P11 实验报告](EXT_REPORT_20261118_p11_eaar_v1_ZH.md) · [P12 设计](research/P12_EAAR_V2_PLAN_20261118_ZH.md) |
| ACOD 任务、预算与解码实验 | [第一轮](acod_round1_20261121/) · [第二版冻结材料](acod_v2_freeze_20261121/) · [部分评测](acod_v2_eval_20261122/) · [兼容评测](acod_compat_20261122/) |
| RSI、接口语义和反例修复 | [RSI 先导实验](research/RSI_PILOT_20261122_ZH.md) · [稀疏反馈](research/RSI_SPARSE_PROBES_REPORT_20261123_ZH.md) · [反例引导修订](research/COUNTEREXAMPLE_SEMANTIC_REPAIR_20261123_ZH.md) |
| 主动反证与跨工具实证 | [两步反证](research/TWO_STEP_FALSIFICATION_20261123_ZH.md) · [历史关系](research/HISTORY_RELATION_20261124_ZH.md) · [实证研究整合](research/EMPIRICAL_STUDY_20261124_ZH.md) |
| ESWA 方法准入与停止依据 | [EGATV](research/ESWA_EGATV_PILOT_20261125_ZH.md) · [CCET](research/ESWA_CCET_TRANSFER_20261125_ZH.md) · [DCEP](research/ESWA_DCEP_FEASIBILITY_20261125_ZH.md) · [多步发布审计](research/ESWA_COMPLEMENTARY_RELEASE_AUDIT_20261125_ZH.md) · [契约合成](research/ESWA_CONTRACT_SYNTHESIS_GATE_20261125_ZH.md) · [输入与判据联合合成](research/ESWA_INPUT_ORACLE_ADMISSION_20261125_ZH.md) |
| ISSRE 契约到测试的证据研究 | [英文主稿](research/issre_res/contract_to_test.pdf) · [实验台账](research/issre_res/evidence_ledger.csv) · [修复适用性](research/issre_res/operation_eligibility_20261125_ZH.md) · [评阅先导结果](research/issre_res/reviewer_pilot_20261125_ZH.md) · [冻结评阅协议](research/issre_reviewer_study/protocol.md) |

后期研究的脚本和协议集中在 [research](research/)，逐项结果多保存在仓库根目录下带日期的 `runs_*` 目录。各报告标有校准集、留出集、事后见证、停止条件或未完成项。人工评阅只公开汇总和方法；原始答卷及个人理由由主持人保管。模型权重、虚拟环境和本机缓存沿用仓库的排除规则。
