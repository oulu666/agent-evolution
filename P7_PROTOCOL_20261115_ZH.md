# P7：实际更新响应与梯度代理诊断

2026-11-15 北京时间。用户已授权开展下一轮实验；此协议在 P7 GPU 结果产生前冻结。

问题：P6 的开发梯度效用能否预测真实优化器短期更新收益？File/Median 的失败是执行、答案投影还是评分错误？

1. CPU 复核 P6 全部 432 个四技能结果，重执行 48 道 gold 工具调用、重算答案、逐项重算评分，统计 first/last 和错误工具。原结果只读。
2. 三个现有种子，中点 Calendar microstep80，完整恢复参数、PagedAdamW8bit 状态、scaler、RNG。随机化五动作运行顺序。动作是四技能候选或非目标背景；每次更新含同样七条 Calendar + 一条 replay，累积8，lr=1e-4，最多两次更新。每个动作独立从中点恢复。背景取每个种子均衡计划中第一条非目标样本；目标取 P6 固定候选序列前两项（不足则循环）。不另造训练经验。
3. 记录0/1/2更新的 P6 dev16题与新P7 check8题 NLL（分 tool/final span）；check每技能2题、新实体、新题面，生成和校验先于 GPU。第0/2更新在check8题做B1双阶段生成，3*(1+5)*8=144题。P6 holdout不进入GPU路径。仅诊断，非新方法正式功效试验。
4. 复用P6的池均值B、梯度范数和交叉dotmatrix；另测当前实际候选的单样本梯度，与dev宏梯度点积；保存实际Adam参数位移与dev梯度的一阶预测，从而区分池均值代理、样本差异、优化器方向和非线性响应。
5. 主输出为每种子、动作的宏NLL相对背景增益、单位replay输入token增益、check Joint变化；报告两个剂量及tool/final分解。动作不是独立种子；不把12个技能×种子当12个独立训练复本，不用小样本p值包装有效性。
6. 算法原型：从独立恢复的动作探针估计 V(k)=[L_dev(control)-L_dev(action k)]/实际replay_tokens；以最大V选下一动作。选动作仅用dev，check仅验证排序。比较P6 B/token的选择、实测V的选择、check事后最优（仅诊断oracle）。此为两步局部策略，不直接部署为完整EAAR，不外推终点训练收益。
7. 固定30次诊断optimizer.step；没有看到负结果就追加训练、阈值或种子。不同动作token长度如实列出，主要是等步数替换实验，单位token是成本归一化，不冒称精确等token因果实验。保存冻结hash、原始输出、成本、完整状态恢复校验。使用现有单GPU watchdog。

下一步决策：若gold/评分错误，独立修复并单列修正结果；若真实错误且局部NLL与Joint脱节，先设计针对实际失败环节的经验和验证信号；只有收益预测在独立check上有可用排序，才进入新的完整预算比较。无需复跑P5/P6。

方法工具参考：Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents. https://doi.org/10.48550/arXiv.2609.00065 （实验设计技能用于配对/分块与避免伪重复；本实验算法和结果由本地代码产生）。
