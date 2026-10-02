"""Render the public Markdown collection; no server or client framework required."""
from pathlib import Path
from html import escape
from html.parser import HTMLParser
from string import Template
from urllib.parse import urlsplit, unquote, quote
import importlib.util
import argparse
import json
import posixpath
import re
import shutil
from functools import lru_cache
from xml.etree import ElementTree as ET

import markdown

from ui import icon, chapter_icon
from health_demo import build_demo

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
REPO = 'https://github.com/IndelibleVivi/infra-field-guide'
PAGES = json.loads((SITE / 'pages.json').read_text(encoding='utf-8'))
ROUTES = {p['source']: p['route'] for p in PAGES}
# Only this published collection is copied. No repository-wide copy/glob.
ASSETS = ['docs/assets/banner.svg', 'docs/assets/drinking-fawn.png', 'docs/assets/drinking-fawn.webp', 'LICENSE']
HEALTH_ROUTES = ('health/demo/', 'health/snapshot/')
for stem in ('infrastructure-overview', 'control-access', 'public-ingress',
             'outbound-access', 'migration-state', 'repository-map'):
    ASSETS.extend(f'docs/diagrams/{stem}.{ext}' for ext in ('svg', 'png', 'excalidraw'))
ASSETS.append('docs/diagrams/architecture-model.json')
CHAPTER_MAPS = json.loads((ROOT / 'docs/diagrams/chapter-maps.json').read_text(encoding='utf-8'))['diagrams']
ASSETS.append('docs/diagrams/chapter-maps.json')
for diagram in CHAPTER_MAPS:
    ASSETS.extend(f'docs/diagrams/{diagram["id"]}{suffix}.svg' for suffix in ('', '.mobile'))


@lru_cache(maxsize=1)
def glossary():
    """Keep inline definitions derived from the one canonical Markdown glossary."""
    raw = (ROOT / 'docs/glossary.md').read_text(encoding='utf-8')
    tree = ET.fromstring('<div>' + markdown.markdown(raw) + '</div>')
    terms, current = {}, None
    for element in tree:
        if element.tag == 'h2':
            name = ''.join(element.itertext())
            current = slugify(name, '-')
            terms[current] = {'name': name, 'definition': ''}
        elif element.tag == 'p' and current and not terms[current]['definition']:
            terms[current]['definition'] = ''.join(element.itertext())
    return terms


def slugify(value, separator):
    """Keep Unicode headings and the existing GitHub-compatible chapter links."""
    return re.sub(r'[^\w\- ]', '', value.lower()).replace(' ', separator)


def resolve_link(value, source, base):
    for route in HEALTH_ROUTES:
        if value == 'https://indeliblevivi.github.io/infra-field-guide/' + route:
            return base + route
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or value.startswith('#'):
        return value
    target = posixpath.normpath(posixpath.join(posixpath.dirname(source), unquote(parsed.path)))
    if target in ROUTES:
        url = base + ROUTES[target]
    elif target in ASSETS:
        url = base + target
    else:
        kind = 'tree' if (ROOT / target).is_dir() else 'blob'
        url = f'{REPO}/{kind}/main/{quote(target)}'
    if parsed.query:
        url += '?' + parsed.query
    if parsed.fragment:
        url += '#' + parsed.fragment
    return url


LINK_LABELS = {'internal': '站内页面', 'term': '本站词义', 'repository': '本项目仓库',
               'external': '外部网站', 'file': '本站文件'}


def link_kind(href, base):
    parsed = urlsplit(href)
    if parsed.hostname == 'github.com' and (parsed.path == '/IndelibleVivi/infra-field-guide' or
                                            parsed.path.startswith('/IndelibleVivi/infra-field-guide/')):
        return 'repository'
    if parsed.netloc and not (parsed.hostname == 'indeliblevivi.github.io' and
                              parsed.path.startswith('/infra-field-guide/')):
        return 'external'
    if parsed.path.startswith(base + 'docs/') or parsed.path.endswith(('.svg', '.png', '.excalidraw', '.json')):
        return 'file'
    return 'internal'


