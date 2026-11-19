# P13 Phase0-B 最终独立报告：主假设不可识别，确有最终答案层退化

北京时间：GPU 2026-11-19 02:17:37完成；监督器02:17:41 rc0；独立CPU final 02:52:10通过；原始输出独立重评分02:53:19通过。不是新的GPU attempt。

## 1. 正式结论
**UNIDENTIFIABLE_no_expansion；不晋级正式MIR/DG-MIR，不自动增加种子/窗口。**

主检验是前缀一步虚拟ΔNLL_call提前预测同一独立开发探针在自然suffix第10步的工具+参数(core)正确→错误。3种子原先正确43、43、42题，共128个at-risk终点记录，**core退化0**，因此无法检验预测能力。不能写成AUROC低于0.65、MIR无效或完全没有遗忘。

本轮确有**10次严格Joint正确→错误**：种子08/09/10分别4/4/2；同时2次错误→正确，总Joint从87/144降到79/144。工具、参数和执行状态未变，这些严格Joint退化均落在最终答案层；是预注册次要结果，不能替代主目标，更不能用事后改目标挽救晋级。

## 2. 逐种子、逐技能：必须看配对而非只看净分
|种子|技能|core 0/5/10（每24）|Joint 0/5/10（每24）|Joint正确→错误|错误→正确|
|---|---|---|---|---:|---:|
|20261108|cal.count_date|21/21/21|20/20/20|0|0|
|20261108|cal.list_locations|22/22/22|10/9/6|4|0|
|20261109|cal.count_date|21/21/21|21/20/20|1|0|
|20261109|cal.list_locations|22/22/22|8/6/6|3|1|
|20261110|cal.count_date|21/21/21|21/20/20|1|0|
|20261110|cal.list_locations|21/21/21|7/7/7|1|1|

所有种子日期/地点工具选择在0/5/10均24/24；参数及执行正确数即上表core（因为工具全对），三个节点相同。原先16条参数错误是能力缺口，不计遗忘。seed10地点Joint总分7→7仍包含1条失去、1条获得，不应说逐题完全不变。

## 3. 冻结主指标、baseline和置信区间
|种子|core at-risk|core退化|MIR-call AUROC|初始NLL-call AUROC|TokenCost AUROC|
|---|---:|---:|---|---|---|
|20261108|43|0|undefined|undefined|undefined|
|20261109|43|0|undefined|undefined|undefined|
|20261110|42|0|undefined|undefined|undefined|

主AUPRC、Top-quartile recall、候选结构配对映射AUROC亦均undefined。两向seed×probe聚类bootstrap请求1000次，主分析有效次数0；MIR−初始NLL、MIR−TokenCost的95%区间及MIR AUROC区间均undefined，不填0、0.5或零宽区间。

冻结gate：
- 工程和状态恢复：通过。
- 至少2种子各≥5 core退化且≥5未退化：不满足（实际各0退化）。
- AUROC≥0.65且优于初始NLL/TokenCost、bootstrap差值95%下界>0且有效≥800：不可检验；机器字段为false表示未通过，并非统计证伪。

主分析每个seed×probe只出现一次；中点仅次要，不把重复节点当独立样本。候选48条与探针48条预冻结一一结构映射，映射分析单列；自身探针ΔNLL预测不等于候选选择泛化，更不等于replay有效。

## 4. 次要预测结果：有局部迹象，但不能改主gate
|种子|基线Joint正确|Joint退化|ΔNLL_final预测final错误 AUROC/AUPRC|ΔNLL_all预测Joint错误 AUROC/AUPRC|
|---|---:|---:|---|---|
|08|30|4|0.9712 / 0.8042|0.9519 / 0.7333|
|09|29|4|1.0000 / 1.0000|0.9900 / 0.9500|
|10|28|2|0.5962 / 0.2857|0.5577 / 0.2024|

这些是原方案已有的不同分段/结局的次要检验，不把Δfinal或Δall冒充主Δcall。前两种子排序较好，第三种子弱且仅2个事件；未凭这些次要数值新增baseline/CI搜索或改判。不能宣称已证明优于NLL/成本、稳定跨种子、或值得训练正式MIR。小样本与只有3个种子簇均限制外推。

## 5. 工程、时序和恢复独立验收
- 阶段A 2临时更新/16 backward/32 NLL/0 generate；保存theta_v恢复后的8×6段NLL精确相同，重新加载模型仍相同。重跑同批loss标量相同但梯度hash已不同，不能靠浮点重演恢复；对照未覆盖主预测。未放宽epsilon、未认定功耗根因。
- 使用LoRA/PagedAdamW8bit/scaler/全部RNG/modes及冻结量化基座、buffers、QuantState/嵌套状态、可记录backend指纹的持久化；独立CPU核验54个检查点receipt、1个去重base blob。全部扩展恢复exact、旧prefix hash未改。
- 逻辑自然suffix仍每种子10步；已保存的一步虚拟状态直接采用为逻辑step1，不重新浮点重演。seed08新增明确授权attempt03，其余种子各attempt01；旧01/02不删除，不当新独立实验，不新增机会。
- 432条原始tool_call_raw/answer_raw逐题用冻结原评分函数代码重新解析，并在原Calendar fixture执行，tool/args/observation/execution/final/Joint全部与保存结果一致；1728组分段(initial, delta, risk)精确重算一致；原主metric table与两组bootstrap独立重算一致。无新NLL forward/生成/训练。

