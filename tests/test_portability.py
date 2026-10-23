"""Behavior checks for a colleague who receives only this skill folder."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import json
import runpy
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import common
from verify_bundle import verify, write_manifest
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'


class PortabilityTests(unittest.TestCase):
    def test_shipped_bundle_matches_its_manifest(self):
        # 改了包内文件却没跑 verify_bundle.py --write，同事端预检就会报“文件已变更”。
        result = verify(ROOT)
        self.assertTrue(result['pass'], result['errors'])

    def test_sharing_rejects_named_private_env_even_after_manifest_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'volcengine.env').write_text('DOUBAO_SPEECH_API_KEY="dummy-only"', encoding='utf-8')
            write_manifest(root)
            self.assertFalse(verify(root)['pass'])

    def test_production_config_rejects_empty_example_and_wrong_voice(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'volcengine.env'
            for key, voice in [('', 'zh_male_dayi_uranus_bigtts'),
                               ('在本机填写自己的火山密钥', 'zh_male_dayi_uranus_bigtts'),
                               ('dummy-test-only', 'wrong-voice')]:
                file.write_text('DOUBAO_SPEECH_API_KEY=' + json.dumps(key) + '\nDOUBAO_SPEECH_VOICE_TYPE=' + json.dumps(voice), encoding='utf-8')
                ok, detail = common.audio_config_status(file)
                self.assertFalse(ok)
                self.assertNotIn('dummy-test-only', detail)

    def test_formal_qa_rejects_failed_determinism_with_zero_upstream_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p / 'design').mkdir(); (p / 'qc').mkdir()
            (p / 'design/config.json').write_text('{}', encoding='utf-8')
            (p / 'qc/huashu_qa.py').write_text('# fixture only', encoding='utf-8')

            def fake_run(*args, **kwargs):
                out = p / 'qc/qa'
                out.mkdir(exist_ok=True)
                (out / 'qa.json').write_text(json.dumps({'page_errors': [], 'segments': [{'deterministic': False}]}), encoding='utf-8')
                return SimpleNamespace(returncode=0, stdout='', stderr='')

            with patch.object(sys, 'argv', ['qa_project.py', '--project', str(p)]), patch('subprocess.run', fake_run):
                with self.assertRaises(SystemExit) as exit_code:
                    runpy.run_path(str(ROOT / 'scripts/qa_project.py'), run_name='__main__')
                self.assertNotEqual(exit_code.exception.code, 0)

    def test_embedded_sources_win_over_old_machine(self):
        original = common.HOME
        old = os.environ.get('HUASHU_SKILL')
        try:
            common.HOME = ROOT / 'nonexistent-home'
            os.environ['HUASHU_SKILL'] = str(ROOT / 'nonexistent-external-skill')
            self.assertEqual(common.find_huashu(), ROOT / 'upstream/huashu-art-motion')
            self.assertEqual(common.find_story_visuals(), ROOT)
        finally:
            common.HOME = original
            if old is None:
                os.environ.pop('HUASHU_SKILL', None)
            else:
                os.environ['HUASHU_SKILL'] = old

    def test_empty_workspace_bootstrap_and_project(self):
        with tempfile.TemporaryDirectory(prefix='hdv isolated ') as directory:
            ws = Path(directory) / 'new machine'
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/new_project.py'),
                                     'portable', '--workspace', str(ws), '--date', '20261014'],
                                    capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((ws / 'AGENTS.md').read_bytes(), (ws / 'CLAUDE.md').read_bytes())
            self.assertIn('.private/', (ws / '.gitignore').read_text(encoding='utf-8'))
            project = ws / 'projects/20261014-portable-v01'
            for file in ('engine/render.py', 'engine/lib/fonts/LXGWWenKai-500.woff',
                         'engine/clips/hand_drawn_marker.js', 'qc/huashu_qa.py'):
                self.assertTrue((project / file).is_file(), file)
            if (ROOT / 'assets/characters/companion-references-v01').is_dir():   # 品牌扩展包存在才有
                for file in ('assets/references/companion/01-线上-书桌手机通话.png',
                             'assets/references/companion-logo-reference-v01.png'):
                    self.assertTrue((project / file).is_file(), file)
            again = subprocess.run([sys.executable, str(ROOT / 'scripts/new_project.py'),
                                    'portable', '--workspace', str(ws), '--date', '20261014'],
                                   capture_output=True, encoding='utf-8')
            self.assertNotEqual(again.returncode, 0)

    def test_project_name_cannot_escape_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/new_project.py'),
                                     '../../escape', '--workspace', directory], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((Path(directory).parent / 'escape-v01').exists())

    def test_voice_preflight_has_no_submission_and_keeps_private_file_local(self):
        spec = importlib.util.spec_from_file_location('bundled_voice', ROOT / 'scripts/audio/generate_candidate.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix='hdv voice ') as directory:
            ws = Path(directory)
            p = ws / 'projects/example-v01'
            (p / 'brief').mkdir(parents=True)
            (p / 'brief/narration.txt').write_text('孩子说，我想去学校试试。', encoding='utf-8')
            (ws / '.private').mkdir()
            (ws / '.private/volcengine.env').write_text(
                'DOUBAO_SPEECH_API_KEY="dummy-offline-key"\n'
                'DOUBAO_SPEECH_VOICE_TYPE="zh_male_dayi_uranus_bigtts"\n', encoding='utf-8')
            result = module.run(p, preflight=True, provider='volcengine')
            self.assertTrue(result['credential_present'])
            self.assertFalse((p / 'assets/audio').exists())

    def _voice_module(self):
        spec = importlib.util.spec_from_file_location('bundled_voice2', ROOT / 'scripts/audio/generate_candidate.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_voice_selection_dayi_default_and_xiaohe_for_female_first_person(self):
        module = self._voice_module()
        self.assertEqual(module.VOICES['dayi'], 'zh_male_dayi_uranus_bigtts')
        self.assertEqual(module.VOICES['xiaohe'], 'zh_female_xiaohe_uranus_bigtts')
        with tempfile.TemporaryDirectory(prefix='hdv voice ') as directory:
            ws = Path(directory)
            p = ws / 'projects/example-v01'
            (p / 'brief').mkdir(parents=True)
            (p / 'brief/narration.txt').write_text('我以前一听到上学就想吐。', encoding='utf-8')
            (ws / '.private').mkdir()
            (ws / '.private/volcengine.env').write_text(
                'DOUBAO_SPEECH_API_KEY="dummy-offline-key"\n'
                'DOUBAO_SPEECH_VOICE_TYPE="zh_male_dayi_uranus_bigtts"\n', encoding='utf-8')
            self.assertEqual(module.run(p, preflight=True, provider='volcengine')['voice_id'], 'zh_male_dayi_uranus_bigtts')
            result = module.run(p, preflight=True, voice='xiaohe', provider='volcengine')
            self.assertEqual(result['voice_id'], 'zh_female_xiaohe_uranus_bigtts')
            self.assertTrue(result['output'].endswith('narration-volcengine-xiaohe-full-v01.mp3'))
            result = module.run(p, preflight=True, voice='wenroumama', provider='volcengine')
            self.assertEqual(result['voice_id'], 'zh_female_wenroumama_uranus_bigtts')
            self.assertTrue(result['output'].endswith('narration-volcengine-wenroumama-full-v01.mp3'))
            self.assertEqual(result['speech_rate'], 19)
            self.assertIn('很着急', result['voice_directive'])
            self.assertEqual(result['voice_directive_source'], 'voice_recipe')
            with self.assertRaises(ValueError):
                module.run(p, preflight=True, voice='yunhao', provider='volcengine')

    def test_changing_voice_for_same_text_needs_explicit_confirmation(self):
        module = self._voice_module()
        text = '我想回学校。'
        h = module.sha_bytes(text.encode('utf-8'))
        with tempfile.TemporaryDirectory(prefix='hdv voice ') as directory:
            p = Path(directory) / 'p'
            (p / 'assets/audio').mkdir(parents=True)
            (p / 'assets/audio/narration-volcengine-dayi-full-v01.mp3.json').write_text(
                json.dumps({'input_text_sha256': h, 'voice_id': module.VOICES['dayi']}), encoding='utf-8')
            self.assertIsNotNone(module.other_voice_receipt(p, h, module.VOICES['xiaohe']))
            self.assertIsNone(module.other_voice_receipt(p, h, module.VOICES['dayi']))


if __name__ == '__main__':
    unittest.main()
