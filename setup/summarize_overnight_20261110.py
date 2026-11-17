"""Offline report calculations and figures; reads completed evaluations only."""
import hashlib
import json
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs_overnight_diagnosis_20261110'
SOURCE = json.loads((OUT / 'summary.json').read_text(encoding='utf-8'))
STATUS = json.loads((OUT / 'status.json').read_text(encoding='utf-8'))
DATA = {r['episode_id']: r for r in map(json.loads, (OUT / 'data' / 'paired_median.jsonl').read_text(encoding='utf-8').splitlines())}
LABELS = ['stage_03_python', 'v2_midpoint', 'v2_none_final', 'stage_04_calendar']
NAMES = ['学习前', '学习中点', 'v2不复习终点', '历史终点']
SEEDS = [20261108, 20261109, 20261110]


def rows_for(state, unit):
    return list(map(json.loads, (OUT / 'evaluations' / state / unit / 'results.jsonl').read_text(encoding='utf-8').splitlines()))


def joint(row):
    return all(row[k] for k in ['tool_correct', 'arguments_correct', 'execution_success', 'final_correct'])


core, wording, errors, seed_scores = {}, {}, {}, []
answer_arrays = {}
for label in LABELS:
    core[label] = {}
    for suite in ['historical', 'probe']:
        records = []
        for seed in SEEDS:
            for family in ['file', 'database', 'python']:
                records.extend(rows_for(f'A_seed{seed}_{label}', f'{suite}/{family}'))
        core[label][suite] = {'joint': mean(joint(r) for r in records),
                             'answer': mean(r['final_correct'] for r in records), 'n': len(records)}
    totals = Counter()
    collected = {'explicit': [], 'natural': []}
    per_seed_answers = []
    for seed in SEEDS:
        records = rows_for(f'A_seed{seed}_{label}', 'paired/python')
        natural = []
        for row in records:
            metadata = DATA[row['episode_id']]
            collected[metadata['wording']].append(row)
            if metadata['wording'] != 'natural':
                continue
            natural.append(row)
            actual = row.get('predicted_arguments', {}).get('values', [])
            expected = metadata['expected_arguments']['values']
            equivalent = (isinstance(actual, list) and len(actual) == len(expected)
                          and all(isinstance(v, (int, float)) for v in actual)
                          and sorted(actual) == sorted(expected))
            category = ('wrong_tool' if not row['tool_correct'] else
                        'exact' if row['arguments_correct'] else
                        'permutation' if equivalent else 'changed_values')
            totals[category] += 1
            totals[category + '_answer_correct'] += row['final_correct']
        natural.sort(key=lambda r: DATA[r['episode_id']]['pair_index'])
        per_seed_answers.append([r['final_correct'] for r in natural])
        seed_scores.append({'seed': seed, 'state': label, 'n': len(natural),
                            'joint': mean(joint(r) for r in natural),
                            'answer': mean(r['final_correct'] for r in natural),
                            'tool': mean(r['tool_correct'] for r in natural)})
    answer_arrays[label] = np.array(per_seed_answers, dtype=float)
    wording[label] = {name: {'joint': mean(joint(r) for r in records),
                            'answer': mean(r['final_correct'] for r in records),
                            'tool': mean(r['tool_correct'] for r in records),
                            'n': len(records)} for name, records in collected.items()}
    errors[label] = dict(totals)

# Sampling analysis is conditional on this fixed pool and these three trained models.
# Each draw uses the same instance subset across seeds and timepoints.
rng = np.random.default_rng(20261110)
sampling = []
for n in [12, 24, 48, 96]:
    draws = np.array([rng.choice(96, n, replace=False) for _ in range(2000)])
    for label in ['v2_midpoint', 'v2_none_final']:
        drops = (answer_arrays['stage_03_python'] - answer_arrays[label])[:, draws].mean(axis=(0, 2))
        sampling.append({'n_pairs': n, 'state': label, 'draws': 2000,
                         'positive_mean_answer_drop_fraction': float(np.mean(drops > 1e-12)),
                         'median_drop_pp': float(np.median(drops) * 100),
                         'pool_subsample_5_95_percentile_pp': (np.quantile(drops, [.05, .95]) * 100).tolist()})

transitions = []
orders = {'A': ['file', 'database', 'python', 'calendar'],
          'B': ['calendar', 'python', 'database', 'file'],
          'C': ['database', 'file', 'calendar', 'python']}
for order, families in orders.items():
    for before in [1, 2, 3]:
        joint_deltas, answer_deltas = [], []
        for seed in SEEDS:
            for family in families[:before]:
                left = rows_for(f'{order}_seed{seed}_stage_{before:02d}_{families[before-1]}', 'historical/' + family)
                right = rows_for(f'{order}_seed{seed}_stage_{before+1:02d}_{families[before]}', 'historical/' + family)
                joint_deltas.append(mean(joint(r) for r in right) - mean(joint(r) for r in left))
                answer_deltas.append(mean(r['final_correct'] for r in right) - mean(r['final_correct'] for r in left))
        transitions.append({'order': order, 'before': before, 'after': before + 1,
                            'joint_change_pp': 100 * mean(joint_deltas),
                            'answer_change_pp': 100 * mean(answer_deltas)})

