from pathlib import Path
import json,hashlib,time,ast
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data_ext_p81_diagnosis_20261116';RUN=ROOT/'runs_ext_p81_diagnosis_20261116'
assert not list(RUN.glob('seed*.jsonl')),'GPU outputs already exist'
old=json.loads((DATA/'manifest.json').read_text())
(RUN/'pre_gpu_initial_manifest.json').write_text(json.dumps(old,ensure_ascii=False,indent=2))
paths=[ROOT/p for p in old['files']]+[ROOT/'fac_tinyagent/p81_semantics.py',ROOT/'scripts/test_p81_semantics.py',ROOT/'scripts/run_p81_diagnosis_20261116.py',Path(__file__)]
for p in paths:
    if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8-sig'))
old['files']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
old['final_cpu_freeze']=time.strftime('%F %T %z');old['pre_gpu_semantic_oracle_tests']=6
(DATA/'manifest.json').write_text(json.dumps(old,ensure_ascii=False,indent=2))
print('P81 final pre-GPU freeze',old['final_cpu_freeze'])
