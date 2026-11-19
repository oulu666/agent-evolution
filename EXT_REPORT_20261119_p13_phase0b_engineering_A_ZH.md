# P13 Phase0-B 工程修复诊断结果（阶段A，不是科学终点验收）

北京时间：A于2026-11-19 01:25:51通过；同轮阶段B随后进入。旧attempt01/02、STOP归档、CPU_DIAGNOSIS及原科学协议均保留，不改门槛、不push、不发GPT。

## 客观结论
**从磁盘持久化的theta_v恢复可精确重建；重新跑同一浮点更新仍不能精确重建。** 这两件事必须分开，不能放宽epsilon掩盖后者。工程门通过仅允许本次已授权的单次测评机会，不证明MIR能预测遗忘，也不授权正式pilot。

- 保存/恢复包含LoRA、PagedAdamW8bit、scaler、Python/NumPy/CPU/CUDA RNG、module modes，以及冻结基座全部参数/buffers、QuantState/嵌套量化状态/offset/codebook、相关dtype/dropout/config和可记录backend指纹。
- 保存theta_v的文件hash、扩展语义hash均核验。origin完整恢复exact=true；其原训练态hash仍为f7fbb2e0040cc4b02bb3d5a5fb061686ef532aa310db574f5051424fd0eebc08。
- 保存theta_v恢复后固定8条×6段NLL共48值全部逐值精确相同，max/mean差均0，完整row payload相等；无epsilon。
- 重跑对照8个训练loss标量全部与主更新逐位相同，但**优化器step之前的梯度hash已不同**，随后LoRA/optimizer hash也不同。这排除了“仅optimizer.step不同”作为充分解释；不能仅凭这些标量判定全部forward中间量相同，也不能定位某个CUDA/bitsandbytes算子或认定功耗为根因。
- 重跑对照的post-update NLL最大差：call 0.0011615651，args 0.0020043813，final 0.0132773966；均8/8行有变化。call原始delta严格两两逆序6对，clipped MIR风险Top4重合3/4。注意原rerun_control_comparison.json的Top4是**更新后绝对NLL**排序(4/4)，不是MIR delta排序；另附engineering_A_delta_rank_CPU_audit.json明确区分，不覆盖原证据。
- 主预测只使用首次保存theta_v，绝不以重跑对照替代。隐藏CUDA/cuBLAS/bitsandbytes实现缓存未声称完全序列化；工程证据是保存态恢复的精确hash与NLL，而非宣称训练算子已变成确定性。

## 实际成本（A单列）
2个临时物理更新，16 backward样本，32 NLL forward样本，0 generate；NLL输入15204 token，训练两次各3947 token。allocated峰值2,585,268,224 bytes，reserved峰值5,282,725,888 bytes。elapsed 284.904秒（包含加载/持久化/恢复等，非纯GPU计算时间）。snapshot capture总40.677秒、save总56.332秒、restore总142.912秒是相互嵌套计时，不能相加当独立walltime；首次及对照训练段分别7.647/8.642秒。

## 同轮阶段B执行边界
seed08为明确授权attempt03；其余两种子使用原库存额度。复用已完整的三种子校准与formal_freeze；不复用旧25条部分node00。seed08直接恢复A保存theta_v，不重演旧失败浮点更新；它贡献逻辑自然后缀step1，随后才执行step2…10。其他种子一次保存的虚拟预览同样作为逻辑step1；所有节点持久化，禁止重新浮点重建或自动重试。

B最多29个新增物理更新（9+10+10）、232 backward、576 NLL样本、432两回合episodes/864 generate。A另计2更新，其中一个被采用、一个对照丢弃；本次合计31物理更新，逻辑自然后缀仍3×10步，不双计step1。历史失败两步、完整校准与旧部分生成的成本另表保留。没有正式新训练模型发布。

主gate仍为原冻结的≥2种子各≥5 core退化/≥5非退化、AUROC≥0.65并优于NLL/TokenCost及原聚类bootstrap差值门槛；不足UNIDENTIFIABLE，不扩规模。候选/探针分开，主自身探针预测不是replay泛化效果。

## 产物和监护
- 修订：P13_PHASE0B_OPERATIONAL_REPAIR_20261119_ZH.md。
- 新增实现：fac_tinyagent/p13_phase0b_persist_20261119.py；p13_phase0b_persist_state_20261119.py。
- 根目录：runs_ext_p13_phase0b_persist_20261119；operational_freeze.json绑定旧协议/校准/新代码。
- A_PASS.json、engineering_A/{saved_state_comparison,rerun_control_comparison,extended_restoration,restoration,cost}.json及engineering_A_delta_rank_CPU_audit.json。
- 监督器WSL PID365，worker PID470，active.json、progress.jsonl、logs/worker_20261119_012018.log、logs/guard.jsonl；Windows启动终端PID68528。
- 3秒持续守卫：无Apex、功耗≥60W、无竞争项目/GPU、无STOP。新STOP永不自动解除，不杀游戏。WSL PID [Not Found]不是停止条件。
- 此阶段报告**不是final acceptance**；仅当全部进程退出、supervisor_end.json rc0、GPU_COMPLETE.json存在，才运行独立CPU final。父routine目前暂停，需父助手接管只读进度监测，不能在GPU运行中并行项目Python验收。

首次CPU测试仅原生QuantState CPU往返，断言“导入native库不初始化CUDA”失败，未加载模型、无forward/backward、未进入A；失败文件保留。随后修正测试描述，记录native库导入会初始化context，精确状态/NLL门槛未变。首次nohup启动未留下进程/日志/attempt；核实后使用现有托管Shell后台承载监督器，未额外消费工程attempt。

### B启动验证补记
北京时间01:29:03，seed08 attempt03前缀与保存theta_v的96行评分已完成并锁定prediction.json；从新加载Engine恢复A theta_v后的8条参考NLL再次精确相等（代码断言通过）。01:29:34 node00生成8/48，01:29:53安全守卫90W、无Apex/竞争进程/STOP。B尚未完成，不能报告MIR科学通过或失败。
