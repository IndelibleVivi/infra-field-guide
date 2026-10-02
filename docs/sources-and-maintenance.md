# 来源、适用范围与维护

[返回首页](../README.md)

## 这套材料是什么

中文是 canonical edition。读者是自己管理小型服务的人及其 agent；教程、脚本与 JSON 示例是同一个仓库的不同阅读入口。示例主线为 Ubuntu 24.04 LTS + systemd，其他发行版、Windows、macOS、容器限制和不同架构必须显式适配。

教程由迁移与运维中可泛化的问题重新组织而成，结合官方资料校正。没有复制私人仓库的源码、原始日志、备忘录、凭据、账号表或历史；没有引入第三方图像、截图或 vendored 代码。封面的小鹿是为本项目生成的 AI 辅助插画，原始 PNG 与含该位图的 SVG 排版一并提供，见 [assets 说明](assets/README.md)。官方产品名称与参考链接不等于 endorsement。

私人运行经验只能支持“曾遇到这种失败”；不推出某个商家一定好坏、某个 IP 必定安全、某种协议能避免封号等结论。社区材料的具体做法可以保留为有归属的路线，同时区分可验证的本地结果和作者对平台风控的推断。第06章列出两套材料的来源识别与分歧；原帖链接未核实，未将截图或原文收入仓库。

## 来源规则

各章在相关断言旁或文末链接官方文档，首次查阅日为 **2026-10-02**。来源类别依次为：协议/OS/软件官方文档、provider 的产品与计费文档、可重现的本仓库合成测试。没有来源或实验支持的推断需要明确标记。

高频变化项：价格和可售地区、套餐资源、平台支持地区、账号申诉、CLI参数、凭据保存方式、Docker防火墙行为、Cloudflare/Tailscale设置入口。读者实施前应核对所用版本；本仓库不把查阅日写成永久事实。

## 修改时要一起检查

| 改动 | 同步对象 | 有意义的检查 |
| --- | --- | --- |
| tutorial 路径／命令／前提 | README导航、agent工单、example | 相对链接、运行机器标签、占位符、预期与恢复步骤 |
| health 数据语义或 CLI | 工具说明、fixture、测试、首页能力描述 | 合成例子、错误/unknown、公式、HTML转义 |
| migration 写入／恢复顺序 | 两类迁移指南、agent工单、plan | 首次新写入前后都能解释state owner |
| 网络路径图 | 网络章节、alt text | 箭头与认证边界、实际渲染 |
| 公开许可或来源 | README与具体license scope | owner明确选定、第三方归属不被覆盖 |

不要把真实诊断报告或 operation record 作为 fixture。`reports/`、`.local/` 被忽略只是减少误提交；分享前仍需检查内容。Git历史中删文件也不等于撤回已经公开的内容。

## 验证状态的表达

“unit tests通过”仅表示在运行测试的系统上通过相应夹具；“合成看板可用”不表示Linux真实采集已经验证；“文档命令已审查”不表示真的改过SSH、firewall、swap或DNS。

教程与 health 工具不会自动安装监控、创建 VPS 或修改账号。仓库的 `Reading site` workflow 会在 main 推送验证通过后发布独立阅读站；这是文档发布，不会部署教程描述的服务。真实机器验证、公开远程仓库、CI 执行与 owner 验收应分别记录，不互相替代。

## 验证记录（2026-10-02）

