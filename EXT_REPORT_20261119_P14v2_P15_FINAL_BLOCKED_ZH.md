# P14v2 / P15 最终独立报告：BLOCKED工程交付

日期：2026-11-19，北京时间。结论：**NOT_FULLY_ACCEPTED/BLOCKED；方法有效性无正负结论。** 正式矩阵不启动，不追加GPU attempt，不创建START，不手填PASS。GitHub交付记录本次已完成的数据/协议/工程与阻塞，不代表算法实验成功。

## 完成与未完成

### P14v2：完成CPU修订与冻结

保留P14v1不变，v2共1392题：train696/dev348/test348；29结构分层单元，七技能。三个group训练规模counts120/locations480/fields96，实际每split21模板。受控合成数据主张不扩成真实外部有效性。

修复month辅助元数据为target_date_event_count/month_total_event_count，补48条month任务的邻日实体闭包；1392条prompt/gold/工具/参数/答案不变，夹具字节不变，逐题reconciliation已发布。独立continual_group区别counts/locations/fields，工具注册仍calendar，逐split绑定fixture。操作矩阵low/medium/high仍待验证假设，日/月路由另列，不把六粗stage顺序当纯干扰因果实验。

v2 manifest SHA256：`da99ed3b8a7fa74b1d9fdcb25a6245d6c086358caf341588baff00f5a6fd4bb8`。全部三split数据和合法fixture保留发布，包括带gold的私有研究盲测数据；未读取任何test生成结果调题。

### P15初稿/v3：实现与CPU冻结完成，科学实验未开始

SeqFT、Uniform、P11-priority七技能适配、最小A+B layer_replay及去A/去B两个消融；每方法6order×seeds17/29/43=18轨迹，总108。128更新/stage，共41472逻辑更新。A以tool/args/gold-final诊断缺口决定技能Replay优先级；B选择call/final/both监督层。它是待检验机制，不宣称参数遗忘因果或已证实创新。

v3固定Replay的new/replay损失0.5/0.5，分支各自监督token归一，SeqFT/no-old用new-only权重1。方法内同order-seed共用新流与更新，跨stage监督长度/遍数不等；上限相同不等于等监督/算力。Full Replay延期，不是第七组；stage1未物理共享。

Dev固定88题，603072最大逻辑生成请求（152064dev+451008test）；若update0逐键缓存匹配，可少19008。test348×4节点×108在全部训练完成且冻结后统一评估；实际尚未执行。真实工具执行final与gold-observation final独立；B1 T/A/E/F/严格Joint、Core、逐技能获取/保持与macro/micro、at-risk/BWT/FWT和配对统计边界不变。没有正式科学轨迹，没有可报告的新旧技能效果、BWT/FWT或方法比较成绩。

v3 runtime SHA256：`386a5cf24a24957b99553120e3dd599b68ef09bbb0ae7ac32e97b049c645155f`。v3的11项CPU检查通过；598个旧保护文件与原冻结不变。

### 有界GPU工程尝试：有实质成功，但整体未验收

2026-11-19 20:39:51–20:43:12（北京时间），RTX4060 Laptop 8188MiB，真实4bit/fp16 AMP。仅3物理/2逻辑更新（重复第二步一次），9forward/9backward、6660输入tokens、6次train/dev生成，无test。梯度有限。重建model/optimizer/scaler对象后从磁盘恢复下一步，两个完整状态与loss逐位相等：

`dd45746708d9d75b9204892f6412983d05925f725f6acce257bc809fda2db940`

该证明范围为同进程重建对象，不扩成任意OS进程/硬件/micro中途等价。训练耗时3.8197/1.3961/1.5072秒，峰值2785MiB allocated、4666MiB reserved。六次生成中tool每题0.794/0.977秒，real-final0.609/1.646秒，gold-final0.690/6.676秒；无长度cap命中。

最后因torch.dtype不能JSON序列化而非零退出，**原RESULT.json不存在**。GPU退出后CPU取证核实了上述磁盘证据，但生成后最后隔离恢复断言没有独立落盘见证，finally错误也可能遮蔽此前被捕获错误，因此不宣称整体GPU验收通过。原冻结、失败日志和本地二进制证据均保留，没有第二次GPU尝试。GPU已释放。

### 本次CPU收尾：报告缺陷已给出修复，不补齐GPU见证

新 `p15_cpu_closeout_20261119/json_safe.py` 递归准确转换dtype/device/path等，未知对象和大tensor payload fail-closed。新增11项CPU序列化回归PASS，包括旧真实指纹结构的CPU mock；不加载模型、不初始化CUDA。FINAL_BLOCKED_STATUS仍为BLOCKED；不新建旧RESULT/START，不将CPU mock算GPU测量。token缓存重建check通过，250448字节及原hash一致，旧文件未重写。

