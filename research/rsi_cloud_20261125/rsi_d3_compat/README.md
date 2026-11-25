# D3 历史兼容性双修复：Pillow 10.4.0 → 12.0.0

一条保留 ICC 的 RGB 标记导出依次做颜色配置转换与绘图；真实 Pillow 10.4.0 和 12.0.0 的 PyPI wheel 在隔离进程中执行，不改库、不打桩。实际 PNG 写出重读，核对 ICC profile、颜色模式、尺寸、标记内像素与背景像素。24 张受控生成图是相同兼容边界的变体，**不是 24 个真实缺陷**。

| 方案 | 10.4.0 正确 | 12.0.0 正确 | 12.0.0 最先失败 |
|---|---:|---:|---|
| 旧调用：旧 ICC 标志 + 绘图 hints | 24/24 | 0/24 | ICC：24 |
| 只改 ICC 标志 | 24/24 | 0/24 | 绘图：24 |
| 只移除绘图 hints | 24/24 | 0/24 | ICC：24 |
| 两条官方替代合并 | 24/24 | 24/24 | 无 |
| 显式惰性 fallback + 移除 hints | 24/24 | 24/24 | 无 |
| 给 getattr 传旧属性作为默认值 + 移除 hints | 24/24 | 0/24 | ICC：24 |

公开文档明确 [ImageCms 标志迁移](https://pillow.readthedocs.io/en/stable/deprecations.html#imagecms-constants-and-versions-function) 和 [ImageDraw.getdraw hints 被移除](https://pillow.readthedocs.io/en/stable/deprecations.html#imagedraw-getdraw-hints-parameter)。ICC 调用先抛出时，后续第二项失败完全被遮蔽；单独修 ICC 才在所有目标执行中观察到绘图失败。两项修复在当前流程里互补，但文档已准确给出合并方案，而且一次任务执行能全通过，**不存在超越文档直改基线的空间**。eager fallback 实例展示了 Python 会在函数调用之前先计算默认实参；它不是库的第三个独立兼容改变。

初次原型传入错误颜色类型与参数位置，旧版本对照全部失败；修正公共测试夹具后才采信结果，初版和说明仍在此。无独立留出缺陷，无新方法优越主张。全部为本地安全的功能性变换。

## 复现

Python 3.12、Linux x86_64 wheel：

```bash
mkdir -p wheels releases
python -m pip download --only-binary=:all: --no-deps -d wheels Pillow==10.4.0
python -m pip download --only-binary=:all: --no-deps -d wheels Pillow==12.0.0
(cd wheels && sha256sum -c ../rsi_d3_compat/WHEELS.sha256)
for v in 10.4.0 12.0.0; do python -m zipfile -e wheels/pillow-${v}-*.whl releases/"$v"; done
sha256sum -c rsi_d3_compat/LOCK.sha256
python rsi_d3_compat/pilot.py --roots releases --out rsi_d3_compat/results
```
