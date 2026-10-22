"""零字形等价仅用于比较，不能掩盖真实稿件差异或改变时间窗。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'scripts/hdv/clock.py'
spec = importlib.util.spec_from_file_location('clock_zero_under_test', MODULE)
clock_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clock_module)
Clock = clock_module.Clock


class ZeroGlyphTests(unittest.TestCase):
    def make_clock(self, folder, source, spoken):
        text = Path(folder) / 'narration.txt'
        receipt = Path(folder) / 'receipt.json'
        text.write_text(source, encoding='utf-8')
        words = [{'word': ch, 'startTime': 1 + i * .25,
                  'endTime': 1 + (i + 1) * .25} for i, ch in enumerate(spoken)]
        receipt.write_text(json.dumps({'provider_query': {'data': {
            'sentences': [{'words': words}]}}}, ensure_ascii=False), encoding='utf-8')
        original = (text.read_bytes(), receipt.read_bytes())
        result = Clock(text, receipt)
        self.assertEqual(original, (text.read_bytes(), receipt.read_bytes()))
        self.assertEqual([(a, b) for _, a, b in result.chars],
                         [(w['startTime'], w['endTime']) for w in words])
        return result

    def test_years_preserve_phrase_times_and_input_files(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.make_clock(folder, '2019年和2026年', '二零一九年和二零二六年')
            self.assertEqual(result.T('2019年'), (1, 2.25))
            self.assertEqual(result.T('2026年'), (2.5, 3.75))
            self.assertEqual(result.line_span(0), (1, 3.75))

    def test_all_zero_spellings_work_in_both_directions(self):
        for source_zero in ('0', '零', '〇'):
            for provider_zero in ('0', '零', '〇'):
                with self.subTest(source=source_zero, provider=provider_zero):
                    with tempfile.TemporaryDirectory() as folder:
                        result = self.make_clock(folder, '二' + source_zero + '二六年',
                                                 '二' + provider_zero + '二六年')
                        for phrase in ('2026年', '二零二六年', '二〇二六年'):
                            self.assertEqual(result.T(phrase), (1, 2.25))

    def test_real_mismatches_still_fail(self):
        for spoken in ('二零二五年', '二零六年', '二零二六天'):
            with self.subTest(spoken=spoken):
                with tempfile.TemporaryDirectory() as folder:
                    with self.assertRaisesRegex(SystemExit, '词级时间戳与口播原文不一致'):
                        self.make_clock(folder, '2026年', spoken)


if __name__ == '__main__':
    unittest.main()
