# 父文档谓词绑定 · 有界筛查

冻结协议提交是 `f0805b3742c2c5c6de728e49dd1d849cda16567b`。`protocol.md` 的 SHA-256 是 `9d78ae6bb3d790576deb83486166db8b284c73898a98e1520db89d9979089dd3`。检索开始时协议、`sentence_grounded.py` 和 `screening.py` 没有未提交改动。本笔记不记方法分数。

## 检索停在哪里

库池 20 个，查询固定为 `repo:{owner}/{name} is:pr is:merged fix in:title`，每个仓库一页 30 条，按冻结的相关度轮转。标题里的依赖升级、变更日志、错别字和空白修改记入 `title_skipped`，共 48 条，不占考察名额。Rich #3718 与 attrs #1427、#1428 没有出现在这 40 条里。

考察 40 条后停止，原因是 `40_examined`。机械规则写下的纳入是 4 条，没有到 10，也没有到计分所需的 6。没有第二轮查询，没有追加库。

三个库没有进入队列：

| 库 | 原因 |
| --- | --- |
| attrs | PyPI 的 GitHub 地址写在 `GitHub` 字段。冻结字段表只有 Source、Source Code、Repository、Homepage、Home 和 home_page，没有读到它 |
| hypothesis | 地址写在小写的 `source`。冻结字段表写的是 `Source`，大小写不一致，因此没读到 |
| beautifulsoup4 | 注册字段里的 Homepage 是 `https://www.crummy.com/software/BeautifulSoup/bs4/`，没有 github.com 地址 |

这是冻结解析器的边界，不是事后换库的理由。attrs 和 hypothesis 没有被拿来补足分母。

## 机械纳入的四条

四条都从父提交的原始文件重新取过。文件 SHA-256 与 `screening.json` 一致，引用句在父文件的空白折叠文本里。

### httpx #2669

