# ACOD v2 修订说明：输出类型与可组合行为

本目录仅新增，不改首轮协议、响应、指标与历史资产。此次只做CPU实现、回归验收、保留输入与独立gold的流程冻结，不加载模型/tokenizer/权重，不启动GPU或后续实验。

## 四层记录，禁止静默混并
1. raw：模型原始字符串永久保存，不删除包装/空白/类型。
2. syntax：完整JSON解析、重复key与NaN拒绝、恰好answer单键object、原始JSON类型。
3. strict task score：本任务只允许完整text的string或无候选时null；integer 9、string "9"、string "line 9"按原类型/字面值分别判分。真text="9"时只有相同string可严格正确；不能因解释成line就改变严格成绩。附加key/包装/代码围栏/非法JSON均不严格正确。
4. behavior：独立于gold和题意的观测解释。仅正整数本体、完整十进制字串、完整`line N`字串可产生行号候选；任意含数字的自然文本不匹配。exact text解释同时保留，text="9"/"line 9"可同时符合text与line，重复text保留所有row_ids。字串到行号是显式有损解释，原值/类型/编码/来源/歧义都保留，不能据gold选解释。

行为层仅在可恢复唯一answer object时解析自然语言/代码围栏包装，标记较低可信度（不是概率）。多个answer对象/非法结构不更新假设、明确证据不足；合法answer数组等原样保留但有限标量规则不匹配时unknown。空text、null、字符串"null"不同。行为解释的唯一性不等于语义正确或隐藏机制唯一。

## 组合语法而非逐题硬拟合
固定24组合：6选择算子（原坐标按问题first/last、反用first/last、显示first、显示last、text字典序min、text字典序max）×4有效字段/编码组合（text/native；line/native integer；line/decimal string；line/`line N`）。text字典序相同的行按line显式破同值；输出相同text时不伪称选中了某个唯一行。

正确行为只是(coordinate_intent,text,native)组合，不是隐藏认知标签。空候选时全部组合返回null；不支持的operator/输出schema/行号冲突/缺失text直接拒绝，不加万能规则解释所有结果。

在original+全部可查询candidate输入上计算完整typed响应签名，等价组合合并一类，每类先验均等，复制等价rule不改变IG先验。reserved输入/输出不参与先验签名；等价类内所有成员保留，reserved上的不同预测取并集，避免合并时丢失预测不确定性。先验仅是算法设计假设，未宣称统计校准。所有自然观测最多支持相容集合；单类也始终可能是开放世界之外的另一规则/混合行为。

## 选择器与访问边界
core.next_query无文件I/O、gold、未来输出参数；只接收公开候选输入及已查询观测。固定/随机/GBS-Gini/IG共享同样输入、观测解析与cost。IG以公开model_messages的UTF-8字节数+128作预响应代价代理，不偷用实际未知输出长度；实际tokens/time必须另报。GBS/IG一般不等价，若实际查询路径一致，报告为同一个经验基线，不能算独立胜负。

interfaces.load_public只接收public/cases.jsonl，拒绝scorer_only路径；model_messages只包含固定system、问题与原始observation，不含gold、family/stratum标签、证书、规则预测或selector状态。normalized rows为公共确定性IR，供所有选择策略同等使用。它能使CPU直接算gold，所以称免人工逐题标注，而非gold不可获得。

## 新保留构建谱系
开发族D_flat_explicit继承已暴露的flat-coordinate范式，只供工程/开发。保留族为两个独立内容构建根：
- H_fragment_offsets_scope：分片本地坐标+offset还原全局顺序，并依据声明的scope排除其他片；原始观测保留分片结构，不是仅换平铺文本实体。
- H_multiline_record_assembly：记录起始物理行+多个continuation_parts，拼接完整多行text并按included筛选；不是Calendar字段列表或旧单行regex模板。

两个保留族的构建函数/seed/模板/基础fixture均不进入开发族；未调用P9/P10/P14/R1生成器。共用规范化字段、first/last等有限操作、纯变换/JSON传输工具属于显式共享语义，不是新工具或现实OOD证据。此处family-heldout指来源结构/构建谱系，不能扩大成完整任务语义独立。没有对未检查的全部历史资产作无重叠保证。

8个开发题；16个保留题=2构建族×4结构格（无included候选、不同text、数字/line字面text、重复text）×2配对意图，共8个保留基础fixture。规模用于诊断工程覆盖，不是功效结论。数字/line字面值等类型测试锚点可跨族共享；不谎称所有词面/实体完全互斥。按基础fixture和构建族分组，不能把配对意图/变换当独立样本。

gold由独立validator从原始观测重新还原并核对；保留数据不运行selector、模拟器方法或模型，也无任何自然响应。人工/代码可审查生成输入；这是流程隔离，不是加密隔离。所有后续见过结果的数据均视为已暴露；任何修订必须新版本、新manifest。
补充：scope/included依据公开任务契约先确定，当前不是待诊断的假设维度；忽略scope、未覆盖编码、混合策略等都可能导致unknown，不能把unknown归成某一种原因。
