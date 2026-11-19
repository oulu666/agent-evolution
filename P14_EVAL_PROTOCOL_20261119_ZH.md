# P14 Calendar 评测协议与数据冻结 v1

日期：2026-11-19（北京时间，Asia/Shanghai）。P14 仅为协议和数据版本，不是方法训练实验。

## 1. 目标与研究边界
先保证实验能真实测出不同能力的退化与获取，再用充分、完整的等预算对照判断方法是否有效。本轮只设计、生成并冻结 Calendar 数据和可重复的 CPU schema/夹具执行/标注/覆盖/隔离/hash 验收；不加载模型、tokenizer、权重，不启动 Uniform / P11 / 新方法训练，不用 GPU，不提交或推送代码，不向 GPT 或其他外部服务发送研究文件。

P11 保留为既有基线；P13 保留为遗忘机制证据。不能把候选池缺少困难样本所导致的失败，当作方法无效；也不能把最终答案层的次要分数当作 MIR 已成立。数据按工具语义及用户任务需求预先构造，不依据任何待比方法的测试表现改题，更不为制造工具调用退化而改题。

## 2. 已核实的工具、历史格式及观测问题
来源：`fac_tinyagent/tools/calendar_tools.py`、`tools/base.py`、`research_data.py`、`metrics.py`、`sft/evaluate.py`、P11/P12/P13 原源码与报告；只读快照为 `data_ext_p14_eval_protocol/source_reference.zip`，机器可复核的 P11 实测统计为 `runs_ext_p14_eval_protocol/historical_audit.json`。

- `calendar_list({date: string})`：YYYY-MM-DD，返回当天事件，按 `(start,id)` 排序。
- `calendar_count({month: string})`：YYYY-MM，仅返回整月事件数；传完整日期是非法参数，不等价于按日计数。
- `calendar_search({title: string})`：标题子串检索。
- `calendar_free_slots({date: string,duration_minutes: integer})`：工作日空闲片段，时长 15–240 分钟。
- `calendar_attendees({event_id: string})`：某事件参与者。
这些 schema 均为 object，required 如上，additionalProperties=false。工具注册表运行时本身未强制拒绝所有额外键，因此本轮验收另行严格检查 schema。

没有独立的“地点提取工具”或“按日计数工具”：按日计数是 `calendar_list` + length；去重地点是 `calendar_list` + pluck(location,unique=true)；字段列表也是 list + pluck。现有 `project_answer` 的 pluck 总会按字典序排序，不保留时间顺序；本轮题干明确这一点。time 使用真实字段 `start`（HH:MM），同时每个非空事件仍含 `title/location/id/start/end/date/attendees`，不杜撰 time 参数。

旧 JSONL 字段包括 `episode_id/tool_family/split/template_id/skill/prompt/system/environment/expected_tool/expected_arguments/skill_labels/answer_spec/expected_observation/expected_final_answer/messages/data_signature`。本轮保留这些字段，并加 `query/strata/entity_set/fixture_path/skill_definition/replay_eligible/template_text`。

P11 的 `cal.count_date` dev 实际只有 4 题；地点 Replay 候选 8 条全部仅 1 个不同地点。验收会用原始候选 ID 对齐原训练题，并由原工具重新计算，不靠注释猜测。P12 源码明确记录 `day_as_month = calendar_count(month=完整日期)` 错误路由。P13 Phase0-B 历史独立报告显示 core(tool+args) 无退化，而严格 Joint 配对损失分别 4/4/2、合计 10 题；这不能表述为“完全没有遗忘”，也不等于 MIR 已有效。

## 3. 固定数据设计与规模

数据位于 `data_ext_p14_eval_protocol/`。train/dev/test 依次 696/348/348，共 1392 题；独立夹具 `fixtures/{split}.json`，不改旧夹具。每个最小可行任务格 train=24、dev=12、test=12。每格有 3 个独立表述模板，分别承载 8/4/4 个不同日期实体实例。

|任务组|最小格数|train|dev|test|
|---|---:|---:|---:|---:|
|按日计数：含 count / 不含 count 的问句 / 同义 total-tally / 日月易混淆|4|96|48|48|
|整月计数正对照|1|24|12|12|
|去重地点提取：可行的基数×重复×输入顺序组合|20|480|240|240|
|字段提取：title / location（保留重复） / id / start time|4|96|48|48|
|合计|29|696|348|348|

