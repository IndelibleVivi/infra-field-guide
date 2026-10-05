# 工单 · 配置来源与运行版本

依据：[配置如何生效](../docs/configuration-and-runtime.md)、[跨机器运维](../docs/multi-machine-operations.md)与[共用执行规则](README.md#所有工单共用的执行规则)。

```text
目标：<准确机器/服务；VPS 可使用已核实的 SSH alias>
现象：<改了配置没生效 / 服务找不到命令 / 版本不一致 / reload 或 restart 后行为不变 / 其他>
用途与可接受影响：<按业务填写；不确定就先只观察>
现有授权：<默认只读；如已授权具体变更，记录精确动作、目标文件和边界>

先确认目标 unit、运行用户、工作目录，以及自己实际在哪一层执行。
区分 system manager（默认目标，未设 User= 默认 root）与 user manager（该用户身份，
不能切换其他身份）；查 user unit 必须用对应真实用户的 systemctl --user，
system 结果不能替 user unit 验收，WorkingDirectory 默认也按管理器区分。
确认服务从哪些文件读配置（FragmentPath / DropInPaths / 实际加载目录），
而不是假定“我编辑的那一份就是被读的那一份”。
配置优先级没有通用答案：按该工具当前版本的官方说明确认读取顺序与覆盖规则。

分开核对各层：source、build、install、运行进程、以及“用户实际连到哪份服务/入口”。
第五层以一个可观察的新行为或 endpoint 入手，客户端自身版本另记；
以运行进程实际加载的可执行文件/库为准反推哪份在跑，不假设“改了源码就变了”。
进程启动时刻用管理器的 ExecMainStartTimestamp 等，不用 /proc/<pid>/exe 的 mtime。

区分 shell 环境与 service 环境：PATH、cwd、User、环境变量的来源不同；
要证明服务能用某命令，须在服务真实身份与环境下检查，不能用交互 shell 结果代替。

区分 systemctl cat（磁盘上的主文件+drop-in，并非合并后的有效配置）、
systemctl show（管理器当前理解的已加载属性；改了未 daemon-reload 可能是旧值）、
运行进程实际状态三层。
区分 daemon-reload（重读 unit 文件）、reload（该 unit 是否支持、是否无中断取决服务本身）、
restart（停后再起，重新读取进程属性）。改 User/Environment/ExecStart 等进程属性一般要 restart；
不要默认所有应用都能无中断 reload。

检查时只暴露配置“来源”，尽量不打印值；环境变量、argv、EnvironmentFile 均可能含秘密。
需要看具体值时先确认范围并脱敏，输出只留本机；不要先把 NUL 换成换行再整段输出环境；
命令历史也可能留存。

交付：
1. 配置来源三层对齐（磁盘文件/管理器已加载/运行进程），进程如何启动（用户、cwd、exe、关键环境键名）。
2. 各层版本的现状与不一致点（source/build/install/process/用户连到的 endpoint）。
3. 若要改配置：准确 diff、按应用支持与影响选动作（reload/restart/daemon-reload 组合）、回退与行为验收；
   备份用唯一不覆盖的新目标。
4. 在已有授权内完成；未授权的重启/reload/写入先给具体候选。
5. 报告哪些层级已用真实客户端验收，哪些仍未验证。

回报：实际在哪执行；有效配置来源；变更与运行版本；哪条真实行为已通过；
      还未验证什么；后续如何查询或接手。
真实机器、账号、路径与运行记录留在 owner 私有位置，不提交公开仓库。
```
