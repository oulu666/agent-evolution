# P10 dev48输出字段澄清：事前协议与判断标准

范围：仅新增48次终答生成，三份ordinary固定权重；复用已完成dev72的全部48条缓存上下文/原始答案，不重新生成工具调用或任何baseline。不训练、不跑正式卷、不改冻结dev和评分。主助手只放行本阶段，结束后不自动训练。

## 原任务审计及歧义
原问题为 Find lines containing ... Which complete matching line occurs first/last in the file?；gold和训练最后一回合为完整text字符串，且与对应匹配项text逐字相等。工具说明只说return matching lines，系统只约定answer为任意value，没有显式规定必须取text而非line字段。完整行的语义偏向文本，但存在输出单位/字段操作说明不充分，故本阶段检验协议澄清，不把低分全称模型能力缺口。没有错金标证据，不接受行号替代原gold。

## 唯一固定干预（全部48条件相同）
追加到原TOOL RESULT消息末尾，不改原问题、实际/给定调用、观察内容或排列：
Output-field clarification: In the answer field, return the complete value of the selected matching item's text field, not its line field and not only a number extracted from its text. Keep the task's original selection instruction unchanged.
没有目标答案、目标行号、最大/最小行号提示或新选择规则，不挑选/删除工具返回项。

## 最小样本与链路
3种子×4文件×2意图×2显示=48次新增answer-only。正常24条复用已正确执行的缓存调用与观察；逆序24条复用oracle正确调用与逆序观察。原48条是开发基线，不重跑。正常可报告cached-trajectory Joint，但不是新执行E2E；逆序仍不是E2E。预算48新增生成，max_new_tokens128、greedy、batch1、0 optimizer。
先seed08首文件4次生成通过真实推理/落盘/计费/参数不变E2E基础设施关卡，再放行余44次；答案正确率不是接口验收条件。

## 预先判断（不根据新答案改）
主假设为输出单位解释：正常严格正确数相对缓存3/24至少增加12/24，且原文件匹配项选择身份正确数不低于缓存24/24。只报告提示/协议收益，不叫训练或未见泛化收益。
逐条件报告严格答案、输出单位、选择项身份前后、正确身份但错误单位的修复、身份改变/损害。使用既有后验解析规则解释身份（完整text；line或line:数字；唯一行内数值），绝不据此更改严格分或自动补答案。
逆序的严格分和原文件选择正确数单列；若身份正确数增加，称提示诱导的选择收益而非只有单位收益，仍不归因于模型更新。若只有正常text改善、逆序仍错，说明单位与原坐标规则分离。all4为混合缓存链路，不叫四条件E2E。
若正常修复不足或选项身份退化，记录失败，不换提示、不追加格点。正式卷仍封存，dev改善不外推。

## 安全和后续边界
沿用已验收原守卫，UTF8 Windows进程检查必须成功，功率上限>=60W、无Apex/STOP/其他任务才启动。持续守卫只停自己，不清STOP、不停GPT、不自动恢复。模型/adapter前后hash不变。后续任何训练由主助手另行决定；Calendar解释只引用P9既有CPU审计。