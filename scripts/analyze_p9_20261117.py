"""Summarize P9 actual receipts, with no GPU work or changes to frozen scores."""
import json,statistics,sys,time,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent.utils import read_json,read_jsonl,write_json,sha256_file
from fac_tinyagent.p9_counterfactual_20261117 import SEEDS,DATA,RUN,verify

def rate(rows,key):
    return {'correct':sum(bool(r.get(key)) for r in rows),'n':len(rows),'rate':statistics.mean(bool(r.get(key)) for r in rows) if rows else None}

def analyze():
    verify();cells=[];usage=collections.Counter();probes=[];training=[];case_rows=[]
    for seed in SEEDS:
        ps=read_jsonl(RUN/f'probe_{seed}.jsonl');probes.extend(ps)
        for r in ps:
            for u in r['usage']:
                for k in ['inference_calls','input_tokens','output_tokens','generation_seconds']:usage[k]+=u[k]
        for arm in ['normal','counter']:
            p=RUN/f'branches/seed{seed}_{arm}/complete.json'
            if p.exists():training.append(read_json(p))
        for arm in ['baseline','normal','counter']:
            rows=read_jsonl(RUN/f'eval_{seed}_{arm}.jsonl');cell={'seed':seed,'arm':arm,'rows':len(rows)}
            if not rows:continue
            for r in rows:
                for u in r['usage']:
                    for k in ['inference_calls','input_tokens','output_tokens','generation_seconds']:usage[k]+=u[k]
            for intent in ['first','last']:
                rs=[r for r in rows if r['kind']=='normal' and r['intent']==intent]
                cell[intent+'_joint']=rate(rs,'joint_success');cell[intent+'_answer']=rate(rs,'final_correct')
                for k in ['tool_correct','arguments_correct','execution_success']:cell[intent+'_'+k]=rate(rs,k)
                cell[intent+'_reverse_answer']=rate([r for r in rows if r['kind']=='reversed' and r['intent']==intent],'final_correct')
            groups=collections.defaultdict(list)
            for r in rows:
                if r['kind']!='side':groups[r['case']].append(r)
            paired=[]
            for case,rs in sorted(groups.items()):
                if len(rs)!=4:continue
                ok=all(r['final_correct'] for r in rs) and all(r.get('joint_success',True) for r in rs)
                paired.append({'correct':ok});case_rows.append({'seed':seed,'arm':arm,'case':case,'n_matches':rs[0]['n_matches'],'four_way_success':ok,'normal_last_joint':next(r['joint_success'] for r in rs if r['kind']=='normal' and r['intent']=='last')})
            cell['four_way']=rate(paired,'correct')
            cell['side_all']=rate([r for r in rows if r['kind']=='side'],'joint_success')
            cell['side_skills']={s:rate([r for r in rows if r['kind']=='side' and r['skill']==s],'joint_success') for s in sorted({r['skill'] for r in rows if r['kind']=='side'})}
            cells.append(cell)
    complete=(RUN/'queue_complete.json').exists()
    if complete:
        assert len(cells)==9 and all(c['rows']==56 for c in cells)
        assert len(probes)==72 and len(training)==6 and usage['inference_calls']==864
        for seed in SEEDS:
            a=next(r for r in training if r['seed']==seed and r['arm']=='normal');b=next(r for r in training if r['seed']==seed and r['arm']=='counter')
            for k in ['start_state','optimizer_calls','input_tokens','supervised_tokens']:assert a[k]==b[k]
    summary={'complete':complete,'created':time.strftime('%F %T %z'),'cells':cells,'training':training,'generation_usage':dict(usage),'case_results':case_rows}
    if complete:
        diffs={k:[] for k in ['last_joint','first_joint','four_way']}
        for seed in SEEDS:
            a=next(c for c in cells if c['seed']==seed and c['arm']=='normal');b=next(c for c in cells if c['seed']==seed and c['arm']=='counter')
            for k in diffs:diffs[k].append(b[k]['rate']-a[k]['rate'])
        summary['counter_minus_normal']=diffs
        summary['progression_gate']=statistics.mean(diffs['last_joint'])>=.10 and sum(x>0 for x in diffs['last_joint'])>=2 and statistics.mean(diffs['four_way'])>0 and statistics.mean(diffs['first_joint'])>=-.05
    probe_cells={}
    for kind in ['file','sql']:
        keys=sorted({(r['variation'],r['intent']) if kind=='file' else (r['source_episode_id'],r['version']) for r in probes if r['kind']==kind})
        for key in keys:
            rs=[r for r in probes if r['kind']==kind and ((r['variation'],r['intent']) if kind=='file' else (r['source_episode_id'],r['version']))==key]
            probe_cells[kind+'/'+str(key)]=rate(rs,'correct' if kind=='file' else 'semantic_correct')
    summary['probe_cells']=probe_cells
    write_json(RUN/'summary.json',summary)
    if complete:report(summary)
    print(json.dumps({'complete':complete,'training_done':len(training),'eval_models':len(cells),'usage':dict(usage),'gate':summary.get('progression_gate'),'deltas':summary.get('counter_minus_normal')},indent=2))

