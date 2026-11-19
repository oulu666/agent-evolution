# P13 Phase0-B：一次有上限的前瞻干扰预测开发实验

2026-11-18，北京时间。用户已恢复并授权本轮；不包括后续正式MIR/DG-MIR训练。只新增Phase0B文件，不改旧报告/盲卷/数据/训练器/.venv，不push或发GPT。

## 一、客观修正与可证伪问题
上次无Joint转移只说明两步窗口不可识别。不能把延长诊断流程本身当论文贡献，也不能把原错地点题当遗忘。GPT建议中的扩规模有理由，但数量不是目的；本轮仅一次冻结三个原种子、完整自然Calendar后缀10步，不升学习率、不重复样本造遗忘。此窗口受P12错误启发，属探索性开发而非独立确认性证据。

主问题：在E4中点theta0，仅用真实下一批8条数据的一步虚拟PagedAdamW8bit更新得到的`max(0, NLL_call(theta_virtual1)-NLL_call(theta0))`，能否在更新发生前，预测未来完整10步自然新流后缀中的工具+参数正确→错误？基线是theta0的NLL_call与token成本。不用终点累计loss变化倒称提前预测。

主观测单位是同一开发探针自身的早期分数→该探针终点错误，这只是可预测性检验，不是replay候选选择泛化证据。候选48条与探针48条预先一一匹配相同技能/模板/事件数量/重复结构、不同实体日期；候选分数→匹配探针事件作为单列次分析，不事后近邻映射。

## 二、一次冻结的规模与阶段
- 种子：20261108/09/10，原E4前缀。每个后缀为原manifest顺序80:160，80条自然新样本、batch1/累积8，共10步；无回放、无clip、无scheduler，与原e3_train.py的优化方式一致。学习率1e-4，原QLoRA/AdamW状态不变。
- 两技能cal.count_date / cal.list_locations各24条探针，共48；候选各24，共48。不是额外扩展到其它技能。
- 日期问题均明确到某一天，不用故意歧义；6种明确日期措辞/表达×4种事件复杂度(0/1/3/5)。地点含空、单地点、重复、未排序多地点。候选/探针结构配对而不同日期与实体。
- 独立校准8题（每技能4）×3种子，只评前缀。校准只报告掌握度，不筛选/改写正式探针。生成器与全部case结构在任何GPU分数前锁定；校准后写formal_freeze收据，再允许正式开发探针生成与任何更新。这样不存在看后缀结果挑题；校准也不成为反复调题循环。
- 每种子：前缀NLL(96条)、一次虚拟更新(8 backward)、虚拟后NLL(96条)，随后恢复完整前缀。原前缀/后缀第5步/第10步各48条严格B1生成。只在0/5/10生成，不每步全生成；中点是预定次分析，不挑窗口。主检验始终0→10，0→5只描述。
- 正常上限：3×(10自然临时更新+1预测虚拟更新)=33临时optimizer步骤、264个backward样本；576个teacher-forced NLL forward样本；456个两回合生成episodes（校准24+正式432）、912次generate。所有都是额外诊断计算，绝非“纯评测、不训练”。不保存新训练adapter。

## 三、分段token合同
基于原chat模板完整token序列与fast-tokenizer offset mapping，必须与原tokenize_episode IDs/labels一致且不截断。
- call：第一assistant完整监督span，包含JSON、固定框架和im_end；主指标是此整段均值CE。
- tool_name：JSON的tool字符串内容覆盖的tokens；args：arguments对象覆盖的tokens。跨边界token按字符区间相交归属对应段；二者不能相交。其余call tokens显式归call_other（JSON键/标点/框架/EOS），不得漏标。
- final：第二assistant监督span，含EOS。tool_name/args/call_other/final四段不重叠且并集等于所有监督token；call=前三段并集。整轨迹NLL为全部监督token均值，每段以自身token数为分母，不能把分段均值直接相加。空段失败停机，不以0替代。
- 保存每条的token masks、解码摘要、分母及CPU验收。主call指标以外的名称/参数/final/Joint均为次要，不挑表现最好的段当主结论。final用gold观测teacher forcing，与实际生成错误可能存在条件差异。

## 四、at-risk与预注册gate
全部48探针保留，不跨种子只挑最易题。每种子的at-risk由该种子0步生成定义：主分析须tool_correct AND arguments_correct；Joint、名称、参数、final各自按其0步正确集合单独报告。仅0→10为主；中点和其它组件不混入主样本、不把重复探针当独立。

主gate同时满足才记“有预测信号，仍无pilot启动授权”：
1. 工程、冻结、精确恢复、时序与分段验收通过；
2. 至少2/3种子各有>=5条主工具+参数正确→错误事件，且各>=5条at-risk未退化；不足即UNIDENTIFIABLE，不扩批/换种子/改提示；
3. 可分析种子的within-seed AUROC宏平均>=0.65，且严格高于初始NLL_call与TokenCost；
4. 1000次固定随机种子20261118的双向种子×探针聚类bootstrap，AUROC相对两基线差的95%区间下界均>0，且有效replicate>=800。三种子区间不代表强总体证据；0.65只是探索gate不是显著性/投稿门槛。
同时报告AUPRC/AP、正例率、Top四分位Recall（ties按分数组分配期望命中），每种子与宏平均，候选映射结果单列。不因次指标好看越过主gate。

## 五、工程、成本和停止
复用已核SQL/文献结论，不再做SQL/GSS/提示矩阵。单GPU守卫：Windows r5apex/r5apex_dx12/Apex、任何粘性STOP、功耗上限<60W或其它GPU项目任务均不启动/停止，不清STOP不杀游戏。监督器3秒检查并记整卡已观测显存；模型forward hook记录CausalLM级forward调用，backward显式计数，保留每段GPU peak，不使用会重置峰值的旧整族评测包装器。

生成/测loss前后恢复完整LoRA、optimizer、scaler、RNG、module modes并hash核验；预测虚拟步结束后与前缀完全一致；整个10步临时轨迹结束finally恢复前缀，再验原文件hash。每步有state hash和progress，结果有绑定hash。意外重启不保存状态时从原前缀确定性重建，原已完成节点只在完整状态hash一致时复用；重建成本单列，最多每种子2次attempt（正常33临时步，总硬上限66临时步；校准最多每种子2次）。部分结果不覆盖。游戏导致的STOP保持粘性，不能绕过自动重试。

任何主gate结果都不自动开2/3臂训练，不扩大本轮。最终中文独立报告、交接及机器审计写入新的Phase0B路径。
