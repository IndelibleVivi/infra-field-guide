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
        self.assertEqual(len(self.documents), len(PAGES) + 4)
        published = {p.relative_to(self.output).as_posix() for p in self.output.rglob('*') if p.is_file()}
        allowed = set(self.documents) | set(ASSETS) | {'assets/site.css', 'assets/site.js', 'assets/search.js', 'assets/health.js', 'assets/health.css', 'health/demo/scenarios.json', 'assets/favicon.svg', 'search.json', 'sitemap.xml', '.nojekyll'}
        self.assertEqual(published, allowed)

    def test_discovery_files_cover_the_public_canonical_routes(self):
        import xml.etree.ElementTree as ET
        base = 'https://indeliblevivi.github.io/infra-field-guide/'
        tree = ET.parse(self.output / 'sitemap.xml')
        namespace = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
        locs = [node.text for node in tree.getroot().iter(namespace + 'loc')]
        self.assertEqual(len(locs), len(PAGES) + 2)
        self.assertIn(base, locs)
        for page in PAGES:
            self.assertIn(base + page['route'], locs)
        self.assertIn(base + 'health/demo/', locs)
        self.assertNotIn(base + '404.html', locs)
        self.assertEqual(len(locs), len(set(locs)))
        # Each indexable reading page must actually be discoverable, including
        # the separately rendered home and health demo.
        for path in self.documents:
            if path in {'404.html', 'health/snapshot/index.html'}:
                continue
            html = (self.output / path).read_text(encoding='utf-8')
            canonical = re.search(r'<link rel="canonical" href="([^"]+)"', html)
            self.assertIsNotNone(canonical, path)
            self.assertIn(canonical.group(1), locs, path)
        self.assertFalse((self.output / 'robots.txt').exists())

    def test_every_published_page_has_unique_distinct_metadata(self):
        # health/snapshot is a fixed offline renderer output (tools/health.py) with a
        # restrictive CSP and no canonical; it is intentionally outside the reading-site
        # head contract and is excluded from the sitemap too.
        fixed_snapshot = {'health/snapshot/index.html'}
        descriptions = {}
        for path, document in self.documents.items():
            html = (self.output / path).read_text(encoding='utf-8')
            if path in fixed_snapshot:
                continue
            if path == '404.html':
                self.assertIn('<meta name="robots" content="noindex">', html)
                self.assertNotIn('rel="canonical"', html)
                continue
            self.assertNotIn('content="noindex"', html)
            canonical = re.search(r'<link rel="canonical" href="([^"]+)"', html)
            self.assertIsNotNone(canonical, path)
            self.assertTrue(canonical.group(1).startswith('https://indeliblevivi.github.io/infra-field-guide/'), path)
            self.assertIn(f'<meta property="og:url" content="{canonical.group(1)}">', html, path)
            self.assertIn('<meta property="og:site_name" content="Infra Field Guide">', html, path)
            self.assertIn('<meta name="twitter:card" content="summary_large_image">', html, path)
            self.assertIn('<meta property="og:image" content="https://indeliblevivi.github.io/infra-field-guide/docs/assets/drinking-fawn.png">', html, path)
            description = re.search(r'<meta name="description" content="([^"]+)"', html)
            self.assertIsNotNone(description, path)
            descriptions.setdefault(description.group(1), []).append(path)
        repeated = {text: paths for text, paths in descriptions.items() if len(paths) > 1}
        self.assertEqual(repeated, {}, repeated)

    def test_health_preview_is_a_rendered_synthetic_fixture(self):
        html = (self.output / 'health/snapshot/index.html').read_text(encoding='utf-8')
        self.assertIn('合成演示数据', html)
        self.assertIn('2026-10-02T06:00:00Z', html)
        self.assertIn('2.0 GiB', html)
        self.assertNotIn('<script', html)
        self.assertNotIn('iframe', html)
        self.assertEqual(html.count('<article class="card '), 7)
        _, content, _ = render_markdown('tools/README.md', '/infra-field-guide/')
        self.assertIn('href="/infra-field-guide/health/demo/"', content)
        _, content, _ = render_markdown('tools/README.md', '/')
        self.assertIn('href="/health/demo/"', content)

    def test_simulator_has_consistent_scenarios_and_explicit_missing_data(self):
        payload = json.loads((self.output / 'health/demo/scenarios.json').read_text(encoding='utf-8'))
        self.assertEqual(payload['kind'], 'synthetic')
        scenes = {scene['id']: scene['frames'] for scene in payload['scenarios']}
        self.assertEqual(len(scenes), 5)
        for frames in scenes.values():
            self.assertEqual([frame['minute'] for frame in frames], list(range(0, 61, 5)))
            self.assertTrue(all(len(frame['metrics']) == 7 for frame in frames))
        self.assertEqual(scenes['memory'][0]['metrics']['memory']['state'], 'ok')
        self.assertEqual(scenes['memory'][-1]['metrics']['memory']['state'], 'critical')
        self.assertEqual(scenes['memory'][-1]['metrics']['swap']['state'], 'warning')
        self.assertEqual(scenes['disk'][-1]['metrics']['root_bytes']['state'], 'critical')
        self.assertEqual(scenes['inodes'][-1]['metrics']['root_bytes']['state'], 'ok')
        self.assertEqual(scenes['inodes'][-1]['metrics']['root_inodes']['state'], 'critical')
        self.assertIsNone(scenes['missing'][-1]['chart']['memory'])
        self.assertEqual(scenes['missing'][-1]['metrics']['memory']['main'], '—')
        self.assertEqual(scenes['missing'][-1]['metrics']['memory_psi']['state'], 'unknown')
        self.assertIsNotNone(scenes['missing'][0]['chart']['memory'])

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
