"""Shared whole-episode gradient engine; CPU toy tests execute this exact routine."""
import contextlib

def optimizer_update(model,opt,scaler,features,examples,device,guard):
 import torch
 assert examples
 total=sum(features[e]['supervised_tokens'][m] for e,m,k in examples)
 assert total>0
 opt.zero_grad(set_to_none=True);model.train();forward=backward=0
 for eid,mode,kind in examples:
  guard.check();f=features[eid];x=torch.tensor([f['input_ids']],device=device);labels=torch.tensor([f['masks'][mode]],device=device)
  ctx=torch.autocast(device_type='cuda',dtype=torch.float16) if device=='cuda' else contextlib.nullcontext()
  with ctx:loss=model(input_ids=x,attention_mask=torch.ones_like(x),labels=labels).loss
  assert torch.isfinite(loss),'nonfinite loss; stop without automatic retry'
  scaled_loss=loss*f['supervised_tokens'][mode]/total
  (scaler.scale(scaled_loss) if scaler is not None else scaled_loss).backward();forward+=1;backward+=1
 if scaler is not None:scaler.unscale_(opt)
 assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None),'nonfinite gradient'
 norm=torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.0)
 guard.check()
 if scaler is not None:scaler.step(opt);scaler.update()
 else:opt.step()
 opt.zero_grad(set_to_none=True)
 if device=='cuda':torch.cuda.synchronize()
 return {'forward_sequences':forward,'backward_sequences':backward,'supervised_tokens':total,'gradient_norm_before_clip':float(norm)}