def report(s):
    lines=['# P9 反事实观察训练实验报告','',f'完成时间：{s["created"]}。三个种子、六个新训练分支、九个模型终点全部完成。','',
    '## 设计与干预','',
    '三个 P8 Decision 最终完整训练状态分别作为共同起点；normal/counter 都额外训练 72 条×2轮（48条新File经验，24条旧技能背景），各18次实际新增更新。counter只改变训练时匹配结果的显示排列，输入/监督token、题目、答案、训练样本顺序、起点状态完全配对。baseline为未追加训练的P8模型。','',
    'File训练24个文件、匹配数2/3/4；独立holdout12文件、匹配数2/3/4/5，使用新标记、内容和措辞。所有训练完成后才进行终点评测；未按测试结果追加epoch或改超参数。','',
    '## 独立文件正常工具链成绩','',
    '|种子|模型|last Joint|first Joint|四项配对全对|旧技能副作用Joint|','|---|---|---|---|---|---|']
    def fmt(c):return f'{c["correct"]}/{c["n"]} ({100*c["rate"]:.1f}%)'
    for c in s['cells']:lines.append('|'+ '|'.join([str(c['seed']),c['arm'],fmt(c['last_joint']),fmt(c['first_joint']),fmt(c['four_way']),fmt(c['side_all'])])+'|')
    lines+=['','四项配对为同一文件的first/last×正常/逆序全部正确。正常使用实际工具调用，逆序只隔离答案阶段、给定正确工具调用，故它是混合链路诊断，不能称为四种完整端到端Joint。正常last Joint是主指标。副作用集为已知旧任务，仅用于检查保持。','',
    '## counter相对normal的配对变化','', '```json',json.dumps(s['counter_minus_normal'],ensure_ascii=False,indent=2),'```','',f'预注册推进门槛达到：{s["progression_gate"]}。门槛要求last均值至少+10个百分点、至少2/3种子为正、四项配对均值为正、first均值下降不超过5个百分点。此为探索决策，不等同统计显著。','',
    '## 固定诊断结果','', '|诊断条件|正确数|','|---|---|']
    for key,v in s['probe_cells'].items():lines.append(f'|{key}|{fmt(v)}|')
    lines+=['','SQL诊断只比较同一P8权重下的输入说明，不是SQL训练收益。legacy沿用旧库描述，schema校正为真实库，schema_turn在此基础上明确当前回合先调用工具。原P8/P8.1分数未修改。','',
    '## 成本与完整性','', '```json',json.dumps(s['generation_usage'],indent=2),'```','',
    f'新增训练更新共{sum(r["optimizer_calls"] for r in s["training"])}次；训练输入token共{sum(r["input_tokens"] for r in s["training"])}，监督token共{sum(r["supervised_tokens"] for r in s["training"])}；各分支计时合计{sum(r["seconds"] for r in s["training"]):.1f}秒。计时包含状态落盘。',
    '六个训练分支逐步保存完整优化状态；两臂同种子起点hash、真实更新数、输入和监督token一致。冻结输入与代码哈希末尾复核通过。独立训练复本为3种子，基础测试文件12个，不把864次生成当作864个独立复本。','',
    '## 核心算法','',
    '固定文件、意图与正确答案，对工具观察序列施加与标签无关的排列π；最小化同一答案的标准SFT负对数似然。训练的唯一组间区别是观察排列。没有加入偏好损失、课程排序、额外教师或梯度分配。评价用正常任务成功和同文件四项规则检查，阻止“只复制第一个显示项”获得虚假规则成功。','',
    '## 文件','',
    '- 协议：P9_PREREG_20261117_ZH.md','- 数据与冻结记录：data_ext_p9_counterfactual_20261117/','- 全部逐题输出、训练回执与summary.json：runs_ext_p9_counterfactual_20261117/','- 实验实现：fac_tinyagent/p9_counterfactual_20261117.py','- 分析脚本：scripts/analyze_p9_20261117.py','']
    target=ROOT/'EXT_REPORT_20261117_p9_counterfactual_ZH.md';target.write_text('\n'.join(lines),encoding='utf-8')
    paths=[target,RUN/'summary.json']+list(RUN.glob('eval*.json*'))+list(RUN.glob('probe*.jsonl'))+list(RUN.glob('branches/*/complete.json'))+[Path(__file__)]
    write_json(RUN/'final_manifest.json',{'complete':True,'frozen_inputs_verified':True,'files':{str(p.relative_to(ROOT)):sha256_file(p) for p in paths}})

if __name__=='__main__':analyze()
