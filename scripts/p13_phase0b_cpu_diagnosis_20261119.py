"""One bounded CPU/static diagnosis; no torch/model imports, no retry or threshold edits."""
import ast,collections,hashlib,json,math,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent import p13_phase0b_20261118 as P
from fac_tinyagent.utils import read_json,read_jsonl,sha256_file,write_json

def stats(a,b):
    assert len(a)==len(b);ds=[abs(x-y) for x,y in zip(a,b)]
    return {'n':len(a),'different':sum(x!=y for x,y in zip(a,b)),'max_abs':max(ds,default=0),'mean_abs':statistics.mean(ds) if ds else 0,'median_abs':statistics.median(ds) if ds else 0,'max_symmetric_relative':max((abs(x-y)/max(abs(x),abs(y),1e-12) for x,y in zip(a,b)),default=0)}
def ranks(values):
    ix=sorted(range(len(values)),key=lambda i:values[i]);out=[0.]*len(ix);start=0
    while start<len(ix):
        end=start+1
        while end<len(ix) and values[ix[end]]==values[ix[start]]:end+=1
        for j in range(start,end):out[ix[j]]=(start+end-1)/2
        start=end
    return out

def rankings(ids,a,b):
    x=ranks(a);y=ranks(b);mx=statistics.mean(x);my=statistics.mean(y);den=math.sqrt(sum((v-mx)**2 for v in x)*sum((v-my)**2 for v in y));rho=sum((u-mx)*(v-my) for u,v in zip(x,y))/den if den else None
    orderA=sorted(range(len(ids)),key=lambda i:(-a[i],ids[i]));orderB=sorted(range(len(ids)),key=lambda i:(-b[i],ids[i]));inversions=0;ties_changed=0
    for i in range(len(ids)):
        for j in range(i):
            d1=a[i]-a[j];d2=b[i]-b[j]
            inversions+=int(d1*d2<0);ties_changed+=int((d1==0)!=(d2==0))
    top={}
    for k in [4,8,12]:
        A=[ids[i] for i in orderA[:k]];B=[ids[i] for i in orderB[:k]]
        top[str(k)]={'intersection':len(set(A)&set(B)),'set_identical':set(A)==set(B),'order_identical':A==B,'old':A,'new':B}
    return {'spearman_with_average_ties':rho,'strict_pairwise_rank_inversions':inversions,'tie_relationships_changed':ties_changed,'full_order_identical':orderA==orderB,'topK':top}

def function_calls(path,function):
    tree=ast.parse(path.read_text(encoding='utf-8'));node=next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==function)
    return sorted(set(ast.unparse(n.func) for n in ast.walk(node) if isinstance(n,ast.Call)))

