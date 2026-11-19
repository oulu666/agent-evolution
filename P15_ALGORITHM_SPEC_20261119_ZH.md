# P15 算法规格：层级诊断回放（Layer Replay，工作名）

2026-11-19，北京时间。不是以新名字冒充创新。待验证主张仅限：在同新数据流、同更新数、相同回放双token上限下，阶段锚定的分层诊断和层对齐监督能否改善旧技能保持而不牺牲新技能获取。未进行新颖性文献系统核查，不宣称参数遗忘因果或方法已有效。

## 两个核心模块（没有第三个隐含MIR模块）

所有操作以七skill为单位。每个skill首次训练阶段结束后，在固定dev子集建立一次锚`b_s`，以后不换峰值、不依test选锚。阶段2/3的更新0、64，对已学技能的同一固定dev题生成工具调用、真实执行后答案、gold-call+gold-observation答案。子集总88题：count_date8（4措辞各2），count_month12，locations20（20结构格各1），四字段各12；选择只用这些固定train/dev资源，不读test。它不是“8/12题判已掌握”的晋级门槛。

### 模块A：阶段锚定的分层预算分配

记当前正确率为c，T=工具名，A=参数，G=gold observation下最终答案。各值均在同skill同子集计算。

```
d_T=max(0,b_T-c_T)+0.25*(1-c_T)
d_A=max(0,b_A-c_A)+0.25*(1-c_A)
d_G=max(0,b_G-c_G)+0.25*(1-c_G)
r=max(d_T,d_A); f=d_G
q_s=1+2*(r+f)
p_s=0.25/K+0.75*q_s/sum(q)
```

K为已学skill数。25%是真正的归一化均匀混合下界，不是先随意加常数再误称均匀floor。第一项是相对首次学习锚的性能损失，第二项为固定权重的旧技能未熟练风险；**并不把所有低准确率称为遗忘**，也不解释为哪层参数已遗忘。

### 模块B：诊断层对齐的回放监督

- r>f：从被分配skill的train候选随机选完整episode，只监督整个工具调用assistant turn（含tool+args），其它标签mask为-100。
- f>r：只监督完整最终答案assistant turn。
- 相等（1e-12容差）：两个assistant turn都监督。

始终输入完整system/user/tool-call/tool-result/final聊天，不截断工具结果或答案，不裁剪字符串凑token。call mask不声称能在工具名/参数内部精确定位因果；只是它们共享的完整调用turn。gold observation的G与真实执行后的F分开保存，不能用G冒充端到端F。完整最终turn含原chat模板规定的结束token等，沿用旧tokenizer的assistant_spans。

每update回放输入≤4096、监督≤512；按概率在可容纳的已学skill之间重归一化，再从该skill所有可容纳train题均匀抽样，直到没有完整题可放入。允许有放回。利用率、实际token、mask模式、候选ID全部记账。装箱靠近上限时的可容纳性会造成长度偏好，必须披露；未进行跨池MIR打分或每步梯度冲突扫描。

## 对照及消融（规则事先固定）

|方法ID|定义|
|---|---|
|seqft|无回放；相同新流与128更新/阶段。总监督量自然少于回放方法，不伪称全部等监督。|
|uniform|在已学skill上均匀分配，再在该skill train池均匀选完整题，监督两个assistant turn。明确是**skill-uniform**，不是按696题全池样本均匀，避免480题地点主导。|
|p11_priority|七skill均使用旧P11 `classify_skill`原函数，分数逻辑不改；p∝1+priority；候选与装箱同uniform、监督both。是P11优先级适配基线，不是逐位重现旧P11十个slot/早插入方案。|
|layer_replay|模块A+B。|
|no_priority|去模块A、skill均匀；保留同样诊断及模块B。检验分层预算分配增量。|
|no_layer|保留A、所有回放都监督both；仍做同样诊断。检验层对齐监督增量。|
|full_replay（可选）|每update额外遍历所有已学group的全部train池一次，无replay cap；固定新流和更新仍一致。独立资源参照，不是等预算组、更不预设性能上界。默认不启动。|

P11七skill映射是恒等映射：count_date、count_month、list_locations、extract_title_sorted、extract_location_sorted、extract_id_sorted、extract_start_sorted，指标都由实际T/A/E/F/J生成。首次训练过的skill prefix_count为正（分类仅判断>0），未暴露skill不进Replay。原规则：J=0加3、0<J<.5加2、.5≤J<.75加1；无覆盖加2；有覆盖且J<.5加2；min(T,A,E)≥.75且F<.5再加1；高于.75没有优先项则0。保留原75%等**基线策略超参数**，但它不再定义科研上“已掌握/淘汰”，legacy `true_forgetting_prior`只作历史策略名字，不等于已证遗忘。候选池不再人为缩成原8条，所有方法共用完整训练候选，所有难度可选；不得看dev调好P11或新方法参数。

## 训练共性与额外成本

Qwen3-0.6B本地预训练基础模型+全新LoRA开始，r8/alpha16、七线性投影、dropout0，4bit NF4双量化fp16计算，所有方法相同。AdamW仅训练LoRA，lr1e-4、betas(.9,.999)、eps1e-8、weight_decay0，梯度范数clip1.0，无scheduler；三stage之间保留optimizer，不重新创建。optimizer一次更新累积完整新batch和Replay全部micro forward/backward，按该update实际监督token总数归一化；这会使Replay混合权重随实际mask利用率变化，属于本机制，不能宣称新任务梯度权重也完全相同。

额外诊断仅固定dev生成及14条固定train（每skill2）teacher-forced call/final NLL；后者每node一次、单次forward同时计算两种masked NLL。无额外诊断backward、虚更新、MIR、梯度冲突，不能宣称已做参数机制因果检验。所有dev生成/诊断包裹Python/numpy/torch CPU/CUDA RNG保存恢复、eval模式，恢复原模式；dropout为0而非用dev调优。CPU已测试同一optimizer_update引擎的真实梯度、optimizer/RNG精确续步；4bit/CUDA/AMP路径尚未执行，不假称GPU已验收。

## 固定终止与安全

每stage128个optimizer update，仅node00、node01/02/03为主评测checkpoint，更新64仅诊断不据结果分支延长训练。达到384次即结束，无正结果则接受负结论。不用两步/单种子科学晋级gate。任何数值、schema、磁盘、安全错误属于工程失败，记录后停止，不自动扩大预算或重试；未完成轨迹默认拒绝覆盖和自动恢复。CPU恢复测试不等于已实现任意中途GPU精确续跑；本版仅完整轨迹完成标记可被batch跳过，半途异常须单独审计恢复方案。
