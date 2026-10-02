# 独立阅读站

[阅读站](https://indeliblevivi.github.io/infra-field-guide/)把仓库现有 Markdown 生成静态 HTML。`docs/`、`agents/`、`tools/README.md` 等仍是正文真源；不要复制出另一套教程，也不要手改生成的 `_site/`。

## 构建与本地预览

构建使用 Python 3.10+ 和唯一的构建依赖 [Python-Markdown](https://python-markdown.github.io/)。health 工具的 Python 3.9+、标准库契约不变。示例以 POSIX shell 为例；Windows 可直接使用虚拟环境中的 `Scripts/python.exe`。

```sh
python3 -m venv .local/site-venv
.local/site-venv/bin/python -m pip install -r site/requirements.txt
.local/site-venv/bin/python site/build.py --output .local/preview/infra-field-guide
.local/site-venv/bin/python -m unittest discover -s site -p 'test_*.py' -v
python3 -m http.server 4178 --bind 127.0.0.1 --directory .local/preview
```

然后打开 `http://127.0.0.1:4178/infra-field-guide/`。预览服务只绑定 loopback；修改源后重新构建并刷新。临时前台服务器随终端退出停止。需要跨终端保留预览时，使用自己的受管会话并记录停止方式。

`--base` 默认为 `/infra-field-guide/`，可以设为 `/` 用于根路径预览。该参数须以 `/` 开始和结束。发布目标固定为本项目 Pages；换仓库时须一并修改 canonical / Open Graph URL、公开站点链接和工作流配置。

## 文件职责与发布边界

| 文件 | 职责 |
| --- | --- |
| `pages.json` | 发布的正文白名单、路径、章节序号与导航短标题；原文 h1 的文字与锚点保留；章节编号移到眉题，冒号后的说明单独一行 |
| `build.py` | Markdown 渲染、站内链接转换、章节目录、分节搜索索引和显式素材白名单 |
| `home.html` / `shell.html` | 首页编辑排版与公共阅读界面 |
| `site.css` / `site.js` | 响应式排版、原生 dialog 搜索／目录／术语解释、代码复制、表格滑动提示与目录当前位置 |
| `test_build.py` | 全部生成页面的链接／锚点、搜索目标、发布文件白名单与 Markdown 关键结构 |
| `../.github/workflows/pages.yml` | PR 只构建验证；main 推送验证后部署到 `github-pages` environment |

页面正文、导航链接和原图入口无需 JavaScript；搜索、手机目录抽屉、术语就地解释和代码复制为渐进增强。搜索索引按需从同一站点加载，关键词在浏览器内匹配，不发往搜索服务；站点无 analytics、第三方脚本、远程字体或登录。普通外链与 referral 由读者自行点击。

正文中的本地 Markdown 链接改写为对应站点路由；选定图片、完整许可与图源直接随站点发布，其他源码和示例链接回 GitHub。密集架构图保留“放大 SVG”、PNG 与可编辑源入口。代码复制只复制代码文本；剪贴板权限不可用时选中文本并提示手动复制。

构建只读取 `pages.json` 与 `build.py` 明确选择的公共内容，不打包整个仓库、`.local/`、`reports/` 或真实 health 输出。CI 在全新 checkout 构建，只上传 `_site/`。本地变更路由／移除页面后，使用新的空输出目录检查，避免旧预览文件干扰判断。

## 章节图、词表与便笺

- `docs/glossary.md` 是词义真源，每个稳定的 `## 术语` 下第一段是释义，另段“继续读”链接回章节。普通 Markdown 链接在 GitHub 与无 JavaScript 的页面均可用；阅读站把指向词条的链接增强为原生 dialog。修正词义只改这份 Markdown，构建器自动提取，避免两份定义漂移。Escape／关闭后焦点返回原词，Ctrl/Cmd 点击仍按普通链接行为处理。
- `docs/diagrams/chapter-maps.json` 与 `scripts/render-chapter-maps.py` 生成 12 张章节概念图的桌面／手机 SVG；9 张用于各章开头，3 张用于重点小节。Markdown 引用普通 SVG；站点构建为 `<picture>`，视口 1000px 及以下改用纵排，并限制图宽以保留可读字号。完整图源约定见[图示维护](../docs/diagrams/README.md)。
- GitHub 兼容的 `> [!TIP]` / `> [!NOTE]` 在站点渲染为带图钉的阅读便笺。只改变容器与视觉层级，不改变提醒正文或代码块。
- `favicon.svg` 是 Moonlight Fawn 月牙／水纹标记的唯一源，页眉与浏览器页签共用。正文保持白底墨蓝；月光和浅金只用来陪衬层级，不承担唯一语义。

## 发布与验收

GitHub 仓库 Settings → Pages 的 Source 为 **GitHub Actions**。发布行为见 [GitHub 官方 custom workflows 文档](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。首次启用与后续 workflow 部署是仓库 owner 授权的独立发布动作，不等于部署教程所描述的 VPS 服务。

每次修改生成器或导航应运行本目录测试；样式或交互改动还需用浏览器查看桌面和手机尺寸，检查首页／长文、搜索结果与空结果、目录跳转、长表格、长命令、复制和架构图原图。构建成功不代表视觉验收或线上可达。线上发布后从 Pages URL 检查首页、至少一章、搜索索引与素材；历史发布状态见 Actions 的 `Reading site` workflow。

构建器、模板功能结构、CSS、JavaScript 与测试使用 SUL-1.0；原创文案、图示和独立视觉素材按 CC BY-NC-SA 4.0，完整范围见 [LICENSING.md](../LICENSING.md)。Python-Markdown 仅为构建时安装的第三方依赖，适用其自身许可，不随站点分发。
