# 定时任务：日历、补跑与并发边界

[返回首页](../README.md) · [时间与时区](time-synchronization.md) · [日常运维](03-operations.md) · [跨机器运维](multi-machine-operations.md) · [给 agent 的调度工单](../agents/scheduled-job.md)

## 这一页帮你做什么

你想让某件事“每天自动跑一次”，但机器可能关机、可能错过时间、也可能上一次还没跑完下一次又来了。这篇讲清楚日历触发与间隔触发的区别、cron 与 systemd timer 各自的行为边界、补跑（catch-up）和并发（overlap）到底由谁决定，以及跨机器时锁、幂等、去重这些概念怎么落到可执行的判断上。目标是让你能判断自己的调度配置**在错过、重叠、跨时区时**会发生什么，而不是抄一段看不懂的 cron。

调度语义由具体实现决定。**cron 与 systemd timer 不能互相代替**，同一个 `OnCalendar=` 表达式在不同 systemd 版本、不同时区设置下也要按实际核对。

<details>
<summary>适用环境与验证范围</summary>
<p>以 Ubuntu 24.04 + systemd 为主，兼讲 cron 的通用行为。时间与时区基础、UTC/本地显示见<a href="time-synchronization.md">时间专题</a>。</p>
<p>本文的 timer/service 配置只作<strong>阅读用的合成示例，不激活、不安装</strong>。仓库核对的是文档、静态语法与链接；未在真实主机上创建 timer、触发任务或验证补跑。</p>
</details>

## 先读哪一段

