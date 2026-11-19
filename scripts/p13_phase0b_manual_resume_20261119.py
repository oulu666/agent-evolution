"""ONE-TIME manual authorization for the exact 2026-11-18 Apex STOP; no future unlatch."""
import datetime,hashlib,json,os,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent import p13_phase0b_20261118 as P
from fac_tinyagent.utils import read_json,read_jsonl,sha256_file
STOP=P.LOG/'STOP';EXPECTED='2aa5dbf9caef93164fd0db60f169e69fe13cd6e486b1e5369d3e84da4cfca0de'
AUTH='允许归档并解除本次游戏触发的STOP，继续完成同一轮测评。'
AUTH_TIME='2026-11-19 00:35 +0800'
def exclusive(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def main():
    time.tzset();P.verify();assert not (P.RUN/'COMPLETE.json').exists()
    original=STOP.read_bytes();assert hashlib.sha256(original).hexdigest()==EXPECTED,'Unknown/new STOP; manual authorization does NOT apply'
    obj=json.loads(original);assert obj['time']=='2026-11-18 22:58:35 +0800' and obj['reason']['all_apex_process_count']==1 and obj['reason']['STOP']==[]
    before_stat=STOP.stat();state=P.inspect({os.getpid()})
    assert not state['windows']['game'] and state['all_apex_process_count']==0 and state['power_limit_W']>=60
    assert not state['other_compute'] and not state['other_project_python'];assert state['STOP']==['runs_ext_p13_phase0b/logs/STOP'],'Another STOP also present'
    freeze=read_json(P.RUN/'formal_freeze.json')
    for rel,h in freeze['hashes'].items():assert sha256_file(ROOT/rel)==h
    reused=[]
    for seed in P.SEEDS:
        c=P.RUN/'calibration'/f'seed{seed}'/'COMPLETE.json';receipt=read_json(c);out=ROOT/receipt['attempt'];done=read_json(out/'prefix_calibration/COMPLETE.json');rs=read_jsonl(out/'prefix_calibration/results.jsonl')
        assert len(rs)==8 and sha256_file(out/'prefix_calibration/results.jsonl')==done['results_sha256'] and read_json(out/'restoration.json')['exact']
        reused.append({'seed':seed,'calibration_n':8,'COMPLETE_sha256':sha256_file(c)})
    attempts={str(s):[str(p.relative_to(ROOT)) for p in sorted((P.RUN/'seeds'/f'seed{s}').glob('attempt[0-9][0-9]'))] for s in P.SEEDS}
    assert len(attempts['20261108'])==1 and all(len(v)<2 for v in attempts.values()),'Attempt limit prevents continuation'
    old=P.RUN/'seeds/seed20261108/attempt01';restore=read_json(old/'restoration.json');assert restore['exact'] and restore['prefix_file_unchanged']
    partial=read_jsonl(old/'node00/results.jsonl');assert not (old/'node00/COMPLETE.json').exists();oldcost=read_json(old/'cost.json')
    stamp=time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:12];folder=P.RUN/'manual_resume'/stamp;folder.mkdir(parents=True,exist_ok=False)
    archive=P.LOG/('STOP.apex_20261118_225835.authorized_'+stamp);assert not archive.exists()
    receipt={'time':P.now(),'authorization_quote':AUTH,'authorization_time_Beijing':AUTH_TIME,'scope':'Only exact historical Apex STOP below; no future STOP authorization; same frozen Phase0B; no change to data/method/gates','original_STOP_path':str(STOP.relative_to(ROOT)),'original_STOP_sha256':EXPECTED,'original_STOP_content':obj,'original_STOP_text':original.decode('utf-8'),'original_STOP_mtime_ns':before_stat.st_mtime_ns,'original_STOP_mtime_Beijing':datetime.datetime.fromtimestamp(before_stat.st_mtime,datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'archive_path':str(archive.relative_to(ROOT)),'fresh_preflight_before_unlatch':state,'frozen_manifest_sha256':sha256_file(P.DATA/'manifest.json'),'formal_freeze_sha256':sha256_file(P.RUN/'formal_freeze.json'),'reused_complete_calibrations':reused,'attempts_before_resume':attempts,'partial_node00_rows_preserved_not_reused_as_complete':len(partial),'prior_interrupted_cost':oldcost,'reconstruction_plan':{'seed08_attempt02_only_remaining_attempt':True,'recompute_NLL_forward_samples':192,'recompute_predictor_virtual_backward_samples':8,'recompute_predictor_virtual_steps':1,'compare_full_prefix_hash_and_prediction_rows_exactly':True,'partial_node00_completed_episodes_to_repeat':len(partial),'reuse_complete_calibration_episodes':24,'no_completed_suffix_nodes_available':True,'not_a_new_independent_experiment':True}}
    exclusive(folder/'authorization_before_archive.json',receipt)
    assert STOP.stat().st_mtime_ns==before_stat.st_mtime_ns and STOP.read_bytes()==original,'STOP changed; abort without unlatching'
    STOP.rename(archive)
    if archive.read_bytes()!=original:
        if not STOP.exists():archive.rename(STOP)
        raise RuntimeError('Concurrent STOP change; not resumed')
    exclusive(folder/'archive_receipt.json',{'time':P.now(),'original_sha256':EXPECTED,'archive_sha256':sha256_file(archive),'archive_path':str(archive.relative_to(ROOT)),'original_bytes_and_mtime_preserved':archive.stat().st_mtime_ns==before_stat.st_mtime_ns,'authorization_receipt':str((folder/'authorization_before_archive.json').relative_to(ROOT)),'future_STOP_must_remain_sticky':True})
    (folder/'RESUME_OPERATION_ZH.md').write_text('# 本次人工恢复操作说明\n\n'+P.now()+' 北京时间\n\n用户在2026-11-19 00:35北京时间明确授权：'+AUTH+'\n\n仅对原SHA256 '+EXPECTED+'、2026-11-18 22:58:35由Apex守卫生成的STOP执行一次完整重命名归档；原字节和mtime保留，归档不覆盖。冻结协议不改写，此操作凭据记录用户对停止条款的一次人工例外，不授予未来自动清STOP权限。\n\n继续相同冻结Phase0B；三种子校准完整复用，seed08重建进入原定attempt02，不新增独立实验。未完成的node00 '+str(len(partial))+'/48原样保留但不能当完整节点复用。192个NLL forward、8个虚拟backward和1个虚拟optimizer step会为确定性验证重新计算，原失败成本与重建成本分attempt记录；最终需额外成本分类审计。后续新STOP/游戏/低功耗仍立即停止，绝不再次用本授权解除。\n',encoding='utf-8')
    P.verify();fresh=P.inspect({os.getpid()});exclusive(folder/'post_archive_preflight.json',fresh)
    if not fresh['safe']:
        exclusive(folder/'NOT_STARTED.json',{'time':P.now(),'reason':fresh});print('Resume stopped by fresh safety inspection',flush=True);return 75
    print(P.now(),'AUTHORIZED ONE-TIME RESUME RECEIPT',str(folder.relative_to(ROOT)),flush=True)
    exclusive(P.RUN/'manual_resume_active_receipt.json',{'time':P.now(),'receipt_dir':str(folder.relative_to(ROOT)),'archive_path':str(archive.relative_to(ROOT)),'authorization_time_Beijing':AUTH_TIME})
    return P.supervise()
if __name__=='__main__':sys.exit(main())
