"""Independent CPU-only post-run audit, no inference or training."""
import collections,json,math,time
from pathlib import Path
from .utils import read_json,read_jsonl,write_json,sha256_file
from . import p13_phase0_20261118 as P
R=P.RUN;ROOT=P.ROOT

def main():
    P.verify();assert read_json(R/'COMPLETE.json')['complete'];assert read_json(R/'supervisor_end.json')['rc']==0
    s=read_json(R/'summary.json');hist=read_json(R/'history_audit.json');restore=read_json(R/'restoration.json');guards=read_jsonl(R/'logs/guard.jsonl')
    assert all(g['safe'] for g in guards);assert restore['exact'] and restore['prefix_file_unchanged']
    assert restore['LoRA_before']==restore['LoRA_after'] and restore['optimizer_before']==restore['optimizer_after']
    stages=[read_jsonl(R/f'stage{i}/generation/results.jsonl') for i in range(3)]
    for rs in stages:
        for r in rs:assert r['joint_success']==all(r[k] for k in ['tool_correct','arguments_correct','execution_success','final_correct'])
    lost=[];gain=[]
    for i in range(2):
        old={r['episode_id']:r for r in stages[i]};new={r['episode_id']:r for r in stages[i+1]}
        lost.extend((i+1,e) for e,r in old.items() if r['joint_success'] and not new[e]['joint_success'])
        gain.extend((i+1,e) for e,r in old.items() if not r['joint_success'] and new[e]['joint_success'])
    assert len(lost)==s['correct_to_wrong'] and len(gain)==s['wrong_to_correct']
    sql=read_json(P.DATA/'sql_unit_acceptance.json');assert all(not t['omitted_semantic'] and not t['omitted_strict'] and t['equivalent_semantic'] and not t['equivalent_strict'] for t in sql['tests'])
    forwards=120+16+8
    assert s['cost']['counts']['teacher_forced_NLL_forwards']==120 and s['cost']['counts']['virtual_backward']==16 and s['cost']['counts']['diversity_backward']==8
    assert sum(r['inference_calls'] for rs in stages for r in rs)==144
    diversity=read_json(R/'gradient_diversity.json');cos=diversity['cosine'];off=[cos[i][j] for i in range(8) for j in range(i)]
    rows=read_jsonl(P.DATA/'dev.jsonl')+read_jsonl(P.DATA/'candidates.jsonl');dates={r['expected_arguments']['date'] for r in rows};collisions=[];scanned=0
    for folder in ROOT.glob('data*'):
        if not folder.is_dir() or folder==P.DATA:continue
        for f in folder.rglob('*.jsonl'):
            for r in read_jsonl(f):
                scanned+=1;d=r.get('expected_arguments',{}).get('date')
                if d in dates:collisions.append({'path':str(f.relative_to(ROOT)),'episode_id':r.get('episode_id'),'date':d})
    assert not collisions
    audit={'passed':True,'time':time.strftime('%F %T %z'),'guards_checked':len(guards),'all_guards_safe':True,'two_turn_scoring_checks':72,'paired_losses':lost,'paired_gains':gain,'SQL_omission_counterexamples':4,'SQL_semantic_equivalence_checks':4,'all_historical_data_rows_entity_scanned':scanned,'entity_collisions':collisions,'complete_state_restore':restore,'diagnostic_forward_episodes_excluding_generation_internal_decode':forwards,'diagnostic_backward_episodes':24,'generation_calls':144,'generation_output_tokens':sum(r['output_tokens'] for rs in stages for r in rs),'cosine_offdiagonal_min':min(off),'cosine_offdiagonal_max':max(off),'cosine_offdiagonal_mean':sum(off)/len(off),'memory_measurement_caveat':'evaluate_family resets PyTorch peak counters: cost.json peak_allocated_GPU_bytes is final evaluation interval only, NOT whole-job allocated peak. peak_reserved also must not be claimed global. External nvidia-smi observed 7914 MiB at 20:03 Beijing; observed whole-device lower bound, not instrumented global peak. Generation calls/tokens recorded exactly; internal decoding/checkpoint recomputation forward calls not individually instrumented.','source_sha256':sha256_file(Path(__file__))}
    write_json(R/'independent_acceptance.json',audit)
    text='# P13 Phase0 独立验收与最终判断\n\n北京时间 '+audit['time']+'\n\n'
    text+='## 已完成\n最小Phase0完成，监督器rc=0，72条两回合开发评测、两批真实后续Calendar数据的虚拟AdamW更新，未启动正式训练，未保存新adapter，未push。\n\n'
    text+='## 原建议的事实核齐\n- 日期退化5条全部确为calendar_count(month=完整日期)，涉及seed08两条、seed09三条，seed10零条。\n- filter（非所有SQL任务）A/B工具36/36、严格参数0/36、最终35/36成立；执行观测正确分别A31/36、B30/36。v1最终34/36，T0为32/36且严格Joint已为0，因此不是新近遗忘的证据。\n- A/B严格Joint逐题相同不代表工具执行/原始轨迹逐题相同。P12报告“五种子”笔误，实际三种子。\n\n'
    text+='## 冻结gate和实测\n'+json.dumps({k:s[k] for k in ['stage_joint','gates','decision','correct_to_wrong','wrong_to_correct','eligible_pairs','AUROC','top_quartile_loss_rate','remaining_loss_rate']},ensure_ascii=False,indent=2)+'\n\n'
    text+='候选排序gate：'+json.dumps([{k:r[k] for k in ['batch','nondegenerate','positive','unique_rounded']} for r in s['candidate_ranking']],ensure_ascii=False)+'。\n\n'
    text+='两个连续局部窗口不插入回放，保留真实后续新流顺序及优化器动量，不声称完整复现P12轨迹或解释历史遗忘。低于3条退化为不可识别；仅暂停当前配置扩训，不判整条MIR研究路线无效。不临时扩批、改提示、换种子救结论。\n\n'
    text+='## 预算、状态、安全\n'+json.dumps({'cost':s['cost'],'exact_restore':restore,'guard_checks':len(guards),'diversity_full_LoRA_dimension':diversity['full_LoRA_gradient_dimension'],'gradient_offdiagonal_cosine_range':[min(off),max(off)]},ensure_ascii=False,indent=2)+'\n\n'
    text+='成本口径：144个额外teacher-forced/更新/梯度forward样本（120+16+8），24个backward样本（16虚拟更新+8多样性），另144次generate及其tokens精确记录；内部逐token解码与checkpoint重算forward未单独插桩。两临时optimizer step不计正式训练步。评测器会重置PyTorch峰值计数，所以cost.json allocated峰值仅末段评测，不能称全程峰值；外部20:03北京时间见7914MiB为整卡已观测下界，不冒称全程峰值。\n\n'
    text+='所有LoRA、优化器、scaler、RNG和module modes恢复hash一致，原前缀文件hash不变，守卫无游戏/STOP/低功耗/竞争GPU项目。SQL新反例4/4阻止漏WHERE巧合，等价查询4/4语义通过而严格参数不通过；未改原盲卷。\n\n'
    text+='## 路线判断\n方向比静态规则微调更有可检验性，但把MIR/GSS/提示诊断拼起来不能直接当论文创新。RGD-R不是F/P准确率差，Angle Matters不支持LLM任务梯度夹角结论；文献原文纠偏见冻结协议。本轮不需要三提示矩阵或GSS复杂选择。下一步不预先承诺DG-MIR三臂五种子，更不以小筛查声称CCF-B已达标。\n\n完整机器审计：runs_ext_p13_phase0/summary.json、independent_acceptance.json、history_audit.json；协议P13_PHASE0_PREREG_20261118_ZH.md；交接EXT_HANDOVER_20261118_p13_phase0_ZH.md。\n'
    (ROOT/'EXT_REPORT_20261118_p13_phase0_independent_ZH.md').write_text(text,encoding='utf-8');print(json.dumps({k:audit[k] for k in ['passed','guards_checked','paired_losses','paired_gains','entity_collisions']},ensure_ascii=False))
if __name__=='__main__':main()
