# P6预注册：开发梯度驱动的一次预算规划（第一阶段为只读参数校准）

2026-11-15，北京时间；在任何P6 GPU校准、训练或模型评测前制定。本轮无实验结果。

## 1. 保留与拒绝GPT建议
保留：不同技能竞争共同replay预算；与强均衡/均匀时机基线比较；策略由可观察开发信号自动输出。拒绝：再复做P5 File时机；把真遗忘、重新激活、能力缺口当互斥oracle分类；看到能力缺口就硬插最早；Random加四模块消融凑组数；把已经看过的P4/P5正式测试当新泛化证据。
独立开发NLL/梯度只测局部损失下降方向，不是已测恢复速度或巩固所需步数。没有独立的时序响应信息，就不伪造“需要早插”的分类器。第一版聚焦自动预算分配，方法的时机默认分散；FixedEarly是挑战基线，而非方法假定。

## 2. 明确可计算机制（工作名DevGrad，不声称新颖命名）
观测输入仅限：同种子Calendar step80只读参数；四组新独立开发题（每组4题）；现有训练候选池；输入token成本。不读P4/P5测试结果、也不读本轮holdout输出来选策略。
技能组是任务元数据，不是规则偏好：db.list_tables、db.filter_cmp_top、file.search_last、py.median。算法对每组完全相同，不按名字给优先权。

令L_s为开发组s的每题assistant监督token平均交叉熵再按题均值。g_s=grad L_s，g=(sum_s g_s)/4。候选组s去重后最多8条，h_s为这些训练经验梯度的题均值。
B_s=max(0, dot(g,h_s)/(norm(h_s)+1e-12))。
这等价于沿单位长度候选梯度下降方向，宏平均开发NLL的一阶下降代理；不是Adam实际收益、非线性恢复速度或未来更新暴露模型。交叉组梯度负相关会降低效用，NLL本身不直接被叫作遗忘状态。

伪代码：
```
对每个组计算开发梯度g_s和训练候选均值梯度h_s
计算非负B_s
每组先分配1个replay（相同最低保留保障）
剩余6个target replay逐个选择最大 B_s / ((n_s+1)*next_input_tokens_s)
全部B为0时退回技能均衡计数
组内经验顺序由种子固定，与B无关；按此顺序取前n_s条并交错排列
经验内容不足时循环同一经验，明确记录为重复，不冒充多样覆盖
将10条target分散到固定target槽，12条非目标背景填其它槽
```
1/(n_s+1)是冻结的递减边际覆盖启发式，不声称已拟合真实饱和曲线。dev输出只决定一次规划，没有在线闭环、自适应停止或时机学习。

## 3. 三臂×三种子，正式训练共9分支
- balanced_uniform：四技能10条target均衡计数（每组2或3条，种子破同分），target分散。
- balanced_early：与balanced_uniform完整经验多重集合、token完全相同，只把target集中前段。
- devgrad_uniform：由上述公式自动分配同10个target名额；和balanced_uniform使用同组内候选顺序、同分散槽；它是检验开发梯度分配这一单机制的组。balanced_uniform同时充当去掉开发效用的关键消融。
这些是技能均衡基线，不冒称历史全池Uniform Replay；不加Random或四模块大消融。
种子20261108/09/10、Qwen3-0.6B QLoRA、相同E4 step80参数/优化器/RNG前缀；23总optimizer steps（前缀10+后缀13），102后缀microsteps=80 Calendar+22 replay。
三臂总replay input tokens同名义7494、允许<=1%离散偏差；实际逐条记录，报告配对差和成本。不得在方法臂偷偷追加模型更新。
10条target + 12条背景，背景每File/Database/Python各4条。所有政策用同一候选背景池和相同确定性DP，补齐目标经验不同长度造成的token残差，不用开发分数优化背景；背景内容因此可能不同。此试验识别整个token受限分配策略的效果，不能归因于纯目标条数的独立效应。
背景排除直接目标、普通median和File first-match近邻，防隐性target补课。目标候选按完整对话去重：LT历史11条实为1个独立内容；可以重复复习，但不称11种覆盖。
分散replay索引[0,2,5,7,9,12,14,16,19,21]；集中前段索引[0..9]。绝对插入槽仍87到159共10槽，每条after从既有真实microstep口径计算并在训练后核验，不把槽位等同optimizer step。

