#!/usr/bin/env python3
"""Read-only Linux resource snapshots and an offline HTML report. Stdlib only."""

import argparse
from datetime import datetime, timezone
import html
import json
import math
import os
from pathlib import Path
import re
import sys


SCHEMA_VERSION = 1
METRICS = ("cpu", "memory", "swap", "root_bytes", "root_inodes", "uptime", "memory_psi")
LABELS = {"ok": "未触及阈值", "warning": "需关注", "critical": "余量很低",
          "unknown": "unknown · 未知", "info": "供参考"}


def utc_now():
    return datetime.now(timezone.utc)


def utc_text(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def number(value, name, integer=False, positive=False, maximum=None):
    allowed = (int,) if integer else (int, float)
    if type(value) not in allowed or (type(value) is float and not math.isfinite(value)):
        raise ValueError(name + " 必须是有限数值" + ("整数" if integer else ""))
    if value < 0 or (positive and value == 0) or (maximum is not None and value > maximum):
        raise ValueError(name + " 超出有效范围")
    return value


def validate_metric(name, value):
    if not isinstance(value, dict):
        raise ValueError(name + " 必须是对象")
    if "error" in value:
        if set(value) != {"error"} or not isinstance(value["error"], str) or not value["error"].strip():
            raise ValueError(name + " 的 unknown 记录必须只含非空 error 文本")
        return value
    fields = {
        "cpu": ("load_1m", "load_5m", "load_15m", "logical_cpus"),
        "memory": ("available_bytes", "total_bytes"),
        "swap": ("used_bytes", "total_bytes"),
        "root_bytes": ("available_bytes", "free_bytes", "total_bytes"),
        "root_inodes": ("available", "free", "total"),
        "uptime": ("seconds",),
        "memory_psi": ("some", "full"),
    }[name]
    if set(value) != set(fields):
        raise ValueError(name + " 字段缺失或不属于 schema v1")
    if name == "memory_psi":
        for kind in fields:
            row = value[kind]
            if not isinstance(row, dict) or set(row) != {"avg10", "avg60", "avg300", "total_us"}:
                raise ValueError("memory_psi 字段不完整")
            for window in ("avg10", "avg60", "avg300"):
                number(row[window], "PSI " + window, maximum=100)
            number(row["total_us"], "PSI total_us", integer=True)
        for key in ("avg10", "avg60", "avg300", "total_us"):
            if value["full"][key] > value["some"][key]:
                raise ValueError("PSI full 不能超过 some")
        return value
    for key in fields:
        number(value[key], name + "." + key,
               integer=name not in ("cpu", "uptime") or key == "logical_cpus",
               positive=key == "logical_cpus" or (key.startswith("total") and name != "swap"))
    if name in ("memory", "swap", "root_bytes", "root_inodes"):
        total_key = "total" if name == "root_inodes" else "total_bytes"
        if any(value[key] > value[total_key] for key in fields if key != total_key):
            raise ValueError(name + " 的部分值超过总量")
    if name in ("root_bytes", "root_inodes"):
        suffix = "_bytes" if name == "root_bytes" else ""
        if value["available" + suffix] > value["free" + suffix]:
            raise ValueError(name + " available 不能超过 free")
    return value


def validate_snapshot(snapshot):
    if not isinstance(snapshot, dict) or type(snapshot.get("schema_version")) is not int:
        raise ValueError("快照必须包含整数 schema_version")
    if snapshot["schema_version"] != SCHEMA_VERSION:
        raise ValueError("仅支持 schema_version 1")
    stamp = snapshot.get("collected_at")
    if not isinstance(stamp, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp):
        raise ValueError("collected_at 必须是 UTC 时间 YYYY-MM-DDTHH:MM:SSZ")
    try:
        datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("collected_at 不是有效日期") from exc
    source = snapshot.get("source")
    if not isinstance(source, dict) or source.get("kind") not in ("linux-procfs", "synthetic"):
        raise ValueError("source.kind 必须是 linux-procfs 或 synthetic")
    if not isinstance(source.get("description"), str) or not source["description"].strip():
        raise ValueError("source.description 必须是非空文本")
    metrics = snapshot.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("快照缺少 metrics 对象")
    # Missing whole metrics remain unknown; malformed supplied values are rejected.
    normalized = {name: validate_metric(name, metrics.get(name, {"error": "快照未提供这一指标"}))
                  for name in METRICS}
    return {"schema_version": SCHEMA_VERSION, "collected_at": stamp,
            "source": source, "metrics": normalized}


def parse_cpu(load_text, stat_text):
    parts = load_text.split()
    if len(parts) < 3:
        raise ValueError("缺少 load averages")
    cpus = {line.split()[0] for line in stat_text.splitlines() if re.match(r"^cpu\d+\s", line)}
    return {"load_1m": float(parts[0]), "load_5m": float(parts[1]),
            "load_15m": float(parts[2]), "logical_cpus": len(cpus)}


def parse_meminfo(text, keys):
    values = {}
    for line in text.splitlines():
        key, sep, rest = line.partition(":")
        if sep and key in keys:
            if key in values or not re.fullmatch(r"\s*\d+\s+kB\s*", rest):
                raise ValueError("内存字段无效")
            values[key] = int(rest.split()[0]) * 1024
    if set(values) != set(keys):
        raise ValueError("内存字段缺失")
    return values


def parse_memory(text):
    values = parse_meminfo(text, ("MemTotal", "MemAvailable"))
    return {"total_bytes": values["MemTotal"], "available_bytes": values["MemAvailable"]}


def parse_swap(text):
    values = parse_meminfo(text, ("SwapTotal", "SwapFree"))
    return {"total_bytes": values["SwapTotal"], "used_bytes": values["SwapTotal"] - values["SwapFree"]}


def parse_psi(text):
    result = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] not in ("some", "full") or parts[0] in result:
            raise ValueError("PSI 行无效")
        pairs = [part.split("=", 1) for part in parts[1:]]
        if any(len(pair) != 2 for pair in pairs):
            raise ValueError("PSI 字段无效")
        fields = dict(pairs)
        if len(pairs) != 4 or set(fields) != {"avg10", "avg60", "avg300", "total"}:
            raise ValueError("PSI 字段缺失")
        result[parts[0]] = {key: float(fields[key]) for key in ("avg10", "avg60", "avg300")}
        result[parts[0]]["total_us"] = int(fields["total"])
    return result


