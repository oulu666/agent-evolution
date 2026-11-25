# RSI：跨版本差分作用域原型与实测

日期：2026-11-25。状态：**真实软件版本执行通过；未通过核心算法立项门槛。**

## 问题和新机制

ScopeRev v1 从新执行中学习“哪个开关影响哪条检查”。这次测试的是下一种候选：**差分作用域迁移（DeltaScope）**。设 `S_j(x)` 为旧环境中组合 x 对第 j 条检查的判定，`T_j(x)` 为当前环境的判定，学习 `D_j(x)=S_j(x) XOR T_j(x)` 的作用域，而非重新猜 `T_j` 的全部作用域。一条新反例只修改它有证据覆盖的差分格子，其他旧结果保留为先验；最终仍必须执行完整候选才能交付。预测不是交付证书。

算法对每条检查枚举 4 个开关的坐标子集：同投影但差分相反的假设被移除；其余假设按复杂度和观测后验式权重混合。未知差分采用固定 0.12 翻转先验。目标候选按五条检查分数的乘积排序，最终通过后再做额外输入复核。这个乘积只是搜索评分，不是实际联合正确概率。

成立条件具体可测：如果旧结果已知、差分确实只依赖 k 个三值开关且作用域已知，用 3^k 个不同投影即可恢复整个差分表；有 r 个开关的任意目标判定表则有 3^r 个格子。未知作用域、获取旧表的成本、以及已有强方法也会利用源证据，都不受这个计数保证。这里不声称对任意目标学习器存在查询优势。

## 文献压力测试

