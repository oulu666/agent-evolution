# L2：完成两个“曾正确 → 后失败 → 修复”严格三版本

在单个 Linux CPython 3.12 x86-64 环境中实际执行六个公开发行 wheel，各进程核验版本和导入路径。所有输入为离线生成的小数组和图，测试普通数值与绘图语义；没有测试安全问题或改动项目代码。

| 上游记录 | 曾正确版本 | 故障版本 | 修复版本 | 故障版原生适配 | 严格配对见证 |
|---|---:|---:|---:|---:|---:|
| [Matplotlib 极坐标标题 #29381](https://github.com/matplotlib/matplotlib/issues/29381) | 3.9.4：12/12 | 3.10.0：0/12 | 3.10.1：12/12 | 12/12 | 12 |
| [scikit-learn 近常量特征 #32259](https://github.com/scikit-learn/scikit-learn/pull/32259/files) | 1.5.2：9/12 | 1.7.2：0/12 | 1.8.0：9/12 | 9/12 | 9 |

各行另有 4 个不变对照，每种版本与适配都通过 4/4。两个独立缺陷的 21 个见证不是 21 个独立缺陷，也不代表其间每个版本都失败。

- **Matplotlib：** 固定合法线条及标题，Agg 实际生成 PNG；独立语义判据是标题不与有横向重叠的角度标签相交、不被画布裁掉，原始线条不变。故障版用公开参数预留上边距、指定标题位置就恢复。同一任务不是对图像二进制逐字节比对。
- **scikit-learn：** 决策树在仪器噪声容差以下的特征不应切分，且应对四个新行给出指定分类。故障版通过应用本来就知道的容差，将该通道设为常量后再用公开 fit/predict，可恢复 9 个见证。另 3 个输入未通过早期/修复版/原生适配的组合判据，保留为非见证，不放松验收，也不把这 3 个归咎于同一个已知回归。

筛选按 SEARCH.md 冻结的来源和优先级：scikit-learn 1.8 的明确近常量回归先入选，后续候选停止；Matplotlib 3.10.1 的数组透明度有已知修复但没有优先获得“早期发行已正确”证据，matshow 的早期与故障版对应实现一致，不计入；官方极坐标 issue 则明确点名 3.9.4 正确、3.10.0 失败，且本次实测验证。共执行两项，没有依赖第三个候选补分。**结论：** 得到两个严格回归见证，但同信息的原生调用与升级已恢复相同见证，未验证新算法。

## Replay

测试机使用 CPython 3.12.14、numpy 2.3.5、scipy 1.17.0、joblib 1.5.3、threadpoolctl 3.6.0、Pillow 13.0.0、contourpy 1.3.3、cycler 0.12.1、fonttools 4.61.1、kiwisolver 1.4.9、packaging 26.4、pyparsing 3.3.2、python-dateutil 4.0.0。各版本共用这些依赖：

```sh
mkdir -p wheels releases mplcache
for p in scikit-learn==1.5.2 scikit-learn==1.7.2 scikit-learn==1.8.0 matplotlib==3.9.4 matplotlib==3.10.0 matplotlib==3.10.1; do
  python3 -m pip download --no-deps --only-binary=:all: -d wheels "$p"
done
(cd wheels && sha256sum -c ../WHEELS.sha256)
for w in wheels/*.whl; do
  v=$(basename "$w" | cut -d- -f1-2)
  python3 -m zipfile -e "$w" "releases/$v"
done
sha256sum -c SEARCH.sha256
sha256sum -c LOCK.sha256
MPLCONFIGDIR="$(pwd)/mplcache" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -B run.py releases | diff -u aggregate.json -
```