class ContentHTML(HTMLParser):
    """Render link destinations and heading markers without touching command text."""
    def __init__(self, source, base):
        super().__init__(convert_charrefs=False)
        self.source, self.base, self.output = source, base, []
        self.active_link = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.output.append('<div class="table-scroll" tabindex="0" role="region" aria-label="可横向滚动的表格">')
        attributes = {k: resolve_link(v, self.source, self.base) if k in ('href', 'src') else v
                      for k, v in attrs}
        if tag == 'a':
            self.active_link = None
            if 'headerlink' not in attributes.get('class', ''):
                href = attributes.get('href', '')
                kind = link_kind(href, self.base)
                if href.startswith(self.base + 'glossary/#'):
                    term = glossary().get(unquote(urlsplit(href).fragment))
                    if term:
                        kind = 'term'
                        attributes.update({'data-term': term['name'], 'data-definition': term['definition']})
                css = 'term-link' if kind == 'term' else 'link-' + kind
                attributes['class'] = (attributes.get('class', '') + ' ' + css).strip()
                attributes['data-link-kind'] = kind
                attributes['aria-describedby'] = 'link-help-' + kind
                host = urlsplit(href).hostname
                attributes['title'] = LINK_LABELS[kind] + ((' · ' + host) if host and kind == 'external' else '')
                self.active_link = kind
        if tag == 'th':
            attributes['scope'] = 'col'
        if tag == 'img':
            attributes.update({'loading': 'lazy', 'decoding': 'async'})
        encoded = ''.join(f' {k}="{escape(v, quote=True)}"' if v is not None else f' {k}' for k, v in attributes.items())
        self.output.append(f'<{tag}{encoded}>')
        if tag in ('h2', 'h3') and attributes.get('id') != '这一章帮你做什么':
            name = chapter_icon(self.source) if tag == 'h2' else 'spark'
            self.output.append(icon(name, 'heading-icon'))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == 'a' and self.active_link:
            self.output.append(icon(self.active_link, 'link-cue cue-' + self.active_link))
            self.active_link = None
        self.output.append(f'</{tag}>')
        if tag == 'table':
            self.output.append('</div>')

    def handle_data(self, data):
        self.output.append(data)

    def handle_entityref(self, name):
        self.output.append(f'&{name};')

    def handle_charref(self, name):
        self.output.append(f'&#{name};')

    def handle_comment(self, data):
        self.output.append(f'<!--{data}-->')


def render_markdown(source, base):
    raw = (ROOT / source).read_text(encoding='utf-8')
    md = markdown.Markdown(extensions=['fenced_code', 'tables', 'sane_lists', 'toc'],
                           extension_configs={'toc': {'slugify': slugify, 'toc_depth': '2-3',
                                                       'permalink': '¶', 'permalink_title': '此节链接'}})
    rendered = md.convert(raw)
    # The source h1 remains the real title; move it to the reader header.
    match = re.search(r'<h1\b[^>]*>(.*?)</h1>', rendered, re.S)
    title = match.group(0) if match else ''
    rendered = rendered.replace(title, '', 1)
    rendered = re.sub(r'^\s*<p><a[^>]*>返回首页</a></p>', '', rendered, count=1)
    rewrite = ContentHTML(source, base)
    rewrite.feed(rendered)
    content = enhance_content(''.join(rewrite.output), base)
    return title, content, md.toc


def enhance_content(content, base):
    def note(match):
        kind, first, remaining = match.groups()
        heading = re.match(r'<strong>(.*?)</strong>\s*(.*)', first, re.S)
        label = heading.group(1) if heading else '记在这里'
        body = heading.group(2) if heading else first
        return (f'<aside class="pinned-note note-{kind.lower()}" aria-label="阅读便笺">'
                f'<span class="pin" aria-hidden="true"></span><div class="note-title">{label}</div>'
                f'<p>{body}</p>{remaining}</aside>')
    content = re.sub(r'<blockquote>\s*<p>\[!(NOTE|TIP)\]\s*(.*?)</p>(.*?)</blockquote>', note, content, flags=re.S)
    content = re.sub(r'(<h2 id="这一章帮你做什么">.*?</h2>\s*<p>.*?</p>)',
                     r'<section class="chapter-orientation">\1</section>', content, count=1, flags=re.S)
    for diagram in CHAPTER_MAPS:
        source = base + 'docs/diagrams/' + diagram['id']
        pattern = r'<p><img\b[^>]*src="' + re.escape(source + '.svg') + r'"[^>]*>\s*</p>'
        alternative = diagram['description'] + ' ' + '；'.join(node['title'] + '：' + node['body'].replace('\n', '，') for node in diagram['nodes'])
        figure = (f'<figure class="concept-map"><picture><source media="(max-width: 1000px)" srcset="{source}.mobile.svg">'
                  f'<img src="{source}.svg" alt="{escape(alternative, quote=True)}" loading="lazy" decoding="async"></picture>'
                  f'<figcaption><span>{escape(diagram["footer"])}</span><a class="link-file" href="{source}.svg" title="本站 SVG 原图" data-link-kind="file" aria-describedby="link-help-file">本站原图 {icon("file", "link-cue cue-file")}</a></figcaption></figure>')
        content = re.sub(pattern, lambda _: figure, content)
    return content


