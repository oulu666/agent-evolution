from pathlib import Path
import collections,datetime,json,statistics,sys
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent.utils import read_json,read_jsonl,write_json,sha256_file
from fac_tinyagent.p81_diagnosis_20261116 import RUN,DATA,SEEDS,verify
mean=statistics.mean
def main():
    verify();s=read_json(RUN/'summary.json');assert s['complete'];stress=read_json(RUN/'sql_stress.json');assert stress['n_queries']==72
    rows=[r for p in sorted(RUN.glob('seed*.jsonl')) for r in read_jsonl(p)];assert len(rows)==244
    now=datetime.datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S +0800')
    def frac(rs,key):return f"{sum(bool(r[key]) for r in rs)}/{len(rs)} ({mean(bool(r[key]) for r in rs):.1%})"
    ft=['|表达|观察呈现|first正确|last正确|两种意图都正确的配对|','|---|---|---|---|---|']
    for w in ['natural','explicit_line']:
        for p in ['ascending','reversed']:
            f=[r for r in rows if r['kind']=='file' and r['meta']['wording']==w and r['meta']['presentation']==p]
            ps=[s['file_pairs'][f'{seed}/{w}/{p}'] for seed in SEEDS]
            ft.append(f'|{w}|{p}|{frac([r for r in f if r["meta"]["intent"]=="first"],"correct")}|{frac([r for r in f if r["meta"]["intent"]=="last"],"correct")}|{sum(round(x["both_correct"]*x["n_pairs"]) for x in ps)}/18|')
    st=['|表达|SQL任务|严格参数正确|当前实例语义正确|3种CPU变体也通过|','|---|---|---|---|---|']
    for w in ['natural','structured']:
        for op in ['sort','filter','filter_sort','filter_sort_tie']:
            rs=[r for r in rows if r['kind']=='sql' and r['meta']['wording']==w and r['meta']['operation']==op]
            ss=[r for r in stress['details'] if r['wording']==w and r['operation']==op]
            st.append(f'|{w}|{op}|{frac(rs,"arguments_correct")}|{frac(rs,"semantic_execution")}|{frac(ss,"robust")}|')
    tt=['|种子|实际P8训练技能|题数|Original Joint|Decision Joint|','|---|---|---|---|---|']
    for seed in SEEDS:
        for skill in ['file.search_first','file.search_last','db.filter_cmp_top']:
            a=s['seen_train'][f'{seed}/original/{skill}'];b=s['seen_train'][f'{seed}/decision/{skill}']
            tt.append(f'|{seed}|{skill}|{a["n"]}|{a["joint_success"]:.1%}|{b["joint_success"]:.1%}|')
    agg={}
    for arm in ['original','decision']:
        agg[arm]={}
        for skill in ['file.search_first','file.search_last','db.filter_cmp_top']:
            rs=[r for r in rows if r['kind']=='seen' and r['arm']==arm and r['skill']==skill]
            agg[arm][skill]={'correct':sum(r['joint_success'] for r in rs),'n':len(rs)}
    write_json(RUN/'seen_aggregate.json',agg)
    counts=read_json(RUN/'p8_detailed_errors.json')['counts']
    structured=[r for r in rows if r['kind']=='sql' and r['meta']['wording']=='structured']
    file_first=mean(r['first_presented'] for r in rows if r['kind']=='file' and r['meta']['presentation']=='reversed')
    lines=f'''# P8.1实验报告：困难技能的组合与顺序诊断

完成：{now}（北京时间）。6个已有模型终点全部评测完成；244条输出记录、272次生成调用，新增训练更新0次。

## 本轮回答了什么

P8的新经验包没有打通File末项提取和复杂SQL。本轮复用其模型，检查实际训练样本、File配对干预和SQL任务阶梯。它直接检验失败环节，不重训P6/P8，不扩种子，也不重复P7梯度诊断。

最关键的判断来自三类证据：模型是否能完成实际见过的题；固定内容后仅改意图/呈现能否改变输出；单操作与组合操作的成功是否分离。原始P8严格成绩保留原值。

本轮得到三个具体结论：P8 Decision对实际训练过的last样本达到4/4，对SQL达到6/7，而Original分别0/4、0/7；File自然表达下表现出完全一致的首呈现项捷径；SQL自然表达能完成单操作，却在组合约束上失败，结构化表达可修复种子09/10的组合调用，但种子08仍失败。因此研究焦点应放在规则迁移、表示依赖与约束组合，而不是把P8解释成经验毫无作用或模型绝对不会这些技能。

## 1. 实际见过的训练样本

样本ID来自每个种子的真实P8 replay计划，而不是整个候选池。每种子共4/5/5条困难样本，分别在Original和Decision终点完整B1评测。

{chr(10).join(tt)}

汇总记录：

```json
{json.dumps(agg,ensure_ascii=False,indent=2)}
```

Decision能否答对这些样本决定下一步解释方向：训练样本成功、新组合或新表达失败，支持研究迁移与组合；训练样本终点失败则还涉及监督或后续训练干扰。终点评测本身无法区分“从未学会”和“学会后又忘记”。

P8实际File last槽数从Original的2/3/2变成Decision的1/2/1，同时各增加1条first。它保持了File总槽数，却减少了直接last练习。后续单因素比较需要固定last次数，避免再次混入这个变化。

## 2. File：内容相同，意图和顺序的配对干预

6个新文件，分别包含2/3/4个匹配，各2例；匹配文本不同，first与last答案始终不同。每个文件交叉first/last意图、正常/逆序工具返回、自然表达/明确最小最大行号，共48个条件×3种子=144次答案生成。

给定相同合法工具调用和全部正确返回内容；正确答案依据原文件行号，不随列表显示顺序改变。这是在隔离最终答案阶段，不是完整端到端Joint评测。

{chr(10).join(ft)}

逆序条件下，总体复制“首个呈现项”的比例为{file_first:.1%}。如果last因逆序变好而first变差，这个提升来自呈现位置与正确答案碰巧对齐；判断是否学会规则，要看同一观察下first和last两个意图是否同时答对。

三个种子在自然表达下得到完全相同的模式：正常顺序first=100%、last=0%；逆序后first=0%、last=100%，每个条件各18次跨种子评测。同一观察下切换first/last，答案没有变化。明确最小/最大行号后，正常顺序last为3/6、4/6、4/6，合计11/18；逆序时first仍为0/18。这是可干预的位置捷径证据，尚不是一条对显示顺序稳定的选择规则。

显式行号表达提供了另一种语言条件；它与自然表达在同一文件、同一观察顺序上配对比较。它可以显示规则表达的敏感性，但不能把表现较好的提示直接称为已学会普遍末项提取。

逐种子与每个配对的结果在summary.json的file_cells/file_pairs中，原始回答在seed*_decision.jsonl。

## 3. SQL：单操作、组合操作与格式迁移

三类新数据库zero/few/ties，每类交叉四个操作和两种表达。自然表达用完整任务句；结构化表达给出Table/Output/Filter/Ordering/Limit字段，没有给完整SQL答案。共24题×3种子=72次工具调用生成。

严格参数匹配与语义执行分开。语义oracle允许任务没有规定的行顺序与并列次序，按真实SQLite记录独立检查输出列、资格、数量、分数顺序和指定的id排序。6项CPU测试核验了合法等价结果与错误结果的区别。

{chr(10).join(st)}

结构化表达中正确工具调用为{sum(r['tool_correct'] for r in structured)}/{len(structured)}。若模型输出answer而未返回合法tool+arguments，失败发生在调用格式，而不是SQL执行。结构化提示在这组模型上需要验证，不能预设它一定更容易。

逐种子差异很重要：种子08的12个结构化调用全失败，常直接输出answer；种子09能完成结构化filter及两个组合操作，种子10能完成全部四类。两个组合任务的结构化语义通过率各为6/9，且这6条查询也通过三个CPU数据变体。与此相对，自然语言的sort和filter分别9/9，两个组合任务的变体稳健通过数均为0/9。模型具有可被特定表达激发的组合能力，但该能力对种子和表达方式敏感。

本轮还直接证实了严格参数字符串评分的一个盲点：structured filter_sort_tie的严格参数正确只有1/9，而语义及CPU变体检验均为6/9。例如种子09生成`ORDER BY score DESC, id LIMIT 4`，gold为`ORDER BY score DESC, id ASC LIMIT 4`；这三条输出因省略ASC被严格字符串匹配判错，实际返回符合要求。下一轮应同时保存严格匹配诊断与schema合法性＋语义执行＋最终答案指标，在共同新评测口径下比较各组。P8仍保留冻结的原口径。

额外CPU反例测试只重执行已生成SQL，没有新增模型调用：打乱name与id的相关性，改变分数分布，并加入score=50边界。每条SQL测试3种变体，共216次CPU查询测试。这个事后诊断保留原有分数，额外区分“当前实例碰巧正确”与能在这些变体上保持规则。其必要性来自观察到ORDER BY name替代id规则、以及省略WHERE在全合格表上仍返回正确结果。

## 4. P8旧失败的具体组成

对已有P8的72次File last和72次SQL输出只做CPU分类，未再次运行模型。

Decision的File last：16/36次复制第一项，20/36次把全部匹配行连接后输出；Original为16次第一项、14次连接全部、6次输出全部组成的列表。两者都不是末项选择。

SQL错误是非互斥的：

|错误|Original（36次）|Decision（36次）|
|---|---|---|
|错表名|{counts['original/db.filter_cmp_top']['wrong_table']}|{counts['decision/db.filter_cmp_top']['wrong_table']}|
|多余/错误输出列|{counts['original/db.filter_cmp_top']['extra_or_wrong_columns']}|{counts['decision/db.filter_cmp_top']['extra_or_wrong_columns']}|
|错误LIMIT|{counts['original/db.filter_cmp_top']['wrong_limit']}|{counts['decision/db.filter_cmp_top']['wrong_limit']}|
|遗漏WHERE|{counts['original/db.filter_cmp_top']['missing_where']}|{counts['decision/db.filter_cmp_top']['missing_where']}|
|遗漏id ASC|{counts['original/db.filter_cmp_top']['missing_tie']}|{counts['decision/db.filter_cmp_top']['missing_tie']}|

这些是对存档简单查询的字面要素分类，不能加总为独立错误题数。典型错误还包括沿用旧表名employees，以及输出SELECT id,name,score而任务只要name。它们提示表实体绑定、列投影和组合约束需要分别衡量。

## 5. 核心算法设计

本轮已经执行的是“失败阶段定位→配对干预→响应矩阵”，具体算法及公式见[P81_CORE_ALGORITHM_20261116_ZH.md](P81_CORE_ALGORITHM_20261116_ZH.md)。

File使用Aθ(x,intent,presentation,wording)，直接测指令配对成功率、首呈现项偏好与顺序/表达效应。SQL使用固定schema的操作阶梯与语义oracle，分开看单操作、组合、格式迁移。实际见过样本用于区分终点训练表现与新题表现。

下一阶段的可执行循环是：针对首个失败环节构造反事实经验，在同一完整训练状态上测短更新后的实际开发任务成功变化，再用单位总成本收益分配预算。收益仍为V(a)=[success_dev(Update(S,a))−success_dev(Update(S,background))]/cost(a)。目前实现并完成的是诊断部分；反事实训练与新的预算分配效能留给下一轮验证。

## 6. 如何开展下一轮

优先做File的呈现不变性单因素实验，因为这里已有直接配对干预。A复用P8 Decision模型作为对照；B从同一前缀出发，用相同训练题、first/last次数、目标槽和预算，仅重排File训练对话中的工具结果呈现。文件内容、任务意图和正确答案不变。这样检验“依赖显示位置”的规则能否通过反事实呈现改变。

新的正式测试应覆盖正常/逆序/随机呈现、first/last最小对照和未见表达，先报正常工具链last成功，再报配对规则正确率。SQL和其他任务保留小型副作用集合。只需要三个新B训练分支；原A不重训。

SQL另设单因素组合约束经验实验：同schema、同实体，单条改变WHERE、LIMIT或tie要求的相邻任务对，核验每条条件改变时生成SQL也作对应改变。暂不把它与File新干预合并成Combined组；先确认各自机制是否奏效，避免重新把多个变化揉成一个经验包。

若反事实经验能改善未见题，再接回收益分配器。此时收益信号使用真正的任务/约束成功变化，NLL作为辅助解释。完整算法的时间和计算预算应包含诊断探针成本。

## 7. 执行评价、成本与证据范围

本轮用已训练模型完成新的机制干预，新增优化更新0次。三种子均使用相同冻结条件，逐条落盘可恢复；六个模型的LoRA参数内存哈希前后相同，磁盘adapter及冻结输入哈希核验通过。

```json
{json.dumps(s['costs'],ensure_ascii=False,indent=2)}
```

统计单位是3个训练种子、6个配对文件、3类SQL实例；244条输出和272次调用不是244个独立复本。本轮定位局部机制，不估计大规模泛化效应。结构化表达是一个新的输入格式，逆序观察是人为干预，两者的结果各自对应具体条件。

实验设计技能沿用配对、分块和避免伪重复原则。参考：Kassis等（2026），Scientific Agent Skills，https://doi.org/10.48550/arXiv.2609.00065 。本轮结论的数据来源是上述本地实际运行。

## 产物与复现

- 实验前协议：P81_PREREG_20261116_ZH.md。
- 冻结数据与输入哈希：data_ext_p81_diagnosis_20261116/manifest.json。
- 逐题结果与汇总：runs_ext_p81_diagnosis_20261116/seed*.jsonl、summary.json。
- SQL追加CPU诊断：sql_stress.json；旧输出分类：p8_detailed_errors.json。
- 实验代码：fac_tinyagent/p81_diagnosis_20261116.py；语义oracle：p81_semantics.py。
- 重新CPU汇总：scripts/analyze_p81.py、p81_sql_stress.py、report_p81.py。无需重新跑GPU。
'''
    report=ROOT/'EXT_REPORT_20261116_p81_diagnosis_ZH.md';report.write_text(lines,encoding='utf-8')
    handover=ROOT/'EXT_HANDOVER_20261116_p81_diagnosis_ZH.md'
    handover.write_text(f'# P8.1交接\n\n完成：{now}。3种子，6模型终点，244条结果、272次生成，0更新。\n\n报告：EXT_REPORT_20261116_p81_diagnosis_ZH.md。核心算法：P81_CORE_ALGORITHM_20261116_ZH.md。结果：runs_ext_p81_diagnosis_20261116/summary.json。\n\n后续优先File呈现不变性单因素实验，复用P8 Decision对照，只新增3个训练分支；SQL组合约束干预单独验证。本轮未开展新训练。\n',encoding='utf-8')
    paths=[p for p in RUN.glob('*.json*') if p.name!='final_manifest.json']+[report,handover,ROOT/'P81_CORE_ALGORITHM_20261116_ZH.md',Path(__file__),ROOT/'scripts/analyze_p81.py',ROOT/'scripts/p81_sql_stress.py',ROOT/'scripts/p81_archived_breakdown.py']
    write_json(RUN/'final_manifest.json',{'complete':True,'created':now,'frozen_inputs_verified':True,'files':{str(p.relative_to(ROOT)):sha256_file(p) for p in paths}})
    print(report);print('\n'.join(ft));print('\n'.join(st));print(json.dumps(agg))
if __name__=='__main__':main()
