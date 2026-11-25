# 请先读：v2本次未完成，且输出契约门槛未通过
时间：2026-11-22 00:41:03 +0800（Asia/Shanghai）

## 真实执行，不是模拟器
2026-11-22 00:13:06—00:38:13（北京时间）按预锁1500秒总时限停止；已尝试208，完成207/224，1次在途被终止、16次未尝试。seed08完成112/112，seed09完成95/112。两份原Qwen3-0.6B ordinary adapter全部参数前后digest一致，0训练。
先前另有2次项目路径启动失败，均在模型加载/生成前；保留日志，不隐藏为“零失败”。实际健康运行墙钟1506.796秒含终止保存。

## 更关键的发现：现在还测不到想测的行为
已保存207条：完整JSON 106，但单键answer envelope 0、严格schema合格0、严格答案正确0、可用于v2行为更新的answer值0。
完整JSON键形状计数：{'record_key,start_line': 65, 'continuation_parts,record_key,start_line': 19, 'in_scope_fragments': 9, 'r_3': 1, 'r_0': 1, 'record': 4, 'record_matches': 3, 'record,start_line': 3, 'display_order,fragments': 1}。
其中95条字面上等于规范输入observation的前缀；108条未达到128上限仍没有answer envelope。
共有99条达到128-token上限，只能说可能截断；不能把全部格式失败归咎于token预算。
例如真实raw：{"id":"20261108:5b82ee97a24f02291cf2:original","raw":"{\"record_key\": \"r_0\", \"start_line\": 3}"}
这些是输出契约失败的直接观测。可能涉及新消息格式/观测结构与旧TinyAgent checkpoint不兼容，但本轮没有对照实验来证明具体原因。不能把记录对象或行号元数据事后提取成answer再抬高严格成绩，也没有这么做。
这是此前v2 CPU冻结没有验证的模型接口兼容性门槛；不应包装成已发现条件行为切换。补齐最后17条也不会自动修复已存207条没有answer的问题。

## 诊断数字该怎样读
完整7视图单元：seed08 16题、seed09 13题；全部为解析证据不足/拒判，closed-library unknown为0不是“24规则拟合成功”，而是没有可用answer观测来排除。各策略coverage均0、错误具体化不能有效评估；GBS与IG有不同查询路径，但没有自然答案证据支撑胜负解释。曲线仅机械中间重放，不是两checkpoint完整主实验或在线模型主动调用。
原锁定analyze.py要求224条齐全，本次没有运行它；CPU中间审计明确另存。

## 交互与MDCS暂不能立项下结论
未见输出前已证明冻结视图没有完整配对四元组：line含rotate，而reserved是reverse+纯line+value；reverse+value-only也缺失。严格交互不可估计，不是“找到0例所以没有交互”。
当前固定24组合内reserved不再细分全池等价类，这是局部结构结论；不能外推开放条件规则。没有可用answer数据，也没有完整交互设计，因此不能声称MDCS必要性已被证实或否定。
合适的后续建议是先在已暴露开发资产上验证模型消息/输出契约兼容性，再决定是否需要独立配对数据。不是增加手写规则、延长当前矩阵、改保留提示刷分或直接实现v3；本次没有执行这些后续动作。

## 资源、保护、交付
已保存usage下界：输入64235、输出15603，合计79838 tokens，生成累计1379.662秒；在途失败usage未知，不能当总成本精确值。
守卫331次；采样功耗[24.38, 34.37]W，最高69.5℃；未调整功耗/风扇。118个保护文件SHA不变；旧v2及round1均未改。
GPU计算进程最终查询：无。原worker/监督器身份已不存在；STOP保留、无自动恢复。
还有17个唯一响应缺失，原224-attempt cap仅余16。若要补齐，失败重试必须有新的明确有界授权；不擅自续跑。
全部v2保留题已有首checkpoint响应，未来v3不能再称其独立最终测试。无训练、无新增规则/query/MDCS、无外发/付费API/push。

详细结果：PARTIAL_REPORT_ZH.md；交接：HANDOVER_PARTIAL_ZH.md；逐条raw：results/responses.jsonl；中间摘要/曲线/缺失ID：results/{summary_partial,budget_curves_partial,missing_response_ids}.json。
