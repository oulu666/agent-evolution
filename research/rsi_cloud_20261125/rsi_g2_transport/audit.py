"""Independent source-only negative control, no change to frozen primary outputs."""
from itertools import product
import json
from run import Row, certify, source_backend

def check():
    tallies={'profiles':0, 'match_invariant':0, 'queries':0}
    for flags in product((0,1),repeat=3):
        gate={0,*(i+1 for i,allow in enumerate(flags) if allow)}
        def query(left,right):
            tallies['queries']+=1
            return source_backend(
                [Row(x.id,x.key,'parity-readout') for x in left],
                [Row(x.id,x.key,'parity-readout') for x in right],
                gate)
        cert=certify(query)
        tallies['profiles']+=1
        tallies['match_invariant']+=cert==gate
    print(json.dumps(tallies,sort_keys=True,indent=2))

if __name__=='__main__':check()
