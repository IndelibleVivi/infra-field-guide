# 架构图的可编辑源与导出

[回到架构地图](../architecture.md)

完整架构图集包含六张独立视图，另有本页后半部分说明的章节概念图。`infrastructure-overview` 是 README 可引用的总览；其余五图承接控制、入站、出站、迁移和仓库 source 结构。所有图中文字以中文为主，English README 可以共享同一导出并注明 Chinese labels。

推荐点击 SVG 以全尺寸阅读：源画布宽 1600–1680 px，README 的窄幅嵌入用于认识整体布局。不要依赖缩到约 900 px 后的细字阅读具体权限和步骤；放大 SVG 或打开对应 PNG，再配合架构页的文字说明。

| 文件角色 | 维护规则 |
| --- | --- |
| 六张完整图的 `*.excalidraw` | 唯一可编辑图源：布局、可见文字、稳定 ID、连接绑定和语义证据都在这里 |
| `*.svg` | 默认文档嵌入格式；保留文字及无外部资源的矢量图 |
| `*.png` | 从同一 SVG 实际渲染的查看副本；固定本次字体与版面 |
| `architecture-model.json` | 从图源 `customData` 提取的 renderer-neutral 模型索引，不单独编辑 |
| `../../scripts/render-diagrams.mjs` | 仅针对这些图所用元素的小型本地导出器，不是完整 Excalidraw 渲染引擎 |

图源可以在 Excalidraw 中打开编辑，也可以作为 JSON 精确修改。当前使用矩形、文本、折线和绑定箭头；普通文本 20 px，图标题 34 px，边标签 17 px，正文不靠缩小字来塞进框。采用白底 `#ffffff`、墨蓝 `#163a5f`、正文蓝 `#365775`、天水蓝区域 `#e9f7fc`、线蓝 `#6ab9db` 和浅金强调 `#e7c979` / `#fff5d9`。不使用颜色表达唯一的语义差异。

## 编辑一张图

1. 确认变更依据来自哪个章节或可执行 source；前五图是 `reference-model`，仓库图是 `implemented-source`，均不描述 live 状态。
2. 在对应 `.excalidraw` 修改内容与布局，保留稳定元素 ID。矩形的 `customData` 记录 `name`、`responsibility`、`evidence` 与 `evidenceStatus`；箭头记录 `source`、`destination` 与 `payload`。同步可见文字和这些字段，避免图与机器可读说明分叉。
3. 标题元素 `id: title` 的 `customData.guide` 记录画布尺寸、全图问题、证据列表与 `state`。`state` 明确 canonical owner、允许的 writer 与可观察 receipt。证据相对路径从本目录计算。Excalidraw 的自定义字段放在元素 `customData` 内，以便保留到场景文件中。
4. 箭头保留 `startBinding` / `endBinding` 与节点 ID；移动节点后确认连接点仍在边界。节点文本通过 `containerId` 绑定卡片。箭头在节点后面绘制，边标签放在留白中。
5. 运行导出器并查看新 SVG 和 PNG。核对源到目的的方向、许可关口、唯一 writer、可选分支和验证边界；再检查字被切断、标签压线、线穿节点与过小字号。

本导出器支持这些源使用的零旋转矩形、文本、line / arrow 元素、纯色、线型和简单箭头。它不支持任意 Excalidraw 图片、手绘笔迹、旋转、曲线、复杂箭头头型或图标；新增这类元素前，需要有意识地扩展渲染器或改用能支持它的完整导出流程。标题的加粗来自保留在 `customData` 中的排版字段；Excalidraw 编辑器内的字体外观可能与最终 SVG 有差别。

## 本地再生成

在仓库根目录执行，Node.js 18+ 可使用脚本涉及的 API；本次实际验证的是 Node.js 24.19.0。

```sh
node scripts/render-diagrams.mjs
```

默认只需要 Node.js 内置模块，写入 SVG 和模型索引。SVG 含 `<title>` / `<desc>` 与文字，没有网络资源。输出顺序稳定；不生成时间戳。

可选 PNG 步骤需要自己已有的 Playwright 和 Chromium。脚本不会下载它们，也不会改变用户浏览器。将占位路径替换成实际文件：

```sh
node scripts/render-diagrams.mjs --png \
  --playwright-module /path/to/playwright/index.mjs \
  --browser /path/to/chromium
```

脚本把生成的 SVG 内容交给独立 headless browser page，阻止外部请求，检查卡片文字边界并截图。若文字溢出会返回错误，同时保留 PNG 供定位。修改图源后，SVG、PNG、模型索引必须一起更新，不能让 PNG 停留在旧版。

静态验证可在仓库根目录运行：

```sh
node --check scripts/render-diagrams.mjs
python3 -m unittest discover -s tests -p 'test_docs.py' -v
git diff --check
```

这些检查不能代替逐张看图；也不证明图中的参考部署已经存在。图像导出的具体验证记录和范围见[架构页](../architecture.md#维护再生成与已验证范围)。

## 章节概念图：先读懂眼前这一件事

这些小图是完整图集之外的入门视图，不代表已部署的机器或实时指标。九章各有一张，再为两种 SSH key、RAM / swap、迁移回退分界增加三张对照图。每张图聚焦一个读者问题；顺序箭头代表验证或操作顺序，网络图的三行代表独立路径，左右对照图不表示数据自动同步。

- [chapter-maps.json](chapter-maps.json) 是可编辑语义模型：稳定 ID、对应章节和小节锚点、标题、解释、节点与阅读提示。事实来源是对应章节及其官方引用。
- [render-chapter-maps.py](../../scripts/render-chapter-maps.py) 是标准库 renderer，维护图标与布局规则；运行 `python3 scripts/render-chapter-maps.py` 再生成全部 SVG。模型与 renderer 各管一个层面，不另存手改导出。
- 普通 `.svg` 为 720px 横向或对照版，`.mobile.svg` 为 360px 纵排版；节点文字保持 16–18px。站点窄屏使用纵排，GitHub 使用普通图。宽度较窄时可以点原图。
- 修改后检查文字是否仍在自己的节点内、顺序与并列关系是否正确，同时查看桌面和手机版。新图需要接入章节 Markdown；站点素材白名单从模型精确提取两份 SVG，不递归复制目录。

概念图、模型与导出按原创图示的 CC BY-NC-SA 4.0 授权；renderer 按 SUL-1.0。它们与六张完整 Excalidraw 图有各自清晰的源文件，不互相覆盖。
