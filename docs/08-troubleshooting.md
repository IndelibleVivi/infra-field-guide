# 08 · 故障先分层，再改动

[返回首页](../README.md) · [网络路径图](architecture.md)

先记录**时间、运行机器、请求目标、预期与实测**。一次只验证一个假设；修复前留下足够的错误证据，不要一遇到错误就把网络、认证、缓存和服务器一起重装。

## 先从症状选入口

| 症状 | 第一个有区分力的检查 | 接下来 |
| --- | --- | --- |
| SSH 和网站同时超时 | 服务商 console 是否可进入；机器是否启动、资源是否耗尽 | console 可用则查网络和监听；console 也失败则查 provider |
| SSH 可以进，网站不可用 | 在服务所在机器请求 loopback origin | origin 失败查进程；成功再查反向代理/Tunnel/认证 |
| 域名失效，IP 路径可达 | DNS 的 A、AAAA、CNAME 是否与预期相符 | IPv6、旧记录、代理状态和解析缓存分开查 |
| 502 / 504 | 入口能否连接正确 origin 端口与协议 | `http`/`https` 配错、容器 localhost、进程退出、超时 |
| 401 / 403 | 哪一层返回响应，认证是谁发起的 | Access、应用、API provider 和账号权限分别处理 |
| 机器卡死、exit 137 | kernel OOM、cgroup 内存限制、人工 kill、PSI | exit 137 本身不证明 OOM；读[Ops](03-operations.md) |
| 磁盘还有空间但写失败 | `df -h` 与 `df -i`；目标是否在另一挂载点 | inode、权限、只读挂载、quota、打开但未释放的日志 |
| 迁完后偶尔读到旧内容 | DNS/Tunnel 多入口与两个 writer | 暂停有冲突的写入，核实状态 owner，勿直接切回旧库 |
| VPS 能看到 Mac，但 SSH 不行 | tailnet 路径、TCP22、普通 SSH key 与用户逐层检查 | 走[私有远程访问](09-private-access.md) |
| SSH 登录正常，agent 的 build 失败 | 用真实 worker 用户跑相同的非交互命令 | PATH、cwd、挂载盘、TCC、权限和 runtime；登录 shell 成功不够 |
| Claude 网页好，CLI 异常 | 实际 config directory 与认证来源 | 走[CC 环境清理与恢复](06-account-recovery.md) |

## 一条 HTTP 请求怎样分段验证

示例是 loopback `8080` 的 HTTP 应用与 `app.example.com`，都要换成你已确认的目标。命令是只读诊断，响应与日志仍可能包含私人数据，检查后再分享。

**应用所在 Linux 主机：**

```sh
systemctl status example-app.service --no-pager
journalctl -u example-app.service -n 50 --no-pager
ss -lntp 'sport = :8080'
curl --noproxy '*' --connect-timeout 3 --max-time 10 \
  --silent --show-error --output /dev/null --write-out 'origin HTTP %{http_code}\n' \
  http://127.0.0.1:8080/health
```

`example-app.service` 和 `/health` 都是占位示例，应用没有该 endpoint 时换成真正无副作用的只读请求。404 可能说明路径错，401 可能说明鉴权生效；不能把“不是 200”全部诊断成网络失败。确认正文或业务特征时避免打印完整用户数据。

**管理电脑或真实使用设备：**

```sh
dig app.example.com A
dig app.example.com AAAA
curl --noproxy '*' --connect-timeout 5 --max-time 15 \
  --silent --show-error --output /dev/null --write-out 'edge HTTP %{http_code}\n' \
  https://app.example.com/
```

这里 `--noproxy '*'` 明确测试直接路径。若日常使用必须经代理，再用第07章的显式代理命令测第二条路径；两份结果不要混记。公司/学校网络不能直连时，直接测试失败只说明这条路径失败。

接下来用真实客户端登录并做授权范围内的业务读写，确认请求到达预期部署。仅 curl 成功不能证明浏览器 Cookie、Access session、WebSocket、IDE 或 MCP 客户端都可用。Cloudflare Tunnel 没有公网可直连的 origin 时，在 origin 本机测 loopback，不凭空给它开放端口。

## SSH 失败时保留能返回的路

| 错误 | 意味着什么 | 下一步 |
| --- | --- | --- |
| timeout | 路径、ACL/firewall、睡眠或监听可能有问题 | 用 console／本地 Mac 查服务和网络；不先换密码 |
| connection refused | 对端可达但该端口未监听或明确拒绝 | 核对端口、Remote Login/sshd 与目标身份 |
| host key changed | 地址对应的主机身份改变，原因尚未确认 | 从 provider console 或 Mac 本地独立核对，不直接删 known_hosts |
| permission denied (publickey) | 网络走到了 SSH，身份验证失败 | 用户、IdentityFile、公钥、authorized_keys权限与from限制 |
| 登录能成功，命令找不到 | 非交互环境与平时终端不同 | 显式 runtime 路径或受控 PATH，不让 agent 猜 profile 内容 |

排查时保留当前已成功登录的 session，并确保 provider console 或 Mac 本地操作可用。`ssh -vv` 会显示主机和路径，日志不要原样贴公共 issue；也不要开启 `StrictHostKeyChecking=no` 把身份问题藏起来。

## 资源检查与下一步

**Linux 主机，只读：**

```sh
uptime
free -h
swapon --show
df -h /
df -i /
cat /proc/pressure/memory
journalctl -k --since '1 hour ago' --no-pager
```

权限不足、PSI 不可用、journal 不保留历史，要写 unknown。没有日志不等于没有故障；当前资源已经恢复也不说明故障时正常。内存、swap、cgroup 与日志限额的具体操作见[日常 Ops](03-operations.md)，可先用[health](../tools/README.md)保存一份资源快照。

做完修复，重复最初失败的那条路径，再看相邻路径是否受影响。例如调整 SSH 后验证新的独立登录，迁移后验证数据与定时任务，改 tailnet grant 后验证获准和未获准 peer。恢复窗口不够、数据 owner 不明、磁盘空间不足，先停下依赖它的变更，保留状态。

## 给别人或 agent 的最小故障包

```text
发生时间与时区：
目标角色、OS、应用版本（真实地址留在私人记录）：
运行命令的位置：
预期结果与实际结果：
准确错误（移除凭据与个人数据）：
最近相关变更：
已经验证的层／还未知的层：
仍然可用的登录或恢复路径：
希望执行的下一步及授权范围：
```

来源与参数核对日期：**2026-10-02**。HTTP/代理参数依据 [curl 官方手册](https://curl.se/docs/manpage.html)；SSH 依据 [OpenSSH 手册](https://man.openbsd.org/ssh.1)。各子系统的版本来源与恢复步骤链接在对应章节。
