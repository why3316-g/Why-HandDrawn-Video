"""配音自检（锁定声音之前和之后都要跑）：检查口播有没有突然变快/变慢、突然变小、漏读/多读/读错。
背景：2026-10-12 小彬片 54 s「那不是土，是你的来处」被 TTS 压缩成每字 0.06 s（正常约 0.17 s），声音又小又快听不清；
当时只靠整体转录相似度 0.964 和人工试听，没有逐句检查，放过了。
用法（项目根目录）：python <skill>/scripts/check_voice.py [--no-asr]
读 design/config.json 的 narration / volc_json / voice_wav；输出 qc/voice-check.json 与 qc/voice-check.md；有红色问题退出码 1。
四项检查：
  1 语速：每句字/秒，对比全片中位数（>1.3× 或 <0.7× 报）；任意连续 4 字窗口 < 0.30 s（>13 字/s；正常快读最短约 0.32 s，坏的那处 0.27 s）报"局部压缩"；句内非标点停顿 > 0.9 s 报"异常停顿"。
  2 响度：每个字的时间段 RMS（dB），连续 ≥3 字低于全片说话中位数 8 dB 以上报"突然变小"；整句中位响度比全片中位低 3.2 dB 报黄、低 6 dB 报红。电平只是辅助信号，最终以人耳为准。
  3 转录对照：用 faster-whisper 按句切片转录，与原稿同句比对；相似度 < 0.80 或出现整句缺失报"可能读错/漏读"（同音字误识会有，所以只在相似度低时报，并列出转录文本供人耳复核）。
  4 全文对照：整段转录与原稿的缺字、多字统计（只报告，不当红灯）。
红色问题必须处理：先人耳听那一句；确认有问题 → 按 references/workspace/AUDIO_STANDARD.md 经用户同意后重新全文合成（不得分段合成/拼接/变速修补）。"""
import argparse, difflib, json, os, re, statistics, sys, wave
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('--project', default='.'); ap.add_argument('--no-asr', action='store_true')
ap.add_argument('--asr-model', default=os.environ.get('HDV_ASR_MODEL', 'small'), help='独立转录模型名或本机模型目录；HDV_ASR_MODEL 可固定本机目录')
a = ap.parse_args()
P = Path(a.project).resolve()
cfg = json.loads((P / 'design/config.json').read_text(encoding='utf-8'))
_ts_raw = json.loads((P / cfg['volc_json']).read_text(encoding='utf-8'))
# generate_candidate.py 把火山 query 响应存在 provider_query.data 下；旧格式顶层 data 也兼容
_ts_data = _ts_raw.get('data') or _ts_raw.get('provider_query', {}).get('data') or {}
ts = _ts_data['sentences']
narr = (P / cfg['narration']).read_text(encoding='utf-8')
strip = lambda s: re.sub(r'[^一-鿿0-9A-Za-z]', '', s)
PUNCT = '，。！？；：、,.!?;:"“”…'

with wave.open(str(P / cfg['voice_wav']), 'rb') as w:
    sr, n = w.getframerate(), w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype='<i2').astype(np.float64) / 32768
    if w.getnchannels() > 1: x = x.reshape(-1, w.getnchannels()).mean(1)

issues, rows = [], []
# ---- 句、字 ----
sents = []
for s in ts:
    chars = []
    for wd in s['words']:
        t = strip(wd['word'])
        for k, ch in enumerate(t):
            m = len(t)
            chars.append((ch, wd['startTime'] + (wd['endTime'] - wd['startTime']) * k / m, wd['startTime'] + (wd['endTime'] - wd['startTime']) * (k + 1) / m, wd['word'][-1] in PUNCT and k == m - 1))
    sents.append({'text': strip(s['text']), 'start': s['startTime'], 'end': s['endTime'], 'chars': chars})
rate = lambda s: len(s['chars']) / max(1e-6, s['end'] - s['start'])
med = statistics.median(rate(s) for s in sents if len(s['chars']) >= 6)

# ---- 1 语速 ----
for s in sents:
    r = rate(s)
    s['rate'] = round(r, 2)
    if len(s['chars']) >= 6 and (r > med * 1.3 or r < med * .7):
        issues.append({'level': 'red', 'kind': '语速', 'at': round(s['start'], 1), 'text': s['text'], 'detail': f'{r:.1f} 字/s，全片中位 {med:.1f}（{"偏快" if r > med else "偏慢"}）'})
    ch = s['chars']
    for k in range(len(ch) - 3):
        d = ch[k + 3][2] - ch[k][1]
        if d < .30:
            issues.append({'level': 'red', 'kind': '局部压缩', 'at': round(ch[k][1], 1), 'text': ''.join(c[0] for c in ch[k:k + 4]), 'detail': f'连续 4 字仅 {d:.2f} s（>{4 / d:.0f} 字/s）'})
            break
    for k in range(len(ch) - 1):
        gap = ch[k + 1][1] - ch[k][2]
        if gap > .9 and not ch[k][3]:
            issues.append({'level': 'yellow', 'kind': '异常停顿', 'at': round(ch[k][2], 1), 'text': ch[k][0] + '|' + ch[k + 1][0], 'detail': f'句内停顿 {gap:.2f} s'})

# ---- 2 响度 ----
def rms_db(t0, t1):
    seg = x[int(max(0, t0) * sr):int(t1 * sr)]
    return 20 * np.log10(max(np.sqrt(np.mean(seg ** 2)) if len(seg) else 0, 1e-6))
