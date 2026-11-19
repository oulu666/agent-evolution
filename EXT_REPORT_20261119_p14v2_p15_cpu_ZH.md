# P14 v2 / P15 CPU阶段完成报告

2026-11-19（北京时间）。六项审查核实，P14v2只修元数据与group/fixture绑定，1392题gold不变、21模板/split保持。原P14v1和598个受保护旧文件hash不变。

已实现独立QLoRA训练/七skill双层评测/配对统计入口。新方法仅两模块：首次学习锚定T/A/gold-final风险分配，call/final完整turn监督mask；两消融对应逐模块。SeqFT/Uniform/P11适配/新法/两消融各18轨迹，共108，Full另18可选非默认。128更新/stage、384/trajectory，所有新流真实tokens冻结；Replay为双cap而非实得精确相等，跨组监督token不等明确披露。

CPU全量验收PASS，同一梯度引擎toy CPU恢复精确；GPU/AMP/吞吐未测。只读守卫发现launcher误报，保留原冻结并新增操作v2修正身份，最终safe=true、90W、无Apex/STOP/其它GPU。

请审阅重大成本：主矩阵41472更新、新input323,674,632、Replay cap94,371,840；生成请求上限940,032，无GPU时长实测，主模型/optimizer磁盘payload约21.8GB、保守阈值45.6GB。Full额外约12.68亿旧input，默认不跑。

P14v2 manifest：`da99ed3b8a7fa74b1d9fdcb25a6245d6c086358caf341588baff00f5a6fd4bb8`
P15应启动runtime_manifest_v2：`8627bee4336c47ecb95824dd78cebb66d8a39d452bc5c1fe31d700478471bc56`

完整证据、九项stage-token账本、启动批准文件和runner_v2命令见 `EXT_HANDOVER_20261119_p15_stageaware_ZH.md`。本阶段未创建批准文件、未GPU训练/推理、未commit/push/发GPT。
