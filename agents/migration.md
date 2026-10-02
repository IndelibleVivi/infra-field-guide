# 工单 · 可恢复的迁移

依据：[本机 → VPS](../docs/04-local-to-vps.md)、[VPS → VPS](../docs/05-vps-to-vps.md)。

```text
你是本次迁移 agent。读本仓库 AGENTS.md、agents/README.md 和对应迁移教程。
本次先交付本地可审查的迁移计划；除非另有精确授权，不改变服务器、账号或入口。

源：<精确机器/服务/数据范围>
目标：<精确候选机器；保持与现有 live alias 不同>
业务需求：<容许停机、可容许数据损失、访问者与验证场景>
owner 与当前授权：<具体操作，而非“参考教程全部执行”>

盘点服务、数据库、目录/volumes、secrets 的传输方式、system/user units、cron、timers、
DNS、Tunnel、Tailnet、证书续期、backup 和全部调用方。不要只按当前正在运行的进程判断范围。
用 examples/ 中的 inventory 和 plan 记录真实发现；样例值不可用于真实执行。

准备顺序：目标独立身份与可恢复登录 → 源只读预拷贝 → 隔离候选 → 写入冻结与最终一致快照
→ 候选验证 → 精确入口切换 → 唯一 writer 接管 → origin/edge/client 验收 → 观察。
复制原始数据库文件前必须有该数据库支持的一致性方案；不能以rsync成功证明一致。
不得复制machine-id、SSH host私钥或Tailnet节点状态来冒充旧机器。
同 tunnel 多个connector可能同时收到请求，不能当作等待激活的被动备机。

迁移任务必须有 durable owner/log/state/status/resume，记录已完成单位而非只记PID。
对意外碰撞、空间不足、未知writer、非零退出、失去回退依据，停止相关变更并保留证据。
目标首次接受写入前后的恢复方案分别写：开始写入后不能直接重启旧writer或只回切DNS。
旧机及独立计费资源的删除、取消、凭据撤销另列确切清单，不从切换授权推导删除授权。

最后报告每层验收与时间，明确新的state/writer owner、仍需保留的旧物、恢复路径和未验证项。
```
