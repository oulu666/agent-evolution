# P13 Phase0-B：状态持久化操作性修订（不改科学判据）

授权：2026-11-19 01:04（北京时间），用户原话：“允许进行一次单种子最多两步的工程诊断，修复并验证状态保存恢复；通过后给受影响种子增加一次测评机会，不改科学判据，再失败就停止。”

仅新增P13 Phase0-B文件；原预注册、数据、候选/探针、失败attempt01/02、STOP归档和CPU_DIAGNOSIS不改。该授权不是未来自动清STOP，也不授权正式MIR/DG-MIR或新增研究实验。当前研究round不更名，seed08新机会明确记作授权attempt03；不是把第三次重命名成原额度。

## 阶段A：先过工程门，最多一次
种子仅20261108；原冻结下一批8条。诊断行固定为训练侧candidate中每技能case 0/7/14/21，共8条。不生成答案，不筛题。
1. 恢复原前缀，保存扩展origin；8条分段NLL。
2. 仅一次虚拟更新，记录8个训练loss、梯度hash、LoRA/optimizer/RNG/backend与量化基座指纹；保存theta_v1检查点，8条NLL作为主预测参考。
3. 从origin恢复，再从磁盘保存的theta_v1恢复；8条NLL。必须LoRA/optimizer/scaler/RNG/modes、冻结基座/buffers/quant_state和已记录backend指纹精确匹配，8条所有分段NLL/row payload逐值精确一致（不用epsilon）。
4. 从origin再重跑同批一次作对照，8条NLL；记录梯度、参数、数值和排序差距，但绝不用对照替代theta_v1，也不因重跑是否相同决定主预测分数。
5. finally恢复origin并验证，才允许A通过。预算硬限2临时optimizer步、16 backward、32 NLL forward、0 generate；失败即止，不进阶段B。

## 扩展持久化合同
LoRA/optimizer/scaler/四类RNG/module modes沿用原精确保存，同时保存冻结非LoRA参数原始张量、全部named buffers、Params4bit与Linear4bit QuantState（原生as_dict/from_dict，含absmax、codebook、nested state、offset、dtype等）、量化参数属性、相关计算dtype/dropout配置、config/attention/use_cache及可记录的TF32/cuDNN/SDPA/版本/环境指纹。以语义hash与文件hash双绑定；不声称可序列化CUDA库全部隐藏缓存。基座内容寻址去重保存，禁止覆盖。

不再要求重新执行浮点更新重建已存在的theta_v。每个逻辑后缀节点都持久化状态，评测前后完整恢复/hash核验；本次失败或新安全中断不自动再开attempt。没有新的近似容差；原科学门槛完全不变。

## 阶段B：A通过后单次测评机会
- 原三个种子与48候选/48探针、6段mask、batch、LR、QLoRA、PagedAdamW8bit、自然后缀10步、0/5/10生成、主0→10及全部主gate均不改。
- seed08使用A保存且已验证的theta_v1，不再重演虚拟浮点步；另两种子各只计算一次theta_v1并保存，后续只从保存状态恢复。三种子完整校准/formal_freeze复用；旧不完整node00不复用。
- 显式物理步骤归属：A的第1个临时更新只贡献seed08后缀逻辑step1，不是完整训练轨迹；A第2个对照更新丢弃。前缀生成后恢复已保存theta_v1，才接step2…10。seed09/10同样将一次保存的预览theta_v1作为逻辑step1，不再次重算。主预测在虚拟分支中先锁定，不能看终点改分数。
- 因此阶段B新增物理更新为seed08的9步+另两种子各10步=29步/232 backward；另有576 NLL forward、432两回合episodes/864 generate。A另计2步/16 backward/32 NLL forward/0 generate。合计本次授权31物理临时步，不双计被复用的step1；历史失败两步及25条部分生成仍单列计成本。逻辑自然后缀仍每种子恰10步，不是9步。
- 受影响seed08仅新增一次attempt03；其它种子仍按原库存上限，本程序每个种子只开一次，不自动重试。任一修复/测评错误或新游戏/STOP/低功耗则安全停，无本授权自动解除新STOP。

## 科学gate原样保留
各种子按自身0步正确定义at-risk，全体探针保留；至少2种子各≥5工具+参数退化且≥5未退化；within-seed AUROC宏平均≥0.65且优于初始NLL_call/TokenCost，种子×探针聚类bootstrap差值95%下界>0、有效replicate≥800。中点/其它组件/候选配对不救主gate；不足即UNIDENTIFIABLE。不自动开正式pilot。

## 监督、产物与验收
新运行根runs_ext_p13_phase0b_persist_20261119；3秒GPU守卫，无Apex/竞争项目且功耗≥60W/无STOP才运行。不得清STOP或杀游戏。原历史guard/STOP归档仍保留，新会话日志独立记录，不过滤安全事件。
A_PASS及精确恢复审计先落盘才进入B。GPU全部退出、监督器rc0、三种子完成后，才运行新的路径/物理步骤兼容的独立CPU final。报告明确工程通过不等于MIR有效，全部诊断/持久化/重建成本单列。不push、不发GPT、不改routine/memory/todo。

### 冻结前CPU测试说明
原生bitsandbytes导入会初始化CUDA context，首次仅CPU QuantState张量往返测试已精确通过，但“不初始化CUDA”的附加断言失败；该构建失败日志保留。此时尚无A_STARTED、无模型加载/forward/backward/generate、不消费工程诊断更新或测评attempt。修正的是CPU测试的运行时描述，不改A精确保存/NLL通过门槛。后续记录原生库是否初始化context，不将CPU张量测试误称完全未触及驱动。
