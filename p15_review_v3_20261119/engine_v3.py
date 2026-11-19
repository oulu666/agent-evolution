"""Whole episodes, fixed branch weights, independently label-token normalized."""
import contextlib,time

def branch_coefficients(features,examples):
 totals={k:sum(features[e]['supervised_tokens'][m] for e,m,b in examples if b==k) for k in ('new','replay')}
 assert totals['new']>0
 weights={'new':.5 if totals['replay'] else 1.,'replay':.5 if totals['replay'] else 0.}
 return totals,weights,[weights[b]*features[e]['supervised_tokens'][m]/totals[b] for e,m,b in examples]

def optimizer_update(model,opt,scaler,features,examples,device,guard,before_step=None,micro_event=None):
 import torch
 totals,weights,coeff=branch_coefficients(features,examples);start=time.perf_counter()
 if device=='cuda':torch.cuda.reset_peak_memory_stats()
 opt.zero_grad(set_to_none=True);model.train();losses=[]
 for (eid,mode,kind),c in zip(examples,coeff):
  guard.check();f=features[eid];x=torch.tensor([f['input_ids']],device=device);y=torch.tensor([f['masks'][mode]],device=device)
  ctx=torch.autocast(device_type='cuda',dtype=torch.float16) if device=='cuda' else contextlib.nullcontext()
  with ctx:loss=model(input_ids=x,attention_mask=torch.ones_like(x),labels=y).loss
  if micro_event:micro_event({'event':'forward_completed','episode_id':eid,'mode':mode,'kind':kind,'input_tokens':f['input_tokens']})
  assert torch.isfinite(loss),'nonfinite loss: no retry'
  losses.append(float(loss.detach()));z=loss*c
  (scaler.scale(z) if scaler is not None else z).backward()
  if micro_event:micro_event({'event':'backward_completed','episode_id':eid,'mode':mode,'kind':kind})
 if scaler is not None:scaler.unscale_(opt)
 assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None),'nonfinite gradient: no retry'
 norm=torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.)
 assert torch.isfinite(norm),'nonfinite gradient norm: no retry'
 guard.check()
 if before_step:before_step()
 if scaler is None:opt.step()
 else:scaler.step(opt);scaler.update()
 opt.zero_grad(set_to_none=True)
 if device=='cuda':torch.cuda.synchronize()
 return {'forward_sequences':len(examples),'backward_sequences':len(examples),'losses':losses,'branch_supervised_tokens':totals,
  'branch_weights':weights,'coefficients':coeff,'gradient_norm_before_clip':float(norm),'update_wall_seconds':time.perf_counter()-start,
  'input_tokens':sum(features[e]['input_tokens'] for e,m,b in examples),'examples':examples,
  'peak_allocated_MiB':torch.cuda.max_memory_allocated()/2**20 if device=='cuda' else None,'peak_reserved_MiB':torch.cuda.max_memory_reserved()/2**20 if device=='cuda' else None}
