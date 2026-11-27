# 2026-11-27 公开近例筛选：没有合格案例

**2026 年 11 月 27 日。** 为检验接收端学习是否还能在查表与固定重放都漏掉的未见工作流上拦住错误放行，对公开近例做了两轮筛选。合取标准未放宽。合格案例为 0。没有实现，没有开拉取请求，也没有给 Material 复制或 jq 加规则。本稿只记录已经核对过的公开证据和当时的不合格原因，不是已经验证核心算法。

写稿所对照的仓库顶端是 main 的 [`88ca0d2090794b363c8db82a4106f2c952b69aec`](https://github.com/oulu666/agent-evolution/commit/88ca0d2090794b363c8db82a4106f2c952b69aec)（2026-11-27 09:38:51 +0800，合并 PR #11）。这些近例当时没有写入仓库。正式四项封存变化、11 月 30 日方法冻结清单和密封的 pandas、Pillow、SciPy 标签没有打开。已冻结协议的科学结论没有改写，计分没有重跑。

筛选依据写在已经冻结的 [receiver_learning/protocol.md](../receiver_learning/protocol.md)、[INCREMENT_ZH.md](../receiver_learning/INCREMENT_ZH.md) 和 [REPORT_ZH.md](../receiver_learning/REPORT_ZH.md)，以及更早的 [clipboard_decision/REPORT_ZH.md](../clipboard_decision/REPORT_ZH.md)。`question_selection` 在 PR #11 合并后仍为 `not_opened`。本稿不改变那一决定。

## 合取标准

一条公开近例要成为可据以继续实现的合格案例，须同时满足下列条件。缺任何一条都不纳入，也不在看过结果之后放宽。

1. **真实、已公开，并且不是发明材料。** 须有可核对的公开议题或修复说明。不得发明故障，不得用构造出来的工作流关闭缺口，也不得靠给已经用过的 Material 复制或 jq 任务加规则来制造分歧。
2. **未见工作流。** 须是 [receiver_learning/REPORT_ZH.md](../receiver_learning/REPORT_ZH.md) 研究分母之外的交付路径。已知的 Material 9.5.21 复制故障，以及作为跨工具机制测试、未经缺陷盲筛的 jq 数值压力组，只说明原型能跑，不能单独打开复杂选问。
3. **能在已冻结的封闭关系下与可信原文比较。** 可用关系只有短语表里已经写下的 `byte`、`full_string` 和 `parsed_value`。没有第四种关系，也不另解析 YAML。可信原文缺失、关系含糊、来源与关系不兼容，或无法落到这三种比较上的路径，都不纳入。
4. **按动作类型查表会误放行。** 查表按公开动作名或重定向参数绑定接收位置，并套用同一保真关系。若出问题的就是该公开动作的常规接收槽——复制对应剪贴板，下载或归档对应目标文件，命令已经写明的输出路径对应那个文件——现有查表会拦住，构不成“查表误放行”。
5. **固定重放也会漏掉。** 用同一等价关系比较同输入、同模式的旧版全通道，仍会放行这次违约。
6. **学习能够拦住。** 在健康示范上，带操作前对照的位置选择能够把真实接收位置上的不符判为不放行。

这六条合取，对应已冻结的保留条件：已知故障上的正确拦截只说明检查能跑；迁移到新工具后若仍被查表或固定语义回归追平，不据此开展复杂选问。需要的是一条未见工作流上的接受路径：查表和固定重放都漏掉，而学习拦住。

[clipboard_decision/REPORT_ZH.md](../clipboard_decision/REPORT_ZH.md) 已经说明，检验算法价值要在未见工作流上，与按动作类型查表、录制重放、观察所有可读接收位置作同预算比较。本次筛选只判断公开近例是否进入那一比较，没有开跑新的计分。

## 结论

两轮合计，没有一条近例同时满足上列合取。因此：

- 没有实现新的学习、查表或轨迹机制。
- 没有为这次筛选开拉取请求。
- 没有开展复杂选问；`question_selection` 保持 `not_opened`。
- 不能把这次筛选写成已经实现或验证核心算法。
- 轨迹对照（机制 B）仍然没有实现：只包一层已知接收接口，会和查表变成同一张绑定。

下面按轮次列出已经核对的近例。第一轮里的 ffuf、Typst、Mermaid、QGIS、matplotlib、`curl -O -J`、ffmpeg 在筛选当时归为同一组“其余近例”，仓库里没有逐项裁定书；本稿保持该分组，不把其中某一工具单独派进更细的不合格分支。

## 第一轮

本轮最接近的一条是 Kibana Fleet 的清单下载。它会被“download → 文件”的查表拦住。其余近例或是命令里已经写明输出路径，或是不能在已冻结的封闭关系下与原文比较。

### Kibana Fleet 清单下载

来源：[elastic/kibana#241730](https://github.com/elastic/kibana/issues/241730)。议题标题是 *Standalone elastic agent manifest file is truncated after downloading*。

议题正文写明：在 Kubernetes 集成里启用策略后，经 `Add agent -> Run standalone -> Download manifest` 得到的文件不完整，下载文件只有 `configmap` 一节，其余对象如 `daemonset`、`clusterrole`、`serviceaccount` 等缺失。预期行为是：下载得到的 YAML 应与使用 `Copy to clipboard` 生成的 YAML 同样完整。也就是说，复制完整，下载不完整。公开动作是 Download。

**不合格原因。** 出问题的是下载动作的常规接收槽（清单文件）。按现有规则，查表会把 Download 绑到文件，因而会拦住。它不能证明查表会误放行。

### 其余近例

本轮同时核对过 ffuf、Typst、Mermaid、QGIS、matplotlib、`curl -O -J`、ffmpeg。它们在筛选记录里归为同一组，总因是：命令里已写明输出路径，或不能在已冻结的封闭关系下与原文比较。

**不合格原因。** 命令已经写明输出路径时，查表按重定向或写文件参数绑定的就是那个常规槽；若不能在 `byte`、`full_string` 或 `parsed_value` 下与可信原文比较，则进不了合取第 3 条。本组没有逐项裁定书，这里不把其中任一工具单独写成更细的分支。

## 第二轮

在协议窗口未到、正式四项与密封标签保持不动的前提下，继续寻找查表会误放行、学习能拦住、固定重放也会漏的真实公开案例。本轮核对的近例仍然卡在同一处：出问题的就是公开动作的常规接收槽，按现有查表会拦住。

### Supabase 表格大字段的复制与导出

来源：[supabase/supabase#42818](https://github.com/supabase/supabase/pull/42818)。拉取请求标题是 *fix(studio): prevent truncation of large values in copy/export operations*。

说明写明：表格编辑器里，对较大的 JSONB 或文本列，复制到剪贴板和文件导出曾交付截断后的数据。网格为展示性能把值截到 10KB，这是有意的展示层行为；被截断的数据却泄进了复制和导出。受影响的操作包括：Copy selected rows、Export selected rows，以及右键 Copy cell、Copy row。Export ALL rows 在修复前就是完整的，说明未改。

**不合格原因。** 截断出现在复制和导出选中行的常规接收槽（剪贴板或导出文件）上。查表按这些公开动作绑定，会拦住。Export ALL rows 本身完整，不能作为查表误放行的见证。

### Kubernetes 文档复制按钮

来源：[kubernetes/website#23817](https://github.com/kubernetes/website/issues/23817)、[kubernetes/website#42179](https://github.com/kubernetes/website/issues/42179)。

议题 #23817 的正文是：*Copy application/deployment.yaml to clipboard* 复制到的是 yaml 文件名，而不是 yaml 本身。

#42179 的标题是 *Copy To Clipboard breaks YAML format*。报告写明，若干页面上的 Copy To Clipboard 会把除首行外的各行多出缩进，粘贴后不再是正确的 YAML；根因是负责渲染代码的 `codenew` 元素本身被缩进，例如它位于有序或无序列表中。报告给出的例子是 `kubectl apply` 解析失败：`yaml: line 2: mapping values are not allowed in this context`。

**不合格原因。** 两份报告里，写坏的都是剪贴板，也就是复制动作的常规接收槽。查表会拦住。

### Alacritty 剪贴板截断

来源：[alacritty/alacritty#6848](https://github.com/alacritty/alacritty/issues/6848)。议题标题是 *Truncated text on copy to clipboard*。

报告写明：复制选区后，文本会被截到约 65k 字符。报告者在传入 `clipboard.set_contents()` 之前打印 `text` 的长度，长度是对的；把约 2 MiB 的文本传入该调用之后，贴出仍然被截断。维护者说明：这是已知的 Wayland 剪贴板问题，限制来自 Linux 管道限制（通常要用对 `fd` 的异步写入来解决）。

**不合格原因。** 交付给用户的不完整结果就是剪贴板内容。写坏的是复制动作的常规接收槽，查表会拦住。

### Mattermost Mobile 附件下载截断

来源：[mattermost/mattermost-mobile#10311](https://github.com/mattermost/mattermost-mobile/issues/10311)。议题标题是 *File download silently truncates and the incomplete file is reused on later attempts*。

报告写明：在 Android 应用的文件预览里下载约 155 MB 的附件，会在大约 59 MB 处停下；重复尝试得到同样截断后的大小，没有报错。同一文件在设备浏览器中可以下完（155 MB 完整）。公开动作是下载。

**不合格原因。** 出问题的是下载动作的常规接收槽（保存下来的文件）。查表会拦住。

### GitLab CLI 归档写入

来源：[gitlab-org/cli!3560](https://gitlab.com/gitlab-org/cli/-/merge_requests/3560)。合并请求标题是 *fix(repo): report a failed close when writing an archive*。

说明写明：`glab repo archive` 可能留下截断的归档，却仍报告成功。它把下载写到 `.tmp` 文件，关闭时丢弃错误，然后改名。相关代码是：

```go
_ = out.Close()
if err = os.Rename(archiveName+".tmp", archiveName); err != nil {
	return fmt.Errorf("failed to rename tmp repos: %w", err)
}
f.IO().LogInfo("Complete...", archiveName)
```

说明还写明：在只在关闭时才报告缓冲写入失败的文件系统上，磁盘满或网络挂载在刷新时失败，不完整文件仍会被改成最终文件名，并告知用户下载完成。

筛选当时，与该合并请求相联系的议题页返回 404。本稿不以当时未核实的修复版当作健康对照，也不把后来另见的议题页补写成当时已经核对过的材料。

**不合格原因。** 不完整的是归档文件本身，也就是该下载或归档动作的常规接收槽；查表若绑定目标文件，会拦住。缺少当时可核实的议题页与健康对照，也不能在冻结关系下完成两侧比较所需的配对。

### 同日已核对、不以议题链接逐条引用的近例

同日还核对过 Vault UI 与 Swagger UI 的复制失败，以及 Grafana Notebooks 的 Copy as Markdown 与 Open in Cursor URL 截断。当时没有把可核对的议题或修复 URL 写入筛选记录，本稿也不编造未核实的议题地址。

已核对的定性结论是：Vault UI 与 Swagger UI 写坏的是复制槽本身，按现有查表会拦住。Grafana Notebooks 的 Copy as Markdown 与 Open in Cursor URL 截断一并核对过；其中 Open in Cursor URL 截断不是同一份可信原文上的 `byte`、`full_string` 或 `parsed_value` 比较，进不了合取第 3 条。Copy as Markdown 没有已核对应议题原文，这里不另作更细分支，也不编造地址。

## 对已有研究线的含义

这次筛选没有改写 [receiver_learning/REPORT_ZH.md](../receiver_learning/REPORT_ZH.md) 里已经写下的计分。那份报告里，学习与查表在复制的 3 行以及 jq 两种模式的全部 48 行上判定相同；重放漏掉的 3 条 jq 样本，查表也拦住了。没有一条未见工作流上的接受路径是查表和固定重放都漏掉、而学习拦住了的。本轮公开近例没有补上这条路径。

因此仍然不能声称已经实现或验证核心算法，也不能开展复杂选问。已停止或分母不足的开发线，不靠放宽纳入标准或发明材料往前推。正式四项主比较的窗口、密封标签和冻结清单的处理，见同目录的 [STATUS_ZH.md](STATUS_ZH.md)。
