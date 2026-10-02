# 工单 · VPS worker 经私有网络访问 Mac

依据：[私有远程访问教程](../docs/09-private-access.md)与[路径图](../docs/architecture.md)。

```text
目标：让<已选VPS的实际worker用户>通过tailnet上的普通OpenSSH访问<指定Mac本机用户>，
在<指定项目>中执行<owner批准的实际命令>。
读取：本仓库AGENTS、agents入口、第09章及两个SSH/grant示例。
授权：<只读盘点 / Mac Remote Login与专用key / 指定tailnet policy修改 / 项目写读测试>
所有真实身份、policy、key路径和证据留在owner私有记录，不回填公开示例。

分清网络grant、SSH认证、OS文件权限/TCC三层。
从当前账号读取policy，保留原规则和tests；窄grant不能覆盖旧allow-all。
不要用整个示例文件替换真实policy，不申请无关端口或把整个tailnet视作同一信任范围。
独立核对Mac host key，使用专用key和明确known_hosts，不关闭host key检查。
SSH以owner登录不等于repo隔离，不擅自赋予全盘访问或无密码sudo。

先只读确认双方身份、服务、睡眠/重启边界、非交互PATH、目标cwd、挂载盘与权限。
按已批准方案操作；保持本地恢复入口。每项变更记录精确目标和回退。
用真实worker用户验证：身份、项目路径/Git、runtime、授权的临时写读与清理、真实项目命令。
再验证未授权peer的TCP22仍拒绝，原有HTTPS路径与原policy功能仍成立。
无法取得测试peer时写未验证，不能声称最小权限验收通过。

收尾逐层报告网络、SSH身份、文件访问、项目执行、原业务及反向验收。
本次未重启就不声称FileVault重启后远程可达；未部署就不声称runtime已启用。
```
