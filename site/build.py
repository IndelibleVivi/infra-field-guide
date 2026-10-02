"""Render the public Markdown collection; no server or client framework required."""
from pathlib import Path
from html import escape
from html.parser import HTMLParser
from string import Template
from urllib.parse import urlsplit, unquote, quote
import argparse
import json
import posixpath
import re
import shutil

import markdown

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
REPO = 'https://github.com/IndelibleVivi/infra-field-guide'
PAGES = json.loads((SITE / 'pages.json').read_text(encoding='utf-8'))
ROUTES = {p['source']: p['route'] for p in PAGES}
# Only this published collection is copied. No repository-wide copy/glob.
ASSETS = ['docs/assets/banner.svg', 'docs/assets/drinking-fawn.png', 'LICENSE']
for stem in ('infrastructure-overview', 'control-access', 'public-ingress',
             'outbound-access', 'migration-state', 'repository-map'):
    ASSETS.extend(f'docs/diagrams/{stem}.{ext}' for ext in ('svg', 'png', 'excalidraw'))
ASSETS.append('docs/diagrams/architecture-model.json')


def slugify(value, separator):
    """Keep Unicode headings and the existing GitHub-compatible chapter links."""
    return re.sub(r'[^\w\- ]', '', value.lower()).replace(' ', separator)


def resolve_link(value, source, base):
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


class ContentHTML(HTMLParser):
    """Rewrite generated and raw-HTML links without touching code-block text."""
    def __init__(self, source, base):
        super().__init__(convert_charrefs=False)
        self.source, self.base, self.output = source, base, []

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.output.append('<div class="table-scroll" tabindex="0" role="region" aria-label="可横向滚动的表格">')
        attrs = [(k, resolve_link(v, self.source, self.base) if k in ('href', 'src') else v)
                 for k, v in attrs]
        if tag == 'img':
            attrs += [('loading', 'lazy'), ('decoding', 'async')]
        encoded = ''.join(f' {k}="{escape(v, quote=True)}"' if v is not None else f' {k}' for k, v in attrs)
        self.output.append(f'<{tag}{encoded}>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
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
                                                       'permalink': '↗', 'permalink_title': '此节链接'}})
    rendered = md.convert(raw)
    # The source h1 remains the real title; move it to the reader header.
    match = re.search(r'<h1\b[^>]*>(.*?)</h1>', rendered, re.S)
    title = match.group(0) if match else ''
    rendered = rendered.replace(title, '', 1)
    rendered = re.sub(r'<p>(?=<a[^>]*>返回首页</a>)', '<p class="source-nav">', rendered, count=1)
    rewrite = ContentHTML(source, base)
    rewrite.feed(rendered)
    return title, ''.join(rewrite.output), md.toc


def navigation(base, current=''):
    result, group = [], None
    for page in PAGES:
        if not page.get('group'):
            continue
        if page['group'] != group:
            if group:
                result.append('</ul>')
            group = page['group']
            result.append(f'<h3>{group}</h3><ul>')
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
    chapters = []
    for page in PAGES[:9]:
        chapters.append(f'<a class="chapter-row" href="{base}{page["route"]}">'
                        f'<span class="chapter-number">{page["number"]}</span><span>'
                        f'<h3>{page["title"]}</h3><p>{page["summary"]}</p></span><span class="row-arrow">↗</span></a>')
    return Template((SITE / 'home.html').read_text(encoding='utf-8')).substitute(base=base, chapters=''.join(chapters))


def reader(page, base):
    title, content, toc = render_markdown(page['source'], base)
    number = page.get('number', 'REF')
    pager = ''
    if 'number' in page:
        index = PAGES.index(page)
        previous = PAGES[index - 1] if index else None
        following = PAGES[index + 1] if index < 8 else None
        for label, item in [('上一章', previous), ('下一章', following)]:
            pager += (f'<a href="{base}{item["route"]}"><small>{label}</small>{item["title"]} <span>→</span></a>'
                      if item else '<span></span>')
    return f'''<div class="reader-layout">
      <aside class="sidebar" aria-label="全书目录">{navigation(base, page['source'])}</aside>
      <main id="main" class="reader" tabindex="-1">
        <header class="article-header"><a class="eyebrow" href="{base}#chapters">FIELD NOTES / {number}</a>
          {title}<p class="article-summary">{escape(page.get('summary', ''))}</p>
          <div class="article-meta"><span>Infra Field Guide</span><a href="{REPO}/blob/main/{page['source']}">阅读 Markdown ↗</a></div>
        </header>
        <details class="inline-toc"><summary>本页目录</summary>{toc}</details>
        <article class="prose">{content}</article>
        <nav class="chapter-pager" aria-label="相邻章节">{pager}</nav>
        <div class="article-end"><span>读到这里，喝口水吧。</span><a href="#main">回到页首 ↑</a></div>
      </main>
      <aside class="page-toc" aria-label="本页目录"><p class="eyebrow">ON THIS PAGE</p>{toc}</aside>
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
            self.heading += value.replace('↗', '')
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
    for name in ('site.css', 'site.js', 'favicon.svg'):
        shutil.copyfile(SITE / name, output / 'assets' / name)
    (output / 'search.json').write_text(json.dumps(search, ensure_ascii=False), encoding='utf-8')
    (output / '.nojekyll').touch()
    missing = '<main id="main" class="not-found"><p class="eyebrow">404 / 迷路了</p><h1>这条小径还没有通向页面。</h1><p>可以回到目录，或搜索你想读的内容。</p><a class="button primary" href="' + base + '">回到手册首页 →</a></main>'
    (output / '404.html').write_text(shell(missing, base, {'title': '页面未找到'}), encoding='utf-8')
    print(f'Built {len(PAGES) + 2} pages, {len(search)} search sections → {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(ROOT / '_site'))
    parser.add_argument('--base', default='/infra-field-guide/')
    args = parser.parse_args()
    if not (args.base.startswith('/') and args.base.endswith('/')):
        parser.error('--base must start and end with /')
    build(args.output, args.base)
