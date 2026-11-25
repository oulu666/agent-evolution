# 兼容性有界预注册（所有新响应前锁定）
仅 historical_0_first / historical_1_last 两个既有历史开发题，均用original；不读入v2保留16题，不用reserved，无新数据。选择ID在查看本次输出前固定。旧raw已知，因此是开发兼容性检查，不是盲验证。
A：逐字重放round1四轮消息及原历史system；B：把同一个问题/TOOL RESULT观测按v2原system及两轮构造包装；C：保持B的system、原问题和同一观测，恢复历史四轮工具后回答阶段包装。B不是重跑v2复杂保留题，不能宣称复现了原失败率。
A与C只差system；B与C只差阶段包装。阶段包装包含提供既有assistant tool-call与将TOOL RESULT移至独立末轮user，不能进一步分辨这两个组成部分的各自作用。观测envelope/字段/行号/text字节和问题语义全程不变；不加字段提醒，不根据结果搜索prompt。
两份原checkpoint，各2题×3配置×1次B1 greedy，共12次；技术失败重试0；单次60秒、监督墙钟600秒，未完成就停，不自动恢复。不训练，不改旧文件。use_cache=False、max_new_tokens128，使用原generate_with_usage，无模板/解析修补。
主终点：完整单键answer JSON且value为string/null的schema计数。单键envelope、严格typed答案正确另列；整数9与string9不混同；不从record_key/start_line等对象提取答案。正确率只是描述，schema合格不代表理解正确。
判读：若B失败而A/C成功，只支持这两道历史开发题上阶段包装影响输出契约；若B/C均失败而A成功，支持system/阶段适配不足但不得再追调；若B也成功，说明历史简单payload未复现故障，原v2复杂任务的观测结构/语义变化仍未被本对照隔离。任何结果都不证明ACOD/MDCS有效或无效。
旧eval STOP经owner/time/reason及SHA核对，仅对该不可变历史超时artifact做作用域隔离，不删除/移动/改写；任意未知、修改后的或新STOP、游戏、其他GPU/项目进程均停止。本次有独立STOP，不清用户停止命令。
结束即释放GPU。原v2/round1/权重/.venv均不改；CPU检查不等于零CPU成本。不推断隐藏根因，不以2题淘汰研究方向。
