import importlib.util
from pathlib import Path
import copy

s=importlib.util.spec_from_file_location('composition_check',Path(__file__).resolve().parents[1]/'scripts/check_composition.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def fixture():
    ev=[{'kind':'text','index':0,'str':'不能上学','x':540,'y':470,'size':64,'at':0,'dur':.5},
        {'kind':'line','index':0,'p':[[540,493],[796,493]],'width':5,'at':.6,'dur':.3}]
    sp={'duration':3,'width':1080,'height':1920,'data':{'header':{'first':['',''],'other':''},'events':ev,'scenes':[{'index':0,'start':0,'end':3}]}}
    plan={'version':1,'panels':[{'index':0,'layout_reason':'门框在左，字在孩子上方','text_anchor':'right','text_bounds_with_marks':[],'alternatives':['left','right'],'caption_zone':[100,1438,980,1520],'protected_bounds':[[50,680,350,1300]],'draw_units':[{'id':'phrase','meaning':'不能上学','completion':'整句加下划线','events':[0,1]}]}]}
    return sp,plan

def test_valid_right_composition():
    assert m.check(*fixture())['pass']

def test_header_rejected():
    s,p=fixture();s['data']['header']['other']='歌名';assert not m.check(s,p)['pass']

def test_overlapping_pen_rejected():
    s,p=fixture();s['data']['events'][1]['at']=.2;assert any('同时落笔' in x for x in m.check(s,p)['errors'])

def test_missing_plan_rejected():
    s,p=fixture();assert not m.check(s,{})['pass']

def test_text_over_protected_region():
    s,p=fixture();p['panels'][0]['protected_bounds']=[[500,400,900,600]];assert not m.check(s,p)['pass']

def test_interrupted_unit():
    s,p=fixture();e=copy.deepcopy(s['data']['events'][0]);e['at']=1;s['data']['events'].append(e)
    p['panels'][0]['draw_units']=[{'id':'a','meaning':'句子','completion':'完整句','events':[0,2]},{'id':'b','meaning':'图','completion':'完整图','events':[1]}]
    assert any('被打断' in x for x in m.check(s,p)['errors'])

def test_end_boundary_touch_is_allowed():
    s,p=fixture();s['data']['events'][1]['at']=.5;assert m.check(s,p)['pass']


def test_event_outside_clipped_content():
    s,p=fixture();s['data']['events'][0]['y']=100;assert not m.check(s,p)['pass']

def test_orphan_event():
    s,p=fixture();s['data']['events'].append(dict(s['data']['events'][0],index=99));assert not m.check(s,p)['pass']

def test_non_pen_fade_does_not_conflict():
    s,p=fixture();s['data']['events'][0]['fade']=True;s['data']['events'][1]['at']=.2;assert m.check(s,p)['pass']

def test_ring_actual_bounds_checked():
    s,p=fixture();s['data']['events'][1]['ringBox']=[50,700,200,100];assert not m.check(s,p)['pass']


def test_truncated_duration_rejected():
    s,p=fixture();s["duration"]=.3;assert not m.check(s,p)["pass"]
