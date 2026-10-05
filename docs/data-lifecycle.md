# 数据保留与释放空间：先判断，再回收

[返回首页](../README.md) · [日常运维](03-operations.md) · [时间与时区](time-synchronization.md) · [给 agent 的数据工单](../agents/data-lifecycle.md)

## 这一页帮你做什么

磁盘快满了，你想“清一下”，但不知道哪些能删、删了会怎样。这篇帮你先判断数据的**性质**（原始数据、可重建缓存、日志、备份），再选合适的检查与回收方式；讲清楚 `df`、`du`、inode、以及“已删除但仍被打开”的文件为什么会让空间对不上；对 SQLite 单独说明 `DELETE` 与 `VACUUM`/WAL 的边界，以及额外空间、写锁和备份一致性；最后覆盖 journal、logrotate、备份保留的 owner 与恢复验证。释放空间依据已批准的保留策略与数据用途，不能因为名字像缓存就删除。

空间是否值得释放、释放哪一份，取决于这份数据属于谁、能否重建、有没有更权威的副本。**先分类，再动手。**

<details>
<summary>适用环境与验证范围</summary>
<p>以 Linux 为主；SQLite 部分以 SQLite 官方文档为准。挂载、权限、文件系统类型与 quota 会改变可用手段，需要在目标机上核实。</p>
<p>仓库在新建、可丢弃的合成数据库上验证了 DELETE 与 VACUUM 的空间变化，文内提供可复现代码。这是写实验库；没有在读者机器上删除、真空或回收任何真实数据。</p>
</details>

## 先读哪一段

