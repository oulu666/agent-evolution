# P15 v3 工程验收报告（2026-11-19，北京时间）

## 结论先行

**本阶段已停止，不能启动正式矩阵。** v3 新增代码/预算/CPU验收已冻结；唯一GPU工程尝试确实完成3个物理更新（2个逻辑更新，其中第2个重复一次作恢复对比）及6个train/dev生成，完整持久化恢复后的下一步与不中断路径**逐位相等**。但是结束时报告中的 `torch.dtype` 未经JSON转换，最终 `RESULT.json` 写出失败，进程非零退出。未自动重试、未追加GPU更新、未清任何STOP、未开始108轨迹、未生成test结果，也未commit/push/发GPT。

**不能将整个工程验收写成PASS。** GPU退出后仅用CPU核对既有两个完整状态与日志，形成 `engineering_attempt01/FORENSIC_RESULT.json`。它证明下面明确列出的事实，但不伪造丢失的最终报告；生成后最终隔离恢复断言没有独立持久化见证，而且finally序列化错误可能掩盖此前被捕获的错误，故这一步不宣称已通过。核心next-update恢复对比则有两个完整磁盘状态与四次提交日志直接作证。

## 已完成与冻结

- 新代码目录 `p15_review_v3_20261119/`：11个模块，含可运行训练/手动update边界恢复/延迟盲测入口、固定分支损失、精确缓存、原子状态、守卫、单次有界验收、CPU tests与冻结器。
- 跑行目录 `runs_ext_p15_review_v3_20261119/`；中文修订 `P15_REVIEW_REVISION_V3_20261119_ZH.md`。
- v3 runtime manifest SHA256：`386a5cf24a24957b99553120e3dd599b68ef09bbb0ae7ac32e97b049c645155f`。
- 11项CPU测试通过：分支梯度权重不受mask监督量改变、new-only权重1、CPU完整磁盘恢复下一步相同、部分临时文件不成为CURRENT、第四物理step拒绝、模型/seed/fixture/prompt/生成配置缓存隔离、real/gold严格同prompt复用、错误fixture拒绝、108矩阵/生成数、正式启动门控、CPU不初始化CUDA。
- 冻结链与598个旧保护文件在GPU后CPU取证重新核对不变；不改P14 v1/v2、旧P15冻结、e3_train.py或.venv。初次CPU玩具夹具缺PEFT接口的问题只在v3冻结前修正，失败日志保留；最终绑定的CPU验收通过。

## 公平性、矩阵与生成预算

Replay时 `0.5 L_new + 0.5 L_replay`，两分支各按自身有效监督tokens归一；SeqFT和无旧数据stage为new-only权重1。whole episodes不裁语义/答案，Replay4096输入/512监督是cap，不是精确相同监督/算力。v3实际engine与review_budget_v3是有效损失规范；继承旧CONFIG中的旧gradient_normalization说明字符串不是执行路径。

六方法×六order×三seed=108完整轨迹、41472逻辑更新。新流323674632输入、24824628监督tokens精确方法内配对；Replay输入上限94371840、监督上限11796480，真实mask/装箱利用率运行时分别记录。跨stage输出长度、遍数仍混杂，仅作暴露控制，不主张纯干扰因果识别。Full Replay延期，不是第七组；不共享stage1状态。

新流每stage128更新，真实输入/监督tokens：

|seed|counts|locations|fields|
|---|---:|---:|---:|
|17|1007211 / 52505|990969 / 85084|998208 / 92160|
|29|1006590 / 52534|995087 / 85408|998208 / 92160|
|43|1002688 / 52313|993793 / 85249|998208 / 92160|

Dev主节点改为固定88题：主节点114048请求+刷新38016=152064；test仍348×4×108×3=451008。总逻辑上限**603072**，不是940032。若同checkpoint的update0缓存实际逐键匹配，可再复用19008，成为584064；real/gold再复用必须完整prompt字节/模型/数据/生成配置相同，不预设命中率。缓存绑定轨迹seed、完整generation-model hash、数据/fixture/tokenizer/manifest及prompt字节SHA/长度、解码参数，payload另验SHA。工程6次生成均为物理请求，无cache命中；CPU已验证命中/失效规则，未将假生成器结果当作模型性能。

## GPU实测（仅工程，不解释方法效果）

