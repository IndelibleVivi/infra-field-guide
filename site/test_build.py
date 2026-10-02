"""Exercise the Markdown→Pages boundary and complete generated link graph."""
from html.parser import HTMLParser
from pathlib import Path
import json
import tempfile
import unittest
from urllib.parse import urlsplit, unquote

from build import build, PAGES, ASSETS, render_markdown, resolve_link


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.ids, self.links = set(), []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if 'id' in attributes:
            self.ids.add(attributes['id'])
        for attribute in ('href', 'src'):
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

    def test_relative_links_work_at_root_or_project_prefix(self):
        self.assertEqual(resolve_link('../docs/03-operations.md#test', 'agents/first-server.md', '/'), '/guide/operations/#test')
        self.assertEqual(resolve_link('../README.md', 'docs/architecture.md', '/guide/'), '/guide/about/')
        self.assertEqual(resolve_link('../examples/health-demo.json', 'tools/README.md', '/'),
                         'https://github.com/IndelibleVivi/infra-field-guide/blob/main/examples/health-demo.json')


if __name__ == '__main__':
    unittest.main()
