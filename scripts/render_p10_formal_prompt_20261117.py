"""Render final Chinese reports from complete formal summary only; no model invocation."""
import datetime,hashlib,json,os
from pathlib import Path
from fac_tinyagent.p10_formal_prompt_20261117 import inspect
R=Path.cwd();Q=R/'runs_ext_p10_formal_prompt_20261117';J=lambda p:json.loads(p.read_text(encoding='utf-8'))
def main():
 s=J(Q/'summary.json');assert s['complete']and J(Q/'supervisor_end.json')['rc']==0;now=datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z');final=inspect({os.getpid()})
 with(Q/'safety_final_CPU.json').open('x',encoding='utf-8')as f:json.dump(final,f,ensure_ascii=False,indent=2)
 t=s['totals'];g=s['group_metrics'];cost=s['costs'];complete=s['completion'];safe=s['safety'];normal=t['normal_both'];first=t['normal_first'];last=t['normal_last'];rev=t['reversed_both'];success=s['preregistered_practical_success'];status='通过'if success else'未通过'
 headline=f"正常E2E Joint {normal['original']}/{normal['n']}→{normal['clarified']}/{normal['n']}（{normal['delta_pp']:+.2f}个百分点）；first {first['original']}/36→{first['clarified']}/36、last {last['original']}/36→{last['clarified']}/36。预注册实用工程门槛{status}。"
 lines=['|seed/提示|正常first Joint|正常last Joint|正常宏平均|逆序first答案|逆序last答案|正常两意图联合|all4混合诊断|','|---|---:|---:|---:|---:|---:|---:|---:|']
 for row in s['per_seed']:
  seed=row['seed']
  for p,label in [('original','原提示'),('clarified','冻结澄清')]:
   np=next(x for x in g['normal_pair']['per_seed']if x['seed']==seed);a4=next(x for x in g['all4']['per_seed']if x['seed']==seed)
   lines.append(f"|{seed}/{label}|{row['normal_first'][p]}/12|{row['normal_last'][p]}/12|{100*row['normal_both'][p]/24:.2f}%|{row['reversed_first'][p]}/12|{row['reversed_last'][p]}/12|{np[p]}/12|{a4[p]}/12|")
 table='\n'.join(lines)
 paired=['|指标|原→澄清|差值pp|均对|原对新错（损害）|原错新对（改善）|均错|','|---|---:|---:|---:|---:|---:|---:|']
 for k,label in [('normal_first','正常first Joint'),('normal_last','正常last Joint'),('normal_both','正常宏平均Joint'),('reversed_first','逆序oracle first'),('reversed_last','逆序oracle last')]:
  a=t[k];p=a['paired'];paired.append(f"|{label}|{a['original']}/{a['n']}→{a['clarified']}/{a['n']}|{a['delta_pp']:+.2f}|{p.get('both_correct',0)}|{p.get('original_only_harm',0)}|{p.get('clarified_only_gain',0)}|{p.get('both_wrong',0)}|")
 strata=['|分层|正常first（原→新）|正常last（原→新）|正常宏平均差pp|逆序first（原→新）|逆序last（原→新）|','|---|---:|---:|---:|---:|---:|']
 for a in s['strata']:
  v=[]
  for k in ['normal_first','normal_last','reversed_first','reversed_last']:
   b=a[k];v.append(f"{b['original']}/{b['n']}→{b['clarified']}/{b['n']}")
  strata.append(f"|{a['field']}={a['value']}|{v[0]}|{v[1]}|{a['normal_both']['delta_pp']:+.2f}|{v[2]}|{v[3]}|")
 costs=['|实际新增部分|生成数|输入tokens|输出tokens|总tokens|生成秒|','|---|---:|---:|---:|---:|---:|']
 for k,label in [('shared_normal_tools','两提示共享实际正常工具前缀'),('normal_original_answers','正常原终答'),('normal_clarified_answers','正常澄清终答'),('reversed_original_answers','逆序原终答'),('reversed_clarified_answers','逆序澄清终答'),('actual_total','实际总计，不重复计共享前缀')]:
  c=cost[k];costs.append(f"|{label}|{c['inference_calls']}|{c['input_tokens']}|{c['output_tokens']}|{c['total_tokens']}|{c['generation_seconds']:.2f}|")
 unit=[]
 for k,label in [('normal_both','正常'),('reversed_both','逆序oracle')]:
  a=t[k];u=a['identity_transitions'];unit.append(f"- {label}：身份正确{a['identity_correct_original']}/{a['n']}→{a['identity_correct_clarified']}/{a['n']}；身份改善{u['identity_gains']}、损害{u['identity_losses']}；保持正确身份的纯单位严格修复{u['pure_unit_strict_repairs']}。单位原分布{json.dumps(a['units']['original'],ensure_ascii=False)}，澄清后{json.dumps(a['units']['clarified'],ensure_ascii=False)}。")
 future=('正式正常净收益为正，说明固定字段澄清在本未见卷有工程迁移收益；这不是训练收益，更不保证每种措辞/种子都安全。'if normal['delta_pp']>0 else'正式正常净收益为负，且三个种子宏平均全部为负，开发集的单位修复收益没有迁移；不应推广本句澄清或设为默认，更不启动字段绑定SFT。正式原提示144条终答已全部为完整text，两提示共288条终答均为完整text，单位错误为0、纯单位严格修复为0，本轮损益全部是选择项变化。正常last的6例损害来自同2个基础文件在3种子重复，不是6个独立文件。正常last复制显示首项11/36→18/36，逆序last复制显示首项10/36→20/36；结合逆序first2/36→0/36及all4仍0，更符合显示位置偏好被重新分配，不能称原坐标规则改善。未来规范输出契约只能作为共同测量控制，不等于沿用这句已失败提示。真正尚待独立研究的是意图/表达与原文件坐标的绑定；若日后测双视图，必须新独立训练/dev/正式卷、所有臂相同表达与输出契约，只改视图覆盖，不能按本正式卷失败措辞/数量补训练或选超参。不得再换提示或用本正式卷追分。')
 body=f'''# P10固定File输出契约：一次未见正式验证（FINAL）

写作：{now}，北京时间UTC+8。独立新报告，不覆盖任何P9/GPT/dev报告。实验仅固定ordinary三适配器、两个预先冻结提示；没有任何新训练。

## 1. 总结与预注册判定

{headline}

first原对新错严格损害{s['first_strict_harms']}例，first身份损害{s['first_identity_losses']}例，两者必须分开。逆序oracle严格{rev['original']}/{rev['n']}→{rev['clarified']}/{rev['n']}；all4为{g['all4']['original']}/36→{g['all4']['clarified']}/36，改善{g['all4']['gains']}、损害{g['all4']['harms']}。all4含正常E2E与逆序oracle两种链路，绝不是四条件E2E。

门槛在开封前冻结：正常Joint宏平均至少+10个百分点，≥2/3种子方向正，正常first总体Joint不降；任何原本严格正确的first变错都披露且不得称无损。本轮判定{status}，不事后换门槛；严格损害为0也不等于选择身份一定无损。没有显著性结论，基础文件仅12个、训练复本3个。

{future} 位置推理需另外看逆序first/last和all4，不能拿正常输出text增益替代规则学习证据。

## 2. 数据来源、分层及开发选择透明披露

正式卷data_ext_p10_twoview_cpu_20261117/holdout.jsonl于北京时间15:41:35冻结，SHA256=9277e44d15fce68c1844722bb599200e9e21452db7a596000060d330e62ecb3d，始终未变。先前只做过gold工具/预算CPU验收，不是模型输出，也没有把正式gold用于诊断或提示选择。启动前对既有runs的3131个jsonl查正式ID，未发现既有正式模型输出/同配置缓存。可核实的既有72dev/48澄清runner都只加载dev.jsonl或其缓存。

路径/marker/确切问题字符串训练、dev、正式互斥；但不能声称所有措辞结构和匹配数完全互斥。原卷是分层设计：4训练风格新实体文件、4edge新改写、4relation新改写；每组2/3/4/5匹配各1文件。训练/dev只有2/3/4，正式5是OOD数量，其余为ID数量。未重新造卷或按gold筛题，不能把全卷统称措辞/数量全OOD。

提示选择过程：先P10独立开发72次（24工具+48终答），发现正常选择身份24/24而严格3/24，主要输出行号；再用唯一固定澄清做48新开发终答，正常严格22/24但身份22/24，逆序严格3/24且all4=0，无损假设失败。不是在多条提示中搜索正式最优。这里的P10开发72次与P9早先72诊断不同。本次正式一旦开封，不再改提示/方法或把它转成开发卷。

原问题complete matching line与gold支持完整文本，未发现错金标；但系统/工具未显式区分line与text字段的输出投影，属于契约说明不足的风险，不宜把所有单位错误叫选择能力缺口。澄清句、位置、评分与开发完全相同，全文见预注册P10_FORMAL_PROMPT_PREREG_20261117_ZH.md。不含目标答案/行号/最大最小规则，也不接受行号替代text。

## 3. 最小完整生成与真实端到端接口

全部360/360调用、288/288终答记录完成：72次正常工具生成及真实执行，每个新执行前缀分叉原/澄清两终答（144次）；逆序oracle正确调用/逆序观察下两提示终答144次。工具选择轮输入相同、greedy、干预仅发生于工具结果后，故共享一次新实际前缀是合法配对，也避免72次无意义重复；不是各自完整独立重跑的432次，更未跑旧576计划。

正常指标为原工具选择→真实沙箱执行→各自最终答案的严格B1 Joint。共享新执行不是复用开发答案，不能与先前dev48的缓存链路混淆。逆序始终是oracle answer-only，没测其工具选择。greedy、max_new_tokens128、batch1、同评分器/gold/权重。每个澄清答案比对应原提示实际多46输入token，共144×46=6,624；没有参数更新、答案映射或扩大格点。

工具/参数/执行观察成功数：{s['pipeline']['tool_correct']}/72、{s['pipeline']['arguments_correct']}/72、{s['pipeline']['execution_success']}/72。工具失败不会因终答碰巧正确而成为Joint成功。

## 4. 完整三种子及配对损益

{table}

正常宏平均先均衡first/last，再三种子平均；由于各格题数相同，也等于正常总成功/72。

{chr(10).join(paired)}

正常两意图联合{g['normal_pair']['original']}/36→{g['normal_pair']['clarified']}/36；逆序两意图联合{g['reversed_pair']['original']}/36→{g['reversed_pair']['clarified']}/36。逐文件all4转移和每seed分组见case_pairs_CPU.json与summary.json，不把不同提示/链路拼一个虚构总分。

## 5. 单位与身份解释（后验，不重计严格分）

{chr(10).join(unit)}

身份解释沿用既有规则：精确匹配工具返回完整text，否则唯一原行号（允许line/line:前缀），再唯一行内数值；不确定则不解析。只解释选择项及显示位置，不用于推理、补全答案或修改严格评分。纯单位修复、选择改善和损害不可合并归因。逐条身份与输出单位见identity_unit_explanation_CPU.json，显示首/末/中分布见summary.json。

## 6. 预定分层（小样本，不反向选训练）

{chr(10).join(strata)}

每个措辞×匹配数只有1个基础文件；不同层不是同文件只换措辞的纯因果对照。三个种子重复同12个文件，不能把种子×条件当新独立实体或用本分层再挑训练变换。

## 7. 实际计费、时长与安全

{chr(10).join(costs)}

worker实测{complete['elapsed_seconds']:.2f}秒（含模型加载/执行/保存，不含worker前置import），完成{complete['finished']}；监督器结束{J(Q/'supervisor_end.json')['finished']}。Windows持久宿主48528，监督器16:31:02启动；首文件10次真实QLoRA/工具执行/落盘接口关卡16:32:20通过，再放行余350次，接口关卡不是提分门槛。三模型各120调用，最高PyTorch allocated峰值{max(x['peak_gpu_GB']for x in s['model_receipts']):.3f} GiB，不等于全进程/整卡显存。

启动前无Apex/STOP/其他GPU和项目任务，明确UTF8 Windows进程JSON；持续{safe['checks']}次守卫全部安全，观察功率上限{safe['min_power']:.2f}–{safe['max_power']:.2f}W，均≥60W，未调功率。结束只读预检状态详见safety_final_CPU.json，时间{final['time']}，GPU计算进程数{len(final['compute'])}。没有清STOP、终止GPT或自动追加运行。adapter文件和live LoRA前后哈希一致，旧12+34冻结输入及本阶段receipt哈希均通过。最终新增文件清单见final_manifest.json。

## 8. P9核心结论、保持缺口和研究含义

P9完整9/9模型同旧卷：P8正常last16/36（44.44%）、ordinary31/36（86.11%）、CF14/36（38.89%）。ordinary−P8三种子方向一致，但只证明额外任务经验适应；CF−ordinary均值−47.22个百分点、三种子全负。CF逆序改善而正常损害、all4均0，说明条件间错误重分配，不是规则迁移成功。P9六训练分支共108更新，每臂53,734输入/7,486监督tokens；本轮没有新增任何训练。旧卷分数不与本新卷相减。

P9 Calendar旧保持3/12→ordinary/CF均1/12，工具/参数/执行均12/12，退在list_locations数组输出（标量/null、去重/排序）；共有背景Calendar8条全count_date，整个72条训练终答全标量，缺数组/列表算子覆盖。这是合理解释而非已隔离因果。本轮权重不变且澄清仅File，故按授权不重跑不变Calendar，绝不声称它已恢复。Python保持范围原来很小；SQL仅list_tables不代表复杂filter_cmp_top，复杂SQL保持尚未解决且本轮不做无关新增评测，原本不会的任务叫能力缺口而非遗忘。

此处是输出接口工程验证，不是抗遗忘/课程/偏好优化或新论文算法。若考虑后续位置推理研究，先把明确输出契约作为所有对照共同基础，在另立独立训练、开发和正式卷上检验普通重复视图vs正常/逆序双视图，严格同起点/预算、同时保护first和Calendar list_locations等真实输出算子。研究假设来自已看的dev错误类别，不把本正式实例、模板分层或分数回灌训练/调参。当前不新训字段绑定SFT、不叠课程/SimPO、不自动继续。

## 9. 证据入口

本阶段runs_ext_p10_formal_prompt_20261117/：runtime_manifest.json、provenance.json、launch_preflight.json、shared_tools.jsonl、records.jsonl、calls_started/completed.jsonl、e2e_gate.json、model_receipts.json、COMPLETE.json、supervisor_end.json、summary.json、case_pairs_CPU.json、identity_unit_explanation_CPU.json、logs/guard.jsonl、safety_final_CPU.json、final_manifest.json。
预注册P10_FORMAL_PROMPT_PREREG_20261117_ZH.md；runner fac_tinyagent/p10_formal_prompt_20261117.py；CPU分析scripts/analyze_p10_formal_prompt_20261117.py。旧报告EXT_REPORT_20261117_p9_independent_final_ZH.md、EXT_REPORT_20261117_p10_dev72_ZH.md、EXT_REPORT_20261117_p10_unitclarify48_ZH.md均保留。交接EXT_HANDOVER_20261117_p10_formal_prompt_ZH.md。没有GPT消息或push。
'''
 hand=f'''# P10未见正式File提示配对验证交接（FINAL）

{now}，北京时间。详细报告EXT_REPORT_20261117_p10_formal_prompt_ZH.md。

{headline}
first严格原对新错{s['first_strict_harms']}例，身份损害{s['first_identity_losses']}例；逆序答案{rev['original']}/{rev['n']}→{rev['clarified']}/{rev['n']}；all4混合诊断{g['all4']['original']}/36→{g['all4']['clarified']}/36，不能叫四条件E2E。正常联合{g['normal_pair']['original']}/36→{g['normal_pair']['clarified']}/36。

{table}

最小360/360实际生成完成（72共享新实际工具+144正常终答+144逆序oracle终答），288唯一终答记录，无重复基线。只P9 ordinary三个固定模型、原提示vs唯一冻结字段澄清；0新训练，未评P8/CF或不变Calendar/复杂SQL，未跑旧576总队列。新成本输入{cost['actual_total']['input_tokens']}、输出{cost['actual_total']['output_tokens']}、总{cost['actual_total']['total_tokens']} tokens，生成{cost['actual_total']['generation_seconds']:.2f}秒，worker{complete['elapsed_seconds']:.2f}秒，完成{complete['finished']}，监督rc0。澄清每终答实际+46输入tokens，共6,624；共享成本只付一次。

正式冻结15:41:35早于dev选择；既有3131个runs jsonl无正式ID输出/缓存。旧gold CPU验收不是模型输出；训练/dev/正式实体和确切题目互斥，但训练风格4文件、改写8文件及2/3/4 ID数量、5 OOD数量必须区分，不要声称全卷完全分布隔离。开发过程：72独立dev调用后选择输出契约，48唯一提示澄清dev得正常22/24但身份损害2例、无损预注册失败；本正式提示从此未改。正式卷已一次开封，今后不得转开发/调参或换提示刷分。

{future} 这是工程提分检验，不是新训练/论文算法。以后如研究双视图，先统一输出契约，再使用全新独立训练/dev/正式卷做普通重复vs正常/逆序双视图，同起点/预算、first和旧技能算子保持；本轮不自动训练或继续诊断。

P9旧卷ordinary正常last86.11% vsP8 44.44%、CF38.89%，CF−ordinary三种子全负、all4全0；ordinary是任务适应而非抗遗忘方法证据。Calendar旧3/12→1/12为列表输出/去重排序问题，背景全count且72答案全标量有覆盖缺口；本File提示不推断其修复，复杂SQL也尚未解决。

持续{safe['checks']}次原守卫全安全，功率上限{safe['min_power']:.2f}–{safe['max_power']:.2f}W，未清STOP/停GPT/改功率；权重与冻结输入哈希不变。当前进程PID文件是历史回执，不是新训练队列。最终状态见safety_final_CPU.json。

原始与完整配对数据：runs_ext_p10_formal_prompt_20261117/summary.json、records.jsonl、shared_tools.jsonl、case_pairs_CPU.json、identity_unit_explanation_CPU.json、calls_*、COMPLETE.json、supervisor_end.json、model_receipts.json、runtime_manifest.json、final_manifest.json。新增报告/交接均未覆盖旧资产，未发GPT、未push。
'''
 for name,text in [('EXT_REPORT_20261117_p10_formal_prompt_ZH.md',body),('EXT_HANDOVER_20261117_p10_formal_prompt_ZH.md',hand)]:
  with(R/name).open('x',encoding='utf-8')as f:f.write(text)
 extra=['EXT_REPORT_20261117_p10_formal_prompt_ZH.md','EXT_HANDOVER_20261117_p10_formal_prompt_ZH.md','P10_FORMAL_PROMPT_PREREG_20261117_ZH.md','fac_tinyagent/p10_formal_prompt_20261117.py','scripts/analyze_p10_formal_prompt_20261117.py','scripts/render_p10_formal_prompt_20261117.py'];paths=[p for p in Q.rglob('*')if p.is_file()and p.name!='final_manifest.json']+[R/x for x in extra]
 manifest=dict(created=now,complete=True,hashes={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths})
 with(Q/'final_manifest.json').open('x',encoding='utf-8')as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
 print(json.dumps(dict(report=extra[0],handover=extra[1],headline=headline,first_strict_harms=s['first_strict_harms'],first_identity_losses=s['first_identity_losses'],all4=g['all4'],reverse_both=rev,cost=cost['actual_total'],final_safety=final,hashed_files=len(manifest['hashes'])),ensure_ascii=False,indent=2))
if __name__=='__main__':main()