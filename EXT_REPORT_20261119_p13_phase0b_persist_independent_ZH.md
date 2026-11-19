# P13 Phase0-B 独立实验报告

北京时间 2026-11-19 02:52:10 +0800

## 客观判断
一次延长的诊断不是方法创新。修复了观测单位和时序：主分析用同一探针的前缀一步虚拟ΔNLL预测未来10步终点工具+参数退化；候选一一结构配对映射单列，并非replay选择效果。完整自然无回放suffix不复现P12带回放过程。

## 结果与冻结gate
{
  "decision": "UNIDENTIFIABLE_no_expansion",
  "gates": {
    "engineering_and_state": true,
    "two_seeds_each_5_events_5_non_events": false,
    "AUROC_065_and_beats_baselines": false,
    "cluster_bootstrap_difference_lower95_above0": false
  },
  "primary_total_at_risk": 128,
  "primary_core_losses": 0,
  "seeds_with_minimum_events": [],
  "primary_per_seed_metrics": {
    "risk_call": {
      "20261108": {
        "n_weight": 43,
        "events_weight": 0,
        "AUROC": null,
        "AUPRC": null,
        "TopQuartileRecall": null,
        "prevalence": 0.0
      },
      "20261109": {
        "n_weight": 43,
        "events_weight": 0,
        "AUROC": null,
        "AUPRC": null,
        "TopQuartileRecall": null,
        "prevalence": 0.0
      },
      "20261110": {
        "n_weight": 42,
        "events_weight": 0,
        "AUROC": null,
        "AUPRC": null,
        "TopQuartileRecall": null,
        "prevalence": 0.0
      }
    },
    "initial_call": {
      "20261108": {
        "n_weight": 43,
        "events_weight": 0,
        "AUROC": null,
        "AUPRC": null,
        "TopQuartileRecall": null,
        "prevalence": 0.0
      },
      "20261109": {
        "n_weight": 43,
        "events_weight": 0,
        "AUROC": null,
        "AUPRC": null,
        "TopQuartileRecall": null,
        "prevalence": 0.0
      },
      "20261110": {
        "n_weight": 42,
        "events_weight": 0,
        "AUROC": null,
        "AUPRC": null,
        "TopQuartileRecall": null,
        "prevalence": 0.0
      }
    },
    "input_tokens": {
      "20261108": {
        "n_weight": 43,
        "events_weight": 0,
        "AUROC": null,
        "AUPRC": null,
        "TopQuartileRecall": null,
        "prevalence": 0.0
      },
      "20261109": {
        "n_weight": 43,
        "events_weight": 0,
        "AUROC": null,
        "AUPRC": null,
        "TopQuartileRecall": null,
        "prevalence": 0.0
      },
      "20261110": {
        "n_weight": 42,
        "events_weight": 0,
        "AUROC": null,
        "AUPRC": null,
        "TopQuartileRecall": null,
        "prevalence": 0.0
      }
    },
    "candidate_mapped_risk": {
      "20261108": {
        "n_weight": 43,
        "events_weight": 0,
        "AUROC": null,
        "AUPRC": null,
        "TopQuartileRecall": null,
        "prevalence": 0.0
      },
      "20261109": {
        "n_weight": 43,
        "events_weight": 0,
        "AUROC": null,
        "AUPRC": null,
        "TopQuartileRecall": null,
        "prevalence": 0.0
      },
      "20261110": {
        "n_weight": 42,
        "events_weight": 0,
        "AUROC": null,
        "AUPRC": null,
        "TopQuartileRecall": null,
        "prevalence": 0.0
      }
    }
  },
  "gate_macro_AUROC_sufficient_event_seeds": {
    "risk_call": null,
    "initial_call": null,
    "input_tokens": null,
    "candidate_mapped_risk": null
  },
  "bootstrap_gate_eligible_seeds": {
    "valid_replicates": 0,
    "intervals": {
      "MIR_minus_initial_NLL": null,
      "MIR_minus_TokenCost": null,
      "MIR_AUROC": null
    },
    "method": "two-way seed x shared-probe bootstrap"
  },
  "outcomes_out_of_24_each_skill": {
    "20261108": {
      "0": {
        "cal.count_date": {
          "tool_correct": 24,
          "arguments_correct": 21,
          "execution_success": 21,
          "final_correct": 20,
          "joint_success": 20
        },
        "cal.list_locations": {
          "tool_correct": 24,
          "arguments_correct": 22,
          "execution_success": 22,
          "final_correct": 10,
          "joint_success": 10
        }
      },
      "5": {
        "cal.count_date": {
          "tool_correct": 24,
          "arguments_correct": 21,
          "execution_success": 21,
          "final_correct": 20,
          "joint_success": 20
        },
        "cal.list_locations": {
          "tool_correct": 24,
          "arguments_correct": 22,
          "execution_success": 22,
          "final_correct": 9,
          "joint_success": 9
        }
      },
      "10": {
        "cal.count_date": {
          "tool_correct": 24,
          "arguments_correct": 21,
          "execution_success": 21,
          "final_correct": 20,
          "joint_success": 20
        },
        "cal.list_locations": {
          "tool_correct": 24,
          "arguments_correct": 22,
          "execution_success": 22,
          "final_correct": 6,
          "joint_success": 6
        }
      }
    },
    "20261109": {
      "0": {
        "cal.count_date": {
          "tool_correct": 24,
          "arguments_correct": 21,
          "execution_success": 21,
          "final_correct": 21,
          "joint_success": 21
        },
        "cal.list_locations": {
          "tool_correct": 24,
          "arguments_correct": 22,
          "execution_success": 22,
          "final_correct": 8,
          "joint_success": 8
        }
      },
      "5": {
        "cal.count_date": {
          "tool_correct": 24,
          "arguments_correct": 21,
          "execution_success": 21,
          "final_correct": 20,
          "joint_success": 20
        },
        "cal.list_locations": {
          "tool_correct": 24,
          "arguments_correct": 22,
          "execution_success": 22,
          "final_correct": 6,
          "joint_success": 6
        }
      },
      "10": {
        "cal.count_date": {
          "tool_correct": 24,
          "arguments_correct": 21,
          "execution_success": 21,
          "final_correct": 20,
          "joint_success": 20
        },
        "cal.list_locations": {
          "tool_correct": 24,
          "arguments_correct": 22,
          "execution_success": 22,
          "final_correct": 6,
          "joint_success": 6
        }
      }
    },
    "20261110": {
      "0": {
        "cal.count_date": {
          "tool_correct": 24,
          "arguments_correct": 21,
          "execution_success": 21,
          "final_correct": 21,
          "joint_success": 21
        },
        "cal.list_locations": {
          "tool_correct": 24,
          "arguments_correct": 21,
          "execution_success": 21,
          "final_correct": 7,
          "joint_success": 7
        }
      },
      "5": {
        "cal.count_date": {
          "tool_correct": 24,
          "arguments_correct": 21,
          "execution_success": 21,
          "final_correct": 20,
          "joint_success": 20
        },
        "cal.list_locations": {
          "tool_correct": 24,
          "arguments_correct": 21,
          "execution_success": 21,
          "final_correct": 7,
          "joint_success": 7
        }
      },
      "10": {
        "cal.count_date": {
          "tool_correct": 24,
          "arguments_correct": 21,
          "execution_success": 21,
          "final_correct": 20,
          "joint_success": 20
        },
        "cal.list_locations": {
          "tool_correct": 24,
          "arguments_correct": 21,
          "execution_success": 21,
          "final_correct": 7,
          "joint_success": 7
        }
      }
    }
  }
}

