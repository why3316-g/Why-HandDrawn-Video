"""真实文字底稿、封面合成和网站字幕的双模式回归；不调用生成服务。"""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import make_cover


class LandscapeDeliveryTests(unittest.TestCase):
    def test_default_cover_keeps_portrait_canvas(self):
        image, _, _ = make_cover.render_text({'lines': [[["测试标题", 0]]]}, '测试标题')
        self.assertEqual(image.size, (1080, 1920))

    def test_landscape_cover_is_native_wide_canvas(self):
        image, bottom, _ = make_cover.render_text(
            {'lines': [[["今天想早点休息", 1]], [["读懂自己的状态", 0]]]},
            '今天想早点休息读懂自己的状态', mode='landscape')
        self.assertEqual(image.size, (1920, 1080))
        # 标题位于左栏，右栏空白留给插画，不能将竖屏文字拉伸。
        self.assertLess(bottom, 900)
        from PIL import ImageChops, Image
        self.assertIsNone(ImageChops.difference(image.crop((1100, 0, 1920, 1080)), Image.new('RGB', (820, 1080), 'white')).getbbox())

    def test_landscape_title_cannot_overflow_left_column(self):
        with self.assertRaises(SystemExit):
            make_cover.render_text({'lines': [[["这是绝对不应该被挤进同一行的很长很长的标题", 0]]]},
                                   '这是绝对不应该被挤进同一行的很长很长的标题', mode='landscape')

    def test_caption_export_accounts_for_cover_and_escapes_markup(self):
        path = ROOT / 'scripts/export_website.py'
        self.assertTrue(path.is_file(), '缺少网站交付脚本')
        spec = importlib.util.spec_from_file_location('website_export', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        vtt = module.captions_vtt([{'start': 0.1, 'end': 2, 'text': '先看 <状态> & 感受'}], offset=.2)
        self.assertIn('00:00:00.300 --> 00:00:02.200', vtt)
        self.assertIn('&lt;状态&gt; &amp; 感受', vtt)
        with self.assertRaises(ValueError):
            module.captions_vtt([{'start': 2, 'end': 1, 'text': '错误'}], offset=.2)


if __name__ == '__main__':
    unittest.main()
