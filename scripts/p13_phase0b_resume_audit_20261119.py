"""CPU-only failure/reconstruction audit. Never changes frozen protocol or launches GPU work."""
import collections,json,math,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent import p13_phase0b_20261118 as P
from fac_tinyagent.utils import read_json,read_jsonl,write_json,sha256_file

def differences(left,right):
    assert set(left)==set(right);summary={};details=[]
    for key in ['call','tool_name','args','call_other','final','all']:
        ds=[(e,float(left[e][key]),float(right[e][key])) for e in left if left[e][key]!=right[e][key]]
        summary[key]={'different_rows':len(ds),'total_rows':len(left),'max_abs_difference':max((abs(a-b) for e,a,b in ds),default=0.),'max_symmetric_relative_difference':max((abs(a-b)/max(abs(a),abs(b),1e-12) for e,a,b in ds),default=0.)}
        details.extend({'episode_id':e,'segment':key,'old':a,'reconstructed':b,'difference':b-a} for e,a,b in ds)
    return {'summary':summary,'differences':details}

def main():
    P.verify();raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],timeout=20).decode().strip();assert not raw,'GPU process remains; no concurrent audit'
    end=read_json(P.RUN/'supervisor_end.json');assert end['rc']==1
    active=read_json(P.RUN/'manual_resume_active_receipt.json');folder=ROOT/active['receipt_dir'];authorization=read_json(folder/'authorization_before_archive.json');archive=ROOT/active['archive_path'];assert sha256_file(archive)==authorization['original_STOP_sha256']
    assert not (P.LOG/'STOP').exists(),'New STOP retained; inspect rather than continue'
    rotation=read_json(folder/'guard_session_rotation_receipt.json');archived_guard=Path(rotation['archive_path'])
    # Convert the Windows receipt path to this WSL filesystem, without guessing another target.
    if not archived_guard.exists():
        expected_name=rotation['archive_path'].replace('\\','/').split('/')[-1];archived_guard=P.LOG/expected_name
    assert sha256_file(archived_guard)==rotation['archive_sha256']
    historical=read_jsonl(archived_guard);current=read_jsonl(P.LOG/'guard.jsonl');unsafe=[g for g in historical+current if not g['safe']]
    assert len(unsafe)==1 and unsafe[0]==authorization['original_STOP_content']['reason'];assert all(g['safe'] for g in current)
    seedroot=P.RUN/'seeds/seed20261108';attempts=sorted(seedroot.glob('attempt[0-9][0-9]'));assert len(attempts)==2
    old,new=attempts;oldp=read_json(old/'prediction.json');newp=read_json(new/'prediction.json');assert oldp['origin_full_state_hash']==newp['origin_full_state_hash']
    restorations=[read_json(p/'restoration.json') for p in attempts];assert all(r['exact'] and r['prefix_file_unchanged'] and r['before']==r['after'] for r in restorations)
    traces=[read_jsonl(p/'updates.jsonl') for p in attempts];assert all(len(t)==1 and t[0]['kind']=='predictor_virtual' for t in traces)
    comparisons={}
    for filename in ['nll_prefix.json','nll_predictor_virtual1.json']:
        a=read_json(old/filename);b=read_json(new/filename);comparisons[filename]={'state_hash_old':a['state_hash'],'state_hash_reconstructed':b['state_hash'],'same_state_binding':a['state_hash']==b['state_hash'],**differences({r['episode_id']:r for r in a['rows']},{r['episode_id']:r for r in b['rows']})}
    prediction_differences={}
    for kind in ['initial','delta','risk']:
        prediction_differences[kind]=differences({e:r[kind] for e,r in oldp['rows'].items()},{e:r[kind] for e,r in newp['rows'].items()})
    costs=[];total=collections.Counter()
    for path in sorted(P.RUN.glob('*/seed*/attempt*/cost.json')):
        c=read_json(path);costs.append({'path':str(path.relative_to(ROOT)),**c})
        for k,v in c['counts'].items():
            if k.startswith('peak_'):total[k]=max(total[k],v)
            else:total[k]+=v
    newcost=read_json(new/'cost.json');oldcost=read_json(old/'cost.json')
    starts=read_jsonl(old/'calls_started.jsonl');completed=read_jsonl(old/'calls_completed.jsonl')
    complete_calibrations=[read_json(P.RUN/'calibration'/f'seed{s}'/'COMPLETE.json') for s in P.SEEDS]
    assert len(read_jsonl(old/'node00/results.jsonl'))==25 and not (old/'node00/COMPLETE.json').exists();assert not (new/'node00').exists()
    assert not any((P.RUN/'seeds'/f'seed{s}'/'COMPLETE.json').exists() for s in P.SEEDS)
    result={'time':P.now(),'audit_consistency_passed':True,'evaluation_completed':False,'status':'ENGINEERING_STOP_RECONSTRUCTION_MISMATCH_ATTEMPT_CAP','supervisor_exit':end,'authorization_and_original_STOP_archive_verified':True,'original_protocol_and_all_frozen_hashes_unchanged':True,'original_full_recorded_prefix_state_equal':oldp['origin_full_state_hash']==newp['origin_full_state_hash'],'restoration_receipts':restorations,'virtual_update_state_comparison':{'old':traces[0][0],'reconstructed':traces[1][0],'LoRA_hash_equal':traces[0][0]['LoRA_hash']==traces[1][0]['LoRA_hash'],'optimizer_hash_equal':traces[0][0]['optimizer_hash']==traces[1][0]['optimizer_hash'],'full_recorded_state_hash_equal':traces[0][0]['state_hash']==traces[1][0]['state_hash']},'NLL_comparisons':comparisons,'prediction_comparisons':prediction_differences,'complete_calibrations_reused':3,'complete_calibration_episodes_reused':24,'old_incomplete_node00_rows_preserved':25,'old_node00_completed_inference_calls':len(completed),'old_node00_started_inference_calls':len(starts),'unfinished_generation_cost_not_assumed_zero':True,'new_attempt02_generation_episodes':newcost['counts'].get('generation_episodes',0),'completed_natural_suffix_steps':0,'completed_primary_forecast_endpoint_pairs':0,'seed08_attempts_used':2,'seed08_attempt_cap':2,'no_third_attempt_started':True,'extra_reconstruction_cost_actual':newcost,'all_attempt_costs_including_calibration_and_failed_work':costs,'cost_totals':dict(total),'historical_guard_rows':len(historical),'current_resume_guard_rows':len(current),'historical_unsafe_rows':1,'known_historical_Apex_stop_preserved_and_authorized':True,'new_unsafe_rows':0,'guard_history_preservation_receipt':str((folder/'guard_session_rotation_receipt.json').relative_to(ROOT)),'experimental_conclusion':'MIR predictive ability not evaluated; this is engineering reconstruction failure, not zero-event or MIR failure evidence. No AUROC/AUPRC or method promotion conclusion.','root_cause_limit':'Same recorded LoRA/optimizer/scaler/RNG/modes state does not guarantee bitwise numerical replay. Initial NLL and post-update state comparisons localize the failure but do not uniquely establish CUDA kernels, quantized base state or backend configuration as root cause. No tolerance relaxation or new GPU diagnostic was attempted.'}
    target=folder/'reconstruction_failure_audit.json';assert not target.exists();write_json(target,result)
    terminal=P.RUN/'TERMINATED_ENGINEERING_20261119.json';assert not terminal.exists();write_json(terminal,{k:result[k] for k in ['time','status','evaluation_completed','seed08_attempts_used','seed08_attempt_cap','completed_natural_suffix_steps','experimental_conclusion']})
    text='# P13 Phase0-B 人工恢复与工程终止报告\n\n北京时间 '+result['time']+'\n\n## 实际执行\n用户00:35明确授权后，重新确认无Apex、90W、无竞争任务、冻结hash通过；00:37:49将唯一已核实的22:58:35 Apex STOP完整归档并保留原字节/mtime/hash和人工授权。00:37:54真实启动supervisor369/worker503，seed08进入原定attempt02；00:40:23完成一步预测虚拟更新。不是只做准备。\n\n## 终止原因\n00:40:54监督器rc=1：冻结代码的`nondeterministic forecast reconstruction`断言触发。原记录前缀state hash一致，但预测表不逐值相等，且虚拟一步后的LoRA/optimizer hash也与attempt01不同。不能简单当小数误差而放宽合同。attempt02已消耗，按每种子最多2attempt停止；没有第三次尝试，没有改门槛、分数容差、数据或方法。\n\n初始NLL差异（发生于更新前）：\n'+json.dumps(comparisons['nll_prefix.json']['summary'],ensure_ascii=False,indent=2)+'\n\n虚拟后NLL差异：\n'+json.dumps(comparisons['nll_predictor_virtual1.json']['summary'],ensure_ascii=False,indent=2)+'\n\n这说明记录的可训练/优化器/RNG状态一致仍不足以保证数值重建；不足以唯一归因于CUDA、量化基座或其它后端设置。本轮不追加GPU定位实验，不用事后容差救结果。\n\n## 保存、复用和成本\n三种子完整校准24题、formal_freeze原样复用；旧node00实际有25/48完整行（日志上一里程碑24），未作为完整节点复用；另1个开始但未完成的generate原记录保留，不能记为零。attempt02在新node00之前即失败，未运行自然suffix，未产生任何完整主终点配对。\n\n额外重建成本：\n'+json.dumps(newcost,ensure_ascii=False,indent=2)+'\n\n所有尝试含校准/中断/重建总成本：\n'+json.dumps(dict(total),ensure_ascii=False,indent=2)+'\n\n两个attempt都将LoRA、optimizer、scaler、RNG、module modes精确恢复为前缀，原前缀文件hash不变。GPU进程已退出。\n\n## 守卫日志说明\n原guard日志整体分卷而非过滤：'+str(archived_guard.relative_to(ROOT))+'，保留'+str(len(historical))+'条原始行和唯一已授权的Apex停止行，hash收据在人工恢复目录。当前会话guard.jsonl包含'+str(len(current))+'条且无新unsafe；守卫未禁用，也没有解除任何未来STOP。分卷是恢复会话的操作日志边界，不是改实验数据或统计gate。\n\n## 研究结论\n本轮是工程重建失败，尚未完成MIR预测测评；不能报“零遗忘事件”，也不能据此判MIR有效/无效。未达到正式final验收前提（supervisor rc0、完整三种子），因此不运行成功态final、不生成COMPLETE假标记。原冻结attempt额度已耗尽，不自动补seed或开启新轮。\n\n机器审计：'+str(target.relative_to(ROOT))+'；终止标记：runs_ext_p13_phase0b/TERMINATED_ENGINEERING_20261119.json。原日志、两个attempt、人工恢复receipt及失败证据全部保留。未push、未发GPT。\n'
    report=ROOT/'EXT_REPORT_20261119_p13_phase0b_resume_failure_ZH.md';assert not report.exists();report.write_text(text,encoding='utf-8')
    handover=ROOT/'EXT_HANDOVER_20261119_p13_phase0b_resume_failure_ZH.md';assert not handover.exists();handover.write_text('# P13 Phase0B终止交接\n\n'+P.now()+' 北京时间\n\n状态ENGINEERING_STOP_RECONSTRUCTION_MISMATCH_ATTEMPT_CAP；supervisor rc1，GPUworker已退出；seed08两次attempt均已使用，不允许自动第三次。\n\n报告EXT_REPORT_20261119_p13_phase0b_resume_failure_ZH.md；机器审计'+str(target.relative_to(ROOT))+'；终止标记runs_ext_p13_phase0b/TERMINATED_ENGINEERING_20261119.json。原冻结代码/数据/门槛未改。不得把工程停止当MIR零事件或性能失败。\n\n完整校准已复用；自然suffix 0步，完整终点0；两个attempt前缀恢复hash通过，但虚拟更新预测不满足逐值重建。没有启动后续pilot。本授权只解除原22:58:35 Apex STOP，不适用于未来STOP。\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'evaluation_completed':False,'restoration_exact':all(r['exact'] for r in restorations),'initial_NLL_comparison':comparisons['nll_prefix.json']['summary'],'cost_extra_reconstruction':newcost['counts'],'audit_path':str(target.relative_to(ROOT))},ensure_ascii=False))
if __name__=='__main__':main()
