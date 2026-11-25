"""Post-primary follow-up; identical history horizon, no-reset strong comparator."""
import argparse
import pilot as p
parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
oldchoose,oldobserve=p.choose,p.observe
p.METHODS=('static','window','version_window','long_tag_no_reset','long_global_no_reset','surprise_reuse')
p.SEEDS=16
def choose(m,mem,tag,t):
    if m=='long_global_no_reset':
        return oldchoose('surprise_reuse',(mem[0],{tag:mem[0]}),tag,t)
    return oldchoose('surprise_reuse' if m=='long_tag_no_reset' else m,mem,tag,t)
def observe(m,mem,tag,t,w,y):
    oldobserve('window' if m in ('long_tag_no_reset','long_global_no_reset') else m,mem,tag,t,w,y)
orig=p.random.Random
p.random.Random=lambda seed:orig(seed+1337)
p.choose,p.observe=choose,observe
p.sim(args.out)
