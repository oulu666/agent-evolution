"""One-shot CPU data freeze. No model runner. All writes exclusive within this directory."""
import hashlib,json,os,resource,subprocess,sys,time
from pathlib import Path
from build_data import HERE,ROOT,save,read,sha,unchanged,now

def main():
    os.environ.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',TZ='Asia/Shanghai');time.tzset()
    started=time.perf_counter();reg=read(HERE/'cpu_regression.json');assert reg['failed']==0
    assert not (HERE/'manifest.json').exists()
    source=[p for p in HERE.iterdir() if p.is_file() and p.suffix in ['.py','.md']]
    save(HERE/'PRE_DATA_LOCK.json',{'time':now(),'meaning':'method, parser, recipes, metrics and independent validator sealed before heldout construction; no heldout outputs exist','source_sha256':{p.name:sha(p) for p in source},'cpu_regression_sha256':sha(HERE/'cpu_regression.json'),'root_seed':2026112102})
    phase=[]
    for script,args in [('build_data.py',['generate']),('validate_data.py',[])]:
        t=time.perf_counter();r=subprocess.run([sys.executable,'-B',str(HERE/script),*args],cwd=ROOT,env=os.environ,capture_output=True,text=True,timeout=120)
        phase.append({'time':now(),'script':script,'argv':args,'rc':r.returncode,'elapsed_seconds':time.perf_counter()-t,'stdout':r.stdout,'stderr':r.stderr})
        print(r.stdout,end='')
        if r.returncode:
            save(HERE/'FREEZE_FAILED.json',{'time':now(),'phases':phase});raise RuntimeError('CPU phase failed; no frozen manifest')
    save(HERE/'cpu_phase_receipts.json',{'phases':phase})
    val=read(HERE/'data_validation.json');assert val['passed'] and val['heldout_selector_executions']==0 and val['new_model_generations']==0
    lock=read(HERE/'PRE_DATA_LOCK.json')
    for name,h in lock['source_sha256'].items():assert sha(HERE/name)==h
    count=unchanged()
    oldmanifest=read(ROOT/'acod_round1_20261121/manifest.json')
    for p,h in oldmanifest['hashes'].items():assert sha(ROOT/p)==h
    save(HERE/'legacy_unchanged.json',{'time':now(),'verified_files':count,'all_equal':True,'round1_file_list_equal':True,'round1_original_reference_hashes_equal':True,'round1_primary_metrics_recomputed':False,'no_old_file_writes':True})
    assert not any(n.split('.')[0] in ['torch','transformers','peft','bitsandbytes'] for n in sys.modules)
    elapsed=time.perf_counter()-started
    cpu=resource.getrusage(resource.RUSAGE_SELF)
    save(HERE/'freeze_receipt.json',{'time':now(),'success':True,'cpu_freeze_wall_seconds':elapsed,'self_user_cpu_seconds':cpu.ru_utime,'self_system_cpu_seconds':cpu.ru_stime,'maxrss_KiB':cpu.ru_maxrss,'new_model_generations':0,'model_imports':0,'training_steps':0,'heldout_selector_runs':0,'CPU_cost_not_zero':True})
    report=f'''# ACOD v2 CPU验收与保留输入冻结报告

时间：{now()}（Asia/Shanghai）。状态：已完成CPU冻结，停在此处。

## 实际验收
- 类型/行为/组合/先验/未来信息接口回归：{reg['tests']}项，PASS {reg['passed']}，FAIL {reg['failed']}；标准库执行{reg['elapsed_seconds']:.6f}秒。包含768个规则×策略模拟器工程案例，不是自然根因gold。
- 独立数据验证：{val['case_checks']}题、{val['view_checks']}视图全部通过；负例{val['negative_checks']}项全部成功拒绝，FAIL 0。
- 开发8题；保留16题、8个基础fixture、2个内容构建谱系（fragment offsets/scope，multiline logical-record assembly）。每族4格×2意图，非功效估计。
- 开发/保留case ID、基础fixture、真实模板交集均0；来源构建根与AST hash独立。共享有限选择/投影语义、类型锚点和变换工具；只称构建family-heldout，不称新工具或现实OOD。
- 先锁源代码/规则/指标/recipe，再生成保留数据；锁见PRE_DATA_LOCK.json。没有在保留集运行selector/模拟器方法或模型，没有自然响应可见。
- gold仅由独立validator自动核对；公开接口拒绝scorer路径。模型消息仅固定system+问题+原始observation，gold/分组/证书/假设预测不进入消息。不是加密或OS权限隔离。
- 历史{count}个资产SHA前后相等；round1文件清单和原manifest引用逐一核对不变。无首轮指标重算、无事后重新报成绩。

## 实际资源与限制
冻结阶段墙钟{elapsed:.6f}秒（生成/validator子过程分项见cpu_phase_receipts.json），另CPU回归{reg['elapsed_seconds']:.6f}秒；不是0 CPU成本。旧资产基线hash与人工编写耗时未包含在这个冻结阶段墙钟中。
CUDA_VISIBLE_DEVICES为空；没有导入torch/transformers/peft/bitsandbytes，没有加载模型、tokenizer、checkpoint，没有推理/训练/GPU任务、API花费、push或外发。

## 命令与复核
在原项目根用已有.venv：
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B acod_v2_freeze_20261121/build_data.py before
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B acod_v2_freeze_20261121/test_v2.py
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B acod_v2_freeze_20261121/seal_and_freeze.py

再次生成/测试/冻结拒绝覆盖；复核使用verify_freeze.py。manifest.json包含代码/协议/数据/CPU证据SHA，manifest.sha256记录自身SHA。不得原地修改。

## 未做
未开新模型实验；无自然模型正确率、诊断率、概率校准、跨新工具结果或统计显著性。尚无新ACOD算法；GBS/IG为成熟强基线。此步与首轮小样本都不能用来筛掉方法。下一轮需另行授权、冻结runner/环境/模型身份，并遵循PREREG_NEXT_ZH.md，当前没有自动继续任务。
'''
    (HERE/'CPU_REPORT_ZH.md').open('x',encoding='utf-8').write(report)
    files=[p for p in HERE.rglob('*') if p.is_file() and p.name not in ['manifest.json','manifest.sha256'] and '__pycache__' not in p.parts]
    manifest={'version':'ACOD-v2-CPU-freeze-20261121','frozen_at':now(),'root_seed':2026112102,'development_cases':8,'heldout_cases':16,'construction_family_heldout':True,'not_new_tool_or_OOD':True,'natural_model_outputs':0,'heldout_selector_runs':0,'hashes':{str(p.relative_to(HERE)):sha(p) for p in sorted(files)}}
    save(HERE/'manifest.json',manifest)
    with (HERE/'manifest.sha256').open('x',encoding='utf-8') as f:f.write(sha(HERE/'manifest.json')+'  manifest.json\n')
    print(json.dumps({'frozen':True,'files':len(files),'manifest_sha256':sha(HERE/'manifest.json'),'regression_passed':reg['passed'],'regression_failed':reg['failed'],'validated_views':val['view_checks'],'negative_checks':val['negative_checks'],'legacy_files_unchanged':count,'new_generations':0},ensure_ascii=False))
if __name__=='__main__':main()