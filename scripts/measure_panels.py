"""排字前先量图：每张人物图的真实占位、三种摆位（居中/靠左/靠右）和各摆位的可写空区。

用法：python <skill>/scripts/measure_panels.py [--project .] [--hero-h 640]
读 design/sprite-strokes-v01.json（第 6 步产物），写 qc/panel-measure.json 和 qc/panel-measure/sheet-N.png（带网格联系表）。
写 design/layout-plan.json、film.py 的 hero 位置和文字坐标时必须引用这份数据（EDITING_COMPOSITION 第 9 节）。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hdv.layout import project_layout  # noqa: E402

GAP = 40          # 文字与人物之间至少留的空
SIDE_MARGIN = 120  # 靠边摆位时人物离画板边的距离


def hero_size(aspect, layout, hero_h=None):
    if layout['mode'] == 'portrait':
        h = hero_h or 640
        h = min(h, 960 / aspect)
        top = max(480, 800 - h / 2)
    else:
        h = hero_h or 560
        h = min(h, layout['width'] * .5 / aspect)
        mid = (layout['content_top'] + layout['content_bottom']) / 2
        top = mid - h / 2
    return h, top


def zones(cx, top, h, aspect, layout):
    """某摆位下四个方向的空区；带宽度可容纳字数（按 60 号字估）。"""
    tb = layout['text_bounds']
    w = h * aspect
    x0, x1, y1 = cx - w / 2, cx + w / 2, top + h
    clock = layout['clock']  # [cx, cy, r]
    clock_x0 = clock[0] - clock[2] - 20
    clock_band = (clock[1] - clock[2] - 20, clock[1] + clock[2] + 20)

    def make(name, rx0, ry0, rx1, ry1):
        if rx1 - rx0 < 120 or ry1 - ry0 < 60:
            return None
        # 顶部横条与小时钟同高时，右端让出时钟
        if ry0 < clock_band[1] and ry1 > clock_band[0] and rx1 > clock_x0:
            rx1 = min(rx1, clock_x0)
        return {'name': name, 'box': [round(rx0), round(ry0), round(rx1), round(ry1)],
                'chars_at_60': int((rx1 - rx0) // 60), 'lines_at_60': int((ry1 - ry0) // 80)}

    zs = [make('left', tb[0], top, x0 - GAP, y1),
          make('right', x1 + GAP, top, tb[2], y1),
          make('above', tb[0], tb[1], tb[2], top - 20),
          make('below', tb[0], y1 + 30, tb[2], tb[3])]
    return [z for z in zs if z], [round(x0), round(top), round(x1), round(y1)]


def measure(project, hero_h=None):
    layout = project_layout(project)
    lib = json.loads((project / 'design/sprite-strokes-v01.json').read_text(encoding='utf-8'))
    out = {'mode': layout['mode'], 'hero_h_cap': hero_h, 'layout': {k: layout[k] for k in ('width', 'height', 'text_bounds', 'caption_top', 'clock')}, 'sprites': {}}
    W = layout['width']
    for sid, sp in lib['sprites'].items():
        r = sp['rect']
        aspect = r[2] / r[3]
        h, top = hero_size(aspect, layout, hero_h)
        w = h * aspect
        pl = {}
        for name, cx in (('center', W / 2), ('left', SIDE_MARGIN + w / 2), ('right', W - SIDE_MARGIN - w / 2)):
            zs, box = zones(cx, top, h, aspect, layout)
            pl[name] = {'cx': round(cx), 'hero_box': box, 'zones': zs}
        out['sprites'][sid] = {'aspect': round(aspect, 3), 'hero_h': round(h), 'hero_w': round(w), 'top': round(top),
                               'narrow': w < W * .45, 'placements': pl}
    return out, lib


def sheets(project, out, lib):
    from PIL import Image, ImageDraw
    layout = project_layout(project)
    W, H = layout['width'], layout['height']
    sc = 330 / W
    d = project / 'qc/panel-measure'
    d.mkdir(parents=True, exist_ok=True)
    ids = list(out['sprites'])
    for k in range(0, len(ids), 5):
        sheet = Image.new('RGB', (5 * 336, int(H * sc) + 22), 'white')
        for j, sid in enumerate(ids[k:k + 5]):
            m = out['sprites'][sid]
            src = project / 'assets/images' / lib['source_images'][sid]['file']
            c = Image.new('RGB', (W, H), 'white')
            dr = ImageDraw.Draw(c)
            tb = layout['text_bounds']
            dr.rectangle(tb, outline=(190, 190, 190), width=3)
            dr.rectangle([0, layout['caption_top'], W, layout['caption_top'] + layout['caption_height']], outline=(0, 160, 0), width=4)
            cx, cy, cr = layout['clock']
            dr.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], outline=(120, 120, 120), width=3)
            if src.is_file():
                r = lib['sprites'][sid]['rect']
                im = Image.open(src).convert('RGB').crop((r[0], r[1], r[0] + r[2], r[1] + r[3])).resize((m['hero_w'], m['hero_h']))
                c.paste(im, (round(W / 2 - m['hero_w'] / 2), m['top']))
            for name, col in (('left', (220, 0, 0)), ('right', (0, 120, 220))):
                b = m['placements'][name]['hero_box']
                dr.rectangle(b, outline=col, width=4)
                dr.text((b[0] + 6, b[1] + 6), name, fill=col)
            for z in m['placements']['center']['zones']:
                dr.rectangle(z['box'], outline=(255, 150, 0), width=3)
                dr.text((z['box'][0] + 8, z['box'][1] + 8), f"{z['name']} {z['chars_at_60']}字", fill=(255, 120, 0))
            t = c.resize((int(W * sc), int(H * sc)))
            ImageDraw.Draw(t).text((4, 2), f'{k + j} {sid}', fill=(0, 0, 0))
            sheet.paste(t, (j * 336, 22))
        sheet.save(d / f'sheet-{k // 5}.png')
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project', default='.')
    ap.add_argument('--hero-h', type=int, default=None)
    a = ap.parse_args()
    p = Path(a.project).resolve()
    try:
        out, lib = measure(p, a.hero_h)
    except OSError as ex:
        print(f'缺少笔画提取结果（先完成第 6 步 analyze_strokes.py）：{ex}')
        return 2
    (p / 'qc').mkdir(exist_ok=True)
    (p / 'qc/panel-measure.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    d = sheets(p, out, lib)
    n = len(out['sprites'])
    narrow = [s for s, v in out['sprites'].items() if v['narrow']]
    print(f'已量 {n} 张图 -> qc/panel-measure.json；联系表 {d}')
    print(f'窄人物 {len(narrow)} 张（可移到一侧、字写在另一侧空区）：{", ".join(narrow)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
