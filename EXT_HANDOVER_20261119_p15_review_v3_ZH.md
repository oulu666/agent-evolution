# P15 v3 交接（2026-11-19，北京时间）

**停止状态：工程报告序列化失败，不启动正式矩阵；GPU已退出，无自动重试。** 不是科学淘汰。

## 关键成果

1. 新增 `p15_review_v3_20261119/`（11模块）与 `P15_REVIEW_REVISION_V3_20261119_ZH.md`，不改旧冻结。
2. 固定Replay损失0.5new/0.5replay，两分支独立监督归一；no-old/SeqFT权重1。108轨迹/41472更新保持；跨stage暴露混杂明示。
3. Dev只用固定88，test348四节点延迟统一。总逻辑请求603072；update0精确缓存条件满足时584064；无stage1跨方法共享。Full Replay延期。
4. 11项CPU验收PASS，旧598保护文件GPU后再核对不变。
5. 唯一GPU工程尝试3物理/2逻辑更新、9forward/9backward、6660输入tokens，真实4bit/AMP、梯度有限；磁盘恢复重建对象的第二步与不中断路径完整状态SHA完全相同。6次train/dev生成，无test。

## 必读证据与hash

- `runs_ext_p15_review_v3_20261119/runtime_manifest_v3.json`
  SHA256 `386a5cf24a24957b99553120e3dd599b68ef09bbb0ae7ac32e97b049c645155f`
- `.../review_budget_v3.json`、`engineering_plan.json`、`cpu_acceptance.json`
- `.../engineering_attempt01/FORENSIC_RESULT.json`：GPU退出后的CPU取证，不是伪造的RESULT/PASS。
- `.../engineering_attempt01/updates.jsonl`、`physical_steps.jsonl`、`generation_records.jsonl`、`state/commits.jsonl`、`terminal_failure.txt`
- A/B完整状态SHA均 `dd45746708d9d75b9204892f6412983d05925f725f6acce257bc809fda2db940`；两份61MB状态与base保留本地。
- `.../postprocess_measurements_cpu.py`：可重复纯CPU复核，绝不加载模型到GPU或追加训练。
- 详细报告 `EXT_REPORT_20261119_p15_review_v3_ZH.md`：逐stage真实tokens、测量、范围公式及全部限制。

## 实测与资源结论

训练三次3.820/1.396/1.507秒，小batch第二步1384–1494 input token/s；训练峰值2785MiB allocated /4666MiB reserved。工具生成0.794–0.977秒；真实final0.609–1.646秒；gold-final0.690–6.676秒，三模式各2条，生成峰值1116MiB allocated /3410MiB reserved。

原子持久化粗估每update约11.60–15.18秒（±2秒）。按有限样本和显式情景倍率推算完整矩阵，短输出占卡约251–1244小时；接近生成cap的极保守压力情景约7677小时，不是保证上限。I/O和长输出有严重成本，不应直接放行603k请求。资源把关不基于模型成绩；不改108科学矩阵。

## 失败与未验证范围

GPU唯一尝试20:39:51–20:43:12（北京时间）进程最终因 `TypeError: Object of type dtype is not JSON serializable` 非零退出；`RESULT.json`未生成。四次提交和两磁盘状态证实next-update恢复完全等价，但生成后最后隔离恢复断言没有独立持久化见证；finally错误还可能掩盖先前被捕获错误，不能把全部工程验收标PASS。未跑新OS进程恢复、正式完整pack、任何test、108轨迹或Full Replay。

## 建议父代理下一步

- 在新操作修订中修复报告递归JSON-safe转换（dtype/device/Path/NumPy等），补CPU序列化回归，并让每项验收立即持久化小见证，保留本次失败及冻结不变。
- 审阅是否优化完整base重复hash/磁盘I/O、解码吞吐；优化应保持模型/生成语义与精确恢复可验证，不因效果缩顺序/种子或调题。
- 按实际资源决定后续，不自动追加工程attempt。本阶段GPU预算已用满3物理更新和6生成。
- 正式入口为 `.venv/bin/python -B p15_review_v3_20261119/runner_v3.py batch --execute`，但当前缺START许可且RESULT缺失，门控拒绝；**不能通过手填PASS绕过**。需父代理续发具体资源/操作修订指令。
- 用户已授权完成后自动GitHub，但依当前内部要求本阶段未提交/推送；最终由父代理精确上传轻量源码/协议/账本/JSONL/取证与hash。不上传base_blobs、state/*.pt、锁、cpu_fixtures或重复传输zip；均保留本地，不删。

当前路径全在原笔记本fac_tinyagent checkout；未CloudAgent、未clone、未动.venv/conda、未GPT、未清STOP。旧 `_p11_fix_tmp/` 等保持原状。硬盘run上限32GiB/保留8GiB，现run约0.98GB，GPU退出时Windows C剩余约55.32GB。
