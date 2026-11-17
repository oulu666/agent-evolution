# P8决策对照经验干预报告

更新时间：2026-11-16 00:44:43 +0800（北京时间）；complete=True，B1 42/42。

本轮只检验经验包信息是否改变严格Joint，不训练收益回归、不比较无独立信号的C，不声称EAAR已成功。

|seed|arm|新holdout四技能Joint宏平均|replay input tokens|

|---|---|---|---|

|20261108|original|0.5|7494|

|20261108|decision|0.45833333333333337|7521|

|20261109|original|0.4375|7494|

|20261109|decision|0.5|7538|

|20261110|original|0.4375|7494|

|20261110|decision|0.45833333333333337|7556|

## 配对差B−A

{
  "per_seed": [
    -0.04166666666666663,
    0.0625,
    0.02083333333333337
  ],
  "mean": 0.013888888888888914
}

预注册判据：3/3种子差值>0且均值>=0.10；本次达到=False。

## 预算与复用

A只读复用P6 balanced_uniform真实最终adapter；B从相同step80前缀训练，保留完全相同12背景条目、22条经验packing及Calendar序列/槽位；仅替换10个目标槽。都23累计更新（前缀10+新增13）。B输入token差异<=1%，无填充，监督token逐臂报告在cpu_data_checks.json，不能冒称精确相同token/监督量。

File目标槽包含first/last合法对照正例，其他为新schema实体、必须WHERE/tie的SQL与中央值函数正例。是整个经验包对照，不把多样性/措辞/输入内容各自宣称独立因果。

主新题48（每技能12），另8题first/mean行为控制；dev16未作GPU选策略；Calendar30与非目标各族4题副作用单列summary。旧P6/P7正式卷不作新主指标。

## 逐技能和副作用