## 成本和审计
{
  "cost_totals_including_all_attempts": {
    "full_snapshot_captures": 88,
    "persisted_state_checkpoints": 54,
    "full_snapshot_exact_restores": 34,
    "NLL_causalLM_forward_calls": 608,
    "NLL_forward_samples": 608,
    "NLL_input_tokens": 288684,
    "generation_causalLM_forward_calls": 16635,
    "generation_inference_calls": 864,
    "generation_input_tokens": 302796,
    "generation_output_tokens": 16635,
    "generation_episodes": 432,
    "logical_adopted_step1": 3,
    "natural_suffix_causalLM_forward_calls": 216,
    "natural_suffix_backward_samples": 216,
    "natural_suffix_input_tokens": 101630,
    "natural_suffix_optimizer_steps": 27,
    "peak_allocated_GPU_bytes_over_all_segments": 2585268224,
    "peak_reserved_GPU_bytes_over_all_segments": 11555307520,
    "elapsed_seconds": 3387.966332180001,
    "predictor_saved_step1_causalLM_forward_calls": 16,
    "predictor_saved_step1_backward_samples": 16,
    "predictor_saved_step1_input_tokens": 6839,
    "predictor_saved_step1_optimizer_steps": 2,
    "engineering_primary_causalLM_forward_calls": 8,
    "engineering_primary_backward_samples": 8,
    "engineering_primary_input_tokens": 3947,
    "engineering_primary_optimizer_steps": 1,
    "engineering_control_causalLM_forward_calls": 8,
    "engineering_control_backward_samples": 8,
    "engineering_control_input_tokens": 3947,
    "engineering_control_optimizer_steps": 1
  },
  "safe_guard_checks": 692,
  "observed_GPU_memory_peak_MiB": 7921.0,
  "formal_optimizer_steps": 0
}

LoRA/optimizer/scaler/RNG/module modes均精确恢复，原前缀文件hash不变。显存记录覆盖所有段且不调用旧评测器的峰值重置；reserved可能反映WSL虚拟/共享分配而非独占物理显存。所有成本含校准和MIR虚拟预测，为额外诊断训练计算，不能称纯评测。

主指标未越门槛不以次组件/中点/候选映射救结论；事件不足为UNIDENTIFIABLE，不扩大规模。即便gate过，也不自动启动正式pilot。已有SQL/GSS/文献结论直接复用，无新提示矩阵。
