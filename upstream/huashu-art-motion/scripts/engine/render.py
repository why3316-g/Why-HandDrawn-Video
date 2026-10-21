#!/usr/bin/env python3
"""固定手绘逐帧渲染：本地 http → Chromium clip.html → renderFrame(t) → FFmpeg。

uv run --with playwright python render.py --spec clip.json --out 画面.mp4 [--stills 0.5,2]
    只接收 hand_drawn_marker spec；时长严格 = spec.duration（帧数 round(duration×fps)）。
    宽高/fps 从 spec 读；无声 H.264 yuv420p、每秒一个关键帧（GOP=fps）。音频由工作流的混音步骤添加。
    spec 里图片路径相对 spec 文件。
页面里有 pageerror 或 console.error（场景报错、缺字形）→ 渲完后非零退出。
"""
import argparse, base64, http.server, json, socketserver, subprocess, threading, functools, time, urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--stills', help='逗号分隔秒数：只导出这些时刻的 png 到 --out 目录')
ap.add_argument('--crf', type=int, default=14)
ap.add_argument('--spec', required=True, help='Why-HandDrawn-Video 的 hand_drawn_marker spec.json')
a = ap.parse_args()

root = Path(__file__).parent
spec = None
if a.spec:
    sp = Path(a.spec).resolve(); spec = json.loads(sp.read_text())
    if spec.get('grammar') != 'hand_drawn_marker':
        ap.error('本包只支持 hand_drawn_marker；请使用固定手绘事件表生成 spec。')
    def ref(v):                                            # 本地图片 → /__file__/<绝对路径>（只服务 spec 里点名的文件）
        if not v or v.startswith(('data:', 'http:', 'https:')): return v
        f = (sp.parent / v).resolve()
        if not f.exists(): raise SystemExit(f'spec 里的图片不存在：{v}（相对 {sp.parent}）')
        ALLOWED.add(str(f)); return '/__file__/' + urllib.parse.quote(str(f))
    ALLOWED = set()
    for q in spec.get('cues', []):
        if q.get('image'): q['image'] = ref(q['image'])
    if (spec.get('data') or {}).get('image'): spec['data']['image'] = ref(spec['data']['image'])
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *x): pass
    def translate_path(self, path):
        if path.startswith('/__file__/'):
            f = urllib.parse.unquote(path[len('/__file__/'):].split('?')[0])
            return f if spec and f in ALLOWED else '/nonexistent'
        return super().translate_path(path)
srv = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(root)))
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

with sync_playwright() as p:
    b = p.chromium.launch(args=['--disable-web-security', '--enable-gpu-rasterization', '--ignore-gpu-blocklist'])
    pg = b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    errors = []
    def on_console(m):
        if m.type in ('error', 'warning'): print('[page]', m.text)
        if m.type == 'error': errors.append(m.text)
    pg.on('console', on_console)
    pg.on('pageerror', lambda e: (print('[pageerror]', e), errors.append(str(e))))
    pg.set_viewport_size({'width': spec.get('width', 1920), 'height': spec.get('height', 1080)})
    pg.add_init_script('window.CLIP_SPEC = ' + json.dumps(spec, ensure_ascii=False) + ';')
    pg.goto(f'http://127.0.0.1:{port}/clip.html?render=1')
    pg.wait_for_function('window.__ready === true || !!window.__bootFailed', timeout=120000)
    bf = pg.evaluate('window.__bootFailed || null')
    if bf: raise SystemExit('场景加载失败，拒绝渲染：\n' + bf)
    fps = spec.get('fps', 30); duration = spec['duration']
    grab = '''async (t)=>{ await window.prepare(t); window.renderFrame(t); return window.__canvas.toDataURL('image/png').split(',')[1]; }'''
    if a.stills:
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
        for s in a.stills.split(','):
            (out / f't{float(s):06.2f}.png').write_bytes(base64.b64decode(pg.evaluate(grab, float(s))))
        print('stills ->', out)
    else:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        enc = ['-c:v', 'libx264', '-preset', 'slow', '-crf', str(a.crf), '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
               '-g', str(fps), '-keyint_min', str(fps), '-sc_threshold', '0']
        ff = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'image2pipe', '-framerate', str(fps), '-c:v', 'png', '-i', '-'] + enc + [a.out],
                              stdin=subprocess.PIPE)
        n0, n1 = 0, round(duration * fps)
        st = time.time()
        for i in range(n0, n1):
            ff.stdin.write(base64.b64decode(pg.evaluate(grab, i / fps)))
            if (i - n0) % 60 == 0:
                print(f'{i}/{n1}  {time.time()-st:.0f}s', flush=True)
        ff.stdin.close(); ff.wait()
        print('done ->', a.out)
    b.close()
srv.shutdown()
if errors: raise SystemExit(f'❌ 页面报错 {len(errors)} 条（见上方 [page]/[pageerror]）')