[
  {
    "seed": 20261108,
    "arm": "original",
    "skills": {
      "db.filter_cmp_top": {
        "n": 12,
        "joint_success": 0,
        "tool_correct": 0.5,
        "arguments_correct": 0,
        "execution_success": 0,
        "final_correct": 0.16666666666666666
      },
      "db.list_tables": {
        "n": 12,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      },
      "file.search_last": {
        "n": 12,
        "joint_success": 0,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0
      },
      "py.median": {
        "n": 12,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      }
    },
    "side_effects": {
      "file.search_first": {
        "n": 4,
        "joint_success": 0.25,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0.25
      },
      "py.mean": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      },
      "calendar": {
        "n": 30,
        "joint_success": 0.3,
        "tool_correct": 0.5,
        "arguments_correct": 0.5,
        "execution_success": 0.5,
        "final_correct": 0.3
      },
      "nontarget_database": {
        "n": 4,
        "joint_success": 0.75,
        "tool_correct": 1,
        "arguments_correct": 0.75,
        "execution_success": 0.75,
        "final_correct": 0.75
      },
      "nontarget_file": {
        "n": 4,
        "joint_success": 0.75,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0.75
      },
      "nontarget_python": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      }
    },
    "replay_tokens": 7494,
    "macro_joint": 0.5
  },
  {
    "seed": 20261108,
    "arm": "decision",
    "skills": {
      "db.filter_cmp_top": {
        "n": 12,
        "joint_success": 0,
        "tool_correct": 0,
        "arguments_correct": 0,
        "execution_success": 0,
        "final_correct": 0
      },
      "db.list_tables": {
        "n": 12,
        "joint_success": 0.8333333333333334,
        "tool_correct": 0.9166666666666666,
        "arguments_correct": 0.9166666666666666,
        "execution_success": 0.9166666666666666,
        "final_correct": 0.9166666666666666
      },
      "file.search_last": {
        "n": 12,
        "joint_success": 0,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0
      },
      "py.median": {
        "n": 12,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      }
    },
    "side_effects": {
      "file.search_first": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      },
      "py.mean": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      },
      "calendar": {
        "n": 30,
        "joint_success": 0.3,
        "tool_correct": 0.5,
        "arguments_correct": 0.5,
        "execution_success": 0.5,
        "final_correct": 0.3333333333333333
      },
      "nontarget_database": {
        "n": 4,
        "joint_success": 0.75,
        "tool_correct": 1,
        "arguments_correct": 0.75,
        "execution_success": 0.75,
        "final_correct": 0.75
      },
      "nontarget_file": {
        "n": 4,
        "joint_success": 0.75,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0.75
      },
      "nontarget_python": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      }
    },
    "replay_tokens": 7521,
    "macro_joint": 0.45833333333333337
  },
  {
    "seed": 20261109,
    "arm": "original",
    "skills": {
      "db.filter_cmp_top": {
        "n": 12,
        "joint_success": 0,
        "tool_correct": 1,
        "arguments_correct": 0,
        "execution_success": 0,
        "final_correct": 0.16666666666666666
      },
      "db.list_tables": {
        "n": 12,
        "joint_success": 0.75,
        "tool_correct": 0.8333333333333334,
        "arguments_correct": 0.9166666666666666,
        "execution_success": 0.8333333333333334,
        "final_correct": 0.75
      },
      "file.search_last": {
        "n": 12,
        "joint_success": 0,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0
      },
      "py.median": {
        "n": 12,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      }
    },
    "side_effects": {
      "file.search_first": {
        "n": 4,
        "joint_success": 0,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0
      },
      "py.mean": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      },
      "calendar": {
        "n": 30,
        "joint_success": 0.3333333333333333,
        "tool_correct": 0.5,
        "arguments_correct": 0.5,
        "execution_success": 0.5,
        "final_correct": 0.4
      },
      "nontarget_database": {
        "n": 4,
        "joint_success": 0.5,
        "tool_correct": 0.75,
        "arguments_correct": 0.5,
        "execution_success": 0.5,
        "final_correct": 0.5
      },
      "nontarget_file": {
        "n": 4,
        "joint_success": 0.75,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0.75
      },
      "nontarget_python": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      }
    },
    "replay_tokens": 7494,
    "macro_joint": 0.4375
  },
  {
    "seed": 20261109,
    "arm": "decision",
    "skills": {
      "db.filter_cmp_top": {
        "n": 12,
        "joint_success": 0,
        "tool_correct": 1,
        "arguments_correct": 0,
        "execution_success": 0.16666666666666666,
        "final_correct": 0.08333333333333333
      },
      "db.list_tables": {
        "n": 12,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      },
      "file.search_last": {
        "n": 12,
        "joint_success": 0,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0
      },
      "py.median": {
        "n": 12,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      }
    },
    "side_effects": {
      "file.search_first": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      },
      "py.mean": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      },
      "calendar": {
        "n": 30,
        "joint_success": 0.3333333333333333,
        "tool_correct": 0.5,
        "arguments_correct": 0.5,
        "execution_success": 0.5,
        "final_correct": 0.36666666666666664
      },
      "nontarget_database": {
        "n": 4,
        "joint_success": 0.75,
        "tool_correct": 1,
        "arguments_correct": 0.75,
        "execution_success": 0.75,
        "final_correct": 0.75
      },
      "nontarget_file": {
        "n": 4,
        "joint_success": 0.75,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0.75
      },
      "nontarget_python": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      }
    },
    "replay_tokens": 7538,
    "macro_joint": 0.5
  },
  {
    "seed": 20261110,
    "arm": "original",
    "skills": {
      "db.filter_cmp_top": {
        "n": 12,
        "joint_success": 0,
        "tool_correct": 1,
        "arguments_correct": 0,
        "execution_success": 0,
        "final_correct": 0.16666666666666666
      },
      "db.list_tables": {
        "n": 12,
        "joint_success": 0.75,
        "tool_correct": 0.8333333333333334,
        "arguments_correct": 1,
        "execution_success": 0.8333333333333334,
        "final_correct": 0.75
      },
      "file.search_last": {
        "n": 12,
        "joint_success": 0,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0
      },
      "py.median": {
        "n": 12,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      }
    },
    "side_effects": {
      "file.search_first": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      },
      "py.mean": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      },
      "calendar": {
        "n": 30,
        "joint_success": 0.36666666666666664,
        "tool_correct": 0.4666666666666667,
        "arguments_correct": 0.4666666666666667,
        "execution_success": 0.4666666666666667,
        "final_correct": 0.4
      },
      "nontarget_database": {
        "n": 4,
        "joint_success": 0.5,
        "tool_correct": 0.75,
        "arguments_correct": 0.5,
        "execution_success": 0.5,
        "final_correct": 0.5
      },
      "nontarget_file": {
        "n": 4,
        "joint_success": 0.75,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0.75
      },
      "nontarget_python": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      }
    },
    "replay_tokens": 7494,
    "macro_joint": 0.4375
  },
  {
    "seed": 20261110,
    "arm": "decision",
    "skills": {
      "db.filter_cmp_top": {
        "n": 12,
        "joint_success": 0,
        "tool_correct": 1,
        "arguments_correct": 0,
        "execution_success": 0.3333333333333333,
        "final_correct": 0.3333333333333333
      },
      "db.list_tables": {
        "n": 12,
        "joint_success": 0.8333333333333334,
        "tool_correct": 0.8333333333333334,
        "arguments_correct": 1,
        "execution_success": 0.8333333333333334,
        "final_correct": 0.8333333333333334
      },
      "file.search_last": {
        "n": 12,
        "joint_success": 0,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0
      },
      "py.median": {
        "n": 12,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      }
    },
    "side_effects": {
      "file.search_first": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      },
      "py.mean": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      },
      "calendar": {
        "n": 30,
        "joint_success": 0.3333333333333333,
        "tool_correct": 0.4666666666666667,
        "arguments_correct": 0.4666666666666667,
        "execution_success": 0.4666666666666667,
        "final_correct": 0.4
      },
      "nontarget_database": {
        "n": 4,
        "joint_success": 0.75,
        "tool_correct": 1,
        "arguments_correct": 0.75,
        "execution_success": 0.75,
        "final_correct": 0.75
      },
      "nontarget_file": {
        "n": 4,
        "joint_success": 0.75,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 0.75
      },
      "nontarget_python": {
        "n": 4,
        "joint_success": 1,
        "tool_correct": 1,
        "arguments_correct": 1,
        "execution_success": 1,
        "final_correct": 1
      }
    },
    "replay_tokens": 7556,
    "macro_joint": 0.45833333333333337
  }
]

主效应与副作用需并列判断。未达到时不自动加臂/改题/启动P9。