def main():
    P.verify();a=P.RUN/'seeds/seed20261108/attempt01';b=P.RUN/'seeds/seed20261108/attempt02';old=read_json(a/'prediction.json');new=read_json(b/'prediction.json');assert old['origin_full_state_hash']==new['origin_full_state_hash']
    stage={};file_comparisons={}
    for name in ['nll_prefix.json','nll_predictor_virtual1.json']:
        A=read_json(a/name);B=read_json(b/name);assert [r['episode_id'] for r in A['rows']]==[r['episode_id'] for r in B['rows']]
        stage[name]={k:stats([r[k] for r in A['rows']],[r[k] for r in B['rows']]) for k in P.SEGMENTS}
        file_comparisons[name]={'file_bytes_equal':(a/name).read_bytes()==(b/name).read_bytes(),'top_level_time_equal':A['time']==B['time'],'state_hash_equal':A['state_hash']==B['state_hash'],'row_payload_equal':A['rows']==B['rows']}
    prediction_stats={};rank={}
    for kind in ['initial','delta','risk']:
        prediction_stats[kind]={}
        for role,ids in [('candidates',sorted(r['episode_id'] for r in read_jsonl(P.DATA/'candidate.jsonl'))),('probes',sorted(r['episode_id'] for r in read_jsonl(P.DATA/'dev.jsonl'))),('all',sorted(old['rows']))]:
            prediction_stats[kind][role]={k:stats([old['rows'][e][kind][k] for e in ids],[new['rows'][e][kind][k] for e in ids]) for k in P.SEGMENTS}
            if kind=='risk':rank[role]={k:rankings(ids,[old['rows'][e][kind][k] for e in ids],[new['rows'][e][kind][k] for e in ids]) for k in ['call','tool_name','args','final','all']}
    traces=[read_jsonl(p/'updates.jsonl')[0] for p in [a,b]];fs=ROOT/'fac_tinyagent/p7_fullstate_v2_20261115.py';tree=ast.parse(fs.read_text());cap=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='capture');ret=next(n for n in ast.walk(cap) if isinstance(n,ast.Return));fields=[k.value for k in ret.value.keys]
    sources={str(p.relative_to(ROOT)):sha256_file(p) for p in [fs,ROOT/'fac_tinyagent/replay_train.py',ROOT/'fac_tinyagent/sft/train.py',ROOT/'fac_tinyagent/sft/dataset.py',ROOT/'fac_tinyagent/utils.py',ROOT/'fac_tinyagent/p13_phase0b_20261118.py']}
    coverage={'captured_state_fields':fields,'covered':['all requires_grad parameters (here LoRA)','optimizer.state_dict','scaler.state_dict','Python/NumPy/torch CPU/CUDA RNG','all named module training flags','optimizer.initialized when present'],'not_covered':['frozen non-LoRA weights and model buffers','bitsandbytes Params4bit quant_state/scales/codebooks and other non-trainable serialized quantization state','model.config/use_cache/attention implementation, actual autocast compute dtype','dropout p and other module attributes beyond training flags','CUDA/bitsandbytes hidden/global workspaces/optimizer manager/kernel choices','TF32/float32 matmul precision, cuDNN flags, deterministic-algorithms settings, SDPA backend policy','process environment and initialization timing such as CUBLAS_WORKSPACE_CONFIG/PYTHONHASHSEED','model loading allocation/cache history'], 'Engine_init_calls':function_calls(ROOT/'fac_tinyagent/p13_phase0b_20261118.py','__init__'),'load_prefix_calls':function_calls(ROOT/'fac_tinyagent/replay_train.py','load_prefix'),'load_base_model_calls':function_calls(ROOT/'fac_tinyagent/sft/train.py','load_base_model'),'note':'Static coverage check only. Does not inspect either dead process historical runtime flags or prove an operator nondeterministic.'}
    config=read_json(ROOT/'runs_phase2/A_seed20261108/config.json');base=Path(config['model_name_or_path']);basecfg=read_json(base/'config.json') if (base/'config.json').exists() else {}
    config_relevant={'model_name_or_path':config['model_name_or_path'],'quantization':config['quantization'],'lora':config['lora'],'training':config['training'],'base_config_attention_dropout':basecfg.get('attention_dropout'),'base_config_torch_dtype':basecfg.get('torch_dtype',basecfg.get('dtype')),'base_config_attn_implementation':basecfg.get('_attn_implementation'),'base_config_sha256':sha256_file(base/'config.json') if (base/'config.json').exists() else None}
    # Source contract: one shared feature/mask file, single-row collator, fixed batch list.
    data_audit={'frozen_features_masks_sha256':sha256_file(P.DATA/'features_masks.json'),'frozen_batches_sha256':sha256_file(P.DATA/'batches.json'),'first_batch_episode_ids':[r['episode_id'] for r in read_json(P.DATA/'batches.json')['20261108'][0]],'probe_and_candidate_order_source':'same frozen candidate.jsonl + dev.jsonl in both attempts','original_prefix_state_hash':old['origin_full_state_hash'],'input_token_lengths_equal':all(old['rows'][e]['input_tokens']==new['rows'][e]['input_tokens'] for e in old['rows']),'NLL_row_order_equal':all(file_comparisons[x]['row_payload_equal'] or [r['episode_id'] for r in read_json(a/x)['rows']]==[r['episode_id'] for r in read_json(b/x)['rows']] for x in file_comparisons)}
    out={'time':P.now(),'scope':'one CPU-only JSON and static-code investigation; zero GPU model loads/updates/generation; no new attempt/threshold changes','file_level_vs_payload_comparison':file_comparisons,'NLL_segment_difference_stats':stage,'prediction_difference_stats':prediction_stats,'risk_rankings':rank,'state_coverage':coverage,'config_source':config_relevant,'same_frozen_inputs':data_audit,'virtual_update_hashes':traces,'source_hashes':sources,'strict_row_equality_failed':old['rows']!=new['rows'],'no_complete_forecast_endpoint_available':True,'attempt_budget_remaining_seed08':0}
    jsonpath=P.RUN/'CPU_DIAGNOSIS_20261119.json';assert not jsonpath.exists();write_json(jsonpath,out)
    mainold=rank['candidates']['call'];mainprobe=rank['probes']['call'];post=stage['nll_predictor_virtual1.json']['call'];delta=prediction_stats['delta']['all']['call'];risk=prediction_stats['risk']['all']['call']
    lines=['# P13 Phase0-B 有界CPU故障核查与交接','',P.now()+'（北京时间）','', '## 真实状态','人工授权后已真实启动attempt02，00:40:23完成预测虚拟一步，随后重建断言失败，00:40:54监督器rc1；没有自然suffix步骤、没有完整预测终点。seed08两次attempt已用尽。所记录LoRA/optimizer/scaler/RNG/modes最后恢复精确、前缀文件hash未变。当前仅做本次CPU核查，未GPU重试、未验收final、未改代码/阈值/协议。','', '## 先纠正一个关键事实','nll_prefix.json的文件字节确实不同（time元数据不同），但其96条row payload全部逐值一致，6段NLL的max/mean差均为0，state_hash也相同。因此“更新前NLL已经数值不同”不受现有JSON支持；不能据文件hash差异错误定位到前向/量化载入。最早保存的可观测差异是虚拟更新后的LoRA/optimizer与NLL。','', '## 数值与排序（只描述，不据此改容差）', '虚拟后call NLL：'+json.dumps(post,ensure_ascii=False),'call ΔNLL：'+json.dumps(delta,ensure_ascii=False),'clipped call risk：'+json.dumps(risk,ensure_ascii=False),'候选call风险：Spearman='+str(mainold['spearman_with_average_ties'])+'，严格成对逆序='+str(mainold['strict_pairwise_rank_inversions'])+'；Top4/8/12交集='+str({k:v['intersection'] for k,v in mainold['topK'].items()}),'探针call风险：Spearman='+str(mainprobe['spearman_with_average_ties'])+'，严格成对逆序='+str(mainprobe['strict_pairwise_rank_inversions'])+'；Top4/8/12交集='+str({k:v['intersection'] for k,v in mainprobe['topK'].items()}),'全部分段max/mean/median、每段排序/ties/TopK名单见CPU_DIAGNOSIS_20261119.json。没有完整终点，不能判断AUROC/AUPRC或最终科学结论是否受影响；排序近似稳定也不等于精确状态重建通过。','', '## hash覆盖及可支持的解释','FS.capture仅收requires_grad参数、optimizer/scaler、四类RNG、named module.training和optimizer.initialized。冻结非LoRA参数、buffer与4bit quant_state/scales/codebooks不在此hash。因而origin_full_state_hash一致不是整个量化模型与计算环境的完整同一性证明。','模块training和RNG确实覆盖；dropout p及模型config/attention/use_cache、实际autocast dtype、TF32、cuDNN/SDPA/deterministic算法开关与进程环境未序列化。load_base_model未显式固定attention backend；prepare_model_for_kbit_training和gradient checkpointing启用，checkpoint默认use_reentrant警告存在。该路径未显式调用torch.use_deterministic_algorithms。utils.set_seed虽有cuDNN/CUBLAS设置，但Engine只恢复prefix RNG，并不调用它；且若事后才设PYTHONHASHSEED/CUBLAS也不能替代进程初始化前合同。','同一冻结batch顺序、mask、分母、单样本collator与输入token长度，且更新前各段完全一致，削弱“换题/错mask/重排/前向已漂移”的解释。不能排除反向或AdamW/量化优化器内部非确定性、未记录后端/隐藏状态、dropout执行历史或加载历史效应；现有日志没有梯度hash或运行时后端快照，不能唯一归因。模块模式/RNG初始化错误亦不能仅凭后验猜测；记录的前缀覆盖部分相同是反证约束。','两次power.limit不同仅是资源快照，不证明因果；不建议为验证这个猜测再改功率试跑。','', '## 严格断言的解释','断言验证的是预测表逐值重建，不是论文性能阈值。它确实发现了更新轨迹没有按合同逐位复现（LoRA/optimizer hash也不同），不是仅JSON时间戳触发。变化的科学影响目前未知；不能把严格失败直接升级为方法失效，也不能因TopK看似相近就悄悄epsilon放行。','', '## 最小修复选项（均未获重跑授权）','1. 首选操作性方案：持久化前缀、预测虚拟步后的LoRA/optimizer/scaler/RNG/modes检查点，并记录量化基座/quant_state、模型与后端设置指纹；恢复时加载保存状态，不再靠重新执行浮点更新重建。同一虚拟θv可在前缀评测后恢复作为自然step1，这会改变物理更新复用/成本账本，必须在操作性修订里明说，不能当原协议已如此执行。','2. 如需先定位重建性：单独明确授权一次工程诊断，建议固定1种子/1批次、同一内存前缀做2次临时更新（最多2 optimizer步、16 backward样本），前后各用固定8条训练侧候选NLL（合计32 forward），0 generate，记录梯度/参数/optimizer/RNG/量化与后端指纹并恢复。它不是新增科学样本，也不是把第三attempt改名后偷偷续跑。','3. 若用户选择继续原实验，需要明确批准一次性操作性修订和新的有界attempt额度（例如仅允许seed08一次额外attempt，原两次保持失败记录）；数据、主终点、门槛仍锁定。若保留原33步合同，必须先证明数值重建可行；若采用保存θv避免重算，须重新冻结物理步骤/成本合同。若明确改为保存θv并复用为step1，剩余三种子一次性全程预计30临时optimizer步/240 backward样本、576 NLL forward样本、432两回合episodes/864 generate，已完成校准24题仍复用；若另批准上述工程诊断，再单列2临时步/16 backward/32 NLL forward。原两失败虚拟步、25条部分生成及未完成调用继续计总成本。该预算与step1复用均须用户明示，不由“继续完成”推定。','不建议现在仅放宽float容差、仅关闭dropout、换attention/优化器/学习率或换种子救结果；这些会改变合同或方法，需新的明确修订，不能自动执行。','', '## 文件与权限边界','原attempt01/02、STOP及整卷guard归档不变；旧报告不覆盖。新增机器审计runs_ext_p13_phase0b/CPU_DIAGNOSIS_20261119.json。当前不启动任何新attempt/GPU定位，不push/发GPT，不跑成功态final。']
    report=ROOT/'EXT_HANDOVER_20261119_p13_phase0b_cpu_diagnosis_ZH.md';assert not report.exists();report.write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'prefix_payload_equal':file_comparisons['nll_prefix.json']['row_payload_equal'],'prefix_file_bytes_equal':file_comparisons['nll_prefix.json']['file_bytes_equal'],'post_virtual_call':post,'call_delta':delta,'candidate_call_ranking':{k:mainold[k] for k in ['spearman_with_average_ties','strict_pairwise_rank_inversions','full_order_identical']},'candidate_call_topK_overlap':{k:v['intersection'] for k,v in mainold['topK'].items()},'probe_call_ranking':{k:mainprobe[k] for k in ['spearman_with_average_ties','strict_pairwise_rank_inversions','full_order_identical']},'probe_call_topK_overlap':{k:v['intersection'] for k,v in mainprobe['topK'].items()},'report':str(report.relative_to(ROOT))},ensure_ascii=False))
if __name__=='__main__':main()
