"""公开版打包：必须剔除品牌/人物参考图/样板案例/配乐，隐私扫描必须能拦住个人信息。"""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import package_skill


@unittest.skipUnless((ROOT / 'public/privacy_denylist.txt').is_file(), '只有维护源才有 public/ 打包配置')
class PublicProfileTests(unittest.TestCase):
    def test_public_zip_has_no_private_or_brand_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'p.zip'
            package_skill.package(ROOT, out, 'public')
            names = zipfile.ZipFile(out).namelist()
        bad = ('assets/brand/', 'assets/characters/', 'assets/layouts/', 'examples/', 'public/', '.mp3')
        self.assertEqual([n for n in names if any(b in n for b in bad)], [])
        self.assertIn('Why-HandDrawn-Video/README.md', names)

    def test_privacy_scan_blocks_personal_strings(self):
        with self.assertRaisesRegex(ValueError, '隐私扫描'):
            package_skill.privacy_scan(ROOT, [('docs/x.md', ('C:' + chr(92) + 'Us' + 'ers' + chr(92) + 'someone').encode())])


if __name__ == '__main__':
    unittest.main()
