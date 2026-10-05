# 配置如何生效：来源、环境与运行版本

[返回首页](../README.md) · [日常运维](03-operations.md) · [跨机器运维](multi-machine-operations.md) · [给 agent 的配置工单](../agents/config-runtime.md)

## 这一页帮你做什么

同一台机器上，你编辑了一份配置却没生效；终端里 `which node` 指向一个版本，服务跑起来的却是另一个；`systemctl restart` 之后行为还是旧的。这篇讲清楚：一个进程实际读到的配置来自哪些层、环境变量和启动参数怎样覆盖文件、`PATH`/工作目录/运行用户在哪一层被决定，以及 source、build、install、运行进程、客户端各自的版本为什么可能不是同一个。重点是给出可核对的顺序和只读检查，而不是记住某个工具的“标准优先级”。

配置优先级没有跨工具的通用答案。**每个工具要按它当前版本的官方说明确认读取顺序**，本页只提供判断方法和检查手段。

<details>
<summary>适用环境与验证范围</summary>
<p>以 Linux/systemd 上的常驻服务为主，读的是 systemd.exec(5)、systemctl、systemd 的配置语义；macOS、桌面 GUI 或各 harness 的具体配置文件位置和优先级按其当前官方文档核实后再给命令，本页不为未核实的平台编造路径。</p>
<p>本页命令作静态说明与只读检查；仓库没有连接读者的机器，也没有运行任何服务重启、reload 或环境变更。示例文件名、路径和值都是合成占位符。</p>
</details>

## 先读哪一段

