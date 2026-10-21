import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from hdv.lint import panel_rhythm_issues


class PanelRhythmTests(unittest.TestCase):
    def test_flags_long_panel_and_idle_gap(self):
        scenes = [{'index': 0, 'id': 'long', 'start': 0, 'end': 14.5}]
        events = [
            {'index': 0, 'at': 0.2, 'dur': 1.0, 'kind': 'hero'},
            {'index': 0, 'at': 8.0, 'dur': 0.5, 'kind': 'line'},
        ]
        issues = panel_rhythm_issues(events, scenes)
        self.assertTrue(any('超过 8.0s' in issue for issue in issues))
        self.assertTrue(any('空档' in issue for issue in issues))

    def test_accepts_board_with_regular_drawing_events(self):
        scenes = [{'index': 2, 'id': 'beat', 'start': 10, 'end': 17}]
        events = [
            {'index': 2, 'at': 10.1, 'dur': 1.0, 'kind': 'hero'},
            {'index': 2, 'at': 13.0, 'dur': 0.4, 'kind': 'text'},
            {'index': 2, 'at': 15.8, 'dur': 0.5, 'kind': 'line'},
        ]
        self.assertEqual(panel_rhythm_issues(events, scenes), [])

    def test_ignores_short_fragments_as_motion(self):
        scenes = [{'index': 0, 'id': 'still', 'start': 0, 'end': 5}]
        events = [{'index': 0, 'at': 0.1, 'dur': 0.1, 'kind': 'line'}]
        self.assertTrue(panel_rhythm_issues(events, scenes))


if __name__ == '__main__':
    unittest.main()
