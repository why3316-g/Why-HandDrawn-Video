"""从成品线稿图提取"手要描的笔画路径"（骨架化），写入 design/sprite-strokes-v01.json。不修改任何图片。
图片清单取自 design/shots.json：每个 shot 的 assets[]（默认 assets/images/C-<id>-v01.png），以及仅供旧项目兼容的 fixed_assets。
用法（项目根目录）：python <skill>/scripts/analyze_strokes.py [id ...]      已分析过的 id 跳过；加 --force 重算。"""
import argparse, hashlib, json, sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pen_analysis import skeleton, paths_from, order

ap = argparse.ArgumentParser()
ap.add_argument('ids', nargs='*')
ap.add_argument('--force', action='store_true')
ap.add_argument('--project', default='.')
a = ap.parse_args()
P = Path(a.project).resolve()
shots = json.loads((P / 'design/shots.json').read_text(encoding='utf-8'))
files = {}
for s in shots['shots']:
    if s.get('generate', True):
        aid = s.get('asset', s['id'])
        files[aid] = s.get('image_file') or f"assets/images/C-{aid}-v01.png"
for k, v in shots.get('fixed_assets', {}).items():
    files[k] = v['file']
OUT = P / 'design/sprite-strokes-v01.json'
lib = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {'source_images': {}, 'sprites': {}}
for sid in (a.ids or list(files)):
    f = P / files[sid]
    if not f.exists():
        print('缺图', sid, f); continue
    if sid in lib['sprites'] and not a.force:
        print('skip', sid); continue
    im = Image.open(f).convert('RGB')
    px = np.asarray(im)
    yy, xx = np.nonzero(px.mean(axis=2) < 224)
    left, right = max(0, int(xx.min()) - 4), min(im.width, int(xx.max()) + 5)
    top, bottom = max(0, int(yy.min()) - 4), min(im.height, int(yy.max()) + 5)
    crop = px[top:bottom, left:right]
    ch, cw = crop.shape[:2]
    scale = min(1, 520 / ch)                                           # 只缩放内存里的分析副本，原图不动
    view = np.asarray(Image.fromarray(crop).resize((max(1, round(cw * scale)), max(1, round(ch * scale))), Image.Resampling.LANCZOS))
    ink = view.mean(axis=2) < 183
    paths = order(paths_from(skeleton(ink)), ink.shape[0])
    paths = [[[round(x / scale, 2), round(y / scale, 2)] for x, y in q] for q in paths]
    lib['source_images'][sid] = {'file': f.name, 'width': im.width, 'height': im.height, 'sha256': hashlib.sha256(f.read_bytes()).hexdigest()}
    lib['sprites'][sid] = {'group': sid, 'rect': [left, top, cw, ch], 'paths': paths, 'brush': max(10, 14 / scale), 'path_count': len(paths), 'analysis_scale': scale}
    print(sid, 'crop', cw, 'x', ch, 'paths', len(paths), flush=True)
OUT.write_text(json.dumps(lib, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print('写入', OUT)
