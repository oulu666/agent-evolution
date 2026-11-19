# P15 最小CPU报告操作修订（2026-11-19，北京时间）

这是新增的报告适配，不覆盖/导入到任何P14/P15旧冻结运行器；不包含GPU重跑、不创建START、不创建原RESULT，不改变科学矩阵、损失、T/A/E/F或验收判据。最终仍 **NOT_FULLY_ACCEPTED/BLOCKED**。

## 缺陷与修复

原 `engineering.py` 将后端指纹直接交给JSON；旧 `backend_fingerprint` 的 `actual_compute_dtype` 已是字符串，但 `actual_config.dtype/torch_dtype` 可是torch.dtype。末尾finally的JSON异常使RESULT写出失败，也可能遮蔽先前被捕获的异常。

新增 `p15_cpu_closeout_20261119/json_safe.py`：dtype/device/layout/memory_format/Path/NumPy dtype映射为其准确公开字符串；NumPy标量映射原生标量；嵌套list/tuple/字符串键mapping递归处理。未知对象、tensor/array payload、非有限浮点及非字符串键一律拒绝，避免 `default=str` 任意对象地址化、超大payload误入报告或键碰撞。输出排序、UTF-8、严格JSON。

CPU入口：`.venv/bin/python -B p15_cpu_closeout_20261119/cpu_reporting_tests.py`。11项测试通过，包含原异常复现、真实旧指纹结构（仅GPU名称/能力函数CPU mock，非GPU实测）的修复、fail-closed边界；前后断言CUDA未初始化。不加载模型。输出 `runs_ext_p15_cpu_closeout_20261119/reporting_CPU_tests.json` 和 `FINAL_BLOCKED_STATUS.json`。CPU mock文件明确标为非GPU测量。

未来若另行修订GPU运行器，应使用该显式转换器，并在每个工程断言后即时原子提交小见证，错误报告独立保留primary/finalization错误；不能仅在finally一次写报告。本轮没有把此建议接入冻结运行器，也没有以CPU修复补写旧RESULT/PASS。旧生成后隔离恢复见证仍缺失。

## 派生缓存重建及发布字节保真

所有模型/adapter/optimizer/scaler/RNG大二进制、cache目录、token特征派生gzip、tokenizer重复、传输zip、CPU临时夹具和锁均不上传，不删除本地副本。原manifest对遗漏派生件的hash保留，不改manifest假装文件齐全。

token特征可用 `.venv/bin/python -B p15_cpu_closeout_20261119/rebuild_token_features_cpu.py --write` 在缺失时重建；默认仅check不写。该脚本只加载本地身份hash匹配的tokenizer、encode1392条已发布数据，不加载模型，gzip mtime=0。此次默认check核对原缓存250448字节完全相同，SHA256 `0982d02d2ee51de2eaa89068efa9a9ea00fe997f05a0436b1b99f400821ae6b0`。新机器须先自行提供身份匹配的本地基座/tokenizer；本次不上传或下载权重。

Windows Git配置core.autocrlf=true。为防发布日志/冻结数据被自动换行改变，新加根.gitattributes只对本轮新增路径 `-text`，原有受保护科学文件没有规则/字节变化；暂存后逐文件比较Git blob SHA256与工作文件，确保冻结hash可审计。
