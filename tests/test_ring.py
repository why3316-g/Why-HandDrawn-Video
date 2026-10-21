"""ring() 的圈线不得穿过被圈文字的字框（1–8 字）。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from hdv.dsl import Film
from hdv.lint import text_w


class RingTests(unittest.TestCase):
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
