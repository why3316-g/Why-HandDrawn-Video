"""渲染后自检：从成片里抽出"每块画板画完的那一帧"，生成逐块大图和联系表，供逐块目检（圈有没有圈住字、字与人物有没有压、有没有被字幕带挡、人物有没有被裁）。
为什么：之前抽静帧用的是固定时间点，常落在画板平移或笔画中途，看到问题也被当成"还没画完"放过（小彬片 8 s 的"第一"、41 s 的"小棋王"圈错位就是这样漏的）。
抽帧时刻 = min(本块最后一个事件结束 + 0.12 s, 镜头平移起点 + 0.15 s)；平移起点 = 下一块起点 - 0.5 s。样板的设计是口播最后一句边说边写，会延续到镜头平移开始之后；这些抽帧时刻之后才写完的内容列在 panel-final-times.json 的 late 里，要另外对照事件表坐标和 lint 结果核对。
用法（项目根目录）：
  python <skill>/scripts/panel_check.py --video renders/<名>-final-v01.mp4 [--offset 0.2]
  --offset：成片开头有封面帧时填封面时长（0.2），默认从 design/spec-film.json 无偏移计算。
产物：qc/panel-final/pNN-<id>.png（逐块大图）、sheet-1.png、sheet-2.png（每张 8 块）、panel-final-times.json。
看图必须逐块回答并写进 qc/panel-final-review.md：①圈/箭头/叉有没有指对地方 ②文字有没有互相压、有没有压到人物 ③有没有进入底部字幕带 ④人物有没有被意外裁切 ⑤手写字是否已写完。任一项不合格 → 改事件表、重渲染受影响版本，再抽一遍。"""
import argparse, json, subprocess, sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass
from PIL import Image, ImageDraw, ImageFont
from common import SKILL

ap = argparse.ArgumentParser()
ap.add_argument('--project', default='.'); ap.add_argument('--video', required=True); ap.add_argument('--offset', type=float, default=0.0)
ap.add_argument('--spec', default='design/spec-film.json'); ap.add_argument('--out', default='qc/panel-final')
a = ap.parse_args()
P = Path(a.project).resolve()
film_spec = json.loads((P / a.spec).read_text(encoding='utf-8'))
spec = film_spec['data']
out = P / a.out; out.mkdir(parents=True, exist_ok=True)
video = a.video if Path(a.video).is_absolute() else str(P / a.video)
scenes, events = spec['scenes'], spec['events']
times = []
for k, sc in enumerate(scenes):
    evs = [e for e in events if e['index'] == sc['index']]
    done = max(e['at'] + e['dur'] for e in evs) + .15
    nxt = scenes[k + 1]['start'] - .5 + .15 if k + 1 < len(scenes) else sc['end'] + 9
    tt = round(max(sc['start'] + .3, min(done - .03, nxt)), 2)
    late = [e.get('str') or e.get('tag') or e['kind'] for e in evs if e['at'] + e['dur'] > tt]
    times.append({'index': sc['index'], 'id': sc['id'], 'time': tt, 'last_event_end': round(done - .15, 2), 'late': late})
files = []
for t in times:
    f = out / f"p{t['index']:02d}-{t['id']}.png"
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f"{t['time'] + a.offset:.3f}", '-i', video, '-frames:v', '1', str(f)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode or not f.exists():
        sys.exit('抽帧失败：' + r.stderr[-300:])
    files.append((t, f))
(out / 'panel-final-times.json').write_text(json.dumps(times, ensure_ascii=False, indent=1), encoding='utf-8')
try: font = ImageFont.truetype(str(SKILL / 'assets/fonts/NotoSansSC-VF.ttf'), 26)
except Exception: font = None
W, H = (720, 405) if film_spec['width'] > film_spec['height'] else (405, 720)
for n in range(0, len(files), 8):
    chunk = files[n:n + 8]
    sh = Image.new('RGB', (W * 4, H * 2), 'white'); d = ImageDraw.Draw(sh)
    for k, (t, f) in enumerate(chunk):
        im = Image.open(f).convert('RGB').resize((W, H))
        x, y = (k % 4) * W, (k // 4) * H
        sh.paste(im, (x, y)); d.rectangle((x, y, x + W - 1, y + H - 1), outline=(190, 190, 190))
        d.text((x + 8, y + 4), f"{t['index']} {t['id']} @{t['time']}s", fill=(200, 0, 0), font=font)
    sh.save(out / f'sheet-{n // 8 + 1}.png')
for t in times:
    if t['late']: print(f"  板{t['index']} {t['id']}：抽帧后才写完 {t['late']}")
print(f'{len(files)} 块画板完成帧 → {a.out}/（联系表 sheet-*.png，逐块大图 pNN-*.png）')
print('请逐块目检并写 qc/panel-final-review.md：圈/箭头是否指对、文字是否互压或压人物、是否进字幕带、人物是否被裁、字是否写完。')
