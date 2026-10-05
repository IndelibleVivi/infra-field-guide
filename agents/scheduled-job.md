# 工单 · 定时任务的触发、补跑与并发

依据：[定时任务](../docs/scheduled-jobs.md)、[时间与时区](../docs/time-synchronization.md)与[共用执行规则](README.md#所有工单共用的执行规则)。

```text
目标：<准确机器/服务/任务；VPS 可使用已核实的 SSH alias>
现象：<没按时跑 / 错过未补 / 重复执行 / 上次没跑完又触发 / 结果未知 / 其他>
用途与可接受影响：<按业务填写；有外部副作用的动作要特别标明>
现有授权：<默认只读；如已授权新增或修改 timer/cron，记录精确 unit、文件与边界>

先确定执行位置、调度器种类（systemd timer / cron / 应用内部调度）与实际表达式。
用 systemd-analyze calendar 之类的只读解析确认“下一次、接下来几次”具体触发时刻，
并确认它按哪个时区解释，不靠直觉推断夏令时附近的当地钟点。
systemd 的时区直接附在 OnCalendar= 表达式末尾；不存在 timer 的 Timezone= 选项。
注意 AccuracySec 默认 1min 等触发精度，触发不是精确到秒的保证。
cron 按机器上实际的 daemon、包版本与手册核对，不能把 cronie 的扩展直接套到 Vixie 等实现，
未核实前不给通用 CRON_TZ 配置。

区分日历触发与间隔触发：Persistent= 只对 OnCalendar= 有补跑含义；
inactive 期间至少漏一次时，激活时安排一次补跑（不是逐次），仍受 RandomizedDelaySec 影响、
不一定立即完成；业务要补哪些日期由任务自身设计。
同 manager 同 service 仍 active/activating 时，新触发与同 unit 手动 start 都不会制造并发；
真正的旁路是直接跑程序、别的 service/模板 instance、别的 manager 或机器；RemainAfterExit=true 会长期 active。

先别默认上分布式锁：优先一个真实调度 owner 与可查询的 job 状态；
确需共享写数据时，优先应用已支持的事务/唯一约束。跨机器时先问：有几个调用者？
flock 是 advisory，只挡住同样申请它的进程，不阻止别人绕过；
NFS/SMB 行为按协议/挂载/内核变，仅共享路径不证明跨机互斥。
任务提交前保留原任务定位与幂等键；超时/断线/换 harness 后先查原任务，结果未知时先定位、不重发写任务。

只读检查优先：list-timers、status、show（NextElapseUSecRealtime/LastTriggerUSec/Persistent）、journalctl。
Result=success 与退出码 0 只证明进程级成功；单独验收任务记录与产物（文件/记录/外部状态、去重计数）。
Type=oneshot 的 TimeoutStartSec 默认禁用；若需时间上限要显式设置并解释停止/恢复。

交付：
1. 触发语义、时区、接下来几次触发时刻；错过/关机的补跑行为（含未验证项）。
2. 并发边界与可能的隐式重叠调用者；现有锁/幂等/去重是否成立。
3. 任务记录与产物在哪里，如何做一次不产生副作用的验收。
4. 若要新增/修改调度：准确配置、按所用版本核实的生效动作（daemon-reload 是否重算触发、timer 是否需单独重启）、
   回退与验收；Persistent 可能立即触发，动手前先查目标 service 是否在跑；有外部副作用要考虑幂等。
5. 在已有授权内完成；未授权的安装/启用/试跑先给具体候选。

回报：实际在哪执行；触发与补跑语义结论；并发/去重边界；产物验收结果；
      哪些是配置静态推断、哪些经真实触发验证；未验证什么；如何接手。
只展示合成或脱敏配置；真实机器、账号、路径与运行记录留在 owner 私有位置，不提交公开仓库。
```
