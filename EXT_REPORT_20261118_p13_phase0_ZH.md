# P13 Phase0 结果

北京时间 2026-11-18 20:09:00 +0800

## 客观判断
MIR值得筛查，但DG-MIR三模块不能直接等同创新或保证论文目标；本轮不做正式三臂五种子训练。Calendar提示诊断不影响当前决策，删除；filter原T0严格Joint为0，不能称遗忘。

## 证据复核
五条日期退化是否全为日期当month：True。SQL逐臂原始核齐见history_audit.json（filter专指db.filter_cmp_top，不是全部SQL）。原报告“五种子”是笔误，实际三种子。

## 新实验
{
  "gates": {
    "engineering": true,
    "candidate_ranking": true,
    "at_least_3_joint_losses": false,
    "predictive_signal": false
  },
  "decision": "UNIDENTIFIABLE_no_expansion",
  "stage_joint": [
    {
      "cal.count_date": 12,
      "cal.list_locations": 3
    },
    {
      "cal.count_date": 12,
      "cal.list_locations": 3
    },
    {
      "cal.count_date": 12,
      "cal.list_locations": 3
    }
  ],
  "correct_to_wrong": 0,
  "wrong_to_correct": 0,
  "eligible_pairs": 30,
  "AUROC": {
    "MIR": null,
    "old_nll": null,
    "cost": null
  },
  "top_quartile_loss_rate": 0.0,
  "remaining_loss_rate": 0.0,
  "cost": {
    "counts": {
      "diversity_actual_model_forward_calls": 8,
      "diversity_backward": 8,
      "diversity_input_tokens": 4137,
      "nll_actual_model_forward_calls": 120,
      "teacher_forced_NLL_forwards": 120,
      "teacher_forced_input_tokens": 62289,
      "generation_episodes": 72,
      "generation_inference_calls": 144,
      "generation_input_tokens": 54738,
      "generation_output_tokens": 3288,
      "virtual_update_actual_model_forward_calls": 16,
      "virtual_backward": 16,
      "virtual_input_tokens": 7350,
      "virtual_optimizer_steps": 2,
      "peak_allocated_GPU_bytes": 1075841536,
      "peak_reserved_GPU_bytes": 11205083136,
      "elapsed_seconds": 367.20574269300005
    },
    "timings_seconds": {
      "diversity_seconds": 9.644105287000002,
      "stage0_nll_seconds": 8.35550198300001,
      "stage0_generation_seconds": 89.23286493799998,
      "virtual_update1_seconds": 5.549569434000034,
      "stage1_nll_seconds": 8.313922450000007,
      "stage1_generation_seconds": 94.941916623,
      "virtual_update2_seconds": 4.296210744000064,
      "stage2_nll_seconds": 10.975406916999987,
      "stage2_generation_seconds": 93.54050240799995
    },
    "all_cost_is_extra_diagnostic": true,
    "production_optimizer_steps": 0
  },
  "restoration": {
    "before": "f7fbb2e0040cc4b02bb3d5a5fb061686ef532aa310db574f5051424fd0eebc08",
    "after": "f7fbb2e0040cc4b02bb3d5a5fb061686ef532aa310db574f5051424fd0eebc08",
    "exact": true,
    "LoRA_before": "c5d0bcba13e968ae663cb98944b63a1686e33206d5bfe6777a77db2929845459",
    "LoRA_after": "c5d0bcba13e968ae663cb98944b63a1686e33206d5bfe6777a77db2929845459",
    "optimizer_before": "43b9d0a718129c10761dd77bef2f82e69c05e5c41e12891902ba98b40340c25f",
    "optimizer_after": "43b9d0a718129c10761dd77bef2f82e69c05e5c41e12891902ba98b40340c25f",
    "prefix_file_unchanged": true
  }
}

若事件不足，结论是当前两批局部更新不可识别，不是MIR无效；不扩批救结论。ΔNLL以gold工具观测轨迹计算，Joint为实际执行两回合生成，两者不可混称。前缀到后缀两步是不含回放的新流局部反事实，不解释完整P12的历史因果。

SQL新反例四例全部阻止漏WHERE碰巧同结果，且合法等价SQL语义通过/严格不通过；未改原盲卷。

文献纠偏、规模及预注册门槛见P13_PHASE0_PREREG_20261118_ZH.md。梯度余弦只作可计算性诊断，未增加诊断门控或多样性采样。所有成本均为额外诊断，不藏入23正式更新。
