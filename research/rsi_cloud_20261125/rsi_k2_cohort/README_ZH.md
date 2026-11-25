# K2：三个真实版本的功能差异

云端 CPython 3.12 Linux x86-64 核验六个公开发行 wheel，以隔离进程加载，校验版本和路径。使用本地生成的普通合法输入。以下复现上游公开修复，不证明更早版本曾经正确，也不是历史缺陷盲测或发生率估计。

| 已公开修复与端点 | 旧版原调用 | 旧版原生调用适配 | 新版原调用 | 不变对照（各方法） |
|---|---:|---:|---:|---:|
| [Pillow #8443](https://github.com/python-pillow/Pillow/pull/8443)，10.4.0 → 12.0.0 | 0/12 | 12/12 | 12/12 | 4/4 |
| [Click #3434](https://github.com/pallets/click/pull/3434)，8.3.3 → 8.4.0 | 0/12 | 12/12 | 12/12 | 4/4 |
| [wcwidth Hangul 修复](https://pypi.org/project/wcwidth/0.2.13/)，0.2.9 → 0.2.14 | 0/12 | 12/12 | 12/12 | 4/4 |

- Pillow：合法的自产调色板动画图层，第二帧中的透明像素应保留底图。旧版错误地产生透明黑像素。旧版改用公开 Image.convert("RGBA") 后编码与新版均符合用两层输入独立计算的 RGBA 期待值。任务有输入图层可用，未声称能修复手头只有外部坏文件的情况。
- Click：不足参数的程序应该有基本 Usage 行。旧版 HelpFormatter.write_usage 只写空行；旧版用 formatter 公开 write 输出标题即可匹配独立文本判据。
- wcwidth：报表规定规范等价的现代韩文音节占两格。NFD 形态旧版测 3–4 格，新版测 2；只在算宽时先转换为 NFC 的公开 API 组合也测 2，发出的原文本不变。未测真实终端字体。

合计三项独立上游修复、36 个功能变体与 12 个不变对照，新版与旧版调用适配均 48/48。同项目补充结果是 [U+00AD 软连字符宽度修复](https://wcwidth.readthedocs.io/en/latest/history.html)，不作为第四独立条目，也不计入 48/48。证据支持保留旧版原生适配并加验收；这里没有提出或验证新算法。

## 筛选账本

先冻结 SEARCH.md 的来源、顺序、截止规则。下列是实际看过、与范围相符或接近的候选，并非统计全量 release notes。

- Pillow 11.0.0：LONG8 与 I;16 滤镜是新功能；句柄所有权不是图像产物；EPS 颜色配置需外部解释器，不在固定 wheels 验证边界。调色板 APNG 首个合格；TIFF 方向尺寸 #8390 和后续版本不再纳入主轮。既有 GIF 试验、移除项和安全条目全部排除。[官方变更记录](https://raw.githubusercontent.com/python-pillow/Pillow/12.0.0/CHANGES.rst)。
- Click 8.4.0：按实际使用说明优先于辅助格式化和标志仲裁，选择无参数空行问题。前序 default_map 元组变更排除。
- wcwidth 0.2.10–0.2.14：既测 VS16 排除，0.2.11–0.2.12 是打包项排除，0.2.13 Jamo 首个合格。测试文件也记录了同项目之后的 SHY；按预定顺序，是补充而非主条目。

## 复跑

下载 pillow==10.4.0、pillow==12.0.0、click==8.3.3、click==8.4.0、wcwidth==0.2.9、wcwidth==0.2.14 的公开 wheels 到 wheels/，按 WHEELS.sha256 验证。然后用 Python zipfile 把每份解压到 releases/<包>-<版本>；校验 SEARCH.sha256、LOCK.sha256、JAMO.sha256。执行以下命令核对汇总（输出不包含逐例数据）：

```bash
python3 -B run.py releases | python3 -B summarize.py | diff -u summary.json -
python3 -B jamo.py releases | python3 -B summarize.py | diff -u jamo_summary.json -
```
