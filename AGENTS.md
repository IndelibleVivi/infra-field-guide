# Infra Field Guide · 仓库契约

这是独立的通用教程与工具仓库，没有继承私人基础设施仓库的 Git 历史。中文配合自然的 English technical terms 是 canonical edition。内容为重新编写的可移植材料、合成示例与有归属的参考链接。

## 真源与执行范围

- `README.md` 管中文读者入口与能力声明，`README.en.md` 是对应英文入口；`docs/` 管解释和 runbook；`agents/` 管可复用工单；`examples/` 管合成输入；`tools/` 与 `tests/` 管可执行行为。
- `site/` 管独立阅读站的排版、路由与构建；正文仍由上面的 Markdown 管理。`site/pages.json` 与 `site/build.py` 的显式白名单定义 Pages 发布范围；`_site/` 是忽略的派生输出，不能手改、提交或扩大为整个仓库的复制。站点规则与预览命令见 `site/README.md`。
- 示例使用 `example.com`、文档 IP、合成身份和占位符。OS 标准路径可用于教学；真实使用者的私人主机、账号、路径、凭据和笔记不得进入仓库。
- 写教程不授权操作真实服务器、修改账号、购买、迁移、防火墙、SSH 或删除数据。编写和验证期间不执行教程中的真实环境变更命令。
- 分开报告 source、测试、安装、service activation、网络可达性与真实客户端验收。只写实际验证过的结果。
- 版本敏感的断言以官方资料为依据并标记查阅日期。社区操作步骤可以按归属保留；作者经验、平台因果推断与本地可验证事实必须分清。
- 许可范围以 `LICENSING.md` 为准：功能代码与配置示例使用 SUL-1.0；原创说明文字、工单文字与图示使用 CC BY-NC-SA 4.0。改变许可需要 owner 明确选择，不覆盖第三方权利。

## 协作

多人可能同时工作。遵守文件责任，不覆盖别人的改动。临时 worker 不访问私人 continuity 或主会话私人说明，不调用 Oracle，不递归派工，不改全局 routing，不 commit、push、发布、部署、操作账号或接触真实服务器；这些动作只有明确工单另外授权才可进行。返回文件、检查结果、限制与来源。

## 验证与文档收口

```sh
python3 -m unittest discover -s tests -v
git diff --check
```

按 `tools/README.md` 运行合成 health 例子，检查新 JSON 与 HTML。单元测试覆盖合成采集与渲染；文档检查验证相对链接／章节锚点、shell 静态语法与 JSON 示例。真实 Linux、SSH、cloud 和账号验收是独立层级。

阅读站变更使用安装了 `site/requirements.txt` 的 Python 3.10+ 运行 `python -m unittest discover -s site -p 'test_*.py' -v` 与 `python site/build.py`；交互改动检查 `node --check site/site.js` 并做实际浏览器验收。Pages workflow 在 PR 只构建测试，在 main 推送后发布白名单产物；这不授予任何教程涉及的真实基础设施操作权限。

修改读者能力或入口时同步两份 README。正文 UI 图标由 `site/ui.py` 管理；链接去向由 `site/build.py` 解析实际 hostname/path，保留普通链接和术语解释的渐进增强。不要把标题锚点或其他 GitHub 仓库标成本项目源码。`docs/glossary.md` 第一段释义是 inline 解释的唯一真源；不要复制到 JS。章节小图以 `docs/diagrams/chapter-maps.json` 为语义源，由 `python3 scripts/render-chapter-maps.py` 生成两种 SVG，不能只改单份导出。九章 Markdown 的代码块与既有锚点要保留。架构图模型、可编辑源与导出关系见 `docs/diagrams/README.md`；修改图后重新生成并实际查看。修改操作步骤时，同步相关教程、工单、示例与 README 导航；改变 health 契约时同步工具说明、fixture 和行为测试。验证状态记录在 `docs/sources-and-maintenance.md`。私人 working continuity 留在仓库外，不能写入文档或提交。