payload = {'source_sha256': {name: hashlib.sha256((OUT/name).read_bytes()).hexdigest()
                            for name in ['summary.json', 'status.json', 'data/paired_median.jsonl']},
           'status': STATUS, 'core': core, 'wording': wording, 'natural_error_categories': errors,
           'natural_per_seed': seed_scores, 'stage_transitions': transitions,
           'sampling_method': '2000 subsets without replacement from fixed 96-instance pool; same subset across three seeds; positive mean answer drop only, not a significance test or calibrated deployment detector',
           'subsampling': sampling}
(OUT / 'REPORT_METRICS.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

font = FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams['font.family'] = font.get_name()
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['svg.fonttype'] = 'none'
plt.rcParams['axes.spines.top'] = False
plt.rcParams['axes.spines.right'] = False
fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.2), constrained_layout=True)
fig.patch.set_facecolor('#fbfcfe')
blue, red, gold = '#2563a6', '#c2444f', '#d89b29'
x = np.arange(3)
axis = axes[0]
for suite, label, color in [('historical', '历史题', blue), ('probe', '原监测题', red)]:
    values = [100 * (core[state][suite]['joint'] - core[LABELS[0]][suite]['joint']) for state in LABELS[:3]]
    axis.plot(x, values, marker='o', linewidth=2.5, color=color, label=label)
    for xx, yy in zip(x[1:], values[1:]):
        axis.annotate(f'{yy:+.2f}', (xx, yy), xytext=(0, 9 if yy > 0 else -19), textcoords='offset points', ha='center', color=color)
axis.axhline(0, color='#aab4c3', linewidth=.8)
axis.set_xticks(x, ['学习前', '中点', 'v2终点'])
axis.set_ylim(-8, 9)
axis.set_ylabel('旧工具严格联合成功率变化（百分点）')
axis.set_title('A  同一模型，监测方向不同', loc='left', fontsize=13, weight='bold')
axis.legend(frameon=False, loc='upper left')
axis.grid(axis='y', alpha=.16)

axis = axes[1]
for category, metric, label, color, style in [
        ('explicit', 'answer', '直接点名：答案正确', blue, '-'),
        ('natural', 'answer', '自然表述：答案正确', red, '-'),
        ('natural', 'joint', '自然表述：严格联合', gold, '--')]:
    values = [100 * wording[state][category][metric] for state in LABELS[:3]]
    axis.plot(x, values, marker='o', linewidth=2.3, linestyle=style, color=color, label=label)
    value_text = Decimal(str(values[-1])).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    axis.annotate(f'{value_text}%', (2, values[-1]), xytext=(-5, -15 if metric == 'joint' else 8), textcoords='offset points', ha='right', color=color)
axis.set_xticks(x, ['学习前', '中点', 'v2终点'])
axis.set_ylim(72, 107)
axis.set_ylabel('成功率（%）')
axis.set_title('B  相同数值，不同任务表述', loc='left', fontsize=13, weight='bold')
axis.legend(frameon=False, loc='lower left', fontsize=9)
axis.grid(axis='y', alpha=.16)

axis = axes[2]
bottom = np.zeros(3)
for category, label, color in [('permutation', '仅重排数值，答案正确', '#8196b0'),
                                ('changed_values', '改动或遗漏输入数值', gold),
                                ('wrong_tool', '工具选择错误', red)]:
    counts = np.array([errors[state].get(category, 0) for state in LABELS[:3]])
    axis.bar(x, counts, bottom=bottom, width=.6, label=label, color=color)
    for xx, yy, bb in zip(x, counts, bottom):
        if yy >= 5:
            axis.text(xx, bb+yy/2, str(yy), ha='center', va='center', color='white', weight='bold')
    bottom += counts
axis.set_xticks(x, ['学习前', '中点', 'v2终点'])
axis.set_ylim(0, 83)
axis.set_ylabel('自然表述题的严格联合失败数（共288题）')
axis.set_title('C  逐题区分变化类型', loc='left', fontsize=13, weight='bold')
axis.legend(frameon=False, loc='upper left', fontsize=9)
axis.grid(axis='y', alpha=.16)
fig.suptitle('小模型持续工具学习：夜间诊断的三个关键结果', fontsize=17, weight='bold')
fig.savefig(OUT / 'OVERNIGHT_FINDINGS.png', dpi=180, facecolor=fig.get_facecolor())
fig.savefig(OUT / 'OVERNIGHT_FINDINGS.svg', facecolor=fig.get_facecolor())
plt.close(fig)
print(json.dumps({'report_metrics': str(OUT/'REPORT_METRICS.json'), 'stage_transitions': transitions,
                  'figure': str(OUT/'OVERNIGHT_FINDINGS.png')}, ensure_ascii=False))
