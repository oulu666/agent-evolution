# ACOD有界兼容性检查：真实完成12次，非v2重跑
报告时间：2026-11-22 11:48:17 +0800（Asia/Shanghai）。
执行：2026-11-22 11:44:41 +0800—2026-11-22 11:47:08 +0800，墙钟146.312秒；12次尝试/12条原始输出，0技术失败/重试。

## 范围与预锁
仅既有historical_0_first、historical_1_last两道已暴露开发题的original；不是v2保留16题，不用reserved，不新造题。两份旧P9 ordinary Qwen3-0.6B checkpoint（seed20261108/20261109），没有训练或新增规则。
每题观测JSON及问题逐字相同；A为原round1四轮消息/旧system，B为原v2 system/两轮消息构造移植到历史payload，C保持B system并恢复A四轮阶段包装。B不是v2复杂保留集失败率的复现。
A↔C仅system不同；B↔C为阶段包装差别，包含既有assistant tool-call和独立末轮TOOL RESULT两个组成，不能进一步分别归因。

## CPU审计
189 PASS、0 FAIL，其中118项为此前保护哈希断言；其余包含消息等价/模板/类型/模型身份等检查。
实际模板仅应用一次，tokenize=False后add_special_tokens=False的IDs与直接chat-template tokenize一致；消息内容无预套模板；所有渲染均有闭合消息和新assistant生成头，未停在未闭合tool JSON。输入不截断，六个prompt仅151—335 tokens；128是输出上限，不是输入上限。tokenizer backend SHA与前次两checkpoint记录一致，基座/adapter身份及全部参数digest另外核验。
观察到旧历史工具结果为ok/result封装与line/text列表；v2保留复杂观测曾是record_key/fragment等结构，且system/阶段/问句均改变。本对照故意不同时改观测表示，因此没有隔离复杂结构或问句新增语义的作用。

## 三配置真实数值
|配置|次数|单answer envelope|严格schema|string/null严格答案正确|达到128上限|
|---|---:|---:|---:|---:|---:|
|A_historical_reference|4|4|4|0|0|
|B_v2_style|4|0|0|0|0|
|C_v2_system_legacy_stage|4|0|0|0|0|

schema合格只是输出格式/类型契约，不等于正确理解任务。integer9、string9、line9仍严格区分；没有从record_key/start_line提取答案。所有raw完整保存在results/responses.jsonl。
原历史A raw与旧记录逐字复现：4/4；两个题/两个checkpoint不能当大量独立样本作显著性或因果根因结论。

## 逐条原输出
|seed|题|配置|raw|严格正确|
|---|---|---|---|---:|
|20261108|historical_0_first|A_historical_reference|`{"answer": "9"}`|0|
|20261108|historical_0_first|B_v2_style|`{"ok": true, "result": {"line": 9, "text": "kdev0z observation 41589"}}`|0|
|20261108|historical_0_first|C_v2_system_legacy_stage|`{"line": "kdev0z observation 41589"}`|0|
|20261108|historical_1_last|A_historical_reference|`{"answer": "16"}`|0|
|20261108|historical_1_last|B_v2_style|`{"ok": true, "result": ["kdev1z observation 93830"]}`|0|
|20261108|historical_1_last|C_v2_system_legacy_stage|`{"arguments":{"path":"p9_dev/note_1.txt","pattern":"kdev1z"}}`|0|
|20261109|historical_0_first|A_historical_reference|`{"answer": "line 9"}`|0|
|20261109|historical_0_first|B_v2_style|`{"ok": true, "result": {"line": 9, "text": "kdev0z observation 41589"}}`|0|
|20261109|historical_0_first|C_v2_system_legacy_stage|`{"line": "kdev0z observation 41589"}`|0|
|20261109|historical_1_last|A_historical_reference|`{"answer": "16"}`|0|
|20261109|historical_1_last|B_v2_style|`{"ok": true, "result": {"line": 16, "text": "kdev1z observation 93830"}}`|0|
|20261109|historical_1_last|C_v2_system_legacy_stage|`{"arguments":{"path":"p9_dev/note_1.txt","pattern":"kdev1z"}}`|0|

## 判断与唯一下一步
本次有限对照未取得阶段包装能够稳定修复schema的证据；不能把假说写成已确证原因，也不继续搜索prompt。
唯一建议：CPU审查已暴露v2开发任务与旧file_search观测/问句的语义契约差异，先明确可比较的接口适配定义，再决定是否需要另行有界验证。
本检查不证明ACOD/MDCS有效，无条件切换或隐藏根因gold；不因这两个开发题淘汰任何研究方向。本次到此停止，不自动实施下一步。

## 成本、冻结与停止
输入2728、输出226、合计2954 tokens；原generate_with_usage计时合计23.574秒，墙钟含两次加载与监护，不能把0训练说成0推理/CPU成本。
33次guard；采样功耗[26.7, 35.17]W、最高温度69.7℃；未调整风扇/功耗。两模型全参数digest前后一致，并与原v2模型digest相同。
158个历史文件SHA不变，原STOP仍在原路径且SHA不变；没有删除、移动或清除。最终GPU计算进程：无；原worker/监督器身份已不存在，无自动恢复。
新目录仅acod_compat_20261122。FREEZE_MANIFEST.json/PLAN_PUBLIC.json/PREREG_COMPAT_ZH.md/六个渲染prompt均在响应前锁定。旧round1/v2freeze/v2eval/.venv/权重不改，无push/外发/付费API。

## 继承生成配置的透明记录
沿用原generate_with_usage与model.config.use_cache=False；加载时generation_config.use_cache记录为[None, None]。模型配置与生成配置若不同，不能仅凭前者声称底层强制关闭cache；附INHERITED_GENERATION_CONFIG_SOURCE.txt保留所用库准备逻辑，未为此额外生成或修改原pipeline。所有A/B/C共享同一继承设置，不是B32提速对照。
