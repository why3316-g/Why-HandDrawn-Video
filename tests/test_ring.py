"""两款审核原笔迹的选择、迁移、缩放和起笔回归。"""
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from hdv.dsl import Film
from hdv.lint import lint, text_w
from hdv.layout import get_layout
from hdv.ring_style import ASSETS, ring_reference, ring_asset_cues


class RingTests(unittest.TestCase):
    def film(self):
        film = Film.__new__(Film)
        film.EV = []
        return film

    def test_only_two_selected_artworks_and_key_replaces_retired_01(self):
        self.assertEqual(sorted(p.name for p in ASSETS.glob('*.svg')), ['ring-02.svg','ring-03.svg'])
        for style, filename in [('normal','ring-02.svg'),('key','ring-03.svg'),('special','ring-03.svg')]:
            ref=ring_reference(320,80,style)
            self.assertEqual(ref['file'],filename)
        self.assertEqual(ring_reference(320,80,'key'),ring_reference(320,80,'special'))
        for invalid in ('01','unknown',''):
            with self.assertRaises(ValueError): ring_reference(320,80,invalid)

    def test_default_and_key_emit_original_artwork_without_approximation(self):
        for style, expected in [('normal','normal'),('key','key'),('special','key')]:
            film=self.film()
            film.ring(0,'重点',200,500,60,1,dur=1,style=style)
            self.assertEqual(len(film.EV),1)
            e=film.EV[0]
            self.assertEqual(e['ringAsset'],expected)
            self.assertEqual(e['tag'],'ring:重点')
            self.assertNotIn('pressure',e)
            self.assertNotIn('dryBrush',e)
            self.assertAlmostEqual(e['at']+e['dur'],2)
        film=self.film();film.ring(0,'重点',200,500,60,1)
        self.assertEqual(film.EV[0]['ringAsset'],'normal')

    def test_original_size_and_approved_breakpoint_start(self):
        for style, box, start in [('normal',[-97,-106,504,163],5.52),('key',[-112,-106,534,177],4.08)]:
            ref=ring_reference(320,80,style)
            self.assertEqual(ref['box'],box)
            self.assertAlmostEqual(ref['start'],start)
            self.assertEqual(len(ref['points']),361)
            # 首笔必须位于所选缺口方向，不能又从旧版弧线中途起笔。
            x,y=ref['points'][0]; bx,by,w,h=box
            angle=math.atan2((y-by-(h-1)/2)/((h-1)/2),(x-bx-(w-1)/2)/((w-1)/2))%(2*math.pi)
            self.assertAlmostEqual(angle,start,delta=.025)

    def test_short_and_long_text_stay_inside_ring_without_text_collisions(self):
        layout = dict(get_layout(), text_bounds=[40,285,2960,1425])
        for style in ('normal','key'):
            for size in (40,60,80):
                for n in range(1,9):
                    s='字'*n;film=self.film()
                    film.text(0,s,600,600,size,0,.4)
                    film.ring(0,s,600,600,size,.5,style=style)
                    errors,_=lint(film.EV,layout=layout)
                    self.assertEqual(errors,[],f'{style} {size}px {n}字: {errors}')
                    e=film.EV[-1]
                    self.assertTrue(all(math.isfinite(v) for point in e['p'] for v in point))

    def test_ring_artwork_cannot_be_clipped_at_board_edge(self):
        film=self.film()
        film.text(0,'重点',50,600,60,0,.4)
        film.ring(0,'重点',50,600,60,.5)
        errors,_=lint(film.EV)
        self.assertTrue(any('圈画原稿越出画板安全区' in e for e in errors))

    def test_project_assets_are_self_contained_required_and_deduplicated(self):
        film=self.film()
        for style in ('normal','key','special'):
            film.ring(0,'重点',200,500,60,1,style=style)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(FileNotFoundError): ring_asset_cues(film.EV,root)
            shutil.copytree(ASSETS,root/'assets/images/ring-styles')
            cues=ring_asset_cues(film.EV,root)
            self.assertEqual(len(cues),2)
            self.assertEqual({c['data']['style'] for c in cues},{'normal','key'})
            self.assertTrue(all(c['image'].startswith('../assets/images/ring-styles/') for c in cues))
            (root/'assets/images/ring-styles/ring-02.svg').write_text('<svg/>',encoding='utf-8')
            with self.assertRaises(ValueError): ring_asset_cues(film.EV,root)

    def test_invalid_geometry_or_duration_is_rejected(self):
        for width,size in [(0,60),(60,0),(-1,60),(math.nan,60),(60,math.inf)]:
            with self.assertRaises(ValueError): ring_reference(width,size)
        for duration in (0,-1,math.inf,math.nan):
            with self.assertRaises(ValueError): self.film().ring(0,'字',200,500,60,1,dur=duration)


if __name__=='__main__':
    unittest.main()
