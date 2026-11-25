# ACOD v2 首次保留响应：执行与配对分析补充预注册

范围由原PREREG_NEXT_ZH.md约束：仅保留16题×7视图×2份原P9 ordinary checkpoint，最多224次答案生成（失败尝试占上限）。开发8题不进入模型矩阵。只新增本目录；不改v2、round1、旧runs/.venv/权重；不训练、不新增规则、不合成查询、不实现MDCS、不扩展CEFR、不push/付费API/外发。

## 原消息、原解码
严格调用冻结interfaces.model_messages；system/问题/原始observation之外不增加gold、规则、分组标签或未来响应。B1、原generate_with_usage greedy/use_cache=False、max_new_tokens128。每次原始raw和实际输入/输出token/time立即落盘；一次采集表格，随后离线重放各策略。全表采集与各策略original+所查询条目的成本分别报告，不把离线模拟称在线主动模型实验。

两模型身份、包版本、源文件hash、每条message hash、调用上限、方法/指标在PROTOCOL_LOCK.json中先锁定，之后才可运行worker。安全守卫沿用已验证r5apex/STOP/GPU并发/功率下限逻辑，并检查真实项目Python进程身份；发现游戏/STOP/检查失败即写本目录带owner/reason的STOP并终止，不清除任何STOP。不创建自动恢复任务。单generate60秒、总监督器1500秒，最多224次，不跑开放矩阵。

## 配对是否真的齐全：先检查输入，不看响应
记I为原始，R为reverse显示，C为rotate-left显示，S为swap前两项，V为冻结text双射，L为纯坐标映射3*l+5。实际冻结view：
original=I；reverse=R；rotate=C；swap=S；value=V；line=C∘L；reserved=R∘L∘V。

所以不能直接把original、reverse、value、reserved当成I/R/V/R∘V的二因素设计，reserved额外改了坐标；同样value与line的复合显示C，不是reserved的R。严格检查每个case全部已有单项的有序二合成，要求row身份、text、坐标、scope和显示顺序完整相等，而不只比选中text或忽略显示。

对存在完整四元组的单元才定义z_v=1[strict_correct(v)]、描述性contrast=z12-z1-z2+z0；“单项正常组合失败”要求base及两单项严格正确且各自schema有效，组合schema有效但严格错误。非法JSON/schema与原始已错的单位另列，不偷偷把正常改成行为规则一致。该contrast不是显著性交互检验，也不证明非加性或隐藏根因。

若0个完整配对，交互标记NOT ESTIMABLE而不是0例；不得新增查询补齐后冒称原预注册。可另报全池相容类对reserved的预测覆盖/失配，只能叫有限行为模型的跨视图预测一致性，不混为严格答案交互。

## 固定算法与指标
不改变原24组合、类型解析或等价类先验。fixed、random(seed0..19)、GBS-Gini、IG/输入字节cost使用相同候选池、可见观测、代价和预算1/2/4；core接口仅获得公开输入和已查询raw，不获得reserved response/gold。GBS/IG路径若相同合并经验解释。

四层结果分别保存：raw、syntax、严格schema/answer、behavior。9、"9"、"line 9"严格不相同；behavior可解析、有损解释、歧义与包装恢复另列，不补成严格正确。unknown仅指封闭24组合失配，不直接解释为真实条件切换。

主指标延用原预注册：reserved typed响应的overall与可解析条件coverage、预测集合宽度、相容类数、unknown、解析不足/拒判、错误具体化及单值预测中的reserved不可解析数。original成本共同计入；reserved仅评分，绝不更新selector。保留natural response本次首次使用后即标暴露，v3不能继续把它作独立最终测试。

基础单位只有8个fixture/2个构建族、first/last配对和同家族checkpoint相关；不把224视图当独立任务，不作小样本淘汰、功效或显著性主张。MDCS仅评必要性：如果后续要声称“最小”，必须另定合法空间、编辑/调用/长度成本及最优性范围；本次不实现、不启动。