"""开头动画检查（按渲染出的视频逐帧检测，不看事件表）。规范：references/OPENING_SPEC.md。
检查内容：视频 0–window 秒（默认 5 s）里，画板区域（不含标题栏、不含底部字幕带）是否出现连续超过 max_still 秒（默认 1.0 s）没有任何笔画变化的静止段。
字幕在底部字幕带里，不在检测区域内，所以字幕变化不会被当成"画面在动"。
用法（项目根目录）：
  python <skill>/scripts/opening_check.py --video renders/<名>-final-vNN.mp4 [--window 5] [--max-still 1.0] [--fps 15]
产物：qc/opening-check.json、qc/opening-check.md；有静止超限退出码 1。
检测区域由项目 mode 决定，并核对真实视频尺寸：portrait y285–1430（采样360×640）；landscape y190–900（采样640×360）。排除标题、字幕和小钟；变化阈值保持亮度差>24且至少12像素。
成片含封面帧时，封面 0.2 s 的静止会计入第一段静止，不另外豁免；封面→正片的硬切产生的像素变化会被忽略（--ignore-start，默认 0.25 s；没有封面的预览版传 --ignore-start 0）。"""
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); import common  # noqa: F401  PATH 里没有 FFmpeg 时自动补齐
import argparse, json, subprocess, sys, shutil
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception: pass
import numpy as np
from hdv.layout import project_layout

ap = argparse.ArgumentParser()
ap.add_argument('--project', default='.')
ap.add_argument('--video', required=True)
ap.add_argument('--window', type=float, default=5.0)
ap.add_argument('--max-still', type=float, default=1.0)
ap.add_argument('--fps', type=float, default=15.0)
ap.add_argument('--diff', type=int, default=24, help='像素亮度差阈值')
ap.add_argument('--min-pixels', type=int, default=12, help='变化像素数阈值（最长边640像素）')
ap.add_argument('--ignore-start', type=float, default=0.25, help='忽略开头多少秒内的变化：成片开头 0.2 s 是封面，封面→正片的硬切不算动画；没有封面的预览版传 0')
a = ap.parse_args()
P = Path(a.project).resolve()
video = (P / a.video) if not Path(a.video).is_absolute() else Path(a.video)
ff = shutil.which('ffmpeg') or 'ffmpeg'
layout = project_layout(P)
probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=width,height,duration', '-of', 'json', str(video)], capture_output=True, text=True)
if probe.returncode:
    sys.exit('读取视频画幅失败：' + probe.stderr[-300:])
stream = json.loads(probe.stdout)['streams'][0]
if (stream['width'], stream['height']) != (layout['width'], layout['height']):
    sys.exit('视频尺寸与项目 mode 不一致，拒绝使用错误检测区域；请核对项目与视频版本。')
if a.window <= 0 or a.fps <= 0 or a.max_still <= 0:
    sys.exit('window、fps 和 max-still 必须为正数。')
W, H = (640, 360) if layout['mode'] == 'landscape' else (360, 640)
scale = W / layout['width']
y0, y1 = int(layout['content_top'] * scale), int(layout['opening_bottom'] * scale)
cmd = [ff, '-v', 'error', '-t', str(a.window + 0.1), '-i', str(video), '-vf', f'fps={a.fps},scale={W}:{H},format=gray,crop={W}:{y1 - y0}:0:{y0}', '-f', 'rawvideo', '-']
r = subprocess.run(cmd, capture_output=True)
if r.returncode != 0 or not r.stdout:
    sys.exit('读取视频失败：' + r.stderr.decode('utf-8', 'replace')[:300])
fs = np.frombuffer(r.stdout, np.uint8).reshape(-1, y1 - y0, W).astype(np.int16)
if len(fs) < round(a.window * a.fps):
    sys.exit('视频不足指定检测窗口，不能把缺失帧当作开头检查通过。')
mx0, my0, mx1, my1 = layout['opening_clock_mask']
fs[:, max(0, int(my0 * scale) - y0):max(0, int(my1 * scale) - y0), int(mx0 * scale):int(mx1 * scale)] = 0       # 小钟是装饰，不能算内容动画；宽屏小钟已在检测区之外
n_act = [int((np.abs(fs[i] - fs[i - 1]) > a.diff).sum()) for i in range(1, len(fs))]
dt = 1.0 / a.fps
moving = [n >= a.min_pixels and i * dt >= a.ignore_start for i, n in enumerate(n_act)]   # moving[i] 对应 (i, i+1) 两帧之间；开头封面硬切不算动
# 静止段 = 连续不动的采样间隔；起点算 0 s
runs, start = [], None
for i, m in enumerate(moving):
    t = i * dt
    if not m and start is None: start = t
    if m and start is not None:
        runs.append((round(start, 2), round(t, 2))); start = None
if start is not None: runs.append((round(start, 2), round(min(a.window, len(moving) * dt), 2)))
bad = [(s, e) for s, e in runs if e - s > a.max_still + 1e-9]
first_motion = next((round(i * dt, 2) for i, m in enumerate(moving) if m), None)
out = {'video': str(video), 'mode': layout['mode'], 'video_size': [stream['width'], stream['height']], 'content_roi': [0, layout['content_top'], layout['width'], layout['opening_bottom']], 'window': a.window, 'max_still': a.max_still, 'first_motion_s': first_motion,
       'static_runs_over_0.3s': [(s, e) for s, e in runs if e - s > .3], 'violations': bad, 'pass': not bad}
(P / 'qc').mkdir(exist_ok=True)
(P / 'qc/opening-check.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
md = [f'# 开头动画检查', f'- 视频：{video.name}', f'- 检测：0–{a.window} s，画板区（不含标题栏与字幕带），静止上限 {a.max_still} s', f'- 首次画面变化：{first_motion} s',
      f'- 结论：{"通过" if not bad else "不通过"}']
for s, e in bad: md.append(f'- ✗ {s}–{e} s 静止 {e - s:.2f} s')
(P / 'qc/opening-check.md').write_text('\n'.join(md), encoding='utf-8')
print('\n'.join(md))
sys.exit(0 if not bad else 1)