- 标准库测试：20 项通过，包括合成采集、schema／阈值／unknown、HTML 转义、CLI roundtrip、现有输出保护，以及文档链接／章节锚点、shell 语法和 JSON 示例。
- 命令代码块只作静态语法检查，没有执行 SSH、firewall、swap、迁移或账号清理。
- [跨平台 CI](https://github.com/IndelibleVivi/infra-field-guide/actions/runs/36984498352) 在 Linux / Windows、Python 3.9 / 3.13 四个组合通过 20 项测试与合成 JSON→HTML 演示；Linux runner 的真实资源采集与渲染也已通过。它不证明真实 VPS 部署或长期监控效果；health HTML 浏览器视觉布局未验收。
- 六张架构图已从 Excalidraw 源生成 SVG、PNG 与语义模型，实际渲染并逐张查看；卡片文字边界检查通过。banner 已按白底、天水蓝、墨蓝、浅金重绘排版，900px 字号／对比度检查通过，实际渲染已查看。
- 基础／网络／私有访问、CC 清理、排障、架构与 health 实现经分批独立技术审查；公开入口、推荐段、许可和 CI 也经审查。修正了 curl 继承代理导致验收失真、清理重复执行的目录碰撞、Windows 文本 stdin 转换换行导致 Bash 静态检查失效的问题；审查没有留下已确认但未解决的 P1/P2。
- 独立仓库已公开，匿名 GitHub 页面与 README 封面显示已检查。后续改动的执行结果见 [Checks](https://github.com/IndelibleVivi/infra-field-guide/actions/workflows/check.yml)，按对应 commit 判断。没有真实 VPS 部署或用户设备验收。

## 许可与推荐关系

功能代码、测试及配置示例使用 SUL-1.0；原创说明文字、agent 工单文字与图示使用 CC BY-NC-SA 4.0。范围与第三方边界以 [LICENSING.md](../LICENSING.md) 为准，不将本仓库称为 OSI 开源。引用的一手资料仍适用其原始权利，链接不转移其版权。

第 01 章的 GreenCloud referral 是 Faye 的推荐链接；购买符合商家规则时可能带来佣金或账户奖励。同章提供普通商品入口，套餐与条款直接链接官方页面，并标记查阅日期。推荐基于个人使用与明确用途，不是商家排名或服务保证。

第 07 章另列作者的 [Proxy-Cheap referral](https://app.proxy-cheap.com/r/3zNHbA) 与普通产品入口。作者购买 Dedicated、所购 IP 测试结果很好及用于官方 Claude 网页／app，是作者自述的使用体验，没有独立复测或推广为所有 ISP／IP 的保证。[官方产品页](https://www.proxy-cheap.com/services/static-residential-proxies)、[ISP 说明](https://www.proxy-cheap.com/services/isp-proxies)与 [referral 规则](https://www.proxy-cheap.com/referrals)于 2026-10-02 查阅，分别支持产品术语与奖励关系，不证明单次 IP 体验。海外 VPS 不推荐常规叠加静态住宅代理。

## 独立阅读站的维护

[阅读站](https://indeliblevivi.github.io/infra-field-guide/)从同一批 Markdown 生成，入口、响应式排版、分节搜索和构建说明见 [site/README.md](../site/README.md)。中文为正文版，English introduction 仍是英文入口说明，没有声称全书已翻译。站点不采集或上传 health 报告。

2026-10-02 的阅读站变更在本地通过 20 项原有测试与 5 项生成站点测试，覆盖全站内部链接／锚点、搜索目标、发布白名单和关键 Markdown 结构；独立审查逐字比对 132 个 fenced code block，渲染后的命令文本与源文件一致。已在浏览器检查 1280px 桌面与 390px 手机排版、搜索与空结果、目录跳转、代码复制、Escape／焦点返回及架构原图入口；未发现横向整页溢出或浏览器 console 错误。这些是工程验收，不代替读者设备或作者审美验收。线上发布结果按 [Reading site workflow](https://github.com/IndelibleVivi/infra-field-guide/actions/workflows/pages.yml) 的对应 commit 查看。


阅读辅助的同日改进：九章补上读者定位与便笺，新增 [29 词小词表](glossary.md)，每词的解释来自对应章节及其引用；释义与继续阅读链接分开，站内弹窗使用同一正文真源。新增 12 张章节概念图及独立的手机纵排 SVG，保留六张完整架构图。测试扩展到 8 项站点检查，验证图示两种素材、词表链接、便笺转换与命令文本完整性；未增加浏览器依赖或外部脚本。正文、表格与目录的层级加深，阅读站 logo 改为原创月牙与水纹标记。

本轮实际浏览器检查覆盖 1280px 桌面、768px 平板与 390px 手机：词义弹窗／Escape 焦点返回、章节图纵排、手机目录、搜索与空结果、表格局部横滑及代码复制。12 张小图的两种排版均已渲染查看，文字尺寸／对比预检通过；九章已有的 110 个 fenced code block 与本轮修改前逐字一致。真实读者设备和新增视觉的 owner 验收仍是独立环节。

同日的阅读编排修订：首页九章按原有三个主题分组，正文页使用实际阅读位置、小节图标与链接去向说明。站点测试扩展到 9 项，新增去向分类、解释关联与修复链接的验证。RFC 6598 失效的 PDF 入口已替换为官方 HTML 正文；对第 07、09 章中 RFC Editor、OpenBSD、Tailscale、Cloudflare 的 20 个不同官方文档地址执行了跟随重定向的 GET，均返回 HTTP 200。这只记录查阅时的可达性，不表示所有外链永久有效，也不替代逐条内容核验。
