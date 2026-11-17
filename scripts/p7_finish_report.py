"""Assemble the final Chinese report from completed, audited P7 measurements."""
from pathlib import Path
import datetime,statistics,sys
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent.utils import read_json,write_json,sha256_file
from fac_tinyagent.p7_response import RUN,SKILLS,verify

def main():
    verify();a=read_json(RUN/'analysis.json');assert a['complete']
    costs=read_json(RUN/'costs.json');audit=read_json(RUN/'audit.json');sql=read_json(RUN/'sql_counterfactual.json')
    ties=read_json(RUN/'sql_tie_counterexample.json');gens=read_json(RUN/'generation_audit.json')
    now=datetime.datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S +0800')
    mean=statistics.mean
    macro=lambda scores:mean(v['joint_success'] for v in scores.values())
    score_table=['|状态 / 两次更新的复习动作|种子08|种子09|种子10|均值|','|---|---|---|---|---|']
    for key,label in [('baseline','起点，0更新'),('background','背景复习'),*[(k,k) for k in SKILLS]]:
        vals=[macro(sd['baseline'] if key=='baseline' else sd['background_scores'] if key=='background' else sd['actions'][f'{key}_2']['scores']) for sd in a['seeds'].values()]
        score_table.append('|'+label+'|'+'|'.join(f'{x:.1%}' for x in [*vals,mean(vals)])+'|')
    gain_table=['|复习动作|dev宏NLL收益|check宏NLL收益|check每千replay token收益|','|---|---|---|---|']
    for k in SKILLS:
        rs=[sd['actions'][f'{k}_2'] for sd in a['seeds'].values()]
        gain_table.append('|'+k+'|'+'|'.join(f'{mean(v):+.6f}' for v in [[r['dev']['nll']['gain_vs_background'] for r in rs],[r['check']['nll']['gain_vs_background'] for r in rs],[r['check_gain_per_1k_tokens'] for r in rs]])+'|')
    rank_table=['|种子|P6 B/token首选|实测开发收益首选|check事后最优|P6排序ρ|实测开发排序ρ|','|---|---|---|---|---|---|']
    for seed,sd in a['seeds'].items():
        c=sd['choices']['2'];rank_table.append(f'|{seed}|{c["p6_proxy"]}|{c["measured_dev"]}|{c["check_oracle"]}|{c["spearman_proxy_to_check"]:.2f}|{c["spearman_dev_to_check"]:.2f}|')
    gt=['|技能|评测次数|工具正确|参数正确|执行结果匹配|最终答案正确|严格Joint|','|---|---|---|---|---|---|---|']
    for k,c in audit['counts'].items():gt.append('|'+k+'|'+'|'.join(str(c[z]) for z in ['n','tool_correct','arguments_correct','execution_success','final_correct','joint_success'])+'|')
    hits={name:sum(sd['choices']['2'][name]==sd['choices']['2']['check_oracle'] for sd in a['seeds'].values()) for name in ['p6_proxy','measured_dev']}
    negative=[f'{s}: {v["negative_cross_pairs"]}/{v["total_cross_pairs"]}' for s,v in audit['cross_gradients'].items()]
    text=f'''# P7实验报告：从梯度代理到实际复习响应

完成时间：{now}（北京时间）。本轮三个种子均已完成；原始P6结论保持原定义。详细数字见[逐种子明细](runs_ext_p7_response/TABLES_ZH.md)。

## 1. 这一轮做成了什么

本轮把“P6为什么没有赢”的宽泛问题拆成可以直接检验的环节：评分和工具执行是否可信、候选梯度是否预测实际更新的损失变化、损失变化能否转化为任务成功。完成了完整旧结果审计、数据库反例实验、三个种子的可回滚真实优化器更新，以及一个只接收开发集响应的收益选择器。

核心工程产物已经运行：独立恢复模型/优化器状态 → 小剂量实际更新 → 测量开发收益 → 按token成本选择动作 → 用另一组题检验排序。它是收益测量与选择原型；本轮没有把这个原型接入整个持续训练周期。

与已有P2/P6的关系：P2主要把梯度打分与历史训练计划成绩做关联；P6验证完整分配政策。本轮新增的是在同一个训练状态上施加明确动作、直接测量实际优化器响应，并用逐条工具反例定位错误，因此补上了此前缺少的机制证据。

先校正一个重要概念：P6使用的是开发宏梯度与候选梯度的归一化方向投影，B_k=max(0, g_dev·h_k / ||h_k||)，不是简单按梯度大小分配。本轮同时读取了梯度范数、交叉方向和实际更新响应，避免把P6简化为它没有使用过的方法。

## 2. 实验设计与复用

- 复用Qwen3-0.6B QLoRA、三个种子20261108/09/10、Calendar第80个microstep的共享前缀。参数、PagedAdamW8bit状态、scaler及随机状态逐动作恢复；学习率1e-4，累积8。
- 每个动作的每次更新：相同七条Calendar样本 + 一条指定replay；比较四技能与同种子背景复习。每个动作运行两次更新，在第0/1/2更新处测NLL。
- 使用原P6开发集16题；另生成P7响应验证集8题，每技能2题，新的措辞、实体，Python采用三位数。数据和算法在GPU运行前冻结。
- 在0和2更新处做B1 greedy工具调用与最终答案生成，共3×6×8=144次题目评测、288次完整生成。144次是8道题在18个模型状态上的评测，不是144道独立题。
- 未重训P5/P6；复用P6校准文件和432条原始结果。P7是同优化步数的动作替换实验，候选长度不同，成本另作归一化。

## 3. 旧结果审计：失败在哪里

重执行了全部432条预测工具调用；重执行并核验了P6 48题和P7 8题的gold工具结果。答案评分和Joint重算一致，未发现评分实现与存档不一致。

{chr(10).join(gt)}

File的108次调用和执行均正确，但108次都回答第一个匹配，而题目要最后一个匹配。这里需要改进的是工具结果的选择规则。

Median中98/108次调用了不存在的stats_sorted，10次正确调用stats_median。这里的主要错误是自然语言意图到工具的映射。

Database筛选的79次执行结果匹配中，只有13次参数完全正确。其余66次全部漏掉WHERE和id ASC；它们在原数据库上碰巧得到正确结果。为区分语法等价与偶然正确，进行了两类额外CPU干预：

1. 所有记录都不满足阈值：66/66条查询失败，证明过滤条件确实必要。
2. 所有记录满足阈值且分数并列，同时使用合法(score DESC, id DESC)索引：66/66条查询失败，独立暴露并列排序错误。

因此，提高执行成功率的评分宽容度会把这些真实语义错误隐藏起来。应该改进测试实例的辨识能力，而不是改写P6主成绩。反例是看过错误后的诊断实验，作用是定位原因。

P7还观察到list_tables的多余参数问题：新响应集所有状态合计{gens[SKILLS[0]].get('extraneous_arguments',0)}/{gens[SKILLS[0]]['n']}次调用携带了额外参数；执行器可以忽略它们继续返回结果。工具参数合法性、执行结果与最终答案应分别衡量。

## 4. 实际更新是否改善任务成功

下面是新P7响应验证集上的严格Joint。每种子只有8题，表中单题对应12.5个百分点。

{chr(10).join(score_table)}

这些数字回答“在这个中点、这两次更新后，实际行为怎样变化”。起点到动作的差同时包含后续Calendar训练；动作相对背景的差用于比较复习内容。表格不代表P6训练终点成绩，也不能与P6的48题考试直接横比。

## 5. 损失收益、梯度排序与任务成功

NLL是标准答案的负对数似然，越低越好。下面是两次更新后相对背景控制的减少量，正数为收益，三种子均值。

{chr(10).join(gain_table)}

选择规则和新响应题排序：

{chr(10).join(rank_table)}

P6的B/token首选命中新响应集NLL最优动作{hits['p6_proxy']}/3次；实测dev收益/token首选命中{hits['measured_dev']}/3次。这里只比较一次局部动作排序，不是重跑P6完整10条预算规划。ρ是每种子四个动作的描述性Spearman，不作显著性检验。另一个剂量、梯度范数和实际单样本梯度排序在明细JSON中完整保留。

不能把“有局部损失预测能力”与“最终任务收益已经被预测”视为同一件事。teacher forcing下，很多格式和答案token本来就容易；完整工具链却可能被一个错误工具名、一个多余参数或一次first/last选择决定。P7的生成与NLL并列记录正是为了直接检查这一差别。

P6已有的跨技能开发/候选梯度矩阵中，非对角负点积数分别为：{'; '.join(negative)}。负点积说明该局部方向存在冲突；真正更新后的跨技能影响已另外测量，见明细矩阵。保存的Adam实际参数位移与开发梯度点积用于事后检查线性近似；它需要知道更新后的参数，不能充当免费预知收益的算法。

## 6. 本轮核心算法

令训练状态S=(θ,optimizer,scaler,RNG)。A_k^d表示按固定日历上下文执行d次“七条Calendar+一条技能k经验”的真实更新；A_0^d为同样的背景动作。

L_dev(S)=四个技能的开发题NLL宏平均。

Δ_k(d)=L_dev(A_0^d(S))−L_dev(A_k^d(S))。

V_k(d)=Δ_k(d)/C_k(d)，C为该动作实际replay输入token数。

选择k*=argmax V_k(d)。函数仅接受开发响应和成本，验证集不进入接口。跨技能损害通过宏平均进入Δ，也单独输出响应矩阵。

```text
保存同一训练状态S
对背景动作0和四个候选动作k：
    完整恢复S
    执行固定剂量真实更新
    记录每项技能的开发NLL和实际token成本
计算每个k相对背景的宏NLL收益/token
选择最高值，保留收益为负的真实符号
另用新响应题评估这个排序与实际任务行为
恢复S，结束诊断
```

实现：[p7_allocator.py](fac_tinyagent/p7_allocator.py)；执行实验：[p7_response.py](fac_tinyagent/p7_response.py)。收益值的单位是NLL/token，尚未校准成正确率提升/token。诊断探针执行的更新虽不留在生产模型里，计算成本仍完整计入。

5项测试覆盖：token成本反转原始收益排序、跨技能损害、开发题不一致拒绝、负收益不包装为正收益、技能宏平均不被题量差异改变。

## 7. 实验执行评价与成本

本轮效率较高的部分是利用原始结果定位错误，再用30次逻辑诊断更新测响应；无须重复9个完整P6训练分支。每次真实更新均有receipt，原有输入哈希保持一致，所有种子最终恢复到原前缀状态。

实验在16:42:34检测到Apex后由watchdog停止；用户随后明确授权“游戏退出后自动接续本轮实验”。已完成评测复用，中断的两次更新从原状态确定性重建，重建参数哈希与原保存状态一致才继续复用结果。

- 逻辑诊断更新：{costs['optimizer_steps']}；中断重建：{costs.get('reconstruction_optimizer_steps',0)}；实际执行合计：{costs['total_optimizer_steps_including_reconstruction']}。
- 训练forward/backward：{costs['total_training_backward_including_reconstruction']}对（含重建）；另有{costs['diagnostic_backward']}次梯度诊断反传。
- NLL测量forward：{costs['nll_forward']}次；完整生成评测{costs['generation_episodes']}题、{costs['generation_calls']}次调用。
- 完整记录的生成输入token：{costs['generation_input_tokens']}，输出token：{costs['generation_output_tokens']}。
- 训练输入token（含重建）：{costs['total_training_input_tokens_including_reconstruction']}。

被中断且未输出的生成token无法精确恢复，未把它记为零。计时、重建和分项成本在[costs.json](runs_ext_p7_response/costs.json)；种子计时不等于包含游戏等待和模型加载的总墙钟。

范围很明确：三个训练种子、四个已知技能、一个中点、两个局部剂量、8道新响应题。这足够定位现有错误和检验短程信号，不足以估计完整EAAR在长期持续训练中的效果；下一轮应验证新的机制，而不是给本轮增加重复次数。

## 8. 下一步如何开展

优先修复经验和评测的辨识能力：File用first/last成对意图；Median区分排序序列与中央值；Database加入0个/少于k个满足条件和并列分数的实例；工具层严格检查参数。先让错误规则在开发集上明确失败。

然后把收益信号从整体NLL改为独立开发题上的实际任务成功变化；若小剂量下动作全打平，保留均衡，不用微小整体NLL差异决定大量预算。关键分支正确/错误候选的概率差可以作为单独待验证的辅助信号。

正式比较只需A原经验均衡、B对照经验均衡、C同一对照池的收益分配。A尽量复用现有P6 adapter，B−A检验经验内容，C−B检验分配规则。匹配条件允许时只需6个新增完整分支。开发/测试重新冻结，P7响应题归入已见历史。具体数据、公式与成本比较见[P8下一轮设计](P8_NEXT_DESIGN_20261115_ZH.md)。

## 9. 参考与复现入口

- 用户提供的ChatGPT聊天《智能体自进化实验规模》，本轮已读取完整近期建议；结合本地P6报告和原始产物制定P7。
- [P7实验前协议](P7_PROTOCOL_20261115_ZH.md)、[逐种子原始分析](runs_ext_p7_response/analysis.json)、[全部数字明细](runs_ext_p7_response/TABLES_ZH.md)。
- 实验设计技能用于配对/分块和避免伪重复。Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents. https://doi.org/10.48550/arXiv.2609.00065 。已核对arXiv当前记录；本报告的实验数据来自本地运行。
'''
    report=ROOT/'EXT_REPORT_20261115_p7_response_ZH.md';report.write_text(text,encoding='utf-8')
    handover=ROOT/'EXT_HANDOVER_20261115_p7_response_ZH.md'
    handover.write_text(f'''# P7交接

完成时间：{now}。3/3种子；30逻辑更新，{costs['total_optimizer_steps_including_reconstruction']}实际更新含重建；144题B1生成；输入hash校验通过。

报告：EXT_REPORT_20261115_p7_response_ZH.md；明细：runs_ext_p7_response/TABLES_ZH.md；下一步：P8_NEXT_DESIGN_20261115_ZH.md。

CPU重新分析：`.venv/bin/python -B scripts/p7_analyze.py analyze`，随后`p7_report_tables.py`和`p7_finish_report.py`。不需要重新运行GPU队列。

执行代码：fac_tinyagent/p7_response.py；中断接续副本：p7_resume.py；选择器：p7_allocator.py。原冻结代码未修改，resume_manifest.json记录接续版本。用户授权游戏退出后接续；STOP.game_*保留首次中断原因。

审计：audit.json、sql_counterfactual.json、sql_tie_counterexample.json、generation_audit.json、costs.json、final_manifest.json。所有路径位于runs_ext_p7_response/。P8仅设计，尚未训练。
''',encoding='utf-8')
    write_json(RUN/'deliverables_manifest.json',{'complete':True,'created':now,'files':{str(p.relative_to(ROOT)):sha256_file(p) for p in [report,handover,ROOT/'P8_NEXT_DESIGN_20261115_ZH.md',Path(__file__)]}})
    print(report)

if __name__=='__main__':main()
