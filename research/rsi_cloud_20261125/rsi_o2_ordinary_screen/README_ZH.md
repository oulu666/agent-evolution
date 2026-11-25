# O2：两个真实公开功能异常可复现，均被强普通方法覆盖
| 上游 | 本次筛查 | 决策 |
|---|---|---|
| [pandas #65118](https://github.com/pandas-dev/pandas/issues/65118)，单列混合类型 MultiIndex 写入被忽略 | 官方报告有同版完整元组索引解法；本次未用受影响 3.0.2 重跑 | 文献排除，非本地基线实测 |
| [pandas #71941](https://github.com/pandas-dev/pandas/issues/71941)，SQL 存储时间差错用微秒 | 同样显式微秒输入，pandas 3.1.0/3.1.1 默认 0/4，公开 as_unit 转纳秒后 4/4；同版共用两动作上限。2.2.3 显式微秒对照也为 0/2→2/2 | 排除，文档转换即可解决；2.2.3 对照不代表其默认构造行为，不证明 3.0 才引入问题 |
| [SciPy #24767](https://github.com/scipy/scipy/issues/24767)，MINPACK 少报 Jacobian 调用数 | SciPy 1.17.0，两方法两起点，默认数量 0/4，包装公开回调后 4/4，两个路线均为 24 个计费动作，按真实进回调次数核定且检验求解残差 | 排除，包装回调可解决，对现有工作负载不需要新算法 |
  
[IO 文档](https://pandas.pydata.org/docs/user_guide/io.html)约定 SQL 写为纳秒；[公开单位转换](https://pandas.pydata.org/docs/reference/api/pandas.Series.dt.as_unit.html)是同版基线。两个功能机制有实际运行证据，未纳入的第一个只是文献筛查；仅这些版本和小输入，不代表任何缺陷都可修。总计 78/240 动作，单线程 CPU，无 GPU/API/付费计算。准入零，没有启动候选算法，没有独立验证，不自动延伸这条案例链。公开档案只有代码、协议、可复现说明和聚合。
  
## 复现
CPython 3.12、NumPy 2.3.5；pandas 2.2.3、SciPy 1.17.0 在默认环境；pandas 3.1.0、3.1.1 分别解压或安装到独立目标目录作为 `--localsite`。使用 `python -I -B screen.py pandas VERSION OUTPUT.jsonl [--localsite PATH]`／`python -I -B screen.py scipy 1.17.0 OUTPUT.jsonl` 输出按 `pandas-2.2.3.jsonl` 等固定命名至一个新目录，再以 `python -I -B summarize.py OUTDIR` 核对聚合。每个首跑逐条哈希且即时落盘，结束后按文件生成 SHA-256。
