# ACOD 首轮冻结协议（开发/工程，不是论文盲测）
本文件与 tasks.json、manifest.json 在模型加载前冻结。只新增本目录，不改旧数据、权重、.venv、runs、训练器或功耗。
目标：检验可观测规则可区分性与固定候选响应表的诊断/预测，不推断隐藏根因、不证明ACOD创新。
16任务：2个历史P9开发文件×first/last=4；新生成6文件×first/last=12，其中2文件重复text碰撞。历史与新开发分组报告，不使用旧正式P10/P14作盲测。新文件为免人工标注的确定性开发资产，不声称gold不可得。
操作只允许完整非空匹配集合、唯一正整数原行号、literal regex、first/last选完整text。空集、歧义行号、regex复杂替换、未知operator不适用应拒绝。显示顺序可变，line表示原坐标；value替换保持匹配且双射保留重复关系；line映射严格递增且重建文件；组合变换另建快照，不谎称工具源未变或答案一律不变。
每任务original+reverse/rotate/swap/value/line+heldout=7条答案生成。2个P9 ordinary seed20261108/20261109 checkpoint，总上限224次，断点按唯一ID逐条保存，失败调用也计账；每调用128新tokens、B1、原greedy/no-cache协议、无梯度/优化器/训练。原工具调用为oracle前缀，不评工具选择/E2E。GPU/进程/Windows Apex/全局及旧runs STOP守卫失败则停止，不自动清任何STOP；只在本目录写有来源reason的STOP。总超时20分钟、单generate超时60秒。
候选规则7类：coordinate、display_first/last、opposite、field_line、lex_max/min。每次只报告相容集合或unknown；singleton仍非确定真实机制。原始回答为共同已付成本；追加查询预算1/2/4，所有策略共享同一pool、解析、观测与预算。随机固定seed 0..19；fixed顺序reverse,rotate,swap,value,line；GBS用多响应Gini均衡划分；IG用均匀相容假设的熵/（预先tokenized输入+128），不是新算法。选择器API不接受未查询响应，reserved heldout从不参与选择/更新，只评预测。
报告每预算剩余候选/预测集合大小、heldout响应集合覆盖、unknown、singleton预测失配（不是根因误归因）、实际查询tokens/time。无相容规则时预测集合为空并拒判，不硬选类。自然行为没有规则gold，不报告根因准确率或伪造概率校准；经验覆盖不是校准置信度。模拟器独立报告规则/等价类恢复、闭集不适配与混合策略，另用小池最短区分子集作CPU参照。
候选响应只采集一次，各策略离线重放，不称在线主动模型试验；采集总成本与反事实策略成本分开，策略选择计算计时。预算是原始+追加k条，heldout是测量额外成本不送选择器。固定seed不是随机稳定性研究，未重复解码；B1/B32不混用。
不做小样本算法淘汰，不推断统计显著性；无主动优势照实报告。无跨新工具/任务族正式泛化证据；以后family split按基础文件及模板整体隔离，跨checkpoint/新工具的独立测试仍待后续授权。
