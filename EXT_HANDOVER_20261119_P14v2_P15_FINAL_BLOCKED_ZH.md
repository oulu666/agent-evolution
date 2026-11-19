# P14v2 / P15 最终交接（2026-11-19，北京时间）

最终 NOT_FULLY_ACCEPTED/BLOCKED；方法无正负结论。正式矩阵0轨迹，不追加GPU、不建START、不补原RESULT/PASS，不开始下一轮。

已交付：P14v2元数据/group修正、1392条完整train/dev/test和合法fixture（gold不删）、逐题gold不变对账；P15预注册/算法/预算/七技能适配；v3固定分支0.5/0.5损失、精确缓存、原子恢复与完整可运行但门控拒绝的入口。108轨迹/41472更新不变。v3与旧598保护文件hash不变。

原唯一GPU工程尝试完成3物理/2逻辑更新、9forward/backward和6次train/dev生成，无test。完整磁盘恢复next-update及loss相等，GPU已释放；最终dtype JSON序列化故障导致RESULT缺失，生成后隔离恢复见证没有独立持久化，不宣称整体验收通过。

本次仅CPU：p15_cpu_closeout_20261119/json_safe.py准确转换dtype/device/Path等；11项报告回归通过，真实旧指纹只做CPU mock，不是GPU测量。token缓存250448字节确定性重建check通过，未写旧缓存、不加载模型。原运行器保持冻结，没有把新适配器接入GPU重跑。

入口与证据：
- EXT_REPORT_20261119_P14v2_P15_FINAL_BLOCKED_ZH.md：独立完整结论、成本分解及建议。
- P15_CPU_CLOSEOUT_OPERATIONAL_20261119_ZH.md：最小CPU修订规范。
- runs_ext_p15_cpu_closeout_20261119/FINAL_BLOCKED_STATUS.json、reporting_CPU_tests.json、token_cache_rebuild_check.json。
- runs_ext_p15_review_v3_20261119/engineering_attempt01/FORENSIC_RESULT.json、terminal_failure.txt、updates.jsonl、physical_steps.jsonl、generation_records.jsonl、state/commits.jsonl。
- v3 runtime SHA 386a5cf24a24957b99553120e3dd599b68ef09bbb0ae7ac32e97b049c645155f。
- 两完整next-update状态SHA dd45746708d9d75b9204892f6412983d05925f725f6acce257bc809fda2db940；大payload保留笔记本，不上传。

成本251–1244小时仅为两步/两题粗情景：训练55–267、持久化111–198、生成85–779小时，不是可靠工期。证据表明base blob内容去重只写一次，而每step仍全base CPU复制、多次深hash、重读857MB基座和约61MB状态写入；/mnt/c挂载边界已证实，但各项耗时归因无profile不可定量。下一版可评估共享冻结base+仅可变状态、稀疏checkpoint/终止save、stage1真实状态谱系共享、必要评测与批量/缓存优化；均未实现未计时，涉及恢复/物理成本/指标定义者须再冻结验证，绝不偷偷缩order/seed。

交付只含精确白名单轻量文件；candidate_inventory/upload_preflight列范围、大小、secret检查及遗漏依赖。旧draft_failure和_p11_fix_tmp保持不动；大状态/权重/cache/token派生gzip/锁/传输包留本地不上传。token缓存重建：.venv/bin/python -B p15_cpu_closeout_20261119/rebuild_token_features_cpu.py --write（只在缺失时写，需要身份匹配的本地tokenizer；不加载模型）。

GitHub按用户t121u授权上传main；不force/rebase/amend/reset或跳hook，不读取凭据；若分叉即停。最终完整SHA、URL及HEAD/origin/main/ls-remote一致性见最终执行回执。上传不改变BLOCKED状态。
