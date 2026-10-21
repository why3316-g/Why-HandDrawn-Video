"""把用户已通过的封面作为成片最开头的几帧（默认 6 帧 = 0.2 s @30fps，约 0.19 s 的视觉停留）。
原因：很多短视频平台默认抓取视频首帧当封面；0.2 s 观众仍能看清封面，且不影响内容。口播和画面整体后移 0.2 s，音画相对关系不变。
用法（项目根目录）：
  python <skill>/scripts/add_cover_intro.py --video renders/x-bgm-v01.mp4 --cover renders/x-cover-v01.png --out renders/x-final-v01.mp4 [--frames 6]
封面开头段静音；输出总帧数 = 原帧数 + frames，时长 = 原时长 + frames/fps；脚本会核对。"""
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); import common  # noqa: F401  PATH 里没有 FFmpeg 时自动补齐
import argparse, json, subprocess, sys, tempfile
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass

ap = argparse.ArgumentParser()
ap.add_argument('--project', default='.'); ap.add_argument('--video', required=True); ap.add_argument('--cover', required=True)
ap.add_argument('--out', required=True); ap.add_argument('--frames', type=int, default=6)
a = ap.parse_args()
P = Path(a.project).resolve()
rp = lambda x: str(x if Path(x).is_absolute() else P / x)
video, cover, out = rp(a.video), rp(a.cover), rp(a.out)
if Path(out).exists():
    sys.exit(f'{a.out} 已存在，不覆盖；请换版本号')


def probe(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate,nb_read_frames,duration', '-of', 'json', f],
                       capture_output=True, text=True, encoding='utf-8')
    st = json.loads(r.stdout)['streams'][0]
    n, d = st['r_frame_rate'].split('/')
    return int(st['width']), int(st['height']), int(n) / int(d), int(st['nb_read_frames']), float(st['duration'])


w, h, fps, n0, d0 = probe(video)
dur = a.frames / fps
fc = (f'[0:v]scale={w}:{h},setsar=1,fps={fps},format=yuv420p[cv];'
      f'[1:v]setsar=1,format=yuv420p[mv];'
      f'[2:a]aresample=44100,apad,atrim=0:{dur:.5f},asetpts=PTS-STARTPTS[ca];'
      f'[1:a]aresample=44100[ma];'
      f'[cv][ca][mv][ma]concat=n=2:v=1:a=1[v][a]')
cmd = ['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-framerate', str(fps), '-t', f'{dur:.5f}', '-i', cover, '-i', video,
       '-f', 'lavfi', '-t', f'{dur:.5f}', '-i', 'anullsrc=r=44100:cl=mono', '-filter_complex', fc, '-map', '[v]', '-map', '[a]',
       '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-r', str(fps), '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out]
r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
if r.returncode:
    sys.exit('ffmpeg 失败：' + r.stderr[-800:])
w2, h2, fps2, n1, d1 = probe(out)
ok = (w2, h2) == (w, h) and n1 == n0 + a.frames
print(f'封面开头 {a.frames} 帧（{dur:.3f} s）；原片 {n0} 帧 {d0:.2f}s → 成片 {n1} 帧 {d1:.2f}s，{w2}x{h2}@{fps2:g}；', '核对通过' if ok else '帧数核对失败！')
if not ok:
    sys.exit(1)
