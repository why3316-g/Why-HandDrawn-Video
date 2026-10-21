"""Wardrobe references must not lock character identity in later shots."""
import sys
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gen_sprites
from wardrobe import copy_wardrobe_assets, logged_attachments, resolve_wardrobe_references, validate_logged_attachments


PACK = (ROOT / 'assets/characters/wardrobe-reference-v01').is_dir()
needs_pack = unittest.skipUnless(PACK, '未安装品牌/服饰扩展包（公开版默认不带）')


class WardrobePromptTests(unittest.TestCase):
    def test_wardrobe_reference_only_changes_clothing(self):
        cast = {
            'teacher': {
                'name': '班主任',
                'wardrobe_role': 'teacher',
                'identity': 'A middle-aged Chinese female teacher wearing glasses.',
                'wardrobe_reference_images': ['assets/characters/wardrobe-reference-v01/teacher-female-clothing-v01.png'],
            }
        }
        shot = {
            'cast': 'teacher',
            'scene': 'Her hair is tied back today; she listens with a concerned expression and holds a chalk stick and book.',
        }
        prompt = gen_sprites.compose(shot, cast)

        self.assertIn('CLOTHING-ONLY IMAGE INPUTS', prompt)
        self.assertIn('Do NOT copy any reference person identity, face, hair, expression, shoes', prompt)
        self.assertIn(cast['teacher']['identity'], prompt)
        self.assertIn(shot['scene'], prompt)
        self.assertNotIn('Keep the SAME person', prompt)

    @needs_pack
    def test_project_copy_contains_every_approved_wardrobe_asset(self):
        with tempfile.TemporaryDirectory(prefix='hdv-ward-') as tmp:
            copied = copy_wardrobe_assets(ROOT, tmp)
            self.assertTrue((copied / 'mother-qipao-clothing-v01.png').is_file())
            self.assertTrue((copied / 'mother-qipao-clothing-v02.png').is_file())
            self.assertTrue((copied / 'mother-dress-clothing-v01.png').is_file())
            self.assertTrue((copied / 'teacher-female-clothing-v01.png').is_file())
            self.assertTrue((copied / 'teacher-male-clothing-v01.png').is_file())

    @needs_pack
    def test_mother_requires_a_per_shot_clothing_choice(self):
        cast = {'mother': {
            'name': '妈妈', 'wardrobe_role': 'mother', 'identity': 'A 38-year-old Chinese mother.',
            'wardrobe_reference_images': ['assets/characters/wardrobe-reference-v01/mother-dress-clothing-v01.png'],
        }}
        shot = {'cast': 'mother', 'scene': 'Mother listens calmly.'}
        with tempfile.TemporaryDirectory(prefix='hdv-ward-') as tmp:
            copy_wardrobe_assets(ROOT, tmp)
            with self.assertRaisesRegex(ValueError, '必须在本镜头'):
                resolve_wardrobe_references(shot, cast, tmp)

    @needs_pack
    def test_mother_can_select_different_outfits_per_script_shot(self):
        cast = {'mother': {'name': '妈妈', 'wardrobe_role': 'mother', 'identity': 'A 38-year-old Chinese mother.'}}
        shots = [
            {'cast': 'mother', 'wardrobe_references': {'mother': ['assets/characters/wardrobe-reference-v01/mother-dress-clothing-v01.png']}},
            {'cast': 'mother', 'wardrobe_references': {'mother': ['assets/characters/wardrobe-reference-v01/mother-qipao-clothing-v02.png']}},
        ]
        with tempfile.TemporaryDirectory(prefix='hdv-ward-') as tmp:
            copy_wardrobe_assets(ROOT, tmp)
            first = resolve_wardrobe_references(shots[0], cast, tmp)
            second = resolve_wardrobe_references(shots[1], cast, tmp)
        self.assertEqual(first['mother'], ['assets/characters/wardrobe-reference-v01/mother-dress-clothing-v01.png'])
        self.assertEqual(second['mother'], ['assets/characters/wardrobe-reference-v01/mother-qipao-clothing-v02.png'])

    @needs_pack
    def test_layout_shot_attaches_clothing_and_composition_images(self):
        cast = {'mother': {'name': '妈妈', 'wardrobe_role': 'mother', 'identity': 'A 38-year-old Chinese mother.'}}
        shot = {
            'cast': 'mother',
            'layout_reference_images': ['assets/layouts/multi-household-v01/A-main-and-supporting.png'],
            'wardrobe_references': {'mother': ['assets/characters/wardrobe-reference-v01/mother-qipao-clothing-v01.png']},
            'scene': 'Mother listens to her child.',
        }
        with tempfile.TemporaryDirectory(prefix='hdv-ward-') as tmp:
            copy_wardrobe_assets(ROOT, tmp)
            refs = resolve_wardrobe_references(shot, cast, tmp)
            prompt = gen_sprites.compose(shot, cast, wardrobe_map=refs)
            inputs = gen_sprites.reference_images_for_shot(
                tmp, shot, cast, refs, Path(tmp) / 'assets/images/style-ref-C.png')
        self.assertIn('COMPOSITION-ONLY', prompt)
        self.assertIn('CLOTHING-ONLY', prompt)
        self.assertIn('mother-qipao-clothing-v01.png', prompt)
        self.assertEqual(inputs[0].name, 'A-main-and-supporting.png')
        self.assertEqual(inputs[1].name, 'mother-qipao-clothing-v01.png')
        self.assertEqual(inputs[2].name, 'style-ref-C.png')

    @needs_pack
    def test_teacher_reference_is_selected_by_gender_and_missing_files_fail(self):
        cast = {'teacher': {
            'name': '女班主任', 'wardrobe_role': 'teacher', 'gender': 'female',
            'identity': 'A middle-aged Chinese female teacher.',
        }}
        shot = {'cast': 'teacher'}
        with tempfile.TemporaryDirectory(prefix='hdv-ward-') as tmp:
            copy_wardrobe_assets(ROOT, tmp)
            refs = resolve_wardrobe_references(shot, cast, tmp)
            self.assertEqual(refs['teacher'], ['assets/characters/wardrobe-reference-v01/teacher-female-clothing-v01.png'])
            bad = {'cast': 'teacher', 'wardrobe_references': {'teacher': ['assets/characters/wardrobe-reference-v01/teacher-male-clothing-v01.png']}}
            with self.assertRaisesRegex(ValueError, '性别匹配'):
                resolve_wardrobe_references(bad, cast, tmp)
            missing = {'cast': 'teacher', 'wardrobe_references': {'teacher': ['assets/characters/wardrobe-reference-v01/teacher-female-clothing-v02.png']}}
            with self.assertRaisesRegex(ValueError, '类别/路径不匹配'):
                resolve_wardrobe_references(missing, cast, tmp)

    def test_render_gate_requires_actual_attached_ref_record(self):
        with tempfile.TemporaryDirectory(prefix='hdv-ward-') as tmp:
            qc = Path(tmp) / 'qc'
            qc.mkdir()
            record = {'runs': [{'records': [{'name': 'C-mom-v01', 'ref': ['dress.png'], 'attached_ref': []}]}]}
            path = qc / 'imagegen-run.json'
            path.write_text(json.dumps(record), encoding='utf-8')
            self.assertEqual(logged_attachments(tmp, 'C-mom-v01'), [])
            with self.assertRaisesRegex(ValueError, '未实际附加'):
                validate_logged_attachments(tmp, 'C-mom-v01', ['dress.png'])
            record['runs'][0]['records'][0]['attached_ref'] = ['dress.png']
            path.write_text(json.dumps(record), encoding='utf-8')
            self.assertEqual(logged_attachments(tmp, 'C-mom-v01'), ['dress.png'])
            self.assertEqual(validate_logged_attachments(tmp, 'C-mom-v01', ['dress.png']), ['dress.png'])

    @needs_pack
    def test_marking_a_mother_as_non_wardrobe_cannot_bypass_guard(self):
        cast = {'mother': {'name': '妈妈', 'wardrobe_role': 'none', 'identity': 'A Chinese mother.'}}
        with self.assertRaisesRegex(ValueError, '不能将 wardrobe_role 设为'):
            resolve_wardrobe_references({'cast': 'mother'}, cast, ROOT)

    def test_layout_reference_only_changes_composition(self):
        shot = {
            'layout_reference_images': ['assets/layouts/multi-household-v01/A-main-and-supporting.png'],
            'scene': 'Show three script-approved households with distinct spaces and generous whitespace.',
        }
        prompt = gen_sprites.compose(shot, {})

        self.assertIn('COMPOSITION-ONLY references', prompt)
        self.assertIn('Do NOT copy any reference people, family facts, text, props', prompt)
        self.assertIn('spatial hierarchy, spacing, relative scale and whitespace', prompt)
        self.assertIn(shot['scene'], prompt)
        self.assertNotIn('Keep the SAME person', prompt)


if __name__ == '__main__':
    unittest.main()
