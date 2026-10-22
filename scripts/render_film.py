"""渲染：花叔引擎 render.py 的统一入口（设好 UTF-8、浏览器目录），整片渲染前强制要求人物资产检查通过。
用法（项目根目录）：
  python <skill>/scripts/render_film.py --stills 3,12,40 [--sheet]          抽静帧（预览，不需要资产检查）
  python <skill>/scripts/render_film.py --out renders/<名>-visual-v01.mp4   整片（需 qc/asset-usage.json 通过；--draft 可跳过，产物只能当草稿）"""
import argparse, json, os, subprocess, sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import playwright_browsers, which
from hdv.layout import project_layout, validate_spec_layout

ap = argparse.ArgumentParser()
ap.add_argument('--project', default='.')
ap.add_argument('--spec', default=None)
ap.add_argument('--out', default=None)
ap.add_argument('--stills', default=None)
ap.add_argument('--stills-dir', default='qc/stills')
ap.add_argument('--sheet', action='store_true')
ap.add_argument('--draft', action='store_true', help='跳过资产检查（只能产出草稿）')
ap.add_argument('--offline', action='store_true')
a = ap.parse_args()
P = Path(a.project).resolve()
cfg = json.loads((P / 'design/config.json').read_text(encoding='utf-8'))
spec = Path(a.spec) if a.spec else P / cfg.get('spec_out', 'design/spec-film.json')
if not spec.is_absolute():
    spec = P / spec
layout = project_layout(P)
try:
    validate_spec_layout(json.loads(spec.read_text(encoding='utf-8')), layout)
except ValueError as e:
    sys.exit(str(e))
env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
pb = playwright_browsers()
if pb:
    env.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(pb))
uv = which('uv', 'uv.exe')
base = [uv, 'run'] + (['--offline'] if a.offline else []) + ['--no-project', '--with', 'playwright', 'python', '-u', str(P / 'engine/render.py'), '--spec', str(spec)]
if a.stills:
    d = P / a.stills_dir
    d.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(base + ['--stills', a.stills, '--out', str(d)], cwd=P, env=env, capture_output=True, text=True)
    print((r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else '')
    if r.returncode:
        sys.exit(r.returncode)
    if a.sheet:
        from PIL import Image
        fs = sorted(d.glob('*.png'), key=lambda p: float(p.stem[1:]))
        W, H, cols = (480, 270, 3) if layout['mode'] == 'landscape' else (270, 480, 6)
        S = Image.new('RGB', (W * cols, H * ((len(fs) + cols - 1) // cols)), 'white')
        for i, f in enumerate(fs):
            S.paste(Image.open(f).convert('RGB').resize((W, H)), ((i % cols) * W, (i // cols) * H))
        S.save(d / 'sheet.png'); print('联系表：', d / 'sheet.png')
    sys.exit(0)
if not a.out:
    sys.exit('整片渲染需要 --out')
chk = P / 'qc/asset-usage.json'
if not a.draft:
    if not chk.is_file() or not json.loads(chk.read_text(encoding='utf-8')).get('pass'):
        sys.exit('资产使用检查未通过或未运行：先运行 make_manifest.py（规范要求：检查不通过禁止渲染）。仅做草稿可加 --draft。')
out = P / a.out
if out.exists():
    sys.exit(f'不覆盖已存在的产物：{out}（请用新版本号）')
out.parent.mkdir(parents=True, exist_ok=True)
r = subprocess.run(base + ['--out', str(out)], cwd=P, env=env, capture_output=True, text=True)
tail = [l for l in (r.stdout + r.stderr).splitlines() if 'willReadFrequently' not in l]
print('\n'.join(tail[-4:]))
if r.returncode:
    sys.exit(r.returncode)
d = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'stream=width,height,r_frame_rate,nb_frames,duration', '-of', 'json', str(out)], text=True))['streams'][0]
sp = json.loads(spec.read_text(encoding='utf-8'))
want = round(sp['duration'] * sp['fps'])
print(f"{d['width']}x{d['height']} {d['r_frame_rate']} 帧数 {d['nb_frames']}（期望 {want}）时长 {d['duration']}")
sys.exit(0 if int(d['nb_frames']) == want and (d['width'], d['height']) == (layout['width'], layout['height']) else 2)
