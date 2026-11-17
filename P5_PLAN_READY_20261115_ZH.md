# P5 开跑前简要方案与CPU验收

2026-11-15 01:42，北京时间。GPU尚未启动，等待协调者审核具体9分支方案。

## 核实结果
- 已读取P4报告、交接、预注册、训练/评测实现及P1 B1逐题结果。
- P4报告中“同模式至少两条”超出可识别证据。本轮不承接成硬性普遍规则；P4两饱和模型也未获验证。
- file.search_last旧B1：stage02为0/0/0（各30题）；stage03为0/1/14；none为0/13/22。旧P1摘要stage03数字和原始joint不同，当前以逐题B1计数为准。能力缺口可作历史表述，不能说当前三个种子全不会；none不能冒充step80 prefix。
- 保留一个干净问题：相同四条File经验的时机跨工具验证。暂不做自动分类、不做覆盖因果消融、删掉随机基线。只有early、等距uniform、late，三种子共9分支。

## 冻结的实际配置
四条ID固定：file-train-e4_last_match-000、006、007、014。同一种子各臂相同经验集合/次序（target相对次序）与token，DB/Python target和File search_first绝对槽位也相同；其它背景相对次序固定但填补槽位改变。

|臂|四条target的slot/after|Σafter|
|---|---|---|
|early|87/13、87/12、95/11、95/11|47|
|uniform|87/13、111/9、135/5、159/1|28|
|late|151/2、159/1、159/1、159/1|5|

注意：分段为22条分到10槽，故同槽两条也可能跨optimizer边界，after不一定相同。以上已用旧真实训练log位置映射与CPU逐microstep模拟双重核对，不能手算成每槽固定after。

|种子|每臂实际replay input tokens|相对7494|
|---|---|---|
|20261108|7550|+56（+0.747%）|
|20261109|7483|−11（−0.147%）|
|20261110|7476|−18（−0.240%）|

训练总计23 optimizer steps，含共享前缀10步、后缀13步（102 microsteps）。主指标natv2_file 30题joint；副指标phase2 File30（其中last8/其它22）、nat Database30、nat Python30、Calendar v3fix30。每分支150题B1。不跑新T0/prefix、不跑全套基准。
主判据early相对uniform、late都三种子同正且均值各>=0.10；否则分情况解释，不自动加臂。不能据此证明早×广、真遗忘的跨工具泛化或自适应Agent。

## CPU检查与安全
- build首次发现旧token cache未覆盖全部手选File target；已改为用已有tokenizer在CPU计量缺项，未加载模型，无数据/环境修改。
- 01:40:15 CPU dry-run PASS：9计划、所有唯一训练条目token/loss masking、预算、同集合、固定其它target位置、23步与after、官方套件hash均通过。
- 01:41:01实机preflight PASS：game=false，enforced power cap=124.2W，无GPU计算进程；显存2003MiB、利用率4%（桌面占用不当训练进程）。01:35另一次cap为90W，未修改任何功耗设置。
- C盘剩余59,334,598,656 bytes（约55.3GiB）；本轮9个小QLoRA adapter，未复制旧模型/前缀大文件。
- 新监督器保留r5apex、进程、>=60W守卫；10秒watchdog、3次读失败fail closed；游戏出现写粘性STOP，只有用户允许再恢复。没有GPU任务被本轮启动。

## 时间与命令
历史P4 seed08 db4_early实际后缀训练45.194秒、单30题B1 Python134.1秒/DB132.7秒。按9分支×150题，加模型载入/系统波动，预计1.5–3小时；不是已完成时长。
WSL根目录：`/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent`。
启动：`bash scripts/launch_p5_20261115.sh`。
看进度：`runs_ext_p5_file_timing/logs/status.log`、`queue.log`、`runner.pid`、`gpu_child.pid`。
CPU收尾：`PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B scripts/finalize_p5_20261115.py`。

## 实现元数据备注
计划保留dose_db4来源部分名义分配字段（例如target_fraction、uniform_actual_input_tokens、quota_error_tokens_by_family），这些来源字段不用于P5实测或公平性结论。P5唯一权威预算字段为actual_input_tokens、actual_supervised_tokens、actual_tokens_by_family、target_actual_input_tokens及p5内budget_deviation，均已重新计算。运行器plan_override按这些逐条tokens校验。
