# 02 · 第一次连接与基础加固

本章的明确环境是 **Ubuntu 24.04 LTS、systemd、OpenSSH server**，以及你自己有管理权的新 VPS。示例用户名是 `operator`；`192.0.2.10`、`198.51.100.20`、`2001:db8::10` 是文档地址，不能在公网连接。执行前换成自己从控制面板核实的地址。本地命令按 macOS、Linux 或 WSL 的 shell 编写；原生 PowerShell 的路径和工具可用性不同，不要直接混用。

目标是留下一个可恢复的服务器：普通用户以 SSH key 登录，需要时使用 sudo；入站端口有明确用途；更新与时间同步可检查；误操作后知道怎样从 console 恢复。下面是供你在自己服务器上手工执行的教程，作者未对读者的服务器执行这些修改。逐块阅读预期结果，遇到停止条件就停，不要整页粘贴执行。

## 1. 先打开恢复入口

**运行位置：服务商网页控制面板。** 找到 console/VNC/serial console，实际打开一次并确认能看到此实例的登录提示；如果镜像没有可用的 console 密码，先按服务商文档确认其救援登录方式。再找到 rescue/recovery 的说明。不要点击“重装”试验恢复，它可能清空磁盘。

在自己的私密记录中保存实例名、系统版本、地址、初始登录用户名、console 入口和救援文档。记录中不放明文私钥，分享故障记录前删去账号与凭据。保留服务商账号 MFA 的恢复方式；它与 SSH key 是两条独立恢复路径。

**预期：** 即使 SSH 配置错了，你仍有另一种进入实例的办法。**停止条件：** console 根本不可用、目标实例不明确，或救援流程要求你无法取得的凭据。先解决恢复入口，再做 SSH 或防火墙变更。

## 2. 本地生成登录密钥

SSH key 有两份：公钥可以放在服务器的 `authorized_keys`；私钥留在自己设备。私钥口令用于保护本地文件，不是远端登录密码。

**运行位置：本地电脑终端。** 先准备用户自己的目录，再看专用文件名是否已存在：

```sh
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ls -l ~/.ssh/infra_demo_ed25519 ~/.ssh/infra_demo_ed25519.pub
```

不存在时，`ls` 报 `No such file or directory` 是本步骤预期。若存在，确认它是否就是要用的密钥；不要覆盖。不确定时选择一个新的、可辨认的文件名并同步调整后文。

```sh
ssh-keygen -t ed25519 -a 64 -f ~/.ssh/infra_demo_ed25519 -C "operator-vps"
ssh-keygen -lf ~/.ssh/infra_demo_ed25519.pub -E sha256
```

交互中设置自己保管的口令。预期生成无后缀的私钥与 `.pub` 公钥，并显示 `SHA256:` 指纹。若提示覆盖，回答 `n` 后停止核对；磁盘或权限错误没有解决前不要继续。把 `.pub` 的内容提交到服务商的 SSH key 字段，或稍后手工安装。不要上传无后缀文件，也不要把私钥粘进聊天窗口。

## 3. 核验服务器身份，再接受 host key

你的用户 key 用来证明“你是谁”；服务器 host key 用来证明“你连的是谁”。首次连接时，SSH 不认识服务器是正常现象，但直接输入 `yes` 只是在盲信本次连接。

**运行位置：刚核实的服务商 console，使用初始管理员。** 读取服务器的 Ed25519 host key 指纹：

```sh
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
```

若已经是 root，`sudo` 前缀可省略。只读取 `.pub` 文件；不要显示 host 私钥。预期是一行 `SHA256:` 指纹。若文件不存在，按该镜像实际提供的 host key 算法核验相应 `.pub`，不要为迁就教程重新生成整套 host key。若服务商在独立、已认证的控制面板显示指纹，也可核对，但单独的 `ssh-keyscan` 只能取得网络上返回的 key，不能证明其可信。

**运行位置：本地电脑。** `INITIAL_USER` 换成服务商给的初始用户名；若控制台分配的 SSH 端口不是 22，应按其说明加 `-p`。

```sh
ssh -o HostKeyAlgorithms=ssh-ed25519 -i ~/.ssh/infra_demo_ed25519 INITIAL_USER@192.0.2.10
```

仅当这里的算法和 `SHA256:` 指纹与 console 所见相符时接受。成功后 host key 会进入本地 `known_hosts`。初始镜像只支持密码时，按服务商初始方式登录；不要因此提前禁用密码。