allc = [(c, rms_db(c[1], c[2])) for s in sents for c in s['chars']]
speech = [v for _, v in allc if v > -55]
base = float(np.median(speech)) if speech else -30
run = []
def flush():
    if len(run) >= 3:
        issues.append({'level': 'red', 'kind': '突然变小', 'at': round(run[0][0][1], 1), 'text': ''.join(c[0] for c, _ in run),
                       'detail': f'连续 {len(run)} 字低于说话中位 {base:.0f} dB 达 {base - float(np.mean([v for _, v in run])):.0f} dB'})
    run.clear()
for c, v in allc:
    if v < base - 8 and not c[3]: run.append((c, v))
    else: flush()
flush()
for s in sents:
    s['rms'] = round(float(np.median([rms_db(c[1], c[2]) for c in s['chars']])), 1)
    if len(s['chars']) >= 6 and s['rms'] < base - 3.2:
        lv = 'red' if s['rms'] < base - 6 else 'yellow'
        issues.append({'level': lv, 'kind': '整句偏小', 'at': round(s['start'], 1), 'text': s['text'], 'detail': f'本句中位 {s["rms"]} dB，比全片中位 {base:.0f} dB 低 {base - s["rms"]:.1f} dB（黄=请人耳复核，红=低 6 dB 以上）'})

# ---- 3/4 转录对照 ----
asr_text = ''
if not a.no_asr:
    from faster_whisper import WhisperModel
    model = WhisperModel(a.asr_model, device='cpu', compute_type='int8', local_files_only=Path(a.asr_model).is_dir())
    full = ''.join(sg.text for sg in model.transcribe(str(P / cfg['voice_wav']), language='zh', initial_prompt='以下是普通话口播，请用简体中文转写。')[0])
    asr_text = full
    for s in sents:
        seg = x[int(max(0, s['start'] - .25) * sr):int((s['end'] + .25) * sr)]
        tmp = P / 'qc/_voice_seg.wav'
        tmp.parent.mkdir(exist_ok=True)
        with wave.open(str(tmp), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.clip(seg, -1, 1) * 32767).astype('<i2').tobytes())
        t = strip(''.join(sg.text for sg in model.transcribe(str(tmp), language='zh', initial_prompt='以下是普通话口播，请用简体中文转写。')[0]))
        sim = difflib.SequenceMatcher(None, s['text'], t).ratio()
        s['asr'], s['sim'] = t, round(sim, 2)
        if sim < .8:
            issues.append({'level': 'red', 'kind': '转录对照', 'at': round(s['start'], 1), 'text': s['text'], 'detail': f'相似度 {sim:.2f}，转录成「{t}」（同音字误识、或转录成繁体字也会拉低相似度，请人耳复核这一句；开头第一句、整句相似度≥0.95 的“局部压缩”可视为自然快读）'})
    tmp.unlink(missing_ok=True)
    a_, b_ = strip(narr), strip(full)
    ops = [o for o in difflib.SequenceMatcher(None, a_, b_).get_opcodes() if o[0] != 'equal']
    miss = sum(i2 - i1 for o, i1, i2, j1, j2 in ops if o in ('delete', 'replace'))
    extra = sum(j2 - j1 for o, i1, i2, j1, j2 in ops if o in ('insert', 'replace'))
    rows.append(f'全文转录对照：原稿 {len(a_)} 字，转录 {len(b_)} 字，不一致处缺 {miss} / 多 {extra}（含同音字误识，仅供参考）')
    for o, i1, i2, j1, j2 in ops:
        if o == 'delete' and i2 - i1 >= 4 and a_[i1:i2] not in ''.join(s.get('asr', '') for s in sents):
            issues.append({'level': 'red', 'kind': '漏读', 'at': None, 'text': a_[i1:i2], 'detail': '整段在整条转录和逐句转录里都找不到'})

for i in issues:                                   # 速度类红灯：该句转录相似度 ≥0.95（听得清、没读错）→ 降为黄，请人耳确认是不是自然快读
    if i['level'] == 'red' and i['kind'] in ('语速', '局部压缩') and i['at'] is not None:
        for s_ in sents:
            if s_['start'] - .2 <= i['at'] <= s_['end'] and s_.get('sim', 0) >= .95:
                i['level'] = 'yellow'; i['detail'] += f'；该句转录相似度 {s_["sim"]}，听得清，多半是自然快读，请人耳确认'
reds = [i for i in issues if i['level'] == 'red']
(P / 'qc').mkdir(exist_ok=True)
(P / 'qc/voice-check.json').write_text(json.dumps({'median_rate': round(med, 2), 'base_rms_db': round(base, 1), 'issues': issues, 'sentences': [{k: v for k, v in s.items() if k != 'chars'} for s in sents]}, ensure_ascii=False, indent=1), encoding='utf-8')
md = ['# 配音自检', '', f'全片中位语速 {med:.1f} 字/s，说话中位响度 {base:.0f} dB；红色 {len(reds)} 项，黄色 {len(issues) - len(reds)} 项。', '']
md += [f"- {'🔴' if i['level'] == 'red' else '🟡'} {i['at']}s **{i['kind']}**「{i['text']}」{i['detail']}" for i in issues] or ['- 没有发现问题']
md += [''] + rows
(P / 'qc/voice-check.md').write_text('\n'.join(md), encoding='utf-8')
print('\n'.join(md))
sys.exit(1 if reds else 0)