| 眼前的问题 | 入口 |
| --- | --- |
| “每天九点”和“每隔 24 小时”有什么不同？ | [日历触发与间隔触发](#日历触发与间隔触发) |
| 机器关机时错过的任务，开机后会不会补跑？ | [Persistent 只作用 OnCalendar](#persistent-只作用-oncalendar) |
| 上一次还没跑完，下一次又来了怎么办？ | [同 service 仍 active 时 timer 不重启它](#同-service-仍-active-时-timer-不重启它) |
| 多台机器会不会重复执行同一件事？ | [跨机器：锁、幂等与去重](#跨机器锁幂等与去重) |
| 一份可读的 timer/service 长什么样？ | [合成配置示例](#合成配置示例只展示不激活) |
| 怎么只读检查任务状态和产物？ | [只读检查](#只读检查) |

## 日历触发与间隔触发

“每隔一段时间”和“每个日历钟点”是两种触发语义，写错会得到不同的补跑和夏令时行为：

| 需求 | 语义 | 保留什么 | 注意 |
| --- | --- | --- | --- |
| 每天用户当地 09:00 | 当地日历时间 | IANA 时区 + 日历规则 | 夏令时附近可能不存在或出现两次，按实现规则处理 |
| 从某次开始每隔 24 小时 | 起点 + 固定间隔 | 起点、间隔 | 不保证始终落在同一当地钟点 |
| 每 15 分钟 | 固定间隔 | 间隔 | 与“每次整点后的第 0/15/30/45 分”不完全相同 |

systemd timer 用 `OnCalendar=` 表达日历触发（如 `*-*-* 09:00:00`），用 `OnUnitActiveSec=`/`OnBootSec=` 等表达基于其他事件往后算的相对触发。cron 的字段是日历式的（每天某个钟点），传统 cron 没有“从上次运行起间隔 N 分钟”这种语义。日历规则在夏令时切换附近可能产生**不存在**或**重复**的当地时间，各调度器有自己的取舍，不能凭直觉推断。[systemd.time(7)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man7/systemd.time.7.html)

**时区直接写在日历表达式末尾。** systemd 的 `OnCalendar=` 支持在末尾附加时区，例如 `OnCalendar=*-*-* 09:00:00 Asia/Shanghai` 或 `… UTC`，即把该日历规则锚定到该 IANA 时区；**timer 没有 `Timezone=` 选项**。不写时区时按系统时区解释。[systemd.time(7)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man7/systemd.time.7.html)

> [!NOTE]
> **停下检查点：调度器用的时区，是它自己的配置。**
> 你的模型或界面收到了用户本地时间，并不会自动改变 cron 或 systemd timer 的时区。systemd timer 把时区**附在 `OnCalendar=` 表达式末尾**（没有 `Timezone=` 选项），不写则按系统时区；`systemd-analyze calendar` 能把你写的表达式解析成**接下来几次具体触发时刻**，用它确认而不是靠想象。[systemd.time(7)](https://manpages.ubuntu.com/manpages/noble/man7/systemd.time.7.html)

### 调度精度：`AccuracySec` 与 `RandomizedDelaySec`

触发时刻**不是**整点即到即执行的保证：

- `AccuracySec=` 默认 `1min`：systemd 允许把触发安排在目标时刻后的这段窗口内，以便合并唤醒省电。要更准，就把它设小（代价是更频繁唤醒）。
- `RandomizedDelaySec=` 会给触发加一个随机延迟，用于打散同时刻任务；`Persistent=` 的补跑也仍受它影响。

所以“配置写了 09:00:00”不等于“09:00:00 精确启动”。验收时看**实际触发时间**，而不是假设零误差。[systemd.timer(5)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man5/systemd.timer.5.html)

## Persistent 只作用 OnCalendar

这是最容易误解的一条：systemd timer 的 `Persistent=true` 只在**该 timer 由 `OnCalendar=` 触发时**才生效。它记录上一次触发时间；若 timer 在 inactive 期间至少漏过一次触发，则**在下一次激活时安排一次触发**（不是把漏掉的每一次都补上），且仍受 `RandomizedDelaySec=` 影响，**不一定立即**完成补跑。

它**不是**：

- 不是“错过多少次就补跑多少次”。timer 只在激活时安排**一次**补跑，**业务上要补哪些日期由任务自己决定**；把漏掉的历史逐次补齐得任务自己设计。
- 不是对所有触发类型都生效。对 `OnBootSec=`、`OnUnitActiveSec=` 这类相对触发，`Persistent=` 没有“补跑”语义。
- 不是自动的幂等保证。补跑仍可能与直接调用底层程序、其他 unit 或其他机器的执行重叠；若同 manager 的相关 service 已在跑，补跑同样受“不新起实例”的边界约束（见下节）。

[systemd.timer(5)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man5/systemd.timer.5.html)、[systemd.timer 源文档](https://github.com/systemd/systemd/blob/main/man/systemd.timer.xml)

因此“关机三天，开机后只安排一次补跑”是常见行为，**想逐日补齐就得自己在任务里设计**（例如按“缺失的日期”自己判断并逐日处理），而不是指望 `Persistent=`。

## 同 service 仍 active 时 timer 不重启它

一个 timer 触发的是对应的 service。若同一个 unit 的 service **已经在运行**（active 或 activating），systemd 默认**不会**再启动一个新实例去覆盖它——timer 到了点也不会“重启”这个正在跑的服务，`systemctl start` 同一 unit 也不会制造并发。这可以避免简单的自我重叠，但要注意：

1. **真正的旁路是“绕开这个 unit”的调用。** 直接运行底层程序、另一个 service 或模板 instance（`@` 名字）、另一个 manager、另一台机器，都会绕开这个边界造成重叠。
2. **长时间运行的任务会“吃掉”后续触发。** 如果每次运行都长于间隔，那么运行期间的后续触发被跳过，实际频率低于你的间隔。
3. **`RemainAfterExit=true` 会让 service 长期保持 active。** 这类 oneshot 服务一旦“完成”也一直算 active，后续触发按上面规则就不再新起实例——要确认这是否符合你的意图。

想要更细的重叠控制，可以显式设置服务的启动/运行约束；例如对不该并发的任务，用应用层自己的锁（见下节），而不是假设调度器替你解决了所有重复。

## 跨机器：锁、幂等与去重

先别默认上“分布式锁”。更实在的顺序是：**先确定一个真实的调度 owner**，让任务状态可查询（job/unit 状态、日志、已完成标记）——这本身就消除了大部分重复。只有当**多台机器确实要共享写同一份数据**时，才需要并发控制，并优先用应用**已支持的事务或唯一约束**，而不是自造锁协议。

需要判断的四个概念：

| 概念 | 回答的问题 | 常见实现 |
| --- | --- | --- |
| 互斥锁 | 同一时刻只允许一个执行 | 文件锁 `flock`、advisory lock |
| 幂等 | 同一操作执行多次，结果与执行一次相同 | 任务自身设计（upsert、带 job id 去重） |
| 去重键 | 用唯一标识判断“这次是不是已经做过” | 业务表唯一约束、已完成标记 |
| 租约/心跳 | 判断某执行者是否还活着，避免死锁 | 带超时的锁或租约表 |

`flock` 提供的是 **advisory** 锁：只有同样去申请这把锁的进程才会被挡住；不申请锁的进程照样能执行。在**同一台机器的普通文件系统**上，它适合“让同一脚本的多个实例互斥”，但**不能阻止**别人绕过它直接跑底层命令。在 **NFS/SMB 等网络文件系统**上，锁行为取决于协议、挂载选项与内核版本；**仅仅“共享一个路径”并不证明跨机器互斥真的成立**，要按实际文件系统核实。[flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html)

下面只是**展示用法**，本仓库不执行它；它本身是**写文件、取锁的动作**（不是只读检查）：

```sh
# 展示用：同一主机普通文件系统上，让本脚本的并发实例互斥
exec 9>/var/lock/example-job.lock
flock -n 9 || { echo "another run in progress"; exit 0; }
```

更稳妥的跨机器去重通常落在**任务自己维护的状态**上（唯一键、已完成标记、带执行者 id 的租约），或直接用数据库事务/唯一约束，而不是靠文件锁的巧合。

### 结果未知时，先查原任务

任务超时、连接断开或换了一个 harness 时，**不要直接重发同一份写任务**。先按[原任务恢复](multi-machine-operations.md#断线超时与原任务恢复)的顺序：查原目标的 job/unit 状态与结果 → 仍在运行就继续观察 → 已结束就读结果并验收产物 → 确实无法判断就记录待定位，而不是再建一份。对发信、付款、迁移、外部 API 这类有副作用的动作，幂等键与操作 id 要在提交前就保留下来。

## 合成配置示例（只展示，不激活）

**以下 unit 只作阅读示例，不要在未核实的主机上安装或启用。** 目标是一个“每天当地 09:00 运行一次、错过则尽量补一次、单次不并发”的作业。文件名与路径都是占位符。

`example-job.service`（`Type=oneshot`，跑完即退出）：

```ini
[Unit]
Description=Example daily job (synthetic)

[Service]
Type=oneshot
User=example
Group=example
WorkingDirectory=/opt/example-job
ExecStart=/usr/local/bin/example-job --batch daily
```

`example-job.timer`（触发上面的 service）：

```ini
[Unit]
Description=Run example daily job (synthetic)

[Timer]
OnCalendar=*-*-* 09:00:00 Asia/Shanghai
Persistent=true
# AccuracySec=1min 是默认值，示例显式写出以便看清触发精度
AccuracySec=1min
Unit=example-job.service

[Install]
WantedBy=timers.target
```

阅读要点：

- `Type=oneshot` 适合“跑一段就退出”的批处理；`Persistent=true` 只在这里因为用了 `OnCalendar=` 才有补跑含义。
- 时区附在表达式末尾 `… Asia/Shanghai`（这是合成的示例时区，不代表读者实际设置）。不写时区则按系统时区。
- `AccuracySec=1min` 是默认，意味着允许在目标时刻后这段窗口内触发，不保证 09:00:00 精确启动。
- timer 触发 service；**timer 自身不会因为你手动 `systemctl start example-job.service` 而记录**，两者状态分开看。
- `Type=oneshot` 的 `TimeoutStartSec=` **默认是禁用的**（不会自动超时）。若任务需要时间上限，要**显式设置**，并想清楚超时后如何停止、如何恢复、是否留下半成品。
- 生产里通常还要考虑失败通知，以及**别让 `ExecStart` 依赖交互式 `PATH`**（见[配置专题](configuration-and-runtime.md#shell-环境与-service-环境的差异)）。

### cron 还是 systemd timer

两者都能做日历式调度，选择看你的实际条件：

| 维度 | cron（按实现的 `crond`） | systemd timer |
| --- | --- | --- |
| 日历语义 | `分 时 日 月 周` 五字段 | `OnCalendar=` 表达式，可附时区 |
| 补跑关机错过的任务 | 传统行为**不补**（开机不追） | `Persistent=` 可在激活时安排一次 |
| 单实例/并发 | 无内建“上次未完成不启动”边界，靠 `flock` 等自理 | 同 unit 已 active 时不新起实例 |
| 与日志/状态 | 输出常走邮件/系统日志 | 走 journal，状态可由 `systemctl` 查询 |
| 安装位置 | 用户/系统 crontab 或 `/etc/cron.d` | unit + timer（system 或 user manager） |
| 依赖环境 | `crond` 给的很有限的环境，`PATH` 很短 | 由管理器给定，可用 `Environment=` |

**要按具体实现引用**：Vixie 系 cron、cronie 及其他实现的扩展不同。时间字段、环境、以及是否支持 `CRON_TZ` 都要按本机实际的 daemon、包版本与手册核对。文末的 Ubuntu manpage 入口返回 cronie/crond 内容，不能据此推断另一实现的行为。

一个**合成** cron 表达式示例（只解释、不安装）：`0 9 * * *` 表示“每天 09:00”，按 `crond` 所在时区解释——具体是哪个时区、能否改，取决于实现。若要跨机器一致，务必先确认每台机器 `crond` 的时区来源。

## 只读检查

**运行位置：待检查的 Linux VPS；只读。** unit 名替换成已确认的目标。`systemd-analyze calendar` 只解析表达式、不触发任务。

```sh
# 这些表达式各自接下来几次会在什么时候触发
systemd-analyze calendar '*-*-* 09:00:00 Asia/Shanghai'
systemd-analyze calendar --iterations=5 '*-*-* 09:00:00 Asia/Shanghai'

# timer 与 service 的状态（active/enabled 分开看）
systemctl list-timers 'example-job*' --all
systemctl status example-job.timer example-job.service --no-pager
systemctl show example-job.timer -p NextElapseUSecRealtime -p LastTriggerUSec -p Persistent -p Unit -p Result
systemctl show example-job.service -p ActiveState -p SubState -p Result -p ExecMainStatus -p NRestarts

# 任务日志：上次什么时候跑、结果如何
sudo journalctl -u example-job.service -n 80 --no-pager
```

用 **cron** 时，对应的只读检查是查看本机实际的 `crond` 与 crontab（**只读**，不编辑）：

```sh
# 本机 cron 实现与状态（按发行版/实现替换；只读）
command -v cron crond
systemctl status cron.service crond.service --no-pager
crontab -l                           # 当前用户的 crontab；加 sudo 会查 root
ls -l /etc/cron.d/                    # 系统 drop-in（只列目录）
```

不同实现的 unit 名与目录不同，缺服务/无权限时保留这条信息，不要把 cron 当成“没有就是没跑”，也不要为检查去安装另一个 cron。

`systemctl list-timers` 的 `NEXT`/`LAST` 列是最直接的“下次何时、上次何时”证据；`Result=success` 且 `ExecMainStatus=0` 只说明**进程级**成功，不等于业务产物正确。若任务会写文件、上传结果或更新数据库，还要单独验收产物。

> [!TIP]
> **先记住这一点：调度器只负责“发起”，不负责“业务正确”。**
> timer 到了点、service 返回 0，只证明命令被运行过。任务记录（job id、起止时间、处理条数、错误）和产物（生成的文件、数据库行、外部系统状态）要单独检查。两者一致，才算这次调度真正完成。

### 任务记录与产物验收

一个可审查的验收清单：

1. **时间**：`list-timers` 的 `LAST`/`NEXT`、日志里的起止时间，与你的时区预期一致。
2. **结果**：`Result`、`ExecMainStatus`、业务日志中的成功/失败标记。
3. **产物**：任务该产出的文件/记录/外部状态实际存在且内容合理，而不是只有退出码。
4. **重复**：检查是否存在同一逻辑单元被处理两次（去重键、计数）。
5. **补跑**：若发生过关机/错过，确认是补了一次还是被逐次补齐，与你的设计一致。
6. **并发**：若上次运行时间接近间隔，确认没有非预期重叠。

## 变更与恢复边界

调度相关的变更（新增/修改 timer、改 cron、改时区）会影响“什么时候、会不会、重复几次”执行，属于有副作用操作：

- 改动前备份原 unit / crontab，记录旧表达式和它的实际触发时刻（用 `systemd-analyze calendar` 留证）。
- **改完要按你所用版本核实实际效果**：`daemon-reload` 本身只是让管理器重读 unit 文件，是否重新计算、何时重算下次触发、以及 timer 是否需要单独重启，都按版本确认；不要假定它一定让 NEXT 变新。
- **`Persistent=true` 可能立刻触发一次**：若改动让 timer 重新激活且期间有错过，补跑可能随即发生。改之前先查**目标 service 当前是否在跑**（`systemctl is-active`），避免在任务运行中制造意外。
- 停用一个 timer 用 `systemctl disable --now example-job.timer`，它会同时停掉计时；但**已经在跑的 service 未必随之停止**，需要单独处理。
- 回退：恢复备份的 unit、`daemon-reload`，用 `systemctl list-timers` 核对 `NEXT`/`LAST` 是否回到预期（以实际输出为准）。
- 对有外部副作用的任务（发信、付款、迁移），变更和回退都要考虑**幂等**：重放一次是否安全。

**提醒：** 本文不提供“立即试跑一次”的写操作建议，也不会替你试跑。如需试跑，应另有一次明确的授权，并先确认任务的幂等/去重能力。

## 怎样算解决

一篇验收记录应能回答：

- **触发语义**：日历还是间隔？按哪个时区？我写下的表达式解析出来是哪几次时刻？
- **错过处理**：关机/停机错过的任务，激活时是否安排一次补跑？业务上要补哪些日期由任务自己决定，是否逐次补齐要单独设计。
- **并发边界**：同 service 在跑时新的触发会怎样？有哪些调用者可能绕过这个约束？
- **结果归属**：任务记录与产物在哪里？除退出码外，怎么证明业务正确？

缺少真实触发、补跑或跨机器实验时，明确写“未验证”，不把“配置看起来对”写成“已验证会按预期补跑”。

## 来源与维护

查阅日期：**2026-10-05**。systemd 示例按 Ubuntu 24.04 的 systemd 255.4 手册核对。本仓库未安装/启用 timer，未在真实主机触发调度或验证补跑；配置解析与真实触发分别验收。

- [systemd.timer(5)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man5/systemd.timer.5.html)（systemd 255.4）：已 active 的同一 unit 到点**不会**被重启或产生新实例；`Persistent=` 只对 `OnCalendar=` 生效，timer 激活时若 inactive 期间至少漏过一次则安排**一次**触发，仍受 `RandomizedDelaySec=` 影响；`AccuracySec=` 默认 `1min`，触发不是精确 `09:00:00` 保证。
- [systemd.time(7)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man7/systemd.time.7.html)：时区**直接附在日历表达式末尾**（支持 IANA/UTC）；**不存在 timer 的 `Timezone=` 选项**。
- [systemd.service(5)](https://manpages.ubuntu.com/manpages/noble/man5/systemd.service.5.html)、[systemctl(1)](https://manpages.ubuntu.com/manpages/noble/man1/systemctl.1.html)、[systemd-analyze(1)](https://manpages.ubuntu.com/manpages/noble/man1/systemd-analyze.1.html)：`Type=oneshot` 的 `TimeoutStartSec` 默认禁用；`systemd-analyze calendar` 解析触发时刻。
- [cron(8)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man8/cron.8.html)：该网址实际返回的是 **cronie/crond 系**实现的内容，**不能**据此推断 Vixie 或其他 cron 的行为；引用时明确实现。
- [flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html)、[flock(1)](https://man7.org/linux/man-pages/man1/flock.1.html)：同机普通文件系统 advisory 锁；NFS/SMB 行为按协议、挂载与内核版本变，仅共享路径不证明跨机互斥。
- [时间同步专题](time-synchronization.md)：时区、UTC 与跨机器时间对应；判断“下一次何时触发”前先确认时钟与时区。

**想一想：一个 timer 设了 `Persistent=true`，机器关机三天后才开机，它会把这三天里错过的那几次都补跑吗？**

<details>
<summary>查看答案</summary>
<p>通常不会。`Persistent=` 只作用于 `OnCalendar=` 触发，错过多次一般只在启动时补跑一次，而不是逐次补齐；“逐日补齐”需要任务自己按缺失的日期处理。具体行为以所用 systemd 版本的 systemd.timer(5) 为准。</p>
</details>