def navigation(base, current=''):
    result, group = [], None
    for page in PAGES:
        if not page.get('group'):
            continue
        if page['group'] != group:
            if group:
                result.append('</ul>')
            group = page['group']
            result.append(f'<h3>{icon({"从零开始": "server", "迁移与恢复": "move", "连接与排障": "network"}.get(group, "source"))}{group}</h3><ul>')
        active = ' aria-current="page"' if current == page['source'] else ''
        number = f'<span class="nav-number">{page["number"]}</span>' if 'number' in page else ''
        result.append(f'<li><a href="{base}{page["route"]}"{active}>{number}{page["title"]}</a></li>')
    return ''.join(result) + '</ul>'


def shell(body, base, page=None):
    page = page or {}
    title = page.get('title', '把自己的服务安顿好')
    return Template((SITE / 'shell.html').read_text(encoding='utf-8')).substitute(
        body=body, base=base, title=escape(title), lang=page.get('lang', 'zh-CN'),
        description=escape(page.get('summary', '一本关于 VPS、迁移、网络与日常运维的实用手册。给人阅读，也给 agent 使用。')),
        canonical='https://indeliblevivi.github.io' + base + page.get('route', ''),
        nav=navigation(base, page.get('source', '')), repo=REPO)


def home(base):
    groups = {'foundations': '从零开始', 'migration': '迁移与恢复', 'connections': '连接与排障'}
    chapters = {}
    for key, group in groups.items():
        entries = []
        for page in PAGES:
            if page.get('group') != group or 'number' not in page:
                continue
            entries.append(f'<li><a class="chapter-entry" href="{base}{page["route"]}">'
                           f'<span class="entry-number" aria-hidden="true">{page["number"]}</span><div>'
                           f'<h4>{escape(page["title"])}</h4><p>{escape(page["summary"])}</p></div>'
                           f'<span class="entry-arrow" aria-hidden="true">→</span></a></li>')
        chapters[key] = ''.join(entries)
    return Template((SITE / 'home.html').read_text(encoding='utf-8')).substitute(base=base, **chapters)


def reader(page, base):
    title, content, toc = render_markdown(page['source'], base)
    group = page.get('group', 'Agent 工单' if page['source'].startswith('agents/') else '参考附录')
    location = f'第 {page["number"]} 章' if 'number' in page else '参考页'
    if 'number' in page:
        title = re.sub(r'(<h1[^>]*>)\d{2} · ', r'\1', title)
        title = re.sub(r'(<h1[^>]*>)([^<：]+)：([^<]+)', r'\1\2<span class="title-detail">\3</span>', title)
    pager = ''
    if 'number' in page:
        index = PAGES.index(page)
        previous = PAGES[index - 1] if index else None
        following = PAGES[index + 1] if index < 8 else None
        for label, item in [('上一章', previous), ('下一章', following)]:
            pager += (f'<a href="{base}{item["route"]}"><small>{label}</small>{item["title"]} <span>→</span></a>'
                      if item else '<span></span>')
    legend = ''.join(f'<span>{icon(kind)}{label}</span>' for kind, label in
                     [('internal', '站内'), ('term', '词义'), ('repository', '仓库'), ('external', '外部')])
    return f'''<div class="reader-layout">
      <aside class="sidebar" aria-label="全书目录"><p class="sidebar-label">阅读目录</p>{navigation(base, page['source'])}</aside>
      <main id="main" class="reader" tabindex="-1">
        <header class="article-header">
          <nav class="reader-breadcrumb" aria-label="阅读位置"><a href="{base}#chapters">手册目录</a><span aria-hidden="true">/</span><span>{escape(group)}</span><span class="reading-location">{location}</span><a class="repository-source" href="{REPO}/blob/main/{page['source']}" title="前往本项目 GitHub 仓库">{icon('repository')}仓库原文{icon('external')}</a></nav>
          <div class="article-title-row"><span class="article-emblem">{icon(chapter_icon(page['source']))}</span><div>{title}<p class="article-summary">{escape(page.get('summary', ''))}</p></div></div>
        </header>
        <details class="link-guide"><summary><span class="link-guide-label">链接标记</span>{legend}</summary><ul>
          <li id="link-help-internal">{icon('internal')}<span><strong>站内页面</strong>继续阅读手册中的章节或本页小节。</span></li>
          <li id="link-help-term">{icon('term')}<span><strong>本站词义</strong>点击就地查词；未启用脚本时进入词表。</span></li>
          <li id="link-help-repository">{icon('repository')}<span><strong>本项目仓库</strong>前往 GitHub 查看原文、代码或示例。</span></li>
          <li id="link-help-external">{icon('external')}<span><strong>外部网站</strong>离开手册，查看引用资料或其他网站。</span></li>
          <li id="link-help-file">{icon('file')}<span><strong>本站文件</strong>打开本站提供的原图、文件或下载资源。</span></li>
        </ul></details>
        <details class="inline-toc"><summary>{icon('compass')}这一页的路标</summary>{toc}</details>
        <article class="prose">{content}</article>
        {f'<nav class="chapter-pager" aria-label="相邻章节">{pager}</nav>' if pager else ''}
        <div class="article-end"><span>读到这里，喝口水吧。</span><a href="#main">回到页首 ↑</a></div>
      </main>
      <aside class="page-toc" aria-label="本页目录"><p class="toc-label">{icon('compass')}这一页的路标</p>{toc}</aside>
    </div>'''