## 6. 成本：不把临时更新称纯评测
|范围|物理optimizer步|backward样本|NLL forward样本|完整两回合episodes|已完成generate|
|---|---:|---:|---:|---:|---:|
|工程A|2|16|32|0|0|
|修复后测评B|29|232|576|432|864|
|本次修复A+B|31|248|608|432|864|
|旧校准+中断01/失败02，另保留|2|16|384|49（24校准+25部分节点）|98|
|同轮Phase0-B记录合计|33|264|992|481|962|

逻辑suffix共30步，物理step1不双计；A另一个更新是丢弃的重跑对照。历史中断还有1个启动后未完成的generate，无法从未结束调用准确恢复其全部token/时间，不能把表中962“已完成调用”当所有启动调用。历史前向调用日志保留该未完成调用的部分工作，不删失败成本。

新A+B NLL输入288684 token；训练输入116363 token；generate输入302796、输出16635 token。新NLL整体记录255.257秒，B的27次step2…10更新段196.119秒，另外两种子保存step1更新段12.723秒；A主/对照更新段7.647/8.642秒。各Engine elapsed合计3387.966秒（A284.904，B3103.063），包含加载、I/O、恢复，不是纯GPU kernel时间。历史Engine elapsed另317.768秒。snapshot capture/save/restore是嵌套计时，详见各cost.json，不与elapsed或生成段重复相加。

CausalLM forward调用：新NLL608、训练248、生成16635；内部gradient-checkpoint层重计算不另算CausalLM调用。allocated峰值2585268224 bytes、reserved峰值11555307520 bytes；reserved/WSL计数不代表独占物理VRAM。nvidia-smi观察峰值7921MiB。额外CPU final wall 351.498秒、原始结果重评分26.608秒；均CUDA_initialized=false，0新增optimizer/forward/generate。早期CPU检查失败与旧CPU final耗时不伪装为零或并入GPU训练时长。

## 7. CPU final PID复用修复，不改科学合同
原02:39:45失败记录保留。旧守卫只判/proc/365或470存在，会把WSL复用PID的系统服务甚至本次CPU final自身误作GPU任务。新增v3 CPU入口用cmdline、项目模块、cwd/exe、boot_id/启动ticks和全局compute扫描，真实项目仍在必须阻断；系统Python只有明确root-owned系统脚本才识别为非项目，未知Python仍fail-closed。

6项模拟测试通过。原冻结GPU/科学模块SHA256仍7eef35c357e9b29c4726dbcb505fa65907788d6072db91773097c64ea4ef1435；数据manifest仍52daa1b9958d7e5f498042579ca88e58b4464beefacc9ca4ffe5418cbe5efa31。guard_only.diff/原新hash/CPU失败均保留，未更新原scientific receipt。原科学函数、数据和阈值一字未改。v1权限异常、v2误把系统Python当未知对象的CPU阻断也分别保留，不计为GPU attempt。

## 8. 收束方向与边界
本轮延长到真实10步、3种子后，仍未出现预定core退化，因此继续扩此无回放窗口不值得自动投入。与此同时，最终答案层确有配对退化，说明“完全没有遗忘事件”是错误表述；其次要分数跨种子不稳定，尚不能支撑replay训练。

自然无回放suffix不是P12含replay过程，未复现P12日期工具混淆，不能解释历史5条退化因果；也不能据此否定整条MIR路线。当前证据支持停止本配置扩训，而非提出已验证的新DG-MIR方法或投稿级创新。若未来改变核心问题，必须另行明确研究目标/预注册和授权；本轮不执行任何后续pilot。没有SQL重测、GSS、提示矩阵、RL/teacher或文献扩张。

## 9. 完成标记与文件
共同根目录（Windows）：C:\Users\Egret\Desktop\oulu\Agent Self-Evolution\fac_tinyagent
WSL：/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent

运行目录runs_ext_p13_phase0b_persist_20261119：
- GPU_COMPLETE.json，supervisor_end.json(rc0)，COMPLETE.json；全部进程已退出。
- summary.json、independent_acceptance.json、persistence_independent_CPU_checks.json。
- raw_independent_CPU_audit_20261119.json；cpu_final_guard_repair_20261119_v3/CPU_FINAL_COMPLETE.json。
- 各seeds/seed*/attempt*/prediction.json、node00/05/10、cost.json、restoration.json、extended_restoration.json。
- 原始CPU失败、各guard补丁receipt/diff和旧STOP归档均保留。

最终GPU只读检查2026-11-19 02:54:28北京时间：compute=[]，无其它项目Python、Apex或STOP，90W；445MiB为桌面占用，不冒充零显存。GPU段692次守卫检查全安全。未push、未发GPT，routine保持暂停，无后台训练或待自动续跑任务。
