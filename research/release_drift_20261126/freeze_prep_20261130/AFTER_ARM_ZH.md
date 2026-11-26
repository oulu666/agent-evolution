# 另一臂校准

**2026 年 11 月 26 日。** 这是校准，不是正式结果。补记协议是 [PROTOCOL_AFTER_ARM_ZH.md](PROTOCOL_AFTER_ARM_ZH.md)，提交 `7b2e502e1074d53b95581e3e59abaf45097ef748`。试跑发生在这次提交之后，当时工作区干净，`HEAD` 是实现提交 `c8a0e2c0c382b43c0fb6d6301053315813379553`。父进程是 CPython 3.12.3。没有把 3.12 当成 3.11。

[REPORT_ZH.md](REPORT_ZH.md) 仍是 PR #7 的接线回执。[GAPS_FOLLOWUP_ZH.md](GAPS_FOLLOWUP_ZH.md) 仍是上一份缺口回执。两份都没有改写。`results/calibration_receipt.json` 和 `results/gaps_followup_receipt.json` 没有覆盖。过夜决定和上级 `protocol.md` 的 11 月 30 日清单没有勾选。正式方法没有修改。正式四项配对比较没有开始。六个案例的 `signoff_ready` 全部为假。没有比较 before 与 after、parent 与 rev 来计分。

0、1、5 仍只来自协议里的三个点质量，`case_rows_used` 为假。它们不能替换正式分母，也不能用来在看见密封结局之后修改已经预注册的正式方法。现场返回没有和 expected 比较。

## 六项

| 事项 | 状态 | 证据 |
| --- | --- | --- |
| 1 另一臂 | 部分关闭 | 三个发布库的 after 进入了资料包版本；三个 slugify rev 已检出并分派，没有可签收的成功返回 |
| 2 Unidecode | 仍然开放 | 公开夹具没有精确钉扎，本次没有安装 |
| 3 结局先验 | 部分关闭 | 深度 3 仍数完且核对通过；没有 `outcome_prior`，未选序列；`[2]` 未使用 |
| 4 案例行损失 | 部分关闭 | 六行都是未定、交付当前；预期任务损失留空 |
| 5 CPython 3.11 | 关闭 | 针脚检查进程是仓库外的 CPython 3.11.18；正式随机对照没有运行 |
| 6 字段与不变量 | 部分关闭 | 没有新包裹，也没有新的跨字段不变量；周历年字符串和时长标量仍不可寻址 |

### 1. 另一臂：部分关闭

before 与 parent 沿用 [results/gaps_followup_receipt.json](results/gaps_followup_receipt.json)，没有重跑。另一臂使用同一预算：共享首请求不计次，探测、失败的未登记校验、在线复位各占一次，第四次恢复在进入适配器之前被拦截，信息是 `three additional calls already attempted`。

| 案例 | 请求的另一臂 | 库报告的版本 | 首请求 / 探测 / 复位 |
| --- | --- | --- | --- |
| xlsx-column | XlsxWriter 3.3.1 | 3.3.1 | 完成，字典 |
| xlsx-duration | XlsxWriter 1.3.8 | 1.3.8 | 完成，浮点 |
| babel-week | Babel 2.17.0 | 2.17.0 | 完成，字符串 |
| python-slugify-1 | rev `0c9b8e069994f6ab76b4f4f5efd2d85cf795bdd8` | 检出一致，调用未完成 | `ModuleNotFoundError: No module named 'unidecode'` |
| python-slugify-2 | rev `a1543fe0ae019606bec660d6cf2e70a435ff29e4` | 检出一致，调用未完成 | 同样的 `ModuleNotFoundError` |
| python-slugify-3 | rev `07155c2001580b0ec70b40f24a475baef6238aac` | 检出一致，调用未完成 | `AttributeError: module 'slugify' has no attribute 'slugify'` |

三个发布库的成功调用版本与资料包一致。slugify 的三条错误都带有 `checked_out=` 和资料包里的完整 rev。没有改用另一个提交，也没有换成另一个 python-slugify。python-slugify-3 的 rev 复现了与存档 parent 相同的属性错误，这个失败就是该提交的记录。前两个 rev 在进入 `slugify` 之前缺少 `unidecode`，所以没有库返回。失败调用占用了额度。

