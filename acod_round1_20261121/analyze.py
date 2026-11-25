"""Offline selector replay. Held-out model responses are scorer-only."""
import collections,os,random,statistics,time
from protocol import *
os.environ['TZ']='Asia/Shanghai';time.tzset()
RUN=HERE/'results'
def main():
    manifest=verify();tests=read(HERE/'cpu_tests.json');assert tests['passed']
    allrows=rows(RUN/'responses.jsonl');index={(r['seed'],r['task'],r['view']):r for r in allrows}
    assert len(index)==len(allrows)
    tasks=read(HERE/'tasks.json');traces=[];full=[]
    for m in manifest['models']:
        seed=m['seed'];costs=read(RUN/f'input_costs_seed{seed}.json')
        for ti,t in enumerate(tasks):
            if not all((seed,t['id'],v) in index for v in t['views']):continue
            # Only this evaluator owns the response table; selector receives obs dictionary.
            def observe(v):return index[(seed,t['id'],v)]['observation']
            original=observe('original');heldout=observe('heldout')
            closed=support(t,{v:observe(v) for v in ['original']+POOL})
            full.append({'seed':seed,'task':t['id'],'family':t['family'],'support_all_pool':closed,'unknown':not closed,'heldout_covered':any(key(predict(h,t['views']['heldout'],t['intent']))==key(heldout) for h in closed)})
            for policy in POLICIES:
                for rep in (range(20) if policy=='random' else [0]):
                    rng=random.Random(20261121+100*ti+seed+rep)
                    obs={'original':original};available=list(POOL);queried=[];selector_s=0
                    for b in range(1,5):
                        start=time.perf_counter();v=select(t,obs,available,policy,rng,costs[t['id']]);selector_s+=time.perf_counter()-start
                        available.remove(v);queried.append(v);obs[v]=observe(v)
                        if b not in [1,2,4]:continue
                        S=support(t,obs)
                        pred={key(predict(h,t['views']['heldout'],t['intent'])) for h in S}
                        usage=[index[(seed,t['id'],x)]['usage'] for x in ['original']+queried]
                        covered=key(heldout) in pred
                        traces.append({'seed':seed,'task':t['id'],'family':t['family'],'file_id':t['file_id'],'policy':policy,'replicate':rep,'budget_additional':b,'queried':list(queried),'observations':dict(obs),'support':S,'unknown':not S,'singleton':len(S)==1,'predicted_set':[json.loads(x) for x in sorted(pred)],'prediction_size':len(pred),'heldout_covered':covered,'singleton_prediction_mismatch':len(S)==1 and not covered,'query_calls_with_original':1+b,'query_total_tokens_with_original':sum(u['total_tokens'] for u in usage),'query_generation_seconds_with_original':sum(u['generation_seconds'] for u in usage),'selector_seconds':selector_s,'weight':0.05 if policy=='random' else 1})
    with open(RUN/'replay_traces.jsonl','x',encoding='utf-8') as f:
        for r in traces:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    grouped=collections.defaultdict(list)
    for r in traces:
        for group in ['ALL',r['family']]:grouped[(r['seed'],group,r['policy'],r['budget_additional'])].append(r)
    curves=[]
    for (seed,family,policy,budget),rr in sorted(grouped.items()):
        den=sum(r['weight'] for r in rr)
        def avg(k):return sum(r['weight']*r[k] for r in rr)/den
        supportden=sum(r['weight'] for r in rr if not r['unknown'])
        single=sum(r['weight'] for r in rr if r['singleton'])
        curves.append({'seed':seed,'family':family,'policy':policy,'additional_queries':budget,'tasks_weighted':round(den,8),'heldout_response_coverage':avg('heldout_covered'),'mean_support_size':sum(r['weight']*len(r['support']) for r in rr)/den,'mean_prediction_set_size':avg('prediction_size'),'unknown_rate':avg('unknown'),'singleton_rate':avg('singleton'),'singleton_heldout_mismatch_rate':sum(r['weight']*r['singleton_prediction_mismatch'] for r in rr)/single if single else None,'coverage_when_not_unknown':sum(r['weight']*r['heldout_covered'] for r in rr)/supportden if supportden else None,'query_tokens_including_original':avg('query_total_tokens_with_original'),'query_generation_seconds_including_original':avg('query_generation_seconds_with_original'),'selector_seconds':avg('selector_seconds')})
    dump(RUN/'budget_curves.json',curves);dump(RUN/'full_pool_support.json',full)
    bygroup=[]
    for seed in [m['seed'] for m in manifest['models']]:
        for family in ['ALL','historical_dev','new_distinct_dev','new_collision_dev']:
            rr=[r for r in allrows if r['seed']==seed and (family=='ALL' or r['family']==family)]
            orig=[r for r in rr if r['view']=='original'];fr=[r for r in full if r['seed']==seed and (family=='ALL' or r['family']==family)]
            bygroup.append({'seed':seed,'family':family,'original_correct':sum(r['correct'] for r in orig),'original_n':len(orig),'all_views_correct':sum(r['correct'] for r in rr),'all_views_n':len(rr),'full_pool_unknown':sum(r['unknown'] for r in fr),'full_pool_n':len(fr),'full_pool_heldout_covered':sum(r['heldout_covered'] for r in fr)})
    usage={k:sum(r['usage'][k] for r in allrows) for k in ['inference_calls','input_tokens','output_tokens','total_tokens','generation_seconds']}
    startrows=rows(RUN/'calls_started.jsonl');errs=rows(RUN/'errors.jsonl') if (RUN/'errors.jsonl').exists() else []
    guards=rows(RUN/'logs/guard.jsonl');powers=[float(r['gpu_actual'][1]) for r in guards]
    sm={'analyzed':now(),'scope':'development fixed response table replay, not online active experiment','complete':(RUN/'COMPLETE.json').exists(),'planned_cap':224,'started_attempts':len(startrows),'completed_generations':len(allrows),'incomplete_or_failed_attempts':len(startrows)-len(allrows),'parse_failures':sum(not r['parsed'] for r in allrows),'generation_usage':usage,'versions_source':'events.jsonl WORKER_ENV','model_receipts':rows(RUN/'model_receipts.jsonl'),'groups':bygroup,'errors':errs,'guard_checks':len(guards),'observed_power_draw_W_range':[min(powers),max(powers)],'max_temperature_C':max(float(r['gpu_actual'][3]) for r in guards),'selector_seconds_replay_all_replicates':sum(r['selector_seconds'] for r in traces if r['budget_additional']==4),'calibration':'No natural rule gold or probabilistic confidence: empirical set coverage only; calibration not claimed','training_steps':0,'limitations':['16 tasks from 8 files; paired intents/variants not independent','2 ordinary checkpoints from same Qwen3-0.6B family, not model-family generalization','No repeated stochastic decodes; B1 greedy only','No novel tool/operator transfer experiment','Closed behavioral library incomplete; singleton does not establish mechanism','New generated cases development-only; historical dev already exposed','Original response cost counted in every strategy; full-table acquisition + heldout is reported separately','IG denominator precomputed input tokens+128, not unseen actual output cost','No statistical power claim or small-sample method rejection']}
    dump(RUN/'summary.json',sm)
    lines=['# ACOD 首轮真实冻结模型实验报告','',f'生成/分析时间：{now()}（Asia/Shanghai）。', '', '## 实际完成',f"- 调用尝试 {len(startrows)}；完成 {len(allrows)}/224；解析失败 {sm['parse_failures']}；训练更新 0。",f"- 输入 {usage['input_tokens']}、输出 {usage['output_tokens']}，合计 {usage['total_tokens']} tokens；生成累计 {usage['generation_seconds']:.2f}秒。",f"- 守卫 {len(guards)}次；采样功耗 {min(powers):.2f}—{max(powers):.2f}W，温度最高{sm['max_temperature_C']:.0f}℃；未改功率/风扇。采样不是能耗积分。",'- 2个P9 ordinary adapter，Qwen3-0.6B NF4 QLoRA，B1原greedy/use_cache=False/max_new_tokens128。完整参数前后digest及磁盘adapter哈希见model_receipts.jsonl。','- 16题（8基础文件×2意图），4历史开发题+12新生成开发题；所有视图均oracle tool prefix，未评tool-call/E2E。','- CPU模拟器448规则×策略验收通过，与真实模型结果严格分开；最短区分子集参照见exhaustive_reference.json。','','## 自然模型描述（不是根因准确率）','|seed|组别|original正确|全部视图正确|全候选后unknown|全候选后保留集覆盖heldout|','|---|---|---|---|---|---|']
    for g in bygroup:lines.append(f"|{g['seed']}|{g['family']}|{g['original_correct']}/{g['original_n']}|{g['all_views_correct']}/{g['all_views_n']}|{g['full_pool_unknown']}/{g['full_pool_n']}|{g['full_pool_heldout_covered']}/{g['full_pool_n']}|")
    lines += ['','## 等预算离线重放：ALL组','追加预算不含共同original；其tokens/time计入。random为20个固定seed的均值，不把重复重放当独立样本。heldout从不交给selector。','|seed|策略|追加查询|预测覆盖|平均规则数|平均预测数|unknown|singleton预测失配|平均tokens含original|','|---|---|---|---|---|---|---|---|']
    for c in curves:
        if c['family']!='ALL':continue
        mm=c['singleton_heldout_mismatch_rate'];ms='NA' if mm is None else f'{mm:.3f}'
        lines.append(f"|{c['seed']}|{c['policy']}|{c['additional_queries']}|{c['heldout_response_coverage']:.3f}|{c['mean_support_size']:.3f}|{c['mean_prediction_set_size']:.3f}|{c['unknown_rate']:.3f}|{ms}|{c['query_tokens_including_original']:.1f}|")
    lines += ['','## 解释边界','相容集合随查询收缩，coverage可能下降；更小的集合不是自动更好。unknown说明闭集规则不足或行为不稳定，不等于检测到某种隐藏根因。singleton的heldout失配只衡量过早具体化的可观测风险，不是根因误归因率。','新开发题含显式坐标/任意显示说明，历史开发题沿原问法；组间不同不能当处理因果效果。此轮未做概率校准、随机重复解码或跨新工具泛化；未来必须按文件/模板family split。','CPU可算gold，准确率为免人工标注不是gold不可获得。value/line映射重建快照并检查输出关系，不要求输出字面恒等。原题oracle prefix不计作模型工具调用。','固定候选响应表生成一次；随机/固定/GBS/IG离线模拟共享响应，不宣称在线自适应模型实测。没有提出独立于这些强基线的新ACOD算法，也不据小样本决定方向生死。','','## 成本与文件',f"所有重放累计选择计算 {sm['selector_seconds_replay_all_replicates']:.6f}秒（不含已采集生成时间；非部署延迟保证）。",'完整budget曲线含分组tokens/time/选择开销见budget_curves.json；逐条实际raw输出见responses.jsonl；逐条选择与相容集合见replay_traces.jsonl；校验证书在../tasks.json。','所有新文件仅位于acod_round1_20261121；旧权重/配置/源码哈希终验。无训练、API、模型下载、push、外发。']
    (HERE/'REPORT_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    hand=['# ACOD 首轮交接',f'时间：{now()}（Asia/Shanghai）',f'Windows：C:\\Users\\Egret\\Desktop\\oulu\\Agent Self-Evolution\\fac_tinyagent\\acod_round1_20261121',f'WSL：{HERE}','执行命令（项目根）：','.venv/bin/python -B acod_round1_20261121/protocol.py init','.venv/bin/python -B acod_round1_20261121/protocol.py test','.venv/bin/python -B acod_round1_20261121/runner.py supervise','.venv/bin/python -B acod_round1_20261121/analyze.py',f'状态：complete={sm["complete"]}；已完成{len(allrows)}次生成；0训练。','不要重跑init或覆盖冻结文件；COMPLETE存在时runner不再生成。未完成时只可在STOP原因核清后从同表续跑，绝不自动删除用户STOP；失败尝试仍占224总上限。','模型身份、时钟、进程PID、rc：results/events.jsonl；逐条调用results/calls_started.jsonl、responses.jsonl；守卫results/logs/guard.jsonl。','结果仅开发/工程证据；没有自然根因gold，没有blind正式卷，没有新工具验证，没有新增ACOD算法。下一步先分析unknown与跨视图预测失败，不能按本轮结果改假设/提示再冒称同一冻结实验。']
    (HERE/'HANDOVER_ZH.md').write_text('\n'.join(hand)+'\n',encoding='utf-8')
    verify()
    artifacts=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    dump(HERE/'final_artifact_hashes.json',{'time':now(),'hashes':{str(p.relative_to(HERE)):sha(p) for p in artifacts},'original_manifest_sha256':sha(HERE/'manifest.json')})
    print(json.dumps(sm,ensure_ascii=False,indent=2))
if __name__=='__main__':main()