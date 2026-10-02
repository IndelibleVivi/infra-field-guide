# Health · 先看一次资源余量

`health.py` 把 Linux 资源指标存成 JSON，再生成一张可离线打开的 HTML 看板。只使用 Python 3.9+ 标准库，不需要 pip、sudo、服务安装或浏览器扩展。它不持续监控，不发送告警，也不验证服务可用性。

## 先看看成品

**[打开 Health 交互模拟仪表盘 →](https://indeliblevivi.github.io/infra-field-guide/health/demo/)**

不用终端，先切换五种合成场景：日常运行、内存吃紧、磁盘快满、小文件堆积、采集缺失。拖动时间轴或回放一小时，数值、曲线和状态提示会一起变化；点指标可切换趋势，图表可看最近 15 分钟或 1 小时。缺失读数留空，不画成零。回放可以暂停、从头开始，切换场景和手动调时间会停止回放。

模拟仪表盘是阅读站的教学界面，**不是你的机器，也没有在线采集**。构建器由仓库 fixture 生成合成序列，交给 `health.py` 的同一套校验、格式化与状态判断，再由浏览器回放。它没有后台服务，也不提供导入真实报告的入口。

下面的 CLI 生成的是固定离线快照，不含时间轴或脚本。可以先[打开同一 renderer 生成的合成快照](https://indeliblevivi.github.io/infra-field-guide/health/snapshot/)，再运行命令复现。模拟界面的源与构建关系见[阅读站维护](../site/README.md#health-模拟仪表盘)。

## 先运行合成演示

在仓库根目录执行。macOS、Linux、Windows 上均可运行合成演示与渲染；下面的 `mkdir -p` 使用 POSIX shell，Windows 可手动创建 `reports` 文件夹。

```sh
mkdir -p reports
python3 tools/health.py collect --demo -o reports/health-demo.json
python3 tools/health.py render reports/health-demo.json -o reports/health-demo.html
```

在文件管理器中双击 `reports/health-demo.html`，用浏览器打开即可。页面包含内嵌 CSS，没有外部资源、脚本、网络请求或自动刷新。数据来自 [合成 fixture](../examples/health-demo.json)，**不读取本机指标**，也不对应真实机器。演示故意保留固定采集时间，因此会随着时间推移显示为历史快照。

输出文件必须尚不存在；再次运行请换一个文件名。工具不覆盖旧快照或输入 JSON。`reports/` 已被仓库忽略，请勿把真实采集结果提交到 Git。输出目录需要先创建。

## 在已授权的 Linux 机器采集

将这个仓库或 `tools/health.py` 放在你有权检查的 Linux 机器上，再在**那台机器**运行：

```sh
mkdir -p reports
python3 tools/health.py collect -o reports/health-snapshot.json
python3 tools/health.py render reports/health-snapshot.json -o reports/health-snapshot.html
```

也可只复制 JSON 到本机后渲染；移动前自行确认数据适合离开服务器。此工具不建立 SSH 连接，也不提供上传功能。

完整 CLI：

```text
python3 tools/health.py collect [--demo] [-o OUTPUT.json]
python3 tools/health.py render INPUT.json -o OUTPUT.html
python3 tools/health.py --help
```

`collect` 不给 `-o` 时将 JSON 写到 stdout；`--demo` 从仓库 fixture 读取数据，不更新时间或伪装成真实采集。只复制单个脚本时，真实采集和渲染仍可用，`--demo` 还需要保持 `../examples/health-demo.json` 的相对位置。非 Linux 的真实 `collect` 明确报错并返回状态码 `2`；不要把测试环境参数当作跨平台采集支持。

## 实际读取什么

| 指标 | 读取来源 | 计算与范围 |
| --- | --- | --- |
| CPU load | `/proc/loadavg` 前 3 项、`/proc/stat` 的 `cpuN` 行名 | 1/5/15 分钟 load；逻辑 CPU 数来自 `cpuN` 数量。忽略 loadavg 后续 PID 等字段，不采集 CPU utilization |
| RAM | `/proc/meminfo` 的 `MemAvailable`、`MemTotal` | 字节 = kB × 1024；不以 MemFree 替代缺失的 MemAvailable |
| Swap | 同文件的 `SwapTotal`、`SwapFree` | used = total − free；total 为 0 表示未配置，不是已 OOM |
| 根文件系统字节 | `os.statvfs('/')` | total = blocks × frsize；free 与普通用户 available 分开保留，used = total − free |
| 根文件系统 inodes | 同一次 `statvfs` | total、free、普通用户 available；总量为 0 时不能推断有可用 inode，显示 unknown |
| Uptime | `/proc/uptime` 首项 | 启动以来的秒数，不是某服务的 uptime |
| Memory PSI | `/proc/pressure/memory` | some/full 的 avg10、avg60、avg300（百分比）与 total（微秒）；接口缺失时 unknown |

不读取 hostname、IP、进程目录/命令行、环境变量、凭据、日志、挂载清单或账号。不会调用 shell/subprocess、联网、申请提权或改变系统设置；除显式输出文件外不写状态。采集是短暂的顺序读取，不是所有指标同一瞬间的原子快照。内存与 swap 各自读取一次 meminfo。

只检查 `/` 所在文件系统；另一个挂载点的数据盘不在覆盖范围内。容器中的 `/proc`、CPU 数和文件系统可能具有不同的可见范围；工具未读取 cgroup 配额，不能用它判断容器限制或宿主机全部资源。采集失败不会隐藏缺口：对应指标保存为 `{"error": "…"}`，其状态为 **unknown**。PSI 是否可用取决于内核配置和权限。

## 怎样读提示

这些阈值是帮助入门的固定启发式，不是 Linux 内核标准、SLA 或故障结论。等于阈值也会触发提示。

| 指标 | 需关注 | 余量很低 / 其他说明 |
| --- | --- | --- |
| CPU load | 5 分钟 load ≥ 逻辑 CPU 数 | Load 包含运行需求和不可中断等待；不是 utilization 百分比，也可能由 I/O 等待推高 |
| RAM | available / total ≤10% | ≤5% 加重；结合趋势与业务症状，不能仅凭此认定 OOM |
| Swap | used / total ≥50% | 历史 swap 使用不证明正在频繁换页；无 swap 为信息提示 |
| 根文件系统字节、inodes | 普通用户 available / total ≤15% | ≤5% 加重；保留给特权用户的资源不算普通用户可用余量 |
| Memory PSI | some avg60 ≥10% 或 full avg60 ≥1% | some 表示有任务因内存受阻，full 表示所有非空闲任务同时受阻的时间占比 |
| Uptime | 无阈值，只展示 | 不代表服务、网络、数据或备份健康 |

每个状态由渲染器重新计算，不信任输入中的颜色或“健康”标签。未触及阈值只说明这项数值；缺失数据始终未知。整体区域同时列出“需关注”和“未知”数量。

看板显示 UTC 采集时间、UTC HTML 生成时间和**生成时**的数据年龄。超过 15 分钟标注“历史快照”；这是本工具的阅读提醒，不是通用失效期限。以后打开该 HTML，年龄文字不会自动更新；请始终以采集时间判断。采集时间晚于渲染时间时明确提示时钟异常。

## JSON 契约与错误

[合成 fixture](../examples/health-demo.json) 是 schema v1 的完整示例。顶层需要整数 `schema_version: 1`、UTC `collected_at`（`YYYY-MM-DDTHH:MM:SSZ`）、`source.kind`（`linux-procfs` 或 `synthetic`）、非空 `source.description` 和 `metrics` 对象。`source` 是数据提供者的声明，没有认证或真实性保证。

整个指标缺失会显示 unknown；已提供但字段不齐、数值越界、错误类型、NaN/Infinity、未知 schema 或无效时间则拒绝渲染并返回状态码 `2`。字节和 inode 必须是非负整数；总量、逻辑 CPU 数、范围关系也会校验。一般文件/JSON 错误同样返回 `2`；成功输出返回 `0`。资源阈值触发和 unknown 不改变成功退出码，此 CLI 不是告警探针。

所有外部文本都做 HTML 转义，并用 CSP 限制页面能力；看板不执行输入中的 HTML。工具不会自动采集身份信息，但自行添加到 `source.description` 的内容仍会出现在 JSON/HTML 中；分享前检查输入与结果，不要写个人路径、账号或凭据。

## 验证范围与来源

```sh
python3 -m unittest discover -s tests -p 'test_health.py' -v
```

测试使用临时的合成 `/proc` 文本、模拟 `statvfs` 和合成 JSON，覆盖公式、阈值、未知/损坏、非 Linux 拒绝、字节与 inode、时间语义、HTML 转义、CLI 演示 roundtrip 与保护既有文件。**不读取测试机器的真实 `/proc` 或文件系统统计，也不连接任何 VPS。** 2026-10-02 的[跨平台 CI](https://github.com/IndelibleVivi/infra-field-guide/actions/runs/36984498352)已在 Linux / Windows、Python 3.9 / 3.13 上通过测试与合成演示，并在 Linux runner 上完成真实资源采集和 HTML 渲染。未对用户的 VPS 执行采集。固定离线 HTML 的浏览器布局未单独验收；交互模拟页于同日另做了 1440px 桌面与 390px 手机视口检查，覆盖场景／指标切换、时间轴键盘操作、回放终止、未知值留空和无整页横向溢出。浏览器模拟尺寸不等于真实手机硬件验收。

接口定义参考一手文档，查阅日期 **2026-10-02**：

- [Linux kernel · /proc](https://docs.kernel.org/filesystems/proc.html)：meminfo、loadavg、uptime 等字段。
- [Linux man-pages · proc_loadavg(5)](https://man7.org/linux/man-pages/man5/proc_loadavg.5.html)：load 包含运行队列与不可中断 I/O 等待，不等于 CPU 使用率。
- [Linux kernel · PSI](https://docs.kernel.org/accounting/psi.html)：some/full、时间窗口与微秒累计值。
- [Python · os.statvfs](https://docs.python.org/3/library/os.html#os.statvfs)：文件系统字节、普通用户余量和 inode 字段。