## 4. 开发/正式holdout独立冻结
- 新dev：4组×4题=16；新holdout：4组×12题=48。
- Database dev和holdout使用本轮新建、表名及行实体完全不同的独立sqlite fixture，查询结构一致、阈值难度近似；不得修改旧DB。File路径/关键词/内容独立，Python数值集合独立，题面模板dev/holdout分开。
- 这是已知四种操作在新题面/新实体上的共同预算泛化，不是新工具或新任务类别泛化。新DB schema实体迁移可能造成低分，这属于固定任务边界，不能看到分数后换容易测试。
- 原有monitor_v2虽独立于训练，但历史上已反复观测且缺list_tables，故不直接作为新的独立方法开发信号。旧P4/P5正式结果不作算法输入；旧考试最多作回顾指标。
- 第一阶段只校准dev+训练候选梯度，不生成holdout模型输出；holdout可在CPU生成并执行工具核对金标准，但不得用模型表现调设计。
- GPU校准输出每种子B_s、开发NLL、梯度norm/dotmatrix、计算成本；随后自动冻结9份计划和hash（plans_manifest.json），在所有正式评测之前。

## 5. 公平计算和阶段边界
GPU校准只forward/backward，创建0个optimizer、执行0次optimizer.step，不把开发题用作持续参数更新。每种子校准后校验LoRA参数hash不变；生产分支重新加载原step80优化器/RNG状态，校准不能改变训练起点。预计每种子16 dev+25去重候选=41个forward/backward，实际记录。
三臂共享同一次诊断，并在总成本表中向每个政策计入同等诊断成本（基线计算后忽略B），不能隐藏方法额外开销；另报告若基线无需诊断时的原始walltime。23是实际生产训练optimizer步数，诊断是0步且单列额外forward/backward FLOPs/时间。
当前先冻结并启动可执行的第一阶段“梯度校准→自动冻结计划”，GPU预计5–10分钟，绝不在此阶段自动启动9个训练分支。协调者检查实际分配及资源后续接正式队列；用户已授权，不再要求用户重复确认。
正式9训练+48新holdout/分支和必要保留指标预计约1.5–3小时；实际以首分支耗时更新，不能视为承诺。

## 6. 主指标和可证伪判据（正式队列冻结前不得更改）
主指标：新holdout四技能各12题的Joint，先逐技能均值再macro平均；每种子独立配对，全部Protocol-B1 greedy，tool/args/final分开报。
主要机制对比devgrad_uniform−balanced_uniform：三种子同正且均值>=0.05才支持本轮开发梯度分配有可用优势；否则如实为未达到标准，不能换用单技能最好分数。
FixedEarly强挑战：报告devgrad_uniform−balanced_early；只有同时不输该基线（三种子>=0、均值>=0），才能称优于这两种固定策略。若只胜均衡分散不胜early，只能支持分配机制相对于去信号消融，不能称总体最佳。
保留Calendar v3fix30题、phase2 File非目标22题（运行完整p2_file30后剥离目标8题）作为副作用；与均衡分散相比任一种子下降>0.10须报告代价。原有目标题不替换新holdout主指标。
如果B_s几乎相同、方法分配与均衡相同：报告算法未产生有效操纵，不自动凑新臂；若新schema全体低分，报告泛化失败/地板，不换旧卷抢正结果。不得用本轮holdout调权重、早插规则或阈值。

## 7. 操作边界与文献状态
只新增P6文件/目录，旧数据、冻结卷、环境和旧实验只读；单GPU；r5apex/其它GPU进程/功耗>=60W preflight，10秒watchdog，3次检查失败fail closed，STOP不自动删除或恢复。不得修改功耗上限，不发GPT。
本轮尝试用已加载的parallel-web-search做极简prior-art定位，但parallel-cli未安装（command not found），按技能要求停止该渠道，未绕用其它搜索。此不阻塞原型验证；DevGrad是工作名，不宣称梯度/干扰感知Replay首创或论文新颖性已成立。后续需要文献时应由用户环境完成/parallel-setup。
