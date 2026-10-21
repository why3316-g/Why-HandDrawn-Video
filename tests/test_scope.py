"""Production bundle contains one entry point and only the fixed-style runtime."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'upstream/huashu-art-motion/scripts/engine'
RUNTIME = {
    'render.py', 'clip.html', 'clip.js', 'lib/fonts.js', 'lib/util.js', 'lib/paint.js',
    'lib/kit.js', 'lib/motion.js', 'lib/diagram.js',
    'lib/fonts/LXGWWenKai-500.woff', 'lib/fonts/NotoSansSC-500.woff',
    'lib/fonts/LICENSES.md', 'lib/fonts/OFL.txt',
}


class ScopeTests(unittest.TestCase):
    def test_exactly_one_discoverable_skill(self):
        entries = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob('SKILL.md'))
        self.assertEqual(entries, ['SKILL.md'])

    def test_runtime_has_only_required_modules_and_assets(self):
        actual = {p.relative_to(ENGINE).as_posix() for p in ENGINE.rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
        self.assertEqual(actual, RUNTIME)

    def test_browser_loads_only_required_libraries_and_fonts(self):
        html = (ENGINE / 'clip.html').read_text(encoding='utf-8')
        scripts = re.findall(r'<script src="([^"]+)"', html)
        self.assertEqual(scripts, ['lib/fonts.js', 'lib/util.js', 'lib/paint.js',
                                   'lib/kit.js', 'lib/motion.js', 'lib/diagram.js', 'clip.js'])
        font_js = (ENGINE / 'lib/fonts.js').read_text(encoding='utf-8')
        urls = re.findall(r"url:\s*'([^']+)'", font_js)
        self.assertEqual(urls, ['lib/fonts/LXGWWenKai-500.woff', 'lib/fonts/NotoSansSC-500.woff'])
        self.assertTrue(all((ENGINE / path).is_file() for path in scripts + urls))


if __name__ == '__main__':
    unittest.main()
