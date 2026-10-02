# 一起把这本手册写准 · Contributing

欢迎补足步骤、复现失败、修正解释、改进图示或工具。中文是教程的 canonical edition；英文首页对应同一组能力。贡献前读 [AGENTS.md](AGENTS.md) 和[许可范围](LICENSING.md)。只提交自己有权贡献的材料；你的原创贡献按所在材料的许可加入本项目，不转移你的版权。

## 报告问题

请在 [Issues](https://github.com/IndelibleVivi/infra-field-guide/issues) 给出：相关章节或命令、OS 与工具版本、预期结果、实际结果，以及能重现问题的最小合成输入。步骤中的“运行在哪台机器”也很重要。价格或平台行为变化请附官方链接和查阅日期。

不要提交真实 token、Cookie、私钥、完整环境变量、主机清单、账号记录、私有路径或原始诊断报告。将主机换成 `example.com` / 文档保留 IP，将数据改成合成示例；保留错误类型和操作顺序即可。如果误把凭据公开，先撤销或轮换凭据；删掉评论不能让已经泄露的凭据恢复安全。

## 提交改动

1. 围绕一个具体问题开分支。教程要写出前提、执行机器、观察结果、失败时的停止点和恢复路径；不要只给一段命令。
2. 同步相应章节、agent 工单、示例和中英文首页。新的平台结论优先引用官方资料，并注明检查日期。
3. 用下面的检查验证改动。教程 shell 代码只做静态语法检查，不会在测试中执行防火墙、迁移或清理。
4. PR 说明原问题、改动后的行为、实际运行的检查，以及没有验证的环境。截图用合成数据，图示同时提交可编辑源。

```sh
python3 -m unittest discover -s tests -v
git diff --check
```

health 演示见 [工具说明](tools/README.md)。图的维护与渲染见 [diagram source](docs/diagrams/README.md)。真实服务器验收需要环境所有者授权，不属于贡献测试的默认步骤。

Windows 的 shell 静态检查使用 Git for Windows 随附的 Git Bash，请让它在 PATH 中优先于系统的 `bash.exe` / WSL 入口；CI 明确选择该路径，测试使用解析后的完整可执行路径，避免 Windows 的系统目录搜索再次选中 WSL。CLI 测试只向子进程传入测试用 Python 设置与 Windows 启动所需的 `SystemRoot`，不带入日常账号环境。

## English

Please describe the affected chapter or command, OS/tool versions, expected and actual behavior, and a small synthetic reproducer. Cite current official sources for changing platform behavior. Keep secrets, private hosts and raw operational data out of issues and pull requests. Run the checks above, update paired reader/agent surfaces, and state what you have actually verified. Contributions retain their authorship and use the license assigned to their material in [LICENSING.md](LICENSING.md).
