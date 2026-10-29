"""由事件表和手写的 design/layout-plan.json 生成 design/composition.json（EDITING_COMPOSITION 第 7、9 节）。

layout-plan.json 每块画板必须自己写：{"<板号>": {"reason": 构图理由, "anchor": 文字摆位, "alternatives": [至少两条没选的方案及原因], "whitespace": 有意留白(可空)}}。
理由、摆位、备选不得照搬同一段套话；protected_bounds 与文字框由事件表实测写入，不手填。
用法：python <skill>/scripts/build_composition.py [--project .] [--spec design/spec-film.json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_composition import bounds  # noqa: E402


def plan_entry(raw):
    if isinstance(raw, list):  # 兼容旧写法 [reason, anchor, alt1, alt2, ...]
        return {'reason': raw[0], 'anchor': raw[1], 'alternatives': raw[2:], 'whitespace': ''}
    return raw


def build(project, spec_path):
    data = json.loads(spec_path.read_text(encoding='utf-8-sig'))['data']
    plan_file = project / 'design/layout-plan.json'
    if not plan_file.is_file():
        raise SystemExit('缺少 design/layout-plan.json：先跑 measure_panels.py 量图，再逐板写构图理由。')
    plan = json.loads(plan_file.read_text(encoding='utf-8-sig'))
    layout = data.get('layout', {})
    cap_top = layout.get('caption_top', 1438)
    cap_h = layout.get('caption_height', 80)
    safe = layout.get('text_bounds', [40, 285, 1040, 1425])
    events = data['events']
    panels = []
    for sc in data['scenes']:
        idx = sc['index']
        raw = plan.get(str(idx))
        if raw is None:
            raise SystemExit(f'layout-plan.json 缺少板 {idx}（{sc["id"]}）')
        p = plan_entry(raw)
        if len(p.get('alternatives', [])) < 2 or not p.get('reason') or not p.get('anchor'):
            raise SystemExit(f'板 {idx} 的 reason/anchor/alternatives(≥2) 不完整')
        protected, text_bounds, units = [], [], []
        for k, (n, e) in enumerate([(n, e) for n, e in enumerate(events) if e.get('index') == idx]):
            kind, tag = e['kind'], e.get('tag', '')
            b = bounds(e, data)
            end = e['at'] + e['dur']
            if kind == 'hero':
                protected.append(b)
                uid, meaning, done = f'p{idx}-hero', f"画出板{idx}人物形象（{e['id']}），确立场景主体", f'人物线稿绘制完成，轮廓清晰（{end:.2f}s）'
            elif kind == 'text':
                text_bounds.append(b)
                uid, meaning, done = f'p{idx}-t{k}', f"写出关键词「{e['str']}」", f"「{e['str']}」书写完毕（{end:.2f}s）"
            elif tag.startswith('ring:'):
                text_bounds.append(b)
                uid, meaning, done = f'p{idx}-ring{k}', f'橙色马克笔圈画强调「{tag[5:]}」', f'圈画闭合完成（{end:.2f}s）'
            elif kind == 'line':
                text_bounds.append(b)
                uid, meaning, done = f'p{idx}-line{k}', f"绘制强调符号（{tag or 'line'}）", f'符号绘制完成（{end:.2f}s）'
            else:
                uid, meaning, done = f'p{idx}-u{k}', f'绘制视觉元素（{kind}）', f'元素完成（{end:.2f}s）'
            units.append({'id': uid, 'meaning': meaning, 'completion': done, 'events': [n]})
        panels.append({
            'index': idx,
            'layout_reason': f"板{idx}（{sc['id']}）：{p['reason']}",
            'text_anchor': p['anchor'],
            'alternatives': p['alternatives'],
            'caption_zone': [safe[0], cap_top, safe[2], cap_top + cap_h],
            'protected_bounds': protected,
            'text_bounds_with_marks': text_bounds,
            'intentional_whitespace': p.get('whitespace', ''),
            'draw_units': units,
        })
    out = project / 'design/composition.json'
    out.write_text(json.dumps({'version': 1, 'note': '构图与语义单元记录；protected/文字框由事件表实测生成', 'panels': panels}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'已生成 design/composition.json（{len(panels)} 块）')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project', default='.')
    ap.add_argument('--spec', default='design/spec-film.json')
    a = ap.parse_args()
    p = Path(a.project).resolve()
    s = Path(a.spec)
    build(p, s if s.is_absolute() else p / s)


if __name__ == '__main__':
    main()
