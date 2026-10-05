# 跨机器与多 harness 的 agent 运维

[返回首页](../README.md) · [日常运维](03-operations.md) · [访问权限](access-control-recovery.md) · [时间约定](time-synchronization.md) · [给 agent 的跨机器工单](../agents/multi-machine-ops.md)

## 这一页帮你做什么

笔记本里一个 CLI 修改代码，VPS 上另一个 CLI 跑长任务，某个远程工具还连接着第三处数据。把这些位置说清楚，才能知道应在哪里检查、哪些工作可以并行，以及换一只 agent 后怎样接着做。

这里的 harness 指承载 agent 的 CLI 或运行框架。本页按具体执行上下文辨认一次 agent 工作：使用哪个 harness、在哪启动、以什么身份调用哪些工具。模型名字用于交流；运维记录还需要准确的机器、任务和资源。本页提供通用判断和合成例子，具体 CLI 的配置、批准模式、hook 与恢复能力按已安装版本核实。

## 先定位实际执行位置

“本地”和“远程”都需要参照点。你看到的聊天界面、harness 进程、工具进程和最终被修改的资源，可能分别在不同机器。

| 场景 | 发起端 | 实际执行或资源位置 | 要确认的对象 |
| --- | --- | --- | --- |
| 笔记本 CLI 通过 SSH 构建 | 笔记本的 harness | VPS 上的 SSH 用户和项目目录 | 目标主机、用户、非交互环境、构建产物 |
| 直接在 VPS 启动另一个 CLI | VPS 的 harness | 默认本机工具，也可能再连接其他机器 | 该进程的用户、cwd、配置与实际工具路由 |
| 同一个对话调用远程 MCP | 当前 harness | MCP server 及其连接的服务 | server 身份、授权账号、真正的数据源 |
| 本地 Docker CLI 使用远程 context | 本地 CLI | 所选 daemon 的容器与存储 | 有效 endpoint、环境/参数覆盖、daemon 侧路径 |

