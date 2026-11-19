"""Exact persisted LoRA/optimizer/RNG + frozen quantized base/buffer/QuantState binding.
No approximate tensor comparisons. Base blobs deduplicated by semantic SHA256.
"""
import copy,importlib.metadata,os,time
from pathlib import Path
import torch
from . import p7_fullstate_v2_20261115 as FS
from .utils import read_json,write_json,sha256_file

PARAM_ATTRS=['blocksize','compress_statistics','quant_type','quant_storage','bnb_quantized']
MODULE_ATTRS=['compute_dtype','compute_type_is_set','quant_storage','p','inplace','lora_alpha','scaling','r','max_seq_len_cached','original_max_seq_len','rope_type','attention_scaling']
CONFIG_ATTRS=['use_cache','_attn_implementation','_attn_implementation_internal','attention_dropout','torch_dtype','dtype']
ENV_KEYS=['CUBLAS_WORKSPACE_CONFIG','PYTHONHASHSEED','NVIDIA_TF32_OVERRIDE','TORCH_ALLOW_TF32_CUBLAS_OVERRIDE','PYTORCH_CUDA_ALLOC_CONF','PYTORCH_ALLOC_CONF','CUDA_LAUNCH_BLOCKING','OMP_NUM_THREADS','MKL_NUM_THREADS','HF_HUB_OFFLINE','TOKENIZERS_PARALLELISM']
def plain_cpu(t):
    out=torch.empty(tuple(t.shape),dtype=t.dtype,device='cpu');out.copy_(t.detach());return out

def backend_fingerprint(model,compute_dtype):
    def call(name,default=None):
        obj=torch
        try:
            for bit in name.split('.'):obj=getattr(obj,bit)
            return obj() if callable(obj) else obj
        except (AttributeError,RuntimeError):return default
    versions={}
    for name in ['torch','bitsandbytes','transformers','peft','accelerate']:
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    cfg=model.get_base_model().config
    return {'versions':versions,'torch_CUDA_build':torch.version.cuda,'GPU_name':torch.cuda.get_device_name(),'GPU_capability':torch.cuda.get_device_capability(),'actual_compute_dtype':str(compute_dtype),'deterministic_algorithms':torch.are_deterministic_algorithms_enabled(),'deterministic_warn_only':call('is_deterministic_algorithms_warn_only_enabled'),'float32_matmul_precision':torch.get_float32_matmul_precision(),'cuda_matmul_allow_tf32':torch.backends.cuda.matmul.allow_tf32,'cudnn_allow_tf32':torch.backends.cudnn.allow_tf32,'cudnn_deterministic':torch.backends.cudnn.deterministic,'cudnn_benchmark':torch.backends.cudnn.benchmark,'flash_SDPA':call('backends.cuda.flash_sdp_enabled'),'memory_efficient_SDPA':call('backends.cuda.mem_efficient_sdp_enabled'),'math_SDPA':call('backends.cuda.math_sdp_enabled'),'cudnn_SDPA':call('backends.cuda.cudnn_sdp_enabled'),'env':{k:os.environ.get(k) for k in ENV_KEYS},'actual_config':{k:FS.clone(getattr(cfg,k)) for k in CONFIG_ATTRS if hasattr(cfg,k)},'limits':'Recorded fingerprint, not serialization of CUDA/cuBLAS/bitsandbytes hidden implementation caches.'}

def capture_base(model):
    params=dict(model.named_parameters());idnames={id(p):n for n,p in params.items()};q={};attrs={}
    for n,p in params.items():
        state=getattr(p,'quant_state',None)
        if state is not None:q[n]=FS.clone(state.as_dict(packed=False));attrs[n]={k:FS.clone(getattr(p,k)) for k in PARAM_ATTRS if hasattr(p,k)}
    qm={}
    for n,m in model.named_modules():
        state=getattr(m,'quant_state',None)
        if state is not None:qm[n]={'state':FS.clone(state.as_dict(packed=False)),'weight_parameter':idnames.get(id(getattr(m,'weight',None)))}
    return {'frozen_parameters':{n:plain_cpu(p) for n,p in params.items() if not p.requires_grad},'buffers':{n:plain_cpu(b) for n,b in model.named_buffers()},'quant_parameter_states':q,'quant_parameter_attrs':attrs,'quant_module_states':qm}

def runtime_attrs(model):
    cfg=model.get_base_model().config
    return {'modules':{n:{k:FS.clone(getattr(m,k)) for k in MODULE_ATTRS if hasattr(m,k)} for n,m in model.named_modules() if any(hasattr(m,k) for k in MODULE_ATTRS)},'config':{k:FS.clone(getattr(cfg,k)) for k in CONFIG_ATTRS if hasattr(cfg,k)}}