上一份回执里的 before / parent 版本仍是：XlsxWriter 3.3.0 与 1.3.7，Babel 2.16.0，slugify parent `eeabcc29eb67dd9ab34c693db44f9ece312e7a2c` 与 `4091b444746032847ccce0d5c6a0cd5b1bb73d81`。python-slugify-3 的 parent `3d75734751b36ae14feab0d84f5d670f1d6225e3` 当时已经按脚本执行，返回的是导入错误，没有成功版本字符串。

### 2. Unidecode：仍然开放

六份资料包和协议允许名单里都没有 `unidecode` 这几个字，因此没有 `Unidecode==` 精确钉扎。本次没有安装任何 Unidecode，也没有把版本写进仓库。三个 rev 的检出声明仍是 `Unidecode>=0.04.16`，这是库声明里的范围，不是公开夹具的钉扎，也没有拿来安装。

slugify 的 `signoff_quality_receipt` 全部为假。前两个 rev 没有现场字符串。第三个 rev 的属性错误也不是签收质量回执。

### 3. 结局先验：部分关闭

允许名单里的 JSON 和六份资料包都没有顶层 `outcome_prior`。`expected` 仍是库输出，不是正确、暂缓、错误上的三元质量。开发结果里的行级 `outcome` 和 `loss` 没有抄进回执。三个发布案例的 `preplanned` 仍是 `[2]`，`matches_direction_gate` 和 `development_preplanned_used` 都为假。slugify 没有这个键。

因此没有对任何序列调用 `expected_task_loss`，`sequence_selected` 为假。两臂设置相同，`check_search_parity` 通过。枚举条数仍是：列 65641，时长 259，周历年 8421，每个 slugify 1885。

### 4. 案例行损失：部分关闭

六个案例的上一臂脚本和这一臂脚本都已经走完，`both_arms_ran` 为真。表达式表仍是空规则表，没有已登记裁决，也没有三元质量。六行裁决都是未定，动作为交付当前，`expected_task_loss` 为 `null`，`evidence_sufficient` 为假，`formal_score` 为假，标签是 `calibration`。没有用现场返回是否等于 expected 来填损失。六行相同是因为规则相同，不是六个分数。

### 5. CPython 3.11：关闭

`uv` 已在用户主目录。`uv python find 3.11` 给出的解释器是：

`/home/ubuntu/.local/share/uv/python/cpython-3.11.18-linux-x86_64-gnu/bin/python3.11`

该进程自报 CPython 3.11.18，`version_info` 为 `[3, 11, 18]`。它为六个案例分别构造了 `random.Random(20261126)`，没有抽取请求，没有调用三个库。`random_arm_comparison_ran` 为假，`formal_paired_comparison_started` 为假。父进程仍是 3.12.3，路径与针脚解释器不同。

解释器不在仓库里，也不在默认 `PATH` 上。安装器留在 `~/.local/bin/python3.11` 的符号链接已经去掉，uv 目录里的解释器还在。逆操作是 `uv python uninstall 3.11`。这次哈希只覆盖校准登记，`formal_checklist_ticked` 为假，总摘要是 `f7443d2963980effcbb30eff9d96ea95e0d41730e72d1c4b86e3de3dd08d617f`。

### 6. 字段与不变量：部分关闭

没有把周历年字符串或时长档案标量包进新结构。档案类型仍是周历年 `str`、时长 `float`，两处 `addressable` 为假，`wrapped` 和 `new_wrapper` 为假。跨字段不变量表是空的。slugify 没有新的字段包裹。这一项不能关闭。

## 重跑

单元测试不读取公开语料：

```
python3 research/release_drift_20261126/freeze_prep_20261130/test_after_arm.py
python3 research/release_drift_20261126/freeze_prep_20261130/test_followup.py
python3 research/release_drift_20261126/freeze_prep_20261130/test_harness.py
python3 research/release_drift_20261126/test_freeze_guards.py
```

另一臂试跑要求补记协议已经提交，且工作区干净：

```
python3 research/release_drift_20261126/freeze_prep_20261130/run_after_arm.py
```

输出是 [results/after_arm_receipt.json](results/after_arm_receipt.json) 和 [results/after_arm_log.txt](results/after_arm_log.txt)。