SSH 的指定命令在远端运行；MCP 的 host、client 和 server 是不同角色，server 可以在本机，也可以在远端。对话界面的位置不足以定位工具执行。[OpenSSH ssh(1)](https://man.openbsd.org/ssh)、[MCP 架构](https://modelcontextprotocol.io/docs/learn/architecture)

Docker 也是容易混淆的一例：context 可能被 `DOCKER_HOST`、`DOCKER_CONTEXT` 或命令参数覆盖，普通远程 daemon 的 bind mount 使用 daemon 主机上的路径。本地存在的项目目录不会因此自动变成远端容器的数据；Docker Desktop 的本机共享路径另有专门机制。[Docker contexts](https://docs.docker.com/engine/manage-resources/contexts/)、[Bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)

**运行位置：实际准备执行任务的 Linux/macOS shell；只读。** 用短输出核对当前环境，不输出完整环境变量或凭据：

```sh
hostname
id
pwd -P
uname -srm
date -u '+%Y-%m-%dT%H:%M:%SZ'
```

这些是定位线索。主机名可以重复，容器看到的系统信息也不等于宿主身份；结合已核实的 SSH host key、实例记录或工具 endpoint 判断。若工具执行在另一层，对那一层重新检查。运行用户、PATH、挂载与非交互认证的具体做法见[私有远程访问](09-private-access.md#8-验证-cwd写入与真实项目命令)。

找到执行位置后，再按[配置与运行版本专题](configuration-and-runtime.md)核对实际进程读到的来源；周期任务的调度 owner、补跑和重复执行见[定时任务专题](scheduled-jobs.md)。

## 留一份能接手的运行记录

先在私有位置记录足够找到任务的信息，几台机器用一张表或一份短文本就可以。不要求把它做成中心调度平台。

| 信息 | 为什么需要 |
| --- | --- |
| 发起机器、harness 及版本、启动方式 | 同一个 CLI 在交互终端和服务中可能取得不同环境 |
| 执行机器、系统用户、工具路由、工作目录 | 接手者能在正确位置复核能力 |
| 仓库副本、commit/ref、未提交改动、产物版本 | 查清正在编辑、已经构建、实际运行的是否同一份内容 |
| 服务/配置/数据库/卷及本次变更负责人 | 识别两个任务会共同碰到的对象 |
| 原任务定位、状态和日志位置、结果位置 | 断线或换 harness 后还能找到同一次执行 |
| 最近一次检查及其时间语义 | 判断记录是否过期，区分事件时间与观察时间 |

只填与任务有关的字段。配置记录写“从哪个受控位置加载”，不复制 token、私钥或整份环境。systemd 的运行用户、工作目录和环境由对应 unit 与服务管理器决定，不能用桌面 Terminal 的结果替它验收。[systemd.exec(5)，Ubuntu 24.04](https://manpages.ubuntu.com/manpages/noble/man5/systemd.exec.5.html)

确认仓库内容时，可以在已经核实的项目目录读取：

```sh
git rev-parse --show-toplevel
git rev-parse HEAD
git status --short
```

HEAD 一样时仍可能有未提交改动；commit、构建产物和运行中的进程也需要各自核对。文件路径只对所属机器有意义。跨机器交付时记录副本、接收位置与内容/版本校验；临时目录里唯一的一份产物不适合作为长期交接依据。

## 并行工作按共享资源安排

两个 agent 可以并行调查和修改互不影响的候选。会争用同一状态时，按具体资源安排负责人和交接时点：

| 共同碰到的对象 | 实用安排 | 仍需注意 |
| --- | --- | --- |
| 同一工作目录和 Git index | 同一目录约定写入责任；独立候选可用独立 worktree/clone | worktree 默认仍共享 Git 配置和部分 refs；不隔离系统权限 |
| 同一服务、SSH/firewall 配置 | 本轮由一个操作者应用相互冲突的变更，其他人复核 | 接手前读最新状态，回退只覆盖本次改动 |
| 同一数据库或输出文件 | 使用应用支持的事务、作业约束或锁 | 协作约定本身不提供并发控制，不能凭“各有一个目录”判断安全 |
| 同一 harness 用户配置、MCP 配置或凭据来源 | 核对配置作用域与已启动进程的生效方式 | 新 session/worktree 不必然拥有独立配置，更新或 logout 可能影响其他工作 |

Git 官方文档说明 linked worktree 的独立状态与共享配置范围。不同 harness 还可能从 home、项目目录、启动参数或其他层读取配置；读各自当前说明，不把一个 CLI 的配置优先级套到另一个。作为具体参考，Claude Code 官方设置页分别说明用户、项目等作用域及 worktree 行为；这些细节仍以该工具当前版本为准。[git-worktree](https://git-scm.com/docs/git-worktree)、[Claude Code settings](https://code.claude.com/docs/en/settings)

独立系统用户在需要区分文件或执行权限时很有用；充分信任的个人维护者也可以继续共用已有用户。具体选择见[访问权限专题](access-control-recovery.md#个人协作的三种常见选择)。这里重点检查哪些状态共享，不要求“每只 agent 一台机器、一个账号”。

## 断线、超时与原任务恢复

对话连接、远程执行进程和任务结果分别观察。选择运行方式时，先问任务是否需要在终端离开后继续、是否要跨重启恢复、结果要保留多久：

| 方式 | 适合的用途 | 接手前要知道 |
| --- | --- | --- |
| 前台 SSH / CLI 调用 | 短任务、交互检查 | 客户端超时或退出后，远端实际状态需要查询 |
| tmux / screen | 需要重新接回的交互会话 | 不自动跨重启；主机会话清理策略可能结束它 |
| nohup / setsid | 处理某些 hangup 或会话关系 | 不提供持久的作业状态与结果记录、重启恢复，也不保证免受 cgroup 清理 |
| 已有服务管理器或任务系统 | 需要独立状态、日志与恢复规则的任务 | 用户、cwd、配置、保留期限与恢复语义都要成立 |

tmux 管理可重新接回的终端会话；GNU nohup 处理 hangup，setsid 建立新的进程 session。退出状态和持久任务记录需要区分，`setsid --wait` 等模式可以等待并返回程序状态，但不由此获得跨重启恢复。[tmux 入门](https://github.com/tmux/tmux/wiki/Getting-Started)、[GNU nohup](https://www.gnu.org/s/coreutils/manual/html_node/nohup-invocation.html)、[setsid(1)](https://man7.org/linux/man-pages/man1/setsid.1.html)

完整进程管理基础见[第 03 章](03-operations.md#4-谁负责让进程继续运行)。Linux 上还要区分 systemd 的 service 与 scope：transient service 由管理器启动，scope 保留调用者执行环境；`--scope` 不是通用的持久化开关。user manager 的生命周期与 logind 策略需要核对。按已有、获准的方式运行，不为一条任务默认修改全局退出登录策略或开启 lingering。[systemd-run(1)](https://manpages.ubuntu.com/manpages/noble/man1/systemd-run.1.html)、[logind.conf(5)](https://manpages.ubuntu.com/manpages/noble/man5/logind.conf.5.html)

远端可能已经接受任务，只是确认或结果没传回来。**超时后先查原任务，结果未知时保留未知。** 对有写入副作用的任务，按下面的顺序接手：

1. 提交前记下目标与已有的任务定位方式；接口支持操作 ID/幂等键时，保留原值。harness session ID、PID 和远端 job ID 分别记录，不假定可以互换。
2. 超时或换 CLI 后，查询原目标的原任务状态与结果。仍在运行就继续观察；已经结束就读取结果并验收产物。
3. 无法确认是否执行时，检查可用日志和业务状态；没有证据就记录待定位，不立即新建同一写任务。
4. 确认失败及已完成部分后，使用该任务支持的恢复方式；能否重跑由其幂等/去重能力决定。

具体恢复命令按所用 harness 或任务系统的说明核对。暂态 unit 可能在完成后被卸载，进程号也不构成长久的作业记录；“查不到”不能单独证明“从未运行”。结果应按需要保存到接手者能找到的日志、任务记录或产物中。界面上的 Stop、关闭终端或退出聊天是否取消远端任务，也要以实际状态确认。[systemd-run 的 unit 保留行为](https://manpages.ubuntu.com/manpages/noble/man1/systemd-run.1.html)

## 换 harness 时怎么交接

交接以任务和资源为中心。接手者先拿到目标、副本版本、允许继续的范围、原任务状态、准确结果位置和未决问题，再用自己的真实执行路径复核。聊天摘要帮助理解缘由；真实文件、服务状态和作业结果支持下一步操作。

同一任务仍在运行时，交接不等于重新提交。一个 harness 的会话文件、批准状态、登录信息或 resume ID 是否可移植，需要该工具明确支持；通用工单不依赖这些内部格式，也不把旧会话中的授权扩大到新目标。

验收一条实际路径即可说明那条路径：本地测试通过后记录本地结果；远程 CLI 能登录后，再验证远程任务所需能力；部署后核对运行版本并从真实客户端完成正常操作。预览、候选构建、已安装程序和在线服务分别注明。

## 来源与维护

查阅日期：**2026-10-05**。本页依据 OpenSSH/系统运行模型、Git、MCP、Docker 和 Ubuntu 24.04 的 systemd 文档组织通用场景；表格中的职责分配与交接顺序是本手册的工程建议。CLI 的具体设置以当前版本为准。仓库检查覆盖命令静态语法、链接与页面，未运行任何真实多机作业、服务变更或断线恢复实验。

**想一想：两个 harness 使用不同 worktree，但都连接同一台 Docker daemon、修改同一个服务，哪些东西真正分开了？**

<details>
<summary>查看答案</summary>
<p>代码工作目录可以分开；daemon、服务、挂载数据及可能共享的配置仍需分别检查。安排工作时按这些真实资源判断冲突，并记录哪一次部署实际生效。</p>
</details>
