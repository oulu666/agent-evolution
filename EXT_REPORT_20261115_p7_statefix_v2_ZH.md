# P7精确状态恢复修复版实验报告

完成：2026-11-15 18:18:04 +0800（北京时间）。3/3种子、15/15配对、144题B1完整。

旧中断与重建失败产物只读保留；本版本没有使旧重建hash校验通过，而是重新运行受影响完整配对并精确落盘绑定其状态。

## 严格Joint宏平均（8题，非144独立题）

|状态|08|09|10|均值|

|---|---|---|---|---|

|baseline|12.500%|25.000%|25.000%|20.833%|

|background|0.000%|25.000%|25.000%|16.667%|

|db.list_tables|0.000%|25.000%|25.000%|16.667%|

|db.filter_cmp_top|0.000%|25.000%|25.000%|16.667%|

|file.search_last|0.000%|25.000%|25.000%|16.667%|

|py.median|0.000%|25.000%|25.000%|16.667%|

## 相对背景的NLL收益（正数为改善）

{
  "db.list_tables": {
    "dev": 0.01788818552934875,
    "check": 0.021416950155980885
  },
  "db.filter_cmp_top": {
    "dev": 0.003039584553334862,
    "check": 0.0006702908625205358
  },
  "file.search_last": {
    "dev": 0.0044100044954878586,
    "check": 0.001053481362760067
  },
  "py.median": {
    "dev": 0.0032590056459108987,
    "check": 0.0013737593156596024
  }
}

## 排序检验

{
  "20261108": {
    "1": {
      "p6_proxy": "db.list_tables",
      "measured_dev": "db.list_tables",
      "check_oracle": "db.list_tables",
      "spearman_proxy_to_check": 0.8,
      "spearman_dev_to_check": 0.2,
      "spearman_norm_to_check": 0.2,
      "check_gain_per_1k_tokens": {
        "db.list_tables": 0.041606719605624676,
        "db.filter_cmp_top": 0.0035045396960163952,
        "file.search_last": 0.004056432660211597,
        "py.median": 0.0026084520077523763
      },
      "spearman_single_unit_gradient_to_check": 1.0,
      "spearman_single_raw_gradient_to_check": 0.2
    },
    "2": {
      "p6_proxy": "db.list_tables",
      "measured_dev": "db.list_tables",
      "check_oracle": "db.list_tables",
      "spearman_proxy_to_check": 1.0,
      "spearman_dev_to_check": 0.4,
      "spearman_norm_to_check": 0.4,
      "check_gain_per_1k_tokens": {
        "db.list_tables": 0.05081705261117724,
        "db.filter_cmp_top": 0.0021079492481632964,
        "file.search_last": 0.003925132002638427,
        "py.median": 0.0037995748830716696
      },
      "spearman_single_unit_gradient_to_check": 0.8,
      "spearman_single_raw_gradient_to_check": 0.4
    }
  },
  "20261109": {
    "1": {
      "p6_proxy": "file.search_last",
      "measured_dev": "db.list_tables",
      "check_oracle": "db.list_tables",
      "spearman_proxy_to_check": -0.4,
      "spearman_dev_to_check": 0.2,
      "spearman_norm_to_check": 0.4,
      "check_gain_per_1k_tokens": {
        "db.list_tables": 0.008803146021604976,
        "db.filter_cmp_top": 0.000599615604561918,
        "file.search_last": -0.006214164174590374,
        "py.median": -0.0023950720747669646
      },
      "spearman_single_unit_gradient_to_check": -0.4,
      "spearman_single_raw_gradient_to_check": -0.4
    },
    "2": {
      "p6_proxy": "file.search_last",
      "measured_dev": "db.list_tables",
      "check_oracle": "db.list_tables",
      "spearman_proxy_to_check": -0.4,
      "spearman_dev_to_check": 0.2,
      "spearman_norm_to_check": 0.4,
      "check_gain_per_1k_tokens": {
        "db.list_tables": 0.01496087626197978,
        "db.filter_cmp_top": 0.002379797461768544,
        "file.search_last": 0.0013536973387972843,
        "py.median": 0.0016440578073345722
      },
      "spearman_single_unit_gradient_to_check": -0.4,
      "spearman_single_raw_gradient_to_check": -0.4
    }
  },
  "20261110": {
    "1": {
      "p6_proxy": "db.list_tables",
      "measured_dev": "db.list_tables",
      "check_oracle": "db.list_tables",
      "spearman_proxy_to_check": 0.4,
      "spearman_dev_to_check": 1.0,
      "spearman_norm_to_check": 0.8,
      "check_gain_per_1k_tokens": {
        "db.list_tables": 0.04076893845408717,
        "db.filter_cmp_top": 0.0014184046307349348,
        "file.search_last": -0.0016387274260060828,
        "py.median": 0.0011909277748491955
      },
      "spearman_single_unit_gradient_to_check": 0.4,
      "spearman_single_raw_gradient_to_check": 0.4
    },
    "2": {
      "p6_proxy": "db.list_tables",
      "measured_dev": "db.list_tables",
      "check_oracle": "db.list_tables",
      "spearman_proxy_to_check": 0.4,
      "spearman_dev_to_check": 0.4,
      "spearman_norm_to_check": 0.8,
      "check_gain_per_1k_tokens": {
        "db.list_tables": 0.05233025213409051,
        "db.filter_cmp_top": -0.0015915631639036346,
        "file.search_last": -0.0006863653915051817,
        "py.median": 0.00026450851039543045
      },
      "spearman_single_unit_gradient_to_check": 0.4,
      "spearman_single_raw_gradient_to_check": 1.0
    }
  }
}

