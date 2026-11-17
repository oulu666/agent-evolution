# P9独立FINAL交接与P10仅CPU候选

数据快照2026-11-17 15:44:43 +0800；报告`EXT_REPORT_20261117_p9_independent_final_ZH.md`。

- P9于2026-11-17 15:40:46北京时间完成，15:40:48监督器CHILD END 0；9/9完整评测、6/6训练、864调用。原summary仍停在15:11的旧稿，不等于队列失败。本助手没有运行GPT的写回汇总器。
- last正常Joint（08/09/10）：P8=8/4/4，ordinary=11/9/11，CF=5/5/4，分母均12。均值44.44/86.11/38.89%；ordinary−P8 +41.67pp，CF−ordinary −47.22pp，CF三种子全负。
- first正常均值P8 86.11%、ordinary/CF均94.44%；逆序first ordinary0/36、CF10/36，逆序last ordinary6/36、CF24/36。所有组all4均0/36。正常两意图联合分别16/36、29/36、12/36。
- ordinary last正常36/36工具/参数/执行正确、31/36答案正确；CF前三项同36/36、答案14/36。ordinary也没有行号不变规则；CF更常复制首呈现项，条件间收益转移，不是正常提分。
- Calendar由P8 3/12降为两个新组各1/12；median均6/6，list_tables均4/6但逐种子变化。P9没测复杂SQL/mean，不能叫旧技能全面无损。

## CPU候选已经落地，但不具备直接GPU启动条件

- 新增草案P10_PREREG_DRAFT_20261117_twoview_ZH.md，构建器fac_tinyagent/p10_twoview_plan_20261117.py，资产data_ext_p10_twoview_cpu_20261117/，检查cpu_acceptance.json和manifest.json。
- 两策略×三种子：复用P9 ordinary；新增B仅3个种子分支（不是3种新策略），从同一P8 fullstate出发，原始normal/reverse各一次，72条×2轮144微步/18更新。
- 实测每条完整labels、每位置输入长度、每优化批和全程token精确相等：53,734输入/7,486监督每臂。合计仅54新增更新。三对起点/来源权重、188次gold检查、CPU toy18+2次更新和完整状态恢复全通过。GPU研究模型0加载/0生成/0更新。
- 新12File正式卷按训练风格/2新措辞×2/3/4/5匹配交叉；沿用未训练dev4文件。保持补全为Calendar4/median2/list_tables2/新独立复杂SQL4。CPU反例与等价ASC测试通过。
- 尚无新GPU runner/真实QLoRA与bitsandbytes E2E，不应声称可一键开跑；下一实施阶段需新增执行器并首B训练摘要+首B1过关。

## 推荐给主助手的决策

暂不无条件启动三新训练。机制缺口明确但没有双视图正向收益证据；先考虑授权72次独立dev推理（0更新），确认问题仍存在。即使触发也只是问题证据，不保证提高ordinary正常B1。若目标仅提正常分数，不能为了挽救CF故事而开；若确认要验证顺序不变性，再有限执行预注册两臂。
若继续：同一新卷必须对ordinary与新B都重评；主效果B−ordinary，不能只比P8或复用旧卷分数。648计划生成（72dev+576正式），约30—40分钟；新训练54更新。当前未授权启动，也未实际GPU诊断。

## 状态核查的局限

CPU准备后执行过一次实时核查，但Windows tasklist非UTF8导致本助手整理异常，未保留实时GPU/Apex输出；未重复轮询。已由固定完成回执与退出日志完成离线核齐。开始任何GPU工作前必须重新安全预检并取得授权，无Apex/其他GPU/STOP、功率上限≥60W；游戏STOP不能自动清除续跑。

## 文件

- 完整报告：`EXT_REPORT_20261117_p9_independent_final_ZH.md`。
- 本交接：`EXT_HANDOVER_20261117_p9_independent_final_ZH.md`。
- 完整独立数据：analysis_p9_independent_final_20261117/results.json。
- 阶段版、P9原资产及GPT报告完全保留；P10候选内容未根据第三种子结果修改。
- Windows项目根：C:\Users\Egret\Desktop\oulu\Agent Self-Evolution\fac_tinyagent。
- WSL项目根：/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent。
