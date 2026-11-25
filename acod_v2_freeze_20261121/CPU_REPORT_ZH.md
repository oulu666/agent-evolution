# ACOD v2 CPU验收与保留输入冻结报告

时间：2026-11-21 14:18:20 +0800（Asia/Shanghai）。状态：已完成CPU冻结，停在此处。

## 实际验收
- 类型/行为/组合/先验/未来信息接口回归：842项，PASS 842，FAIL 0；标准库执行0.384181秒。包含768个规则×策略模拟器工程案例，不是自然根因gold。
- 独立数据验证：24题、168视图全部通过；负例9项全部成功拒绝，FAIL 0。
- 开发8题；保留16题、8个基础fixture、2个内容构建谱系（fragment offsets/scope，multiline logical-record assembly）。每族4格×2意图，非功效估计。
- 开发/保留case ID、基础fixture、真实模板交集均0；来源构建根与AST hash独立。共享有限选择/投影语义、类型锚点和变换工具；只称构建family-heldout，不称新工具或现实OOD。
- 先锁源代码/规则/指标/recipe，再生成保留数据；锁见PRE_DATA_LOCK.json。没有在保留集运行selector/模拟器方法或模型，没有自然响应可见。
- gold仅由独立validator自动核对；公开接口拒绝scorer路径。模型消息仅固定system+问题+原始observation，gold/分组/证书/假设预测不进入消息。不是加密或OS权限隔离。
- 历史90个资产SHA前后相等；round1文件清单和原manifest引用逐一核对不变。无首轮指标重算、无事后重新报成绩。

## 实际资源与限制
冻结阶段墙钟4.633192秒（生成/validator子过程分项见cpu_phase_receipts.json），另CPU回归0.384181秒；不是0 CPU成本。旧资产基线hash与人工编写耗时未包含在这个冻结阶段墙钟中。
CUDA_VISIBLE_DEVICES为空；没有导入torch/transformers/peft/bitsandbytes，没有加载模型、tokenizer、checkpoint，没有推理/训练/GPU任务、API花费、push或外发。

## 命令与复核
在原项目根用已有.venv：
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B acod_v2_freeze_20261121/build_data.py before
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B acod_v2_freeze_20261121/test_v2.py
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B acod_v2_freeze_20261121/seal_and_freeze.py

再次生成/测试/冻结拒绝覆盖；复核使用verify_freeze.py。manifest.json包含代码/协议/数据/CPU证据SHA，manifest.sha256记录自身SHA。不得原地修改。

## 未做
未开新模型实验；无自然模型正确率、诊断率、概率校准、跨新工具结果或统计显著性。尚无新ACOD算法；GBS/IG为成熟强基线。此步与首轮小样本都不能用来筛掉方法。下一轮需另行授权、冻结runner/环境/模型身份，并遵循PREREG_NEXT_ZH.md，当前没有自动继续任务。
