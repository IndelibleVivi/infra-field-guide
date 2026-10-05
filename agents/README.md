# 给 agent 的入口

[返回首页](../README.md)

这组工单把通用参考转成一次具体任务：填写目标、现有授权、执行位置与验收，可以在不同 harness 中复用。实际执行依赖读者已有的工具和访问路径；仓库中的教程、日志和示例提供依据，具体授权仍来自 owner。

## 选一张工单

| 目标 | 工单 | 人读的依据 |
| --- | --- | --- |
| 新 VPS 的只读盘点与首日操作建议 | [新机检查](first-server.md) | [新机教程](../docs/02-first-server.md) |
| 本机或旧 VPS 搬家 | [迁移](migration.md) | [本机迁移](../docs/04-local-to-vps.md)、[跨 VPS 迁移](../docs/05-vps-to-vps.md) |
| CC 环境盘点、清理与恢复 | [账号整理](account-cleanup.md) | [账号章节](../docs/06-account-recovery.md) |
| VPS worker 访问自己的 Mac 项目 | [私有远程访问](private-access.md) | [内网穿透教程](../docs/09-private-access.md) |
| 时间约定、hook 时间与 NTP / UDP 123 排查 | [时间同步](time-sync.md) | [机器时间专题](../docs/time-synchronization.md) |
| 多人/agent 的访问变更、误封与恢复 | [共享访问变更](access-change.md) | [访问权限与恢复专题](../docs/access-control-recovery.md) |
| 多个 harness 跨机器协作、长任务交接 | [跨机器运维](multi-machine-ops.md) | [执行位置与原任务恢复](../docs/multi-machine-operations.md) |
| 配置来源与实际运行版本核对 | [配置与运行](config-runtime.md) | [配置生效专题](../docs/configuration-and-runtime.md) |
| 定时、补跑、任务重叠与产物验收 | [定时任务](scheduled-job.md) | [调度与恢复专题](../docs/scheduled-jobs.md) |
| 磁盘占用、保留策略与可恢复清理 | [数据生命周期](data-lifecycle.md) | [数据、日志、缓存与备份](../docs/data-lifecycle.md) |

将工单复制到自己的 agent 会话，只填写需要的目标信息。私有主机名、真实 IP、账号和路径留在自己的本地 operation record；不要作为 PR 提交回来。密码、私钥和 token 不通过工单传递。

[迁移 JSON](../examples/migration-plan.example.json)与[服务 inventory CSV](../examples/service-inventory.example.csv)是合成模板，不是可直接执行的 plan，也不证明授权存在。用它们记录现状、owner 和证据；字段内容来自用户授权与新鲜观察，不能由 agent 猜测。

## 所有工单共用的执行规则

1. 先说清准备读取什么、哪个 host/账号/目录属于本次任务。区分发起端与工具实际执行端；未知身份、SSH host key 改变、跨账号目标、意外数据碰撞，停止依赖它的操作。
2. 优先完成已授权的只读调查和本地候选；不能把读权限扩展成 root、写入、停机、购买、DNS 修改或删除权限。
3. 对每个实际变更列出目标、命令、影响、恢复、停止条件和验收。操作审批绑定具体动作与目标；已明确授权的范围不用反复确认，范围改变才重新请求。
4. 长任务有独立 owner、日志、state、status 和 resume；继续原任务，不因为工具超时就重发另一份写任务。
5. 不打印 secrets，不上传原始配置或日志。发现敏感值只记录它的类别和所在受控文件，不复述值。
6. 观察结果分开：source、安装、进程、origin、edge、用户路径。缺少日志权限或 probe 不可达应写 unknown，不写 healthy。
7. 收尾说明已做、未做、证据、恢复路径和下一步。更新 operator 文档后再更新私有 operation record，避免机器已经换了、命令仍指向旧主机。

## 回报模板

```text
目标与范围：
本次授权：
执行结果：完成 / 部分 / 阻塞
已观察事实（时间、目标、检查、结果）：
已变更对象与恢复位置：
数据写入 owner：
未验证层级：
下一步及是否需要新增授权：
```

请保留不确定性。不要为了填满格式编造真实 IP、服务名、备份位置或通过状态。
