# P14 v2 / P15 本地工程冻结交接

2026-11-19 20:16（北京时间，Asia/Shanghai）。本阶段完成核实、实现、CPU验收与运行冻结；**未启动GPU/模型推理/正式训练，未创建START_APPROVED.json，未commit/push/发GPT。**

## 关键结论与改动范围

六项审查均核实，详见 `P14_V2_REVISION_20261119_ZH.md`：120/480/96不平衡属实；low/medium/high原来只是eligible；每split确实21模板；合成局限保留且未核实文献不引用背书；旧replay_train按family/旧eval单fixture确有工程冲突；48条月题辅助event_count及实体闭包有问题、gold无误。

新增data_ext_p14_eval_protocol_v2/，1392题任务/gold/messages/fixtures不变，只改group/清晰计数/实体闭包/资格元数据；gold_reconciliation.json逐题双hash一致。没有为了MIR出现工具退化或任何方法效果改题，也没有扩模板/现实数据塞满本轮。旧P14v1及598个受保护旧文件hash未变；e3_train.py、旧代码/旧runs/.venv/conda和_p11_fix_tmp均未修改。基础权重仅CPU流式hash固定身份，不实例化或推理。

## 实现与冻结路径

- `P14_V2_REVISION_20261119_ZH.md`：六项证据和v2变更。
- `P15_PREREG_20261119_ZH.md`：矩阵、预算、终止、统计、盲测与局限。
- `P15_ALGORITHM_SPEC_20261119_ZH.md`：两个核心模块、P11适配和消融。
- `P15_OPERATIONAL_AMEND_20261119_guard_identity_ZH.md`：真实进程身份守卫操作v2，**后续入口以该文件为准**。
- `p15_stageaware_20261119/core.py`：独立continual_group、真实assistant mask、候选/预算规则、分split fixture绑定、指标/配对条件。
- `p15_stageaware_20261119/optimization.py`：CPU测试与真实训练共用的更新引擎。
- `p15_stageaware_20261119/runner_v2.py`、`guards_v2.py`：可运行QLoRA三stage、统一延迟test、CPU默认拒绝、单GPU/STOP等守卫；不是只写计划。
- `p15_stageaware_20261119/{prepare,cpu_tests_v2,freeze_v2,analyze}.py`：版本/预算、验收、操作冻结、配对统计入口。
- `runs_ext_p15_stageaware_20261119/{cohort,optional_full_replay_cohort,new_streams,config,budget_ledger,diagnostic_budget_detail,diagnostic_subsets,operation_pair_conditions,operation_pair_CPU_schedules}.json`：完整计划/实际token和成本。
- 同目录`token_features.json.gz`、`tokenizer_identity.json`、`base_model_identity.json`：真实本地tokenizer/mask与CPU流式基础模型身份。
- 同目录`cpu_tests_v2.json`：最终验收含11个被测源码hash；`protected_before/after.json`：598个旧文件；`guard_read_only_v2_20261119.json`：只读真实启动前置状态。

### hash

- P14v1 manifest：`944b8e3d9b254e928559a55623aef3c41060234a8b04f010b9f1919f0f0b3881`（未变）。
- P14v2 manifest：`da99ed3b8a7fa74b1d9fdcb25a6245d6c086358caf341588baff00f5a6fd4bb8`。
- P15原科学运行冻结：`7fdcf44f6e80cc4150c7203765a7416ba37bbb447d2d813ac4b589e9fb27bb6e`（保留原样）。
- **应启动的操作v2 manifest**：`8627bee4336c47ecb95824dd78cebb66d8a39d452bc5c1fe31d700478471bc56`，文件`runs_ext_p15_stageaware_20261119/runtime_manifest_v2.json`。

## 具体待检验方法，不冒充已证创新

Layer Replay工作名，不是P11换名：模块A用首次学习结束的固定dev锚与当前T/A/gold-final损失分配old-skill概率（25%归一均匀混合）；模块B按调用风险vs答案风险选择完整call或final turn监督mask。无逐步全池MIR、无虚更新/梯度冲突或参数遗忘因果解释。两个消融分别移除优先分配/层mask；都保留同样诊断以计成本。P11原classify优先级函数不改、七skill恒等映射、p∝1+priority，明确是优先级适配而非旧十slot/插入时序逐位重现。

主组seqft、skill-uniform、p11_priority、layer_replay、no_priority、no_layer，每组6order×3seed=18轨迹，共108。Full Replay另18可选，默认禁止且不是性能上界。每stage128更新，384/轨迹，共41472更新；node00/01/02/03固定，不依效果延长/选checkpoint。

## 每stage真实新数据tokens（input / supervised），均128更新

|seed|counts|locations|fields|
|---|---:|---:|---:|
|17|1,007,211 / 52,505|990,969 / 85,084|998,208 / 92,160|
|29|1,006,590 / 52,534|995,087 / 85,408|998,208 / 92,160|
|43|1,002,688 / 52,313|993,793 / 85,249|998,208 / 92,160|

新流cap：每update8192 input/1024监督，每stage1,048,576/131,072；Replay在stage2/3每update4096/512，整轨迹上限1,048,576/131,072。完整episode，不语义截断或裁答案凑token。主矩阵新input323,674,632/监督24,824,628；五回放方法总Replay cap94,371,840/11,796,480。**cap不等于实际exact**：新数据同order×seed方法间逐ID/token/update对齐；跨组监督利用率仍39.9–70.3%，明显不等，SeqFT没有Replay所以更不等总监督。实际Replay token和利用率须GPU运行时记账，不能现在编造。

