"""Check the handoffs between chapters, examples and executable snippets.

No tutorial command is executed. Bash parses shell fences with -n only.
"""
from pathlib import Path
import json
import re
import shutil
import subprocess
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which('bash')
DOCUMENTS = sorted(ROOT.glob('*.md')) + sorted(ROOT.glob('docs/**/*.md')) + sorted(ROOT.glob('agents/*.md')) + [ROOT / 'tools/README.md', ROOT / 'site/README.md']


def prose(text):
    return re.sub(r'^```[^\n]*\n.*?^```\s*$', '', text, flags=re.M | re.S)


def anchors(text):
    counts = {}
    result = set()
    for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*$', prose(text), re.M):
        slug = re.sub(r'[^\w\- ]', '', heading.lower(), flags=re.UNICODE).replace(' ', '-')
        suffix = counts.get(slug, 0)
        counts[slug] = suffix + 1
        result.add(slug + (f'-{suffix}' if suffix else ''))
    return result


class DocumentationTests(unittest.TestCase):
    def test_cleanup_prerequisites_appear_before_quarantine(self):
        text = (ROOT / 'docs/06-account-recovery.md').read_text(encoding='utf-8')
        markers = ['cp -pR', '先抽查关键历史与配置能打开',
                   '**按所选范围退出登录。**', '**再次退出写入者。**',
                   '**A：只隔离', 'mv "$cc_source"', '**B：移走完整用户配置',
                   '逐项检查原路径已移走', '**可选分支：卸载／重装程序。**']
        positions = [text.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))

    def test_relative_links_and_heading_targets(self):
        checked = 0
        for doc in DOCUMENTS:
            for link in re.findall(r'\[[^\]\n]*\]\(([^)\s]+)\)', prose(doc.read_text(encoding='utf-8'))):
                parsed = urlsplit(link)
                if parsed.scheme or parsed.netloc:
                    continue
                target = (doc.parent / unquote(parsed.path)).resolve() if parsed.path else doc
                with self.subTest(document=str(doc.relative_to(ROOT)), link=link):
                    self.assertTrue(target.is_relative_to(ROOT), 'link leaves repository')
                    self.assertTrue(target.exists(), 'missing local target')
                    if parsed.fragment and target.suffix == '.md':
                        self.assertIn(unquote(parsed.fragment), anchors(target.read_text(encoding='utf-8')))
                checked += 1
        self.assertGreater(checked, 20)

    @unittest.skipUnless(BASH, 'bash unavailable; tutorial syntax check skipped')
    def test_shell_fences_parse_without_execution(self):
        for doc in DOCUMENTS:
            text = doc.read_text(encoding='utf-8')
            self.assertEqual(len(re.findall(r'^```', text, re.M)) % 2, 0, str(doc))
            for index, code in enumerate(re.findall(r'^```(?:bash|sh)\n(.*?)^```\s*$', text, re.M | re.S)):
                with self.subTest(document=str(doc.relative_to(ROOT)), block=index):
                    # Preserve LF for Bash even when Python runs on Windows.
                    result = subprocess.run([BASH, '-n'], input=code.encode('utf-8'), capture_output=True)
                    detail = (result.stdout + result.stderr).decode('utf-8', errors='replace')
                    self.assertEqual(result.returncode, 0, detail)

    def test_examples_are_json_and_policy_is_narrow(self):
        for path in sorted((ROOT / 'examples').glob('*.json')):
            with self.subTest(example=path.name):
                json.loads(path.read_text(encoding='utf-8'))
        grant = json.loads((ROOT / 'examples/tailnet-ssh-grant.example.json').read_text(encoding='utf-8'))
        self.assertEqual(len(grant['grants']), 1)
        rule = grant['grants'][0]
        self.assertEqual(rule['ip'], ['tcp:22'])
        self.assertEqual(len(rule['src']), 1)
        self.assertEqual(len(rule['dst']), 1)
        self.assertNotIn('*', rule['src'] + rule['dst'])


if __name__ == '__main__':
    unittest.main()
