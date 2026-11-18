# P12 结果与限制

北京时间 2026-11-18 14:27:20 +0800

{
  "aggregate": {
    "t0": {
      "macro_joint": 0.4490740740740741,
      "old_correct_out_of_72": 39,
      "new_correct_out_of_144": 58,
      "skills_correct_out_of_36": {
        "cal.count_date": 29,
        "cal.list_locations": 10,
        "db.list_tables": 0,
        "db.filter_cmp_top": 0,
        "file.search_last": 31,
        "py.median": 27
      }
    },
    "v1": {
      "macro_joint": 0.6064814814814815,
      "old_correct_out_of_72": 40,
      "new_correct_out_of_144": 91,
      "skills_correct_out_of_36": {
        "cal.count_date": 24,
        "cal.list_locations": 16,
        "db.list_tables": 21,
        "db.filter_cmp_top": 0,
        "file.search_last": 34,
        "py.median": 36
      }
    },
    "floor_random": {
      "macro_joint": 0.6296296296296297,
      "old_correct_out_of_72": 42,
      "new_correct_out_of_144": 94,
      "skills_correct_out_of_36": {
        "cal.count_date": 24,
        "cal.list_locations": 18,
        "db.list_tables": 24,
        "db.filter_cmp_top": 0,
        "file.search_last": 34,
        "py.median": 36
      }
    },
    "floor_rules": {
      "macro_joint": 0.6296296296296297,
      "old_correct_out_of_72": 42,
      "new_correct_out_of_144": 94,
      "skills_correct_out_of_36": {
        "cal.count_date": 24,
        "cal.list_locations": 18,
        "db.list_tables": 24,
        "db.filter_cmp_top": 0,
        "file.search_last": 34,
        "py.median": 36
      }
    }
  },
  "targets": {
    "floor_random": false,
    "floor_rules": false
  },
  "decision": "neither_no_next_experiment"
}

本轮为见过P11结果后的探索性修订。A也因高覆盖成本层选择而受规则启发；B-A仅检验同层排序增益。不能分别证明保底配额或候选扩充的因果作用；不是GEM复现。列库表新库成绩原样报告，不因掉分救榜。不自动进入filter实验。逐技能逐种子及配对转移见summary.json。
