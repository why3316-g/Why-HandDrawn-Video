"""音画对齐报告：每个文字事件的出现时间，对照口播里该词被说出的时间（取离事件最近的一次出现）。
输出 qc/sync-report.md。偏差判读：文字应在词说出前后 ±0.5s 内出现；晚于 0.5s 或早于 1.0s 标记为需检查。
用法（项目根目录）：python <skill>/scripts/sync_report.py"""
import argparse, json, sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hdv import Clock

ap = argparse.ArgumentParser()
ap.add_argument('--project', default='.')
a = ap.parse_args()
P = Path(a.project).resolve()
cfg = json.loads((P / 'design/config.json').read_text(encoding='utf-8'))
spec = json.loads((P / cfg.get('spec_out', 'design/spec-film.json')).read_text(encoding='utf-8'))
clock = Clock(str(P / cfg['narration']), str(P / cfg['volc_json']))
txt = clock.text if hasattr(clock, 'text') else (P / cfg['narration']).read_text(encoding='utf-8')
rows, bad = [], 0
for e in spec['data']['events']:
    if e['kind'] != 'text':
        continue
    s = e['str'].strip()
    best = None
    n = 0
    while True:
        try:
            t = clock.T(s, n)[0]
        except (SystemExit, IndexError):
            break
        if best is None or abs(t - e['at']) < abs(best - e['at']):
            best = t
        n += 1
        if n > 12:
            break
    if best is None:
        rows.append(f"| {e['index']} | {s} | {e['at']:.2f} | — | — | 口播里没有这个词（图上标注，允许） |")
        continue
    d = e['at'] - best
    flag = '' if -1.0 <= d <= .5 else '需检查'
    bad += bool(flag)
    rows.append(f"| {e['index']} | {s} | {e['at']:.2f} | {best:.2f} | {d:+.2f} | {flag} |")
out = ['# 音画对齐报告', '', '| 画板 | 文字 | 出现(s) | 说出(s) | 偏差 | 判读 |', '|---|---|---|---|---|---|'] + rows
(P / 'qc/sync-report.md').write_text('\n'.join(out), encoding='utf-8')
print(f'文字事件 {len(rows)} 个，需检查 {bad} 个 → qc/sync-report.md')
