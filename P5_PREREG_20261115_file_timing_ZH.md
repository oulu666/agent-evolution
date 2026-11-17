# P5 预注册：File 固定经验集合的暴露时机验证

2026-11-15，北京时间；写于任何P5 GPU训练/评测之前。当前仅设计、CPU检查，等待协调者审核后启动。

## 研究判断及纠偏
- 不把“真遗忘/重新激活/能力缺口”当作三个可由前后成绩直接识别且互斥的先验类别。重新激活是复习响应，当前不建状态分类器。
- P4 list_tables 的单条early与两条mid同时改变经验身份、条数和位置，不能识别条数独立因果，不能推出同模式普遍至少两条。
- P4 两个饱和模型均未达到预注册胜出条件，不能作为已验证预测器。不额外跑模型赛马。
- 本轮只问：在File工具相同四条经验、相同预算下，提前给予后续更新的固定调度是否优于分散及晚插？这不是完整自适应Agent，也不声称识别早×广交互。

## 既有证据及范围
P1 B1逐题原始结果：`runs_ext_p1_b1/evaluation/A_seed{seed}_{stage_02_database,stage_03_python,none}/natv2_file/results.jsonl`。
按 joint_success 重新CPU计数：stage_02_database为0/30、0/30、0/30；stage_03_python为0/30、1/30、14/30；Calendar无复习末态none为0/30、13/30、22/30。
旧P1报告stage_03一行与原始B1 joint计数不一致，本轮以原始逐题B1为准，不能混用final_correct。
所以file.search_last在选定T0考试上是原有能力缺口，但种子09、10后续已有部分能力；不称三个种子当前全不会，亦不称真遗忘。
未重测step80 prefix：none不是prefix。本轮直接配对比较相同prefix分出的调度，不以缺失prefix分数推断遗忘。T0/none只作背景参照，不作本轮额外GPU基线。

## 唯一实验：3臂×3种子，共9训练分支
- Qwen3-0.6B QLoRA，种子20261108/09/10；每种子复用E4 Calendar step80相同前缀（包含参数/优化器/RNG状态），只读旧资产。
- 23总optimizer steps（前缀10，后缀13），后缀80个Calendar microstep+22个replay microstep。约7494 replay input tokens，同一种子三臂精确相等；与名义预算偏差<=1%。新数据顺序、训练超参、候选池和评测协议B1一致。
- 四条File经验固定为e4_last_match-000、006、007、014。仅依据训练池选择：覆盖四个不同关键词、末匹配行6/4/5/2、2/3个匹配以及数值/常规文本两种答案形式。不是数据驱动学到的选择器，也不说明四条最优。
- 从每种子dose_db4计划起，只移除原1条File target和3条非search_first的File背景，换入固定4条；移除的三条以距7494 token最近为唯一目标、索引字典序破同分。仍22条，File/DB/Python样本数不变。DB/Python target与File search_first条目的槽位在三臂固定。其它背景保持相对顺序，填补空槽；这是预算内target与背景的调度交换，不声称背景绝对时机完全不变。
- 0-based replay索引：early=[0,1,2,3]；uniform=[0,7,14,21]；late=[18,19,20,21]。4条身份及顺序在三臂相同。
- 十个插入槽87、95、103、111、119、127、135、143、151、159；after沿用P3/P4计入包含该经验的更新。确切逐条slot/after、移除经验ID、实际token写入冻结plan和manifest；CPU干跑与旧真实训练日志交叉核对，运行后再核对实际训练日志。
- early是固定暴露感知候选规则；uniform是等距分散的target调度，不是历史全池Uniform Replay算法。late为集中晚插。Random去掉：3种子下随机调度方差与训练随机性混在一起，且不能增加本轮核心辨识力。不添加覆盖消融，因此本轮不检验广度优势。

## 评测及冻结
- 主指标：原有natv2_file 30题 joint_success；逐种子报告tool/arguments/final分项。全部B1 greedy，不能用final替代joint。
- 次指标：phase2 File全30题及search_last 8题/其余22题；natv2_database 30题、natv2_python 30题、Calendar v3fix 30题。保留跨模式/旧目标与新任务代价，总计每分支150题，不跑150题Calendar全卷和全量MMLU。
- 不造新探针；旧测试集只读、hash冻结。不得根据任何P5测试结果调经验、槽位或阈值。只做一次9分支；失败不自动加臂、加种子或加模型。
- manifest冻结实现/方案/候选池/训练输入/初始adapter及前缀/测试与fixture hashes；CPU dry使用同tokenizer和loss masking核对每条预算、分段位置和23步。冻结后若发现实现错误，必须新增修订而不能用测试反馈改设计。

## 判据与失败解释
- 主要配对：early−uniform和early−late，逐种子报告差及均值/SD。“方向一致”仅指三个种子差均>0；均值提高>=0.10且两个比较都方向一致，才称本轮支持固定早插具有可用优势（10个百分点为实用阈值，非统计检验）。
- 若只胜late不胜uniform：只支持避免训练末端集中，不支持占用最早槽位。
- 若都接近满分、或三臂都低、或种子分歧：分别解释为当前难度天花板、四条/既有模板不足、或种子依赖；均不能宣称普遍早而广或自适应策略成功。不自动补实验。
- 若early相对uniform任一种子非target File/DB/Python/Calendar joint下降>0.10，明确报告代价，不当作无代价改进。仅描述，不追加免责实验。
- 该实验不能证明数量独立效应、覆盖收益、真正遗忘跨工具泛化或自动状态识别。

## 执行、预计时长、安全
仅新增`fac_tinyagent/p5_file_timing.py`、`scripts/*p5*20261115*`、`data_ext_p5_file_timing/`、`runs_ext_p5_file_timing/`及本轮中文报告/交接。环境、旧脚本/数据/实验/冻结测试不改。
预计9分支约1.5–3小时（据P4同机工作量量级，实际以GPU日志为准）；本轮无step80/T0额外评测。一个GPU子进程串行。
`run_p5_20261115.py`启动前检查r5apex、GPU计算进程、功耗上限>=60W。运行中每10秒查游戏/功耗；连续3次守卫检查失败则终止。检测游戏后写粘性STOP，用户明确允许后才能续跑；launcher不自动删除STOP。不得改功耗上限。使用flock防本轮重复队列。
完成后必须生成中文实验报告和交接，不自动启动P6。