| 眼前的问题 | 入口 |
| --- | --- |
| 哪些数据能删，哪些不能？ | [先给数据分类](#先给数据分类) |
| `df` 说满了，但 `du` 加起来没那么多 | [df、du 与 inode](#dfdu-与-inode) |
| 删了文件，空间却没回来 | [已删除但仍被打开的文件](#已删除但仍被打开的文件) |
| SQLite 删了行，文件还是那么大 | [SQLite：DELETE、VACUUM 与 WAL](#sqlitedeletevacuum-与-wal) |
| journal / 日志 / 备份怎么定保留？ | [日志、journal 与备份的保留](#日志journal-与备份的保留) |
| 怎么只读地看清楚现状？ | [只读检查](#只读检查) |

## 先给数据分类

回收空间前，先把目标数据贴到某一类。类别决定“能不能删、删之前要做什么”：

| 类别 | 特征 | 能否释放 | 前提 |
| --- | --- | --- | --- |
| 原始数据（唯一来源） | 用户上传、业务记录、还无法重建的采集结果 | 谨慎 | 必须已有可恢复的、经验证的副本，且 owner 同意 |
| 可重建缓存 | 由原始数据按确定规则重新生成（编译产物、缩略图、索引、拉取的镜像层） | 可以 | 确认“重建规则确定、代价可接受、重建不会丢输入” |
| 日志/诊断 | 运行痕迹，通常有保留策略 | 可以（按策略） | 确认保留窗口、审计/合规要求与安全停止点 |
| 备份 | 为恢复而保存的副本 | 按保留策略 | 至少保留一份在**不同故障域**、且**验证过可恢复** |

关键区分：**“我能重新生成它”** 才是缓存可删的依据，而不是“我看它像临时文件”。一个文件在 `/tmp` 或名字带 `cache`，都不足以证明它可重建。

## df、du 与 inode

“磁盘满了”要看两个维度：**空间（bytes）**和 **inode（文件数）**。大量小文件可以耗尽 inode，此时空间可能还有很多，但新文件已无法创建。

| 工具 | 它报告什么 | 注意 |
| --- | --- | --- |
| `df` | 文件系统的**整体**已用/可用（按挂载点） | 看的是文件系统，不是某个目录；`df -i` 看 inode |
| `du` | 某个目录树里文件占用的**磁盘块** | 默认不跟随符号链接、按块计算；同一次默认把硬链接只计一次 |
| `ls -s` | 单个文件的块数 | 稀疏文件与 `du` 的差异来源之一 |

三个常见“对不上”：

1. **`du` 小于 `df`**：扫描只覆盖该文件系统的一部分、权限不足、已删除但仍被打开的文件、快照或文件系统 metadata 占用。
2. **`du` 大于 `df`**：对硬链接**重复计算**——同一次默认只计一次，但若你**分开多次扫描再相加**（或用 `du -l` 让所有链接都计），同一个块会被数多次。
3. **空间还有却写不了**：inode 耗尽，或触碰其它限制（下文的准确 errno）。

`du` 对硬链接**默认只计一次**（用 `-l` 才会全部计），但对稀疏文件按**实际分配的块**算；因此“`ls -l` 显示的大小”与“实际占用”可能差很多。[du(1)](https://man7.org/linux/man-pages/man1/du.1.html)、[df(1)](https://man7.org/linux/man-pages/man1/df.1.html)

**对照 `df` 与 `du` 时**要保证两者在**同一个文件系统**范围内（`df` 按挂载点、`du -x` 不跨 fs），并注意权限不足、快照、以及“已删除但仍打开”的文件会让两者对不上；目录可读权限不足时 `du` 会少算，应保留 unknown 而不是当成“系统真的变小了”。

### 写失败的准确 errno 不要混同

“空间还有却写不了”有很多种原因，**不要把不同的错误混成一个 `ENOSPC`**：

- `ENOSPC`：确实没有可用块/inode。
- `EDQUOT`：磁盘配额超出（`df` 看着还有空间也会失败）。
- `EROFS`：文件系统是**只读**挂载，跟空间无关。

看真实报错（`errno` 或工具输出）再判断，别一律当成“磁盘满”。

## 已删除但仍被打开的文件

Linux 上删除一个文件时，**最后一个 hard link 被移除、且最后一个已打开的引用关闭**后，文件才可释放；内存映射、快照等还可能延长数据的保留。因此“`rm` 了但空间没回来”的一个常见原因是仍有进程打开着它：`df` 显示空间被占，`du` 却找不回来，因为路径已经没了。[unlink(2)](https://man7.org/linux/man-pages/man2/unlink.2.html)

典型场景：正在运行的服务把日志写到 `app.log`，你用 `rm app.log` “清理”，但服务持有打开的文件描述符；空间直到它关闭/重启/重开日志才释放。**正确做法通常是让服务轮转日志（logrotate 或应用自身），而不是 `rm`。**

检查“已删除但仍被打开”的文件（**有界**诊断：先缩到已确认的 PID 或目录，不要把扫描无限铺开）：

```sh
# 只读：针对已知服务 PID 检查它持有的已删除文件
pid=$(systemctl show --value -p MainPID example-app.service)
case "$pid" in
  ''|0|*[!0-9]*) echo "service not running; skip checks" ;;
  *) sudo lsof -nP -a -p "$pid" +L1 ;;
esac
```

`-a` 把 PID 与链接数筛选组合为 AND；单独使用 `lsof +L1` 会检查更多进程，`head` 只限制**输出**。若需硬性限定观察范围，也可对已确认的非零 PID 查看 `/proc/$pid/fd`。权限不足、PID 变化或仅查看主进程时，都可能漏掉持有者，缺口记为 unknown。

找到持有进程后，正确操作是让该进程**重新打开日志或重启**（按应用/服务的正常方式），而不是删除文件；恢复动作属于有副作用变更，需要单独授权与验收。

## SQLite：DELETE、VACUUM 与 WAL

SQLite 的空间回收有两个独立步骤，很多人把它们混为一谈。

- **`DELETE`** 删除行后，腾出的页通常进入**空闲页链表（freelist）留待复用**，文件大小**未必缩小**（更准确说：不一定立即还给文件系统）。是否在删除时物理缩减还取决于 **`auto_vacuum`** 设置。
- **`VACUUM`** 重建数据库文件，把空闲页真正还给文件系统，因此文件**可能**变小；但**不保证一跑就缩**（若本来就没有多少空闲页，收益有限），且代价见下。

```sql
-- 只读式观察（不改变数据）
PRAGMA freelist_count;   -- 空闲页数量
PRAGMA page_count;       -- 总页数
PRAGMA page_size;        -- 每页字节
PRAGMA auto_vacuum;      -- 影响删除时是否物理缩减
-- 空闲字节 ≈ freelist_count * page_size
```

### WAL 模式的边界

启用 **WAL（Write-Ahead Logging）** 后，写入先追加到 `-wal` 文件，直到发生 **checkpoint** 才合并回主库；因此“删了行”后空间可能仍体现在 `-wal` 里，甚至主库和 `-wal` 一起占用更多。`PRAGMA journal_mode` 报告当前模式（`delete`/`wal`/…），`DELETE` 在 `delete` 模式下走回滚日志，在 `wal` 模式下走 WAL 文件。

**checkpoint 是写入、会持锁的动作**，`TRUNCATE` 截断也可能被活跃 reader 阻塞；普通 checkpoint 通常**复用** WAL 而不缩文件。**不要随手删除 `-wal`/`-shm`**：`-wal` 可含已提交但未写回主库的数据，`-shm` 是共享的 WAL 索引。下面两条都属于需授权的写操作。

```sql
PRAGMA wal_checkpoint(PASSIVE);  -- 不等待 reader/writer，尽可能合并；可能返回 busy，不保证截断
PRAGMA wal_checkpoint(TRUNCATE); -- 合并并尝试截断；会被活跃 reader 阻塞，属于写+锁动作
```

WAL 的自动检查点由 `wal_autocheckpoint` 控制；`-wal` 长期很大可能是长读事务阻塞了检查点。这些都要在了解当前连接/事务状态后再处理。[SQLite WAL](https://sqlite.org/wal.html)、[PRAGMA](https://sqlite.org/pragma.html)

### VACUUM 的代价与替代

- 就地 `VACUUM` 在重建期间**可能需要相当于原库 2 倍的额外空闲空间**（不是仅 1 倍），空间紧张时可能失败；**不能**在事务里运行，且运行期间写操作被阻塞，生产上要选低峰并评估锁影响。
- 它可能改变 ROWID：如果表**没有 `INTEGER PRIMARY KEY`**，`VACUUM` 后行的 ROWID 可能变化——依赖 ROWID 的代码要当心。
- `VACUUM INTO '目标.db'` 把**整理后的副本**写到**新文件**，**不改原库**；但它是“写一个新文件”，**失败时不能当作备份**。
- 想要可恢复的备份，应使用 SQLite 的在线备份 API 或 `VACUUM INTO`（这两个方式产出的是一致副本），**而不是直接 `cp` 正在写入的库文件**；直接复制可能拿到不一致状态，也会漏掉 `-wal` 里的内容（除非同时正确处理 WAL）。[SQLite backup](https://sqlite.org/backup.html)、[lang_vacuum.html](https://sqlite.org/lang_vacuum.html)

> [!NOTE]
> **停下检查点：`DELETE` 后文件未必缩小，`VACUUM` 的回收收益也要先判断。**
> 若空闲页很快会被新数据复用，`VACUUM` 只是白费一次重写和锁。先看 `freelist_count` 与增长趋势，再决定要不要真空。备份永远在动 `VACUUM` 之前：**先确认有一份一致的、能恢复的备份。**

### 仓库本地量级验证（合成、可丢弃的实验库）

下面使用 Python 标准库，在自动创建的临时目录里写合成数据。`auto_vacuum=NONE` 与 rollback journal 把实验条件固定下来；退出后临时目录自动清理。**不要改成真实业务库路径。**

```python
import sqlite3
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="example-sqlite-space-") as directory:
    path = Path(directory) / "synthetic.db"
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA auto_vacuum=NONE")
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("CREATE TABLE samples (id INTEGER PRIMARY KEY, payload BLOB)")
        connection.executemany("INSERT INTO samples(payload) VALUES (zeroblob(800))", [()] * 1000)
        connection.commit()

        def report(stage):
            free = connection.execute("PRAGMA freelist_count").fetchone()[0]
            print(stage, "bytes=", path.stat().st_size, "free_pages=", free)

        print("SQLite", sqlite3.sqlite_version)
        report("filled")
        connection.execute("DELETE FROM samples")
        connection.commit()
        report("deleted")
        connection.execute("VACUUM")
        report("vacuumed")
        print("integrity:", connection.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        connection.close()
```

2026-10-05 在本地运行这段代码：填充后约 808 KiB，`DELETE` 后大小不变且出现空闲页；`VACUUM` 后为 8 KiB、空闲页归零，结构检查返回 `ok`。精确结果随 SQLite 版本与页大小变化，代码会打印实际版本。这只验证合成库的空间变化，不证明业务库的锁、恢复或生产回收效果。

## 日志、journal 与备份的保留

三类都应有**明确的 owner 和保留策略**，而不是临时手删。

### systemd journal

journal 可能是内存（volatile）或磁盘（persistent）存储。查看与限额：

```sh
sudo systemd-analyze cat-config systemd/journald.conf
sudo journalctl --disk-usage
sudo journalctl --list-boots
```

预算项（`SystemMaxUse=`、`SystemKeepFree=`、`RuntimeMaxUse=`、`MaxRetentionSec=`）决定 journal 的淘汰；它们是“按预算淘汰最旧”，**不是**替别的服务回收磁盘。急需释放旧归档且证据已保留时，才用 `sudo journalctl --rotate --vacuum-size=200M`——**这会不可逆删除最旧归档日志**，先说明丢失哪个窗口。journal 限额**管不到**应用自写日志、Docker JSON 日志或数据库 WAL，那些要另设轮转。[journalctl(1)](https://man7.org/linux/man-pages/man1/journalctl.1.html)、[journald.conf(5)](https://www.freedesktop.org/software/systemd/man/latest/journald.conf.html)

### logrotate

logrotate 的 owner 是 `/etc/logrotate.d/` 下的配置；它按规则轮转、压缩、删除旧日志，并可让服务重新打开日志文件（`create`/`postrotate`）。要点：

- 配置里 `rotate N` 决定保留几份；`copytruncate` 与 `create`+`postrotate` 处理“进程仍持有句柄”的方式不同。**`copytruncate` 在“拷贝完、截断前”有一个间隙，这期间写入的记录可能丢失**，选错还可能空间不释放，按上游 manpage 权衡。
- 轮转**不**等于备份；轮转后的旧日志仍在同一磁盘，除非另做异地/异盘。
- 修改前先 `logrotate -d`（debug）核对配置解析；**debug 不改变日志、也不改变 state 文件**，可以放心先看。

以已安装版本与上游文档为准。[logrotate 上游](https://github.com/logrotate/logrotate)

### 备份保留

备份的保留策略要同时满足 **RPO/RTO** 与**至少一份在不同故障域**，并且**验证过可恢复**。删掉旧备份前的底线是：确认“还留着的那份”确实能恢复（在隔离目录/测试实例里读回已知记录），而不是只看文件存在。**没有恢复验证的“唯一备份”不能当作已被保护。**

## 只读检查

**运行位置：待检查的 Linux VPS；只读。** 目标目录/数据库换成真实路径。输出可能含路径与数据，分享前脱敏。

```sh
# 空间与 inode（对所有相关挂载点分别看）
df -hT /
df -i /
findmnt -no SOURCE,FSTYPE,OPTIONS -T /var/lib/example

# 某目录占用（按一级子目录汇总；不跨文件系统）
sudo du -xhd1 /var/lib/example | sort -h

# 最大的若干文件（仍遍历 /var/log；tail 只限制输出，权限错误保留）
sudo find /var/log -xdev -type f -printf '%s\t%p\n' | sort -n | tail -20

# 已删除但仍被打开：用上文的已知 PID 检查，不以 head 代替限定范围

# journal 用量
sudo journalctl --disk-usage
```

SQLite 库的只读检查（**不要**在业务库上随手 `VACUUM`）：

```sh
sqlite3 -readonly /var/lib/example/app.db "PRAGMA journal_mode; PRAGMA freelist_count; PRAGMA page_count; PRAGMA page_size; PRAGMA auto_vacuum;"
```

用 [`-readonly`](https://sqlite.org/cli.html#command_line_options) 可以**避免目标不存在时悄悄建空库**。SQLite 3.22.0+ 只读打开 WAL 库时，`-wal`/`-shm` 已存在且可读，或目录允许创建它们即可；不可变数据库还有独立的 `immutable` 条件，不能把运行中的库冒充不可变。只读打开限制数据库写入，不保证零文件活动；权限或锁失败时保留错误，不为查看大小擅自停服务。[SQLite 只读 WAL](https://sqlite.org/wal.html#read_only_databases)

## 变更与恢复边界

释放空间是有副作用的操作。做之前必须能回答：

1. **这份数据属于谁？** 是原始数据、缓存、日志还是备份？owner 是否同意删？
2. **它能不能重建？** 依据是什么（确定的规则、上游副本）？重建代价可接受吗？
3. **有没有更好的副本？** 备份是否在**不同故障域**、是否**验证过可恢复**？
4. **回退是什么？** 删除后如何恢复？**按已批准的保留策略，允许明确不可恢复的过期数据被淘汰**（例如超出保留窗口的日志/缓存），前提是 owner 接受这项损失、且任何仍需恢复的数据已另有保留。但**唯一来源的原始数据**在无副本、无恢复路径时不要删。

明确**不做**：

- 不教无差别 `rm -rf`、`truncate -s 0` 或清空整个目录。
- 不以“看起来是缓存”作为删除依据；不可重建的数据要按 owner 已批准的保留策略与损失边界处理。
- 不删除正在被打开的数据库/日志文件来“腾空间”（见上文）。
- 不在没有一致备份的情况下就地 `VACUUM` 大库。
- 不动容器/存储内部目录、不删 Docker 镜像层目录当作通用清理。

安全的通用方向：先**只读**定位增长来源（哪个挂载点、哪个目录、哪类文件、是否 deleted-open），再用**该组件自己的机制**处理（journald 预算、logrotate、数据库 VACUUM/备份、包管理器清理、应用自身的保留设置），并在动手前记录恢复路径。

## 怎样算解决

验收记录写清：

- **现状证据**：`df -hT` / `df -i` 的目标挂载点前后对比；inode 是否也紧张。
- **数据性质**：释放的是哪一类、依据是什么、owner 是谁。
- **动作与恢复**：用了哪个组件的机制、可回退到什么程度、有没有保留必要证据。
- **产物/一致性**：涉及数据库的，做一次**业务层恢复验收**（读回已知记录/附件）。`PRAGMA integrity_check` 只检查库结构完整性，**不能替代完整业务恢复验收**；重型扫描（如全库 `integrity_check`）在繁忙库上要考虑负载影响，不是每次小清理都必须跑。

只说“删了一些文件，空间多了”不足以说明问题已解决——要看增长是否受控、是否触及根因，以及删除是否符合已批准的保留策略、仍需恢复的数据是否被保护。

相关：[日常运维](03-operations.md#5-日志与磁盘先查增长来源再限制)讲日志与磁盘；[时间与时区](time-synchronization.md)解释日志时间的跨机器对应。

## 来源与维护

查阅日期：**2026-10-05**。SQLite 机制按下列官方文档核对；本地执行范围是上面的合成库实验。没有在真实主机删除、真空或回收任何数据。

- [SQLite `VACUUM`](https://sqlite.org/lang_vacuum.html)：就地 `VACUUM` 可能需要相当于原库 **2 倍**的额外空闲空间（不是仅 1 倍）；`VACUUM INTO` 产出**一致副本**但写**新文件**，**失败时不能当备份**；表无 `INTEGER PRIMARY KEY` 时 ROWID 可能变；`auto_vacuum` 影响删除时是否物理缩减。
- [SQLite WAL](https://sqlite.org/wal.html)：checkpoint 通常**复用** WAL 而不缩文件，`TRUNCATE` 可能被活跃 reader 阻塞；不要随手删 `-wal`/`-shm`。
- [SQLite backup](https://sqlite.org/backup.html)：Backup API 与 `VACUUM INTO` 是一致的副本机制；纯 `cp` 运行中的主文件不可靠。
- [du(1)](https://man7.org/linux/man-pages/man1/du.1.html)、[df(1)](https://man7.org/linux/man-pages/man1/df.1.html)、[unlink(2)](https://man7.org/linux/man-pages/man2/unlink.2.html)：块与 inode 统计；**最后一个 hard link 移除且最后一个打开引用关闭后**才释放（其他 fs/快照边界按实际）。
- [journalctl(1)](https://man7.org/linux/man-pages/man1/journalctl.1.html)、[journald.conf(5)](https://www.freedesktop.org/software/systemd/man/latest/journald.conf.html)：journal 用量与预算。
- [SQLite CLI](https://sqlite.org/cli.html#command_line_options)：`-readonly` 打开方式。
- [logrotate 上游手册](https://github.com/logrotate/logrotate/blob/main/logrotate.8.in)：轮转、压缩、保留与 `copytruncate` 的丢记录窗口。

**想一想：你在服务运行中删掉了它的日志文件，`df` 立刻少了很多吗？为什么？**

<details>
<summary>查看答案</summary>
<p>通常不会立刻减少。目录项被移除，但服务仍持有该文件的打开描述符，数据块在其关闭前不释放；要等进程关闭/重新打开日志，或按应用方式轮转后，空间才真正回收。应优先用 logrotate 或应用的日志机制，而不是直接 `rm`。</p>
</details>
