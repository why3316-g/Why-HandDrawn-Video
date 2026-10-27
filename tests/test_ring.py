"""ring() 的圈线不得穿过被圈文字的字框（1–8 字）。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from hdv.dsl import Film
from hdv.lint import text_w
from hdv.ring_style import ring_geometry


class RingTests(unittest.TestCase):
    def test_approved_styles_keep_strokes_outside_text_and_are_distinct(self):
        size = 60
        for n in range(1, 9):
            width = text_w('字' * n, size)
            for style in ('normal', 'key', 'special'):
                points, widths, details, brush = ring_geometry(width, size, style)
                self.assertEqual(len(points), len(widths))
                strokes = [(points, widths)] + [(p, [w] * len(p)) for p, w, _, _ in details]
                for points, pen_widths in strokes:
                    for i, ((ax, ay), (bx, by)) in enumerate(zip(points, points[1:])):
                        for k in range(11):
                            px = ax + (bx - ax) * k / 10
                            py = ay + (by - ay) * k / 10
                            radius = max(pen_widths[i], pen_widths[i + 1]) / 2
                            self.assertFalse(-radius < px < width + radius and
                                             -size * .82 - radius < py < size * .12 + radius,
                                             f'{style} {n}字圈线碰到字框')
        key = ring_geometry(240, size, 'key')
        normal = ring_geometry(240, size, 'normal')
        special = ring_geometry(240, size, 'special')
        self.assertGreater(max(key[1]), max(normal[1]) * 2)
        self.assertGreater(max(key[1]), min(key[1]) * 2)
        self.assertTrue(special[3])
        self.assertTrue(normal[2])

    def test_default_and_explicit_style_emit_sequential_draw_events(self):
        for style in ('normal', 'key', 'special'):
            film = Film.__new__(Film)
            film.EV = []
            film.ring(0, '重点', 200, 500, 60, 1, dur=1, style=style)
            self.assertEqual(film.EV[0]['tag'], 'ring:重点')
            self.assertEqual(len(film.EV), 1)
            self.assertEqual(len(film.EV[0]['pressure']), len(film.EV[0]['p']))
            self.assertEqual(film.EV[0]['dryBrush'], style == 'special')
            self.assertAlmostEqual(film.EV[-1]['at'] + film.EV[-1]['dur'], 2, places=2)
        film = Film.__new__(Film)
        film.EV = []
        film.ring(0, '重点', 200, 500, 60, 1)
        self.assertEqual(film.EV[0]['dryBrush'], False)
        with self.assertRaises(ValueError):
            film.ring(0, '重点', 200, 500, 60, 1, style='unknown')

    def test_ring_stays_outside_text_box(self):
        size = 60
        for n in range(1, 9):
            w = text_w('字' * n, size)
            pts = Film.squircle(w / 2, -size * .34, w / 2 + size * .5, size * .66)
            x0, x1, y0, y1 = size * .05, w - size * .05, -size * .82 + size * .05, size * .12 - size * .05
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                for k in range(11):
                    x, y = ax + (bx - ax) * k / 10, ay + (by - ay) * k / 10
                    self.assertFalse(x0 < x < x1 and y0 < y < y1, f'{n}字圈线穿过字框')


if __name__ == '__main__':
    unittest.main()
