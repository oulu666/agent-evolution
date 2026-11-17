# P7恢复修复：精确状态落盘与最小受影响配对重算

2026-11-15，北京时间。用户明确授权修复并续跑本轮P7，不扩到P8。

## 事实与原因边界
17:53:50旧resume rc=1：seed09 file.search_last_1重演后的参数hash不等于旧nll.json.parameter_hash。load_prefix确实恢复了参数、optimizer、scaler及Python/numpy/CPU/CUDA RNG，参数hash按排序后的可训练参数原始字节计算，未发现简单命名/排序变化。模型train/eval切换和评测间CPU/CUDA RNG恢复也存在，不能仅凭报错断言是哪一个随机源或GPU kernel造成漂移。
能够直接证实的恢复设计缺陷是：旧每剂量产物只保存参数hash、NLL和receipt，没有该剂量的参数/optimizer/scaler/RNG完整状态文件。resume要求重新计算必须bitwise得到旧hash，失败时无法从旧hash恢复原状态；具体数值漂移源不能从既有产物唯一追溯。本次不删除校验、不放宽相等条件、不伪造hash，也不宣称旧重建已成功。

## 最小修复
新增p7_fullstate_20261115.py：在新测量前保存可训练参数、完整optimizer state（保留8bit整数dtype）、scaler、Python/numpy/torch CPU/CUDA RNG、所有module train/eval状态、optimizer初始化标记。落盘文件SHA与语义hash双校验，读取后真实恢复，逐项hash完全相等；测量后再恢复同一状态并核验。NLL的参数hash必须等于checkpoint模型hash。相当于把不可可靠重演的问题改为精确状态恢复，不改变训练算法、学习率、剂量或评测规则。
新CPU测试用带dropout的微型网络+AdamW，验证恢复后同一次更新完全重现，以及磁盘往返后参数、optimizer/scaler/RNG/模式全部相同。正式GPU基线将先做相同精确磁盘恢复，再进行任何新更新；不额外增加GPU测试更新。

## 复用与重新计算
旧runs_ext_p7_response全部只读保留。新输出runs_ext_p7_statefix_20261115。
复用seed08完整5动作（10次逻辑更新、48题生成）、seed09完整DB filter两剂量和基线。校验原冻结数据/源代码/前缀文件，receipt的prefix_hash、dose、step和完整三族B1；所有复用源hash写入repair_manifest。
旧seed09 File未完整配对不复制，不把其旧单步NLL与新模型混用。新attempt从原相同前缀完整重算seed09剩余4动作及seed10全部5动作，共9配对、18次新诊断更新。逻辑全实验仍3种子×5动作×2=30更新，144题B1，不增加独立样本。对已复用种子/动作不要求凭空补新checkpoint，也不声称旧产物已有完整状态。
旧中断File的2次更新和17:53失败重建的1次更新单列额外开销，至少3次；因此新attempt完成后可核实累计物理更新至少33，不把中断未记录的生成token记零。旧17:47启动无实际更新凭据，不臆算为0或再加一次完整配对。

## 科学与安全边界
P7原协议与新check8/dev16、计划、候选、原P6holdout全部不改。开发收益选择器仅接dev响应与成本；check用于验证排序，不进策略。并非新算法正式胜出试验。
监督器保留单GPU、Apex/功率上限60W/连续检查失败守卫，同时尊重旧P7 STOP与新STOP，不自动清除。当前授权仅本次修复续跑；若游戏出现停止，不自动再恢复，不启动P8。
新启动入口scripts/run_p7_statefix_20261115.py --phase queue会启动GPU，不是查询。使用持久Windows wsl宿主保持前台Python进程，输出新日志。
CPU收尾入口：PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B -m fac_tinyagent.p7_statefix_report_20261115。
结果/交接/算法说明均为新statefix文件，不覆盖旧报告中关于重建成功的失实预期。