按日计数的事件数为 0/1/2/3/4/6，词面 count 与工具选择解耦；同一夹具有其他日期事件，月级正对照也有相邻日期事件。不能用“题干含 count 就选 calendar_count”的捷径解释正确路由。

地点核心覆盖（仅统计地点去重组）：

|分层|train|dev|test|
|---|---:|---:|---:|
|0 个不同地点|24|12|12|
|1 个不同地点|48|24|24|
|2 个不同地点|120|60|60|
|3 个及以上（实际分别含 3 与 4）|288|144|144|
|不重复（含空日）|240|120|120|
|部分重复|216|108|108|
|全部重复（至少 2 事件）|24|12|12|
|已排序（非平凡）|144|72|72|
|逆序（非平凡）|144|72|72|
|随机非单调顺序|120|60|60|
|常量顺序（1 地点）|48|24|24|
|顺序不适用（空日）|24|12|12|

“随机”用固定种子打乱，强制既非升序也非降序；排序标签依据工具返回的 start/id 顺序，而不是 fixture 文件存储顺序。fixture 存储刻意反转，原工具正确还原时间顺序。

结构不可能的格不伪造样本：0 地点定义为空日（不是事件缺 location），重复程度为空集合时归为无重复；1 地点不可能有非平凡升/降/随机比较；2 个互异值无重复时不存在既非升序也非降序的排列；全部重复不可能同时是 2+ 个不同地点。覆盖按这些可行格验收，不宣称全笛卡尔积。字段原始返回同时包含多个易混字段，location 字段题保留重复，与唯一地点输出分开定义技能。

## 4. 严格拆分与盲测纪律
- 生成时按 split 独立实体命名空间与不相交日期段：train 从 2030 年、dev 从 2040 年、test 从 2050 年起，均为合成日历，不代表真实预约。
- 验收题干全文、模板 ID、**真实模板文本（不是仅改 ID）**、日期、月份、事件 ID、标题、地点、参与者，train/dev/test 两两交叉数必须全为 0。每个 split 独立夹具，执行时必须按行的 fixture_path 分批构造 registry，不能套旧默认夹具。
- schema 字段名、JSON 约定、通用时钟常量、技能操作定义可以共享；它们不是泄漏实体。保留相同任务难度，不进行“训练没有、测试才有”的难度外推。
- `replay_candidates.json` 必须只索引全部 696 条 train 题，包括 3+/4 地点、去重、非单调排序等困难样本；dev/test 禁止进入候选经验池。
- train 用于训练和回放。dev 用于方法开发及预先允许的阈值/检查点选择。test 为盲测，只能在方案、预算与选择规则固定后由独立评分流程使用，不能在 dev 调参时查看 test 成绩；不得据 test 做下一次同版本方法选择。
- 本轮仅确定性程序查看 test gold 以验 schema/执行一致性，不运行任何方法，不读取方法测试成绩。这是流程盲测，不是加密访问控制，不能声称技术上不可访问。以后变更必须新版本、新 manifest、注明原因；不得原地重写本冻结包。

## 5. 指标：B1 严格 Joint + 双层逐技能报告
技能=工具×操作×输出，不只按工具名汇总。主协议仍 B1：
1. tool_correct：预测工具名等于 gold。
2. arguments_correct：参数对象独立比较，沿用 `answers_equal`；即使工具错也单独记录参数维度。
3. tool_args_core = tool_correct AND arguments_correct（工具调用层 Joint）。执行层 execution_success 另列，现有评分器定义为预测 observation 与 gold observation 一致，不仅仅是 ok=true。
4. final_correct：最终答案与 gold 用现有 `answers_equal` 比较；列表长度与顺序严格，字串严格，数值沿用现有 1e-4 容差。真实 rollout 和给定 gold observation 的答案诊断必须分开标注，不能混为一谈。
5. **B1 strict Joint = tool_correct AND arguments_correct AND execution_success AND final_correct**，不是只报 tool_args_core。空数组/空日也必须按这一标准处理。

