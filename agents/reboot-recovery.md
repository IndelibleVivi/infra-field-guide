# 工单 · VPS 重启后的服务恢复

依据：[冷启动恢复的只读路径](../docs/03-operations.md#冷启动恢复从-boot-到-readiness-的只读路径)、[意外重启调查](../docs/08-troubleshooting.md#vps-突然重启先分开-boot-边界与启动后故障)与[共用执行规则](README.md#所有工单共用的执行规则)。

```text
目标：<准确 VPS；可使用已核实的 SSH alias>
现象或演练目的：<已知 boot 后服务未恢复 / 重启原因未知 / 计划冷启动演练>
用途与可接受影响：<服务、依赖、入口、可接受停机时间与数据边界>
现有授权：<默认只读；是否另授权 enable/start/restart/reboot 等精确动作>

先固定本次调查的 boot ID、UTC 时间、上一/当前 boot 与最初用户症状。
已发生的异常重启先读 docs/08：区分离开上一 boot 的原因、boot 后恢复故障和目前未知项；
不把新 kernel、更新任务、provider Boot 任务或某个端口冲突单独写成根因。

以下默认只读，不启用 unit、不启动 container、不 reset-failed、不重建索引、不清数据：
1. system manager：power state、is-system-running、failed units、目标 service 的
   enabled/active、Result、NRestarts、启动时刻、依赖与当前 boot 的 journal。
2. user manager：用实际用户查 Linger 与 systemctl --user；记录 system 与 user
   manager 各自结果；无法进入该用户的 user bus 时读 linger 标记与 unit 文件，
   user-manager 运行状态写 unknown。开启 linger 属于登录策略变更，不在只读阶段执行。
3. Docker：确认 context 指向预期 daemon；分别查 docker.service 的 boot owner、
   container 当前状态/退出码/restart policy 与日志。policy 名称不等于本次已启动。
   若容器由 systemd 管理，或服务由解锁挂载后的外部 controller 启动，沿实际 owner
   核对其持久注册、执行结果与依赖条件，不要把 restart=no/disabled 一律当作缺陷。
4. boot 依赖：查 network-online、挂载、unit Requires/Wants/After 的实际状态与日志；
   Requires/Wants 与 After/Before 是不同关系，都不证明远端服务、挂载或应用 ready；
   network-online 也不证明 DNS、入口或应用 ready。
5. 端口：按 TCP/UDP、IPv4/IPv6、具体 public/mesh/Tailnet 地址或 wildcard 记录 listener；
   不从“443 occupied”推导两条协议或两类入口同时故障。
6. readiness：跑应用文档允许的无副作用 verify/health/readiness 请求，再分别验证
   SSH 新连接、进程、origin/listener、入口、鉴权与真实客户端；HTTP 200 要匹配正文或业务特征。
7. 恢复任务：查 timer 的 LAST/NEXT、补跑和产物；备份另查完成时间、独立故障域与 restore 证据。
   定时器或备份进程 active/成功不等于产物正确。

遇到 transient dependency 失败时，读应用 retry、Restart/Result/NRestarts/start-limit 和 journal，
保留错误并等待设计允许的恢复；不要用反复手动 restart 覆盖证据。人工 stop 后不要假设
restart policy 会重新拉起。canonical data 与可重建索引分开：索引异常先按应用只读 verify/dry-run，
未经授权不清空数据、不放宽校验、不删除持久卷。
一次补齐索引后，继续检查正常新增/修订是否进入维护路径；区分当前进程健康与下次启动就绪。

只读 preflight 完成后，核对现有授权是否已覆盖 reboot；缺少时给出具体演练候选：精确目标、时间窗、
预期中断、console 与独立 SSH 恢复路径、writer 停止、备份、版本/配置回退、失败停止条件、
演练后验收与谁可决定继续。不要执行未授权的 reboot；已明确覆盖的授权无需重复索取。

交付：
1. boot ID、时区/UTC、manager 与本机症状；confirmed/probable/unknown 分开。
2. 每层实际证据：system/user service、Docker daemon/container、网络与挂载、端口、
   readiness、入口和真实客户端。缺失权限写 unknown。
3. 当前 failed unit、restart/start-limit 与 timer/备份状态；未验证层级。
4. 已执行动作及恢复位置；若没有变更就明确写“没有执行状态变更”。
5. 重启演练候选与所需新增授权；preflight PASS 不得写成 reboot rehearsal PASS。

真实主机名、地址、账号、路径、容器名与日志留在 owner 私有记录；公开回报只使用合成占位。
```