def capture(name, reader):
    try:
        return validate_metric(name, reader())
    except OSError:
        return {"error": "读取不可用：文件缺失、权限不足或系统不支持"}
    except (ValueError, UnicodeError, IndexError):
        return {"error": "数据不可用：字段缺失、格式损坏或数值不合理"}


def collect_snapshot(proc_root=Path("/proc"), statvfs=None, system=None, now=None):
    """Test seams accept a synthetic proc directory and a fake statvfs callable."""
    if (sys.platform if system is None else system) != "linux":
        raise ValueError("live collect 仅支持 Linux；本系统可使用 collect --demo 或 render")
    proc_root = Path(proc_root)

    def read(name):
        return (proc_root / name).read_text(encoding="ascii")

    metrics = {
        "cpu": capture("cpu", lambda: parse_cpu(read("loadavg"), read("stat"))),
        "memory": capture("memory", lambda: parse_memory(read("meminfo"))),
        "swap": capture("swap", lambda: parse_swap(read("meminfo"))),
        "uptime": capture("uptime", lambda: {"seconds": float(read("uptime").split()[0])}),
        "memory_psi": capture("memory_psi", lambda: parse_psi(read("pressure/memory"))),
    }
    try:
        fs = (os.statvfs if statvfs is None else statvfs)("/")
    except OSError:
        metrics["root_bytes"] = metrics["root_inodes"] = {"error": "根文件系统统计不可用"}
    else:
        metrics["root_bytes"] = capture("root_bytes", lambda: {
            "total_bytes": fs.f_blocks * fs.f_frsize, "free_bytes": fs.f_bfree * fs.f_frsize,
            "available_bytes": fs.f_bavail * fs.f_frsize})
        metrics["root_inodes"] = capture("root_inodes", lambda: {
            "total": fs.f_files, "free": fs.f_ffree, "available": fs.f_favail})
    return validate_snapshot({"schema_version": SCHEMA_VERSION,
                              "collected_at": utc_text(now or utc_now()),
                              "source": {"kind": "linux-procfs", "description": "Linux /proc 与 statvfs(/) 顺序读取"},
                              "metrics": metrics})


