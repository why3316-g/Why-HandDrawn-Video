"""成片混音：口播 + 配乐（授权闸门 + 人声下压；不用音效），响度归一到 -16 LUFS，封装进画面视频。
用法（项目根目录）：
  python <skill>/scripts/mix_audio.py --video renders/x-visual-v01.mp4 --out renders/x-final-v01.mp4 --bgm 曲目文件名 [--bgm-lufs 数值]
  不要配乐必须明确写 --no-bgm；本 Skill 不使用音效（规范，用户 2026-10-12 决定）。
规则：
- 口播取 design/config.json 的 voice_wav（对齐母带）。
- 配乐只能用 <library>/bgm/ 里、且在 <library>/LICENSES.md 登记"可商用"以"是"开头的文件；未登记或不可商用 → 拒绝（--draft 例外，产物标草稿，不得发布）。
  --bgm 由工作流中的当前执行本工作流的 AI 工具按脚本文案自动选定后传入，不等待用户挑曲。
- 配乐先按响度归一到 --bgm-lufs，口播出现时再 sidechain 压低；整体 loudnorm I=-16 TP=-1.5。优先读取 assets/audio-library/bgm-levels.json 的曲目专属响度；没有登记值时自动使用 -28 LUFS 并写入报告，不等待试听或人工认可。
"""
import argparse, json, re, subprocess, sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import find_library

