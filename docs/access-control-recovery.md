# 人和 agent 共享 VPS：访问权限与防锁死

[返回首页](../README.md) · [首日 SSH 操作](02-first-server.md) · [私有远程访问](09-private-access.md) · [给 agent 的访问变更工单](../agents/access-change.md)

## 这一页帮你做什么

几个人、几台设备或几个 agent 一起维护服务器时，怎样让合法操作者持续能进入、各自获得所需权限，并在改坏规则后恢复。本页补充协作和排障判断；创建用户、安装 key、修改 SSH 与 UFW 的完整步骤继续使用第 02 章。

<details>
<summary>适用环境与验证范围</summary>
<p>以 Linux/OpenSSH 和普通个人 VPS 为主；服务名、防火墙后端、fail2ban jail 与恢复控制台按实际平台核实。Ubuntu 24.04 还需区分 ssh.service 与 ssh.socket 的监听职责。</p>
<p>本文使用合成身份和文档 IP。命令只在已授权的目标上使用；本仓库仅核对文档、静态语法与站点，不改变任何真实主机的权限、会话或网络。</p>
</details>

## 已经有人进不去了

先保留仍可用的会话，停止其他操作者继续叠加 SSH、防火墙或封禁规则。记录谁从哪条路径、用哪个账号和 key 失败，找到最近一次变更的 owner。**旧 shell 还能运行不代表它能重新登录，也不能证明“只有这个 agent 获得了特殊权限”。** OpenSSH 在接收连接后分出会话进程，已认证连接和新连接要分别观察。[OpenSSH sshd](https://man.openbsd.org/sshd.8)

| 观察到的症状 | 先分辨哪一层 | 有区分力的下一步 |
| --- | --- | --- |
| 新连接 timeout，旧会话还活着 | 路由、云/主机规则、监听、封禁、连接限制 | 由旧会话或 console 看监听和规则，结合服务端日志；别先换 key |
| `Connection refused` | 端口未监听或主动拒绝 | 核对地址/端口与实际 unit，不能据此宣布身份已验证 |
| `Permission denied (publickey)` | 已到 SSH 认证；用户、key、权限、来源限制可能不匹配 | 核对真实客户端配置和服务端那次拒绝日志 |
| `Too many authentication failures` | 单次连接提供了过多身份或认证尝试 | 看选中了哪些 key；它与 fail2ban 的 IP 封禁是不同机制 |
| 某个网络下所有人都失败 | 共同出口 IP、IPv6、VPN/跳板或网络策略 | 查服务端实际看到的来源，别把设备名称当 IP 身份 |
| 能登录，但不能读项目或 sudo | 系统用户、groups、文件 ACL、提权策略 | 用真实 worker 身份检查 `id` 和对应权限 |
| host key 改变 | 目标机器身份尚未确认 | 从独立可信渠道核对；不要自动删 `known_hosts` |

缺少服务端日志或控制台时，明确标记尚未定位。不要在失败循环里无限尝试不同密码和 key，这会污染证据，也可能触发实际存在的限制。

**运行位置：VPS 的保留管理会话或 console；只读。** 先确认正在运行的服务和监听，再读取本次启动的少量记录：

```sh
systemctl status ssh.service ssh.socket sshd.service --no-pager
sudo ss -lntp
sudo journalctl -b -u ssh.service -u sshd.service -n 80 --no-pager
```

这里列出常见 unit，未安装的名称可报不存在。日志权限不足、发行版写入其他日志源或记录已经轮转时，结果保持未知。时间也可能错误时，先用本次 boot 和条数限定，避免相对时间筛选漏掉关键事件。只分享脱敏的那次失败信息。

## 先把谁能做什么写清楚

“本机的 agent 能做什么，VPS 上的 agent 就应该能做什么”可以是 owner 的协作偏好，但能力需要从实际路径和运行身份确认。机器位置、模型名字、SSH alias、提示词和 `cd` 都不会自动建立系统权限边界。

| 层 | 它决定什么 | 常见误读 |
| --- | --- | --- |
| 网络路径 | 哪个来源能到哪个地址和端口 | 加入私有网络不等于获得 shell |
| SSH 认证 | 哪个 key/证书能进入哪个系统账号 | 独立 key 不等于独立系统用户 |
| UID、groups、文件 ACL | 登录后能读写哪些文件、访问哪些 socket | 只把 cwd 设为项目目录不构成目录隔离 |
| sudo、capabilities、宿主控制接口 | 能否越过普通用户边界修改系统 | 不在 sudo 组也未必无提权路径，例如能控制宿主 Docker daemon |
| agent harness | 工具暴露、批准流程及可能存在的实际沙箱 | 提示词中的“只读”不自动变成 OS 强制限制 |
| console/rescue 控制面 | SSH/网络改坏后谁能恢复 | “网页能打开”还不等于具有救援凭据 |

这些是不同检查面；按实际需求选用即可。同一 UID、同一可读凭据和同样的提权能力，通常意味着很接近的主机权限。若其中一个 agent 已能任意 root 执行，靠它可修改的配置文件无法形成对它自己的可靠限制。[Linux credentials(7)](https://man7.org/linux/man-pages/man7/credentials.7.html)、[Docker daemon attack surface](https://docs.docker.com/engine/security/#docker-daemon-attack-surface)

### 个人协作的三种常见选择

| 实际用途 | 合适的安排 | 接受的边界 |
| --- | --- | --- |
| owner 自己的多台设备和充分信任的维护 agent | 每个设备/用途独立 key，可共用已有管理用户 | 易撤销某个入口；登录后的同账号权限共享 |
| 需要区分人员、项目文件或部署职责 | 独立系统用户、明确目录/服务权限、按需 sudo | 多维护少量账号；仍需排查共享 groups/socket 等旁路 |
| 自动化只需一个固定动作 | 已受控的任务接口或真正受限的命令账号 | 输入、可执行文件、配置和写入路径都需受控；仅固定命令字符串不够 |

不要为了“更安全”同时加入复杂 KRL、动态 IP 白名单和多个封禁服务。先让既定协作可用、可撤销、可恢复。已有充分理由使用这些控制时，再逐项证明其效果。

**独立 key 的直接收益是可辨认和可撤销。** 私钥留在各自设备或获准的运行环境；记录公开指纹、用途、目标账号和撤销位置，不共享一份管理私钥。服务端日志能否归因到 key，还取决于实际日志配置与保留情况；共享系统账号下的全部进程行为不因此自动可区分。硬隔离需求继续参考[第 09 章的权限边界](09-private-access.md#2-明确这条-ssh-能做什么)。

## 变更顺序：先加新入口，再撤旧入口

第 02 章已经提供逐条操作；共享维护时增加一张小的验收表，列出本次必须继续可用的人、设备、worker 和来源路径。每次仅让一个操作者负责写访问策略，其他人进行验收。

1. **确认恢复可以实际使用。** 打开正确实例的 console，确认拥有所需账号/密码或救援方式；provider 登录/MFA 恢复材料应由 owner 保管。console 若仍依赖已损坏的 guest 认证，查清是否有可用的 rescue 路径和它的停机影响。
2. **留下旧路径与变更前配置。** 记录本次要改的文件/规则及准确回退方法；不在多个维护任务之间整体覆盖配置快照。
3. **先添加需要的 key/账号/允许规则。** 保留其他已确认的合法入口。动态家庭/移动 IP 不适合未经恢复设计就写死为唯一来源。
4. **校验待生效配置。** 检查语法、该连接上下文的计算结果，以及 firewall 的实际 owner。失败时停在应用之前。
5. **让变更生效并测试全新连接。** 从各自真实来源、真实运行用户建立新连接，验证身份与批准的实际能力。原会话、连接复用和本机 root 的测试都不能替代 worker 验收。
6. **新路径通过后才收掉旧入口。** 再验收一次应保留的访问，以及本次确需禁止的新连接。撤销已有会话和后台任务另作明确决定。

只调整 SSH 认证时，按实际服务管理方式进行 reload；修改 `Port`/`ListenAddress` 还涉及监听和云规则。在 Ubuntu 24.04 的 socket activation 路径下，重载 `ssh.service` 不一定更新 socket 监听。不要把“reload 成功”当成整条路径已经验证。[Ubuntu 24.04 release notes](https://discourse.ubuntu.com/t/ubuntu-24-04-lts-noble-numbat-release-notes/39890)

## 两种检查各自证明什么

### 服务端：语法与连接上下文

**运行位置：已保留的 VPS 管理会话或 console；只读校验。** 服务实际使用自定义配置文件或启动参数时，同步核对那个来源。第二条中的身份和文档地址要替换为该客户端在服务器看来真实的连接上下文。

```sh
sudo /usr/sbin/sshd -t
sudo /usr/sbin/sshd -T -C user=operator,addr=198.51.100.20,host=client.example.com,laddr=192.0.2.10,lport=22
```

`-t` 检查配置语法与 key 的基本有效性；`-T -C` 计算相应 `Match` 条件下的配置。它们不证明运行中的 daemon 已重载、不检查完整网络路径，也不代替账号、PAM、实际公钥文件权限和新连接认证。OpenSSH 多数单值选项使用先取得的值，应把 `Include` 顺序与 `Match` 一起读。[sshd(8)](https://man.openbsd.org/sshd.8)、[sshd_config(5)](https://man.openbsd.org/sshd_config.5)

### 客户端：真正的新连接

**运行位置：应获准访问的那台电脑或真实 worker 环境。** 以下仅用于已独立核验 host key 的普通直连、单把 Ed25519 私钥测试；`192.0.2.10` 和文件名都是示例。

```sh
ssh -F /dev/null -o ControlMaster=no -o ControlPath=none \
  -o IdentitiesOnly=yes -o IdentityAgent=none \
  -o PreferredAuthentications=publickey \
  -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no \
  -o StrictHostKeyChecking=yes -o ConnectTimeout=10 \
  -i ~/.ssh/infra_demo_ed25519 operator@192.0.2.10 'id'
```

`-F /dev/null` 排除日常配置里附加的身份与跳板；`IdentityAgent=none` 不借 ssh-agent 的另一把 key。带口令的文件可能需要人工解锁。`ControlPath=none` 禁用连接复用；仅写 `ControlMaster=no` 仍可能复用已有 master。预期输出准确的目标用户身份；超时只限制连接/初始握手阶段，不是任意远程任务的执行期限。[ssh_config(5)](https://man.openbsd.org/ssh_config.5)

如果真实路径依赖 ProxyJump、专用 known_hosts、SSH certificate、硬件 key 或受限命令，使用核对过的专用配置完成同样的验收，保留必要条件；不要临时绕开这些条件让测试变绿。自动 worker 另核实 `BatchMode` 和真实凭据交付，不能用人工解锁成功证明无人值守可用。受限账号若不允许 `id`，应运行它被授权的最小检查动作。

登录成功之后，按用途检查所需项目或服务操作。owner 管理账号可按第 02 章验证 sudo；不需要 sudo 的 worker 验收其批准动作即可，不为对齐测试结果临时提权。

## fail2ban 与定点恢复

fail2ban 根据配置的日志过滤器累计失败，达到 jail 阈值后采取封禁动作；不会因为“哈希比较复杂”直接封 IP。多个用户经过同一 NAT、VPN 或跳板时，可能共享服务端所见的来源地址。是否安装、哪些 jail 正在运行、具体 ban 和时间窗口都需要证据。[Fail2ban 上游配置](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf)

**运行位置：仍可用的 VPS 管理会话/console；仅当已安装 fail2ban 时读取：**

```sh
sudo fail2ban-client status
sudo fail2ban-client status sshd
```

第二条中的 `sshd` 是常见 jail 名，先用第一条确认，再替换为真实名称。核对该次失败的日志、jail、源地址和封禁动作；不能从出现 fail2ban 进程就认定它是原因。确认误封后，由获授权的操作者只解除相应 jail 中的那个准确地址，修好实际凭据/客户端配置后进行一次新连接验收；不要循环解封重试、清空整个规则集或豁免整个公网网段。[Fail2ban 客户端手册](https://github.com/fail2ban/fail2ban/blob/master/man/fail2ban-client.1)

| 已确认的问题 | 定点恢复 | 恢复后的证据 |
| --- | --- | --- |
| 本次误删合法公钥 | 从受控记录恢复那一行，保留其余合法 key | 对应私钥建立全新连接 |
| 本次 SSH 片段排除合法用户/认证方式 | 回退这次片段，重新校验后按 unit 生效 | 对应用户的计算配置与真实新登录 |
| 云规则拦了来源/端口 | 在 provider 控制面修复准确规则 | 从原失败来源验证该路径 |
| 主机规则误挡入口 | 在旧会话/console 恢复本次准确规则 | 监听和外部新连接都成立 |
| 已证实的 fail2ban 误封 | 修复对应 jail/源地址与触发原因 | 一次成功新连接，日志不再重复触发 |
| 所有 SSH 入口丢失 | 使用事先确认的 console 或 provider rescue | 先修主机身份与必要入口，再恢复业务 |

不要把整机重装作为默认恢复操作。救援环境是否要关机、怎样挂载原盘、磁盘加密凭据和登录方式随 provider 不同；按该实例的官方流程处理。控制台/救援的能力示例可参考 [Hetzner Console](https://docs.hetzner.com/cloud/servers/getting-started/vnc-console/)与 [Hetzner Rescue](https://docs.hetzner.com/cloud/servers/getting-started/rescue-system/)，这不表示任意商家都提供相同能力。

## 撤销 key 后还有什么没有结束

移除 `authorized_keys` 中的一把 key，影响之后使用它进行的认证；已经认证的 shell、SSH 转发、复用连接和后台任务需要另行处理。若共享系统用户仍可修改其 `authorized_keys`，存活会话甚至有能力重新增加入口。因此“撤掉某把 key”与“结束某个操作者的现有能力”要分别验收。前者用全新且不复用的连接测试；后者先确认具体会话/任务和它们的安全停止方式，再按授权处理，不能按共享用户名杀掉所有人的工作。[OpenSSH 会话与认证](https://man.openbsd.org/sshd.8)

同理，删一条网络 allow 规则是否影响现有连接取决于具体防火墙与连接状态。把新连接的禁止结果写清楚，不承诺旧连接一定当场消失。

## 与时间问题交叉时

TOTP、短期 token 和 SSH certificate 等会检查时间或有效期；时钟异常可能同时影响业务登录和某些恢复路径。已有普通静态公钥的 OpenSSH 登录并不因此自动失效。实际报错要先确定认证机制，再联系[时间同步专题](time-synchronization.md)排查；不能把所有 `publickey` 拒绝都解释成 NTP 故障。[RFC 6238](https://www.rfc-editor.org/rfc/rfc6238.html)、[RFC 7519](https://www.rfc-editor.org/rfc/rfc7519.html)、[OpenSSH 证书与有效期](https://man.openbsd.org/ssh-keygen.1#CERTIFICATES)

恢复记录留在 owner 私有位置，记住实例、入口、账号、公开 key 指纹、真实来源、批准能力、变更 owner、准确回退及最后验收时间。密码/MFA 恢复材料通过适合的凭据管理方式保管。重点是 owner 在当前 agent 的会话消失以后，仍知道如何取回机器。

## 来源与维护

查阅日期：**2026-10-05**。OpenSSH 上游手册用于协议与选项语义，Ubuntu 操作仍以实际发行版和 unit 为准；fail2ban 以已安装版本和 jail 配置为准。社区讨论没有提供完整配置、日志和新连接对照，因此本文给出可验证的故障分支，不断言某次锁死已经归因。

**想一想：给两个 agent 各一把 key、都登录同一个可 sudo 的账号，是否隔离了它们的文件和系统权限？**

<details>
<summary>查看答案</summary>
<p>两把 key 可以分别识别和撤销登录入口；登录后仍共享该账号的权限。需要区分文件、进程或提权能力时，必须检查并设计真正的系统边界。</p>
</details>
