"""Exercise the Markdown→Pages boundary and complete generated link graph."""
from html.parser import HTMLParser
from pathlib import Path
import json
import tempfile
import unittest
from urllib.parse import urlsplit, unquote

from build import build, PAGES, ASSETS, CHAPTER_MAPS, glossary, render_markdown, resolve_link, link_kind
import re
from html import unescape


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.ids, self.links, self.descriptions = set(), [], []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if 'id' in attributes:
            self.ids.add(attributes['id'])
        self.descriptions.extend(attributes.get('aria-describedby', '').split())
        for attribute in ('href', 'src', 'srcset'):
            if attribute in attributes:
                self.links.append(attributes[attribute])


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)
        build(cls.output, '/infra-field-guide/')
        cls.documents = {p.relative_to(cls.output).as_posix(): Document(p.read_text(encoding='utf-8'))
                         for p in cls.output.rglob('*.html')}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_complete_internal_link_graph(self):
        for path, document in self.documents.items():
            for value in document.links:
                parsed = urlsplit(value)
                if parsed.scheme or parsed.netloc:
                    continue
                with self.subTest(page=path, link=value):
                    if parsed.path:
                        self.assertTrue(parsed.path.startswith('/infra-field-guide/'))
                        relative = unquote(parsed.path.removeprefix('/infra-field-guide/'))
                        target = self.output / relative
                        if target.is_dir():
                            target /= 'index.html'
                    else:
                        target = self.output / path
                    self.assertTrue(target.is_file(), f'Missing {target}')
                    if parsed.fragment and target.suffix == '.html':
                        self.assertIn(unquote(parsed.fragment), self.documents[target.relative_to(self.output).as_posix()].ids)

    def test_link_destinations_are_distinct_and_explained(self):
        cases = {
            '/infra-field-guide/guide/operations/': 'internal',
            '#来源规则': 'internal',
            'https://indeliblevivi.github.io/infra-field-guide/': 'internal',
            'https://github.com/IndelibleVivi/infra-field-guide/blob/main/tools/health.py': 'repository',
            'https://github.com/IndelibleVivi/another-project': 'external',
            'https://www.rfc-editor.org/rfc/rfc6598.html': 'external',
            '/infra-field-guide/docs/diagrams/03-operations-map.svg': 'file',
        }
        for href, expected in cases.items():
            self.assertEqual(link_kind(href, '/infra-field-guide/'), expected, href)
        for path, document in self.documents.items():
            for description in document.descriptions:
                self.assertIn(description, document.ids, path)
        _, content, _ = render_markdown('docs/09-private-access.md', '/infra-field-guide/')
        self.assertIn('data-link-kind="term"', content)
        self.assertIn('data-link-kind="external"', content)
        self.assertIn('https://www.rfc-editor.org/rfc/rfc6598.html', content)
        self.assertNotIn('/pdfrfc/', content)
        self.assertIn('class="heading-icon"', content)
        self.assertNotRegex(content, r'class="headerlink"[^>]*data-link-kind')

    def test_every_chapter_and_asset_is_published(self):
        for page in PAGES:
            self.assertTrue((self.output / page['route'] / 'index.html').is_file())
        for asset in ASSETS:
            self.assertTrue((self.output / asset).is_file())
        self.assertEqual(len(self.documents), len(PAGES) + 2)
        published = {p.relative_to(self.output).as_posix() for p in self.output.rglob('*') if p.is_file()}
        allowed = set(self.documents) | set(ASSETS) | {'assets/site.css', 'assets/site.js', 'assets/favicon.svg', 'search.json', '.nojekyll'}
        self.assertEqual(published, allowed)

    def test_search_results_target_real_sections(self):
        index = json.loads((self.output / 'search.json').read_text(encoding='utf-8'))
        self.assertGreater(len(index), 100)
        self.assertTrue(any('住宅代理' in section['text'] for section in index))
        for section in index:
            parsed = urlsplit(section['url'])
            path = parsed.path.removeprefix('/infra-field-guide/') + 'index.html'
            self.assertIn(path, self.documents)
            if parsed.fragment:
                self.assertIn(unquote(parsed.fragment), self.documents[path].ids)

    def test_markdown_commands_tables_and_unicode_anchors_survive(self):
        _, content, _ = render_markdown('docs/03-operations.md', '/infra-field-guide/')
        self.assertIn('<pre><code', content)
        self.assertIn('swapon', content)
        self.assertIn('class="table-scroll"', content)
        _, network, _ = render_markdown('docs/07-network-and-proxies.md', '/infra-field-guide/')
        self.assertIn('id="住宅代理选项proxy-cheap-dedicated"', network)
        self.assertIn('https://app.proxy-cheap.com/r/3zNHbA', network)

    def test_reading_aids_keep_canonical_content_and_fallback_links(self):
        terms = glossary()
        self.assertEqual(len(terms), 29)
        self.assertTrue(all(value['definition'] for value in terms.values()))
        self.assertTrue(all('继续读：' not in value['definition'] for value in terms.values()))
        for page in PAGES[:9]:
            with self.subTest(chapter=page['source']):
                _, content, _ = render_markdown(page['source'], '/infra-field-guide/')
                self.assertIn('class="concept-map"', content)
                self.assertIn('class="chapter-orientation"', content)
                self.assertIn('aria-label="阅读便笺"', content)
                self.assertNotIn('[!NOTE]', content)
                self.assertNotIn('[!TIP]', content)
                self.assertNotIn('配套示意图占位', content)
                self.assertIn('class="term-link"', content)
                self.assertRegex(content, r'href="/infra-field-guide/glossary/#[^"]+"')
        _, content, _ = render_markdown('docs/03-operations.md', '/')
        self.assertIn('href="/glossary/#systemd"', content)
        self.assertIn('data-definition="' + terms['systemd']['definition'] + '"', content)

    def test_all_concept_maps_have_mobile_and_desktop_compositions(self):
        from xml.etree import ElementTree as ET
        for item in CHAPTER_MAPS:
            page = next(p for p in PAGES if p['source'] == 'docs/' + item['chapter'] + '.md')
            html = (self.output / page['route'] / 'index.html').read_text(encoding='utf-8')
            for suffix, width in (('', '720'), ('.mobile', '360')):
                path = 'docs/diagrams/' + item['id'] + suffix + '.svg'
                self.assertIn(path, html)
                svg = ET.fromstring((self.output / path).read_text(encoding='utf-8'))
                self.assertEqual(svg.get('width'), width)
                self.assertEqual(len(svg.findall('.//{http://www.w3.org/2000/svg}g[@id]')), len(item['nodes']))

    def test_fenced_commands_survive_new_reading_markup(self):
        from build import ROOT
        for page in PAGES[:9]:
            raw = (ROOT / page['source']).read_text(encoding='utf-8')
            expected = re.findall(r'^```[^\n]*\n(.*?)^```', raw, re.M | re.S)
            _, content, _ = render_markdown(page['source'], '/')
            actual = [unescape(block) for block in re.findall(r'<pre><code[^>]*>(.*?)</code></pre>', content, re.S)]
            self.assertEqual(actual, expected, page['source'])

    def test_relative_links_work_at_root_or_project_prefix(self):
        self.assertEqual(resolve_link('../docs/03-operations.md#test', 'agents/first-server.md', '/'), '/guide/operations/#test')
        self.assertEqual(resolve_link('../README.md', 'docs/architecture.md', '/guide/'), '/guide/about/')
        self.assertEqual(resolve_link('../examples/health-demo.json', 'tools/README.md', '/'),
                         'https://github.com/IndelibleVivi/infra-field-guide/blob/main/examples/health-demo.json')


if __name__ == '__main__':
    unittest.main()
