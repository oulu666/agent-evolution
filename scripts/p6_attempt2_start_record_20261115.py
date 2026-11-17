from pathlib import Path
import json,os,time
R=Path(__file__).resolve().parents[1];O=R/'runs_ext_p6_devplan_attempt2';J=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
g=J(O/'e2e_gate.json');assert g['status']=='PASS';a=J(O/'branches/A_seed20261108_balanced_uniform/checkpoint/optimizer_step_audit.json')
t=[p for p in (O/'branches').glob('*/checkpoint/train_summary.json') if J(p).get('completed')]
e=[p for p in (O/'evaluation').glob('*/*/stage_report.json') if J(p)['evaluation_protocol']['batch_size']==1]
assert not (O/'logs/STOP').exists() and not (R/'runs_ext_p6_devplan/logs/STOP').exists()
for pid in [470,479]:os.kill(pid,0)
now=time.strftime('%F %T %z')
base='''# P6 attempt2 修复续跑记录（不是最终实验结论）

## 状态与进度
北京时间：{now}。11:19:24安全预检通过后自动启动，WSL supervisor PID470、真实GPU训练/评测子进程PID479，当前仍存活。首分支A_seed20261108_balanced_uniform已11:21:07完整训练成功，11:23:14完成新Database 24题Protocol-B1，e2e_gate=PASS，余8臂已放行（仍是同一个单GPU串行队列）。当前完整训练{nt}/9，B1套件{ne}/45，首分支继续其余评测；没有等待全队列完成，也没有开始下一轮。

## 修复与真实更新
旧计划缺少trainer摘要必需quota字段，不是模型训练本体崩溃。新增adapter从真实trainer AST扫描全部5个必需键，补齐诊断元数据，不改变items、经验分配、7494 tokens、超参、dev/holdout或校准。旧失败adapter与日志原地保留，新attempt全部从原step80前缀fresh开始。
原最后microstep182日志的22在尾部flush之前，不能当作正式总更新。共享前缀80 microsteps/10更新，后缀80 Calendar+22 replay=102 microsteps，12个完整累积窗+6条尾窗=13次实际后缀更新，总23。新GPU首臂实际step receipts已证明10+13=23、tail6且真实尾部调用1次；train_summary.completed=true，7494 replay tokens。没有额外加样本、加步或改日志数字。P4/P5同型旧证据也是日志22/summary23/tail6，更新协议不变。

## 验收与隔离
CPU真实runner→plan→train控制流→尾部归一→checkpoint/summary通过；1参数CPU SGD模型真实13次更新结果0.9974032044，解析值0.9974031177。checkpoint→评测接口及partial/complete finalize分支用明确synthetic桩验收，不是模型实验指标，所有CPU产物在独立attempt2_cpu目录。GPU首正式分支已真正通过原崩溃点及24题B1，不再仅以语法/dryrun放行。
校准3种子仍0 optimizer更新，原参数hash与冻结计划只读复用，不额外训练校准。9新计划items hash逐项等于旧冻结计划；新manifest锁定计划/源码/修订/校准及CPU验收hash。正式holdout成绩未用于修复、算法分配或门控。

## 科学设计未变
三臂balanced_uniform/balanced_early/devgrad_uniform×种子20261108/09/10，共9分支，每臂7494 replay input tokens、22条replay、23总optimizer updates（包含复用前缀10，实际新增13）。
四技能顺序：db.list_tables / db.filter_cmp_top / file.search_last / py.median。
|seed|两balanced臂|devgrad_uniform|
|---|---|---|
|20261108|3/2/2/3|5/1/3/1|
|20261109|2/2/3/3|3/1/4/2|
|20261110|3/3/2/2|6/1/2/1|
方法仍是独立dev LoRA梯度的一次规划：B_s=max(0,g_macro·h_s/(||h_s||+1e-12))；先每技能1条，余6个名额按B_s/((n_s+1)*next_input_tokens)分配。不是在线自适应、状态分类器或已测恢复速度。默认分散，不按技能名硬编码早槽。每技能dev4/新holdout12，已冻结并实体/数据分离；本次不改数据与算法。主指标为新holdout四技能joint宏平均，旧卷仅副作用/回顾。

## 安全与监测
开跑预检game=false、功率上限90W（门槛60W）、无其它GPU任务、旧/新STOP均不存在；不是要求瞬时功耗一直60W。单GPU/游戏/功率上限/连续检查失败守卫仍运行，游戏STOP不自动删除或恢复。当前无STOP。
- logs：runs_ext_p6_devplan_attempt2/logs/status.log、queue.log、runner.pid、gpu_child.pid
- 首关：runs_ext_p6_devplan_attempt2/e2e_gate.json
- 各checkpoint：train_summary.json、optimizer_step_audit.json、optimizer_update_log.jsonl
- 完成必须QUEUE COMPLETE + END queue rc=0 + 9训练/45套B1齐全；仅有adapter不算完成。
总时长预估1.5–3小时，从11:19北京时间计；实际依日志。每分支5套后runner自动CPU finalize写summary及中文报告，最终仍建议核齐后执行下列同一命令收尾（不启动GPU）：
```
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B -m fac_tinyagent.p6_attempt2 --phase finalize
```
手动监测不得误用旧attempt路径。安全停止后不得自行清STOP重启。本轮完成不自动加实验。

## 新增文件/输出
- P6_ATTEMPT2_AMEND_20261115_ZH.md（开跑前修订）
- fac_tinyagent/p6_attempt2.py；fac_tinyagent/p6_e3_train_attempt2.py
- scripts/p6_a2_generate_trainer_20261115.py；scripts/p6_a2_complete_runner_20261115.py
- scripts/test_p6_attempt2_contract_20261115.py；scripts/p6_attempt2_freeze_20261115.py
- scripts/run_p6_attempt2_20261115.py；scripts/launch_p6_attempt2_20261115.sh；scripts/p6_attempt2_handshake_20261115.py
- scripts/p6_attempt2_start_record_20261115.py（本状态记录）
- data_ext_p6_devplan_attempt2/；runs_ext_p6_devplan_attempt2/；runs_ext_p6_devplan_attempt2_cpu/
- P6_ATTEMPT2_START_20261115_ZH.md；EXT_REPORT_20261115_p6_attempt2_ZH.md；EXT_HANDOVER_20261115_p6_attempt2_ZH.md
以上均在用户本机项目内新增；旧研究目录/共享e3_train/冻结数据/.venv/zxx/Small Agent均未改动。
'''.format(now=now,nt=len(t),ne=len(e))
(R/'P6_ATTEMPT2_START_20261115_ZH.md').write_text(base,encoding='utf-8')
# Initial status documents only; the queue's own finalize will replace these with actual collected results.
for name in ['EXT_REPORT_20261115_p6_attempt2_ZH.md','EXT_HANDOVER_20261115_p6_attempt2_ZH.md']:
 p=R/name
 if not p.exists():p.write_text(base,encoding='utf-8')
print(json.dumps({'time':now,'complete_train':len(t),'B1_suites':len(e),'gate':g,'step_audit':a,'pids':[470,479],'stop':False},ensure_ascii=False))