## 逐技能与跨技能

analysis.json包含各动作/剂量的dev/check tool/final NLL及逐技能严格Joint；summary.json保留跨技能check损失收益矩阵。负值是代价，不包装为恢复。

## 原始错误审计来源

复用CPU审计：评分重算432条，gold核验56题，评分不一致0。

{
  "db.list_tables": {
    "n": 108,
    "tool_correct": 82,
    "arguments_correct": 95,
    "execution_success": 82,
    "final_correct": 80,
    "joint_success": 80,
    "tool:db_list_tables": 82,
    "tool:None": 13,
    "tool:db_query": 13
  },
  "db.filter_cmp_top": {
    "n": 108,
    "tool_correct": 108,
    "arguments_correct": 13,
    "execution_success": 79,
    "final_correct": 79,
    "joint_success": 13,
    "tool:db_query": 108
  },
  "file.search_last": {
    "n": 108,
    "tool_correct": 108,
    "arguments_correct": 108,
    "execution_success": 108,
    "final_correct": 0,
    "joint_success": 0,
    "tool:file_search": 108,
    "first_match_answer": 108,
    "last_match_answer": 0
  },
  "py.median": {
    "n": 108,
    "tool_correct": 10,
    "arguments_correct": 108,
    "execution_success": 10,
    "final_correct": 10,
    "joint_success": 10,
    "tool:stats_median": 10,
    "tool:stats_sorted": 98
  }
}

## 修复执行记录

v1新增包装器在18:04:14因bnb FSDP包装态被误当运行态而失败，v2使用原生load_state_dict并通过真实bnb CPU回归及GPU完整状态校验；旧hash漂移根因不能从不完整历史产物唯一推断。详见P7_STATEFIX_V2_AMEND_20261115_ZH.md。

## 成本与方法结论

逻辑30次诊断更新；本次新增18，复用12；另有已知旧中断/失败重建至少4次，累计物理更新至少34。旧中断未输出的生成token不可精确追溯，未记为零。新exact state binding数量：20。

仅dev收益/token进入选择，check不进入选择器。NLL响应和严格Joint并非同义，须分别查看；排序相关只作三个种子的描述性诊断，不是长期EAAR已胜出，也不是在线部署。

恢复工程补充：P7_STATEFIX_AMEND_20261115_ZH.md。全部输入沿用原冻结协议，不按check结果改策略，不启动P8。
