import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from hdv.logic import logic_errors


class LogicTests(unittest.TestCase):
    def fixture(self, p):
        (p/'brief').mkdir(); (p/'design').mkdir()
        text='甲与乙。'
        (p/'brief/narration.txt').write_text(text, encoding='utf-8')
        cfg={'mode':'landscape','narration':'brief/narration.txt'}
        (p/'design/config.json').write_text(json.dumps(cfg),encoding='utf-8')
        plan={'source_sha256':hashlib.sha256(text.encode()).hexdigest(),
              'units':[{'id':'u','text':text,'relations':[{'id':'r','type':'parallel',
                         'quote':text,'nodes':['甲','乙'],'qualifiers':[], 'presentation':'同级卡片'}]}],
              'documents':[], 'boards':[{'id':'one','relations':['r'],'presentation':'person'}]}
        (p/'design/logic-plan.json').write_text(json.dumps(plan),encoding='utf-8')
        return plan

    def check(self, p, events=None):
        return logic_errors(p, [{'id':'one','index':0,'start':0,'end':6}],events or [{'kind':'hero','index':0}])

    def test_wide_requires_real_plan_and_complete_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); plan=self.fixture(p)
            self.assertEqual(self.check(p),[])
            plan['units'][0]['text']='甲。'
            (p/'design/logic-plan.json').write_text(json.dumps(plan),encoding='utf-8')
            self.assertTrue(self.check(p))
            (p/'design/logic-plan.json').unlink()
            self.assertTrue(self.check(p))

    def test_no_person_needs_genuinely_centered_full_diagram(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); plan=self.fixture(p)
            events=[{'kind':'text','index':0,'str':'甲乙','x':100,'y':400,'size':70}]
            self.assertTrue(self.check(p, events))
            plan['boards'][0].update(presentation='full_board_logic',space_reason='两层整体包含图需要全板')
            (p/'design/logic-plan.json').write_text(json.dumps(plan),encoding='utf-8')
            self.assertTrue(self.check(p, events))
            events=[{'kind':'line','index':0,'p':[[130,250],[1790,250],[1790,840],[130,840],[130,250]]},
                    *[{'kind':'text','index':0,'str':s,'x':700,'y':y,'size':60} for s,y in [('甲',350),('乙',550),('甲乙',750)]]]
            self.assertEqual(self.check(p, events),[])

    def test_centered_text_explanation_and_off_center_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); plan=self.fixture(p)
            plan['boards'][0].update(presentation='centered_text',space_reason='居中文字解释完整的概念与限定词')
            (p/'design/logic-plan.json').write_text(json.dumps(plan),encoding='utf-8')
            ev=[{'kind':'text','index':0,'str':s,'x':690,'y':y,'size':60} for s,y in [('有效应对生活压力',460),('发挥自己的潜能',650)]]
            self.assertEqual(self.check(p,ev),[])
            ev[0]['x']=80; ev[1]['x']=80
            self.assertTrue(self.check(p,ev))

    def test_found_document_requires_real_verified_image_and_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); plan=self.fixture(p)
            plan['documents']=[{'id':'d','source_quote':'甲','status':'found','search_queries':['甲报告'],
                                'official_url':'https://example.org/paper','verified':True}]
            (p/'design/logic-plan.json').write_text(json.dumps(plan),encoding='utf-8')
            self.assertTrue(self.check(p))
            from PIL import Image
            Image.new('RGB',(20,20),'white').save(p/'paper.png')
            plan['documents'][0].update(image_file='paper.png',image_sha256=hashlib.sha256((p/'paper.png').read_bytes()).hexdigest())
            (p/'design/logic-plan.json').write_text(json.dumps(plan),encoding='utf-8')
            self.assertTrue(self.check(p))
            media={'kind':'media','index':0,'document_id':'d','image':'../paper.png','w':400,'h':400,'at':.2,'dur':.4}
            self.assertEqual(self.check(p,[{'kind':'hero','index':0},media]),[])
            self.assertTrue(self.check(p,[{'kind':'hero','index':0},dict(media,w=1,h=1)]))
            self.assertTrue(self.check(p,[{'kind':'hero','index':0},dict(media,at=10)]))
            self.assertTrue(self.check(p,[{'kind':'hero','index':0},dict(media,h=200)]))
            self.assertTrue(self.check(p,[{'kind':'hero','index':0},dict(media,index=99)]))

    def test_future_document_is_not_forced_into_current_pilot(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); plan=self.fixture(p)
            plan['documents']=[{'id':'later','source_quote':'后续报告','status':'found','search_queries':['后续报告'],
                                'official_url':'https://example.org/later','verified':True}]
            (p/'design/logic-plan.json').write_text(json.dumps(plan),encoding='utf-8')
            self.assertEqual(self.check(p),[])

    def test_portrait_does_not_require_wide_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); (p/'design').mkdir()
            (p/'design/config.json').write_text('{}')
            self.assertEqual(self.check(p),[])

    def test_hand_pose_is_diagonal_in_wide_and_legacy_in_portrait(self):
        import shutil
        if not shutil.which('node'): self.skipTest('node unavailable')
        js=SKILL/'template/engine_overrides/clips/hand_drawn_marker.js'
        code="const fs=require('fs'),vm=require('vm');const c={CLIPS:{}};vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),c);console.log(JSON.stringify(['landscape','portrait'].map(mode=>c.CLIPS.hand_drawn_marker.inspectHand([100,320],{mode,width:1920,content_bottom:900}))));"
        a,b=json.loads(subprocess.check_output(['node','-e',code,str(js)],text=True))
        self.assertGreaterEqual(a['armAngle'],.78); self.assertLessEqual(a['armAngle'],1.14)
        self.assertEqual(a['scale'],.18); self.assertLess(a['scale'],b['scale'])
        self.assertAlmostEqual(b['rotation'],0)      # 竖屏 2026-10-26 起手臂保持素材原姿态（右下 45°），不再旋 -45°

if __name__=='__main__': unittest.main()
