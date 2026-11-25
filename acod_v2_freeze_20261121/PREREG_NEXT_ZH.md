# 下一轮预注册边界：当前停在冻结，不启动

冻结本文件不等于授权推理。此次0模型加载、0tokenizer、0新生成、0GPU、0训练；CPU有实际成本，见验收报告。

## 必须先满足的执行条件
1. 用户另行明确授权新推理；先复核本manifest、CPU测试、数据独立validator、所有旧资产哈希和公开/评分路径。
2. 冻结所用checkpoint身份、环境、逐条持久化/超时/恢复runner的新源码；模型消息只能由interfaces.model_messages产生。此目录没有自动执行模型的runner。
3. 仍用Windows r5apex检查、用户/历史STOP与GPU并发守卫，不自动清STOP、不训练、不修改功耗。GPU忙/游戏/资源不足时不争用。
4. B1 greedy、max_new_tokens<=128；不得改B32提速后当同一协议。两checkpoint只说明跨checkpoint，非跨模型家族。记录失败尝试、raw、syntax/strict/behavior分别记录、实际token/time与参数前后摘要。
5. 本阶段不得依据保留模型结果选择提示、规则、阈值；如以后发现协议错误，另起版本并清楚标为已暴露，不原地追分。

## 有界后续规模与预算（尚未执行）
保留16题×7视图（original、reverse/rotate/swap/value/line、reserved组合）×至多2已有冻结checkpoint，上限224次答案生成，失败尝试占上限。只测给定只读observation后的回答，不测真实API工具选择/端到端成功。开发输入不自动追加模型矩阵。

original作为各策略共同付费观测；追加查询预算1/2/4（5候选中至少仍有1未查询，且reserved始终只供评分）。固定顺序见POOL；随机seed0..19离线重放均值，不把重复模拟当新自然样本。GBS与IG若路径相同则合并经验结果。先一次采集固定候选响应表再重放时必须准确标注，不称各策略在线主动模型实验。

## 预注册指标
- 主诊断量：reserved自然响应的typed answer预测集合coverage，同时报告集合宽度（distinct typed values）和相容行为等价类数。歧义保留并集，不挑有利成员；类数减少本身不是成功。
- 报告overall coverage（reserved无法行为解析计未覆盖）与reserved行为可解析条件下coverage；另报reserved解析率，避免隐藏语法失败。集合为空为unknown；存在unparsed/multiple-object观测时单独报告证据不足/拒判，不硬消去假设。
- 错误具体化：在仅输出一个typed预测值时，reserved可解析值不在该预测集合的次数/单值预测次数；另报不可解析reserved数，不能称根因误归因准确率。
- strict syntax / strict schema / strict answer分开统计；strict score只读scorer_only gold。行为解析的wrapper恢复、行号有损解释/歧义、重复text row_ids多值另列，不把行为归一化改善写成严格正确率提升。
- 开放世界：自然模型没有root-cause gold，不报告closed-world根因准确率或未经验证的数值置信度/校准。模拟器标签仅为确定规则工程oracle。
- 成本：采集全表original+pool+reserved、失败尝试总cost独立报告；离线策略original+实际查询项的calls/tokens/time及selector CPU计算单报，reserved评分成本不偷送selector。IG使用已冻结输入字节cost代理，不当精确token/延迟预测。
- 按checkpoint、构建族、基础fixture聚合；配对意图/视图/随机重放非独立样本。16题仅工程/诊断验证，不承诺功效或显著性；不据这一轮或首轮小样本筛掉方法。

## 变换约束
permutation只改显示，不改原坐标/成员；value对完整text双射，保留重复等价和record分段数；line严格递增3*l+5，并重建片段offset/记录start_line。二者可新建快照，输出关系为双射映射而非一律字面不变。scope/included不能变化。raw观察与normalized rows必须由独立validator一致还原，否则不准开跑。未支持的复杂操作/坐标冲突/缺失text不适用并拒绝。