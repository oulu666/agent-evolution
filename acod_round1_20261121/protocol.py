"""ACOD R1: auditable development protocol, pure CPU selection and tests."""
import copy, hashlib, itertools, json, math, random, re, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
RULES=['coordinate','display_first','display_last','opposite','field_line','lex_max','lex_min']
POOL=['reverse','rotate','swap','value','line']
POLICIES=['random','fixed','gbs_gini','ig_per_cost']
def now():return time.strftime('%Y-%m-%d %H:%M:%S %z')
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def dump(p,x):
    with open(p,'x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def append(p,x):
    with open(p,'a',encoding='utf-8') as f:f.write(json.dumps(x,ensure_ascii=False)+'\n');f.flush()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf-8').splitlines() if x]
def key(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def predict(h,v,intent):
    r=v['rows'];s=sorted(r,key=lambda x:x['line']);ix=0 if intent=='first' else -1
    if h=='coordinate':return s[ix]['text']
    if h=='opposite':return s[-1 if ix==0 else 0]['text']
    if h=='field_line':return s[ix]['line']
    if h=='display_first':return r[0]['text']
    if h=='display_last':return r[-1]['text']
    if h=='lex_max':return max(x['text'] for x in r)
    if h=='lex_min':return min(x['text'] for x in r)
    raise ValueError(h)
def support(task,obs):
    return [h for h in RULES if all(key(predict(h,task['views'][v],task['intent']))==key(y) for v,y in obs.items())]
def signature_groups(task,names=RULES,views=None):
    groups={}
    for h in names:
        sig=key([predict(h,task['views'][v],task['intent']) for v in (views or list(task['views']))])
        groups.setdefault(sig,[]).append(h)
    return list(groups.values())
def select(task,obs,available,policy,rng,costs=None):
    # API deliberately accepts observed responses only, never an answer table.
    if policy=='random':return rng.choice(available)
    if policy=='fixed':return next(v for v in POOL if v in available)
    H=support(task,obs)
    if not H:return next(v for v in POOL if v in available)
    def score(v):
        counts={}
        for h in H:
            y=key(predict(h,task['views'][v],task['intent']));counts[y]=counts.get(y,0)+1
        probs=[n/len(H) for n in counts.values()]
        if policy=='gbs_gini':return 1-sum(p*p for p in probs)
        assert policy=='ig_per_cost'
        entropy=-sum(p*math.log2(p) for p in probs)
        return entropy/(costs[v] if costs else len(key(task['views'][v]['messages']).encode())+128)
    return max(available,key=lambda v:(score(v),-POOL.index(v)))
def validate_source(source):
    assert source['intent'] in ['first','last']
    assert source['rows'] and len({x['line'] for x in source['rows']})==len(source['rows'])
    assert all(isinstance(x['line'],int) and x['line']>0 for x in source['rows'])
    assert re.fullmatch('[A-Za-z0-9_]+',source['marker']), 'Only literal safe patterns supported'
    actual=[{'line':i+1,'text':s} for i,s in enumerate(source['file_lines']) if re.search(source['marker'],s)]
    assert actual==sorted(source['rows'],key=lambda x:x['line']), 'Incomplete/inconsistent evidence'
def make_view(src,name):
    validate_source(src)
    if name not in ['original']+POOL+['heldout']:raise ValueError('Unsupported transform')
    v={'rows':copy.deepcopy(src['rows']),'file_lines':list(src['file_lines'])}
    # Only first/last by source coordinate; text is output-only, regex membership unchanged.
    value=name in ['value','heldout'];line=name in ['line','heldout']
    mapping={}
    if value:
        unique=list(dict.fromkeys(x['text'] for x in sorted(v['rows'],key=lambda x:x['line'])))
        labels=['Zulu','Alpha','Mango','Delta','Echo']
        mapping={s:src['marker']+' remapped '+labels[i] for i,s in enumerate(unique)}
        assert len(set(mapping.values()))==len(mapping)
        for x in v['rows']:x['text']=mapping[x['text']];v['file_lines'][x['line']-1]=x['text']
    if line:
        for x in v['rows']:x['line']=2*x['line']+3
        v['file_lines']=['unrelated filler']*(max(x['line'] for x in v['rows'])+2)
        for x in v['rows']:v['file_lines'][x['line']-1]=x['text']
    if name in ['reverse','heldout']:v['rows'].reverse()
    if name in ['rotate','line']:v['rows']=v['rows'][1:]+v['rows'][:1]
    if name=='swap':v['rows'][0],v['rows'][1]=v['rows'][1],v['rows'][0]
    actual=[{'line':i+1,'text':s} for i,s in enumerate(v['file_lines']) if re.search(src['marker'],s)]
    assert actual==sorted(v['rows'],key=lambda x:x['line'])
    basegold=predict('coordinate',{'rows':src['rows']},src['intent'])
    gold=predict('coordinate',v,src['intent'])
    assert gold==(mapping.get(basegold,basegold))
    cert={'legal':True,'operator':'argmin/max source line then text','complete_regex_matches':True,'unique_positive_coordinates':True,'selection_order_preserved':True,'answer_relation':'bijective text mapping' if value else 'equal','text_map':mapping,'coordinate_map':'2*l+3' if line else 'identity','display_permutation':True,'new_snapshot':value or line,'source_snapshot_sha256':hashlib.sha256(key(src['file_lines']).encode()).hexdigest(),'view_snapshot_sha256':hashlib.sha256(key(v['file_lines']).encode()).hexdigest()}
    call={'tool':'file_search','arguments':{'path':src['path'],'pattern':src['marker']}}
    obs={'ok':True,'result':v['rows']}
    v.update(messages=[{'role':'system','content':src['system']},{'role':'user','content':src['prompt']},{'role':'assistant','content':key(call)},{'role':'user','content':'TOOL RESULT:\n'+key(obs)}],certificate=cert,gold=gold)
    return v
PROTOCOL='''# ACOD 首轮冻结协议（开发/工程，不是论文盲测）
本文件与 tasks.json、manifest.json 在模型加载前冻结。只新增本目录，不改旧数据、权重、.venv、runs、训练器或功耗。
目标：检验可观测规则可区分性与固定候选响应表的诊断/预测，不推断隐藏根因、不证明ACOD创新。
16任务：2个历史P9开发文件×first/last=4；新生成6文件×first/last=12，其中2文件重复text碰撞。历史与新开发分组报告，不使用旧正式P10/P14作盲测。新文件为免人工标注的确定性开发资产，不声称gold不可得。
操作只允许完整非空匹配集合、唯一正整数原行号、literal regex、first/last选完整text。空集、歧义行号、regex复杂替换、未知operator不适用应拒绝。显示顺序可变，line表示原坐标；value替换保持匹配且双射保留重复关系；line映射严格递增且重建文件；组合变换另建快照，不谎称工具源未变或答案一律不变。
每任务original+reverse/rotate/swap/value/line+heldout=7条答案生成。2个P9 ordinary seed20261108/20261109 checkpoint，总上限224次，断点按唯一ID逐条保存，失败调用也计账；每调用128新tokens、B1、原greedy/no-cache协议、无梯度/优化器/训练。原工具调用为oracle前缀，不评工具选择/E2E。GPU/进程/Windows Apex/全局及旧runs STOP守卫失败则停止，不自动清任何STOP；只在本目录写有来源reason的STOP。总超时20分钟、单generate超时60秒。
候选规则7类：coordinate、display_first/last、opposite、field_line、lex_max/min。每次只报告相容集合或unknown；singleton仍非确定真实机制。原始回答为共同已付成本；追加查询预算1/2/4，所有策略共享同一pool、解析、观测与预算。随机固定seed 0..19；fixed顺序reverse,rotate,swap,value,line；GBS用多响应Gini均衡划分；IG用均匀相容假设的熵/（预先tokenized输入+128），不是新算法。选择器API不接受未查询响应，reserved heldout从不参与选择/更新，只评预测。
报告每预算剩余候选/预测集合大小、heldout响应集合覆盖、unknown、singleton预测失配（不是根因误归因）、实际查询tokens/time。无相容规则时预测集合为空并拒判，不硬选类。自然行为没有规则gold，不报告根因准确率或伪造概率校准；经验覆盖不是校准置信度。模拟器独立报告规则/等价类恢复、闭集不适配与混合策略，另用小池最短区分子集作CPU参照。
候选响应只采集一次，各策略离线重放，不称在线主动模型试验；采集总成本与反事实策略成本分开，策略选择计算计时。预算是原始+追加k条，heldout是测量额外成本不送选择器。固定seed不是随机稳定性研究，未重复解码；B1/B32不混用。
不做小样本算法淘汰，不推断统计显著性；无主动优势照实报告。无跨新工具/任务族正式泛化证据；以后family split按基础文件及模板整体隔离，跨checkpoint/新工具的独立测试仍待后续授权。
'''
def initialize():
    assert not (HERE/'manifest.json').exists()
    tasks=[];old=rows(ROOT/'data_ext_p10_twoview_cpu_20261117/dev.jsonl')
    for r in old:
        if r['case'] not in [0,1]:continue
        p=r['expected_arguments']['path'];marker=r['expected_arguments']['pattern']
        tasks.append({'id':'historical_'+str(r['case'])+'_'+r['intent'],'family':'historical_dev','file_id':'historical_'+str(r['case']),'intent':r['intent'],'path':p,'marker':marker,'system':r['system'],'prompt':r['prompt'],'rows':json.loads(r['expected_observation'])['result'],'file_lines':r['environment']['files'][p].splitlines()})
    system=old[0]['system']
    for f in range(6):
        marker='acodr1m'+str(f);path='acod_dev/file_'+str(f)+'.txt';coords=[2+f,7+f,13+f]
        values=['Zulu','Alpha','Mango'] if f%2==0 else ['Delta','Zulu','Bravo']
        if f==4:values=['Same','Same','Same']
        if f==5:values=['Repeat','Other','Repeat']
        rr=[{'line':l,'text':marker+' token '+t} for l,t in zip(coords,values)]
        lines=['unrelated filler']*(coords[-1]+2)
        for x in rr:lines[x['line']-1]=x['text']
        for intent in ['first','last']:
            prompt=f"Find lines containing '{marker}' in {path}. Return the complete matching line occurring {intent} in the original file. The line field is the original source coordinate; result rows may be displayed in any order."
            tasks.append({'id':f'new_{f}_{intent}','family':'new_collision_dev' if f>=4 else 'new_distinct_dev','file_id':f'new_{f}','intent':intent,'path':path,'marker':marker,'system':system,'prompt':prompt,'rows':rr,'file_lines':lines})
    assert len(tasks)==16
    for t in tasks:t['views']={v:make_view(t,v) for v in ['original']+POOL+['heldout']}
    dump(HERE/'tasks.json',tasks)
    (HERE/'PROTOCOL_ZH.md').write_text(PROTOCOL,encoding='utf-8')
    models=[];ref=read(ROOT/'runs_ext_p10_formal_prompt_20261117/model_receipts.json')
    for seed in [20261108,20261109]:
        plan=read(ROOT/f'data_ext_p10_twoview_cpu_20261117/plan_seed{seed}.json');adapter=Path(plan['reuse_ordinary_checkpoint'])
        h=sha(adapter/'adapter_model.safetensors');assert h==next(x['adapter_sha256'] for x in ref if x['seed']==seed)
        models.append({'seed':seed,'adapter':str(adapter),'adapter_sha256':h,'adapter_config_sha256':sha(adapter/'adapter_config.json')})
    originals=[ROOT/'fac_tinyagent/sft/evaluate.py',ROOT/'fac_tinyagent/sft/train.py',ROOT/'fac_tinyagent/sft/dataset.py',ROOT/'fac_tinyagent/replay_study.py',ROOT/'fac_tinyagent/p10_devdiagnosis_20261117.py',ROOT/'data_ext_p10_twoview_cpu_20261117/dev.jsonl']
    for m in models:originals += [Path(m['adapter'])/'adapter_model.safetensors',Path(m['adapter'])/'adapter_config.json',ROOT/f"runs_phase2/A_seed{m['seed']}/config.json"]
    files=[HERE/'protocol.py',HERE/'runner.py',HERE/'analyze.py',HERE/'PROTOCOL_ZH.md',HERE/'tasks.json']+originals
    dump(HERE/'manifest.json',{'created':now(),'models':models,'tasks':16,'max_calls':224,'max_new_tokens':128,'batch_size':1,'decode':'original generate_with_usage greedy use_cache=False','random_seeds':list(range(20)),'hashes':{str(p.relative_to(ROOT)):sha(p) for p in files},'scope':'post-tool fixed response table development only','optimizer_updates':0})
def verify():
    m=read(HERE/'manifest.json')
    for p,h in m['hashes'].items():assert sha(ROOT/p)==h,'Frozen input changed: '+p
    return m

def tests():
    tasks=read(HERE/'tasks.json');passed=[];sim=[]
    for t in tasks:
        for v in t['views'].values():assert v['certificate']['legal']
    passed.append('112 views complete-match/order/answer relation certificates')
    for bad in ['empty','duplicate_coordinate','nonliteral_regex','unknown_transform']:
        t=copy.deepcopy(tasks[4])
        try:
            if bad=='empty':t['rows']=[]
            if bad=='duplicate_coordinate':t['rows'][1]['line']=t['rows'][0]['line']
            if bad=='nonliteral_regex':t['marker']='.*'
            make_view(t,'bad' if bad=='unknown_transform' else 'value')
            raise RuntimeError('invalid transform accepted')
        except (AssertionError,ValueError):passed.append('reject_'+bad)
    # Strict JSON typed comparisons prevent line/text coercion collisions.
    assert key(9)!=key('9');passed.append('typed observation equality')
    for t in tasks:
        equivalence=signature_groups(t)
        for h in RULES:
            response={v:predict(h,t['views'][v],t['intent']) for v in t['views']}
            eq=next(g for g in equivalence if h in g)
            for policy in POLICIES:
                obs={'original':response['original']};avail=list(POOL);rng=random.Random(0)
                for b in range(1,6):
                    v=select(t,obs,avail,policy,rng);obs[v]=response[v];avail.remove(v)
                    S=support(t,obs);assert h in S
                    if b==5:assert sorted(S)==sorted(eq)
                sim.append({'task':t['id'],'rule':h,'policy':policy,'class':eq,'final_support':S,'passed':True})
    passed.append('448 closed-rule/policy full-pool equivalence recoveries')
    # Explicit open-world and mixed behavior. No forced closed-class label.
    t=tasks[4];assert support(t,{'original':'OUTSIDE_THE_VOCABULARY'})==[]
    mixed={'original':predict('coordinate',t['views']['original'],t['intent']),'reverse':predict('field_line',t['views']['reverse'],t['intent'])}
    assert support(t,mixed)==[];passed += ['unknown_reject','mixed_strategy_reject']
    coll=next(t for t in tasks if t['id']=='new_4_last')
    assert len(support(coll,{'original':predict('coordinate',coll['views']['original'],'last')}))>=5
    passed.append('collision_not_forced_unique')
    # A constant lexical rule can match coordinate on permutations yet separate with a value map.
    t=next(t for t in tasks if t['id']=='new_0_last')
    assert any(len(g)>1 for g in signature_groups(t,views=['original','reverse','rotate','swap']))
    passed.append('permutation_equivalence_detected')
    references=[]
    for t in tasks:
        for h in RULES:
            full=next(g for g in signature_groups(t) if h in g)
            minimum=None
            for k in range(6):
                for sub in itertools.combinations(POOL,k):
                    obs={v:predict(h,t['views'][v],t['intent']) for v in ['original']+list(sub)}
                    # Only compare to pool-equivalence; reserved heldout cannot be used to choose.
                    target=next(g for g in signature_groups(t,views=['original']+POOL) if h in g)
                    if sorted(support(t,obs))==sorted(target):minimum=k;break
                if minimum is not None:break
            references.append({'task':t['id'],'rule':h,'min_additional_queries_to_pool_equivalence':minimum,'full_equivalence':full})
    dump(HERE/'cpu_tests.json',{'time':now(),'passed':True,'tests':passed,'simulator_cases':len(sim),'scope':'simulator engineering not natural model accuracy'})
    dump(HERE/'simulator_results.json',sim);dump(HERE/'exhaustive_reference.json',references)
    print(json.dumps({'passed':True,'checks':len(passed),'simulator_cases':len(sim)},ensure_ascii=False))
if __name__=='__main__':
    import sys,os
    os.environ['TZ']='Asia/Shanghai';time.tzset()
    if sys.argv[1]=='init':initialize()
    elif sys.argv[1]=='test':verify();tests()