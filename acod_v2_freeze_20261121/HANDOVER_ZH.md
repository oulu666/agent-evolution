# ACOD v2 冻结交接

Windows新增目录：C:\Users\Egret\Desktop\oulu\Agent Self-Evolution\fac_tinyagent\acod_v2_freeze_20261121
WSL新增目录：/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/acod_v2_freeze_20261121

本次授权止于代码、CPU验收与数据冻结。没有新模型推理/训练/分支GPU矩阵，没有自动启动后续实验。旧round1目录、旧runs、.venv、权重、冻结数据、原首轮主分析一律不修改；也不重报首轮百分比。

文件：
- REVISION_ZH.md：四层类型/行为解析、24可组合规则、等价类先验与边界。
- PREREG_NEXT_ZH.md：下一轮预算/指标/成本/拒判/执行条件；另需授权。
- core.py：纯CPU行为与选择器；interfaces.py：公开输入/模型消息边界（没有模型执行）。
- test_v2.py、cpu_regression.json：仅独立开发回归与模拟器工程检查，保留集未参与。
- build_data.py、validate_data.py、data_validation.json：构建与独立原始观测/gold/变换校验。
- data/development/public/cases.jsonl、data/heldout/public/cases.jsonl：唯一可给selector/模型接口的文件。
- data/*/scorer_only/gold.jsonl、data/scorer_only/groups.jsonl：仅评分/分组。
- data/validator_only/source_fixtures.jsonl：仅fixture一致性检查；不得用作模型额外证据。
- data/recipe_manifest.json：seed、真实模板/谱系与函数AST摘要。family-heldout而非新工具/OOD。
- legacy_before.json、legacy_unchanged.json：旧资产前后摘要证据。
- CPU_REPORT_ZH.md、manifest.json、manifest.sha256：实际验收结果与不可原地改写的冻结清单。

执行过的CPU命令见CPU_REPORT_ZH.md。再次执行测试/生成/冻结默认拒绝覆盖；复核用verify_freeze.py，不会加载模型。若要修订必须另起版本，不能覆盖冻结文件。流程访问限制不是OS/加密权限隔离，所有文件仍由用户控制。

下一步如获授权，先创建单独有界执行器并冻结其guard/环境/消息与model身份，复核manifest；当前没有运行中的任务需要接续，也不要创建routine或自动开GPU。即使下一轮结果不佳，也先判断测量/表示与可识别性，不能按小样本淘汰方向。