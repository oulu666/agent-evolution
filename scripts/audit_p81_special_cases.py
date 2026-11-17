"""Read-only output audit; writes a separate addendum, never changes P81 scores."""
import collections
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fac_tinyagent.p81_semantics import semantic_sql_result

DATA = ROOT / 'data_ext_p81_diagnosis_20261116'
RUN = ROOT / 'runs_ext_p81_diagnosis_20261116'
OUT = ROOT / 'analysis_p81_special_cases_20261116'
OUT.mkdir(exist_ok=True)

def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

gold = {r['episode_id']: r for name in ['file', 'sql'] for r in read_rows(DATA / (name + '.jsonl'))}
records = [r for p in sorted(RUN.glob('seed*_decision.jsonl')) for r in read_rows(p)]
selected = []
for r in records:
    if r['seed'] == 20261109 and (r['kind'] == 'sql' or (r['kind'] == 'file' and r['meta']['case'] in [0, 1])) or r['seed'] == 20261108 and r['kind'] == 'sql' and r['meta']['case'] == 'zero':
        g = gold[r['episode_id']]
        selected.append({'record': r, 'prompt': g['prompt'], 'expected_arguments': g['expected_arguments'], 'expected_answer': g['expected_final_answer'], 'presented_observation': g.get('presented_observation')})

by_count = collections.defaultdict(lambda: {'n': 0, 'correct': 0})
alias_cases = []
for r in records:
    m = r['meta']
    if r['kind'] == 'file' and m['intent'] == 'last' and m['wording'] == 'explicit_line' and m['presentation'] == 'ascending':
        cell = by_count[m['n_matches']]
        cell['n'] += 1
        cell['correct'] += int(r['correct'])
    if r['kind'] == 'sql' and r.get('tool_correct') and not r['semantic_execution']:
        observation = json.loads(r['observation'])
        result = observation.get('result')
        if observation.get('ok') and isinstance(result, dict) and len(result.get('columns', [])) == 1 and result['columns'] != ['name']:
            original_columns = list(result['columns'])
            result['columns'] = ['name']
            if semantic_sql_result(gold[r['episode_id']], observation, DATA / 'probe.sqlite'):
                alias_cases.append({'seed': r['seed'], 'id': r['episode_id'], 'sql': r['predicted_arguments']['sql'], 'original_columns': original_columns, 'value_semantics_pass_after_column_label_normalization': True})

schema_audit = []
with sqlite3.connect('file:' + str(DATA / 'probe.sqlite') + '?mode=ro', uri=True) as c:
    real_tables = [x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
for r in read_rows(DATA / 'sql.jsonl'):
    table = re.search(r'FROM\s+(\w+)', r['expected_arguments']['sql'], re.I).group(1)
    schema_audit.append({'id': r['episode_id'], 'target_table': table, 'target_in_system': table in r['system'], 'legacy_employees_in_system': 'employees(' in r['system']})

seen = json.loads((DATA / 'seen_train.json').read_text(encoding='utf-8'))
seen_files = []
for seed, rows in seen.items():
    for r in rows:
        if r['tool_family'] == 'file':
            obs = json.loads(r['expected_observation'])
            seen_files.append({'seed': seed, 'id': r['episode_id'], 'prompt': r['prompt'], 'n_matches': len(obs['result']), 'expected_answer': r['expected_final_answer']})

output = {'new_model_calls': 0, 'changes_frozen_metrics': False,
          'explicit_last_ascending_by_match_count': dict(by_count),
          'alias_only_value_correct_cases': alias_cases,
          'actual_database_tables': real_tables, 'schema_prompt_audit': schema_audit,
          'selected_seen_file_samples': seen_files, 'selected_cases': selected}
(OUT / 'evidence.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: output[k] for k in ['new_model_calls', 'explicit_last_ascending_by_match_count', 'alias_only_value_correct_cases', 'actual_database_tables', 'selected_seen_file_samples']}, ensure_ascii=False, indent=2))
