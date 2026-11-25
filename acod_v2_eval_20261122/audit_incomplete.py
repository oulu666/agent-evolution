"""Transparent completeness-gated intermediate audit; locked full-table main is NOT run."""
import collections
from lock_protocol import *
from core import behavior_observation,strict_score,initial_state,update,diagnosis,prediction_set,next_query
RUN=HERE/'results'
def main():
    lock=verify();assert not (RUN/'COMPLETE.json').exists()
    assert read(RUN/'logs/STOP')['reason']=={'deadline_seconds':1500}
    data=rows(RUN/'responses.jsonl');starts=rows(RUN/'calls_started.jsonl');idx={(r['seed'],r['case_id'],r['view']):r for r in data};assert len(idx)==len(data)
    events=rows(RUN/'events.jsonl');end=next(e for e in reversed(events) if e['event']=='SUPERVISOR_END');assert end['rc']==75
    cases=load_public(V2/'data/heldout/public/cases.jsonl');cm={c['case_id']:c for c in cases};views=('original',*POOL,'reserved')
    gold={g['case_id']:g for g in rows(V2/'data/heldout/scorer_only/gold.jsonl')}
    meta={g['case_id']:g for g in rows(V2/'data/scorer_only/groups.jsonl') if g['split']=='heldout'}
    scored=[];scidx={}
    for r in data:
        c=cm[r['case_id']];v=c['views'][r['view']]
        ss=strict_score(r['raw'],c['contract']['output_schema'],gold[r['case_id']]['answers'][r['view']]);bo=behavior_observation(r['raw'],v['rows'])
        x={**r,'strict':ss,'behavior':bo,'meta':meta[r['case_id']],'at_output_cap':r['usage']['output_tokens']==128}
        scored.append(x);scidx[(r['seed'],r['case_id'],r['view'])]=x
    SR=RUN/'intermediate_scorer_only';SR.mkdir(exist_ok=True)
    with (SR/'layered_records.jsonl').open('x',encoding='utf-8') as f:
        for r in scored:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    eligible={m['seed']:[c for c in cases if all((m['seed'],c['case_id'],v) in idx for v in views)] for m in lock['models']}
    missing=[]
    for m in lock['models']:
        for c in cases:
            for v in views:
                if (m['seed'],c['case_id'],v) not in idx:
                    ident=f"{m['seed']}:{c['case_id']}:{v}"
                    missing.append({'id':ident,'seed':m['seed'],'case_id':c['case_id'],'view':v,'attempted':any(r['id']==ident for r in starts)})
    save(RUN/'missing_response_ids.json',missing)
    traces=[];full=[];analysis_start=time.perf_counter()
    for m in lock['models']:
        seed=m['seed']
        for c in eligible[seed]:
            cid=c['case_id'];private=meta[cid];rb=scidx[(seed,cid,'reserved')]['behavior'];parsed=rb['update_value_available']
            s=initial_state(c)
            for v in ('original',*POOL):s=update(s,c,v,idx[(seed,cid,v)]['raw'])
            dg=diagnosis(s);ps=prediction_set(s,c);fit=bool(s['classes'] and not s['unusable']);cov=bool(parsed and canonical(rb['update_value']) in ps)
            full.append({'seed':seed,'case_id':cid,'family':private['family'],'fixture_id':private['fixture_id'],'diagnosis':dg,'fits_all_pool':fit,'reserved_parsed':parsed,'reserved_covered':cov,'reserved_breaks_fitting_library':bool(fit and parsed and not cov),'prediction_width':len(ps),'compatible_classes':s['classes']})
            for policy in lock['policies']:
                for rep in (lock['random_seeds'] if policy=='random' else [0]):
                    t=time.perf_counter();state=update(initial_state(c),c,'original',idx[(seed,cid,'original')]['raw']);update_s=time.perf_counter()-t;selector_s=0;chosen=[]
                    costs=selector_costs(c)
                    for b in range(1,5):
                        t=time.perf_counter();v=next_query(state,c,policy,seed=rep,cost=costs);selector_s+=time.perf_counter()-t
                        t=time.perf_counter();state=update(state,c,v,idx[(seed,cid,v)]['raw']);update_s+=time.perf_counter()-t;chosen.append(v)
                        if b not in [1,2,4]:continue
                        ds=diagnosis(state);pred=prediction_set(state,c);covered=bool(parsed and canonical(rb['update_value']) in pred);uu=[idx[(seed,cid,z)]['usage'] for z in ['original',*chosen]]
                        traces.append({'seed':seed,'case_id':cid,'family':private['family'],'fixture_id':private['fixture_id'],'policy':policy,'replicate':rep,'budget':b,'queried':list(chosen),'diagnosis':ds,'coverage':covered,'reserved_parsed':parsed,'prediction_width':len(pred),'prediction_values':[json.loads(x) for x in pred],'class_count':ds['class_count'],'unknown':not state['classes'],'parse_insufficient':bool(state['unusable']),'refusal':not state['classes'] or bool(state['unusable']),'single_prediction':len(pred)==1,'wrong_specificity':bool(len(pred)==1 and parsed and not covered),'single_reserved_unparsed':len(pred)==1 and not parsed,'calls_with_original':len(uu),'tokens_with_original':sum(u['total_tokens'] for u in uu),'generation_seconds_with_original':sum(u['generation_seconds'] for u in uu),'selector_seconds':selector_s,'update_seconds':update_s,'weight':0.05 if policy=='random' else 1})
    with (SR/'replay_traces.jsonl').open('x',encoding='utf-8') as f:
        for r in traces:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    save(SR/'full_pool_consistency.json',full)
    grouped=collections.defaultdict(list)
    for r in traces:
        for family in ['ALL',r['family']]:grouped[(r['seed'],family,r['policy'],r['budget'])].append(r)
    curves=[]
    for (seed,family,policy,b),rr in sorted(grouped.items()):
        den=sum(r['weight'] for r in rr)
        def avg(k):return sum(r['weight']*r[k] for r in rr)/den
        parse=sum(r['weight']*r['reserved_parsed'] for r in rr);single=sum(r['weight']*r['single_prediction'] for r in rr)
        curves.append({'seed':seed,'family':family,'policy':policy,'additional_queries':b,'complete_case_count':round(den,8),'intermediate_incomplete_study':True,'coverage_overall':avg('coverage'),'coverage_when_reserved_parsed':sum(r['weight']*r['coverage'] for r in rr)/parse if parse else None,'reserved_parse_rate':avg('reserved_parsed'),'mean_prediction_width':avg('prediction_width'),'mean_class_count':avg('class_count'),'unknown_rate':avg('unknown'),'parse_insufficient_rate':avg('parse_insufficient'),'refusal_rate':avg('refusal'),'wrong_specificity_over_single_predictions':sum(r['weight']*r['wrong_specificity'] for r in rr)/single if single else None,'single_prediction_rate':avg('single_prediction'),'single_reserved_unparsed_count':sum(r['weight']*r['single_reserved_unparsed'] for r in rr),'mean_calls_with_original':avg('calls_with_original'),'mean_tokens_with_original':avg('tokens_with_original'),'mean_generation_seconds_with_original':avg('generation_seconds_with_original'),'mean_selector_seconds':avg('selector_seconds'),'mean_update_seconds':avg('update_seconds')})
    save(RUN/'budget_curves_partial.json',curves)
    det={(r['seed'],r['case_id'],r['budget'],r['policy']):r for r in traces if r['policy']!='random'};paths=[]
    for seed,cc in eligible.items():
        for b in [1,2,4]:paths.append({'seed':seed,'budget':b,'same_GBS_IG_paths':sum(det[(seed,c['case_id'],b,'gbs_gini')]['queried']==det[(seed,c['case_id'],b,'ig_per_byte_cost')]['queried'] for c in cc),'complete_cases':len(cc)})
    layer=[];consistency=[];clusters=[]
    for m in lock['models']:
        seed=m['seed']
        for family in ['ALL',*sorted({x['family'] for x in meta.values()})]:
            rr=[r for r in scored if r['seed']==seed and (family=='ALL' or r['meta']['family']==family)];oo=[r for r in rr if r['view']=='original'];re=[r for r in rr if r['view']=='reserved']
            layer.append({'seed':seed,'family':family,'generations':len(rr),'whole_json':sum(r['behavior']['syntax']['whole_json'] for r in rr),'exact_answer_envelope':sum(r['strict']['syntax_valid'] for r in rr),'strict_schema_valid':sum(r['strict']['output_schema_valid'] for r in rr),'strict_answer_correct':sum(r['strict']['strict_correct'] for r in rr),'original_correct':sum(r['strict']['strict_correct'] for r in oo),'original_observed':len(oo),'reserved_correct':sum(r['strict']['strict_correct'] for r in re),'reserved_observed':len(re),'behavior_value_available':sum(r['behavior']['update_value_available'] for r in rr),'at_output_token_cap':sum(r['at_output_cap'] for r in rr),'cap_and_no_exact_envelope':sum(r['at_output_cap'] and not r['strict']['syntax_valid'] for r in rr),'wrapper_recovered':sum(any(e['source']=='recovered_wrapper' for e in r['behavior']['envelopes']) for r in rr),'behavior_ambiguity':sum(r['behavior']['ambiguous'] for r in rr)})
            ff=[f for f in full if f['seed']==seed and (family=='ALL' or f['family']==family)]
            consistency.append({'seed':seed,'family':family,'complete_cases':len(ff),'pool_fits':sum(f['fits_all_pool'] for f in ff),'reserved_breaks_previously_fitting_library':sum(f['reserved_breaks_fitting_library'] for f in ff),'pool_unknown':sum(f['diagnosis']['class_count']==0 for f in ff),'pool_parse_insufficient':sum(f['diagnosis']['unusable_observations']>0 for f in ff),'reserved_covered':sum(f['reserved_covered'] for f in ff)})
        byfixture=collections.defaultdict(list)
        for r in scored:
            if r['seed']==seed:byfixture[r['meta']['fixture_id']].append(r)
        for fid,rr in byfixture.items():clusters.append({'seed':seed,'fixture_id':fid,'family':rr[0]['meta']['family'],'stratum':rr[0]['meta']['stratum'],'observed_generations':len(rr),'planned_generations':14,'strict_correct':sum(r['strict']['strict_correct'] for r in rr)})
    save(SR/'fixture_clusters_partial.json',clusters)
    usages={k:sum(r['usage'][k] for r in data) for k in ['inference_calls','input_tokens','output_tokens','total_tokens','generation_seconds']}
    guards=rows(RUN/'logs/guard.jsonl');start=next(e for e in events if e['event']=='SUPERVISOR_START')
    summary={'status':'INCOMPLETE_PRELOCKED_WALL_TIMEOUT','audit_type':'completeness-gated intermediate audit, not locked full224 main analysis','analyzed':now(),'started':start['time'],'stopped':end['time'],'wall_seconds':end['elapsed_seconds'],'rc':end['rc'],'planned_unique_responses':224,'generation_attempts':len(starts),'completed_responses':len(data),'interrupted_or_failed_attempts':len(starts)-len(data),'never_attempted':sum(not m['attempted'] for m in missing),'missing_responses':len(missing),'complete_cases_by_checkpoint':{str(seed):len(cc) for seed,cc in eligible.items()},'completed_usage_lower_bound':usages,'inflight_token_usage_unavailable':True,'startup_failures_before_model_loading':sum('ModuleNotFoundError' in e['error'] for e in rows(RUN/'errors.jsonl')),'layers':layer,'full_pool_consistency':consistency,'GBS_IG_paths':paths,'model_receipts':rows(RUN/'model_receipts.jsonl'),'protected_files_unchanged':len(lock['protected_hashes']),'guard_checks':len(guards),'sampled_power_W_range':[min(float(g['gpu_actual'][1]) for g in guards),max(float(g['gpu_actual'][1]) for g in guards)],'max_temperature_C':max(float(g['gpu_actual'][3]) for g in guards),'strict_paired_interaction_estimate':None,'interaction_reason':'0 exact frozen factor quads; line view includes rotation, reserved uses reversal and also value+line. Do not treat missing design as zero interaction.','raw_outputs_now_exposed_for_v3':True,'MDCS_implemented':False,'new_rules':0,'new_queries':0,'optimizer_updates':0,'analysis_seconds':time.perf_counter()-analysis_start,'automatic_resume':False}
    save(RUN/'summary_partial.json',summary)
    text=['# ACOD v2 真实推理中间报告：未完成，已按预算停止',f'审计时间：{now()}（Asia/Shanghai）。',f"实际监督运行：{start['time']}—{end['time']}；{end['elapsed_seconds']:.3f}秒，rc=75。预锁1500秒上限触发后仅收尾保存，不延长生成预算。",'', '## 完成度与失败',f"计划224次；已尝试{len(starts)}，完成{len(data)}；在途终止{len(starts)-len(data)}；尚未尝试{summary['never_attempted']}；缺{len(missing)}个唯一响应。",'- seed20261108：112/112，16/16题完整；seed20261109：95/112，13/16题有完整7视图，另1题仅部分视图、2题未尝试。两模型参数digest前后一致，0训练。','- 另有2次启动环境失败，均发生于模型加载和generate之前；日志和两次环境补充原样保留，不混入生成失败分母。','- 没有创建COMPLETE，原锁定要求224齐全的主分析未运行。以下仅对机械完整单元做CPU中间审计，资格只看7视图是否持久化，不看答案分数；不能据不同分母比较checkpoint胜负。',f"- 已保存调用usage：输入{usages['input_tokens']}、输出{usages['output_tokens']}、总{usages['total_tokens']} tokens，生成累计{usages['generation_seconds']:.3f}秒。以上为成功持久化部分的成本下界；在途失败的完整token/time不可恢复，不能宣称总成本仅为此数。",'', '## 四层计数（全部已保存响应）','|seed|组别|响应数|完整JSON|单answer envelope|严格schema|严格正确|行为可解析|达到128上限|','|---|---|---|---|---|---|---|---|---|']
    for r in layer:text.append(f"|{r['seed']}|{r['family']}|{r['generations']}|{r['whole_json']}|{r['exact_answer_envelope']}|{r['strict_schema_valid']}|{r['strict_answer_correct']}|{r['behavior_value_available']}|{r['at_output_token_cap']}|")
    text+=['','达到128-token上限只能称可能截断，不能凭计数确定截断原因。严格任务答案没有把integer9/string9/line9混为相同；行为恢复/有损解释不回写严格分数。','', '## 完整单元上的预算曲线（离线重放，中间结果）','original共同计费；追加预算1/2/4；random20固定seed均值，不当新自然样本。reserved只评分，不喂给选择器。','|seed|完整题数|策略|追加|coverage|预测宽度|相容类|unknown|解析不足|拒判|错误具体化率|','|---|---|---|---|---|---|---|---|---|---|---|']
    for r in curves:
        if r['family']!='ALL':continue
        e=r['wrong_specificity_over_single_predictions'];ee='NA' if e is None else f'{e:.3f}'
        text.append(f"|{r['seed']}|{r['complete_case_count']:.0f}|{r['policy']}|{r['additional_queries']}|{r['coverage_overall']:.3f}|{r['mean_prediction_width']:.3f}|{r['mean_class_count']:.3f}|{r['unknown_rate']:.3f}|{r['parse_insufficient_rate']:.3f}|{r['refusal_rate']:.3f}|{ee}|")
    text+=['','## 固定库跨视图一致性','|seed|组别|完整题|全池可拟合|reserved打破此前拟合|全池unknown|全池解析不足|','|---|---|---|---|---|---|---|']
    for r in consistency:text.append(f"|{r['seed']}|{r['family']}|{r['complete_cases']}|{r['pool_fits']}|{r['reserved_breaks_previously_fitting_library']}|{r['pool_unknown']}|{r['pool_parse_insufficient']}|")
    text+=['','## 交互与MDCS：尚不能建立必要性','严格配对交互不可估计，不是发现0例。预响应结构锁中0个精确四元组：line=C∘L，reserved=R∘L∘V；value与line组合显示C，不是R。reverse+value的无坐标变化组合也不存在。不得把单项对、reserved错叫二因素非加性或隐藏条件切换。','固定24规则内，reserved没有进一步拆分全池签名等价类（预响应CPU结构检查）；这个局部结论不外推未建模条件行为。自然库失配还可能是解析、输出上限、编码或任务理解问题，一次greedy不能证明切换触发器。','因此本轮不实现MDCS、不加手写规则、不合成额外查询；先明确本次有界检验未完整结束及配对证据缺项。即使无主动优势或交互，也不据小样本淘汰路线。','用户示例若原始行号升序，reverse后display-first仍为最大line；H2切成display-first仍应输出新Cherry，而非新Apple。例子需要真正可分的构造，本次不改题补齐。','若以后研究最小见证，须限定合法编辑空间与编辑/调用/长度成本；贪心不能直接叫全域最小，且IG/随机/覆盖数组等应获相同扩展候选权限。','', '## 暴露、保护与停止',f"{len(lock['protected_hashes'])}个受保护历史/v2文件SHA不变；旧round1/v2冻结包均未改。守卫{len(guards)}次；停止原因仅预锁总时限，不是游戏/权限绕过；STOP保留不清除。",'整个v2保留输入及首checkpoint自然输出已暴露，未来v3不能继续当独立最终测试；仅8个fixture/2构建族，配对意图/视图/checkpoint不独立，不作显著性/功效宣称。','没有自动恢复任务。若要补齐17个唯一响应，其中1个需要失败重试；原224尝试cap只剩16，必须另行明确授权新的有界恢复预算，不能偷偷续跑。','主文件：PROTOCOL_LOCK.json、STARTUP_AMENDMENT_01/02.json、results/responses.jsonl、summary_partial.json、budget_curves_partial.json、missing_response_ids.json、intermediate_scorer_only/逐条分层与重放、logs/STOP和guard。']
    (HERE/'PARTIAL_REPORT_ZH.md').open('x',encoding='utf-8').write('\n'.join(text)+'\n')
    hand=['# ACOD v2 未完成交接',f'时间：{now()}（Asia/Shanghai）',f'目录：{HERE}',f'实际结果：{len(data)}/224响应，{len(starts)}attempts，1500秒deadline安全停止，rc75。','seed08完整112；seed09完成95。原完整主分析未运行，只有单独标记的中间审计。','STOP原因是本实验总时限，owner acod_v2_eval_20261122；未清除，无自动恢复。','模型digest前后一致，旧118保护资产SHA一致。未训练/MDCS/新规则/新增query。','还缺17唯一响应（1在途终止+16未尝试），原cap仅余16attempt，不能自动补齐。若恢复须另行授权/预算并保留本次失败成本。','未来不再把v2保留集称新盲测；严格交互因无完整因子配对不可估计。','交付：PARTIAL_REPORT_ZH.md、results/summary_partial.json、results/budget_curves_partial.json、results/missing_response_ids.json、raw与分层证据。']
    (HERE/'HANDOVER_PARTIAL_ZH.md').open('x',encoding='utf-8').write('\n'.join(hand)+'\n')
    verify();files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    save(HERE/'final_hashes_partial.json',{'time':now(),'protocol_lock_sha256':sha(HERE/'PROTOCOL_LOCK.json'),'protected_hashes_equal':True,'hashes':{str(p.relative_to(HERE)):sha(p) for p in files}})
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()