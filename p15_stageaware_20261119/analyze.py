"""Post-freeze paired trajectory summaries; no selection or checkpoint tuning."""
import itertools,json,statistics
from core import *
def holm(pvalues):
 order=sorted(pvalues,key=pvalues.get);out={};running=0
 for i,k in enumerate(order):running=max(running,(len(order)-i)*pvalues[k]);out[k]=min(1,running)
 return out

def paired_summary(deltas):
 # 18 trajectory pairs are descriptive units; 6 orders share the same three seeds.
 assert len(deltas)==18
 seedmeans={s:statistics.mean(v for (o,seed),v in deltas.items() if seed==s) for s in SEEDS}
 ordermeans={o:statistics.mean(v for (order,s),v in deltas.items() if order==o) for o,s in deltas}
 obs=abs(statistics.mean(seedmeans.values()));null=[abs(statistics.mean(v*sign for v,sign in zip(seedmeans.values(),signs))) for signs in itertools.product((-1,1),repeat=3)]
 return {'paired_order_seed_units':18,'mean_delta':statistics.mean(deltas.values()),'direction_positive_pairs':sum(x>0 for x in deltas.values()),
         'direction_negative_pairs':sum(x<0 for x in deltas.values()),'seed_block_means':seedmeans,'order_means':{'-'.join(k):v for k,v in ordermeans.items()},
         'seed_block_signflip_two_sided_p':sum(v>=obs-1e-12 for v in null)/len(null),
         'inference_limit':'Only 3 seed blocks, 6 fixed orders; sign symmetry unverified. NOT 348 independent experiments, no broad IID-task generalization; exact seed-block test has very coarse resolution.'}

def main():
 cohort=read(RUN/'cohort.json');scores={};details={}
 for c in cohort:
  base=RUN/'test_evaluation'/c['id'];assert read(base/'COMPLETE.json')['nodes']==4
  s=read(base/'node03_summary.json');key=(tuple(c['order']),c['seed'])
  scores[(c['method'],key)]=s['skill_macro']['joint_success'];details[c['id']]={'final':s,'longitudinal':read(base/'longitudinal.json')}
 contrasts={}
 for other in ['seqft','uniform','p11_priority','no_priority','no_layer']:
  ds={key:scores[('layer_replay',key)]-scores[(other,key)] for method,key in scores if method=='layer_replay'}
  contrasts['layer_replay-minus-'+other]=paired_summary(ds)
 primary={k:v['seed_block_signflip_two_sided_p'] for k,v in contrasts.items() if k.split('minus-')[1] in ('seqft','uniform','p11_priority')}
 secondary={k:v['seed_block_signflip_two_sided_p'] for k,v in contrasts.items() if k not in primary}
 write(RUN/'final_paired_analysis.json',{'primary_metric':'final-node test skill-macro strict Joint','contrasts':contrasts,'Holm_primary_three':holm(primary),'Holm_secondary_two':holm(secondary),
  'all_trajectory_metrics':details,'no_checkpoint_selection':True})
if __name__=='__main__':main()
