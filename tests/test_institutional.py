import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'

class InstitutionalTests(unittest.TestCase):
    def module(self, name, rel):
        spec = importlib.util.spec_from_file_location(name, SCRIPTS / rel)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_profile_routes_by_content_and_preserves_explicit_choice(self):
        m = self.module('institutional_profile_test', 'audio/institutional_profile.py')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'design').mkdir()
            self.assertEqual(m.select_voice(p, None), 'dayi')
            (p/'design/config.json').write_text(json.dumps({'content_type':'institutional_promo'}))
            self.assertEqual(m.select_voice(p, None), 'yichen')
            self.assertEqual(m.select_voice(p, 'xiaohe'), 'xiaohe')
            self.assertEqual(m.PROFILE['speech_rate'], 0)
            self.assertEqual(m.PROFILE['voice_id'], 'zh_male_ruyayichen_uranus_bigtts')

    def test_broadcast_body_preserves_text_and_uses_instruction_field(self):
        sys.path.insert(0, str(SCRIPTS.parent / 'upstream/openmontage-audio'))
        m=self.module('institutional_request_test','audio/institutional_profile.py')
        original='原文2019年，不改写。'
        b=m.broadcast_tts_class()()._submit_body({'text':original}, voice_id=m.PROFILE['voice_id'], request_id='fixture')
        self.assertEqual(b['req_params']['text'],original)
        self.assertEqual(json.loads(b['req_params']['additions'])['context_texts'],[m.PROFILE['directive']])

    def test_formal_cover_keeps_title_and_rejects_wrong_text(self):
        from PIL import Image
        m=self.module('institutional_cover_test','make_institutional_cover.py')
        title='看见校园里的每一份成长：读懂学生状态，营造支持性的学习环境'
        cfg={'lines':['看见校园里的每一份成长：','读懂学生状态，','营造支持性的学习环境'],'sizes':[64,55,55]}
        im,record=m.compose(cfg,title,Image.new('RGB',(1920,1080),'#10283b'))
        self.assertEqual(im.size,(1920,1080));self.assertEqual(record['title'],title)
        with self.assertRaisesRegex(ValueError,'标题'):
            m.compose({'lines':['改写标题']},title,Image.new('RGB',(1920,1080)))

    def test_new_project_receives_institutional_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            r=subprocess.run([sys.executable,str(SCRIPTS/'new_project.py'),'school','--workspace',d,
                              '--date','20261022','--mode','landscape','--content-type','institutional_promo'],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            cfg=json.loads((Path(d)/'projects/20261022-school-v01/design/config.json').read_text(encoding='utf-8'))
            self.assertEqual((cfg['voice'],cfg['cover_style']),('yichen','institutional'))

    def test_cli_preflight_uses_profile_without_paid_submission(self):
        with tempfile.TemporaryDirectory() as d:
            ws=Path(d);(ws/'.private').mkdir();(ws/'.hdv-workspace.json').write_text('{}')
            (ws/'.private/volcengine.env').write_text('DOUBAO_SPEECH_API_KEY="fixture-not-a-secret"\nDOUBAO_SPEECH_VOICE_TYPE="zh_male_dayi_uranus_bigtts"\n')
            p=ws/'projects/clip';(p/'design').mkdir(parents=True);(p/'brief').mkdir()
            (p/'design/config.json').write_text('{"content_type":"institutional_promo"}')
            (p/'brief/narration.txt').write_text('原文逐字保留。',encoding='utf-8')
            r=subprocess.run([sys.executable,str(SCRIPTS/'audio/generate_candidate.py'),'--project',str(p),
                              '--provider','volcengine','--preflight'],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            data=json.loads(r.stdout.strip())
            self.assertEqual((data['voice'],data['speech_rate']),('yichen',0))
            self.assertTrue(data['institutional_directive'])
            self.assertFalse((p/'assets').exists())

if __name__=='__main__':unittest.main()