| 眼前的问题 | 入口 |
| --- | --- |
| 我改了配置文件，为什么没反应？ | [配置来自哪一层](#配置来自哪一层) |
| 终端里能跑的命令，服务里找不到 | [shell 环境与 service 环境的差异](#shell-环境与-service-环境的差异) |
| `which`、`node -v`、服务里报告的不一致 | [各层不是同一个版本](#各层不是同一个版本) |
| 改了 unit 或环境，怎样让它真正生效？ | [daemon-reload、reload 与 restart](#daemon-reloadreload-与-restart) |
| 怎么查而不打印秘密？ | [只读检查：显示配置来源而非值](#只读检查显示配置来源而非值) |
| 改坏了怎么退回来？ | [变更与恢复边界](#变更与恢复边界) |

## 配置来自哪一层

一个进程真正使用的“有效配置”，通常是多个来源按该工具自己的顺序合并或覆盖后的结果。常见的层有：

| 层 | 典型载体 | 谁决定它 |
| --- | --- | --- |
| 程序内置默认值 | 编译或发布时写死 | 程序版本与构建选项 |
| 系统级配置 | 如 `/etc/<tool>/…` | 系统管理员、包管理器 |
| 用户级配置 | 用户 home 下某个路径 | 运行该进程的用户 |
| 项目级配置 | 项目目录内某个文件 | 仓库或项目 owner |
| 环境变量 | 进程启动时继承或注入的值 | 启动它的父进程 / 服务管理器 |
| 命令行参数 | `ExecStart` 或直接调用的 argv | 启动命令行或 unit 文件 |
| 运行时/动态覆盖 | 环境、OS 变量、control socket 下发的值 | 运行时接口或控制面 |

**不要假定“层数越深、文件越新就越优先”。** 有的工具让命令行参数压过所有文件，有的让某类环境变量压过命令行，有的按目录里文件名排序逐个读取而不做覆盖，还有的明确采用“先读到的值生效”。这些都要按具体工具确认。[systemd 配置语义](https://www.freedesktop.org/software/systemd/man/latest/systemd.syntax.html)

一个具体的、有区分力的例子是 OpenSSH：`sshd_config` 对多数单值关键字采用**先读到的值生效**，Ubuntu 主配置通常在前面就 `Include /etc/ssh/sshd_config.d/*.conf`，因此“文件名数字最大就赢”是错的；`Match` 块还会按用户/来源改写结果。[Ubuntu OpenSSH](https://ubuntu.com/server/docs/openssh-server/)

### 合成案例：一份没生效的配置

假设有个自建服务 `example-web.service`，你把改动写进了 `/etc/example-web/config.d/90-tune.conf`，但重启后行为不变。可能的原因**不只一种**，要按证据排除：

1. **改的不是被读的那份。** 服务实际从 `/etc/example-web/config.toml` 读取，`config.d/` 目录根本没被加载。
2. **顺序不对。** 工具采用“先读到的值生效”：前面已经取了某个值，你这份后缀虽然大、排在后面，就不会被采用。
3. **环境变量压过文件。** `ExecStart` 或 `Environment=` 给出了一个更高优先级的开关。
4. **根本没重启到。** 服务有 loader 缓存、或多实例只重启了一个。
5. **改了但没生效成功。** 配置解析报错，服务退回默认值或上一个有效值，日志里有线索。

正确做法是先确定“服务到底从哪读、读到了什么”，而不是继续猜优先级。

## shell 环境与 service 环境的差异

你在交互 shell 里成功运行过一条命令，**不能推出服务也能运行它**。交互 shell 和服务进程拿到的是不同的环境：

| 维度 | 交互 shell | systemd service |
| --- | --- | --- |
| `PATH` | 由登录 shell 的 profile、`PATH` 扩展等拼出 | 由服务管理器给的一组默认路径，加上 unit 里显式设置的值 |
| 工作目录 | 你 `cd` 到的地方 | `WorkingDirectory=` 指定，未设时按管理器的默认 |
| 运行用户 | 你登录的账号 | system manager 通常按 `User=`/`Group=`；未设且未用动态用户时为 root，user manager 则是该用户 |
| 环境变量 | 你的 `~/.zshrc`、`export` 等 | 只继承管理器提供的，加上 `Environment=`/`EnvironmentFile=` |

systemd 对服务给出的默认 `PATH` 通常是一组固定的系统目录（例如包含 `/usr/local/sbin`、`/usr/local/bin`、`/usr/sbin`、`/usr/bin`、`/sbin`、`/bin`），它**不包含**你交互 shell 里额外追加的目录。具体默认值按发行版与 systemd 版本核对，不要照抄网上的字符串。[systemd.exec(5)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man5/systemd.exec.5.html)

因此，“命令在我的终端里能跑”只证明**那个 shell 的环境**里有它。要证明服务能用，必须在服务的真实用户、真实 `PATH`、真实 `WorkingDirectory` 下检查。

### 用绝对路径，别依赖 PATH

给服务的 `ExecStart=` 用绝对路径，可以消掉一整类“找不到命令”的问题：

```ini
[Service]
User=example
Group=example
WorkingDirectory=/opt/example-web
Environment=PATH=/usr/local/bin:/usr/bin:/bin
EnvironmentFile=-/etc/example-web/env
ExecStart=/usr/local/bin/example-web --config /etc/example-web/config.toml
```

这里 `EnvironmentFile=` 前的 `-` 表示该文件可缺失且不算失败（写系统 unit 时按你的工具语义确认这个前缀是否被支持）。`Environment=` 里的值是**明文**，unit 文件可被有权限的用户读到——**不要在这里写秘密**。

## 各层不是同一个版本

排障时经常把这几件事混成“版本不对”，但它们各自独立。下面前四层是“这份程序是什么”，第五层是“用户实际连到了哪份服务”：

| 层 | 含义 | 典型的核对方式（示例） |
| --- | --- | --- |
| source | 你手上的代码/配置副本 | `git -C <repo> status --short` 看是否有未提交改动 |
| build | 由 source 构建出的产物 | 产物路径、版本标识、对应的 source revision |
| install | 被安装到系统、服务会去调用的那份 | 安装前缀、包管理器记录、软链接指向 |
| process | 当前正在运行的那个进程 | 进程的 `exe` 指向、`MainPID`、管理器记录的启动时刻 |
| client/endpoint | 用户实际连到了哪份服务、走到哪个入口 | 一次可观察的新行为；服务端实际运行版本/endpoint（客户端自身版本另记） |

第五层要回答的是“**用户的请求真正到了哪里、跑的是哪一版**”，而不是“我本地客户端是几版”。客户端自己的版本是另一项记录，不要拿它证明服务端版本。验证时应从一个可观察的行为或入口入手（真实请求的结果、响应头/版本字段、endpoint 地址），而不是只报一个无具体身份用途的 hash。

一个常见陷阱：`which node`（或 `command -v node`）只反映**你当前 shell**的 `PATH` 里排在最前面的那个，它既不一定是服务用的，也不一定等于服务实际加载的共享库版本。语言运行时、库和容器镜像都可以各自带一份版本。

**核查顺序建议：** 先确认**进程实际加载的是哪个可执行文件和哪些库**，再回头核对 source/build/install 是否一致。用运行进程去反推哪份代码在跑，而不是假设“我改了源码 → 进程就变了”。

## system、user manager：默认身份与 `--user`

systemd 有两种管理器，检查对象必须对应到正确的一种：

| 管理器 | 管什么 | 未设 `User=` 时的默认身份 | 命令入口 |
| --- | --- | --- | --- |
| system manager（PID 1） | 系统服务、`/etc/systemd/system` 等系统 unit | **root** | `systemctl …`（默认就是 system） |
| user manager | 某个用户自己的 unit、`~/.config/systemd/user` | **就是该用户**，且不能切换到其他用户 | `systemctl --user …`，实际运行在该用户的 user manager 上 |

两点容易踩：

- `systemctl` 默认操作的是 **system** 目标。查 user unit 必须用**对应真实用户**的 `systemctl --user`（通常还要在该用户会话或 user bus 可用的前提下），否则你查的是另一套 unit。
- user manager **不能**把服务切成别的身份运行；需要以别的用户身份运行时，要用 system manager（或该用户自己的 user manager）。所以“用 `systemctl` 的结果”不能替 user unit 验收，反之亦然。

`WorkingDirectory=` 未设时，system manager 默认使用服务的根目录，user manager 默认使用该用户的 home；`RootDirectory=`/`RootImage=` 还会改变服务所见的根目录。不要跨管理器套用。[systemd.exec(5)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man5/systemd.exec.5.html)

## daemon-reload、reload 与 restart

这三个词只差几个字母，作用完全不同。下面给的是 **systemd 的语义**；其他服务管理器（含各 harness）请按各自文档确认对应概念。

| 动作 | 它做什么 | 它**不**做什么 |
| --- | --- | --- |
| `systemctl daemon-reload` | 让管理器重新读取 unit 文件与 drop-in，使新内容能被理解 | 不重启、不重新加载任何正在运行服务的业务配置 |
| `systemctl reload <svc>` | 按该 unit 支持的方式让服务重读配置 | 需要服务自己支持；**不保证无中断** |
| `systemctl restart <svc>` | 停掉再启动进程，重新读取进程属性（用户、环境、可执行文件） | 不等于业务已经健康，也不保证已正确处理完在途请求 |

关于 `reload` 的支持方式：systemd 可由 unit 的 `ExecReload=` 提供 reload 命令，服务也可通过 **notify-reload** 之类协议主动报告“已重载”；具体是否支持、是否真能无中断，取决于服务本身，**不能默认所有 reload 都无中断**。[systemd.service(5)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man5/systemd.service.5.html)

关键区别：**改了 unit 里影响“进程如何被启动”的部分（`User=`、`Environment=`、`ExecStart=`、`WorkingDirectory=`），一般需要 `restart` 才会生效**；只 `reload` 不会重建进程，也就不会应用这些属性。而 `daemon-reload` 只是让管理器看到 unit 文件的新内容，本身不触碰运行中的进程。三者可以组合，**改完要按应用支持情况与影响面选择动作**，不要把 `reload` 当成对所有应用的默认首选（不支持 reload 的应用就只能 restart）。[systemctl(1)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man1/systemctl.1.html)

另外，**应用自身的配置文件**是否需要 reload，取决于该应用，与 systemd 无关：有些应用收到信号才重读，有些必须重启，有些每次请求都读。以应用官方说明为准。

> [!NOTE]
> **停下检查点：`reload` 成功不等于新配置已生效。**
> `reload` 只说明服务接受了这个动作（或命令返回 0）。要证明新配置生效，应从**行为**上验证：一次真实请求的结果、日志里新配置载入的证据，或进程重新读取相关文件的记录。

## 只读检查：显示配置来源而非值

**运行位置：待检查的 Linux VPS；只读。** 目标 unit 用 `example-web.service` 占位，替换为你已确认的 unit。这些命令可能输出内联配置或含敏感路径，**输出只留在本机，不要整段贴到公开处**。

```sh
# 磁盘上的 unit 主文件与 drop-in
systemctl cat example-web.service

# 管理器当前理解的属性与启动时刻
systemctl show example-web.service -p MainPID -p User -p Group -p WorkingDirectory -p ExecStart -p FragmentPath -p DropInPaths -p ExecMainStartTimestamp

# 运行状态与是否开机启用
systemctl is-active example-web.service
systemctl is-enabled example-web.service

# 定位当前进程（若服务未运行，MainPID 为空/0，下面的 /proc 读取应跳过）
pid=$(systemctl show --value -p MainPID example-web.service)
case "$pid" in ''|0|*[!0-9]*) echo "no running process; skip /proc checks" ;; *) echo "MainPID=$pid" ;; esac

# 日志：看它读的是哪个配置、是否报解析错误
sudo journalctl -u example-web.service -n 60 --no-pager
```

**要区分三层，不能混为一谈：**

- **磁盘上的文件**：`systemctl cat` 打印的是管理器会去读的主文件与 drop-in（按名字顺序），它**不是**合并后的“有效配置”，也可能与已经加载的版本不同。
- **管理器当前理解的配置**：`systemctl show` 反映**已加载**的属性；若改了 unit 但**没有 `daemon-reload`**，这里可能仍是旧值。
- **运行进程实际状态**：进程真正的 `exe`、cwd、环境要以运行进程为准，与上面两层各自独立。

确认了 `MainPID` 是有效非零数字后（上面用 `case` 排除了空/0/非数字），才去读进程层。以 root 读取 `/proc/$pid/exe`、cwd 时，**符号链接指向的是运行时的可执行文件/解释器**；如果服务是脚本或有容器包装，还要继续追它实际加载的代码或镜像，链接本身不等于“跑的是这份源码”。

想确认某个 unit 的加载与条件：

```sh
systemctl list-unit-files 'example-web*'
systemctl show example-web.service -p LoadState -p ActiveState -p SubState -p ConditionResult
```

`LoadState=masked` 表示该 unit 被指向 `/dev/null` 而无法启动；`ConditionResult` 反映 `Condition…=` 是否通过。这些是定位“为什么没按预期启动”的线索，不能从“文件存在”就断定服务会运行。

### 核对各层版本（只读）

```sh
# source 层
git -C /opt/example-web rev-parse --short HEAD
git -C /opt/example-web status --short

# 运行进程层：先取 MainPID，排除未运行，再看 exe 指向与启动时刻
pid=$(systemctl show --value -p MainPID example-web.service)
case "$pid" in ''|0|*[!0-9]*) echo "no running process" ;; *) sudo readlink -f "/proc/$pid/exe" ;; esac
systemctl show example-web.service -p ExecMainStartTimestamp -p ActiveEnterTimestamp

# 用户视角：一次可观察的真实行为，确认连到的是哪份服务/入口
#（换成真实 endpoint 与只读请求；客户端自身版本另记）
curl --noproxy '*' --connect-timeout 3 --max-time 10 -sS -o /dev/null \
  --write-out 'endpoint HTTP %{http_code}\n' http://127.0.0.1:8080/health
```

`git status --short` 有输出说明有未提交改动，此时固定的 commit 引用也不代表运行的就是工作区内容。**进程启动时刻用管理器的 `ExecMainStartTimestamp` 之类属性，不要用 `/proc/$pid/exe` 的 stat mtime**（那是文件时间，不是进程启动时间，文件也可能被替换）。`exe` 链接是**事实**，但它证明的是运行时/解释器；“源码里已经是新的”是**期望**，两者要分开陈述。进程退出或 PID 复用时，`/proc/$pid` 会指向别的进程，读之前要重读 `MainPID` 并保留未知。

上面的 HTTP 状态码只说明该 endpoint 对这次请求的响应；要证明版本或配置已经改变，仍需应用提供的版本字段，或一项能区分新旧行为的请求。

## 变更与恢复边界

改配置是有副作用的操作。做之前先明确边界，做完分开验收：

1. **先备份，再编辑。** 复制原文件并保留权限/时间戳，记录你改了哪一行；不要把整份配置覆盖成模板。**备份目标要是新的、不覆盖旧备份**：时间戳也可能碰撞，不能仅凭名字就断言唯一。核实复制动作确实创建了备份，抽查内容与权限，再继续编辑；恢复时从你真正想回退的那一份复制回去。
2. **先校验再应用。** 很多工具提供语法/配置检查子命令（如只校验不运行的 dry-run）；先跑它，失败就停在应用之前。
3. **按支持与影响选动作。** 只改应用配置且该应用支持重载 → 可 `reload`（注意它不保证无中断）；不支持重载的应用只能 `restart`；改了 unit 的进程属性 → 需要 `restart`；只改了 unit 文件本身 → 先 `daemon-reload`，再结合实际重启/重载（见下）。
4. **行为验收。** 用真实客户端发一次有代表性的请求或操作，确认新行为；不要只看 `active` 或返回 0。
5. **恢复路径要写下来。** 回退命令（把备份复制回去、再 `daemon-reload`/`restart`）和“改坏了谁负责”都要在动手前写清楚。

**不要打印秘密。** 检查环境变量、配置内容、命令行参数时，它们都可能含凭据。分享日志或 `systemctl cat` 输出前先脱敏；`EnvironmentFile`、命令行 argv 都是常见的敏感来源。**环境的完整值容易泄漏多行内容，安全做法是只看键名**；若确需在本地受控诊断中查看，需真正按 NUL 分隔解析、逐项处理，绝不能先把 NUL 换成换行再整段输出（那会让含换行的值混成多行泄漏）。

## 怎样算解决

验收记录写三件事：

1. **配置来源三层对齐**：磁盘文件（`systemctl cat`）、管理器已加载值（`systemctl show`，改了要 `daemon-reload` 才是新值）、运行进程实际状态；不要只报告“我编辑的那个文件”。
2. **进程实际怎么启动**：运行用户、`WorkingDirectory`、`exe` 指向、启动时刻（用 `ExecMainStartTimestamp` 等）；关键环境变量只记键名或脱敏值。
3. **一次真实行为**：从真实客户端完成一次能区分新旧配置的操作。

没有重启或 reload、只对照了文件内容的，要标明“未验证生效”。源码改了但没重新构建/安装的，注明 build/install 层未更新。这些层级分别陈述，不互相替代。

相关：[跨机器运维](multi-machine-operations.md)讲实际执行端与共享配置；[日常运维](03-operations.md#4-谁负责让进程继续运行)讲服务 owner 与恢复策略；[排障](08-troubleshooting.md)从症状选入口。

## 来源与维护

查阅日期：**2026-10-05**。systemd 示例按 Ubuntu 24.04 的 systemd 255.4 手册核对；未在真实主机运行服务重启、reload 或环境变更。文件语法检查、进程状态与客户端行为是不同的验证层。

- [systemd.exec(5)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man5/systemd.exec.5.html)：system manager 未设 `User=` 默认 root，普通 user manager 是该用户且不能切换其他身份；`Environment=` 等为进程属性，与磁盘上的文件不同。
- [systemctl(1)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man1/systemctl.1.html)：`cat` 打印磁盘上的主文件与 drop-in，**并非合并后的有效配置**；未 `daemon-reload` 时可能与管理器理解不一致。
- [systemd.service(5)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man5/systemd.service.5.html)：`Type=oneshot` 的 `TimeoutStartSec` 默认禁用；reload 可由 `ExecReload=` 或 notify-reload 等支持，不保证无中断。
- systemd.syntax(7)、systemd.unit(5)、systemd.exec(5)：配置合并与 `EnvironmentFile=`/`WorkingDirectory=`/`PATH` 语义，可按目标机 `man systemd.exec` 核对。示例核对版本：systemd 255.4（Ubuntu 24.04）。
- [Ubuntu OpenSSH server](https://ubuntu.com/server/docs/openssh-server/) 与 `sshd_config(5)`：单值关键字“先读到的值生效”与 `Include`/`Match`。
- 具体 CLI/harness 的配置作用域与优先级：以各工具当前官方设置文档为准（例如 Claude Code 的 settings 页、Docker 的 CLI 环境与 context 文档）；本页不复制其优先级到别的工具。

**想一想：`systemctl reload example-web` 返回 0，能否证明你把 `Environment=PATH=…` 的改动已经生效？**

<details>
<summary>查看答案</summary>
<p>不能。`Environment=` 属于“进程如何被启动”的属性，`reload` 不会重建进程，因此不会应用它；要让新的 `PATH` 生效，通常需要 `restart`。`reload` 返回 0 只说明服务接受了这个动作。</p>
</details>
