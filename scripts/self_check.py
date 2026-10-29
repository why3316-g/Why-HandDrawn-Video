"""一条命令的自检（2026-10-28）：渲染前、成片后各跑一次，机器能查的全部查完，剩下必须人眼看的列清单。
工具无关：Claude / Codex / WorkBuddy / Antigravity 都只是运行这个脚本、再看它生成的联系表，不依赖任何工具专属功能。

  渲染前  python <skill>/scripts/self_check.py --stage pre
          → 构图重建与检测、资产检查、声音锁定、量图新鲜度，并抽每块画板的"写到一半"和"写完"静帧，拼成联系表 qc/self-check/pre-sheet-N.png
  看图后  python <skill>/scripts/self_check.py --ack-viewed "逐块看了联系表：…（写你看到的问题和已改的地方）"
  成片后  python <skill>/scripts/self_check.py --stage post --video renders/<名>-final-vNN.mp4
          → 开头检测、音画对齐、成片封面帧、响度、QA、板完成帧联系表 qc/self-check/post-sheet-N.png

结果写 qc/self-check.md，末行 "结论：可交付审核" 或 "结论：不可交付"。机器项有失败就改到过，不把半成品给用户。
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SK = Path(__file__).resolve().parent
sys.path.insert(0, str(SK))
sys.path.insert(0, str(SK / 'hdv'))
import common  # noqa: E402,F401  PATH 里没有 FFmpeg 时自动补齐

ENV = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')


def run(args, cwd):
    r = subprocess.run([sys.executable, *map(str, args)], cwd=cwd, env=ENV, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout + r.stderr).strip()


def newer(a, b):
    return a.is_file() and b.is_file() and a.stat().st_mtime >= b.stat().st_mtime - 1


class Report:
    def __init__(self):
        self.rows = []
        self.eyes = []

    def add(self, name, ok, detail=''):
        self.rows.append((name, ok, detail))

    def eye(self, text):
        self.eyes.append(text)

    @property
    def ok(self):
        return all(ok for _, ok, _ in self.rows)

    def md(self, title):
        out = [f'# 自检 — {title}', f'- 时间：{time.strftime("%Y-%m-%d %H:%M:%S")}', '', '| 项 | 结果 | 说明 |', '|---|---|---|']
        for n, ok, d in self.rows:
            out.append(f'| {n} | {"通过" if ok else "**失败**"} | {d.replace(chr(10), " ")[:300]} |')
        if self.eyes:
            out += ['', '## 必须人眼看（机器查不出）'] + [f'- {e}' for e in self.eyes]
        out += ['', '结论：可交付审核' if self.ok else '结论：不可交付（先改到全部通过）']
        return '\n'.join(out)


def sheet(images, out, cols, tile):
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype(str(SK.parent / 'assets/fonts/NotoSansSC-VF.ttf'), 18)
    except OSError:
        font = None
    rows = (len(images) + cols - 1) // cols
    s = Image.new('RGB', (tile[0] * cols, tile[1] * rows), 'white')
    for i, (f, label) in enumerate(images):
        im = Image.open(f).convert('RGB').resize(tile)
        ImageDraw.Draw(im).text((6, 4), label, fill=(255, 0, 0), font=font)
        s.paste(im, ((i % cols) * tile[0], (i // cols) * tile[1]))
    s.save(out)


def stage_pre(P, rep):
    spec_path = P / 'design/spec-film.json'
    cfg = json.loads((P / 'design/config.json').read_text(encoding='utf-8'))
    spec_path = P / cfg.get('spec_out', 'design/spec-film.json')
    rep.add('声音已锁定', (P / 'qc/voice-lock.json').is_file(), 'qc/voice-lock.json（用户明确说通过后由 lock_voice.py 写入）')
    rep.add('事件表已生成且比 film.py/breaks.json 新', spec_path.is_file() and newer(spec_path, P / 'design/film.py') and newer(spec_path, P / 'design/breaks.json'), '改过 film.py 后要重跑 python design/film.py')
    meas = P / 'qc/panel-measure.json'
    strokes = P / 'design/sprite-strokes-v01.json'
    rep.add('已量图（measure_panels.py）', meas.is_file() and newer(meas, strokes), '排字前必须先量图；缺失就运行 measure_panels.py 并按联系表定位')
    plan = P / 'design/layout-plan.json'
    rep.add('逐板构图计划 layout-plan.json 已写', plan.is_file(), '每块板自己的理由、摆位、至少两条备选')
    if plan.is_file() and spec_path.is_file():
        code, out = run([SK / 'build_composition.py', '--project', P, '--spec', spec_path], P)
        rep.add('composition.json 由事件表实测重建', code == 0, out[-200:])
        code, out = run([SK / 'check_composition.py', '--project', P, '--spec', spec_path], P)
        try:
            res = json.loads(out.splitlines()[0])
        except (ValueError, IndexError):
            res = {'pass': False, 'errors': [out[-200:]], 'warnings': []}
        rep.add('构图检测（含排字同质化/人物居中/窄人物旁空位/小时钟）', res['pass'], '；'.join(res['errors'])[:300] or f'警告 {len(res.get("warnings", []))} 条')
        for w in res.get('warnings', []):
            rep.eye(f'构图警告：{w}')
    au = P / 'qc/asset-usage.json'
    try:
        ok = json.loads(au.read_text(encoding='utf-8')).get('pass') is True
    except (OSError, ValueError):
        ok = False
    rep.add('资产使用检查（make_manifest.py）', ok and newer(au, P / 'design/film.py'), '改过事件表要重跑 make_manifest.py')
    if not rep.ok:
        return
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    data = spec['data']
    times, labels = [], []
    for sc in data['scenes']:
        ev = [e for e in data['events'] if e.get('index') == sc['index']]
        a = min(e['at'] for e in ev)
        b = max(e['at'] + e['dur'] for e in ev)
        for t, lab in ((a + (b - a) * .5, '写到一半'), (b + .05, '写完')):
            times.append(round(min(t, spec['duration'] - .05), 2))
            labels.append(f"{sc['index']} {sc['id']} {lab}")
    d = P / 'qc/self-check/pre-stills'
    if d.exists():
        for f in d.glob('*.png'):
            f.unlink()
    code, out = run([SK / 'render_film.py', '--project', P, '--spec', spec_path, '--stills', ','.join(str(t) for t in times), '--stills-dir', 'qc/self-check/pre-stills'], P)
    files = sorted(d.glob('*.png'), key=lambda p: float(p.stem[1:])) if d.is_dir() else []
    rep.add('静帧抽取（不整片渲染）', code == 0 and len(files) == len(times), out[-200:])
    if code == 0 and len(files) == len(times):
        layout = data.get('layout', {})
        land = layout.get('mode') == 'landscape'
        tile = (480, 270) if land else (270, 480)
        per = 5
        items = list(zip(files, labels))
        for k in range(0, len(items), per * 2):
            chunk = items[k:k + per * 2]
            ordered = [chunk[j] for j in range(0, len(chunk), 2)] + [chunk[j] for j in range(1, len(chunk), 2)]
            sheet(ordered, P / f'qc/self-check/pre-sheet-{k // (per * 2)}.png', min(per, max(1, len(chunk) // 2)) if len(chunk) > 1 else 1, tile)
        n = len(list((P / 'qc/self-check').glob('pre-sheet-*.png')))
        rep.eye(f'逐张看 qc/self-check/pre-sheet-0..{n - 1}.png（每张上排=写到一半，下排=写完；共 {len(data["scenes"])} 块板）：字是否压到脸/手/道具、是否压右上角小时钟、读序是否顺、窄人物旁空位是否用上、有没有大洞')
        rep.eye('看完后运行：self_check.py --ack-viewed "<逐块看了什么、发现并修了什么>"；没看就不能整片渲染')


def stage_post(P, rep, video):
    v = (P / video) if not Path(video).is_absolute() else Path(video)
    rep.add('成片存在', v.is_file(), str(v))
    ack = P / 'qc/self-check-ack.json'
    rep.add('渲染前已看联系表并记录（--ack-viewed）', ack.is_file(), 'qc/self-check-ack.json')
    if not v.is_file():
        return
    code, out = run([SK / 'opening_check.py', '--project', P, '--video', v], P)
    rep.add('开头检测（成片）', code == 0, out.splitlines()[-1] if out else '')
    code, out = run([SK / 'sync_report.py', '--project', P], P)
    rep.add('音画对齐报告', code == 0, '见 qc/sync-report.md（"需检查"项逐条看）')
    code, out = run([SK / 'qa_project.py', '--project', P], P)
    rep.add('QA（确定性/页面报错/动感）', code == 0, out.splitlines()[-1] if out else '')
    pr = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height,nb_frames', '-show_entries', 'format=duration', '-of', 'json', str(v)], capture_output=True, text=True)
    try:
        info = json.loads(pr.stdout)
        kinds = {s['codec_type'] for s in info['streams']}
        dur = float(info['format']['duration'])
        spec = json.loads((P / json.loads((P / 'design/config.json').read_text(encoding='utf-8')).get('spec_out', 'design/spec-film.json')).read_text(encoding='utf-8'))
        w, h = spec['width'], spec['height']
        vs = [s for s in info['streams'] if s['codec_type'] == 'video'][0]
        ok = kinds == {'video', 'audio'} and (vs['width'], vs['height']) == (w, h) and abs(dur - (spec['duration'] + .2)) < .35
        rep.add('成片规格（音视频齐全、尺寸、时长=正片+封面 0.2 s）', ok, f'{vs["width"]}x{vs["height"]} {dur:.2f}s')
    except (ValueError, KeyError, IndexError, OSError) as ex:
        rep.add('成片规格', False, str(ex))
    mixes = sorted((P / 'qc').glob('mix-report-*.json'), key=lambda p: p.stat().st_mtime)
    if mixes:
        r = json.loads(mixes[-1].read_text(encoding='utf-8'))
        lufs = r.get('input_i')
        rep.add('混音响度 -16±1.5 LUFS，峰值 ≤ -1 dBTP', lufs is not None and abs(float(lufs) + 16) <= 1.5 and float(r.get('input_tp', 0)) <= -1, f'{lufs} LUFS / {r.get("input_tp")} dBTP')
        rep.add('配乐只用库内曲目且无音效', bool(r.get('bgm')), str(r.get('bgm')))
    else:
        rep.add('混音报告存在', False, '缺 qc/mix-report-*.json')
    d = P / 'qc/self-check/post-final'
    d.mkdir(parents=True, exist_ok=True)
    code, out = run([SK / 'panel_check.py', '--project', P, '--video', v, '--offset', '0.2', '--out', d], P)
    rep.add('板完成帧抽取', code == 0, out[-160:])
    files = sorted(d.glob('p*.png'))
    if files:
        land = (json.loads((P / 'design/config.json').read_text(encoding='utf-8')).get('mode') == 'landscape')
        tile = (480, 270) if land else (270, 480)
        for k in range(0, len(files), 10):
            ch = files[k:k + 10]
            sheet([(f, f.stem) for f in ch], P / f'qc/self-check/post-sheet-{k // 10}.png', 5, tile)
        rep.eye(f'看 qc/self-check/post-sheet-*.png（{len(files)} 块板的成片完成帧）与第 0 帧封面、第 6 帧起正片、结尾渐隐')
    rep.eye('用耳朵或转录抽查：口播清晰度、配乐是否盖住人声、前 6 帧是否静音（机器项已查响度，听感需人判断）')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--project', default='.')
    ap.add_argument('--stage', choices=['pre', 'post'])
    ap.add_argument('--video')
    ap.add_argument('--ack-viewed', help='记录你已逐张看过渲染前联系表，并写下发现与处理')
    a = ap.parse_args()
    P = Path(a.project).resolve()
    (P / 'qc/self-check').mkdir(parents=True, exist_ok=True)
    if a.ack_viewed:
        sheets = sorted((P / 'qc/self-check').glob('pre-sheet-*.png'))
        if not sheets:
            print('还没有渲染前联系表：先跑 --stage pre 且全部通过')
            return 2
        if len(a.ack_viewed.strip()) < 20:
            print('--ack-viewed 要写清看到了什么、改了什么（至少一句完整的话）')
            return 2
        rec = {'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'note': a.ack_viewed,
               'sheets': {s.name: hashlib.sha256(s.read_bytes()).hexdigest() for s in sheets}}
        (P / 'qc/self-check-ack.json').write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding='utf-8')
        print('已记录。可以整片渲染。')
        return 0
    if not a.stage:
        ap.error('需要 --stage pre|post 或 --ack-viewed')
    rep = Report()
    if a.stage == 'pre':
        stage_pre(P, rep)
    else:
        if not a.video:
            ap.error('--stage post 需要 --video')
        stage_post(P, rep, a.video)
    text = rep.md(f'{a.stage} 阶段')
    (P / 'qc/self-check.md').write_text(text, encoding='utf-8')
    print(text)
    return 0 if rep.ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
