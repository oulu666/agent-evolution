# P15 审阅修订 v3（2026-11-19，北京时间）

本修订发生于任何 P15 GPU 训练之前；只新增 v3 文件，不改 P14 v1/v2、P15 旧冻结、原训练器或598个受保护文件。v1/v2 的科学定义保留，以下明确覆盖其中的工程/预算规定。不是 Phase0C，不按小样本成绩选择方法，不为正结果扩训。用户已授权实验，但当前正式矩阵仍由父代理在工程测量后作资源判断；本轮只执行单次有界工程验收。

## 1. 配对公平性与结论边界

六方法 SeqFT、Uniform、P11-priority适配、A+B layer_replay、去A no_priority、去B no_layer；六完整顺序×种子17/29/43，每方法18轨迹，共108轨迹。每阶段128更新，每轨迹384，合计41472逻辑更新。保持原冻结 new_streams，方法间同order/seed新数据输入、监督和更新完全相同。

回放存在时固定 `L=0.5 sum(new token losses)/N_new + 0.5 sum(replay token losses)/N_replay`，各分支按自身有效监督token独立归一。无旧数据阶段、SeqFT只用新损失权重1。layer mask 不再通过改变总监督分母间接改变新任务梯度权重；mask实际监督量的差异仍存在，必须报告，绝不称等监督或等算力。全序列保留，不截答案凑tokens。Replay输入4096/监督512均为上限，装箱利用率和实际监督量逐更新记录。

跨阶段长度和训练遍数不一致：counts/locations/fields规模120/480/96；同128更新下约13.9/2.5/12遍，输出长度明显不同。固定暴露控制≠跨阶段强度完全受控。主结论限同order-seed方法间配对比较；三粗stage六顺序不单独识别纯干扰因果。操作配对矩阵仍是待验证假设，本轮不新增GPU操作配对实验，也不声称已测干扰强度。

## 2. 诊断/评测去冗余和精确缓存

主节点00/01/02/03只生成固定dev88，而非dev348。dev88分组counts20/locations20/fields48（技能count_date8、month12、locations20、四fields各12）。自适应四方法仍在阶段2/3更新0/64诊断旧技能。初始及各阶段固定train14 loss探针保留，无诊断反向传播/虚更新。

逻辑生成请求上限：dev主节点114048 + dev刷新38016 + test451008 = **603072**，由旧940032降低。每题工具128、真实结果final256、gold-observation final256均为输出上限，不假定实际输出等长。update0与上一主节点同模型时，可在绑定完全一致的条件下复用19008请求，上限降至584064；该条件须由缓存键实际命中证实，不提前伪造物理节省。真实final与gold final仅在完整渲染prompt UTF-8字节SHA与长度、生成配置、模型与数据绑定全部相同才共用；解析后工具/参数正确不构成复用证据。

缓存绑定：轨迹id与seed、完整generation-model semantic hash（训练参数+冻结参数/quant/buffers+runtime attrs）、v3 manifest、P14v2 manifest、对应split fixture hash、tokenizer identity、完整prompt字节、max_new/EOS/pad/use_cache等。模式名不进键，因此相同prompt的两final可以精确复用；不同模型/seed/数据/空格/生成设置必不复用。记录逻辑请求和实际inference_calls、输入/输出tokens、hit、来源模式与prompt hash，缓存payload另验SHA。CPU使用伪生成器验证缓存机制，不能把CPU缓存测试说成模型生成等价性验证。

不实现跨方法stage1共享；逻辑与物理训练均108轨迹，不以浮点近似相同充当精确共享。Full Replay逐更新全旧池方案延期，不作为第七组，也不称真性能上界。

test仍是348×4节点×108=150336题（451008最大逻辑生成请求），**全部108轨迹训练完成、方法与预算冻结后才统一评估**；不读test生成结果改题/选方法/扩训。T/A/E/F、Core与严格Joint不变，真实执行final与gold-observation final分别报告。保留逐技能获取/保持、skill macro、stage macro、micro；at-risk分母、BWT/FWT与配对18轨迹/三seed统计边界沿用原预注册。dev88统计只代表固定诊断集，不冒充dev348。

## 3. 持久化、安全与磁盘

每个成功optimizer update后、响应下一次STOP前提交完整状态；micro中断退回最近已提交update边界，不承诺任意micro继续。两滚动slot先原子写+fsync，再原子CURRENT+目录fsync作为提交点，旧CURRENT所在另一slot在提交前保持完整。完整base/quant/buffers按内容哈希去重，不能假定4bit内部状态天然不变；状态含训练参数、optimizer、scaler、Python/NumPy/CPU/CUDA RNG、module modes、runtime attrs、stream位置、诊断锚、决策、Replay队列/选择RNG及manifest。物理optimizer intent账本在回滚状态外，不隐瞒重算；正式恢复只手动 `--resume`，若出现未提交optimizer intent则拒绝继续，先明确恢复计算预算，不自动重开。

节点保存仅供生成的训练参数+attrs+base引用，不重复保存adapter包及optimizer。保留四节点，滚动两份完整训练状态。运行目录硬上限32GiB、C盘至少保留8GiB；每次写大状态前检查，绝不自动删除旧科学文件。按5,046,272个FP32 LoRA参数估算：四节点约8.72GB、两滚动optimizer状态约13.08GB（108轨迹），再加共享base、缓存/输出/日志；32GiB是强停上限而非无限保证。完整base每更新capture/hash、checkpoint I/O成本必须实测纳入，不只报GPU kernel时间。

守卫：Apex/r5apex、AC非放电、功率限制≥60W、全部现有STOP、其它GPU计算/项目Python、排他锁与磁盘。STOP粘性，绝不清理，guard异常也安全停。固定deterministic algorithms、cuDNN deterministic、关闭benchmark、CUBLAS_WORKSPACE_CONFIG=:4096:8，所有方法一致；若后端不支持或数值失败，保留证据停止，不自动改精度/增加attempt。

## 4. 本轮唯一GPU工程验收，不是科学筛选

独立 engineering_attempt01，仅train/dev，固定两个逻辑更新；update1持久化→update2 A→重建模型/optimizer/scaler对象→从磁盘update1恢复→重复update2 B。最多3个物理optimizer.step，比较完整状态semantic SHA和逐micro loss严格相等。该测试验证同进程新对象恢复，不直接宣称全新OS进程、任意硬件/驱动或任意micro位点完全等价。

生成只固定2题（train月计数、dev ID字段），每题tool/real-final/gold-final，逻辑≤6条、每模式≤2，绝不test。记录4bit/AMP、有限梯度、input/supervised tokens、forward/backward、optimizer物理更新、VRAM、加载/持久化/恢复和生成耗时。失败/环境阻塞只留一次证据，不自动重试，不用表现判断方法价值。未测量前不写GPU小时；完成后依据此次有限长度测量给范围，明确长尾/上下文/完整回放批量外推不确定性。

入口：`p15_review_v3_20261119/engineering.py --execute`；CPU `prepare_v3.py`、`cpu_tests_v3.py`、`freeze_v3.py`。正式 `runner_v3.py batch --execute` 还要求父代理创建绑定v3 hash的 START_APPROVED_V3.json，且工程PASS；本阶段不创建此许可。正式可用 `train --id ID --resume --execute` 手动恢复，所有STOP仍生效；不自动启动完整矩阵、不提交、不push、不发GPT。
