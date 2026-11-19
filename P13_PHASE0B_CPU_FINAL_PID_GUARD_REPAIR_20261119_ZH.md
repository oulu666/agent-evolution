# Phase0-B CPU final进程身份守卫修复（仅操作性补丁）

北京时间2026-11-19。本轮GPU已于02:17:37完成3种子，监督器02:17:41 rc0。本补丁不增加GPU attempt，不加载GPU模型、不训练、不生成、不改任何结果/科学门槛；原routine保持暂停。

## 原故障
02:39:45原CPU final仅以`/proc/365`或`/proc/470`是否存在判断原GPU任务存活。WSL重新启动会复用短PID；父助手当时已核实470为udev-worker，不能当作原实验worker。执行本次只读预检02:42:59，这两个PID均已不存在；不能靠等待PID空出放行，仍修复原判据。

保留runs_ext_p13_phase0b_persist_20261119/FAILED_20261119_023945.json，其SHA256为85903fefd6d680a94396f30b2d1d6c4bf326a4e5f1c05f5626b1c9281e2a33fc。

## 修复范围与审计
冻结GPU/科学模块p13_phase0b_persist_20261119.py完全未改，SHA256仍7eef35c357e9b29c4726dbcb505fa65907788d6072db91773097c64ea4ef1435。新增CPU入口p13_phase0b_cpu_final_guard_v3_20261119.py；其原独立检查函数逐行复制，仅将一行“数值PID存在即阻断”替换为真实身份检查。原科学分析/统计函数直接原样调用，不复制或改变指标计算；原数据manifest、旧协议、算法代码和科学gate hash再验证，未更新原scientific receipt冒充原版。

补丁receipt与guard_only.diff见runs_ext_p13_phase0b_persist_20261119/cpu_final_guard_repair_20261119_v3/。入口在内存中明确接入此窄检查函数，原冻结文件字节不变。新入口SHA256：26202f9eb290e399c0eeb17e09ee2751c007f799ca9c9c45019d251acbb4747d。

新守卫记录boot_id、PID/cmdline/exe/cwd/启动ticks；检查原数值PID的当前身份，并扫描所有当前项目Python（不局限原PID）、GPU compute和Windows Apex/STOP。只排除当前CPU final自身。真实项目仍在或身份不明Python则阻断；明确的root-owned系统Python脚本可通过脚本绝对路径和root所有权识别为系统服务，不杀任何进程。还必须监督器rc0、GPU_COMPLETE三种子及所有0/5/10节点各48条完整才放行。

六项纯CPU测试：PID不存在→不阻断；无关PID复用→不阻断；真实实验worker在→阻断；真实实验换PID→阻断；已验证系统Python/cwd不可读→不误判项目；未知Python/cwd不可读→仍阻断。没有移除守卫或强制pass。

## CPU补丁开发失败也保留
- v1受/proc/1/exe权限限制失败；尚未导入torch进行状态/科学重算。
- v2采取未知Python fail-closed时将两个root系统服务networkd-dispatcher、unattended-upgrade-shutdown误当待查项目，正常阻断；无GPU活动。v3只增加明确的系统脚本身份验证，未知对象仍阻断。
- v1/v2代码与各自cpu_final_guard_repair_20261119[_v2]/的失败、测试、receipt均原样保留。这些是CPU工程检查，不是GPU attempt，更不是新种子或独立实验。

最终必须由v3完成原独立逐题统计、状态/文件hash、成本、gate和CI检查，并验证torch.cuda.is_initialized()==False，才写CPU_FINAL_COMPLETE。若遇实质性结果/科学校验失败则停止，不调阈值、不重生成。该补丁不授权任何后续GPU重跑。
