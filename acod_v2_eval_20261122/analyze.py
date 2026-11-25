"""Frozen v2 response-table replay and scorer. No new queries or behavioral rules."""
import collections,statistics
from lock_protocol import *
from core import behavior_observation,strict_score,initial_state,update,diagnosis,prediction_set,next_query,RULES
RUN=HERE/'results'

def self_test():
    # Integration checks use previously exposed development inputs and synthetic rule outputs only.
    cases=load_public(V2/'data/development/public/cases.jsonl');tests=0
    for c in cases:
        for rule in RULES:
            for policy in ['fixed','random','gbs_gini','ig_per_byte_cost']:
                s=initial_state(c);s=update(s,c,'original',canonical({'answer':predict(rule,c['views']['original'],c['contract']['intent'])}))
                for k in range(4):
                    v=next_query(s,c,policy,seed=17,cost=selector_costs(c));assert v in POOL
                    s=update(s,c,v,canonical({'answer':predict(rule,c['views'][v],c['contract']['intent'])}))
                assert canonical(predict(rule,c['views']['reserved'],c['contract']['intent'])) in prediction_set(s,c);tests+=1
    print(json.dumps({'integration_simulator_checks':tests,'passed':tests,'failed':0,'natural_generations':0},ensure_ascii=False))

def main():
    lock=verify();assert (RUN/'COMPLETE.json').exists(),'No analysis before bounded collection completes'
    data=rows(RUN/'responses.jsonl');assert len(data)==224
    cases=load_public(V2/'data/heldout/public/cases.jsonl');cm={c['case_id']:c for c in cases}
    # Gold/groups are opened only in the scorer after the complete fixed response table exists.
    gm={x['case_id']:x for x in rows(V2/'data/heldout/scorer_only/gold.jsonl')}
    meta={x['case_id']:x for x in rows(V2/'data/scorer_only/groups.jsonl') if x['split']=='heldout'}
    idx={(r['seed'],r['case_id'],r['view']):r for r in data};assert len(idx)==224
    SR=RUN/'scorer_only';SR.mkdir(exist_ok=True)
    score=[];scoreidx={}
    for r in data:
        c=cm[r['case_id']];v=c['views'][r['view']]
        sc=strict_score(r['raw'],c['contract']['output_schema'],gm[r['case_id']]['answers'][r['view']])
        ob=behavior_observation(r['raw'],v['rows'])
        item={**r,'strict_score':sc,'behavior':ob,'family':meta[r['case_id']]['family'],'fixture_id':meta[r['case_id']]['fixture_id'],'stratum':meta[r['case_id']]['stratum']}
        score.append(item);scoreidx[(r['seed'],r['case_id'],r['view'])]=item
    with (SR/'layered_records.jsonl').open('x',encoding='utf-8') as f:
        for r in score:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    full=[];traces=[];analysis_start=time.perf_counter()
    for identity in lock['models']:
        seed=identity['seed']
        for c in cases:
            cid=c['case_id'];info=meta[cid];reserved=scoreidx[(seed,cid,'reserved')]['behavior']
            s=initial_state(c)
            for v in ('original',*POOL):s=update(s,c,v,idx[(seed,cid,v)]['raw'])
            ds=diagnosis(s);pred=prediction_set(s,c);parsed=reserved['update_value_available']
            covered=bool(parsed and canonical(reserved['update_value']) in pred)
            fit=bool(s['classes'] and not s['unusable'])
            full.append({'seed':seed,'case_id':cid,'family':info['family'],'fixture_id':info['fixture_id'],'stratum':info['stratum'],'diagnosis':ds,'compatible_classes':s['classes'],'prediction_values':[json.loads(x) for x in pred],'reserved_behavior_parsed':parsed,'reserved_covered':covered,'fits_all_query_pool':fit,'reserved_breaks_previously_fitting_library':bool(fit and parsed and not covered),'reserved_unparsed_after_fit':bool(fit and not parsed),'correct_text_combination_remaining':any(('coordinate_intent','text','native') in cl['members'] for cl in s['classes'])})
            for policy in lock['policies']:
                for rep in (lock['random_seeds'] if policy=='random' else [0]):
                    start=time.perf_counter();state=update(initial_state(c),c,'original',idx[(seed,cid,'original')]['raw']);diagnostic_s=time.perf_counter()-start
                    selector_s=0;queried=[]
                    for b in range(1,5):
                        start=time.perf_counter();view=next_query(state,c,policy,seed=rep,cost=selector_costs(c));selector_s+=time.perf_counter()-start
                        assert view in POOL and view not in queried
                        start=time.perf_counter();state=update(state,c,view,idx[(seed,cid,view)]['raw']);diagnostic_s+=time.perf_counter()-start;queried.append(view)
                        if b not in lock['additional_query_budgets']:continue
                        dg=diagnosis(state);ps=prediction_set(state,c)
                        cov=bool(parsed and canonical(reserved['update_value']) in ps)
                        uu=[idx[(seed,cid,x)]['usage'] for x in ['original',*queried]]
                        traces.append({'seed':seed,'case_id':cid,'family':info['family'],'fixture_id':info['fixture_id'],'policy':policy,'replicate':rep,'additional_queries':b,'queried':list(queried),'observed_views':list(state['observed']),'unusable_views':list(state['unusable']),'diagnosis':dg,'support_class_count':dg['class_count'],'support_rule_count':dg['rule_count'],'prediction_size':len(ps),'predicted_values':[json.loads(x) for x in ps],'reserved_behavior_parsed':parsed,'reserved_covered':cov,'unknown':not state['classes'],'parse_insufficient':bool(state['unusable']),'refusal':not state['classes'] or bool(state['unusable']),'single_value_prediction':len(ps)==1,'wrong_specificity':bool(len(ps)==1 and parsed and not cov),'unparsed_reserved_with_single_prediction':len(ps)==1 and not parsed,'calls_with_original':len(uu),'input_tokens_with_original':sum(u['input_tokens'] for u in uu),'output_tokens_with_original':sum(u['output_tokens'] for u in uu),'total_tokens_with_original':sum(u['total_tokens'] for u in uu),'generation_seconds_with_original':sum(u['generation_seconds'] for u in uu),'selector_seconds':selector_s,'update_seconds':diagnostic_s,'weight':0.05 if policy=='random' else 1})
    save(SR/'full_pool_consistency.json',full)
    with (SR/'replay_traces.jsonl').open('x',encoding='utf-8') as f:
        for r in traces:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    group=collections.defaultdict(list)
    for r in traces:
        for family in ['ALL',r['family']]:group[(r['seed'],family,r['policy'],r['additional_queries'])].append(r)
    curves=[]
    for (seed,family,policy,b),rr in sorted(group.items()):
        den=sum(r['weight'] for r in rr)
        def avg(name):return sum(r['weight']*r[name] for r in rr)/den
        parse=sum(r['weight']*r['reserved_behavior_parsed'] for r in rr);single=sum(r['weight']*r['single_value_prediction'] for r in rr)
        curves.append({'seed':seed,'family':family,'policy':policy,'additional_queries':b,'weighted_task_count':round(den,8),'coverage_overall':avg('reserved_covered'),'coverage_when_reserved_parsed':sum(r['weight']*r['reserved_covered'] for r in rr)/parse if parse else None,'reserved_parse_rate':avg('reserved_behavior_parsed'),'mean_prediction_width':avg('prediction_size'),'mean_compatible_classes':avg('support_class_count'),'mean_compatible_rules':avg('support_rule_count'),'unknown_rate':avg('unknown'),'parse_insufficient_rate':avg('parse_insufficient'),'refusal_rate':avg('refusal'),'single_prediction_rate':avg('single_value_prediction'),'wrong_specificity_over_single_predictions':sum(r['weight']*r['wrong_specificity'] for r in rr)/single if single else None,'unparsed_reserved_in_single_predictions':sum(r['weight']*r['unparsed_reserved_with_single_prediction'] for r in rr),'mean_calls_with_original':avg('calls_with_original'),'mean_tokens_with_original':avg('total_tokens_with_original'),'mean_generation_seconds_with_original':avg('generation_seconds_with_original'),'mean_selector_seconds':avg('selector_seconds'),'mean_update_seconds':avg('update_seconds')})
    save(RUN/'budget_curves.json',curves)
    det={(r['seed'],r['case_id'],r['additional_queries'],r['policy']):r for r in traces if r['policy']!='random'}
    same=[]
    for seed in [m['seed'] for m in lock['models']]:
        for b in [1,2,4]:
            n=sum(det[(seed,c['case_id'],b,'gbs_gini')]['queried']==det[(seed,c['case_id'],b,'ig_per_byte_cost')]['queried'] for c in cases)
            same.append({'seed':seed,'budget':b,'same_query_sequences':n,'tasks':16})
    save(RUN/'baseline_path_equivalence.json',same)
    strict=[];consistency=[]
    for seed in [m['seed'] for m in lock['models']]:
        for family in ['ALL',*sorted({m['family'] for m in meta.values()})]:
            rr=[r for r in score if r['seed']==seed and (family=='ALL' or r['family']==family)]
            orig=[r for r in rr if r['view']=='original'];res=[r for r in rr if r['view']=='reserved']
            strict.append({'seed':seed,'family':family,'original_correct':sum(r['strict_score']['strict_correct'] for r in orig),'original_n':len(orig),'reserved_correct':sum(r['strict_score']['strict_correct'] for r in res),'reserved_n':len(res),'all_views_correct':sum(r['strict_score']['strict_correct'] for r in rr),'all_views_n':len(rr),'syntax_valid':sum(r['strict_score']['syntax_valid'] for r in rr),'schema_valid':sum(r['strict_score']['output_schema_valid'] for r in rr),'behavior_value_available':sum(r['behavior']['update_value_available'] for r in rr),'wrapper_recoveries':sum(any(e['source']=='recovered_wrapper' for e in r['behavior']['envelopes']) for r in rr),'behavior_ambiguous':sum(r['behavior']['ambiguous'] for r in rr)})
            ff=[r for r in full if r['seed']==seed and (family=='ALL' or r['family']==family)]
            consistency.append({'seed':seed,'family':family,'n':len(ff),'unknown_after_all_pool':sum(not r['diagnosis']['class_count'] for r in ff),'parse_insufficient_after_all_pool':sum(bool(r['diagnosis']['unusable_observations']) for r in ff),'fits_all_pool':sum(r['fits_all_query_pool'] for r in ff),'reserved_breaks_fitting_library':sum(r['reserved_breaks_previously_fitting_library'] for r in ff),'reserved_unparsed_after_fit':sum(r['reserved_unparsed_after_fit'] for r in ff),'reserved_covered':sum(r['reserved_covered'] for r in ff)})
    # Factorial gate is fixed by public rows before any responses were collected.
    pairs=[p['pair_inspection'] for p in lock['plans']]
    complete=[p for p in pairs if p['exact_two_factor_pairs_for_reserved']]
    interaction={'source':'pre-response PROTOCOL_LOCK public-input structural test','complete_case_quads':len(complete),'strict_paired_interaction_estimate':None,'single_normal_combo_fail_count':None,'reason':'No exact paired quad: line singleton includes display rotation, while reserved applies display reversal in addition to value+line. No reverse+value-only view exists. Content equality is insufficient to isolate display-dependent behavior.','not_statistical_interaction_or_hidden_cause':True,'no_extra_queries_generated':True}
    assert not complete,'Unexpected complete pair requires predeclared extension; do not silently change scoring'
    save(RUN/'interaction_assessment.json',interaction)
    # Paired intents and checkpoints share fixtures; report their raw cluster records, no IID inference.
    cluster=collections.defaultdict(list)
    for r in score:cluster[(r['seed'],r['fixture_id'],r['family'])].append(r)
    clusters=[{'seed':seed,'fixture_id':fid,'family':family,'cases':len({r['case_id'] for r in rr}),'views':len(rr),'strict_correct':sum(r['strict_score']['strict_correct'] for r in rr),'all_views_strictly_correct':all(r['strict_score']['strict_correct'] for r in rr)} for (seed,fid,family),rr in sorted(cluster.items())]
    save(SR/'fixture_clusters.json',clusters)
    usage={k:sum(r['usage'][k] for r in data) for k in ['inference_calls','input_tokens','output_tokens','total_tokens','generation_seconds']}
    events=rows(RUN/'events.jsonl');guards=rows(LOG/'guard.jsonl') if (LOG:=RUN/'logs').exists() else []
    end=next(r for r in reversed(events) if r['event']=='SUPERVISOR_END');start=next(r for r in events if r['event']=='SUPERVISOR_START')
    summary={'analyzed':now(),'started':start['time'],'finished':end['time'],'supervisor_rc':end['rc'],'wall_seconds':end['elapsed_seconds'],'generation_usage':usage,'attempts':len(rows(RUN/'calls_started.jsonl')),'completed':len(data),'failed_or_incomplete':len(rows(RUN/'calls_started.jsonl'))-len(data),'model_receipts':rows(RUN/'model_receipts.jsonl'),'strict_layers':strict,'full_pool_consistency':consistency,'baseline_paths':same,'interaction':interaction,'guard_checks':len(guards),'sampled_power_W_range':[min(float(g['gpu_actual'][1]) for g in guards),max(float(g['gpu_actual'][1]) for g in guards)],'max_temperature_C':max(float(g['gpu_actual'][3]) for g in guards),'analysis_wall_seconds':time.perf_counter()-analysis_start,'exposure':'v2 heldout now exposed; cannot be reused as an independent final v3 test','training_steps':0,'MDCS_implemented':False,'new_rules_added':0,'new_queries_synthesized':0,'fixed_response_table_replay':True,'limits':['8 heldout fixtures,2 construction families,2 checkpoints of same model family; not IID 224 tasks','No complete paired interaction design in frozen views','Closed 24-rule mismatch does not identify conditional switching, noise or hidden cause','Single B1 greedy response per view; no stochastic stability claims','Strict output and behavior parsing remain separate; no normalization-based strict score inflation','No power/significance claim or small-sample elimination of a direction']}
    save(RUN/'summary.json',summary)
    lines=['# ACOD v2 首次保留集真实推理报告',f'分析时间：{now()}（Asia/Shanghai）。',f"实际运行：{summary['started']}—{summary['finished']}；rc={summary['supervisor_rc']}；墙钟{summary['wall_seconds']:.3f}秒。",'', '## 范围与成本',f"- 按原v2预注册仅16保留题×7视图×2 checkpoint=224；开发8题未跑。尝试{summary['attempts']}、完成{summary['completed']}、失败/未完成{summary['failed_or_incomplete']}。",f"- Qwen3-0.6B P9 ordinary seed20261108/20261109；B1 greedy/use_cache=False/max_new_tokens128；0训练，全部参数digest前后一致。",f"- 输入{usage['input_tokens']}、输出{usage['output_tokens']}，合计{usage['total_tokens']} tokens；生成累计{usage['generation_seconds']:.3f}秒。模型加载、守卫和hash开销在墙钟内，不冒充生成时间。",'- 固定消息来自原v2 interfaces.model_messages；不含gold/分组/行为规则/未来response。全表仅采集一次，以下为离线策略重放，不是各策略独立在线生成。','', '## 四层严格分开','|seed|组别|original严格正确|reserved严格正确|全视图严格正确|语法合格|schema合格|行为可解析|','|---|---|---|---|---|---|---|---|']
    for r in strict:lines.append(f"|{r['seed']}|{r['family']}|{r['original_correct']}/{r['original_n']}|{r['reserved_correct']}/{r['reserved_n']}|{r['all_views_correct']}/{r['all_views_n']}|{r['syntax_valid']}|{r['schema_valid']}|{r['behavior_value_available']}|")
    lines+=['','## 等预算预测：ALL组','original是共同付费观测；追加预算1/2/4。预测覆盖、集合宽度与拒判必须合看；random为20固定seed重放均值而非独立样本。','|seed|策略|追加查询|coverage|预测宽度|相容类数|unknown|拒判|错误具体化率|平均tokens含original|','|---|---|---|---|---|---|---|---|---|---|']
    for r in curves:
        if r['family']!='ALL':continue
        err=r['wrong_specificity_over_single_predictions'];ee='NA' if err is None else f'{err:.3f}'
        lines.append(f"|{r['seed']}|{r['policy']}|{r['additional_queries']}|{r['coverage_overall']:.3f}|{r['mean_prediction_width']:.3f}|{r['mean_compatible_classes']:.3f}|{r['unknown_rate']:.3f}|{r['refusal_rate']:.3f}|{ee}|{r['mean_tokens_with_original']:.1f}|")
    lines+=['','## 固定库一致性与组合命题','|seed|组别|全部可查询池可拟合|之后reserved不在预测集合|全池unknown|','|---|---|---|---|---|']
    for r in consistency:lines.append(f"|{r['seed']}|{r['family']}|{r['fits_all_pool']}/{r['n']}|{r['reserved_breaks_fitting_library']}|{r['unknown_after_all_pool']}/{r['n']}|")
    lines+=['','严格配对交互：不可估计，不是“发现0例”。预先CPU代数核查显示0个完整四元组：line单项=rotate∘L，reserved=reverse∘L∘V；V和line单项的组合显示顺序是rotate，不是reverse。reverse+value单项组合视图也缺失。故不能把单项正确但reserved错直接叫二因素交互，本次未新增查询补齐。','上表“全池可拟合但reserved失配”仅是有限行为库的跨视图预测失配；可能有未覆盖编码/任务理解/不稳定等，不能据一次greedy推出条件触发规则。正确组合输出应按各view独立gold判断，不按原字符串恒等。','', '## MDCS判断与限制','当前完成的是v2检验，不是MDCS/v3。尚未建立“真实条件切换触发机制”，也没有公平的同扩展候选空间合成算法比较。固定24规则的可识别性结构检查已在PROTOCOL_LOCK记录；它不能证明未建模条件规则不存在。','用户举例若原始行号升序，reverse后显示第一条仍是最大line记录；此时“按原坐标last”与触发后“display-first”输出相同，原例中的差异表不能直接成立，需要另有真正可分的构造。本次不为修例新增数据。','“最小见证”未来必须先限定合法编辑空间、编辑/调用/长度成本及最优性范围；枚举或贪心不自动是全域最小。无论本轮有无优势/交互，都不据小样本淘汰路线。','8个基础fixture、2构建族，first/last和checkpoint相关；不将224视图当224独立任务，不报告显著性或现实OOD。v2保留输出本次首次使用后全部视为已暴露；任何v3要另有独立最终集。','', '## 文件','PROTOCOL_LOCK.json：未见响应前锁；results/responses.jsonl：逐条raw及实际usage；results/scorer_only/layered_records.jsonl：分层评分；budget_curves.json：完整成本曲线；fixture_clusters.json：基础fixture簇；model_receipts.jsonl：冻结参数；guard.jsonl：安全监控。']
    (HERE/'REPORT_ZH.md').open('x',encoding='utf-8').write('\n'.join(lines)+'\n')
    hand=['# v2真实推理交接',f'时间：{now()}（Asia/Shanghai）',f'原机目录：{HERE}',f"状态：224完成，rc={summary['supervisor_rc']}，已停止；没有MDCS或额外查询任务。",'旧round1、v2冻结包和受保护历史资产核验不变。模型只加载两份既有checkpoint，不训练、不push、不付费API。','本次首次打开v2保留自然响应；未来不可称同一批为独立v3测试。','严格交互不可估计，因为没有完整因子配对；不能把未检验写成负面证据。','基线是固定候选表离线重放；原始采集成本与每策略成本已分列。GBS/IG实际路径同异见baseline_path_equivalence.json。','若需后续MDCS，先基于本报告判断研究问题，再另行授权、独立数据与同候选权限强基线；本目录不自动继续。']
    (HERE/'HANDOVER_ZH.md').open('x',encoding='utf-8').write('\n'.join(hand)+'\n')
    verify();files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    save(HERE/'final_hashes.json',{'time':now(),'hashes':{str(p.relative_to(HERE)):sha(p) for p in files},'all_protected_hashes_unchanged':True,'protocol_lock_sha256':sha(HERE/'PROTOCOL_LOCK.json')})
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='self_test':self_test()
    else:main()