import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from hdv.emotion_styles import draw,STYLES

class Recorder:
    def __init__(self): self.EV=[]
    def line(self,index,p,at,dur,color,width,curved):
        self.EV.append(dict(index=index,p=p,at=at,dur=dur,color=color))

def test_emotions_are_sequential_and_bounded():
    for style in STYLES:
        for intensity in ('light','medium'):
            f=Recorder();draw(f,0,style,100,300,200,150,1,intensity=intensity)
            assert all(a['at']+a['dur']<=b['at']+1e-9 for a,b in zip(f.EV,f.EV[1:]))
            assert all(100<=x<=300 and 300<=y<=450 for e in f.EV for x,y in e['p'])

def test_approved_props_and_paths_match():
    root=ROOT/'assets/narrative-props-v01'
    m=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    lib=json.loads((root/'strokes.json').read_text(encoding='utf-8'))
    assert len(m['items'])==12
    for item in m['items']:
        sha=hashlib.sha256((root/item['file']).read_bytes()).hexdigest()
        assert sha==item['sha256']==lib['source_images'][item['id']]['sha256']
        assert lib['sprites'][item['id']]['paths']

def test_renderer_has_no_persistent_title_branch():
    js=(ROOT/'template/engine_overrides/clips/hand_drawn_marker.js').read_text(encoding='utf-8')
    assert 'fillText(H.' not in js