**停止与恢复：** 指纹不同、显示 `REMOTE HOST IDENTIFICATION HAS CHANGED` 或实际目标有疑问时先停。核对是否刚刚由你重装、是否 IP 被回收、是否 DNS 指错以及 console 指纹。只有确认变更来源后才按 `ssh-keygen(1)` 的说明移除那一个旧记录并重新核验，不关闭 `StrictHostKeyChecking`，也不清空整个 `known_hosts`。

## 4. 识别系统与当前 SSH 服务

**运行位置：已建立的初始管理员 SSH 会话或 console。以下全是读取操作。**

```sh
cat /etc/os-release
uname -m
ps -p 1 -o comm=
whoami
id
systemctl status ssh.service ssh.socket --no-pager
sudo ss -lntp
```

预期确认 Ubuntu `24.04`、预期 CPU 架构，PID 1 为 `systemd`。`ss` 显示实际监听端口和地址；`0.0.0.0` 表示所有 IPv4 接口，`[::]` 是 IPv6 通配地址，其 IPv4 接受行为还与 socket 设置有关，不能只凭这行推断双栈均可用。

Ubuntu 24.04 的 OpenSSH 默认可能使用 **systemd socket activation**；监听者可能是 systemd，`ssh.service` 由连接激活，`ssh.socket` 管理监听。身份验证设置与监听地址设置的生效路径应分别判断。本章保留已有端口，不把改 SSH 端口当成安全前提。[Ubuntu 24.04 release notes](https://discourse.ubuntu.com/t/ubuntu-24-04-lts-noble-numbat-release-notes/39890)

如果发行版、服务名或 PID 1 不符，停止套用后续修改，先找该系统的对应文档。某个 unit 不存在导致 `systemctl status` 返回非零时，读取完整输出；不要为了让命令变绿卸载或重装 SSH。

## 5. 建立普通 sudo 用户并安装公钥

**运行位置：初始管理员会话，保留该会话直到第 8 节完成。** 先确认名字未被使用：

```sh
getent passwd operator
```

本教程预期无输出、退出状态 2；若已有该用户，先确认其所有权和现有用途，不要覆盖 home 或重置其密钥。确认是新用户名后：

```sh
sudo adduser operator
sudo usermod -aG sudo operator
id operator
```

按提示设置独立密码，供需要时的 sudo/console 认证使用。`id` 应包含 `sudo` 组。`-aG` 的 `-a` 表示追加组；遗漏它会改掉原有附加组。若命令失败，保留原会话，解决错误后再继续。

**运行位置：本地电脑。** 显示并复制刚创建的公钥整行：

```sh
cat ~/.ssh/infra_demo_ed25519.pub
```

**运行位置：初始管理员会话。** 创建目录，用编辑器粘贴那一行公钥：

```sh
sudo install -d -m 700 -o operator -g operator /home/operator/.ssh
sudoedit /home/operator/.ssh/authorized_keys
sudo chown operator:operator /home/operator/.ssh/authorized_keys
sudo chmod 600 /home/operator/.ssh/authorized_keys
sudo ssh-keygen -lf /home/operator/.ssh/authorized_keys -E sha256
```

`sudoedit` 会打开系统配置的编辑器；若是 nano，保存用 `Ctrl+O`、确认文件名后回车，退出用 `Ctrl+X`。公钥应是一行，以 `ssh-ed25519` 开头，不带 Markdown 围栏、行号或私钥头。预期最后显示的用户 key 指纹与本地第 2 节相同。若文件已有内容，保留已确认有效的其他公钥并追加，不整体替换。不要把初始 root 的所有 `authorized_keys` 不加检查地复制给新用户。

## 6. 验证第二次独立登录与 sudo

**运行位置：本地电脑的另一个终端窗口。** 保留第一个连接；显式禁用连接复用和密码回退，以免复用旧连接掩盖配置问题。

```sh
ssh -o ControlMaster=no -o ControlPath=none -o IdentitiesOnly=yes \
  -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no \
  -i ~/.ssh/infra_demo_ed25519 operator@192.0.2.10
```

**运行位置：新登录的 operator 会话。**

```sh
whoami
id
sudo -k
sudo -v
sudo id -u
```

预期当前用户是 `operator`，必要时输入刚设置的 **operator 密码**，最终输出 `0`。SSH 提示 key 的 passphrase 是本地私钥口令；sudo 提示的是服务器用户密码，两者不要混淆。若密钥登录或 sudo 失败，停在这里。回到原会话检查公钥、用户组、文件权限和 `sudo journalctl -u ssh.service --since '-10 minutes' --no-pager`，不要先关密码或 root 登录来“排除干扰”。

## 7. 读取有效配置，再收紧认证

OpenSSH 对多数单值关键字采用**先读到的值生效**，不是“文件名数字最大就赢”。Ubuntu 主配置通常在前部 `Include /etc/ssh/sshd_config.d/*.conf`；cloud-init 或镜像可能已经写入片段。还有 `Match` 条件可以按用户、来源等改变结果。先找这些事实，再选编辑位置。[Ubuntu OpenSSH guide](https://ubuntu.com/server/docs/openssh-server/)、[Ubuntu 24.04 sshd_config(5)](https://manpages.ubuntu.com/manpages/noble/man5/sshd_config.5.html)

**运行位置：operator 会话。读取与校验，不修改。**

```sh
sudo ls -l /etc/ssh/sshd_config.d
sudo grep -nE '^[[:space:]]*(Include|Match|PasswordAuthentication|KbdInteractiveAuthentication|PubkeyAuthentication|PermitRootLogin|AuthenticationMethods)' /etc/ssh/sshd_config
sudo grep -RnsE '^[[:space:]]*(Include|Match|PasswordAuthentication|KbdInteractiveAuthentication|PubkeyAuthentication|PermitRootLogin|AuthenticationMethods)' /etc/ssh/sshd_config.d
sudo /usr/sbin/sshd -t
sudo /usr/sbin/sshd -T
```

`grep` 没有匹配可返回 1，不等于 SSH 故障；`sshd -t` 则应无输出且成功，出错必须先解决。`-T` 展示配置计算结果，不证明当前进程已经重载。用 `echo "$SSH_CONNECTION"` 在远端查看当前连接的客户端地址和服务端地址，按实际值替换下面的文档地址，检查该登录上下文。存在 `Match Host` 时还需使用实际匹配的客户端主机名，并阅读本机 `man sshd` 的 `-C` 说明。

```sh
sudo /usr/sbin/sshd -T -C user=operator,addr=198.51.100.20,host=client.example.com,laddr=192.0.2.10,lport=22
```

确认第二登录已经成功、没有依赖密码的其他使用者后，本例创建一个靠前且尚不存在的自有片段。先用 `sudo ls -l /etc/ssh/sshd_config.d/00-local-auth.conf` 确认名字未被占用；若已有文件或有更早覆盖设置，先理清该设置的 owner，不另加重复片段碰运气。

**运行位置：operator 会话。此步修改 SSH 认证规则。**

```sh
sudoedit /etc/ssh/sshd_config.d/00-local-auth.conf
```

文件内容：

```text
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
```

这是面向已经验证 key 的普通管理场景。如果你原来使用需要 keyboard-interactive 的 MFA，不套用这一片段。系统账户密码仍可用于 sudo；禁用的是 SSH 的这些认证方式。

再次执行 `sudo /usr/sbin/sshd -t`、`sudo /usr/sbin/sshd -T` 和带真实上下文的 `-T -C`，确认上述四项分别为 `yes/no/no/no`；也用 `user=root` 检查 root 上下文。任何语法错误或不符合预期，都先用 `sudoedit` 修正新文件，**不要重载**。

确认无误后：

```sh
sudo systemctl reload ssh.service
systemctl status ssh.service ssh.socket --no-pager
```

这是重载认证配置。若 unit 不活跃或 reload 失败，保留原连接，查看 `sudo journalctl -u ssh.service -u ssh.socket --since '-10 minutes' --no-pager` 后按实际 unit 处理，不把失败理解为配置已经应用，也不要盲目 stop SSH。若未来确需改 `Port`/`ListenAddress`，还必须处理 24.04 的 socket generator、云防火墙与新端口验证；本节没有完成那种迁移。

## 8. 收紧后再次独立登录；需要时回退

**运行位置：本地第三个终端窗口。** 重复第 6 节的独立 key 登录，再验证 `sudo -v`。新连接成功才说明真实认证路径可用；第一条一直在线的 shell 不算验证。还应确认读取出的有效配置与预期一致，而非只凭日志里一个“reload succeeded”。

如果新连接失败，保留旧管理员连接或进入 console。**只回退本次新建的片段**：用 `sudoedit /etc/ssh/sshd_config.d/00-local-auth.conf` 注释本次新增行，重新 `sshd -t`，成功后 `systemctl reload ssh.service`，再测试登录。这样恢复之前的配置来源；不要把整个 `/etc/ssh` 替换成网上模板。若原因其实是防火墙或网络，修改认证不会解决问题，按下一节和故障表区分。

## 9. 先允许 SSH，再启用主机防火墙

**运行位置：服务商控制面板。** 先看云防火墙/security group 是否绑定了该实例，读清入站和出站默认策略。在收紧入站前保留实际 SSH 端口，IPv4 和 IPv6 分别核对。只有固定且可信的管理来源时才使用来源 IP 白名单；若你的家庭/移动公网地址会变，先设计好 console 或私有管理网恢复路径。不要把文档示例 IP 写成自己的白名单。

**运行位置：operator 会话。** 先检查 UFW 是否安装、是否已经有人维护规则、IPv6 是否受管理：

```sh
command -v ufw
sudo ufw status verbose
sudo grep '^IPV6=' /etc/default/ufw
ip -br address
ip -4 route
ip -6 route
sudo ss -lntup
```

本例要求 `IPV6=yes`，并假定 SSH 实际监听 TCP 22。如果 UFW 未安装，在确认包管理器正常后用 `sudo apt update`、`sudo apt install ufw` 安装，再回到检查。如果这是尚未启用 UFW 的新机，而配置为 `IPV6=no`，先用 `sudoedit /etc/default/ufw` 把该项改为 `IPV6=yes`，保留其他内容并读回确认，再继续。不要在既有复杂 nftables/iptables、Docker 或 VPN 规则的系统上直接套用新机配方。若 UFW 已启用或有规则，先理解原有用途，不 reset。

**仅在确认这是尚未设规则的新机、SSH 确实为 22 后，运行以下修改：**

```sh
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw enable
sudo ufw status verbose
```

`enable` 可能提示中断现有连接，确认恢复入口和 SSH allow 规则已准备好再答复。预期 active，默认拒绝入站、允许出站，并看到 SSH 的 IPv4 和 `(v6)` 规则。再次从本地开新 SSH 连接；有可用 IPv6 的本地网络时，也用 `ssh -6` 配合服务器 IPv6 测试。IPv6 在本地不可用时，应把该条验收记为未完成，不通过删除 AAAA 或随意关闭 IPv6 掩盖原因。

失败时优先从保留会话/console 检查端口和规则，补回准确的 SSH allow。若确实是刚启用的 UFW 锁住入口，可在 console 临时 `sudo ufw disable` 回到修改前状态，保持云防火墙保护，修正规则后重新验证。云防火墙挡住流量时，关 UFW 不会修复；在面板恢复该次云规则变更。

新服务部署后再按用途放行，例如公开 HTTPS 需要 TCP 443；只有确有 HTTP/证书验证需要时才放行 TCP 80。不要为了“省事”一次允许所有端口，也不通过关掉全部 ICMPv6 解决 IPv6 扫描；IPv6 邻居发现与路径 MTU 等需要相应 ICMPv6 工作。[Ubuntu firewall guide](https://documentation.ubuntu.com/server/how-to/security/firewalls/index.html)

**Docker 例外：** Docker 发布端口的流量可能在到达 UFW 管理的链之前被转发，`ufw deny`/`status` 不能证明容器端口被阻断。优先减少 published ports，确认绑定地址；需要本机反向代理访问时使用明确的 loopback 绑定，再按实际 Docker 版本和 firewall backend 使用官方适配方式。不要直接关闭 Docker 的 iptables 管理来“修好 UFW”。最后从授权的外部客户端测试实际暴露面。[Docker packet filtering and firewalls](https://docs.docker.com/engine/network/packet-filtering-firewalls/)

## 10. 安全更新、时间与资源基线

**运行位置：operator 会话。以下先读取。**

```sh
timedatectl status
free -h
df -hT /
df -i /
uptime
systemctl --failed --no-pager
systemctl list-timers --all --no-pager
apt-config dump | grep -E 'APT::Periodic|Unattended-Upgrade'
```

预期时钟与真实时间相符，时间同步服务状态可解释，磁盘/内存有可用余量，没有不明 failed unit。时区可以不同，但错误的绝对时间会影响 TLS、日志与定时任务。若未同步，先看当前使用的时间服务（如 systemd-timesyncd 或 chrony）及日志、DNS/出站条件，不并行启用多个时间客户端。`timedatectl` 的单个字段不代替对实际时间源的检查。

**仍在 operator 会话，更新会安装软件并可能重启服务：**

```sh
sudo apt update
apt list --upgradable
sudo apt upgrade
```

逐步看完整输出，确认更新来源与包列表，理解提示后再继续；初次练习不加 `-y` 隐藏决策。`apt update` 出现仓库、签名或网络错误时先停，不能把旧索引当作最新。锁被占用时查看正在运行的自动更新任务，等待其完成；不要删除 lock 文件或强杀 dpkg。配置文件冲突时保留当前有效配置并阅读差异，尤其不要盲目替换 SSH 配置。

Ubuntu 默认安装通常有 unattended-upgrades，但供应商镜像可能改变它。查明是否启用、允许哪些来源、日志有无成功记录；没有安装/启用时，按官方指南执行 `sudo apt install unattended-upgrades` 与 `sudo dpkg-reconfigure unattended-upgrades`。完成后用 `sudo unattended-upgrade --dry-run --debug` 核查允许来源和候选更新，再读 `/var/log/unattended-upgrades/` 的记录。自动安全更新不等于第三方软件、容器镜像和全部依赖都会更新；不要未经计划启用自动重启。[Ubuntu security updates](https://documentation.ubuntu.com/security/security-updates/)

**读取是否提示重启：**

```sh
if test -e /var/run/reboot-required; then cat /var/run/reboot-required; fi
```

需要重启时，先读 [运维章节的更新与重启](03-operations.md)，确认没有运行中的写入工作并有恢复入口。更新完成但还在旧内核上运行，与新内核已经启动是不同状态。

## 11. 用症状选择下一步

| 症状 | 先核查 | 此刻不要做 |
| --- | --- | --- |
| SSH timeout | 地址/端口、云防火墙、主机防火墙、客户端路由、实例 console | 反复重置密码 |
| Connection refused | 实际监听端口、`ssh.socket`/`ssh.service` 状态 | 不看日志就重装系统 |
| Permission denied (publickey) | 用户名、指定 key、公钥内容/权限、服务端日志 | 开放所有入站端口 |
| Host key changed | console 指纹、重建历史、地址归属 | 关闭 host key checking |
| 只有部分网络能访问 | 分别测试 IPv4/IPv6、DNS 与路径 | 假设全站可用或仅凭 ping 判故障 |
| sudo 不可用 | 当前用户组、新登录是否带入组、sudo 配置 | 关闭最后一个初始管理员会话 |

完成时，记录已验证的第二登录、sudo、有效 SSH 配置、云与主机防火墙、IPv4/IPv6 实测范围、更新时间、console 恢复方式。可以关闭初始 root/管理员 SSH 会话；console 仍是恢复通道。然后进入 [03 · 日常运维](03-operations.md)。

## 一手资料与查阅日期

查阅日期：**2026-10-02**。命令以 Ubuntu 24.04 的实际本机 manual 和配置为最后核对依据，供应商镜像不保证保留发行版默认。

- [Ubuntu OpenSSH server](https://ubuntu.com/server/docs/openssh-server/)：密钥、配置片段与配置检查。
- [Ubuntu 24.04 sshd_config(5)](https://manpages.ubuntu.com/manpages/noble/man5/sshd_config.5.html)：先读到的值、Include 与 Match；也可在目标机使用 `man sshd_config`。
- [OpenBSD sshd(8)](https://man.openbsd.org/sshd)：`-t`、`-T`、`-C` 的上游说明。
- [OpenBSD ssh-keygen(1)](https://man.openbsd.org/ssh-keygen)：key 与指纹核验。
- [Ubuntu 24.04 release notes](https://discourse.ubuntu.com/t/ubuntu-24-04-lts-noble-numbat-release-notes/39890)：SSH socket activation。
- [Ubuntu firewall](https://documentation.ubuntu.com/server/how-to/security/firewalls/index.html)：UFW 的主机防火墙职责。
- [Docker packet filtering and firewalls](https://docs.docker.com/engine/network/packet-filtering-firewalls/)：Docker 与 UFW 的交互。
- [Ubuntu security updates](https://documentation.ubuntu.com/security/security-updates/)：自动安全更新的配置、来源与日志。
