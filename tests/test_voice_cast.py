"""学生第一人称稿：声音性别必须与主角性别一致。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from voice_cast import check_voice_cast


def cfg(voice, first=True):
    return {'voice': voice, 'narrator_is_protagonist': first, 'protagonist_cast': 'hero'}


def cast(gender, identity='A 15-year-old student.'):
    return {'hero': {'name': 'x', 'gender': gender, 'identity': identity}}


class VoiceCastTests(unittest.TestCase):
    def test_matching_voice_and_gender_pass(self):
        self.assertEqual(check_voice_cast(cfg('xiaohe'), cast('female', 'A 15-year-old girl.')), [])
        self.assertEqual(check_voice_cast(cfg('dayi'), cast('male', 'A 15-year-old boy.')), [])

    def test_female_voice_with_male_protagonist_fails(self):
        self.assertTrue(check_voice_cast(cfg('xiaohe'), cast('male', 'A 15-year-old boy.')))

    def test_male_voice_with_female_protagonist_fails(self):
        self.assertTrue(check_voice_cast(cfg('dayi'), cast('female', 'A girl.')))

    def test_unspecified_gender_fails_for_first_person(self):
        self.assertTrue(check_voice_cast(cfg('xiaohe'), cast('unspecified')))

    def test_identity_text_cannot_contradict_gender(self):
        self.assertTrue(check_voice_cast(cfg('xiaohe'), cast('female', 'A girl who looks like a boy.')))

    def test_third_person_or_legacy_config_not_checked(self):
        self.assertEqual(check_voice_cast(cfg('dayi', first=False), cast('female')), [])
        self.assertEqual(check_voice_cast({'voice': 'dayi'}, cast('female')), [])

    def test_missing_protagonist_or_bad_voice(self):
        self.assertTrue(check_voice_cast({'voice': 'xiaohe', 'narrator_is_protagonist': True, 'protagonist_cast': 'nobody'}, cast('female')))
        self.assertTrue(check_voice_cast(cfg('yunhao'), cast('female')))


if __name__ == '__main__':
    unittest.main()
