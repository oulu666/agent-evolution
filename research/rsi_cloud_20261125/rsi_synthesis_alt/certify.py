"""Independently check the one-probe upper bound with exhaustive state tables."""
from collections import defaultdict
from pilot import STATES,REGIMES,PROBES,TASKS,encode,decode

for region, probes in REGIMES.items():
    print(region)
    for name, task in TASKS.items():
        ceiling={}
        for probe in probes:
            parts=defaultdict(list)
            for actual in STATES:
                parts[encode(PROBES[probe],actual)].append(encode(task,actual))
            # There is no single independent assignment of a different action
            # to indistinguishable worlds. Choose the best one per observation.
            ceiling[probe] = sum(max(sum(decode(raw,a)==task for raw in bucket)
                for a in STATES) for bucket in parts.values())
        best=max(ceiling.values())
        print(name, best, [p for p,k in ceiling.items() if k==best])
