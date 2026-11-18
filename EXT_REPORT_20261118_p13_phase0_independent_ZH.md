# P13 Phase0 独立验收与最终判断

北京时间 2026-11-18 20:09:54 +0800

## 已完成
最小Phase0完成，监督器rc=0，72条两回合开发评测、两批真实后续Calendar数据的虚拟AdamW更新，未启动正式训练，未保存新adapter，未push。

## 原建议的事实核齐
- 日期退化5条全部确为calendar_count(month=完整日期)，涉及seed08两条、seed09三条，seed10零条。
- filter（非所有SQL任务）A/B工具36/36、严格参数0/36、最终35/36成立；执行观测正确分别A31/36、B30/36。v1最终34/36，T0为32/36且严格Joint已为0，因此不是新近遗忘的证据。
- A/B严格Joint逐题相同不代表工具执行/原始轨迹逐题相同。P12报告“五种子”笔误，实际三种子。

## 冻结gate和实测
{
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
  "gates": {
    "engineering": true,
    "candidate_ranking": true,
    "at_least_3_joint_losses": false,
    "predictive_signal": false
  },
  "decision": "UNIDENTIFIABLE_no_expansion",
  "correct_to_wrong": 0,
  "wrong_to_correct": 0,
  "eligible_pairs": 30,
  "AUROC": {
    "MIR": null,
    "old_nll": null,
    "cost": null
  },
  "top_quartile_loss_rate": 0.0,
  "remaining_loss_rate": 0.0
}

候选排序gate：[{"batch": 1, "nondegenerate": true, "positive": 5, "unique_rounded": 6}, {"batch": 2, "nondegenerate": true, "positive": 4, "unique_rounded": 5}]。

两个连续局部窗口不插入回放，保留真实后续新流顺序及优化器动量，不声称完整复现P12轨迹或解释历史遗忘。低于3条退化为不可识别；仅暂停当前配置扩训，不判整条MIR研究路线无效。不临时扩批、改提示、换种子救结论。

## 预算、状态、安全
{
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
  "exact_restore": {
    "before": "f7fbb2e0040cc4b02bb3d5a5fb061686ef532aa310db574f5051424fd0eebc08",
    "after": "f7fbb2e0040cc4b02bb3d5a5fb061686ef532aa310db574f5051424fd0eebc08",
    "exact": true,
    "LoRA_before": "c5d0bcba13e968ae663cb98944b63a1686e33206d5bfe6777a77db2929845459",
    "LoRA_after": "c5d0bcba13e968ae663cb98944b63a1686e33206d5bfe6777a77db2929845459",
    "optimizer_before": "43b9d0a718129c10761dd77bef2f82e69c05e5c41e12891902ba98b40340c25f",
    "optimizer_after": "43b9d0a718129c10761dd77bef2f82e69c05e5c41e12891902ba98b40340c25f",
    "prefix_file_unchanged": true
  },
  "guard_checks": 97,
  "diversity_full_LoRA_dimension": 5046272,
  "gradient_offdiagonal_cosine_range": [
    -0.06951776891946793,
    0.3347928822040558
  ]
}

成本口径：144个额外teacher-forced/更新/梯度forward样本（120+16+8），24个backward样本（16虚拟更新+8多样性），另144次generate及其tokens精确记录；内部逐token解码与checkpoint重算forward未单独插桩。两临时optimizer step不计正式训练步。评测器会重置PyTorch峰值计数，所以cost.json allocated峰值仅末段评测，不能称全程峰值；外部20:03北京时间见7914MiB为整卡已观测下界，不冒称全程峰值。

所有LoRA、优化器、scaler、RNG和module modes恢复hash一致，原前缀文件hash不变，守卫无游戏/STOP/低功耗/竞争GPU项目。SQL新反例4/4阻止漏WHERE巧合，等价查询4/4语义通过而严格参数不通过；未改原盲卷。

## 路线判断
方向比静态规则微调更有可检验性，但把MIR/GSS/提示诊断拼起来不能直接当论文创新。RGD-R不是F/P准确率差，Angle Matters不支持LLM任务梯度夹角结论；文献原文纠偏见冻结协议。本轮不需要三提示矩阵或GSS复杂选择。下一步不预先承诺DG-MIR三臂五种子，更不以小筛查声称CCF-B已达标。

完整机器审计：runs_ext_p13_phase0/summary.json、independent_acceptance.json、history_audit.json；协议P13_PHASE0_PREREG_20261118_ZH.md；交接EXT_HANDOVER_20261118_p13_phase0_ZH.md。
