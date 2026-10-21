import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from hdv.lint import panel_rhythm_issues, panel_exit_issues


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

    def test_flags_too_short_panel(self):
        scenes = [{'index': 0, 'id': 'blink', 'start': 0, 'end': 1.9}, {'index': 1, 'id': 'ok', 'start': 1.9, 'end': 4.4}]
        events = [{'index': 0, 'at': 0.1, 'dur': 1.0, 'kind': 'hero'}, {'index': 1, 'at': 2.0, 'dur': 1.0, 'kind': 'hero'}]
        issues = panel_rhythm_issues(events, scenes)
        self.assertEqual(len(issues), 1)
        self.assertIn('短于 2.5s', issues[0])

    def test_ignores_short_fragments_as_motion(self):
        scenes = [{'index': 0, 'id': 'still', 'start': 0, 'end': 5}]
        events = [{'index': 0, 'at': 0.1, 'dur': 0.1, 'kind': 'line'}]
        self.assertTrue(panel_rhythm_issues(events, scenes))


class PanelExitTests(unittest.TestCase):
    scenes = [{'index': 0, 'id': 'a', 'start': 0, 'end': 6}, {'index': 1, 'id': 'b', 'start': 6, 'end': 12}]

    def test_flags_text_finishing_during_pan(self):
        # 镜头 5.5s 开始离开板 0；这句 5.84s 才写完（学霸请假片审片实例同型）
        events = [{'index': 0, 'at': 5.2, 'dur': .64, 'kind': 'text', 'str': '还算什么'}]
        issues = panel_exit_issues(events, self.scenes)
        self.assertEqual(len(issues), 1)
        self.assertIn('还算什么', issues[0])

    def test_accepts_small_overlap_and_last_panel(self):
        events = [
            {'index': 0, 'at': 5.0, 'dur': .65, 'kind': 'line'},           # 5.65 ≤ 5.7
            {'index': 1, 'at': 11.5, 'dur': .9, 'kind': 'text', 'str': '结尾'},  # 最后一块不检查
        ]
        self.assertEqual(panel_exit_issues(events, self.scenes), [])


if __name__ == '__main__':
    unittest.main()