- [Partition-Based Regression Verification，ICSE](https://2013.icse-conferences.org/content/partition-based-regression-verification.html) 已做版本差分输入分区；[Difference Verification with Conditions](https://link.springer.com/chapter/10.1007/978-3-030-58768-0_8) 也定位当前版本相对旧版本的差异区域。不能把“分区学习版本差异”本身当作新颖性。
- [Invariant Models for Causal Transfer Learning，JMLR](https://jmlr.csail.mit.edu/papers/v19/16-432.html) 用条件不变性支持迁移；[Residual Transfer Networks](https://arxiv.org/abs/1602.04433) 使用残差来描述源和目标不同。差异假设仅是：**逐条黑盒修复反馈下，在相同完整候选执行预算内，差分作用域是否比直接学习目标作用域更有用**。
- [PreCA，JAIR](https://binsec.github.io/assets/publications/papers/2025-jair.pdf)、[QuACQ2，Artificial Intelligence](https://cgi.cse.unsw.edu.au/~tw/aij2023.pdf) 和 [GrowAcq，CP](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CP.2023.36) 覆盖黑盒约束获取、部分询问和增长候选约束空间。本轮“主动学习当前作用域”基线不是对这些论文的完整复现；它直接用同一个完整执行反馈接口比较，不把填默认值后的完整调用当成免费的部分查询。未来若挑战算法新颖性仍应实现反馈匹配的发表方法对照。

## 测试设计与冻结

- 在当前对话云电脑的 Linux CPU 上，从公开 PyPI wheels 隔离执行三组：wcwidth 0.2.9/0.2.14、packaging 23.1/23.2、python-dateutil 2.8.1/2.8.2。每套环境验证版本号，调用真实库；没有模拟故障、GitHub 写入或语言模型跑分。
- 在每组有 16 个自动构造功能任务、两种方向的真实版本切换和两种同版本对照，合计 192 个场景。**不是 192 个独立缺陷。** 任务来自事先可见的上游变更记录，不能称为独立缺陷盲测。用 [wcwidth 历史](https://wcwidth.readthedocs.io/en/latest/history.html)、[packaging 23.2 变更记录](https://github.com/pypa/packaging/blob/main/CHANGELOG.rst) 和 [dateutil 变更记录](https://dateutil.readthedocs.io/en/stable/changelog.html#version-2-8-2-2021-07-08) 锚定功能行为。
- 每次在线执行一个完整修复配置，给所有方法同样的五维布尔反馈。相同的 81 个配置的源执行表事先提供给自适应候选；有源数据成本，未证明收益可摊销。各自适应方法共同从源最佳配置开始，预先声明主预算 3；2 和 6 是敏感性切片。工程固定规则按公开语义手写，不是盲选算法，列为上限对照。
- 通过开发时可见检查后执行一次额外保留输入，不把其反馈给搜索器；统计正确、错误和暂缓。额外检查由同一设计者构造，只算二次复核，不等于第三方完整规范。初始源码和计划哈希在试验前留存；后加的 audit 只做复核。

## 测试结果

每行分母均为 192。所有方法在复核输入上的已交付错误数为 0；未正确交付的均为暂缓。

| 方法 | 2 次预算内正确 | 3 次主预算内正确 | 3 次预算实际总调用 |
|--|--:|--:|--:|
| 直接复用源最优 | 160 | 160 | 192 |
| 冷启动主动作用域 | 160 | 168 | 256 |
| 共享源信息，主动学习目标绝对作用域 | 176 | 184 | 240 |
| 相同旧表，只记单个差分格子 | 160 | 172 | 256 |
| **DeltaScope 差分作用域** | **172** | **192** | **244** |
| **某条旧判据被证伪后，仅重学这一条** | **192** | **192** | **224** |
| 按公开规范写死的跨版本规则 | 192 | 192 | 192 |

主结果中 DeltaScope 比主动目标作用域多 8 个正确，但多花 4 次调用，且比逐条重学多花 20 次。逐条重学对 32 个源策略失败但可修的场景全部在第 2 次成功；在共享首查的策略里，这已经达到逐场景调用下界。预设的固定规则一遍就成功。这批任务对现有算法没有剩下可证实的收益空间。

### 真实差异不等于差分更容易学

从程序执行表逐条穷举，64/96 个版本切换场景至少一项判定变化；32 个确实改变了某条判定依赖的变量集合，其中 16 个同时造成复用错误。**没有一个发生变化的场景中，变化项的最小差分作用域严格小于它相应的目标作用域。** 低维差分这个假设没有得到本面板支持，不能把平局解释为仅仅样本太少。

例如 dateutil 2.8.1 接受并规范化 `2024-05-06T10:3456`，2.8.2 拒绝。为严格 ISO 子集交付时，从新版回迁旧版会失效；保留其他检查、只重新学习拒绝非法串的判据就足够。wcwidth 的 VS16 心形宽度在所测旧版是 1、新版是 2。详见 scope_audit.json 中的输入和原始输出。

## 决策

冻结 DeltaScope，不继续调先验，也不把 192/192 当成稳定进步。下一轮若投入：独立组题者应当先登记确实有任务损失、逐条重学/可移植固定规则尚无简解、且多个候选干预在当前可见回读上无法区别的自然版本切换。把真实依赖是否变化、差分结构是否更小作为离线分层，不能提供给规划器；把设计和留出答案分别保管。最少先证明存在可改进空间，再选算法机制。现有数据不支持 A 会主方法的结论。

## 复现

Python 3.12 + NumPy。不会安装 CUDA，也不运行用户本地项目。

```sh
mkdir -p wheels releases
for p in wcwidth==0.2.9 wcwidth==0.2.14 packaging==23.1 packaging==23.2 python-dateutil==2.8.1 python-dateutil==2.8.2 six==1.17.0; do
  python -m pip download --no-deps --only-binary=:all: -d wheels "$p"
done
(cd wheels && sha256sum -c ../rsi_transfer/WHEELS.sha256)
for w in wheels/*.whl; do
  python -m zipfile -e "$w" "releases/$(basename "$w" | cut -d- -f1-2)"
done
sha256sum -c rsi_transfer/LOCK.sha256
python rsi_transfer/main.py --roots releases --out rsi_transfer/results
python rsi_transfer/audit.py --roots releases --results rsi_transfer/results
```
