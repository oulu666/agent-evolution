# 先读：历史system兼容性证据与生成参数纠偏
时间：2026-11-22 11:50:33 +0800（Asia/Shanghai）。

## 已完成的有界真实检查
2026-11-22 11:44:41 +0800—2026-11-22 11:47:08 +0800，监督墙钟146.312秒；两道既有历史开发题×三配置×两份既有checkpoint＝12次，完成12，失败/重试0。不使用v2保留16题、reserved或新题。
A＝原round1四轮＋原system；B＝v2原system＋两轮包装移植至相同历史payload；C＝v2原system＋原四轮阶段包装。所有配置的问题、工具观测逐字一致，未做语义提醒或答案提取。

## 主终点：answer输出格式，而非任务正确
|配置|单键answer及string/null schema|严格任务答案正确|
|---|---:|---:|
|A 历史system/四轮|4/4|0/4|
|B v2 system/两轮|0/4|0/4|
|C v2 system/四轮|0/4|0/4|
历史A的4条raw均与旧round1记录逐字复现。A输出string9/string16/line9等，而非完整text，所以严格答案仍错。B/C可能在别的JSON键中出现请求文本，但没有事后从中抽取answer或记为正确。

## 真正证实与尚未证实
证实：在这两个固定历史开发输入及两个固定checkpoint上，相同四轮/同一观测下，仅把完整system从v2换回历史版本（C→A），schema由0/4恢复4/4。这是system整体版本影响输出契约的直接配对证据。
同时，仅恢复四轮工具后阶段但保留v2 system（B→C），schema仍0/4；“只补工具前缀就够了”没有得到支持。
不能进一步归因于历史system中的某一句、工具定义或输出阶段指令。缺少“旧system＋两轮”第四格，不能估计system×阶段交互，也不能声称旧system在任何包装下均必要/充分。没有再补第四配置。
更不能说原v2的207条失败全因system：那些复杂观测结构与问句不同，本次没有把它们纳入模型对照。这里复现的是历史payload上v2式构造的格式失败，不是重跑原保留集。
CPU审计189 PASS/0 FAIL（含118项原保护哈希断言）；未发现重复模板、输入截断、未闭合tool JSON生成头或tokenizer身份差异。输入仅151—335 tokens，全部12条输出均少于128，因此此次失败不是输出上限触发。

## 生成参数的必要纠偏（不改旧记录）
模型config.use_cache均False；加载的generation_config.use_cache为None。CPU按同一已记录配置和原generate显式kwargs解析，得到：[{"configuration_only_no_model_inference":true,"loaded_generation_config_use_cache":null,"model_config_use_cache":false,"resolved_do_sample":false,"resolved_generation_use_cache":true,"resolved_max_new_tokens":128,"seed":20261108},{"configuration_only_no_model_inference":true,"loaded_generation_config_use_cache":null,"model_config_use_cache":false,"resolved_do_sample":false,"resolved_generation_use_cache":true,"resolved_max_new_tokens":128,"seed":20261109}]。
原generate_with_usage没有显式传use_cache=False；本次已审计的生成配置准备逻辑将None回填为全局默认True。故不能声称本轮在生成层强制关闭cache；这是预锁decode字段写False与继承原函数实际解析间的不符，明确列作协议偏差/历史函数参数审计发现，不在结果后偷偷改为False。
用户允许沿用原协议，本次A/B/C严格共享这个原函数与同一设置，并未采用B32；共同cache设置不能解释C↔A仅system改变的配对差异。没有为纠正参数新增任何生成。CPU配置重放不是模型重跑，也未记录逐forward cache探针，证据范围到生成配置解析。
此前只记model.config.use_cache=False的报告亦不足以证明实际关闭cache；没有擅自改写旧v2/round1结果。未来若要求强制False，须在新授权协议显式传参并验证，不能悄悄补跑此轮。

## 唯一下一步建议（未实施）
以“原历史system＋原四轮”作为唯一兼容接口参考，先仅CPU审查已暴露v2开发输入能否在不改变任务语义下适配该旧file_search契约；若不能，要明确新增能力/结构需求，而不是把格式失配解释成24规则不足。先给语义适配证书与开发验收协议，不直接在保留题试prompt、不扩矩阵、不启动MDCS。
这是一条格式兼容性证据，不是任务修复，更不证明ACOD/MDCS有效或无效。

## 成本、保护与停止
已保存输入2728、输出226，合计2954 tokens；generate累计23.574秒。两模型全部参数digest前后及相对旧v2身份均一致，0训练。
158个旧文件SHA不变；原eval STOP仍在原位置且SHA未变，仅隔离唯一已知历史超时记录，没有删除/移动/清除。33次监护、采样功耗[26.7, 35.17]W、最高69.7℃；未调功耗或风扇。
最终GPU计算进程为空，原worker/监督器身份已不存在；无自动后续。旧round1/v2freeze/v2eval/.venv/权重未改，无push、外发、付费API。

详细表和12条原始输出：REPORT_COMPAT_ZH.md、results/responses.jsonl、results/scorer_only_layered.json。FREEZE_MANIFEST/PLAN_PUBLIC/PREREG_COMPAT及六份渲染prompt均在生成前锁定；本页是生成后对预注册配对结果和额外参数审计的明确解释，未重算/修改主终点。
