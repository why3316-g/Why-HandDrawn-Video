"""Fail-closed pre-render composition checks. Semantic completeness still needs review."""
import argparse
import json
import math
from pathlib import Path


def intersects(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def bounds(e, data):
    if e.get('ringBox'):
        x,y,w,h=e['ringBox']; return [x,y,x+w,y+h]
    if e['kind']=='media': return [e['x'],e['y'],e['x']+e['w'],e['y']+e['h']]
    if e['kind'] == 'text':
        z = e['size']; x = e['x']; y = e['y']
        return [x, y-z*.9, x+sum(1 if ord(c)>127 else .65 for c in e['str'])*z, y+z*.2]
    if e['kind'] == 'line':
        pts = e.get('p', []); pad=e.get('width', 6)/2
        if pts:
            return [min(p[0] for p in pts)-pad,min(p[1] for p in pts)-pad,max(p[0] for p in pts)+pad,max(p[1] for p in pts)+pad]
    if e['kind'] == 'hero':
        r=data['spriteLibrary']['sprites'][e['id']]['rect']; w=e['h']*r[2]/r[3]
        return [e['cx']-w/2,e['top'],e['cx']+w/2,e['top']+e['h']]


def check(spec, plan):
    errors=[]; warnings=[]; data=spec['data']; events=data.get('events', [])
    duration=spec.get('duration',0)
    if not isinstance(duration,(float,int)) or not math.isfinite(duration) or duration<=0:
        errors.append('成片duration缺失或无效'); duration=0
    if any(e['at']+e['dur']>duration+.0011 for e in events): errors.append('事件超出成片时长')
    if any(s['start']<0 or s['end']>duration+.0011 or s['end']<=s['start'] for s in data.get('scenes',[])):
        errors.append('画板超出成片时长或时间倒置')
    header=data.get('header', {})
    if any(header.get('first', [])) or header.get('other') or data.get('showHeader'):
        errors.append('常驻标题/歌名必须关闭并清空')
    if plan.get('version') != 1:
        errors.append('缺少有效 design/composition.json version=1')
    panels={p['index']:p for p in plan.get('panels', [])}
    scene_ids=[s['index'] for s in data.get('scenes', [])]
    if len(set(scene_ids))!=len(scene_ids): errors.append('重复画板index')
    if len(panels)!=len(plan.get('panels', [])): errors.append('重复构图index')
    if any(e.get('index') not in scene_ids for e in events): errors.append('事件引用不存在的画板')
    layout=data.get('layout', {})
    safe=layout.get('text_bounds',[40,285,1040,1425])
    for scene in data.get('scenes', []):
        i=scene['index']; p=panels.get(i)
        if not p:
            errors.append(f'板{i}缺少构图与语义单元记录'); continue
        for field in ['layout_reason','text_anchor','caption_zone','protected_bounds','text_bounds_with_marks','draw_units']:
            if field not in p or p[field] is None:
                errors.append(f'板{i}缺少{field}')
        if len(p.get('alternatives', []))<2:
            errors.append(f'板{i}至少比较两种版式')
        ownership={}; units=p.get('draw_units', [])
        unit_ids=[u.get('id') for u in units]
        if any(not x for x in unit_ids) or len(set(unit_ids))!=len(unit_ids):
            errors.append(f'板{i}语义单元id为空或重复')
        for u in units:
            if not u.get('meaning') or not u.get('completion'):
                errors.append(f'板{i}单元缺少完整意思/阶段完成状态')
            for n in u.get('events', []):
                if not isinstance(n,int) or n<0 or n>=len(events) or events[n].get('index')!=i:
                    errors.append(f'板{i}无效事件引用{n}'); continue
                if n in ownership: errors.append(f'事件{n}重复归属')
                ownership[n]=u.get('id')
        selected=sorted([(n,e) for n,e in enumerate(events) if e.get('index')==i],key=lambda ne:ne[1]['at'])
        if len({e['emotion_style'] for _,e in selected if 'emotion_style' in e})>1:
            errors.append(f'板{i}混用多种主情绪符号')
        seen=set(); last=None; active_end=-1; active_n=None
        for n,e in selected:
            if n not in ownership: errors.append(f'板{i}事件{n}未归属语义单元')
            uid=ownership.get(n)
            pen=e['kind'] in ('hero','line','text') and not (e['kind']=='text' and e.get('fade'))
            if pen and uid!=last:
                if uid in seen: errors.append(f'板{i}语义单元{uid}被打断后续写/续画')
                seen.add(uid); last=uid
            at=e['at']; dur=e['dur']
            if not math.isfinite(at) or not math.isfinite(dur) or dur<=0:
                errors.append(f'事件{n}时间无效'); continue
            if pen and at<active_end-.0011:
                errors.append(f'板{i}事件{active_n}/{n}同时落笔')
            if pen and at+dur>active_end: active_end=at+dur; active_n=n
            if at<scene['start']-1e-6 or at+dur>scene['end']+1e-6:
                errors.append(f'事件{n}超出画板时间')
            b=bounds(e,data)
            if b:
                if b[0]<safe[0] or b[1]<safe[1] or b[2]>safe[2] or b[3]>safe[3]:
                    errors.append(f'事件{n}超出可见安全区')
                if e['kind'] in ('text','line'):
                    for protected in p.get('protected_bounds', []):
                        if intersects(b,protected): errors.append(f'文字事件{n}遮挡脸/手/关键结构')
                    if p.get('caption_zone') and intersects(b,p['caption_zone']):
                        errors.append(f'文字事件{n}侵入字幕区')
        for box in p.get('text_bounds_with_marks', []):
            if any(intersects(box,b) for b in p.get('protected_bounds', [])):
                errors.append(f'板{i}圈线整体遮挡关键结构')
        if not p.get('intentional_whitespace'):
            bs=[bounds(e,data) for _,e in selected if e['kind'] in ('hero','text')]
            bs=sorted([b for b in bs if b],key=lambda b:b[1])
            if any(b[1]-a[3]>spec['height']*.16 for a,b in zip(bs,bs[1:])):
                warnings.append(f'板{i}图文纵向间隔偏大，请目检或记录留白意图')
    return {'pass':not errors,'errors':errors,'warnings':warnings,
            'limits':'语义完整性、漏标关键区域、实际字形和美感仍须过程目检；本检测不替代审片。'}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--project',default='.'); ap.add_argument('--spec',required=True)
    a=ap.parse_args(); p=Path(a.project).resolve(); s=Path(a.spec)
    if not s.is_absolute(): s=p/s
    try:
        result=check(json.loads(s.read_text(encoding='utf-8-sig')),json.loads((p/'design/composition.json').read_text(encoding='utf-8-sig')))
    except (OSError,ValueError,KeyError,TypeError,IndexError) as ex:
        result={'pass':False,'errors':[f'构图输入无效：{ex}'],'warnings':[]}
    (p/'qc').mkdir(exist_ok=True); (p/'qc/composition-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False)); return 0 if result['pass'] else 2


if __name__=='__main__': raise SystemExit(main())