def remaining_status(available, total, warning):
    if available * 100 <= total * 5:
        return "critical"
    return "warning" if available * 100 <= total * warning else "ok"


def assess(name, value):
    if "error" in value:
        return "unknown"
    if name == "cpu":
        return "warning" if value["load_5m"] >= value["logical_cpus"] else "ok"
    if name == "memory":
        return remaining_status(value["available_bytes"], value["total_bytes"], 10)
    if name == "swap":
        if value["total_bytes"] == 0:
            return "info"
        return "warning" if value["used_bytes"] * 2 >= value["total_bytes"] else "ok"
    if name == "root_bytes":
        return remaining_status(value["available_bytes"], value["total_bytes"], 15)
    if name == "root_inodes":
        return remaining_status(value["available"], value["total"], 15)
    if name == "memory_psi":
        return "warning" if value["some"]["avg60"] >= 10 or value["full"]["avg60"] >= 1 else "ok"
    return "info"


def byte_text(value):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if value < 1024 or unit == "PiB":
            return f"{value:,.1f} {unit}"
        value /= 1024


def duration_text(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{days} 天 {hours:02d}:{minutes:02d}:{seconds:02d}"


def metric_display(name, value):
    titles = {"cpu": "CPU load", "memory": "RAM 可用余量", "swap": "Swap 使用",
              "root_bytes": "根文件系统 /", "root_inodes": "根文件系统 inodes",
              "uptime": "Uptime", "memory_psi": "Memory PSI"}
    notes = {
        "cpu": "5 分钟 load ≥ 逻辑 CPU 数时提示。Load 是运行队列与不可中断等待的负载，不是 CPU utilization；I/O 等待也可能推高它。",
        "memory": "MemAvailable 是无需 swap 可供新应用使用的估计。可用 ≤10% 提示，≤5% 加重；不是 MemFree，也不是 OOM 诊断。",
        "swap": "使用 ≥50% 时提示复查 RAM 与 PSI；已有 swap 使用不证明正在频繁换页。无 swap 不等于已发生 OOM。",
        "root_bytes": "普通用户可用 ≤15% 提示，≤5% 加重。可用量扣除了保留块；占用量为 total − free。只检查 / 所在文件系统。",
        "root_inodes": "普通用户可用 ≤15% 提示，≤5% 加重。字节够用时 inode 仍可能耗尽；0 总量或不支持的统计视为 unknown。",
        "uptime": "本次读取时系统启动后的秒数；不代表某项服务持续可用，也不能证明服务或备份健康。",
        "memory_psi": "60 秒平均 some ≥10% 或 full ≥1% 时提示。Some 是有任务受阻的时间占比，full 是所有非空闲任务同时受阻；缺失不按零处理。",
    }
    if "error" in value:
        return titles[name], "—", value["error"], notes[name], None
    bar = None
    if name == "cpu":
        main = f'{value["load_5m"]:.2f}'
        detail = f'5 分钟 load · {value["logical_cpus"]} 个逻辑 CPU；1 / 5 / 15 分钟：{value["load_1m"]:.2f} / {value["load_5m"]:.2f} / {value["load_15m"]:.2f}'
    elif name in ("memory", "root_bytes"):
        available, total = value["available_bytes"], value["total_bytes"]
        main = byte_text(available)
        detail = f'可用 {available / total:.1%} · 总计 {byte_text(total)}'
        if name == "root_bytes":
            detail += f' · 已占用 {byte_text(total - value["free_bytes"])}'
        bar = (100 * (1 - available / total), "不可用比例（含保留量）" if name == "root_bytes" else "非可用比例")
    elif name == "swap":
        total, used = value["total_bytes"], value["used_bytes"]
        main = "未配置" if total == 0 else byte_text(used)
        detail = "总量为 0；需结合内存余量判断" if total == 0 else f'已用 {used / total:.1%} · 总计 {byte_text(total)}'
        if total:
            bar = (100 * used / total, "已用比例")
    elif name == "root_inodes":
        main = f'{value["available"]:,}'
        detail = f'普通用户可用 {value["available"] / value["total"]:.1%} · 总计 {value["total"]:,} · 已占用 {value["total"] - value["free"]:,}'
        bar = (100 * (1 - value["available"] / value["total"]), "不可用比例（含保留量）")
    elif name == "uptime":
        main, detail = duration_text(value["seconds"]), "系统运行时长 · 单次观测"
    else:
        main = f'{value["some"]["avg60"]:.2f}%'
        detail = f'some / full：10s {value["some"]["avg10"]:.2f}% / {value["full"]["avg10"]:.2f}%；60s {value["some"]["avg60"]:.2f}% / {value["full"]["avg60"]:.2f}%；300s {value["some"]["avg300"]:.2f}% / {value["full"]["avg300"]:.2f}%'
    return titles[name], main, detail, notes[name], bar


CSS = """
:root{color-scheme:light;--ink:#18342e;--muted:#52675f;--line:#d8e1d9;--paper:#f5f3eb}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 system-ui,-apple-system,'Segoe UI',sans-serif}
main{max-width:1220px;margin:auto;padding:48px 28px}header{border-top:5px solid var(--ink);padding-top:22px}
.eyebrow{font-size:12px;letter-spacing:.14em;font-weight:750;text-transform:uppercase}h1{font-size:clamp(32px,5vw,58px);line-height:1.12;margin:16px 0}h2{font-size:18px;margin:0}
.intro{max-width:760px;color:var(--muted)}.strip{display:flex;gap:16px 36px;flex-wrap:wrap;margin:28px 0;padding:20px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.strip p{margin:0}.meta{font-size:13px;color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.card{background:#fffef8;border:1px solid var(--line);border-radius:14px;padding:24px;min-width:0}.card-top{display:flex;align-items:start;justify-content:space-between;gap:8px}
.badge{display:inline-block;white-space:nowrap;border-radius:5px;padding:3px 7px;font-size:11px;font-weight:750;background:#e8efeb;color:#325948}
.warning .badge{background:#fff0cc;color:#805000}.critical .badge{background:#fbe3d9;color:#95351c}.unknown .badge{background:#e9e9ed;color:#505460}.info .badge{background:#e8eef0;color:#3d5d6b}
.value{font-size:clamp(25px,3vw,37px);font-weight:720;letter-spacing:-.03em;margin:20px 0 5px;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
.detail{min-height:54px;font-size:13px;color:var(--muted);overflow-wrap:anywhere}.note{font-size:12px;line-height:1.8;border-top:1px solid var(--line);padding-top:14px;margin-top:16px;color:var(--muted)}
.bar{height:6px;background:#e5ebe5;border-radius:4px;overflow:hidden;margin-top:18px}.bar span{display:block;height:100%;background:#668675}.warning .bar span{background:#c58a26}.critical .bar span{background:#ba5436}
.bar-label{font-size:11px;color:var(--muted)}.summary{font-weight:750;margin-bottom:18px}.disclaimer{background:#e9eee5;border-left:4px solid #758b68;padding:18px 22px;margin:24px 0;font-size:14px}.time-warning{color:#8a451d}
footer{padding:24px 0;font-size:12px;color:var(--muted);overflow-wrap:anywhere}code{font-size:12px}strong{font-weight:750}
@media(max-width:1000px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){main{padding:24px 16px}.grid{grid-template-columns:1fr}.card{padding:20px}}
@media print{body{background:white}main{padding:0}.card{break-inside:avoid}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""


def render_snapshot(snapshot, now=None):
    snapshot = validate_snapshot(snapshot)
    now = now or utc_now()
    collected = datetime.strptime(snapshot["collected_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    age = (now - collected).total_seconds()
    age_text = "采集时间晚于渲染时间：请核对两端时钟" if age < 0 else f"生成 HTML 时的数据年龄：{duration_text(age)}"
    age_label = "时钟异常" if age < 0 else ("历史快照（超过 15 分钟）" if age > 900 else "近期快照（仍非实时）")
    escape = html.escape
    cards, statuses = [], []
    for name in METRICS:
        value = snapshot["metrics"][name]
        status = assess(name, value)
        statuses.append(status)
        title, main, detail, note, bar = metric_display(name, value)
        bar_html = "" if bar is None else f'<div class="bar"><span style="width:{bar[0]:.2f}%"></span></div><div class="bar-label">{escape(bar[1])} {bar[0]:.1f}%</div>'
        cards.append(f'<article class="card {status}"><div class="card-top"><h2>{escape(title)}</h2><span class="badge">{LABELS[status]}</span></div><p class="value">{escape(main)}</p><div class="detail">{escape(detail)}</div>{bar_html}<p class="note">{escape(note)}</p></article>')
    attention = statuses.count("warning") + statuses.count("critical")
    unknown = statuses.count("unknown")
    summary = f"{attention} 项需关注 · {unknown} 项未知"
    if not attention and not unknown:
        summary += " · 已测项目未触及提示阈值"
    source = snapshot["source"]
    synthetic = '<div class="disclaimer"><strong>合成演示数据</strong> · 所有数值均为编造的教学输入，不能用于判断任何机器的健康。</div>' if source["kind"] == "synthetic" else ""
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>资源快照 · Infra Field Guide</title><style>{CSS}</style></head>
<body><main><header><div class="eyebrow">Infra Field Guide / Offline resource snapshot</div>
<h1>把资源余量看清楚。</h1><p class="intro">单次、只读、离线的资源观察。没有自动刷新、后台采集或外部请求。提示阈值帮助定位下一步，不是对整台机器或业务的健康承诺。</p></header>
{synthetic}<section class="strip" aria-label="快照时间与来源"><div><p class="meta">采集时间 · UTC</p><p>{escape(snapshot["collected_at"])}</p></div><div><p class="meta">快照时效</p><p class="time-warning">{age_label}</p></div><div><p class="meta">数据来源</p><p>{escape(source["kind"])}</p></div></section>
<p class="meta">{age_text}。年龄固定在 HTML 生成时；以后打开此文件，仍需按采集时间判断时效。</p>
<p class="summary">{summary}</p><section class="grid" aria-label="资源指标">{"".join(cards)}</section>
<aside class="disclaimer"><strong>如何继续</strong> · 关注余量、趋势与业务症状。unknown 表示证据不足；一次快照无法诊断 OOM、识别泄漏、检查服务/备份或验证网络。容器中的 /proc、CPU 数与 / 可能反映不同范围，不能据此推断容器配额。所有阈值都是本工具的教学提示，需结合工作负载判断。</aside>
<footer>Schema v{SCHEMA_VERSION} · HTML 生成于 {utc_text(now)}<br>来源说明：{escape(source["description"])}<br>本工具不主动采集 hostname、IP、进程列表、环境变量或凭据；自行添加的说明文本仍会展示。若 JSON 来自他人，请核对其来源。</footer></main></body></html>'''


def load_snapshot(path):
    # Python's JSON decoder otherwise accepts non-standard NaN / Infinity.
    def invalid_constant(_):
        raise ValueError("JSON 不允许 NaN 或 Infinity")

    return validate_snapshot(json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=invalid_constant))


def main(argv=None):
    parser = argparse.ArgumentParser(description="只读 Linux 资源快照与离线 HTML；无需依赖、不联网")
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect", help="读取 Linux /proc 和 statvfs(/)，或输出合成演示")
    collect.add_argument("--demo", action="store_true", help="读取仓库合成 fixture，不采集本机；保留示例采集时间")
    collect.add_argument("-o", "--output", type=Path, help="写入新的 JSON 文件；省略则 stdout")
    render = sub.add_parser("render", help="从 JSON 生成不联网的单文件 HTML")
    render.add_argument("input", type=Path, help="schema v1 快照 JSON")
    render.add_argument("-o", "--output", type=Path, required=True, help="新的 HTML 文件路径")
    args = parser.parse_args(argv)
    try:
        if args.command == "collect":
            snapshot = load_snapshot(Path(__file__).resolve().parents[1] / "examples/health-demo.json") if args.demo else collect_snapshot()
            output = json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        else:
            output = render_snapshot(load_snapshot(args.input))
        if args.output:
            # Preserve inputs and earlier evidence; choose a fresh output filename.
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(output)
        else:
            print(output, end="")
    except (OSError, ValueError, UnicodeError) as exc:
        print("health: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
