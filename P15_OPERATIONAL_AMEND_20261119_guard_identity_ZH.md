# P15 操作补充 v2：真实 Python 进程身份，而非命令行子串

2026-11-19，北京时间。原运行冻结 `7fdcf44f6e80cc4150c7203765a7416ba37bbb447d2d813ac4b589e9fb27bb6e` 和全部被其引用文件保持不变。**没有任何GPU启动、训练或模型效果观察**，只是CPU/只读前置守卫实际执行发现误报：Bash -lc 的命令行包含python，被v1误认为另一研究Python进程。

新增而不覆盖：`guards_v2.py` / `runner_v2.py` / `cpu_tests_v2.py` / `freeze_v2.py`。原科学方法、数据v2、108主轨迹+18可选Full、所有tokens/更新/评测/统计/存储规则一律不变。新运行冻结 `runtime_manifest_v2.json` 引用并核验整个原科学冻结，同时增加这些操作文件和新CPU证据。

进程身份按/proc真实exe basename或argv[0]为python/python3.x/pypy判断，而非任意命令行中出现python；launcher Bash/PowerShell不冒充Python。真实批量父进程必须确认为Python，cwd为项目根、脚本实际路径等于本轮runner_v2.py且子命令batch，才准许作为同一GPU队列的控制器；不通过历史数字PID任意放行其它进程。CPU增加5个实际解释器/启动器用例和2个父控制器用例。其它GPU、STOP、Apex、<60W、放电和守卫失败等阻断规则完全保留；不清除任何STOP。

**后续唯一推荐入口（替代原预注册中的同名操作命令）**：

```bash
.venv/bin/python -B p15_stageaware_20261119/cpu_tests_v2.py
.venv/bin/python -B p15_stageaware_20261119/freeze_v2.py
.venv/bin/python -B p15_stageaware_20261119/runner_v2.py guard
# 父代理复核后才创建START_APPROVED.json，runtime_manifest_sha256必须为v2 hash：
.venv/bin/python -B p15_stageaware_20261119/runner_v2.py batch --execute
.venv/bin/python -B p15_stageaware_20261119/runner_v2.py test --execute
.venv/bin/python -B p15_stageaware_20261119/analyze.py
```

批准文件allowed_commands可为["train","batch","test"]，allow_full_replay默认false；若预先批准Full，batch/test都加--include-full。该文件本阶段不创建。v2 worker和父队列都使用v2 runtime hash；旧runner面对v2批准hash会拒绝启动，不会意外退回旧guard。

此为工程真实检查修正，不是Phase0-C、小样本科学淘汰、增加训练预算或借方法结果改题。原冻结文件与598个旧受保护文件仍逐hash核对。
