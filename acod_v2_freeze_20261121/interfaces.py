"""Public-data boundary helpers, not cryptographic or OS sandboxing. No inference entry point."""
import json
from pathlib import Path
from core import canonical,validate_case,POOL
class AccessBoundaryError(ValueError):pass
def load_public(path):
    p=Path(path)
    if p.name!='cases.jsonl' or p.parent.name!='public':raise AccessBoundaryError('Only public/cases.jsonl may enter selector/model interfaces')
    data=[]
    with p.open(encoding='utf-8') as f:
        for line in f:
            if line.strip():
                obj=json.loads(line);validate_case(obj);data.append(obj)
    return data

def model_messages(case,view_name):
    validate_case(case)
    v=case['views'][view_name]
    return [{'role':'system','content':'You are answering a controlled read-only tool-observation task. Output exactly one JSON object with the sole key answer. Its value must be the complete requested text as a JSON string, or JSON null for no included records. Do not output markdown, explanations, or a tool call.'},{'role':'user','content':v['question']+'\nTOOL RESULT:\n'+canonical(v['observation'])}]

def selector_costs(case):
    # Pre-response input-only surrogate, same across policies. Actual model tokens/time must be reported separately.
    return {v:len(canonical(model_messages(case,v)).encode('utf-8'))+128 for v in POOL}