机器 RTX4060 Laptop，8188MiB；启动前AC、电源限制90W、无Apex/STOP/其他计算或项目Python、磁盘守卫通过。196个4bit量化参数状态、fp16 AMP、GradScaler最终scale65536/growth_tracker2，9次forward+9次backward，共6660输入tokens。

|物理更新|输入tokens|监督new/replay|耗时秒（不含checkpoint）|峰值allocated / reserved MiB|
|---|---:|---:|---:|---:|
|1|2488|176 / 53|3.8197|2766.16 / 4666|
|2A|2086|144 / 22|1.3961|2785.41 / 4666|
|2B恢复重算|2086|144 / 22|1.5072|2785.41 / 3410|

第二步输入吞吐约1494和1384 token/s；首次含冷启动效应约651 token/s。梯度范数有限，两条第二步loss序列完全相同。完整状态SHA（包含base/quant/buffers/attrs、模型训练参数、optimizer/scaler、RNG、modes和队列/位置）两份均为：

`dd45746708d9d75b9204892f6412983d05925f725f6acce257bc809fda2db940`

这是同进程内重建model/optimizer/scaler对象后从磁盘恢复，不扩称新OS进程/任意硬件/micro中间点等价。

生成每种模式2条，无test、无输出cap命中：

|模式|两条秒数|两条输出tokens|峰值allocated / reserved MiB|
|---|---:|---:|---:|
|tool|0.7936、0.9771|7、10|991.47 / 3410|
|real final|0.6087、1.6461|7、10|1002.08 / 3410|
|gold observation final|0.6903、6.6759|6、60|1116.29 / 3410|

首次启动+初始提交合计约93.6秒，不能拆成精确模型加载耗时。由提交时间差减训练耗时估计两次持久化边界开销约15.18、11.60秒（各±2秒，含少量边界尾项），不是丢失报告中原本精确timer的替代。每更新capture/hash完整base及磁盘读写明显慢于本次小batch训练，正式预算不能忽略。

## 资源外推：不能直接放行大batch

CPU取证脚本给透明情景，而非置信区间/保证上限：

- 训练活跃计算约55–267小时（按实测seconds/input token、75–100%Replay输入cap及0.75–1.5倍率）。
- 逐update完整持久化占卡等待约111–198小时。
- 类似本次短输出情景的生成约85–779小时。
- 合计约**251–1244占卡小时**（约10–52天连续占用），还未完整覆盖所有隔离快照、固定train14 probes、模型重载及cache fsync/热降频等成本。
- 接近输出长度cap的极保守情景可能约7677小时；这是将本次很短输出的慢wall/token外推到128/256上限并放大1.5的资源压力情景，不是预测、置信上界或承诺，prefill摊销和输出长度会使外推很粗糙。

因此应先由父代理审阅工程优化和可接受占卡预算，不因任何模型成绩缩矩阵/扩训。完整矩阵108轨迹未改变。

## 安全、磁盘与真实阻塞

双slot原子CURRENT、完整状态、独立物理intent账本与micro事件；STOP中断时保存最近成功update边界，不承诺任意micro恢复。正式恢复仅显式 `--resume`，遇未提交optimizer intent拒绝自动继续。两slot与四节点只保必要状态，base按内容去重；硬上限32GiB、C盘保留8GiB。写入采用启动清点+逐文件增量计账，避免每个cache写入全目录递归。

本轮新增目录约0.98GB（主要是独立量化base和两个61MB状态）；Windows C盘在GPU结束时约55.32GB空闲（WSL statvfs口径56.32GB），均高于8GiB。模型权重/optimizer/base blobs仍留本地，不准备作为轻量Git证据；未删除任何文件。

阻塞：`terminal_failure.txt`第31行起，最终JSON包含torch.dtype。源已冻结，不原地改、不自动重跑。后续应新增操作修订：递归JSON-safe转换dtype/device/Path/NumPy标量，并在每项验收完成时先提交可序列化小见证，避免finally覆盖主要错误；补CPU回归。还需明确本次生成后恢复断言的持久化见证不足。不要把该工程阻塞当成新方法失败或科学淘汰。

正式命令（当前不执行且门控拒绝）：`.venv/bin/python -B p15_review_v3_20261119/runner_v3.py batch --execute`；父代理需先处理上述阻塞和资源判断，另建绑定新操作冻结hash的启动许可，不能仅补一个PASS字符串。当前无 `START_APPROVED_V3.json`、无正式轨迹、无test评估。
