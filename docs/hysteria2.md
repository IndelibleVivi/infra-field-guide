# Hysteria 2 实用教程：部署、连接与维护

写给准备在自己的 VPS 上搭 Hysteria 2（下文简称 HY2）的人。目标是：电脑或手机能连上，证书验证保持开启，重启与续期有明确的负责人，出问题时知道查哪一段。

**主线：Ubuntu 24.04 LTS + systemd + 官方 Hysteria 2 + 自动申请证书。** Debian 的 systemd 环境也可参考，包名、服务与权限以目标机实际输出为准。示例全是占位符；只在自己有权管理的服务器和网络上执行。

这是一份可以单独转发的 Markdown。官方资料查阅日期：**2026-11-13**。本文完成了参数核对与本地静态检查；没有替读者安装服务，也没有验证读者的网络、设备或吞吐量。

## 先看整条路

```text
电脑 / 手机里的 HY2 客户端
    │ 加密连接：UDP/443，验证 proxy.example.com 的证书
    ▼
你自己的 VPS 上的 Hysteria 2
    │ 用 VPS 的网络访问目标
    ▼
目标网站 / API

证书另一条路：CA → VPS 的 TCP/80 → Hysteria 内置 ACME HTTP-01
```

DNS 把 `proxy.example.com` 指向 VPS；客户端必须真正选择这个节点，应用请求才会走它。给某个网站设置 Cloudflare Tunnel，不会自动让电脑的出口走这台 VPS。

可扩展成两个独立节点：A 和 B 各有域名、密码、证书与服务，客户端在两者中选择。它们不是 A 转发到 B 的多跳链，也不会因为买了两台就自动故障切换。另配 Trojan / TCP 可以应对 UDP 路径不可用；**本教程完成一个 HY2 节点，TCP 备用是独立部署。**

## 1. 开始前准备四样东西

| 项目 | 本文示例 | 换成什么 |
| --- | --- | --- |
| 自己能 SSH 登录的 VPS | Ubuntu 24.04 + systemd | 你已核实过的机器和管理员入口 |
| 自己控制的域名 | `proxy.example.com` | 真实、可修改 DNS 的域名 |
| 证书联系邮箱 | `admin@example.com` | 自己能收信的邮箱 |
| 独立的 HY2 密码 | `REPLACE_WITH_RANDOM_PASSWORD` | 随机生成并妥善保存的长密码 |

`example.com` 是文档示例，不能用它申请证书。服务器不必装桌面环境，也不需要先装面板、Docker 或住宅代理。先让一个节点稳定工作，再决定是否需要第二台和其他协议。

先核对 SSH 主机身份，保留一个已经登录的终端和商家的控制台入口。本文不会重置 SSH、防火墙或其他既有服务。

**下面标注「VPS」的命令在服务器执行；「本地」在电脑执行。不要把服务端配置粘进手机客户端。**

## 2. DNS、端口和证书要配成一套

给域名添加 A 记录，指向 VPS 的公网 IPv4。只有确认 IPv6 已分配、服务监听、两层防火墙和客户端路径都可用时，才添加 AAAA；坏掉的 AAAA 会让一部分设备连不上，也可能影响签证书。

