# P13 Phase 0：前瞻局部干扰筛查（冻结协议）

2026-11-18 北京时间。只新增 P13 文件，不改变旧实验/盲卷/训练器，不推送。

## 判断与目标
DG-MIR 有合理研究动机，但三模块叠加不构成已证明创新，也不能保证达到 CCF-B。P6 开发梯度分配未优于固定策略，P7 NLL改善未转成严格Joint收益；本轮不能重复只测loss的故事。
只检验：在真实 E4 Calendar 中点、真实后续新数据顺序下，使用保存的 PagedAdamW8bit 动量、LoRA、scaler和RNG做两次局部虚拟更新，开发探针的 ΔNLL 能否预报严格Joint的正确→错误。
这不是在P12最终模型上反推历史因果；两批为真实后续 Calendar 新数据连续8条（顺序80:88及88:96），有意不插入旧回放，故为新流更新的局部反事实，不冒充完整P12训练轨迹。Calendar是此阶段正在学习的工具族，旧/新技能沿用P12报告口径而非新任务到达时序。

## 固定规模和输入
- 首个已有种子20261108；现有E4中点及真实优化器状态，QLoRA配置不变。
- 新建2031年Calendar fixture；16条候选（每技能8），24条开发探针（每技能12），日期、实体与历史数据隔离。候选与探针不同日期。只用开发探针，不读取P12盲卷调参。
- 前缀、虚拟步1、虚拟步2：各24条严格B1开发生成，共72 episodes、144次generate；各40条gold轨迹NLL，共120次额外teacher-forced forward。
- 两批各8个forward/backward，累计2个临时optimizer步骤；不算正式训练步，不保存新adapter。候选前8条（每技能4）额外8次forward/backward计算完整LoRA梯度余弦，非GSS复现、不参与本轮选择。
- 全部在finally中恢复LoRA/optimizer/scaler/RNG/module modes，做语义sha256比对。只在新P13目录写日志/审计，模型状态只保存在内存。
- 若无事件，不扩批、不换种子、不调提示追结果。普通/改写/guidance不改变本轮选择决策，故删去；提示差不能识别真实/伪遗忘。

## 提前冻结的执行gate
1. 工程：输入哈希、完整状态恢复、评分自检、有限loss、SQL反例单测全部通过。
2. 排序可用：16候选的clipped ΔNLL至少4条为正、至少4个不同值(1e-6精度)，top4不同时等同当前高loss或高token成本top4；两批至少一批满足。
3. Joint可识别：两批共48个配对转移中，baseline-correct→wrong至少3个；同一探针在两批出现不是独立样本，不能报显著性。
4. 初步信号：在各批baseline-correct的合并配对中，ΔNLL预报退化AUROC至少0.65且严格高于原NLL与token成本；top四分之一退化率高于其余。
四项均通过只允许建议下一轮单种子、等预算MIR对随机的训练pilot，不自动开训。少于3退化为不可识别；其余未过为当前配置不升级，不断言MIR路线无效。不进行5种子3臂训练。

## SQL CPU验收
原来score>阈值再降序topk，在合格记录>=k时漏WHERE仍可能同答案；仅增加低分无效。新独立fixture必须同时有不足k个合格、0个合格、边界相等与混合比较反例。严格SQL参数与执行语义分别报告；合法等价SQL允许语义正确而严格不正确。原盲卷与原分数不修改。

## 文献核查（父流程已打开原文）
- MIR机制成立：https://proceedings.neurips.cc/paper_files/paper/2019/hash/15825aee15eb335cc13f9b559f166ee8-Abstract.html
- GSS是梯度特征驱动的记忆库选择，不是任意余弦加权即等价：https://proceedings.neurips.cc/paper_files/paper/2019/hash/e562cd9c0768d5464b64cf61da7fc6bb-Abstract.html
- RGD-R §3.1用正确rationale困惑度比值与动态回放，非F/P准确率差；有答案/正确rationale导向GCG，不能据无答案提示推断参数能力：https://aclanthology.org/2025.findings-acl.1212/
- Angle Matters是两层CNN信号向量/样本相对prototype夹角分析，非LLM任务梯度夹角结论：https://proceedings.mlr.press/v267/wan25d.html
- STE领域相关但设置不同：https://aclanthology.org/2024.acl-long.570/
- 未具名2026 LLA未核，不作本轮依据。

## 安全与成本
沿用项目GPU守卫并补全Apex进程匹配；游戏、任何STOP、功耗上限<60W、其它GPU项目任务均不启动/立即中止。绝不清STOP或杀游戏。监督器每3秒检查，日志断点可查；所有额外forward/backward、生成、tokens、耗时与峰值显存单列。7494tokens/22条/23步是P12合同，不强塞进诊断。
