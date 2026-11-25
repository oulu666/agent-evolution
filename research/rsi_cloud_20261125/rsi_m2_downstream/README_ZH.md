# M2：一个真实外部调用方重放了 Matplotlib 标题回归

复跑的是独立作者的 [2023 图表教程，Polar Axis 原始代码](https://github.com/mpolinowski/python-matplotlib-2023/blob/7a63e5e9b74fd0346beeca306122c648f97279d8/README.md#polar-axis)，不是 Matplotlib 的问题示例，也不是本项目设计的新图。固定提交日期是 2023-05-06；提交里的 [柱状图](https://github.com/mpolinowski/python-matplotlib-2023/blob/7a63e5e9b74fd0346beeca306122c648f97279d8/assets/Matplotlib_Pyplot_Cheat_Sheet_27.webp) 与 [线图](https://github.com/mpolinowski/python-matplotlib-2023/blob/7a63e5e9b74fd0346beeca306122c648f97279d8/assets/Matplotlib_Pyplot_Cheat_Sheet_28.webp) 都清楚把标题与 90° 标签分开。这是早于 [上游 2024-12 问题记录](https://github.com/matplotlib/matplotlib/issues/29381) 的真实外部教育用例，不是生产事故或具备显式断言的下游回归测试。

| 路线 | 符合判据 | 标题至角度标签间距 |
|---|---:|---:|
| Matplotlib 3.9.4 原调用 | 2/2 | +4.333 px |
| Matplotlib 3.10.0 原调用 | 0/2 | −22.111 px |
| Matplotlib 3.10.1 原调用 | 2/2 | +4.333 px |
| Matplotlib 3.10.0，同信息原生 set_title 显式 y | 2/2 | +47.189 px |

实际重放四个固定源码块（两段准备、两段绘制与导出），只重定向存盘为内存 WebP。隔离加载三个真实发行 wheel。8 份 WebP 都可读，线条数据、柱高及标题字符串均没有改变。独立验收比较实际渲染器给出的文本包围盒；负间距表示重叠。旧版原生适配只使用已经可见的轴、标题与公开位置参数，未读取老参考图、未换版本、未读上游补丁或增加其他渲染；同一质量约束下能修复，但留白明显比原图大，不能称逐像素复原。没有提供检测未知布局退化的算法。

## 筛选与边界

- Windrose 1.9.2（2024-07-30）固定标签下确有 samples/example_pdf_by.py 的轴标题调用，但未查到该精确调用在问题前的可用参考输出或相关断言，不能仅凭标题文字推定布局义务。未执行。
- pycircstat/Pingouin 的有界检索中未找到符合“问题前固定源 + 隐式极坐标标题 + 对应原始输出”的可独立重放案。
- 因此只记录一个强证据的外部教育调用方，两个独立源码单元，不是两个外部项目。没有把没有标题的第三张图当作见证。未验证其他第三方软件、操作系统、字体或现场影响。

## Replay

需要 rsi_l2_apps 中按其锁文件配置的 Matplotlib 3.9.4 / 3.10.0 / 3.10.1 私有 wheel 解压目录（或任何等价绝对目录），及上述固定提交的原始 README.md。下载原文但不要把它或图片放入交付包。程序检查 SHA-256 并限制可执行片段的 AST。执行：

    sha256sum -c SEARCH.sha256
    sha256sum -c LOCK.sha256
    MPLCONFIGDIR=/tmp/m2-agg-cache python3 -B run.py ../rsi_l2_apps/releases /path/to/exact-README.md | diff -u aggregate.json -

此次运行依赖与 L2 相同；字体配置改变可能导致记录的精确像素间距变化。输出汇总不包含第三方代码或参考图片。