## 成本账本复核：不是可靠工期

短输出情景251–1244占卡小时的分解：训练活跃计算约55–267小时；持久化占卡等待约111–198小时；生成约85–779小时。其来源仅2个独立小训练更新与2道生成题，不能用作可靠交付工期或置信区间。

- 新输入323674632精确tokens，Replay输入上限94371840。训练情景 `(new + 0.75..1×replay_cap) × 实测min..max秒/input_token ×0.75..1.5 /3600`。
- 提交日志的相邻时间差减对应训练耗时得到持久化约15.18、11.60秒，各约±2秒，含少量边界尾项，不是原本丢失的精确timer。外推 `41472×(min−2 .. max+2)/3600`。
- 各生成模式194688（条件缓存命中）至201024（无该节省）请求，乘该模式实测min..max秒/请求、0.75..1.5倍率。原6请求均物理生成，没有实际cache hit；下界的19008节省只是假设全矩阵缓存键一致时的条件情景。
- 接近128/256输出cap的极保守压力情景约7677小时，来自本次慢wall/output-token×cap×1.5；prefill摊销和长度变化会使它非常粗糙，不是保证上限。隔离快照、6048次train探针forward、cache fsync、重载、热/OS中断等尚未充分计入。

### 高持久化成本：哪些证实，哪些未证实

代码与四提交记录证实：不是每步重写857797695字节的冻结量化基座。`state_v3.Store.commit` 仅在内容hash blob不存在时写base；本次四次GPU提交引用同一个base blob。每次仍完整capture/复制base到CPU，多次递归深度hash（base、完整state、generation-model），并重新流式读取/sha256该857MB blob；滚动小状态每份约61244021字节（初始无optimizer状态较小）。这些重复全基座处理确实存在，不能只报1.4秒训练而忽略约12–15秒边界。

路径位于 `/mnt/c/...`，确实跨WSL/Windows挂载边界；**没有**做原生Linux盘/仅CPU hash/仅I/O的对照profile，所以不能定量归因给DrvFS、称其为跨物理磁盘、或断言某一项占全部成本。此轮无长benchmark。

### 下一版优化建议（未实现、未计时，不改本轮冻结）

1. 只持久化可变LoRA/optimizer/scaler/RNG/流/锚/队列及必要可变buffer/quant属性，共享冻结base身份，避免每update全权重hash。须证明冻结存储和量化内部状态确实不可变、重建后下一步等价；不能仅假设requires_grad=False足够。
2. 稀疏固定checkpoint+安全终止边界保存，可减少I/O，但会改变最大丢失工作/重算物理预算、STOP尾延迟和恢复承诺；须预注册间隔、记录partial backward/step intent、重新验证原子恢复，不能静默改。
3. 相同seed/order的stage1跨六方法共享一个真实执行状态及评测，只有在任务/损失/optimizer/RNG/诊断状态完全相同并有严格谱系证明时允许；逻辑仍108轨迹/配对统计，物理账本另报，不能把重复浮点近似当相同。跨order同首group共享也须单独证明。
4. 保留真正定义所需的请求，优先严格同checkpoint/prompt cache、合理批量解码和I/O优化；批量化可能改变浮点/解码，需要验证。若删test节点、gold-conditioned final或baseline，会影响T/A/E/F、忘却/BWT/FWT定义，必须正式修订而不能暗删。不得因本次工程小样本成绩缩6order×3seed、改题或扩训。

## 发布与复现边界

只发布P14v2完整轻量数据/fixture、P15各版本代码/预注册/预算/轻量CPU/GPU日志/forensic/本最终报告交接。旧失败草稿与_p11_fix_tmp不纳入不清理；本地base/optimizer/scaler/RNG大二进制、cache/token派生gzip、tokenizer重复、传输zip、CPU临时夹具、锁PID不上传。manifest原始引用/hash不修改，缺少的缓存依赖与本地证据在交付清单说明；二进制恢复对比仅能在保留本地payload处重核。

token特征可用 `rebuild_token_features_cpu.py --write` 从身份匹配的本地tokenizer重建；默认check不写已通过。新增根.gitattributes只对本轮路径禁行尾转换，暂存blob逐文件SHA与原字节对账。所有旧科学冻结不变。上传目标既有私有研究仓库 https://github.com/oulu666/agent-evolution 的main，正常add/commit/push；完整commit SHA和三方远程核验在最终回执报告，不为写入自己的SHA修改历史。

最终状态不因上传改变：**BLOCKED工程交付，方法无正负结论；下一步需要资源方案和操作恢复见证修订，不开始下一轮。**