class SearchSections(HTMLParser):
    def __init__(self, page, base):
        super().__init__()
        self.page, self.base = page, base
        self.parts, self.entries = [], []
        self.heading, self.anchor, self.in_heading = page['title'], '', False

    def flush(self):
        text = ' '.join(' '.join(self.parts).split())
        if text:
            self.entries.append({'title': self.page['title'], 'heading': self.heading,
                                 'url': self.base + self.page['route'] + ('#' + self.anchor if self.anchor else ''),
                                 'text': text})
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('h2', 'h3'):
            self.flush()
            self.heading, self.anchor, self.in_heading = '', dict(attrs).get('id', ''), True

    def handle_endtag(self, tag):
        if tag in ('h2', 'h3'):
            self.in_heading = False

    def handle_data(self, value):
        if self.in_heading:
            self.heading += value.replace('¶', '')
        else:
            self.parts.append(value)


def build(output, base):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'index.html').write_text(shell(home(base), base), encoding='utf-8')
    search = []
    for page in PAGES:
        target = output / page['route']
        target.mkdir(parents=True, exist_ok=True)
        (target / 'index.html').write_text(shell(reader(page, base), base, page), encoding='utf-8')
        if page['source'] != 'LICENSE-DOCUMENTATION.md':
            _, content, _ = render_markdown(page['source'], base)
            index = SearchSections(page, base)
            index.feed(content)
            index.flush()
            search.extend(index.entries)
    for source in ASSETS:
        target = output / source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, target)
    (output / 'assets').mkdir(exist_ok=True)
    for name in ('site.css', 'site.js', 'search.js', 'favicon.svg', 'health.css', 'health.js'):
        shutil.copyfile(SITE / name, output / 'assets' / name)
    (output / 'search.json').write_text(json.dumps(search, ensure_ascii=False), encoding='utf-8')
    # Render only the explicit synthetic fixture; never call collect_snapshot or copy reports/.
    spec = importlib.util.spec_from_file_location('guide_health', ROOT / 'tools/health.py')
    health = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(health)
    build_demo(output, base, health)
    (output / '.nojekyll').touch()
    missing = '<main id="main" class="not-found"><p class="eyebrow">404 / 迷路了</p><h1>这条小径还没有通向页面。</h1><p>可以回到目录，或搜索你想读的内容。</p><a class="button primary" href="' + base + '">回到手册首页 →</a></main>'
    (output / '404.html').write_text(shell(missing, base, {'title': '页面未找到'}), encoding='utf-8')
    print(f'Built {len(PAGES) + 4} pages, {len(search)} search sections → {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(ROOT / '_site'))
    parser.add_argument('--base', default='/infra-field-guide/')
    args = parser.parse_args()
    if not (args.base.startswith('/') and args.base.endswith('/')):
        parser.error('--base must start and end with /')
    build(args.output, args.base)
