"""Build a public simulator from synthetic snapshots and the canonical health rules."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import math
from string import Template

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent


def scenarios(health):
    fixture = health.load_snapshot(ROOT / 'examples/health-demo.json')
    definitions = [
        ('everyday', '日常运行', '先熟悉一台有余量的机器。', '各项未触及提示阈值。状态提示也不能替代业务验收。'),
        ('memory', '内存吃紧', '看 RAM 减少，swap 与等待增加。', '先结合进程、kernel 日志与工作负载定位压力。增加 swap 不能替代 RAM，也不能证明解决了 OOM。'),
        ('disk', '磁盘快满', '容量减少，inode 仍有余量。', '先确认增长来源、挂载点和日志占用，再决定清理或扩容；不要直接删除不明文件。'),
        ('inodes', '小文件堆积', '磁盘还有空间，inode 却快用尽。', '字节和文件数量是两种余量。检查小文件来源；不要只看 df -h，还要看 df -i。'),
        ('missing', '采集缺失', '指标读不到时，不能画成零。', '未知表示证据不足。核对权限、内核接口与采集范围，取得数据后再判断。'),
    ]
    result = []
    for key, title, description, lesson in definitions:
        frames = []
        for step in range(13):
            progress = step / 12
            snapshot = deepcopy(fixture)
            at = datetime(2026, 10, 2, 6, tzinfo=timezone.utc) + timedelta(minutes=step * 5)
            snapshot['collected_at'] = health.utc_text(at)
            snapshot['source']['description'] = '完全合成的模拟场景：' + title + '；不对应真实机器或真实历史。'
            m = snapshot['metrics']
            available = .57 + math.sin(step * .8) * .03
            disk, inodes = .63 - progress * .02, .68 - progress * .015
            load, psi, full, swap = .45 + math.sin(step * .7) * .14, .5, .03, .02
            if key == 'memory':
                available, swap = .58 - progress * .55, .02 + progress * .67
                load, psi, full = .6 + progress * 1.7, .6 + progress ** 3 * 18, .03 + progress ** 3 * 1.9
            elif key == 'disk':
                disk = .64 - progress * .61
            elif key == 'inodes':
                inodes = .68 - progress * .65
            m['memory']['available_bytes'] = int(m['memory']['total_bytes'] * available)
            m['swap'] = {'total_bytes': 536870912, 'used_bytes': int(536870912 * swap)}
            m['root_bytes']['available_bytes'] = int(m['root_bytes']['total_bytes'] * disk)
            m['root_bytes']['free_bytes'] = int(m['root_bytes']['total_bytes'] * (disk + .05))
            m['root_inodes']['available'] = int(m['root_inodes']['total'] * inodes)
            m['root_inodes']['free'] = int(m['root_inodes']['total'] * (inodes + .03))
            m['cpu'].update({'load_1m': round(load * 1.14, 2), 'load_5m': round(load, 2), 'load_15m': round(load * .79, 2)})
            m['uptime']['seconds'] += step * 300
            for kind, value in (('some', psi), ('full', full)):
                m['memory_psi'][kind] = {'avg10': round(value * 1.1, 2), 'avg60': round(value, 2), 'avg300': round(value * .8, 2), 'total_us': int(value * 1000000)}
            if key == 'missing' and step >= 6:
                m['memory'] = {'error': '合成示例：MemAvailable 未能读取'}
                m['memory_psi'] = {'error': '合成示例：内核 PSI 接口不可用'}
            normalized = health.validate_snapshot(snapshot)
            display = {}
            for name, value in normalized['metrics'].items():
                label, main, detail, note, _ = health.metric_display(name, value)
                state = health.assess(name, value)
                display[name] = {'label': label, 'main': main, 'detail': detail, 'note': note, 'state': state, 'status': health.LABELS[state]}
            chart = {'memory': None if 'error' in m['memory'] else round(available * 100, 2),
                     'root_bytes': round(disk * 100, 2), 'cpu': m['cpu']['load_5m'],
                     'memory_psi': None if 'error' in m['memory_psi'] else m['memory_psi']['some']['avg60'],
                     'root_inodes': round(inodes * 100, 2), 'swap': round(swap * 100, 2)}
            frames.append({'at': snapshot['collected_at'], 'minute': step * 5, 'metrics': display, 'chart': chart})
        result.append({'id': key, 'title': title, 'description': description, 'lesson': lesson, 'frames': frames})
    return {'kind': 'synthetic', 'interval_minutes': 5, 'scenarios': result}


def build_demo(output, base, health):
    target = Path(output) / 'health/demo'
    target.mkdir(parents=True, exist_ok=True)
    data = scenarios(health)
    # JSON is an explicit synthetic product, never a copy of reports/ or a live collect.
    (target / 'scenarios.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    source = Template((SITE / 'health.html').read_text(encoding='utf-8'))
    (target / 'index.html').write_text(source.substitute(base=base), encoding='utf-8')
    snapshot = Path(output) / 'health/snapshot'
    snapshot.mkdir(parents=True, exist_ok=True)
    (snapshot / 'index.html').write_text(health.render_snapshot(health.load_snapshot(ROOT / 'examples/health-demo.json')), encoding='utf-8')
