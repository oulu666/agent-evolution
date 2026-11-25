# 首轮结果补充审计（事后描述，非主分析改版）
时间：2026-11-21 14:04:04 +0800（Asia/Shanghai）
所有以下统计均基于已保存224条真实输出；没有新增生成、改提示、扩规则或重算主指标。
实际监督器运行：2026-11-21 13:56:19 +0800—2026-11-21 14:02:52 +0800（北京时间），392.865秒，rc=0。

## 关键限制：规则库和输出表示
输出表型计数：{'numeric_string_matching_line': 72, 'line_prefixed_string_matching_line': 21, 'other': 3, 'exact_complete_text': 128}。
25个full-pool unknown任务实例中，带至少一条字符串行号/line前缀行号的有23个。这里的任务实例包含两个checkpoint的配对题，不能当独立样本。
冻结field_line仅预测JSON整数；例如实际{"answer":"9"}和{"answer":"line 9"}都不匹配整数9。严格类型比较有审计价值，但若研究目标是语义行为诊断，这个规则库显然不充分，unknown率不能直接解读为真实策略变化率。
另外，选择display-first并输出line是组合规则，库中没有。不能从单条line样式答案推出坐标选择正确或隐藏字段根因。下一版若研究表示归一化/组合语法，须另行预注册独立数据，不覆盖本轮主结果。
历史开发题只是复用P9/P10已有文件与问题，oracle工具JSON前缀本轮经统一compact/sorted序列化；不是历史逐字prompt或既有正常端到端成绩的复现。旧P10正式题没有重新使用。

## 强基线冗余
GBS与IG实际查询序列一致性：[{'seed': 20261108, 'budget': 1, 'same_GBS_IG_query_sequence': 16, 'tasks': 16}, {'seed': 20261108, 'budget': 2, 'same_GBS_IG_query_sequence': 16, 'tasks': 16}, {'seed': 20261108, 'budget': 4, 'same_GBS_IG_query_sequence': 16, 'tasks': 16}, {'seed': 20261109, 'budget': 1, 'same_GBS_IG_query_sequence': 16, 'tasks': 16}, {'seed': 20261109, 'budget': 2, 'same_GBS_IG_query_sequence': 16, 'tasks': 16}, {'seed': 20261109, 'budget': 4, 'same_GBS_IG_query_sequence': 16, 'tasks': 16}]。
两者实现的Gini均衡与entropy/cost目标一般不同，但此轮所有实际路径完全相同，应把本池结果作为同一个经验基线看待，不能包装成两个独立胜负证据。没有独立的“ACOD新算法”臂；此次是问题与基线协议工程。

## 本轮可支持的结论
1. 变换证书、开放拒判和固定表重放已打通，真实冻结推理可运行。
2. 当前7规则+严格类型不足以覆盖自然模型响应；这是协议/表示不足的证据，不是对研究方向的淘汰依据。
3. 1/2/4预算曲线没有展示IG/GBS超过固定/随机的稳定预测优势；不同支持集合大小和coverage需要共同解释，不能拿收缩或unknown增加当诊断成功。
4. 根因准确率、概率校准、新工具泛化、统计显著性均未建立。

下一轮首要决策不是增加GPU规模，而是冻结行为输出规范与可组合规则表示，并用独立保留文件检验预测；本轮数据从此均为开发暴露资产。
