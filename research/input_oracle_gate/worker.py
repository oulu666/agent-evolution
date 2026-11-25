"""Public precedence operations on canonical local version strings."""
import json
from pathlib import Path
import sys
import warnings

root=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(root/"src"),str(root)]
project=sys.argv[2]
warnings.simplefilter("ignore",DeprecationWarning)
if project=="python-semver":
    import semver as lib
    compare=lib.compare
else:
    import semantic_version as lib
    def compare(x,y):
        a,b=lib.Version(x),lib.Version(y)
        return int(a>b)-int(a<b)
assert Path(lib.__file__).resolve().is_relative_to(root)
rows=[]
for pair in json.load(sys.stdin):
    try:
        result=compare(*pair)
        if type(result) is not int:
            raise TypeError("Non-integer precedence")
        rows.append((result>0)-(result<0))
    except Exception as exc:
        rows.append(type(exc).__name__)
print(json.dumps(rows))
