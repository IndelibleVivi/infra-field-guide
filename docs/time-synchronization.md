# 机器时间、时区与同步

[返回首页](../README.md) · [首日检查](02-first-server.md#10-安全更新时间与资源基线) · [给 agent 的时间检查工单](../agents/time-sync.md)

## 这一页帮你做什么

先把日常时间约定讲清楚：服务器如何记录时刻，界面与 agent 如何理解用户的本地时间，定时任务和日志怎样跨机器对应。需要排障时，再检查当前偏差、校时服务与 UDP 123 路径。这一页适用于一台 VPS，也适用于[多机器、多 harness 的协作](multi-machine-operations.md)。

<details>
<summary>适用环境与验证范围</summary>
<p>时间表示、日程与上下文的区分可跨平台使用；后面的系统检查命令面向 Linux/systemd。chrony 选项核对官方 4.8 手册，实际安装版本与编译选项仍须确认。Ubuntu 24.04 的包版本、unit 名和配置路径可能不同。可选探测需要已有工具；缺失时记录未知，不为了只读检查替换时间服务。</p>
<p>本页是排障与方案参考。仓库验证覆盖来源核对、命令静态语法和页面链接；没有连接读者的 VPS，没有验证任何商家或上游的封端口政策，也没有执行改钟。</p>
</details>

## 先读哪一段

| 眼前的问题 | 入口 |
| --- | --- |
| VPS 用 UTC，对话或界面用本地时间，怎样配合？ | [UTC、时区与本地显示](#utc时区与本地显示) |
| hook 告诉了 agent 当前时间，长会话和恢复后还准确吗？ | [给 agent 注入时间](#给-agent-注入时间) |
| 每天九点、每隔一天和超时三十秒有什么区别？ | [定时触发与经过时长](#定时触发与经过时长) |
| 两台机器的日志顺序对不上 | [跨机器日志的时间](#跨机器日志的时间) |
| `kvm-clock` 在运行，是否可以不管 NTP？ | [时钟源与校时服务](#时钟源与校时服务) |
| `synchronized: no`，想知道现在到底准不准 | [只读检查时间服务](#只读检查时间服务) |
| UDP 123 不通、一直没有 NTP 回包 | [区分 UDP 123 的请求与回包](#区分-udp-123-的请求与回包) |
| 商家确认拦截，想找可用的备用办法 | [按现有条件选择方案](#按现有条件选择方案) |
| 只剩 HTTP/HTTPS 能访问 | [HTTP 时间只能粗验](#http-时间只能粗验) |

## UTC、时区与本地显示

系统钟表示当前时刻，时区规则把这个时刻转换成人看到的日期与钟点。服务器使用 UTC，界面按用户时区显示，是便于跨机器核对的一种安排；两边不需要显示同样的钟点。下面是同一个合成时刻的两种表示：

| 用途 | 时间 |
| --- | --- |
| 机器之间交换的 UTC 时间戳 | `2026-01-15T16:30:00Z` |
| 按 `Asia/Shanghai` 展示给用户 | `2026-01-16T00:30:00+08:00` |

RFC 3339 的数值偏移按“本地时间减 UTC”定义。`+08:00` 已足够解释这一次时间戳与 UTC 的关系；`Asia/Shanghai` 这样的 IANA 时区名还表示一套日期相关的规则。跨夏令时、旅行或计算未来当地时间时，应保留时区意图，不能把某次偏移当成所有日期的规则。用户时区来自明确设置或当前约定，不能从 VPS 所在地区推断。[RFC 3339](https://www.rfc-editor.org/rfc/rfc3339.html)、[RFC 9557 §1.2](https://www.rfc-editor.org/rfc/rfc9557.html#section-1.2)

本例中用户的“今天”已经进入 1 月 16 日，UTC 日期仍是 1 月 15 日。UTC 的显示方式和时钟是否准确是两件检查事项。把系统时区设为 UTC 不会自动启用校时；反过来，差八小时的两个显示也未必存在时钟误差。先把带偏移的时间换算到同一基准，再比较。

## 给 agent 注入时间

时间 hook 为模型提供一份带生成时刻的上下文。它有助于解释“今天”“今晚”等词，机器的持续校时仍由系统负责。以下 JSON 是可移植的字段示例，不要求使用某个 harness 的 hook 格式：

```json
{
  "generated_at_utc": "2026-01-15T16:30:00Z",
  "user_local_time": "2026-01-16T00:30:00+08:00",
  "user_timezone": "Asia/Shanghai",
  "generated_by": "example-session-start-hook",
  "refresh_policy": "session_start_only"
}
```

从一次取样生成 UTC 与本地表示，避免两次独立读钟造成不必要的差异。`generated_by` 标识生成组件；另在私有运行记录中确认它在哪台机器取样，不能据此证明目标 VPS 已校时。`refresh_policy` 只填写实际执行的策略。用户的 IANA 时区未知时保留未知，不能只凭 `+08:00` 反推出一个地区。

只有 session-start hook 的会话会逐渐持有旧时间；恢复会话、跨日期长任务，以及准备解释一个新的相对截止时间时，重新取样并明确参照时刻与用户时区。已确定的截止时刻保留原参照，恢复时检查它是否过期；不能把旧指令“30 分钟后”重新向后推 30 分钟。具体触发点与 hook 是否真的运行，要按当前 harness 验证。旧消息的发送时间仍保留为事件时间，不能用新生成的 hook 时间覆盖。

把“明早九点”转成具体日期、时区和触发规则后，再交给实际调度器。调度器使用哪个时区，要查它的配置；模型收到了本地时间，并不会自动改变 cron、systemd timer 或远端服务的时间约定。

## 定时触发与经过时长

| 想表达的需求 | 需要保留的语义 | 验收重点 |
| --- | --- | --- |
| 每天用户当地九点 | 当地日历时间与 IANA 时区 | 夏令时、旅行后是否仍跟随原地区、下一次触发时刻 |
| 从某次开始每隔 24 小时 | 起点、间隔，以及挂起/重启处理 | 不假定始终落在同一个当地钟点；漏跑是否补跑 |
| 一次请求等待 30 秒 | 同一运行环境内的经过时长 | 使用合适的单调时钟/超时 API，明确是否计入睡眠 |

当地时间在夏令时切换附近可能不存在，也可能对应两个时刻。日历标准对这类情况有自己的规则，但 cron、systemd 与云调度器不能互相代替；按实际实现核对。定时任务还需约定上次未完成时怎么处理、补跑多少次，以及如何避免重复副作用。[RFC 5545](https://www.rfc-editor.org/rfc/rfc5545.html)

Linux 的 `CLOCK_REALTIME` 会受到系统改钟影响；`CLOCK_MONOTONIC` 不随墙上时间的跳变倒退，但不计入系统挂起时间，`CLOCK_BOOTTIME` 则计入。不同机器或不同启动的单调时钟数值没有通用的可比较起点。日志中的日历时刻、进程内的耗时、跨重启的截止日期，应分别选用适合的表示与恢复规则。[clock_gettime(3)](https://man7.org/linux/man-pages/man3/clock_gettime.3.html)

## 跨机器日志的时间

区分事件发生时的 `event_time` 和采集端看到它的 `observed_time`：旧任务的日志可能在重连以后才到达。OpenTelemetry 的日志数据模型也分别定义了 `Timestamp` 与 `ObservedTimestamp`；这里只借用这一语义，无需为几台机器立即部署整套采集系统。[OpenTelemetry Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/)

跨机器记录保留带偏移的事件时间、来源与 job/request 标识。原时间未知时明确写未知，另记采集时间；不要偷偷按接收机器的时区补齐历史时间。混有不同偏移或精度的时间字符串应先解析成时刻，再排序；采集时间减事件时间还可能包含两台机器的钟差，不能直接当成纯网络延迟。[RFC 3339 §5.1](https://www.rfc-editor.org/rfc/rfc3339.html#section-5.1)

排序时结合请求与响应关系、任务序号和状态记录：时钟偏差、网络延迟与缓存都可能让显示顺序不同于实际过程。接手任务时查[原作业的状态](multi-machine-operations.md#断线超时与原任务恢复)，不能只凭“最后一条看起来更新的聊天消息”判断完成。

## 时钟源与校时服务

机器需要解决两个问题：时间怎样向前走；当前这个读数与 UTC 相差多少。Linux 的 clocksource 为内核计时提供基础，chrony 等时间服务根据外部参考估算误差并校准。时区只控制显示方式；把 UTC 改成 Asia/Shanghai 不会修好错误的绝对时间。

`kvm-clock` 是 KVM 的半虚拟化计时机制。Linux KVM 文档分别定义了宿主提供的单调时间信息和 wall-clock 信息；后者仅保证在 guest 写入相应 MSR 时更新。**看到 `kvm-clock`，无法推出 guest 的 UTC 一直被宿主持续校准，更无法保证今后永远准确。** 宿主已经使用 NTP、guest 的启动读数正确，也不能代替 guest 当前校时状态的证据。[Linux KVM MSR 文档](https://docs.kernel.org/virt/kvm/x86/msr.html)

服务商可能另外使用 guest agent、虚拟 PTP、启动/恢复事件校时或其他机制。这些需要服务商说明及当前实例证据；是否安装 `qemu-guest-agent` 也不能单独决定答案。不要仅为消除一个红字去更换内核 clocksource。

| 观察 | 可以支持的结论 | 仍需核实 |
| --- | --- | --- |
| clocksource 为 `kvm-clock` | 内核正在使用该计时源 | 哪个机制校准 guest UTC、最近是否成功 |
| NTP service 为 active/enabled | 某个时间服务在运行或已启用 | 是否有可用 source、近期误差与样本时间 |
| `NTPSynchronized=no` | 内核没有报告已同步 | 原因、当前偏差、其他同步机制 |
| 两个界面显示同一秒 | 那次粗略比较未见明显差异 | 取样时刻、传输耗时、精度和长期漂移 |

`NTPSynchronized` 来自内核的同步状态，`NTP` 属性表示网络校时服务是否启用；这些字段都没有独立测量你与标准时间的误差。不能把 `no` 简化成“只是没走 NTP，可以忽略”。[systemd timedate1 接口定义](https://github.com/systemd/systemd/blob/main/man/org.freedesktop.timedate1.xml)

## 只读检查时间服务

**运行位置：待检查的 Linux VPS；只读。**

```sh
date -u '+%Y-%m-%dT%H:%M:%SZ'
timedatectl status
timedatectl show -p CanNTP -p NTP -p NTPSynchronized
cat /sys/devices/system/clocksource/clocksource0/current_clocksource
systemctl status systemd-timesyncd.service chrony.service chronyd.service --no-pager
```

这些 unit 名列出常见候选，正常系统通常只使用其中一种。某个 unit 或 sysfs 文件不存在时保留这条信息，不要求把它们全部装上。若运行在普通 Linux 容器内，先确认宿主：time namespace 不虚拟化 `CLOCK_REALTIME`；不要给容器增加 `CAP_SYS_TIME` 或 privileged 来单独“修钟”。[Linux time_namespaces(7)](https://man7.org/linux/man-pages/man7/time_namespaces.7.html)

**使用 systemd-timesyncd 时，在同一 VPS 读取：**

```sh
timedatectl timesync-status
journalctl -b -u systemd-timesyncd.service -n 60 --no-pager
```

**使用 chrony 时，在同一 VPS 读取：**

```sh
chronyc -n tracking
chronyc -n sources -v
```

timesyncd 的命令无法报告 chrony 的来源详情。chrony 的 `*` 表示当前选择的 source；同时看参考时间、offset、root delay/dispersion 与 leap status。`Reach` 持续为 `0` 是近期没有有效响应的线索；一次 `377` 也只说明近期响应情况。没有选中 source、输出过期或权限不足，都要如实保留，不能从“进程 active”推断已校准。[chronyc 手册](https://chrony-project.org/doc/4.8/chronyc.html)

先查看当前配置指向的实际服务器、DNS 解析及日志，再决定是否需要下一节的有限探测。不要并行启动多个会修改系统时间的守护进程。

## 区分 UDP 123 的请求与回包

“123 被封”必须带上协议、方向、两端地址和端口。普通 NTP 客户端向服务器的 **UDP 123** 发请求；回复返回客户端实际使用的源端口。chrony 默认会为客户端请求选择随机源端口。[chrony acquisitionport](https://chrony-project.org/doc/4.8/chrony.conf.html#acquisitionport)

| 被限制的实际流量 | 对客户端校时的含义 |
| --- | --- |
| 外部主动访问本机 UDP 123 | 通常限制本机对外授时；未必妨碍随机源端口的客户端请求 |
| 本机发往远端目的 UDP 123 | 公共 NTP 请求可能出不去 |
| 来自远端源 UDP 123 的回复 | 请求能发出，回包仍可能被丢弃 |
| 只允许一个固定本地源端口 | 需核对客户端实际端口及完整往返规则 |
| 无状态 ACL 未允许回程目的端口 | 出站规则正确也可能收不到回复 |

在有状态防火墙上，允许必要的出站请求及其关联回复，通常无需向全网开放本机 UDP 123。规则由云安全组、主机防火墙和上游共同决定。改 `acquisitionport` 只改变客户端源端口，不能修好远端目的 123 被拦的问题。

**可选的一次探测：在该 VPS 的普通用户会话运行，仅限已经安装兼容 chronyd，且已确认可访问的时间服务器。** 将文档 IP `192.0.2.123` 替换为选定服务器的实际 IPv4；一次只查一个明确目标。

```sh
chronyd -Q -t 10 'server 192.0.2.123 iburst maxsamples 1'
```

大写 `-Q` 只打印偏差，不校准时钟；小写 `-q` 会改钟。命令行已提供完整 directive，此次不读取默认 chrony 配置，`-t 10` 限制等待时间；无需先停止现有校时服务。未收到有效测量时应记录失败。成功只支持“这次到该服务器的 NTP 交换及偏差估计可用”，普通未认证 NTP 的单个样本不构成可信 UTC 或长期同步保证。[chronyd 手册](https://chrony-project.org/doc/4.8/chronyd.html)

若仍需区分“未发请求”与“未见回包”，且已经获准读取网络元数据，可在另一个 VPS 会话启动下面的有限观察，再做一次上述查询：

```sh
sudo timeout 15s tcpdump -ni any -nn -c 12 \
  'udp and host 192.0.2.123 and port 123'
```

需要已有 GNU `timeout` 与 tcpdump；替换为同一个准确目标 IP。这里最多观察 15 秒或 12 个包，只输出必要摘要，不写 pcap，不输出原始载荷。到时退出可为 `124`。没有请求可能是未触发轮询、DNS/地址或观察接口不对；有请求无回复只能定位到“本机观察点未见回包”，还不能认定是哪家上游拦截。收到包但 source 不被采用，还需查协议有效性、source 状态和客户端日志。[tcpdump 手册](https://www.tcpdump.org/manpages/tcpdump.1.html)、[GNU timeout](https://www.gnu.org/software/coreutils/manual/html_node/timeout-invocation.html)

`curl telnet://host:123` 测的是 TCP，无法验证 UDP NTP。`nc -u` 没报错也不等于服务端回了合法 NTP 数据。不要用这些结果给商家或运营商下结论；跨节点对照和客服确认都要保留适用地址与时间。

## 按现有条件选择方案

按以下顺序查找能持续工作的路径。只采用符合当前机器条件的一条；不需要把所有组件都装上。

| 当前条件 | 推荐方向 | 落地前确认 |
| --- | --- | --- |
| 商家提供内网或链路本地 NTP/PTP | 使用该实例支持的官方时间源 | 适用机型、地址、guest 配置、维护责任、如何观察失联 |
| 只是一组服务器或某个地址族失败 | 在现有客户端调整到允许使用且已验证的 source | 实际往返、DNS、IPv4/IPv6 和 source 新鲜度 |
| 你已有能可靠校时的第二台 VPS | 通过可达的受控路径向它查询 NTP | 第二台确实提供服务、已同步、限制来源；被限制的路径是否仍经过 UDP 123 |
| 有现成可用的私有网络，公网 NTP 被拦 | 在私有网络内访问授时节点 | 两端在线、ACL、服务监听和封装路径；实际测量延迟与抖动 |
| 只限制目的 UDP 123，另一个 UDP 端口获准使用 | 自己控制的两端配置非标准 NTP 端口 | 服务端也监听该端口；改变客户端端口参数不会改变公共服务器 |
| 仅 HTTP/HTTPS 可达，暂无稳定授时路径 | 先做粗验与有条件的临时恢复，再补长期方案 | 参考是否可信、误差容忍度、持续失联是否可见 |

**EC2 有专用路径，但不能照搬给任意 VPS。** AWS 官方提供实例内可达的 Amazon Time Sync 地址 `169.254.169.123`；IPv6 `fd00:ec2::123` 有 Nitro 条件。是否还能用直接 PTP 硬件时钟，按实例支持列表核对。普通 VPS 无法因为“底层可能来自亚马逊”就使用 EC2 链路本地地址。[AWS EC2 时间配置](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configure-ec2-ntp.html)

**“跟我的 Mac 对时”要先具备服务和路径。** Mac 的自动时间设置表示它可以作为客户端，并未证明它向 VPS 提供 NTP。Mac 还可能睡眠、切换网络或处在 NAT 后。已有常驻授时节点通常更适合；不要仅为备用校时暴露家中 UDP 123。普通 SSH `-L` 转发 TCP，无法直接转发这里的 UDP NTP。

私有网络把可达性问题转为已有受控路径的一部分，依然需要测量和维护；它也增加了依赖。两台 VPS 都失去外部参考时，互相回答相同时间只能维持一致，无法证明绝对时间准确。自建 relay 不使用 `local` 模式把失去同步的节点伪装为可靠源，不为一个客户端开放全网授时。[chrony FAQ](https://chrony-project.org/faq.html)

### NTS 与 TCP 的区别

标准 chrony NTP 配置的 `port` 指 UDP；没有通用的“把公共 NTP 改成 TCP 123”步骤。NTS 首先通过 TLS/TCP（通常 4460）进行认证和密钥建立，之后仍使用 UDP 的 NTP 数据包授时。**只放通 TCP 4460 不能替代后续 UDP 路径。** 非标准端口或额外隧道必须有双方支持，不能靠单边改配置获得。[RFC 8915](https://www.rfc-editor.org/rfc/rfc8915.html)

`rdate` 也需要核对实现。RFC 868 定义过 TCP 37 的 Time 服务，但任意 NTP 域名未必提供它；OpenBSD 的当前 `rdate` 默认使用 SNTP。不要把网上某个 `rdate` 命令直接当成跨发行版、经过认证的备用校时法。[RFC 868](https://www.rfc-editor.org/rfc/rfc868.html)、[OpenBSD rdate](https://man.openbsd.org/rdate)

## HTTP 时间只能粗验

HTTP `Date` 表示响应消息生成时的近似时间，精度到秒；它可能来自 CDN/中间层，也可能随缓存响应返回。请求传输耗时、源站的时钟质量以及两次取样的先后都影响比较。因此“同一秒”不能写成“偏移为 0 秒，长期无影响”。[RFC 9110 §6.6.1](https://www.rfc-editor.org/rfc/rfc9110.html#section-6.6.1)

**运行位置：待检查 VPS；一次 HTTPS 粗验，不改钟。** `www.example.com` 是示例，替换为选定、可信且允许查询的 HTTPS 站点；输出只保留时间相关字段。

```sh
date -u '+%Y-%m-%dT%H:%M:%SZ'
curl --noproxy '*' --connect-timeout 3 --max-time 10 \
  --silent --show-error --head https://www.example.com/ \
  --write-out 'http_code=%{http_code} total_seconds=%{time_total}\n' |
  awk 'tolower($0) ~ /^(date:|age:|http_code=)/ { print }'
date -u '+%Y-%m-%dT%H:%M:%SZ'
```

对照请求前后本机 UTC、Date、Age、HTTP 状态和耗时。Date 缺失、缓存较旧或请求失败时，记为无法比较；这条管道的最终退出码是 awk 的状态，不可以仅凭退出码零宣布 HTTPS 成功。`--noproxy '*'` 明确选择直连；必须使用代理的环境要另记那条实际路径。[curl 手册](https://curl.se/docs/manpage.html)

TLS 验证失败可能与时间有关，也可能来自证书链、域名、代理或服务端配置。保留错误并使用独立可信的恢复依据；不要通过加 `-k` 后把不验证证书的返回当成可信校时。不要把这段输出直接接到 `date -s`。

htpdate 可以作为进一步研究的 HTTP 校时工具，但先核对具体版本和模式。上游 2.0.2 手册中 `-q` 才是只查询，`-c` 启用服务器证书验证（默认不验证），`-t` 会关闭大偏移合理性检查，并非超时参数。不能把来历不明的 cron 片段当成“只告警、不改钟”。[htpdate 上游手册](https://github.com/twekkel/htpdate/blob/master/htpdate.8)

## 怎样算解决

验收记录应写清三件事：当前观测到的偏差及其测量限制；负责长期校准的一个机制；失去参考后怎样发现和恢复。按正常轮询观察更新过的样本和误差趋势；若没有经历重启/迁移，就保留这两个未验证项。不能为验证而随意重启有业务的机器。

如果已确认偏差较大，先识别定时任务、日志、数据库与时间相关认证的影响，再由 owner 决定渐进调整还是在维护窗口 step。把一次手工改准和长期自动同步分别验收。

普通个人服务的误差阈值和检查频率由实际用途决定；每周检查一次没有普遍适用的依据。HTTPS 粗验适合发现明显异常，要求更小误差时使用真正的授时客户端和适当 source。现有 Health 工具只采集资源，不测量 NTP 偏差，也没有自动增加这类告警。

向服务商咨询时，可以带上以下脱敏问题；真实地址和抓包元数据留在私有支持渠道：

```text
系统与当前时间客户端：
观察窗口、目标时间服务器、IPv4/IPv6：
实际请求源端口、目的 UDP 123、是否收到有效回复：
本机和云规则已核实的范围：
请确认限制的是哪一方向、哪个端口，是否对本实例生效。
是否有本实例可用的内网 NTP/PTP 或 guest 校时机制？
该机制在启动、持续运行、恢复与热迁移时分别怎样工作？
推荐的 guest 配置、校时状态和失联观察方式是什么？
```

## 来源与维护

查阅日期：**2026-10-05**。一手来源随具体机制链接；chrony 4.8 与 htpdate 2.0.2 是本次选项核对版本，不声称所有发行版都提供相同版本。社区讨论只用来提出问题，不能证明某家服务商或运营商的网络政策。

**想一想：UDP 收到回复、`kvm-clock` 在工作、HTTP Date 相同，这三条能证明持续自动校时吗？**

<details>
<summary>查看答案</summary>
<p>还不能。需确认有效且足够新鲜的参考样本、负责校准系统钟的机制，以及后续样本与误差趋势；三条观察分别属于网络、底层计时和一次粗略比较。</p>
</details>