输入利用率约94.5–96.1%，不代表监督也匹配。counts约13.9遍、locations约2.5遍、fields12遍是预先固定token流的结果而非性能驱动追加epoch。输出mask减少计费监督token并不自动减少整段forward/backward算力；实际梯度权重随mask监督量变动是方法机制的一部分。

## 干扰假设、统计与计算边界

- 四个操作对（month-extract/date-extract/unique-retain/day-month）已给精确IDs、双cap、两方向和可执行CPU装配队列；**未运行实际GPU操作配对**，无纯干扰强度因果主张。粗stage六顺序不能消掉监督比例等混杂。
- 报T/A/E/真实F/gold-final/Core/严格Joint，七skill保持与获取、skill macro/group-stage macro/micro；失去数有at-risk分母，0分母=null。BWT/FWT有明确group和skill公式，node00和未学任务节点具备才报FWT。
- test必须108主轨迹全部完成后统一评全部阶段，如预先纳入Full则126条先完成，不在训练中看test调算法。
- 配对单位18个order×seed轨迹，不把题目当独立实验；固定6order共享3seed，保守seed块sign-flip仅8种符号，最小双侧p=.25，主3比较Holm、消融2比较Holm，不承诺显著。

### 大成本必须由父代理明确审阅

- Dev/test各150,336 episodes、各451,008生成请求。固定dev88题诊断额外至多12,672 episodes/38,016请求。主矩阵总生成请求上限**940,032**，输出token总cap200,540,160；真实执行prompt/实际输出尚未知。
- 额外固定train14条NLL探针共6048次forward、3,986,928 input token；额外诊断backward=0、optimizer=0。逐stage/顺序已在diagnostic_budget_detail.json。真实wall time在运行时记，GPU本轮未计时，不能编小时数或保证8GB吞吐。
- Full Replay可选18条额外旧input1,267,531,776/监督104,398,848，约160万旧样本forward/backward；另加18条新流、dev/test各75,168请求。因此默认不纳入，须明确allow_full_replay=true，不以论文完整性自动开这个资源大项。
- 结构估计LoRA5,046,272参数，GPU加载时校验实际数。主组adapter/optimizer payload约21.80GB，保守剩余运行阈值45.60GB，初测free57.39GB。保存每轨迹4adapter+3optimizer/RNG；不复制基础权重/每step模型/logits/重复prompt，不自动删旧runs。Full另约3.63GB payload。

## CPU验收与实际守卫修正

最终CPU PASS：1392执行/完整mask分区/实体闭包隔离，48月题闭包修正，12错误fixture路径/错行负例（含空日），9份seed×group流重现，108+18cohort，300回放双cap/拒dev候选，B1真值16项、逐skill/BWT/FWT/序列化/Holm，7安全规则及7真实进程身份案例；同一optimizer_update引擎CPU tiny随机模型的梯度、optimizer/RNG恢复后续步逐参数相等，CUDA未初始化、无预训练模型。

实际只读guard曾发现把Bash -lc命令含python当研究Python的误报；保留原科学冻结和旧代码，新增操作v2按/proc exe/argv[0]判断及验证真实batch父进程。无任何GPU启动，无科学参数/预算改动，不是Phase0-C。最终20:16（北京时间）只读guard safe=true、Apex=false、AC=true、GPU power limit90W、other_compute/project_python/STOP均空；未来启动必须重查。

CPU通过不等于实际4bit/CUDA AMP/显存/吞吐验收；GPU路径尚未跑。未实现任意半途GPU精确自动续跑，半程轨迹拒绝覆盖/自动重试，需单独审计恢复；只跳过同manifest完整COMPLETE轨迹。代码/数据有确定性重现，测量性CPU耗时/磁盘首测环境元数据不承诺换机bitwise相同。

## 父代理下一步：审阅后启动，不再问用户是否开始

用户t120u已授权后续完整实验。父代理内部确认具体方法/940k生成预算后，才可在本轮RUN新建以下批准文件（**本执行者没有创建**）：

```json
{
  "runtime_manifest_sha256": "8627bee4336c47ecb95824dd78cebb66d8a39d452bc5c1fe31d700478471bc56",
  "allowed_commands": [
    "train",
    "batch",
    "test"
  ],
  "allow_full_replay": false
}
```

文件名`START_APPROVED.json`。WSL根目录：

```bash
.venv/bin/python -B p15_stageaware_20261119/runner_v2.py guard
.venv/bin/python -B p15_stageaware_20261119/runner_v2.py batch --execute
# 全部主轨迹完成后：
.venv/bin/python -B p15_stageaware_20261119/runner_v2.py test --execute
.venv/bin/python -B p15_stageaware_20261119/analyze.py
```

若批准Full，batch/test均加--include-full；不可仅改其中一个。旧runner.py面对v2批准hash会拒绝启动，勿使用旧入口。Apex/低功耗(<60W)/其它GPU/研究Python/STOP阻断，2秒监测、逐micro和生成token停止，STOP粘性绝不自动解除。当前阶段到此停止，不GPU开跑，不改小样本科学淘汰策略。
