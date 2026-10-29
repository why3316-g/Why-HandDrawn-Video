"""排字测量、构图记录生成与"全片同一左栏"拦截（2026-10-28）。"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def load(name):
    s = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


cc = load('check_composition')
mp = load('measure_panels')
bc = load('build_composition')

N = 10


def varied():
    """人物 750/300/540 三种摆位，字写在人物旁的空区：左 4、中 4、右 2。"""
    cx = [750, 300, 750, 300, 540, 300, 750, 300, 750, 540]
    xs = [100, 500, 100, 800, 400, 500, 100, 800, 100, 400]
    return xs, cx


def make(xs, hero_cx):
    """N 块板：每板一个窄人物（宽 200）和一行字；xs/hero_cx 为每板的文字 x 与人物中心。"""
    events, scenes, panels = [], [], []
    for i in range(N):
        scenes.append({'index': i, 'id': f's{i}', 'start': i * 4, 'end': i * 4 + 4})
        events.append({'kind': 'hero', 'index': i, 'id': f's{i}', 'cx': hero_cx[i], 'top': 480, 'h': 640, 'at': i * 4 + .1, 'dur': 1})
        events.append({'kind': 'text', 'index': i, 'str': '关键词', 'x': xs[i], 'y': 1300 if hero_cx[i] == 540 else 700, 'size': 60, 'at': i * 4 + 1.5, 'dur': .5})
    sprites = {f's{i}': {'rect': [0, 0, 200, 640]} for i in range(N)}
    spec = {'duration': N * 4, 'width': 1080, 'height': 1920,
            'data': {'header': {'first': ['', ''], 'other': ''}, 'events': events, 'scenes': scenes, 'spriteLibrary': {'sprites': sprites}}}
    for i in range(N):
        hb = cc.bounds(events[2 * i], spec['data'])
        panels.append({'index': i, 'layout_reason': f'板{i}：理由{i}', 'text_anchor': f'位置{i}', 'alternatives': [f'备选甲{i}', f'备选乙{i}'],
                       'caption_zone': [40, 1438, 1040, 1518], 'protected_bounds': [hb], 'text_bounds_with_marks': [],
                       'draw_units': [{'id': 'h', 'meaning': 'm', 'completion': 'c', 'events': [2 * i]}, {'id': 't', 'meaning': 'm', 'completion': 'c', 'events': [2 * i + 1]}]})
    return spec, {'version': 1, 'panels': panels}


class VarietyTests(unittest.TestCase):
    def test_all_left_column_rejected(self):
        spec, plan = make([95] * N, [540] * N)
        errs = cc.check(spec, plan)['errors']
        self.assertTrue(any('同质化' in e for e in errs), errs)
        self.assertTrue(any('全部居中' in e for e in errs), errs)

    def test_varied_layout_passes(self):
        spec, plan = make(*varied())
        res = cc.check(spec, plan)
        self.assertTrue(res['pass'], res['errors'])

    def test_boilerplate_reason_rejected(self):
        spec, plan = make(*varied())
        for p in plan['panels']:
            p['text_anchor'] = '上区下区左对齐'
        self.assertTrue(any('text_anchor' in e for e in cc.check(spec, plan)['errors']))

    def test_clock_overlap_rejected(self):
        spec, plan = make([100] * 2 + [650] * (N - 2), [750] * 2 + [300] * (N - 2))
        spec['data']['events'][1].update(x=800, y=350)
        self.assertTrue(any('小时钟' in e for e in cc.check(spec, plan)['errors']))

    def test_forged_protected_bounds_rejected(self):
        spec, plan = make(*varied())
        plan['panels'][0]['protected_bounds'] = [[0, 0, 10, 10]]
        self.assertTrue(any('protected_bounds' in e for e in cc.check(spec, plan)['errors']))


class MeasureAndBuildTests(unittest.TestCase):
    def project(self):
        d = Path(tempfile.mkdtemp())
        (d / 'design').mkdir()
        (d / 'design/config.json').write_text(json.dumps({'mode': 'portrait'}), encoding='utf-8')
        (d / 'design/sprite-strokes-v01.json').write_text(json.dumps({
            'source_images': {'a': {'file': 'a.png'}, 'w': {'file': 'w.png'}},
            'sprites': {'a': {'rect': [0, 0, 200, 640]}, 'w': {'rect': [0, 0, 1200, 640]}}}), encoding='utf-8')
        return d

    def test_narrow_sprite_gets_side_zones(self):
        d = self.project()
        out, _ = mp.measure(d)
        a = out['sprites']['a']
        self.assertTrue(a['narrow'])
        right_zone = [z for z in a['placements']['left']['zones'] if z['name'] == 'right'][0]
        self.assertGreaterEqual(right_zone['chars_at_60'], 8)
        self.assertFalse(out['sprites']['w']['narrow'])

    def test_zones_avoid_clock(self):
        d = self.project()
        out, _ = mp.measure(d)
        above = [z for z in out['sprites']['a']['placements']['center']['zones'] if z['name'] == 'above'][0]
        self.assertLess(above['box'][2], 932 - 24)

    def test_build_requires_plan(self):
        d = self.project()
        spec, _ = make([100] * N, [540] * N)
        (d / 'design/spec-film.json').write_text(json.dumps(spec), encoding='utf-8')
        with self.assertRaises(SystemExit):
            bc.build(d, d / 'design/spec-film.json')


if __name__ == '__main__':
    unittest.main()
