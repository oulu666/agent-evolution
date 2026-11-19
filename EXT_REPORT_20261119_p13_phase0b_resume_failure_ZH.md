# P13 Phase0-B 人工恢复与工程终止报告

北京时间 2026-11-19 00:43:36 +0800

## 实际执行
用户00:35明确授权后，重新确认无Apex、90W、无竞争任务、冻结hash通过；00:37:49将唯一已核实的22:58:35 Apex STOP完整归档并保留原字节/mtime/hash和人工授权。00:37:54真实启动supervisor369/worker503，seed08进入原定attempt02；00:40:23完成一步预测虚拟更新。不是只做准备。

## 终止原因
00:40:54监督器rc=1：冻结代码的`nondeterministic forecast reconstruction`断言触发。原记录前缀state hash一致，但预测表不逐值相等，且虚拟一步后的LoRA/optimizer hash也与attempt01不同。不能简单当小数误差而放宽合同。attempt02已消耗，按每种子最多2attempt停止；没有第三次尝试，没有改门槛、分数容差、数据或方法。

初始NLL差异（发生于更新前）：
{
  "call": {
    "different_rows": 0,
    "total_rows": 96,
    "max_abs_difference": 0.0,
    "max_symmetric_relative_difference": 0.0
  },
  "tool_name": {
    "different_rows": 0,
    "total_rows": 96,
    "max_abs_difference": 0.0,
    "max_symmetric_relative_difference": 0.0
  },
  "args": {
    "different_rows": 0,
    "total_rows": 96,
    "max_abs_difference": 0.0,
    "max_symmetric_relative_difference": 0.0
  },
  "call_other": {
    "different_rows": 0,
    "total_rows": 96,
    "max_abs_difference": 0.0,
    "max_symmetric_relative_difference": 0.0
  },
  "final": {
    "different_rows": 0,
    "total_rows": 96,
    "max_abs_difference": 0.0,
    "max_symmetric_relative_difference": 0.0
  },
  "all": {
    "different_rows": 0,
    "total_rows": 96,
    "max_abs_difference": 0.0,
    "max_symmetric_relative_difference": 0.0
  }
}

虚拟后NLL差异：
{
  "call": {
    "different_rows": 96,
    "total_rows": 96,
    "max_abs_difference": 0.008372440934181213,
    "max_symmetric_relative_difference": 0.23898082202574283
  },
  "tool_name": {
    "different_rows": 96,
    "total_rows": 96,
    "max_abs_difference": 0.0007964600808918476,
    "max_symmetric_relative_difference": 0.17360039040130826
  },
  "args": {
    "different_rows": 96,
    "total_rows": 96,
    "max_abs_difference": 0.014477308839559555,
    "max_symmetric_relative_difference": 0.2475823594681557
  },
  "call_other": {
    "different_rows": 96,
    "total_rows": 96,
    "max_abs_difference": 8.295374573208392e-05,
    "max_symmetric_relative_difference": 0.16084902792443384
  },
  "final": {
    "different_rows": 96,
    "total_rows": 96,
    "max_abs_difference": 0.024555861949920654,
    "max_symmetric_relative_difference": 0.23907762835873514
  },
  "all": {
    "different_rows": 96,
    "total_rows": 96,
    "max_abs_difference": 0.012944459915161133,
    "max_symmetric_relative_difference": 0.2354686460922006
  }
}

这说明记录的可训练/优化器/RNG状态一致仍不足以保证数值重建；不足以唯一归因于CUDA、量化基座或其它后端设置。本轮不追加GPU定位实验，不用事后容差救结果。

## 保存、复用和成本
三种子完整校准24题、formal_freeze原样复用；旧node00实际有25/48完整行（日志上一里程碑24），未作为完整节点复用；另1个开始但未完成的generate原记录保留，不能记为零。attempt02在新node00之前即失败，未运行自然suffix，未产生任何完整主终点配对。

额外重建成本：
{
  "time": "2026-11-19 00:40:49 +0800",
  "counts": {
    "NLL_causalLM_forward_calls": 192,
    "NLL_forward_samples": 192,
    "NLL_input_tokens": 91160,
    "predictor_virtual_causalLM_forward_calls": 8,
    "predictor_virtual_backward_samples": 8,
    "predictor_virtual_input_tokens": 3947,
    "predictor_virtual_optimizer_steps": 1,
    "peak_allocated_GPU_bytes_over_all_segments": 2585268224,
    "peak_reserved_GPU_bytes_over_all_segments": 9659482112,
    "elapsed_seconds": 108.69743177299998
  },
  "timings_seconds": {
    "nll_prefix_seconds": 25.043861221000014,
    "predictor_virtual_1_seconds": 7.481248768,
    "nll_predictor_virtual1_seconds": 23.946812514000015
  },
  "production_optimizer_steps": 0,
  "all_extra_diagnostic_cost": true,
  "forward_counter": "CausalLM invocation, includes token decode; internal layer checkpoint recomputation not separate CausalLM invocation"
}

所有尝试含校准/中断/重建总成本：
{
  "generation_causalLM_forward_calls": 1936,
  "generation_inference_calls": 98,
  "generation_input_tokens": 33934,
  "generation_output_tokens": 1918,
  "generation_episodes": 49,
  "peak_allocated_GPU_bytes_over_all_segments": 2585268224,
  "peak_reserved_GPU_bytes_over_all_segments": 9659482112,
  "elapsed_seconds": 317.76848165399997,
  "NLL_causalLM_forward_calls": 384,
  "NLL_forward_samples": 384,
  "NLL_input_tokens": 182320,
  "predictor_virtual_causalLM_forward_calls": 16,
  "predictor_virtual_backward_samples": 16,
  "predictor_virtual_input_tokens": 7894,
  "predictor_virtual_optimizer_steps": 2
}

两个attempt都将LoRA、optimizer、scaler、RNG、module modes精确恢复为前缀，原前缀文件hash不变。GPU进程已退出。

## 守卫日志说明
原guard日志整体分卷而非过滤：runs_ext_p13_phase0b/logs/guard.before_manual_resume_20261119_004040.jsonl，保留89条原始行和唯一已授权的Apex停止行，hash收据在人工恢复目录。当前会话guard.jsonl包含3条且无新unsafe；守卫未禁用，也没有解除任何未来STOP。分卷是恢复会话的操作日志边界，不是改实验数据或统计gate。

## 研究结论
本轮是工程重建失败，尚未完成MIR预测测评；不能报“零遗忘事件”，也不能据此判MIR有效/无效。未达到正式final验收前提（supervisor rc0、完整三种子），因此不运行成功态final、不生成COMPLETE假标记。原冻结attempt额度已耗尽，不自动补seed或开启新轮。

机器审计：runs_ext_p13_phase0b/manual_resume/20261119_003749_fe0c04263767/reconstruction_failure_audit.json；终止标记：runs_ext_p13_phase0b/TERMINATED_ENGINEERING_20261119.json。原日志、两个attempt、人工恢复receipt及失败证据全部保留。未push、未发GPT。
