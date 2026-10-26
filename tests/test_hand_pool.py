"""手与笔素材池的行为回归：池清单、随机规则、装进项目、渲染参数解析（2026-10-26 定稿）。
公开版不带素材池图片，所以行为测试用临时池夹具；只有清单一致性检查依赖真实素材池（缺图时跳过）。"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
import hand_pool
from hdv.dsl import Film

LEGACY_HAND = SKILL / 'assets/marker-hand-v02.png'


def make_project(tmp, config=None):
    p = Path(tmp)
    (p / 'design').mkdir(parents=True, exist_ok=True)
    (p / 'design/config.json').write_text(json.dumps(config or {}, ensure_ascii=False), encoding='utf-8')
    (p / 'design/sprite-strokes-v01.json').write_text(
        json.dumps({'sprites': {'person': {'rect': [0, 0, 400, 600]}}, 'source_images': {}}), encoding='utf-8')
    return p


def make_fake_skill(tmp):
    """临时池：2 张可用、1 张下划线前缀、1 个文字文件、1 张藏在子目录里。"""
    pool = Path(tmp) / hand_pool.POOL_REL
    (pool / '_spare').mkdir(parents=True)
    for name in ('01-alpha.png', '02-beta.png', '_draft.png'):
        shutil.copy(LEGACY_HAND, pool / name)
    shutil.copy(LEGACY_HAND, pool / '_spare/03-gamma.png')
    (pool / 'notes.txt').write_text('不放图', encoding='utf-8')
    return tmp


class RealPoolTests(unittest.TestCase):
    """真实素材池（个人版才有图；公开版跳过）。"""

    def setUp(self):
        self.entries = hand_pool.entries(SKILL)
        if not self.entries:
            self.skipTest('公开版不含手部素材池图片')

    def test_every_pool_image_has_usable_geometry(self):
        self.assertGreaterEqual(len(self.entries), 1)
        for e in self.entries:
            self.assertTrue(e['file'].endswith('.png'))
            self.assertFalse(e['file'].startswith('_'))
            w, h = e['size']
            x, y = e['tip']
            self.assertTrue(0 <= x < w and 0 <= y < h, f"{e['file']} 笔尖越界")
            self.assertTrue(.25 <= e['scale'] <= .45, f"{e['file']} 缩放异常：{e['scale']}")
            self.assertEqual(e['sha256'], hand_pool.sha256_of(Path(e['path'])))

    def test_manifest_matches_disk(self):
        names = [e['file'] for e in self.entries]
        saved = hand_pool.load_manifest(SKILL)
        self.assertEqual([i['file'] for i in saved['images']], names, '手-pool-v01.json 与磁盘不一致，请跑 --sync')


class PoolBehaviourTests(unittest.TestCase):
    def test_only_top_level_pngs_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_fake_skill(tmp)
            self.assertEqual([e['file'] for e in hand_pool.entries(tmp)], ['01-alpha.png', '02-beta.png'],
                             '子目录、下划线文件、非 PNG 都不得进池')

    def test_pick_avoids_last_used_and_supports_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = make_fake_skill(Path(tmp) / 'skill')
            files = [e['file'] for e in hand_pool.entries(skill)]
            with tempfile.TemporaryDirectory() as ws:
                hand_pool.record_use(ws, {'file': files[0]})
                picks = {hand_pool.pick(skill, ws)['file'] for _ in range(30)}
                self.assertEqual(picks, {files[1]}, '一轮内不得重复，2 张池时只能轮到另一张')
                hand_pool.record_use(ws, {'file': files[1]})
                self.assertIn(hand_pool.pick(skill, ws)['file'], files, '两张都用过后重新开一轮')
                self.assertEqual(hand_pool.pick(skill, ws, '02')['file'], files[1])

    def test_install_writes_meta_and_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = make_fake_skill(Path(tmp) / 'skill')
            entry = hand_pool.entries(skill)[0]
            p = make_project(Path(tmp) / 'proj')
            meta = hand_pool.install(p, entry)
            self.assertTrue((p / 'assets/images' / entry['file']).is_file())
            self.assertEqual(meta['tip'], entry['tip'])
            self.assertIsNone(meta['sleeve'], '彩色手不带旧线稿袖管几何')
            saved = json.loads((p / 'assets/images/hand-meta.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['file'], entry['file'])

    def test_dsl_uses_pool_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = make_fake_skill(Path(tmp) / 'skill')
            entry = hand_pool.entries(skill)[0]
            p = make_project(Path(tmp) / 'proj', {'mode': 'portrait'})
            hand_pool.install(p, entry)
            cfg = json.loads((p / 'design/config.json').read_text(encoding='utf-8'))
            cfg['hand'] = entry['file']
            (p / 'design/config.json').write_text(json.dumps(cfg), encoding='utf-8')
            f = Film(p, SimpleNamespace(end=4.0))
            self.assertEqual(f.hand, '../assets/images/' + entry['file'])
            self.assertEqual(f.hand_tip, entry['tip'])
            self.assertAlmostEqual(f.hand_scale, entry['scale'])
            self.assertIsNone(f.hand_sleeve)

    def test_landscape_ignores_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = make_fake_skill(Path(tmp) / 'skill')
            entry = hand_pool.entries(skill)[0]
            p = make_project(Path(tmp) / 'proj', {'mode': 'landscape'})
            hand_pool.install(p, entry)
            cfg = json.loads((p / 'design/config.json').read_text(encoding='utf-8'))
            cfg['hand'] = entry['file']
            (p / 'design/config.json').write_text(json.dumps(cfg), encoding='utf-8')
            f = Film(p, SimpleNamespace(end=4.0))
            self.assertEqual(f.hand, '../assets/images/marker-hand-landscape-v01.png')
            self.assertAlmostEqual(f.hand_scale, .18)

    def test_legacy_hand_keeps_old_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(Path(tmp) / 'proj', {'mode': 'portrait'})
            f = Film(p, SimpleNamespace(end=4.0))
            self.assertEqual(f.hand, '../assets/images/marker-hand-v02.png')
            self.assertEqual(f.hand_tip, [147, 119])
            self.assertAlmostEqual(f.hand_scale, .34)
            self.assertEqual(f.hand_sleeve, [[1253, 885], [1052, 1253]])


if __name__ == '__main__':
    unittest.main()