def restore_base(model,base):
    from bitsandbytes.functional import QuantState
    params=dict(model.named_parameters());buffers=dict(model.named_buffers());assert set(base['frozen_parameters'])=={n for n,p in params.items() if not p.requires_grad};assert set(buffers)==set(base['buffers'])
    with torch.no_grad():
        for n,t in base['frozen_parameters'].items():
            p=params[n];assert tuple(p.shape)==tuple(t.shape) and p.dtype==t.dtype;p.copy_(t.to(p.device))
        for n,t in base['buffers'].items():
            b=buffers[n];assert tuple(b.shape)==tuple(t.shape) and b.dtype==t.dtype;b.copy_(t.to(b.device))
    for n,d in base['quant_parameter_states'].items():
        p=params[n];p.quant_state=QuantState.from_dict(FS.clone(d),p.device)
        for k,v in base['quant_parameter_attrs'][n].items():setattr(p,k,FS.clone(v))
    modules=dict(model.named_modules())
    for n,record in base['quant_module_states'].items():
        m=modules[n];weight=record['weight_parameter']
        if weight is not None and weight in base['quant_parameter_states']:
            assert FS.digest(record['state'])==FS.digest(base['quant_parameter_states'][weight]);m.quant_state=params[weight].quant_state
        else:
            device=next(m.parameters()).device;m.quant_state=QuantState.from_dict(FS.clone(record['state']),device)

def restore_attrs(model,attrs):
    modules=dict(model.named_modules())
    for n,fields in attrs['modules'].items():
        for k,v in fields.items():setattr(modules[n],k,FS.clone(v))
    cfg=model.get_base_model().config
    for k,v in attrs['config'].items():setattr(cfg,k,FS.clone(v))

class Store:
    def __init__(self,engine,root):self.e=engine;self.root=Path(root);(self.root/'base_blobs').mkdir(parents=True,exist_ok=True);self.cache={}
    def capture(self):
        e=self.e;start=time.perf_counter();base=capture_base(e.model);bhash=FS.digest(base);train=e.capture();attrs=runtime_attrs(e.model);backend=backend_fingerprint(e.model,e.dtype)
        semantic=FS.digest({'base_semantic_sha256':bhash,'train':train,'attrs':attrs,'backend':backend})
        e.timings['snapshot_capture_seconds_total']=e.timings.get('snapshot_capture_seconds_total',0)+time.perf_counter()-start;e.cost['full_snapshot_captures']+=1
        return {'base':base,'base_semantic_sha256':bhash,'train':train,'attrs':attrs,'backend':backend,'semantic_sha256':semantic}
    def save(self,path):
        path=Path(path);assert not path.exists(),'snapshot cannot overwrite';path.parent.mkdir(parents=True,exist_ok=True);start=time.perf_counter();s=self.capture();bhash=s['base_semantic_sha256'];bp=self.root/'base_blobs'/(bhash+'.pt')
        if bhash not in self.cache:
            if not bp.exists():torch.save(s['base'],bp)
            # A newly loaded CPU payload must equal its bound semantic content.
            check=torch.load(bp,map_location='cpu',weights_only=False);assert FS.digest(check)==bhash;del check
            self.cache[bhash]={'path':str(bp),'file_sha256':sha256_file(bp),'semantic_sha256':bhash,'bytes':bp.stat().st_size}
        s.pop('base');s['base_reference']=self.cache[bhash];torch.save(s,path)
        receipt={'path':str(path),'file_sha256':sha256_file(path),'semantic_sha256':s['semantic_sha256'],'base_reference':s['base_reference'],'train_semantic_sha256':FS.digest(s['train']),'LoRA_sha256':FS.digest(s['train']['parameters']),'optimizer_sha256':FS.digest(s['train']['optimizer']),'backend_sha256':FS.digest(s['backend']),'bytes':path.stat().st_size}
        write_json(path.with_suffix('.receipt.json'),receipt);self.e.timings['snapshot_save_seconds_total']=self.e.timings.get('snapshot_save_seconds_total',0)+time.perf_counter()-start;self.e.cost['persisted_state_checkpoints']+=1;return receipt
    def restore(self,receipt):
        e=self.e;start=time.perf_counter();path=Path(receipt['path']);assert sha256_file(path)==receipt['file_sha256'];s=torch.load(path,map_location='cpu',weights_only=False);ref=s['base_reference'];bp=Path(ref['path']);assert sha256_file(bp)==ref['file_sha256'];base=torch.load(bp,map_location='cpu',weights_only=False);assert FS.digest(base)==s['base_semantic_sha256']
        restore_base(e.model,base);del base;restore_attrs(e.model,s['attrs']);e.restore(s['train']);current=self.capture()
        assert current['semantic_sha256']==receipt['semantic_sha256'],'FULL PERSISTED STATE EXACT RESTORE FAILED';del current
        e.timings['snapshot_restore_seconds_total']=e.timings.get('snapshot_restore_seconds_total',0)+time.perf_counter()-start;e.cost['full_snapshot_exact_restores']+=1;return s

def cpu_test():
    from bitsandbytes.functional import QuantState
    q=QuantState(absmax=torch.tensor([1,2],dtype=torch.uint8),shape=torch.Size([4,4]),code=torch.arange(16,dtype=torch.float32),blocksize=64,quant_type='nf4',dtype=torch.bfloat16,offset=torch.tensor(.125),state2=QuantState(absmax=torch.tensor([.5]),code=torch.arange(8,dtype=torch.float32),blocksize=256,dtype=torch.float32))
    d=FS.clone(q.as_dict(packed=False));q2=QuantState.from_dict(FS.clone(d),torch.device('cpu'));assert FS.digest(d)==FS.digest(q2.as_dict(packed=False))
    return {'passed':True,'native_QuantState_CPU_exact_roundtrip':True,'GPU_initialized_by_native_library_import':torch.cuda.is_initialized(),'CPU_payload_only_no_model_or_forward':True,'empty_approximate_comparisons':True}
