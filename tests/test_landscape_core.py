"""双画幅的行为回归：坐标、旧项目默认、尺寸契约和实际工程初始化。"""
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from hdv.layout import get_layout, project_layout, validate_spec_layout
from hdv.dsl import Film
from hdv.lint import lint


class LandscapeCoreTests(unittest.TestCase):
    def test_layouts_are_independent_and_unknown_mode_fails(self):
        wide = get_layout('landscape')
        self.assertEqual((wide['width'], wide['height'], wide['panel_width']), (1920, 1080, 1960))
        wide['width'] = 1
        self.assertEqual(get_layout('landscape')['width'], 1920)
        with self.assertRaises(ValueError):
            get_layout('square')

    def test_legacy_config_defaults_portrait(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(project_layout(tmp)['mode'], 'portrait')
            p = Path(tmp) / 'design'
            p.mkdir()
            (p / 'config.json').write_text('{}', encoding='utf-8')
            self.assertEqual(project_layout(tmp)['height'], 1920)

    def test_landscape_accepts_right_column_and_rejects_caption_overlap(self):
        e = {'kind': 'text', 'index': 0, 'str': '睡眠', 'x': 1300, 'y': 400, 'size': 60}
        self.assertFalse(lint([e], layout=get_layout('landscape'))[0])
        self.assertTrue(lint([e])[0])
        e['y'] = 930
        self.assertTrue(lint([e], layout=get_layout('landscape'))[0])

    def test_spec_dimensions_cannot_disagree_with_project(self):
        wide = get_layout('landscape')
        sp = {'width': 1920, 'height': 1080, 'data': {'layout': wide}}
        validate_spec_layout(sp, wide)
        with self.assertRaises(ValueError):
            validate_spec_layout(sp, get_layout())
        with self.assertRaises(ValueError):
            validate_spec_layout({'width': 1920, 'height': 1080, 'data': {}}, wide)

    def test_film_reads_mode_and_rejects_cut_off_hero(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'design').mkdir()
            (p / 'design/config.json').write_text('{"mode":"landscape"}', encoding='utf-8')
            (p/'design/config.json').write_text('{"mode":"landscape","narration":"narration.txt"}',encoding='utf-8')
            (p/'narration.txt').write_text('测试',encoding='utf-8')
            (p/'design/logic-plan.json').write_text(json.dumps({'source_sha256':hashlib.sha256('测试'.encode()).hexdigest(),
                'units':[{'id':'u','text':'测试','relations':[{'id':'r','type':'scene','quote':'测试','nodes':['测试'],'presentation':'技术夹具人物'}]}],
                'documents':[],'boards':[{'id':'intro','relations':['r'],'presentation':'person'}]}),encoding='utf-8')
            (p / 'design/sprite-strokes-v01.json').write_text(json.dumps({
                'sprites': {'person': {'rect': [0, 0, 400, 600]}}, 'source_images': {}}), encoding='utf-8')
            f = Film(p, SimpleNamespace(end=4.0))
            f.panel(0, 'intro', 0)
            f.hero(0, 'person', 1450, 240, 550, .1, 4.2)
            sp = f.build([])
            self.assertEqual((sp['width'], sp['height']), (1920, 1080))
            self.assertEqual(sp['data']['layout']['mode'], 'landscape')
            self.assertEqual(f.hand, '../assets/images/marker-hand-landscape-v01.png')
            self.assertEqual(Film(p, SimpleNamespace(end=4.0),mode='portrait').hand, '../assets/images/marker-hand-v02.png')
            f.EV[0]['top'] = 600
            with self.assertRaises(SystemExit):
                f.build([])
            f.EV[0]['top'] = 240
            f.header_first = ['过长标题' * 20, '第二行']
            with self.assertRaises(SystemExit):
                f.build([])
            f.header_first = ['', '']
            with self.assertRaises(SystemExit):
                f.build([{'start': 0, 'end': 3, 'text': '字' * 40}])

    def test_new_landscape_project_is_self_contained(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(SKILL / 'scripts/new_project.py'), 'wide',
                                     '--workspace', tmp, '--date', '20261022', '--mode', 'landscape'],
                                    capture_output=True, encoding='utf-8', errors='replace')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            p = Path(tmp) / 'projects/20261022-wide-v01'
            cfg = json.loads((p / 'design/config.json').read_text(encoding='utf-8'))
            self.assertEqual(cfg['mode'], 'landscape')
            self.assertIn('1920×1080', (p / 'brief/BRIEF.md').read_text(encoding='utf-8'))
            self.assertTrue((p / 'design/hdv/layout.py').is_file())

    def test_opening_check_uses_wide_content_not_changing_captions(self):
        import shutil
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            self.skipTest('FFmpeg is not installed')
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'design').mkdir()
            (p / 'design/config.json').write_text('{"mode":"landscape"}', encoding='utf-8')
            for y, expected in ((300, 0), (950, 1)):
                video = p / f'motion-{y}.mp4'
                cmd = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                       'color=c=white:s=1920x1080:r=15:d=5.2', '-vf',
                       f"drawbox=x=1100:y={y}:w=300:h=50:color=black:t=fill:enable='lt(mod(t,0.6),0.3)'",
                       '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', str(video)]
                make = subprocess.run(cmd, capture_output=True)
                self.assertEqual(make.returncode, 0, make.stderr.decode('utf-8', 'replace'))
                check = subprocess.run([sys.executable, str(SKILL / 'scripts/opening_check.py'),
                                        '--project', str(p), '--video', str(video), '--ignore-start', '0'],
                                       capture_output=True, encoding='utf-8', errors='replace')
                self.assertEqual(check.returncode, expected, check.stdout + check.stderr)
                report = json.loads((p / 'qc/opening-check.json').read_text(encoding='utf-8'))
                self.assertEqual(report['mode'], 'landscape')
                self.assertEqual(report['pass'], expected == 0)


if __name__ == '__main__':
    unittest.main()
