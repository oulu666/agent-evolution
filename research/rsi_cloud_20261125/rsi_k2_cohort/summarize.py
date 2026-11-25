"""Drop individual sample outputs, keeping counts and version metadata."""
import json,sys
cell=json.load(sys.stdin)
if 'panel' in cell:
    for sample in cell['panel'].values():
        sample.pop('example', None)
else:
    cell.pop('sample', None)
print(json.dumps(cell,indent=2,sort_keys=True))