[PR #2669](https://github.com/encode/httpx/pull/2669)，标题 “Fix exception suppression in asgi transport”。父提交 `f9abbbbb4898cac96420e5c5b9d34036a94d46bf`，文件 `httpx/_transports/asgi.py`，符号 `ASGITransport`。修复提交 `a682f6f1c7f1c5e10c66ae5bef139aea37ef0c4e`。

父文档原句：

> Can be set to `False` for use cases such as testing the content of a client 500 response.

上一句是 “Boolean indicating if exceptions in the application should be raised. Default to `True`.” 强记号是质量词 `false`。PR 正文写的是 `raise_app_exceptions=False` 且响应不完整时异常仍然抛出。这句话和那个开关是同一件事，但它是用途说明，不是无条件的“必须抛出某异常”。

### marshmallow #2792

[PR #2792](https://github.com/marshmallow-code/marshmallow/pull/2792)，标题 “Fix handling data_key in ValidationErrors raised in schema validators”。父提交 `a578ed23092bd558acfbd9cd09a164108689326d`，文件 `src/marshmallow/schema.py`，符号 `Schema.validate`。议题 [#2170](https://github.com/marshmallow-code/marshmallow/issues/2170)。修复提交 `9f751e1cef943e2ca1a77f93d3483b4a171d4303`。

父文档原句：

> If `None`, the value for `self.many` is used.

强记号是质量词 `none`。筛查日志里对上的行为片段是 PR 正文中的 `def validate_restricted_permission2(self, data, **kwargs) -> None:`。`None` 出现在返回注解里。PR 标题说的是校验器抛出的 `ValidationError` 如何处理 `data_key`。这句父文档说的是 `many is None` 时用 `self.many`。机械规则把它们连上了，科学标准要求的“同一条义务”并不成立。不把这一条当成能够计分的组。

### arrow #1242 与 #1264

[#1242](https://github.com/arrow-py/arrow/pull/1242) 的标题是 “Fix humanize reporting 'a month' for 16-day differences”，父提交 `67ca577fb248ce9d803a9a85584b90a77ca989f0`。议题 [#1240](https://github.com/arrow-py/arrow/issues/1240)。[#1264](https://github.com/arrow-py/arrow/pull/1264) 的标题是这条修复的回退，父提交 `b423717da81aaf8117313b4b377efaa6413a9639`，也就是 #1242 的修复提交。两句父文档是同一句，符号都是 `Arrow.humanize`，文件都是 `arrow/arrow.py`：

> :param only_distance: (optional) returns only time difference eg: "11 seconds" without "in" or "ago" part.

强记号是长度为 2 的引文 `in`。冻结实现用子串判断引文是否出现在 PR 文本里，`in` 会落进 “reporting” 这类普通英文。记录到的差异是 16 天被说成 “a month”，不是 `only_distance` 要不要带 “in” 或 “ago”。两句都在父树里，但都不是这次行为差的那条义务。按“一次独立修复算一组”，回退和原修复也不是两组。

## 40 条考察

| # | 库 | PR | 决定 | 理由 | 父提交 |
| --- | --- | --- | --- | --- | --- |
| 1 | click | [#3764](https://github.com/pallets/click/pull/3764) | `exclude` | `no_parent_sentence` | `150d1071d69c5cdad7de78590013ffe56cf9e3bb` |
| 2 | requests | [#7309](https://github.com/psf/requests/pull/7309) | `exclude` | `no_parent_sentence` | `bc7dd0fc4d56e808bcdd85ac2d797b3107c89259` |
| 3 | httpx | [#2669](https://github.com/encode/httpx/pull/2669) | `include` | `parent_sentence_states_obligation` | `f9abbbbb4898cac96420e5c5b9d34036a94d46bf` |
| 4 | pydantic | [#14201](https://github.com/pydantic/pydantic/pull/14201) | `exclude` | `not_a_behavior_repair` | `12edde5adebc13b74b45e11e966ddadfc99f8fa1` |
| 5 | pytest | [#14630](https://github.com/pytest-dev/pytest/pull/14630) | `exclude` | `ambiguous_obligation` | `6665a79fb9a6553ce4e1be5574c21a9e3b769eec` |
| 6 | Jinja2 | [#1367](https://github.com/pallets/jinja/pull/1367) | `exclude` | `no_parent_sentence` | `eaf0cca37baddfdbd065924194a948199186f397` |
| 7 | flask | [#5136](https://github.com/pallets/flask/pull/5136) | `exclude` | `ambiguous_obligation` | `b80baaf35985a9a48f2db903a21b6ee7e7cc7340` |
| 8 | werkzeug | [#3050](https://github.com/pallets/werkzeug/pull/3050) | `exclude` | `parent_sentence_absent_from_fix` | `22e00851b37fa232711f036c85d06508e729e15b` |
| 9 | marshmallow | [#2792](https://github.com/marshmallow-code/marshmallow/pull/2792) | `include` | `parent_sentence_states_obligation` | `a578ed23092bd558acfbd9cd09a164108689326d` |
| 10 | jsonschema | [#1562](https://github.com/python-jsonschema/jsonschema/pull/1562) | `exclude` | `no_parent_sentence` | `eda977904c0205be337ede3865834b50c50d5f24` |
| 11 | python-dateutil | [#1667](https://github.com/dateutil/dateutil/pull/1667) | `exclude` | `ambiguous_obligation` | `a78cbd81d5d03b5f126eb36edb92bca78972c804` |
| 12 | arrow | [#1264](https://github.com/arrow-py/arrow/pull/1264) | `include` | `parent_sentence_states_obligation` | `b423717da81aaf8117313b4b377efaa6413a9639` |
| 13 | rich | [#3180](https://github.com/Textualize/rich/pull/3180) | `exclude` | `no_parent_sentence` | `b32e42bda00c6275d4e18dcbe298268094359549` |
| 14 | lxml | [#521](https://github.com/lxml/lxml/pull/521) | `exclude` | `no_parent_sentence` | `56a851bb1446dcc0a0ec75fbc5e8b84e0b28d33f` |
| 15 | PyYAML | [#556](https://github.com/yaml/pyyaml/pull/556) | `exclude` | `no_parent_sentence` | `56644b3a9f80f72ed5ae3b474cef594bbb105fa5` |
| 16 | toml | [#433](https://github.com/uiri/toml/pull/433) | `exclude` | `not_a_behavior_repair` | `ce4f7a4ed14480171abf67c8bc80e2277e45d1d5` |
| 17 | tomli | [#67](https://github.com/hukkin/tomli/pull/67) | `exclude` | `no_parent_sentence` | `b0691ff9c998878176cab8cf26a864ab71ae39e1` |
| 18 | click | [#2930](https://github.com/pallets/click/pull/2930) | `exclude` | `ambiguous_obligation` | `011b9f9d190c71310264e6c54bae6259f5e38a9f` |
| 19 | requests | [#6951](https://github.com/psf/requests/pull/6951) | `exclude` | `ambiguous_obligation` | `c65c780849563c891f35ffc98d3198b71011c012` |
| 20 | httpx | [#3056](https://github.com/encode/httpx/pull/3056) | `exclude` | `predicate_not_about_recorded_difference` | `73e688875a3579b67eee5795839b9660a1cfe5d8` |
| 21 | pydantic | [#14413](https://github.com/pydantic/pydantic/pull/14413) | `exclude` | `not_a_behavior_repair` | `6d2a0265f568f2fc99d4470af9a4d5c9a5d237e0` |
| 22 | pytest | [#15399](https://github.com/pytest-dev/pytest/pull/15399) | `exclude` | `no_parent_sentence` | `c5a4d1418c0c7370d37772fe7ad1ebee0b207277` |
| 23 | Jinja2 | [#1665](https://github.com/pallets/jinja/pull/1665) | `exclude` | `no_parent_sentence` | `fbc3a696c729d177340cc089531de7e2e5b6f065` |
| 24 | flask | [#6096](https://github.com/pallets/flask/pull/6096) | `exclude` | `ambiguous_obligation` | `514fc6b3e8402e4c646d5284e97a4f0ab50a7c4b` |
| 25 | werkzeug | [#3299](https://github.com/pallets/werkzeug/pull/3299) | `exclude` | `ambiguous_obligation` | `fa93b5cee027bc9baadba67f21360a8a39b2317b` |
| 26 | marshmallow | [#2902](https://github.com/marshmallow-code/marshmallow/pull/2902) | `exclude` | `ambiguous_obligation` | `252090c7c707166cf4fcfcdc73eb4376b7bbc4b7` |
| 27 | jsonschema | [#1444](https://github.com/python-jsonschema/jsonschema/pull/1444) | `exclude` | `ambiguous_obligation` | `a7277432b0f7bcd0551f6e589d30457017125df4` |
| 28 | python-dateutil | [#1583](https://github.com/dateutil/dateutil/pull/1583) | `exclude` | `ambiguous_obligation` | `5391455e7c7839e300b63649041806fb5219432e` |
| 29 | arrow | [#1242](https://github.com/arrow-py/arrow/pull/1242) | `include` | `parent_sentence_states_obligation` | `67ca577fb248ce9d803a9a85584b90a77ca989f0` |
| 30 | rich | [#1643](https://github.com/Textualize/rich/pull/1643) | `exclude` | `no_parent_sentence` | `eb673d1204340738d3084ebc2e4c789a35a4e49b` |
| 31 | lxml | [#305](https://github.com/lxml/lxml/pull/305) | `exclude` | `not_a_behavior_repair` | `076c6740da7236ae6558436835b828da419f6476` |
| 32 | PyYAML | [#820](https://github.com/yaml/pyyaml/pull/820) | `exclude` | `no_parent_sentence` | `a2d19c0234866dc9d4d55abf3009699c258bb72f` |
| 33 | toml | [#431](https://github.com/uiri/toml/pull/431) | `exclude` | `predicate_not_about_recorded_difference` | `7ffcfa3a08ffdbead6c814bcbb7c3fcd1f3a499d` |
| 34 | tomli | [#27](https://github.com/hukkin/tomli/pull/27) | `exclude` | `not_a_behavior_repair` | `c1f87cef949b1477f574d31ce52ee4b572141328` |
| 35 | click | [#2724](https://github.com/pallets/click/pull/2724) | `exclude` | `ambiguous_obligation` | `c021f05c838c1d0401ebc340d1de9b663c7fb578` |
| 36 | requests | [#6963](https://github.com/psf/requests/pull/6963) | `exclude` | `no_parent_sentence` | `7bc45877a86192af77645e156eb3744f95b47dae` |
| 37 | httpx | [#2667](https://github.com/encode/httpx/pull/2667) | `exclude` | `no_parent_sentence` | `4b5a92e88e03443c2619f0905d756b159f9f0222` |
| 38 | pydantic | [#14377](https://github.com/pydantic/pydantic/pull/14377) | `exclude` | `ambiguous_obligation` | `1deb3acca0fd93166d2ee524aec87d0a296ad3d4` |
| 39 | pytest | [#15342](https://github.com/pytest-dev/pytest/pull/15342) | `exclude` | `no_parent_sentence` | `fc9a7ef678f64d17f1c03b619f3842ea1d127e74` |
| 40 | Jinja2 | [#1852](https://github.com/pallets/jinja/pull/1852) | `exclude` | `no_parent_sentence` | `48b0687e05a5466a91cd5812d604fa37ad0943b4` |

排除理由：`no_parent_sentence` 16，`ambiguous_obligation` 12，`not_a_behavior_repair` 5，`predicate_not_about_recorded_difference` 2，`parent_sentence_absent_from_fix` 1。机械纳入 4。父提交以 `screening.json` 为准。
