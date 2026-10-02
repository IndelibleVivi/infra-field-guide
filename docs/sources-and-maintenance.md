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

本仓库不会自动安装监控、创建VPS、部署网站或修改账号。真实机器验证、公开远程仓库、CI执行与owner验收应分别记录，不互相替代。

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
