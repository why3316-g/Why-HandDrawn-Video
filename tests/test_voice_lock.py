"""声音锁定闸门：新项目没有用户通过记录时禁止生图；旧项目不受影响。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from lock_voice import voice_lock_errors


class VoiceLockTests(unittest.TestCase):
    def make(self, required=True):
        d = Path(tempfile.mkdtemp())
        (d / 'design').mkdir(); (d / 'assets/audio').mkdir(parents=True)
        (d / 'assets/audio/v1.mp3').write_bytes(b'fake-audio-1')
        cfg = {'voice_mp3': 'assets/audio/v1.mp3'}
        if required:
            cfg['voice_lock_required'] = True
        (d / 'design/config.json').write_text(json.dumps(cfg), encoding='utf-8')
        return d

    def lock(self, d, *extra):
        return subprocess.run([sys.executable, str(SCRIPTS / 'lock_voice.py'), '--project', str(d), '--audio', 'assets/audio/v1.mp3',
                               '--user-says', '声音可以，通过', *extra], capture_output=True, text=True, encoding='utf-8')

    def test_old_project_without_flag_is_not_blocked(self):
        self.assertEqual(voice_lock_errors(self.make(required=False)), [])

    def test_new_project_blocked_until_user_lock(self):
        d = self.make()
        self.assertTrue(voice_lock_errors(d))
        self.assertEqual(self.lock(d).returncode, 0)
        self.assertEqual(voice_lock_errors(d), [])
        rec = json.loads((d / 'qc/voice-lock.json').read_text(encoding='utf-8'))
        self.assertEqual(rec['user_says'], '声音可以，通过')

    def test_changed_audio_after_lock_is_blocked(self):
        d = self.make()
        self.lock(d)
        (d / 'assets/audio/v1.mp3').write_bytes(b'other-audio')
        self.assertTrue(voice_lock_errors(d))

    def test_relock_needs_flag(self):
        d = self.make()
        self.lock(d)
        self.assertNotEqual(self.lock(d).returncode, 0)
        self.assertEqual(self.lock(d, '--relock').returncode, 0)

    def test_gen_sprites_refuses_without_lock(self):
        d = self.make()
        (d / 'design/shots.json').write_text('{"shots": []}', encoding='utf-8')
        (d / 'design/cast.json').write_text('{}', encoding='utf-8')
        r = subprocess.run([sys.executable, str(SCRIPTS / 'gen_sprites.py'), '--project', str(d), '--emit-only'],
                           capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 5, r.stdout + r.stderr)
        self.assertIn('声音还没锁定', r.stdout)


if __name__ == '__main__':
    unittest.main()