每一阶段、每个种子、每个技能都同时报告调用层、执行层、最终答案层、严格 Joint，给出正确数/总数；总体准确率只能补充，不能替代逐技能结果。必须记录旧技能保持、新技能获取及每种指标下的正确→错误/错误→正确配对事件。旧技能必须在先前已暴露/训练后度量；未学会的能力缺口不能称遗忘，尤其历史 `filter_cmp_top` 是能力缺口。建议同时列当前分数、首次学习后分数、历史峰值与差值，避免总体提升掩盖旧技能牺牲。多种子只称“方向一致”，不凭小样本称显著。

不再用 4 条 dev 探针或 3/4 正确定义已掌握。不再以“必须先出现若干次工具调用退化”作为方法继续与否的统一门槛。工程冒烟仅检代码、梯度、状态恢复、数据正确性；本轮 CPU 不运行梯度/模型状态测试。若完整、覆盖合理、训练时长合理、多种子、等预算的对照仍无优势，应接受当前条件下的负面结论，不能反复改题或追加预算直到正结果。

## 6. 持续学习组装因素（均未启动）
`continual_factors.json` 预留 counts/locations/fields 三组的 6 个顺序，按阶段动态分 old/new/unlearned；各题有 operation_group、error_facets、interference_groups、stage_role、interference_eligible 标注。可比较不同顺序、不同新旧技能组合、低/中/高共享工具或输出操作干扰；这些是组装条件，不是已证明的实际干扰强度。本轮没有运行任何顺序或模型训练，角色不从 test 正误倒推。

后续需用户批准，另行冻结阶段长度、训练种子（预留17/29/43）、任务顺序/混合比例、训练步数、回放 token/监督 token 双预算、候选池访问范围、选择规则、检查点和终止时长，再启动 Uniform / 原 P11 适配基线 / 新方法 / 关键消融的完整对照。方法工程检查不能重新变成算法有效性的晋级门槛。各臂相同初始状态、序列、数据、更新和预算；虚拟更新、打分推理与 wall time 另列算力开销，不靠额外计算“等预算”。本轮不设计或开跑新的多模块算法。

## 7. 可复现 CPU 验收与冻结范围
在 WSL 项目根目录使用现有 Python：

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' .venv/bin/python -B data_ext_p14_eval_protocol/p14_cpu_freeze.py
```

只依赖标准库及现有 Calendar/metrics 代码。为避免导入任何训练依赖，AST 提取并执行原 `research_data.project_answer` 的纯函数；另外从原始 fixture 独立计算 gold，双重核对。验收直接执行原 `build_calendar_registry`，不模拟/猜接口；覆盖所有 1392 题的 schema、observation、gold、实际顺序与去重标签，B1 全部16种布尔真值表。禁止 torch/transformers/peft/bitsandbytes 导入。运行前后只读查询 nvidia-smi，如发现任何 compute 进程立即停止，不干扰。所有已有 Python、根报告与历史 data_ext_p* 的 JSON/JSONL/SQLite 先后 hash 核对；不遍历或修改 .venv，不读权重。

生成文件已存在时只允许字节完全相同，否则报错，绝不覆盖旧冻结；同一命令再次执行即验证确定性再生成。manifest 包含数据、模板、经验池、因素、生成验收脚本、参考快照和本协议的 SHA256；自身 hash 写于 `manifest.sha256`，CPU 输出另存 `runs_ext_p14_eval_protocol/`。交接及 CPU 报告不纳入 manifest 自引用。

限制：本轮覆盖 Calendar 的 count/list 后处理，不扩展 free_slots/search/attendees、其他家族、自然语言复杂多步工具链、缺失/null 地点或时区/跨日事件。没有 tokenizer 长度/模型可学性、统计功效或训练预算可行性的实证，12 题/最小格只是覆盖下限而非显著性保证；未来正式实验应保留逐格计数和不确定性，不能据本轮正确性通过宣称方法有效。若接旧 evaluator，其单一 calendar_path 参数需按 split 指定本夹具；本轮不改 evaluator 核心。合成实体带 split 命名空间和年份分离，属于受控实体/表述 holdout，不宣称现实 OOD。先验明确的组合缺口见第3节。
