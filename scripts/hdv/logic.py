"""宽屏输入契约；校验覆盖/原件/人物和图的空间，不替代语义与美术审查。"""
import hashlib
import json
import re
from pathlib import Path

from .layout import project_layout
from .lint import tbox


def compact(text):
    return re.sub(r'\s+', '', text)


def event_bounds(events):
    boxes=[]
    for e in events:
        if e['kind']=='text': boxes.append(tbox(e))
        elif e['kind']=='line' and e.get('p'):
            x,y=zip(*e['p']); boxes.append((min(x),min(y),max(x),max(y)))
        elif e['kind']=='media': boxes.append((e['x'],e['y'],e['x']+e['w'],e['y']+e['h']))
    if not boxes: return None
    return min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)


def logic_errors(project, scenes, events):
    p=Path(project)
    cfg=json.loads((p/'design/config.json').read_text(encoding='utf-8'))
    if cfg.get('mode','portrait')!='landscape': return []
    errors=[]
    try:
        plan=json.loads((p/cfg.get('logic_plan','design/logic-plan.json')).read_text(encoding='utf-8'))
        source=(p/cfg.get('logic_source',cfg['narration'])).read_text(encoding='utf-8').strip()
    except (OSError,ValueError,KeyError) as exc:
        return [f'宽屏缺少有效全文逻辑策划：{exc}；先完成LANDSCAPE_LOGIC.md要求的脚本分析']
    if plan.get('source_sha256')!=hashlib.sha256(source.encode()).hexdigest():
        errors.append('逻辑策划的全文SHA-256与锁稿不同')
    units=plan.get('units',[])
    if compact(''.join(u.get('text','') for u in units))!=compact(source):
        errors.append('逻辑策划没有按原顺序逐段覆盖完整锁稿')
    relations={}
    for u in units:
        if not u.get('id') or not u.get('relations'): errors.append('每段须有ID及主/次关系，不能只摘关键词')
        for r in u.get('relations',[]):
            rid=r.get('id')
            if not rid or rid in relations: errors.append('逻辑关系ID缺失或重复')
            relations[rid]=r
            quote=compact(r.get('quote',''))
            if not quote or quote not in compact(u.get('text','')): errors.append(f'{rid}关系缺少逐字原文锚点')
            if not r.get('type') or not r.get('presentation') or not r.get('nodes'):
                errors.append(f'{rid}缺关系类型、节点或呈现策划')
            for node in r.get('nodes',[])+r.get('qualifiers',[]):
                if compact(node) not in quote: errors.append(f'{rid}节点/限定词不在原文锚点中：{node}')
    docs=plan.get('documents',[])
    boards=plan.get('boards',[])
    scoped={e.get('document_id') for e in events if e.get('kind')=='media'}
    for b in boards:
        scoped.update(b.get('documents',[]))
        nodes=[n for rid in b.get('relations',[]) for n in relations.get(rid,{}).get('nodes',[])]
        scoped.update(d.get('id') for d in docs if any(d.get('source_quote','').strip('《》') in n for n in nodes))
    scene_by={s['index']:s for s in scenes}
    for title in set(re.findall(r'《[^》]*(?:声明|报告|通知|指南|办法|意见|规划|标准)[^》]*》', source)):
        if not any(title.strip('《》') in d.get('source_quote','') for d in docs):
            errors.append(f'具名官方材料未进入检索清单：{title}')
    for d in docs:
        did=d.get('id')
        if not d.get('search_queries') or not d.get('source_quote'): errors.append(f'{did}缺真实检索记录/原文依据')
        if d.get('status')=='not_found':
            if not d.get('reason'): errors.append(f'{did}未找到原件但未记录结论')
            continue
        if d.get('status')!='found' and did not in scoped:
            if not d.get('reason'): errors.append(f'{did}全文检索未完成且缺少记录')
            continue
        if d.get('status')!='found':
            errors.append(f'{did}官方原件尚未取得：{d.get("reason",d.get("status"))}')
            continue
        f=p/d.get('image_file','')
        if not d.get('official_url','').startswith('https://') or d.get('verified') is not True:
            errors.append(f'{did}官方原件来源/版本未核对')
        # 全文先分析；后半篇的原件不强迫提前出现在当前样片。
        if did not in scoped: continue
        dimensions=None
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=d.get('image_sha256'):
            errors.append(f'{did}缺真实原件图片或哈希不符')
        else:
            try:
                from PIL import Image
                with Image.open(f) as im: dimensions=im.size; im.verify()
            except (OSError,ValueError): errors.append(f'{did}原件不是有效图片（不能把错误页面存成PNG）')
        used=[e for e in events if e.get('kind')=='media' and e.get('document_id')==did]
        if not used or any(e.get('image')!='../'+d.get('image_file','') for e in used):
            errors.append(f'{did}已找到原件，须原样图片入镜，不能用手写框代替')
        for e in used:
            w,h=e.get('w',0),e.get('h',0)
            if w<240 or h<100 or w*h<48000:
                errors.append(f'{did}原件展示尺寸过小，不能以不可读的小图算入镜')
            elif dimensions and abs((w/h)/(dimensions[0]/dimensions[1])-1)>.03:
                errors.append(f'{did}原件展示比例被拉伸')
            sc=scene_by.get(e.get('index'))
            if not sc or 'start' not in sc or 'end' not in sc:
                errors.append(f'{did}原件事件不属于有效画板窗口')
                continue
            start,end=sc['start'],sc['end']
            at,dur=e.get('at',-1),e.get('dur',0)
            if at<start or dur<=0 or at+dur+1>end-.5:
                errors.append(f'{did}原件没有在本画板可见窗口完整展示至少1秒')
    for e in events:
        if e.get('kind')=='media' and e.get('document_id') not in {d.get('id') for d in docs}:
            errors.append('原件图片事件没有对应的真实材料检索记录')
    by={b.get('id'):b for b in boards}
    if len(by)!=len(boards) or set(by)!=set(s['id'] for s in scenes):
        errors.append('逐板逻辑策划须与本版实际画板一一对应')
    layout=project_layout(p); left,top,right,bottom=layout['text_bounds']
    width,height=right-left,bottom-top
    for sc in scenes:
        b=by.get(sc['id'],{}); ev=[e for e in events if e.get('index')==sc['index']]
        if not b.get('relations') or any(r not in relations for r in b.get('relations',[])):
            errors.append(f'{sc["id"]}没有映射真实全文逻辑关系')
        if any(e['kind']=='hero' for e in ev):
            if b.get('presentation')!='person': errors.append(f'{sc["id"]}实际有人物，策划字段不一致')
            continue
        if b.get('presentation')!='full_board_logic' or len(b.get('space_reason',''))<8:
            errors.append(f'{sc["id"]}缺手绘人物；只有必须全板的居中完整逻辑图可例外')
            continue
        bound=event_bounds(ev)
        if not bound or sum(e['kind']=='text' for e in ev)<3 or not any(e['kind']=='line' for e in ev):
            errors.append(f'{sc["id"]}不是完整逻辑图，不得以概念/章节板豁免人物')
        elif (abs((bound[0]+bound[2])/2-(left+right)/2)>width*.05 or
              abs((bound[1]+bound[3])/2-(top+bottom)/2)>height*.08 or
              bound[2]-bound[0]<width*.65 or bound[3]-bound[1]<height*.5):
            errors.append(f'{sc["id"]}全板逻辑图未居中或未实际利用完整内容区')
    return errors
