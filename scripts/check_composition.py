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


def _close(a, b, tol=6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def variety_errors(data, plan, scenes, events, layout):
    """防"照抄一套坐标"：排字同质化、人物全居中、窄人物旁不用空位、构图理由套话。只在 ≥6 块板时检查。"""
    errors = []
    if len(scenes) < 6:
        return errors
    width = layout.get('width', 1080)
    n = len(scenes)
    # 1) 构图记录不得是同一段套话
    plans = {p['index']: p for p in plan.get('panels', [])}
    def tail(s):
        return s.split('：', 1)[-1].strip() if s else ''
    for field in ('text_anchor', 'layout_reason'):
        vals = [tail(plans[s['index']].get(field, '')) for s in scenes if s['index'] in plans]
        if vals:
            top = max(vals.count(v) for v in vals)
            if top >= max(4, int(n * .5)):
                errors.append(f'{n}块板里有{top}块的{field}完全相同：构图理由必须逐板按量出的人物边界写（EDITING_COMPOSITION 第9节）')
    alts = [json.dumps(plans[s['index']].get('alternatives', []), ensure_ascii=False) for s in scenes if s['index'] in plans]
    if alts and max(alts.count(a) for a in alts) >= max(4, int(n * .5)):
        errors.append('多块板的备选方案完全相同：备选须针对本板的人物与空区各自写')
    # 2) 人物摆位与文字锚点
    centers, hero_cx, narrow, beside = [], [], 0, 0
    for sc in scenes:
        i = sc['index']
        es = [e for e in events if e.get('index') == i]
        texts = [e for e in es if e['kind'] == 'text' and not e.get('fade')]
        heroes = [bounds(e, data) for e in es if e['kind'] == 'hero']
        for t in texts:
            tb = bounds(t, data)
            centers.append((tb[0] + tb[2]) / 2)
        if not heroes:
            continue
        hb = heroes[0]
        hero_cx.append(round((hb[0] + hb[2]) / 2 / 60))
        if hb[2] - hb[0] < width * .45:
            narrow += 1
            hh = hb[3] - hb[1]
            for t in texts:
                tb = bounds(t, data)
                ov = min(tb[3], hb[3]) - max(tb[1], hb[1])
                if ov >= (tb[3] - tb[1]) * .6 and (tb[2] <= hb[0] or tb[0] >= hb[2]):
                    beside += 1
                    break
    if len(centers) >= 8:
        thirds = [sum(1 for c in centers if lo <= c < hi) for lo, hi in ((0, width / 3), (width / 3, width * 2 / 3), (width * 2 / 3, width + 1))]
        if thirds[0] > len(centers) * .5 or max(thirds) > len(centers) * .6:
            errors.append(f'排字位置同质化：左/中/右三分之一的文字数为 {thirds[0]}/{thirds[1]}/{thirds[2]}，超过一半挤在同一侧。请按每张图的空区逐板重新定位（measure_panels.py 的联系表）')
        if thirds[2] < len(centers) * .1:
            errors.append(f'排字位置同质化：右侧几乎没有字（{thirds[2]}/{len(centers)}）；窄人物应移到左侧，字写在右侧空区')
    if len(hero_cx) >= 8 and len(set(hero_cx)) < 3:
        errors.append('人物全部居中：窄人物应按量图结果移到一侧，字写在另一侧空区')
    if narrow >= 4 and beside < max(1, int(narrow * .25)):
        errors.append(f'{narrow}张窄人物板里只有{beside}块把字写在人物旁：窄人物两侧的空位没利用（人物高度范围内应有字，除非记录了有意留白）')
    return errors


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
    clock=layout.get('clock',[932,322,24]); clock_box=[clock[0]-clock[2]-8,clock[1]-clock[2]-8,clock[0]+clock[2]+8,clock[1]+clock[2]+8]
    errors.extend(variety_errors(data,plan,data.get('scenes',[]),events,layout))
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
                if e['kind'] in ('text','line') and intersects(b,clock_box):
                    errors.append(f'文字事件{n}压住右上角小时钟')
                if e['kind'] in ('text','line'):
                    for protected in p.get('protected_bounds', []):
                        if intersects(b,protected): errors.append(f'文字事件{n}遮挡脸/手/关键结构')
                    if p.get('caption_zone') and intersects(b,p['caption_zone']):
                        errors.append(f'文字事件{n}侵入字幕区')
        for n,e in selected:
            if e['kind']=='hero':
                hb=bounds(e,data)
                if p.get('protected_bounds') and not any(_close(hb,pb) for pb in p['protected_bounds']):
                    errors.append(f'板{i}protected_bounds与事件表人物位置不符：须由 build_composition.py 实测生成，不得手填')
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
