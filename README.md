[简体中文](README.md) · [English](README.en.md)

[![Infra Field Guide：从第一台 VPS 到可恢复的个人基础设施](docs/assets/banner.svg)](https://github.com/IndelibleVivi/infra-field-guide)

# Infra Field Guide · 把自己的服务安顿好

给第一次买 VPS、准备把本机服务搬上云、或正在更换服务器的人。也给陪你操作的 AI agent。

这是一套中文基础设施现场手册：先理解机器和网络，再部署、观察、备份、迁移，最后把旧资源收干净。你不需要先成为 Linux 专家，但需要知道每条命令在哪台机器运行、改变什么、失败后如何回来。

即使让 AI 帮你操作，也能逐渐看懂它准备改什么，以及它到底有没有做成。

**九章教程、时间与访问恢复专题、agent 工单、配置示例、六张架构图，以及可运行的只读 health 工具。** 教程使用合成地址，实施时换成自己核实过的目标。

[教程导航](#从你的问题进入) · [完整架构](docs/architecture.md) · [Agent 入口](agents/README.md) · [检查状态](https://github.com/IndelibleVivi/infra-field-guide/actions/workflows/check.yml)

**[打开独立阅读站 →](https://indeliblevivi.github.io/infra-field-guide/)** · 按「从零开始／迁移与恢复／连接与排障」分组的章节目录、站内搜索、手机阅读、术语就地释义与完整架构图集。正文与仓库保持同一份来源；构建和维护见 [site/README.md](site/README.md)。

## 从你的问题进入

| 我现在想做什么 | 从这里开始 | 完成后应该得到什么 |
| --- | --- | --- |
| 还没买 VPS，看不懂套餐 | [01 · VPS 101](docs/01-vps-basics.md) | 一份按用途、预算、资源和网络选择的购买清单 |
| 刚收到一台机器 | [02 · 新机检查与首日操作](docs/02-first-server.md) | 能恢复、能独立登录、最小暴露面的基础环境 |
| 服务老掉线、内存爆、磁盘满 | [03 · 日常 Ops](docs/03-operations.md) / [排障入口](docs/08-troubleshooting.md) | 分层定位与可验证的修复路径 |
| 本机服务想常驻 VPS | [04 · 本机 → VPS](docs/04-local-to-vps.md) | 候选部署、数据迁移、入口与客户端验收 |
| VPS 涨价、配置不够、准备换商家 | [05 · VPS → VPS](docs/05-vps-to-vps.md) | 单一 writer 的切换与数据边界清楚的恢复方案 |
| 想按 CC「转生」材料重整环境 | [06 · 备份、环境清理与恢复](docs/06-account-recovery.md) | 两套清单、具体路径、分层重置与选择性恢复 |
| Tunnel、DNS、VPN、代理分不清 | [07 · 网络与代理](docs/07-network-and-proxies.md) / [架构图集](docs/architecture.md) | 说清请求从哪来、往哪去、由谁鉴权 |
| 想让 VPS worker 回到 Mac 做项目 | [09 · 私有远程访问](docs/09-private-access.md) | Tailscale grant、OpenSSH、非交互环境与项目验收 |
| 时间不准、NTP 无响应、UDP 123 疑似被拦 | [时间同步专题](docs/time-synchronization.md) | 分清 clocksource 与校时，验证往返并选择持续可用的时间源 |
| 多个人或 agent 共用 VPS，加固后有人进不来 | [访问权限与恢复专题](docs/access-control-recovery.md) | 可辨认的入口、实际执行权限、新连接验收与定点恢复 |
| 想先看一眼自己的机器 | [health 工具与离线看板](tools/README.md) | 不上传数据的 Linux 资源快照和离线 HTML |
| 想让 agent 帮我操作 | [给 agent 的入口](agents/README.md) | 明确范围、停机条件、证据与授权边界的工单 |

每章开头有一张入门示意图；关键小节另有两种 SSH key、RAM / swap、迁移回退分界的对照图。陌生词可以先查[29 词的小词表](docs/glossary.md)，阅读站中点虚线下划线的词即可就地展开，关闭后接着读。带图钉的便笺标出容易混淆、值得停一下的概念。正文链接用不同标记区分站内阅读、词义解释、本项目仓库和外部资料；标题下可展开标记说明。

第一次学建议顺序：**01 → 02 → 03 → 07**，再按需要选 04、05 或 09。遇到账号问题直接读 06，不必先买服务器。

搜索可以直接输入「SSH 超时」「磁盘满」「公钥拒绝」「UDP123」「加固后连不上」等问题，也支持多个关键词。每章的适用环境与验证范围可展开查看，章末有一道理解题，答案默认折叠。

## 五分钟内先看见一个结果

**[先玩一遍 Health 模拟仪表盘 →](https://indeliblevivi.github.io/infra-field-guide/health/demo/)** 无需终端：切换日常运行、内存吃紧、磁盘快满、小文件堆积、采集缺失五种合成场景，拖动时间或回放一小时，让曲线、数值与提示一起变化。它不连接真实机器。想看命令会生成什么，可先打开[固定合成快照](https://indeliblevivi.github.io/infra-field-guide/health/snapshot/)。

需要 Python 3.9+；无需 pip 安装依赖。先下载仓库，或在终端克隆：

```sh
git clone https://github.com/IndelibleVivi/infra-field-guide.git
cd infra-field-guide
```

从仓库根目录运行：

```sh
mkdir -p reports
python3 tools/health.py collect --demo -o reports/health-demo.json
python3 tools/health.py render reports/health-demo.json -o reports/health-demo.html
```

在文件管理器中打开 `reports/health-demo.html`，会看到 RAM、swap、load、磁盘／inode、uptime 和 memory PSI 的离线快照。数据是仓库附带的固定合成样例，包含低内存、低磁盘余量与未配置 swap 的提示；它没有时间回放。重复演示请换输出文件名，工具会保护已有结果。

这个例子不 SSH、不联网、不安装服务、不读取你的账号。真实采集仅面向 Linux；macOS、Windows 可做合成演示与渲染。Windows 请手动创建 `reports` 目录并使用可用的 Python 命令。完整选项与限制见 [health 工具说明](tools/README.md)。合成演示不证明你的 VPS 健康。

## 把整套路径看清楚

[![参考基础设施总览：管理访问、服务入口、出站 API，以及数据、备份和观察的关系](docs/diagrams/infrastructure-overview.svg)](docs/architecture.md)

[打开总览 SVG 放大阅读](docs/diagrams/infrastructure-overview.svg)。这是供读者按需组合的参考架构，图中节点不代表仓库替你部署了服务。管理连接、公网入口和应用出站是不同路径；迁移时还要单独追踪数据 writer。进入[完整架构图集](docs/architecture.md)查看六张图、边界说明及可编辑源：总览、控制访问、公网入口、出站访问、迁移状态、仓库与 health 数据流。

## 作者的服务选择与 referral

**VPS：GreenCloud Budget KVM Sale。** 作者从 Hetzner 搬到 GreenCloud 后，愿意推荐这一年付方案给个人小服务与远程 worker 使用。选购章保留了[GreenCloud referral、普通入口与带日期的套餐对照](docs/01-vps-basics.md#作者选择greencloud-budget-kvm-sale)；先按自己的地区、用途与账期选配置。

**住宅代理：Proxy-Cheap Dedicated。** 作者购买的是静态住宅产品中的 **Dedicated** 档，反馈这次拿到的 IP 测试结果很好，可用于访问官方 Claude 网页 / app。这是作者所购样本的使用体验，不是全部 IP 的评分或可用性保证；不同 ISP、分配地址与测试时间可能有差异。[使用作者的 Proxy-Cheap referral](https://app.proxy-cheap.com/r/3zNHbA)，或先看[普通产品入口](https://www.proxy-cheap.com/services/static-residential-proxies)与[术语、体验边界和选购说明](docs/07-network-and-proxies.md#住宅代理选项proxy-cheap-dedicated)。

海外地区的 VPS 默认直接使用自身出口，**无需把静态住宅代理作为标配，也不推荐常规叠加**。使用目标服务仍须符合其地区、账号与使用规则；代理不是访问资格或账号安全的保证。

以上为 referral 链接；符合各商家规则的购买可能为作者带来佣金或账户奖励，不承诺额外折扣。两处都提供普通产品入口，可以自行比较后选择。

## 可以在 VPS 上放什么

个人网站、经过鉴权的小型 API/MCP 服务、定时任务、轻量数据库、监控、独立备份接收端、你有权管理的私有网络入口。先确认资源、数据敏感度、网络访问者和备份责任。

依赖桌面 UI、系统 Keychain、只在个人电脑有权限的数据源、重型 GPU 工作负载，不会因为复制到 VPS 就自动可用。`localhost` 的服务加上 Tunnel 后也不会自动获得用户身份校验。涉及私有文件或可写 MCP 时，把“谁能访问、谁能调用什么”作为部署的一部分。

## 手册如何使用证据

- **原理**解释机制；**操作步骤**写明适用平台和验收；**经验**用于提示失败模式，不冒充普遍因果；**示例**全部使用合成身份和保留地址。
- 通用方案参考了真实跨服务商迁移、内存压力故障和入口排障的经验，但本仓库重新编写教程；不包含私人运维仓库、主机清单、账号记录或其 Git 历史。
- 版本与平台行为以各章链接的一手文档为依据，首轮查阅日期为 **2026-10-02**。遇到 CLI 输出与教程不符，先查看该版本 `--help` 与官方文档，再决定下一步。
- 本仓库不提供托管运维、生产 SLA、商家排名或平台风控结论。测试证明的是附带工具与样例的行为，不能代替真实机器上的验收。

## 文件与维护

`docs/` 是给人读的教程；`agents/` 是给机器的任务约束；`examples/` 是可复制的合成输入；`tools/` 是实现；`tests/` 是行为证据。[AGENTS.md](AGENTS.md) 只约束仓库贡献，不授予对任何服务器的权限。

贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)；资料归属、适用环境和实际验证范围见[来源与维护](docs/sources-and-maintenance.md)。检查只使用合成输入并静态解析教程命令：

```sh
python3 -m unittest discover -s tests -v
```

CI 在 Linux / Windows、Python 3.9 / 3.13 运行这些检查；Linux job 另做 runner 本机的只读采集和渲染。它不连接你的 VPS。提交问题时给 OS、工具版本、失败步骤和脱敏错误，不要贴 token、Cookie、完整日志或含个人路径的截图。

**许可：功能代码与配置示例使用 [SUL-1.0](LICENSE)，原创文字与图示使用 [CC BY-NC-SA 4.0](LICENSE-DOCUMENTATION.md)。** 这是 source-available 项目；具体路径、代码片段及第三方材料的边界见 [LICENSING.md](LICENSING.md)。第三方产品名称用于说明，不代表官方合作或背书。