SR = 44100
ap = argparse.ArgumentParser()
ap.add_argument('--project', default='.')
ap.add_argument('--video', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--bgm', default=None, help='bgm 目录里的文件名')
ap.add_argument('--no-bgm', action='store_true')
ap.add_argument('--library', default=None)
ap.add_argument('--draft', action='store_true')
ap.add_argument('--bgm-lufs', type=float, default=None, help='不写则查 assets/audio-library/bgm-levels.json 里该曲目的已认可值')
a = ap.parse_args()
P = Path(a.project).resolve()
cfg = json.loads((P / 'design/config.json').read_text(encoding='utf-8'))
spec = json.loads((P / cfg.get('spec_out', 'design/spec-film.json')).read_text(encoding='utf-8'))
lib = Path(a.library).resolve() if a.library else find_library(P)
voice = P / cfg['voice_wav']
if not voice.is_file():
    sys.exit(f'找不到口播母带：{voice}')
out = P / a.out
if out.exists():
    sys.exit(f'不覆盖已存在的产物：{out}')
out.parent.mkdir(parents=True, exist_ok=True)
notes, warns = [], []
total = spec['duration']


def decode(path, ss=None, t=None):
    cmd = ['ffmpeg', '-v', 'error'] + (['-ss', str(ss)] if ss else []) + (['-t', str(t)] if t else []) + ['-i', str(path), '-ac', '1', '-ar', str(SR), '-f', 's16le', '-']
    return np.frombuffer(subprocess.check_output(cmd), dtype='<i2').astype(np.float32) / 32768


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


def db(x):
    return 20 * np.log10(max(x, 1e-9))


# ---------- 配乐 ----------
def licensed(lib, name):
    f = lib / 'LICENSES.md'
    if not f.is_file():
        return False, '没有 LICENSES.md'
    for ln in f.read_text(encoding='utf-8').splitlines():
        cells = [c.strip() for c in ln.strip().strip('|').split('|')]
        if len(cells) >= 4 and cells[0] == name:
            v = cells[3]
            ok = v.startswith('是') or v.lower() in ('yes', 'y')
            return ok, ('已登记，可商用：' + v if ok else f'已登记但"可商用"为"{v}"')
    return False, '未在 LICENSES.md 登记'


bgm_path = None
if a.no_bgm:
    notes.append('配乐：按要求不用（--no-bgm）')
else:
    bdir = lib / 'bgm' if lib else None
    cands = sorted(f for f in bdir.iterdir() if f.suffix.lower() in ('.mp3', '.wav', '.m4a', '.flac')) if bdir and bdir.is_dir() else []
    if not cands:
        sys.exit(f'配乐库 {bdir} 里没有曲目。要无配乐版请明确写 --no-bgm。')
    if not a.bgm:
        sys.exit('缺少工作流选定的配乐参数。当前执行本工作流的 AI 工具应依据脚本文案从已授权曲目中自动选定一首并传入 --bgm；不要暂停等待用户挑曲。')
    pick = [f for f in cands if f.name == a.bgm]
    if not pick:
        sys.exit(f'配乐库里没有 {a.bgm}；现有：' + '、'.join(f.name for f in cands))
    ok, why = licensed(lib, pick[0].name)
    if not ok and not a.draft:
        sys.exit(f'配乐 {pick[0].name} 拒绝使用：{why}')
    bgm_path = pick[0]
    notes.append(f'配乐 {bgm_path.name}: ' + (why if ok else f'{why}，仅草稿，禁止发布'))

# 本流程不用音效；旧项目留下的提示表不参与混音。
notes.append('音效：不用（规范）')
voice_arr = decode(voice)

# ---------- ffmpeg ----------
inputs, fc = ['-i', str(a.video if Path(a.video).is_absolute() else P / a.video), '-i', str(voice)], []
idx = 2
fc.append(f'[1:a]aresample=44100,pan=mono|c0=c0,apad=whole_dur={total},asplit=2[v1][v2]')
mix_in = ['[v1]']
if bgm_path:
    seg = decode(bgm_path, t=total)
    m = subprocess.run(['ffmpeg', '-v', 'info', '-t', str(total), '-i', str(bgm_path), '-af', 'loudnorm=I=-16:TP=-1.5:print_format=json', '-vn', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
    mm = re.search(r'\{[^{}]*"input_i"[^{}]*\}', m, re.S)
    bl = float(json.loads(mm.group(0))['input_i']) if mm else -16.0
    if a.bgm_lufs is None:
        lv = json.loads((bgm_path.parent.parent / 'bgm-levels.json').read_text(encoding='utf-8')) if (bgm_path.parent.parent / 'bgm-levels.json').is_file() else {}
        if bgm_path.name in lv and 'bgm_lufs' in lv[bgm_path.name]:
            a.bgm_lufs = float(lv[bgm_path.name]['bgm_lufs'])
            notes.append(f'配乐响度取曲目登记值 {a.bgm_lufs} LUFS（bgm-levels.json）')
        else:
            a.bgm_lufs = -28.0
            notes.append('配乐没有曲目专属响度登记，自动采用默认目标 -28 LUFS')
    gain_db = a.bgm_lufs - bl
    notes.append(f'配乐实测 {bl:.1f} LUFS，增益 {gain_db:+.1f} dB → 目标 {a.bgm_lufs} LUFS（口播约 -16 LUFS）')
    ba = seg[:len(voice_arr)] * (10 ** (gain_db / 20)); va = voice_arr[:len(ba)]
    act = np.convolve(np.abs(va), np.ones(2205) / 2205, 'same') > 0.02          # 口播在说话的片段
    if act.any():
        bgm_vs_voice = db(rms(ba[act])) - db(rms(va[act]))
        notes.append(f'配乐相对口播（说话时，压低前）{bgm_vs_voice:.1f} dB')
    inputs += ['-stream_loop', '-1', '-i', str(bgm_path)]
    fade_out = max(0, total - 2.5)
    fc.append(f'[{idx}:a]aresample=44100,pan=mono|c0=0.5*c0+0.5*c1,atrim=0:{total},volume={gain_db:.2f}dB,afade=t=in:d=2,afade=t=out:st={fade_out}:d=2.5[b0]')
    fc.append('[b0][v2]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[b1]')
    mix_in.append('[b1]'); idx += 1
else:
    fc.append('[v2]anullsink')
fc.append(f"{''.join(mix_in)}amix=inputs={len(mix_in)}:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
cmd = ['ffmpeg', '-v', 'error', '-y'] + inputs + ['-filter_complex', ';'.join(fc), '-map', '0:v', '-map', '[aout]', '-c:v', 'copy',
                                                  '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-t', str(total), str(out)]
r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
if r.returncode:
    sys.exit('ffmpeg 失败：\n' + r.stderr[-1500:])
m = subprocess.run(['ffmpeg', '-v', 'info', '-i', str(out), '-af', 'loudnorm=I=-16:TP=-1.5:print_format=json', '-vn', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
mm = re.search(r'\{[^{}]*"input_i"[^{}]*\}', m, re.S)
loud = json.loads(mm.group(0)) if mm else {}
rep = {'out': str(out), 'draft': bool(a.draft and bgm_path and not licensed(lib, bgm_path.name)[0]), 'input_i': loud.get('input_i'), 'input_tp': loud.get('input_tp'),
       'bgm': bgm_path.name if bgm_path else None, 'bgm_vs_voice_db_before_ducking': round(bgm_vs_voice, 1) if bgm_path and 'bgm_vs_voice' in dir() else None, 'cues': [], 'notes': notes, 'warnings': warns}
(P / 'qc').mkdir(exist_ok=True)
name = Path(a.out).stem
(P / f'qc/mix-report-{name}.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
print('\n'.join(notes))
for w in warns:
    print('警告：' + w)
print(f"响度 {loud.get('input_i')} LUFS  峰值 {loud.get('input_tp')} dBTP")
