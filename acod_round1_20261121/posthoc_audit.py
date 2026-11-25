"""Clearly post-hoc descriptive output audit; does not change frozen primary analysis."""
import collections,json,os,re,time
from protocol import *
os.environ['TZ']='Asia/Shanghai';time.tzset()
def main():
    verify();R=HERE/'results';rr=rows(R/'responses.jsonl');tt={t['id']:t for t in read(HERE/'tasks.json')};counts=collections.Counter();examples=[]
    for r in rr:
        t=tt[r['task']];v=t['views'][r['view']];y=r['answer'];labels=[]
        if isinstance(y,str):
            if any(y==x['text'] for x in v['rows']):labels.append('exact_complete_text')
            if re.fullmatch(r'\d+',y) and any(int(y)==x['line'] for x in v['rows']):labels.append('numeric_string_matching_line')
            if re.fullmatch(r'line\s+\d+',y,re.I) and any(int(re.findall(r'\d+',y)[0])==x['line'] for x in v['rows']):labels.append('line_prefixed_string_matching_line')
        if isinstance(y,int) and not isinstance(y,bool) and any(y==x['line'] for x in v['rows']):labels.append('integer_matching_line')
        if not labels:labels=['other']
        for label in labels:counts[label]+=1
        if len(examples)<8 and labels!=['exact_complete_text']:examples.append({'id':r['id'],'answer':y,'labels':labels,'support_original_only':support(t,{'original':r['observation']}) if r['view']=='original' else None})
    tr=rows(R/'replay_traces.jsonl');det={(r['seed'],r['task'],r['budget_additional'],r['policy']):r for r in tr if r['policy']!='random'}
    pair=[]
    for seed in [20261108,20261109]:
        for budget in [1,2,4]:
            keys=[(seed,t,budget) for t in tt];same=sum(det[k+('gbs_gini',)]['queried']==det[k+('ig_per_cost',)]['queried'] for k in keys)
            pair.append({'seed':seed,'budget':budget,'same_GBS_IG_query_sequence':same,'tasks':len(keys)})
    full=read(R/'full_pool_support.json');idx={(r['seed'],r['task'],r['view']):r for r in rr};format_affected=[]
    for f in full:
        if not f['unknown']:continue
        obs=[idx[(f['seed'],f['task'],v)] for v in ['original']+POOL]
        matches=[]
        for r in obs:
            y=r['answer'];v=tt[r['task']]['views'][r['view']]
            if isinstance(y,str) and re.fullmatch(r'(?:line\s+)?\d+',y,re.I) and any(int(re.findall(r'\d+',y)[0])==x['line'] for x in v['rows']):matches.append(r['view'])
        if matches:format_affected.append({'seed':f['seed'],'task':f['task'],'some_string_line_responses':matches})
    audit={'time':now(),'posthoc':True,'no_new_generations':True,'primary_results_unchanged':True,'output_phenotype_counts':dict(counts),'examples':examples,'GBS_IG_same_realized_queries':pair,'unknown_tasks_with_some_string_line_answers':len(format_affected),'unknown_tasks_total':sum(f['unknown'] for f in full),'format_affected':format_affected,'not_a_root_cause_or_new_classifier':'String/int variants and field-selection combinations were not modeled in the frozen 7-rule library; do not reinterpret unknown as genuine unseen cognition.'}
    dump(R/'posthoc_output_audit.json',audit)
    ev=rows(R/'events.jsonl');end=next(x for x in ev if x['event']=='SUPERVISOR_END');start=next(x for x in ev if x['event']=='SUPERVISOR_START')
    text=['# 首轮结果补充审计（事后描述，非主分析改版）',f'时间：{now()}（Asia/Shanghai）','所有以下统计均基于已保存224条真实输出；没有新增生成、改提示、扩规则或重算主指标。',f"实际监督器运行：{start['time']}—{end['time']}（北京时间），{end['elapsed_seconds']:.3f}秒，rc={end['rc']}。",'', '## 关键限制：规则库和输出表示',f'输出表型计数：{dict(counts)}。',f"25个full-pool unknown任务实例中，带至少一条字符串行号/line前缀行号的有{len(format_affected)}个。这里的任务实例包含两个checkpoint的配对题，不能当独立样本。",'冻结field_line仅预测JSON整数；例如实际{"answer":"9"}和{"answer":"line 9"}都不匹配整数9。严格类型比较有审计价值，但若研究目标是语义行为诊断，这个规则库显然不充分，unknown率不能直接解读为真实策略变化率。','另外，选择display-first并输出line是组合规则，库中没有。不能从单条line样式答案推出坐标选择正确或隐藏字段根因。下一版若研究表示归一化/组合语法，须另行预注册独立数据，不覆盖本轮主结果。','历史开发题只是复用P9/P10已有文件与问题，oracle工具JSON前缀本轮经统一compact/sorted序列化；不是历史逐字prompt或既有正常端到端成绩的复现。旧P10正式题没有重新使用。','','## 强基线冗余',f'GBS与IG实际查询序列一致性：{pair}。','两者实现的Gini均衡与entropy/cost目标一般不同，但此轮所有实际路径完全相同，应把本池结果作为同一个经验基线看待，不能包装成两个独立胜负证据。没有独立的“ACOD新算法”臂；此次是问题与基线协议工程。','','## 本轮可支持的结论','1. 变换证书、开放拒判和固定表重放已打通，真实冻结推理可运行。','2. 当前7规则+严格类型不足以覆盖自然模型响应；这是协议/表示不足的证据，不是对研究方向的淘汰依据。','3. 1/2/4预算曲线没有展示IG/GBS超过固定/随机的稳定预测优势；不同支持集合大小和coverage需要共同解释，不能拿收缩或unknown增加当诊断成功。','4. 根因准确率、概率校准、新工具泛化、统计显著性均未建立。','', '下一轮首要决策不是增加GPU规模，而是冻结行为输出规范与可组合规则表示，并用独立保留文件检验预测；本轮数据从此均为开发暴露资产。']
    (HERE/'POSTHOC_AUDIT_ZH.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    dump(HERE/'delivery_hashes.json',{'time':now(),'hashes':{str(p.relative_to(HERE)):sha(p) for p in files},'primary_manifest_unchanged':sha(HERE/'manifest.json')})
    print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=='__main__':main()