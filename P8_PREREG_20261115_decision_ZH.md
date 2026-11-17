# P8预注册：有辨识力的经验内容能否打通严格任务成功

状态：正式GPU开跑前冻结；没有P8实验结论。2026-11-15，北京时间。仅用户笔记本fac_tinyagent本地新增资产，不启动P9。

## 研究判断与GPT建议取舍
保留：P7已测短程NLL响应、细粒度失败诊断和完整状态恢复，下一步必须看严格Joint而不是只看NLL。
拒绝：五特征回归没有足够独立样本，目标Joint基本平坦，不能拟合成收益预测器；五组Random/Uniform/Early/Gradient/ShortHorizon当前不能回答内容是否有用。P7的6次嵌套dev/check top1一致只涉及短程NLL，不证明完整训练收益预测。原审计list_tables的108次=82正确db_list_tables+13未解析工具+13错误db_query，不沿袭82+13的漏计。
本轮只回答一个有辨识度问题：固定其他训练因素，新的合法决策对照正例包，能否提高新holdout严格Joint？不为凑三组再跑一个无已证实任务信号的C。P7小剂量任务成功相对背景全平；本轮预设零信号fallback=固定均衡分散，不用微小整体NLL决定预算。C与收益分配留待内容有效后另行设计，本轮不自动开展。

## 两臂、三个种子与复用边界
种子固定20261108/09/10。
A original：只读复用已完成P6 attempt2 balanced_uniform的三个最终adapter，不重新训练A。在同一新P8评测协议/题目上重新B1评测。
B decision：三个新正式训练。从同一个E4 Calendar step80前缀（参数/optimizer/scaler/RNG）开始；同学习率、QLoRA、Calendar顺序、同22条replay packing与插入槽位。12条背景经验的ID/内容/顺序完全不变，仅替换10个目标槽。
均衡技能槽数量继承A：08为list/filter/file/median=3/2/2/3；09=2/2/3/3；10=3/3/2/2。File槽内至少一对同文件first/last合法正例，不推理时硬编码答案。
A复用须核实完整summary、23累计更新、13后缀实际optimizer事件、相同前缀、相同Calendar新数据及102行实际packing日志。B审计逐行比较(kind,new_position,microstep,optimizer_step)、新Calendar ID/token完全相同；任何差异停止，不混用不公平A。

## 经验包与可计算选择机制
新训练池44条：list_tables8、SQL12、File first/last 8对共16、median8。合法完整正例，不构造错误调用为训练目标。
- File：同一文件多个不同匹配，first≠last；分别要求第一/最后，观察结果与答案合法。
- SQL：zero、few、ties；few场景同时不足k且合格项并列。以score DESC,id DESC索引制造省略tie规则的可检验反例。gold使用WHERE与id ASC；CPU分别验证漏WHERE、漏tie和组合错误，不改执行器/评分。
- Median：合法stats_median工具、中央标量而非排序列表；训练/开发/正式全部与A匹配7个两位数11..40，完整输入数值集合相互分离并避开历史原题，不把数字位数与措辞混淆。
- list_tables：新schema实体、合法空参数与多种措辞；严格参数指标拒绝额外参数。

选择不看模型分数、dev表现或holdout结果：
```
给定A的10个目标槽及每技能数量n_k：
  枚举各技能合法候选组合（ID不同）；
  File必须同文件first/last成对；SQL必须含zero与few+tie；
  在这些有限组合中，最小化|B目标输入tokens−A目标输入tokens|；
  随机种子固定的遍历顺序打破完全相同成本的平局；
  依A的目标技能序列填回相同槽位，背景12条原封不动。
```
这是token约束的经验内容干预，不是已实现在线自适应。经验包同时改变错误辨识信息/措辞/多样性，不把其中某一项独立因果或算法新颖性夸大。

## 实际预算、监督量与开销
每分支累计23次optimizer更新=复用前缀10+新后缀13；80 Calendar后缀+22 replay=102 microsteps，最后6条归一化后真实flush一次。禁止凭空补步。
A各7494 replay input tokens；B最接近的合法组合为08=7521（+0.3603%）、09=7538（+0.5871%）、10=7556（+0.8273%），均<=1%。不声称精确相同token；无padding、无无意义答案填充、batch1。监督token A=1202/1187/1184，B=1238/1223/1234，差异如实报告，不能将内容干预效果说成与监督量完全独立。
本轮只有3个新训练分支，新增39次optimizer更新；A历史训练成本单列，不伪称未发生。没有GPU开发校准、没有虚拟探针更新，两臂诊断额外训练成本都为0。新B全部候选可见不代表全部训练，实际只训练计划22条。
前缀使用原池真实hash/元数据；附加P8池只在前缀之后参与显式plan，不改原池，也不更改或伪造prefix metadata。prefix replay_samples必须为0。

## 独立数据与指标
新dev16：每技能4题，仅CPU gold检查；本轮不以其成绩选经验或调参。
新prospective holdout：主4技能各12=48题；额外4题File first与4题Python mean作行为专属性控制，共56。训练/dev/holdout模板家族、数据库实体、File路径/关键词、完整数值集合分开并冻结；与P6/P7已见卷完整prompt/message不重合。不是跨新技能/新模型泛化证明。
主指标：4技能strict Joint宏平均（tool、严格args、执行、final全部满足）。不改变SQL参数匹配口径，不把字符串不同一概解释为语义错误；执行正确与严格args分阶段单列。
次指标：每技能tool/args/execution/final/Joint；first、mean控制；Calendar v3fix30；旧非目标Database/File/Python各预先固定4题，不全量重复历史卷。旧正式题仅副作用指标，不进入经验选择。
共6个终点×7个B1 suites=42套；每终点98题，总588题状态评测，不是588个独立统计复本。

## 事先判据与失败解释
内容支持的主判据：三种子B−A严格Joint宏平均全部>0，均值>=0.10。报告所有逐种子差，不进行伪重复p值包装。
副作用：Calendar均值下降>0.05或任一非目标族均值下降>0.10时明确报告代价，不能只报目标技能提升。first/mean控制下降提示特异性或过拟合问题。
未达主判据：本轮经验包在此预算下未提供预注册强支持；不能推出有辨识经验普遍无用。若NLL/工具改好而Joint没改好，仍分别定位错误链；不得看正式结果后临时追加C、换题、改预算/参数。

## 验收、持久性与运行
CPU必须覆盖116条新样本gold、预定义错误反例、独立性、全部计划字段；真实P8 runner→trainer→13次实际SGD更新→尾flush→summary/full-state磁盘恢复；B1结果字段与partial/complete finalize边界用显式CPU桩，不伪称真实模型效果。
完整状态用已修复P7 v2原生bnb loader契约，真实PagedAdamW8bit FSDP序列化/解包/prefetch已验收，P8再在prefix和训练终点严格落盘加载并校验参数/optimizer/scaler/RNG/模式。旧资产/环境不改。
首个正式B08必须训练收尾成功、实际更新审计通过并完成首24题Database真实B1，才放行余比较；只检查执行/协议/题数，不看成绩决定是否放行。修复如需变更实质行为则新attempt，不删校验。
单GPU，Apex、其他GPU任务、功率上限>=60W、连续检查失败守卫；STOP粘性，绝不自动清除/恢复。可靠Windows WSL持久宿主。预计整个队列约50–100分钟（以真实日志为准），启动确认首关后交接，不等待全部完成。
完成：QUEUE COMPLETE + END queue rc=0 + summary.complete=true + 42套B1。CPU收尾：PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B -m fac_tinyagent.p8_decision_20261115 --phase finalize。
