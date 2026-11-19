# P13 Phase0-B 有界CPU故障核查与交接



2026-11-19 00:49:39 +0800（北京时间）



## 真实状态

人工授权后已真实启动attempt02，00:40:23完成预测虚拟一步，随后重建断言失败，00:40:54监督器rc1；没有自然suffix步骤、没有完整预测终点。seed08两次attempt已用尽。所记录LoRA/optimizer/scaler/RNG/modes最后恢复精确、前缀文件hash未变。当前仅做本次CPU核查，未GPU重试、未验收final、未改代码/阈值/协议。



## 先纠正一个关键事实

nll_prefix.json的文件字节确实不同（time元数据不同），但其96条row payload全部逐值一致，6段NLL的max/mean差均为0，state_hash也相同。因此“更新前NLL已经数值不同”不受现有JSON支持；不能据文件hash差异错误定位到前向/量化载入。最早保存的可观测差异是虚拟更新后的LoRA/optimizer与NLL。



## 数值与排序（只描述，不据此改容差）

虚拟后call NLL：{"n": 96, "different": 96, "max_abs": 0.008372440934181213, "mean_abs": 0.0005545318762566845, "median_abs": 2.059858525171876e-05, "max_symmetric_relative": 0.23898082202574283}

call ΔNLL：{"n": 96, "different": 96, "max_abs": 0.008372440934181213, "mean_abs": 0.0005545318762566845, "median_abs": 2.059858525171876e-05, "max_symmetric_relative": 1.9522277097343002}

clipped call risk：{"n": 96, "different": 68, "max_abs": 0.003193426877260208, "mean_abs": 0.00020495722871298008, "median_abs": 5.469362804433331e-06, "max_symmetric_relative": 1.0}

候选call风险：Spearman=0.5521768313458789，严格成对逆序=170；Top4/8/12交集={'4': 2, '8': 5, '12': 8}

探针call风险：Spearman=0.5792896018332856，严格成对逆序=199；Top4/8/12交集={'4': 3, '8': 5, '12': 8}

全部分段max/mean/median、每段排序/ties/TopK名单见CPU_DIAGNOSIS_20261119.json。没有完整终点，不能判断AUROC/AUPRC或最终科学结论是否受影响；排序近似稳定也不等于精确状态重建通过。



## hash覆盖及可支持的解释

FS.capture仅收requires_grad参数、optimizer/scaler、四类RNG、named module.training和optimizer.initialized。冻结非LoRA参数、buffer与4bit quant_state/scales/codebooks不在此hash。因而origin_full_state_hash一致不是整个量化模型与计算环境的完整同一性证明。

模块training和RNG确实覆盖；dropout p及模型config/attention/use_cache、实际autocast dtype、TF32、cuDNN/SDPA/deterministic算法开关与进程环境未序列化。load_base_model未显式固定attention backend；prepare_model_for_kbit_training和gradient checkpointing启用，checkpoint默认use_reentrant警告存在。该路径未显式调用torch.use_deterministic_algorithms。utils.set_seed虽有cuDNN/CUBLAS设置，但Engine只恢复prefix RNG，并不调用它；且若事后才设PYTHONHASHSEED/CUBLAS也不能替代进程初始化前合同。

同一冻结batch顺序、mask、分母、单样本collator与输入token长度，且更新前各段完全一致，削弱“换题/错mask/重排/前向已漂移”的解释。不能排除反向或AdamW/量化优化器内部非确定性、未记录后端/隐藏状态、dropout执行历史或加载历史效应；现有日志没有梯度hash或运行时后端快照，不能唯一归因。模块模式/RNG初始化错误亦不能仅凭后验猜测；记录的前缀覆盖部分相同是反证约束。

两次power.limit不同仅是资源快照，不证明因果；不建议为验证这个猜测再改功率试跑。



## 严格断言的解释

断言验证的是预测表逐值重建，不是论文性能阈值。它确实发现了更新轨迹没有按合同逐位复现（LoRA/optimizer hash也不同），不是仅JSON时间戳触发。变化的科学影响目前未知；不能把严格失败直接升级为方法失效，也不能因TopK看似相近就悄悄epsilon放行。



## 最小修复选项（均未获重跑授权）

1. 首选操作性方案：持久化前缀、预测虚拟步后的LoRA/optimizer/scaler/RNG/modes检查点，并记录量化基座/quant_state、模型与后端设置指纹；恢复时加载保存状态，不再靠重新执行浮点更新重建。同一虚拟θv可在前缀评测后恢复作为自然step1，这会改变物理更新复用/成本账本，必须在操作性修订里明说，不能当原协议已如此执行。

2. 如需先定位重建性：单独明确授权一次工程诊断，建议固定1种子/1批次、同一内存前缀做2次临时更新（最多2 optimizer步、16 backward样本），前后各用固定8条训练侧候选NLL（合计32 forward），0 generate，记录梯度/参数/optimizer/RNG/量化与后端指纹并恢复。它不是新增科学样本，也不是把第三attempt改名后偷偷续跑。

3. 若用户选择继续原实验，需要明确批准一次性操作性修订和新的有界attempt额度（例如仅允许seed08一次额外attempt，原两次保持失败记录）；数据、主终点、门槛仍锁定。若保留原33步合同，必须先证明数值重建可行；若采用保存θv避免重算，须重新冻结物理步骤/成本合同。若明确改为保存θv并复用为step1，剩余三种子一次性全程预计30临时optimizer步/240 backward样本、576 NLL forward样本、432两回合episodes/864 generate，已完成校准24题仍复用；若另批准上述工程诊断，再单列2临时步/16 backward/32 NLL forward。原两失败虚拟步、25条部分生成及未完成调用继续计总成本。该预算与step1复用均须用户明示，不由“继续完成”推定。

不建议现在仅放宽float容差、仅关闭dropout、换attention/优化器/学习率或换种子救结果；这些会改变合同或方法，需新的明确修订，不能自动执行。



## 文件与权限边界

原attempt01/02、STOP及整卷guard归档不变；旧报告不覆盖。新增机器审计runs_ext_p13_phase0b/CPU_DIAGNOSIS_20261119.json。当前不启动任何新attempt/GPU定位，不push/发GPT，不跑成功态final。