如果 DNS 托管在 Cloudflare，这个记录选 **DNS only / 灰云**。普通橙云 HTTP 代理不会把你的 HY2 认证流量转交给这台服务器；看到 Cloudflare 的 HTTP/3 宣传也不能据此推断能代理 HY2。[Hysteria 官方 CDN 说明](https://v2.hysteria.network/docs/misc/CDN/)

本教程选内置 ACME **HTTP-01**，端口安排如下：

| 用途 | 入站端口 | 说明 |
| --- | --- | --- |
| 已有 SSH 管理 | 以当前 SSH 端口为准 | 保留现有规则，不能假定所有人都用 22 |
| HY2 | **UDP/443** | 客户端连接走这里；只开放 TCP/443 无效 |
| HTTP-01 申请与续期 | **TCP/80** | CA 从公网访问；未来续期时也要可达 |

云控制台的 security group / firewall 和 VPS 本机 firewall 都要核对。先在 **VPS** 看当前状态：

```sh
sudo ss -lunp 'sport = :443'
sudo ss -ltnp 'sport = :80'
sudo ss -ltnp 'sport = :443'
sudo ufw status verbose
```

如果没有 UFW，沿现有 nftables / iptables 管理路径检查。若 UFW 已经 active、你确认继续用它管理，才添加本教程的两条规则：

```sh
sudo ufw allow 443/udp
sudo ufw allow 80/tcp
```

不要为照抄教程执行 `ufw reset`，也不要在没保留实际 SSH 入口时贸然启用它。云 firewall 里的入站放行仍需单独完成；使用受限出口策略时，还要允许 DNS 查询、ACME 的 HTTPS 请求与实际目标访问。

**端口冲突先查 owner。** UDP/443 已占用时，先确认是否已有 HY2、HTTP/3 或其他服务。TCP/80 已有 Nginx / Caddy 时，本文的独立 HTTP-01 路线需要改为正确的 challenge 路由、外部证书部署，或按官方文档选择 DNS-01；不要直接停止现有网站。TCP/443 与 UDP/443 是不同 socket，可以分别由不同服务使用；但若改用 ACME TLS-ALPN-01，它会用到 TCP/443，可能与现有服务冲突。[完整服务端 TLS / ACME 配置](https://v2.hysteria.network/docs/advanced/Full-Server-Config/#tls)

这里需要一个公网可直接接受上述入站连接的 VPS。NAT VPS、共享端口机器和受额外网络限制的环境需要单独映射，不能原样套用。

## 3. 安装官方程序，确认谁负责启动

**VPS：**以下安装步骤会添加软件和 systemd 服务，供你在确认目标与前提后自行执行。已有 HY2 的机器先检查版本、unit 与现有配置，不把重装当成排障。

```sh
sudo apt-get update
sudo apt-get install -y ca-certificates curl openssl nano less dnsutils
```

先下载官方脚本到一个新的临时文件，查看后再以管理员权限安装：

```sh
hy2_installer=$(mktemp)
curl --fail --show-error --location --proto '=https' --tlsv1.2 \
  https://get.hy2.sh/ -o "$hy2_installer" &&
  less "$hy2_installer" &&
  sudo bash "$hy2_installer"
```

**逐条确认成功后再继续；下载失败就停，不执行空文件或错误页面。** `less` 里按 `q` 退出。脚本由官方文档链接提供；它会安装程序、systemd unit 和示例配置，仍需你完成配置。下载遇到 403、TLS 或连接失败时，保留错误，到[官方安装说明](https://v2.hysteria.network/docs/getting-started/Installation/)查看 GitHub Releases 发布产物，或采用官方 installer 的 `--local` 本地二进制安装方式，别换成来路不明的镜像脚本。[官方安装脚本与管理命令](https://v2.hysteria.network/docs/getting-started/Server-Installation-Script/)

```sh
/usr/local/bin/hysteria version
sudo systemctl cat hysteria-server.service
sudo systemctl show hysteria-server.service -p User -p Group -p WorkingDirectory
getent passwd hysteria
```

标准安装的主配置是 `/etc/hysteria/config.yaml`，服务名是 `hysteria-server.service`。下面采用 unit 的运行用户和组均为 `hysteria` 的新安装；若实际输出不同，先按已安装 unit 确认权限与路径，再继续。不要为了读取证书，把整个服务改成 root。

服务使用已有 unit 的低端口绑定能力；**不要另开一个 `sudo hysteria server` 长期进程**与它争抢端口。

## 4. 写服务端配置：先不加调参

**VPS：**先备份安装生成的配置，再生成本节点独立的密码：

```sh
hy2_config_backup="/etc/hysteria/config.yaml.before-$(date -u +%Y%m%dT%H%M%SZ)"
sudo cp -p /etc/hysteria/config.yaml "$hy2_config_backup"
sudo chmod 600 "$hy2_config_backup"
printf '配置备份路径：%s\n' "$hy2_config_backup"
openssl rand -hex 32
sudo nano /etc/hysteria/config.yaml
```

把生成的密码存进自己的 password manager，后面客户端用同一个值。不要把真实密码、节点链接或二维码上传到公开仓库、截图或在线配置转换网站。

将配置改成下面这份，替换三个占位符。YAML 用空格缩进：

```yaml
listen: :443

acme:
  domains:
    - proxy.example.com
  email: admin@example.com
  ca: letsencrypt
  type: http
  dir: /var/lib/hysteria-acme

auth:
  type: password
  password: REPLACE_WITH_RANDOM_PASSWORD
```

这一版让 Hysteria 自己申请、保存和续期证书，因此**不要再同时写 `tls.cert` / `tls.key`，也不必另跑 Certbot。** 如果服务器本来已有可靠的证书 owner，可改用 `tls` 文件模式；那时必须继续由那个 owner 负责续期、部署文件与权限，并确认 unit 的实际运行用户能读取新文件，不能把两种方案拼在一起。

为这份配置收紧读取权限，并为 ACME 准备独立、可写的状态目录：

```sh
sudo chown root:hysteria /etc/hysteria/config.yaml
sudo chmod 640 /etc/hysteria/config.yaml
sudo install -d -o hysteria -g hysteria -m 700 /var/lib/hysteria-acme
sudo -u hysteria test -r /etc/hysteria/config.yaml
sudo -u hysteria test -w /var/lib/hysteria-acme
```

`/var/lib/hysteria-acme` 会含私钥和 ACME 账户状态，要持续保留并按敏感数据管理。服务用户能读配置、能写证书目录，才能完成申请和后续续期。保持 DNS 正确、TCP/80 公网可达与机器时钟正常；首次申请成功不代表未来续期必然成功。

这份配置故意不写 `bandwidth`、`ignoreClientBandwidth`、obfs、QUIC window 或端口跳跃。它们各有具体用途，默认跑通以后才有调整的依据。

## 5. 启动并检查服务器这一侧

**VPS：**先看安装后的 unit 是否已有 `Restart=on-failure`。如果没有，在新机上创建一个独立 drop-in，让异常退出由 systemd 重试；不要覆盖已有 unit 或其他 drop-in：

```sh
sudo install -d -m 755 /etc/systemd/system/hysteria-server.service.d
sudo nano /etc/systemd/system/hysteria-server.service.d/10-restart.conf
```

文件内容：

```ini
[Service]
Restart=on-failure
RestartSec=5s
```

这会在进程异常退出后重试，手动 `systemctl stop` 不会因此被自动拉起；持续失败仍可能触发 systemd 的启动速率限制，需要先修复原因。[systemd.service 的 Restart 语义](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html#Restart=)

加载 drop-in，启用开机启动并启动服务：

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now hysteria-server.service
sudo systemctl status hysteria-server.service --no-pager
sudo journalctl -u hysteria-server.service -n 80 --no-pager
sudo ss -lunp 'sport = :443'
```

如果服务在编辑配置前已经运行，再明确重启一次以加载新配置：

```sh
sudo systemctl restart hysteria-server.service
```

你要看到：服务维持 `active (running)`、没有重复退出、证书申请与加载没有报错、UDP/443 由预期进程监听。HTTP-01 的 TCP/80 listener 可能只在 challenge 期间出现，空闲时看不到它不能单独证明申请失败。

遇到失败先读日志；不要连续重装或反复申请证书。CA 有速率限制，错误的 DNS、端口或权限不会通过重试自动修好。安装完成、unit enabled、进程 active、UDP 公网可达和客户端可用是不同事实。

## 6. 在电脑或手机上配客户端

客户端必须支持 **Hysteria 2**，旧版 Hysteria 1 配置不能混用。图形客户端的名字和菜单可能变化，可以从[官方第三方客户端列表](https://v2.hysteria.network/docs/getting-started/3rd-party-apps/)确认所用平台与当前支持情况。

### 手机或图形客户端：字段一一对应

| 客户端字段 | 本教程填写 |
| --- | --- |
| 类型 | Hysteria 2 / Hysteria2 / HY2 |
| Server / 地址 | `proxy.example.com` |
| Port / 端口 | `443`，不要填成容器内部端口 |
| Password / Auth | 服务端刚设置的随机密码 |
| SNI / Server Name | `proxy.example.com`，与证书名称一致 |
| TLS 验证 | 开启；`insecure` / `skip-cert-verify` 关闭 |
| Obfs / 混淆 | 关闭 / 留空，服务端没有配置它 |
| 上传 / 下载带宽 | 先不填；确认客户端对留空的具体语义 |

保存并**选择这个节点**，启动连接；有规则分流的客户端还要确认测试目标确实命中它。导入成功、延迟测试成功、真正的业务请求通过，分别验收。

### 原生 CLI：用来把问题缩小

**本地电脑：**按[官方安装说明](https://v2.hysteria.network/docs/getting-started/Installation/)获取与你的 OS / CPU 对应的客户端二进制，先运行 `hysteria version` 确认是 v2。以下假设可执行文件已在 PATH 中；若下载文件仍叫平台文件名，改用它的实际路径。这里不需要在电脑上安装 server unit。

新建 `hy2-client.yaml`，填同一个域名和密码：

```yaml
server: proxy.example.com:443
auth: REPLACE_WITH_RANDOM_PASSWORD

tls:
  sni: proxy.example.com
  insecure: false

socks5:
  listen: 127.0.0.1:1080

http:
  listen: 127.0.0.1:8080
```

在该文件所在目录运行：

```sh
hysteria client -c hy2-client.yaml
```

保留终端，在另一个终端测试。`127.0.0.1` 让代理只在自己的电脑回环地址监听；不要顺手改成 `0.0.0.0`。1080 / 8080 若已有程序占用，改成本地空闲端口，并同步修改测试命令。[原生客户端参数](https://v2.hysteria.network/docs/advanced/Full-Client-Config/)

### Mihomo：一份能独立使用的配置

**本地电脑：**下面是单独的测试 profile。已有 profile 的人只合并所需 node / group / rule，不要覆盖原有 DNS、TUN、rules 或 subscriptions。使用支持 Hysteria 2 的 Mihomo core；这是 Mihomo YAML，不能粘贴到原生 Hysteria 的服务端文件。

```yaml
mixed-port: 7890
allow-lan: false
mode: rule
log-level: info

proxies:
  - name: HY2-A
    type: hysteria2
    server: proxy.example.com
    port: 443
    password: REPLACE_WITH_RANDOM_PASSWORD
    sni: proxy.example.com
    skip-cert-verify: false

proxy-groups:
  - name: HY2-SELECT
    type: select
    proxies:
      - HY2-A

rules:
  - MATCH,HY2-SELECT
```

没有设置 `up` / `down` 或 obfs；字段语义见 [Mihomo Hysteria2 文档](https://wiki.metacubex.one/en/config/proxies/hysteria2/)。这个 profile 把经本地代理入口的请求选到 `HY2-A`，不会自动接管所有应用。若启动的是 CLI core，可先用 `mihomo -t -f hy2-mihomo.yaml` 校验，再用 `mihomo -f hy2-mihomo.yaml` 运行；图形壳按其导入与 core 校验路径操作。测试时用下节的 HTTP 命令，将端口换成 `7890`。

## 7. 真正验收：从自己的客户端走完整条路

**本地电脑：**以下原生客户端测试使用 `curl`；Windows PowerShell 请写 `curl.exe`，并按 PowerShell 规则处理换行。

```sh
curl --fail --show-error --connect-timeout 10 --max-time 30 \
  --noproxy '' --socks5-hostname 127.0.0.1:1080 \
  https://api.ipify.org
```

这是一个外部 IP 查询服务，会看到此次连接的出口地址；也可以换成自己控制的回显端点。结果应为你预期的 VPS 出口；与 VPS 公网地址和客户端日志一起核对。有 IPv6、NAT 或额外出口策略时，以实际选中的出口为准，不能只要求字符串等于面板里的某个 IPv4。

`--socks5-hostname` 让目标域名交给 SOCKS 代理解析；节点域名本身仍需要本地能解析。`--noproxy ''` 避免已有 `NO_PROXY` 列表把这次指定的代理绕开。若系统已经启用其他 VPN / TUN，底层到节点的连接仍可能穿过它；先明确这层关系，再判断是否为直连 HY2。

再选一个自己有权访问、内容稳定的 HTTPS 目标检查正文。例如：

```sh
curl --fail --show-error --connect-timeout 10 --max-time 30 \
  --noproxy '' --proxy http://127.0.0.1:8080 \
  https://example.com/ -o /dev/null -w 'HTTP %{http_code}\n'
```

Mihomo 的这个测试 profile 使用 `http://127.0.0.1:7890`。浏览器、手机 app 和后台服务是否采用代理，要在各自入口验证；一条 curl 成功不能代表所有程序都已接入。

最后检查维护闭环：服务 `is-enabled`、一次受控 service restart 后新连接正常、证书状态目录仍在、日志没有持续失败。真实 reboot 会影响整台 VPS，选择合适窗口并确认其他服务的恢复责任后再演练；别在正常业务中为测试代理突然重启整台机器。

## 8. 为什么 HY2 可能很快，哪些参数先别动

HY2 的基础传输是 UDP 上的 QUIC；它承载的目标流量可以是 TCP 或 UDP。路径、时段、丢包、家庭网络、VPS 负载以及客户端都会影响表现。网页体感快、握手延迟低和持续下载快是不同指标。

先保持双端不填带宽。原生 Hysteria 的拥塞控制会受客户端带宽声明和服务端设置共同影响；只看到服务端没写 `bandwidth`，不能推出所有客户端都在用 BBR。sing-box 的 HY2 outbound 不填 `up_mbps` / `down_mbps` 时使用 BBR；原生配置和 Mihomo 使用各自的字段名。[Hysteria 带宽与拥塞控制](https://v2.hysteria.network/docs/advanced/Full-Server-Config/#bandwidth)、[sing-box HY2 outbound](https://sing-box.sagernet.org/configuration/outbound/hysteria2/)

要调 Brutal 时，带宽值应来自当前客户端到 VPS 的可用路径；服务器网卡写着 1 Gbps、家里宽带标着 1000 Mbps，都不能直接当成这条跨网路径的实测值。填得过大会增加拥塞、重传与浪费。下载 / 上传也有方向：服务器上传对应客户端下载。`Mbps` 是 bit/s，下载软件里的 `MB/s` 是 byte/s，约相差八倍。

**Linux 的 `net.ipv4.tcp_congestion_control=bbr` 管的是内核 TCP。** 它不等于开启 HY2 的用户态 QUIC BBR，也不能证明这次速度提升来自它。先别为了 HY2 复制整套 TCP sysctl；UDP socket buffer 是另一项问题，只有日志与实际负载显示瓶颈时，再按[官方 Performance 指南](https://v2.hysteria.network/docs/advanced/Performance/)测量和调整。

比较速度时，用同一客户端、同一网络、同一目标、相近时间和相同的单连接 / 多连接条件，记录延迟、持续吞吐、失败和流量开销。下载别人的测试文件还会消耗对方与 VPS 的流量；用明确允许测速的端点，控制大小与次数。没有做这样的对照，就把「我这里用着快」保留为体验。

## 9. 连不上时，按这张表往下查

| 症状 | 先核对 | 别被什么误导 |
| --- | --- | --- |
| 域名打不开 / 解析错 | 本地 `nslookup proxy.example.com`；VPS 上 `dig +short A proxy.example.com`、`dig +short AAAA proxy.example.com`；是否指向目标公网地址、是否灰云 | DNS 成功只证明解析，不能证明端口或认证 |
| 服务启动就退出 | `systemctl status` 与最近 journal；配置语法、unit 用户对配置／状态的权限、UDP/443 冲突、TCP/80 是否被其他程序占用 | 不要反复重装、关闭 firewall 或用 root 掩盖权限错误 |
| 首次签证书失败 | DNS / AAAA、TCP/80 的两层 firewall、是否已有服务占用、ACME 目录权限、系统时间 | `acme.http.altPort` 改到 8080 并不会自动让 CA 改访问端口 |
| QUIC handshake timeout | 节点地址、UDP/443、客户端网络是否限制 UDP、是否误填 obfs；换另一个已授权网络对照 | `ping`、`nc -vz` 和普通 `openssl s_client` 都不能验证 HY2 认证路径 |
| 认证失败 | 两端 password 是否逐字一致、是否连错节点、客户端 core 的协议版本 | SNI 是证书名称，不是认证密码 |
| TLS / x509 错误 | SNI、证书名称与有效期、系统时钟、是否连到错误 IP | 不用 `insecure: true` 或跳过证书校验当常规修复 |
| 能连接但网站失败 | 节点实际选择、分流、客户端与服务端日志、VPS 的 DNS 和目标连通性 | 一次延迟测试不保证业务目标可达 |
| 大请求卡住或时快时慢 | 去掉自填带宽对照、检查 VPS CPU/内存/流量配额；再定位 UDP buffer、MTU 与实际丢包 | 不一次改 MTU、window、obfs 和几十项 sysctl |
| 过一段时间突然全部失败 | 证书续期、DNS 是否变了、状态目录是否丢失、服务是否停止 | 进程 active 不证明新 TLS 连接能通过 |

日志可能含客户端地址与访问目标；分享排障信息时只截必要错误，去掉密码、URI 和私人地址。[官方 Troubleshooting](https://v2.hysteria.network/docs/advanced/Troubleshooting/)

## 10. 后续维护与配置恢复

原生 ACME 路线由 Hysteria 进程负责证书；要保持服务、DNS、challenge 入口与状态目录可用。内置续期不需要另设每月 cron。若用的是外部 Certbot，则分别检查 scheduler、最近续期结果、部署后的实际证书、服务用户能否读取新文件，不能只看 timer active。

每次改配置前都建立一个新的、权限收紧的备份，并记住完整路径；不要覆盖最初的备份。若新配置失败，**先确认你要恢复的是哪一份**，再在 VPS 上运行：

```sh
# 替换为自己刚核对过的实际备份文件名，不使用通配符。
sudo cp -p /etc/hysteria/config.yaml.before-YYYYMMDDTHHMMSSZ /etc/hysteria/config.yaml
sudo chown root:hysteria /etc/hysteria/config.yaml
sudo chmod 640 /etc/hysteria/config.yaml
sudo systemctl restart hysteria-server.service
sudo systemctl status hysteria-server.service --no-pager
```

恢复后重新做客户端请求。配置备份不包含程序版本、ACME 状态、DNS 和 firewall；恢复 YAML 不会自动还原这些层。不要把 ACME 私钥和账户目录当成可随手删除的缓存。

升级前阅读官方 changelog，保存当前二进制版本、配置和所需恢复材料；官方 installer 的升级路径与首次安装共用，升级会影响运行服务，需要安排窗口并重新验收，不要定时盲跑。先从 unit 的 `ExecStart` 确认实际二进制路径；标准安装用 `/usr/local/bin/hysteria version` 查版本，不依赖 shell 中可能指向另一副本的 PATH。文件版本更新、服务进程真正重启、客户端仍可用，也要分别确认。

需要临时停止时，用 `sudo systemctl stop hysteria-server.service`；要取消开机启动，用 `sudo systemctl disable hysteria-server.service`。先停服务并不需要卸载、删配置或删证书。

## 11. 已有 Docker 部署时，哪些地方不同

这也是常见的双协议安排：HY2 容器负责 UDP，Xray Trojan 容器负责 TCP，外部证书 owner 给两者部署文件。**它与本文的原生 systemd + 内置 ACME 是两条完整路线，不要混装。**

| 事项 | 本文的新机路线 | Docker + 外部证书路线 |
| --- | --- | --- |
| HY2 公网入口 | 进程直接监听 UDP/443 | 例如宿主 `443:8443/udp`，容器 `listen: :8443` |
| 客户端填哪个端口 | 公网 `443` | 仍是公网 `443`，不能填内部 `8443` |
| 运行 owner | `hysteria-server.service` | Docker / Compose 与明确的 restart policy |
| 证书 owner | Hysteria 内置 ACME | Certbot / 其他外部 owner，负责续期与部署 |
| 配置方式 | `acme`，状态目录可写 | `tls.cert` / `tls.key`，文件通常只读挂载 |
| 权限 | unit 用户读配置、写 ACME 状态 | 非 root UID/GID 能穿过证书目录并读取文件；不能靠 `chmod 777` |
| UDP / TCP 共存 | 先只部署 HY2 | 独立发布 UDP/443 与 TCP/443，分别核对绑定地址和 owner |

Hysteria 文件证书模式在 TLS handshake 时读取证书文件，因此续期部署成功后不一定需要重启 HY2；同样使用证书的其他程序是否需要 reload / restart，由各自实现决定。只读挂载整个证书目录时，还要确认更新的是容器实际可见的目录与文件。[Hysteria TLS 文件行为](https://v2.hysteria.network/docs/advanced/Full-Server-Config/#tls)

Docker 发布端口还要按 [Docker firewall 文档](https://docs.docker.com/engine/network/packet-filtering-firewalls/)核对；不能把 UFW 显示的规则直接当成容器暴露面的完整描述。同一机器还有 Tailscale Serve 或其他 TCP/443 listener 时，逐个检查实际绑定的地址，避免 wildcard 绑定抢占；UDP/443 的成功不能证明 TCP 备用也正常。

## 给帮你操作的 agent

下面一段可以随教程一起转发。把占位符换成自己的目标，批准范围由你决定：

```text
帮我在自己有权管理的 VPS 上部署 Hysteria 2。

先只读核对：准确主机身份、OS/systemd、现有服务、UDP443与TCP80的owner、
实际SSH端口、现有firewall管理方式、云firewall、DNS A/AAAA、可用客户端。
不要打印凭据、重置firewall、停止现有网站或关闭TLS验证。

采用官方Hysteria 2 + 原生systemd + password auth + 内置ACME HTTP-01。
域名：proxy.example.com（需替换）。邮箱：admin@example.com（需替换）。
先不加bandwidth、obfs、端口跳跃或TCP sysctl调参。
已安装同协议或有端口冲突时先报告具体owner和可选路径，不并行重装。

先列出具体安装、配置、端口、证书与恢复方案；我批准变更范围后再执行。
验收分开报告：配置文件、运行unit、UDP监听、证书申请/续期责任、
开机启动、真实客户端认证、出口及业务请求；没有做的不要写成通过。
云账号修改、已有服务中断、整机reboot与删除资料另行说明。
交付配置路径、版本、维护命令、准确恢复路径和脱敏客户端字段。
```

如果还需要解释 DNS / Tunnel / VPN / 代理的区别，继续读[第 07 章](07-network-and-proxies.md)；新机的管理与恢复基础见[第 02 章](02-first-server.md)。
