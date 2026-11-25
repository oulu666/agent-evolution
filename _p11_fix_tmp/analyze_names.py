#!/usr/bin/env python3
import json
from pathlib import Path
p=Path("/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/_p11_fix_tmp/t0_name_dump_cpu.json")
d=json.loads(p.read_text())
ss,aa=d["state_summary"],d["adapter_summary"]
print("state n", ss["n"], "kinds", ss["kinds"], "default_seg", ss["n_with_default_segment"])
print("adapter n", aa["n"], "kinds", aa["kinds"], "default_seg", aa["n_with_default_segment"])
print("state0", ss["sample_head"][0])
print("adap0", aa["sample_head"][0])
only_s=d["only_in_state_vs_adapter"]
only_a=d["only_in_adapter_vs_state"]
mapped={n.replace(".default.weight", ".weight") for n in only_s}
print("strip .default before weight: equal to adapter keys?", mapped==set(only_a))
print("n mapped", len(mapped), "n adapter", len(only_a))
print("mapped-adapter", sorted(mapped-set(only_a))[:8])
print("adapter-mapped", sorted(set(only_a)-mapped)[:8])
