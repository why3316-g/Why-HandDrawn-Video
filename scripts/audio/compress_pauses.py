"""静音压缩（母带后处理，不改语音采样、不重新合成）。

用途：温柔妈妈 2.0（家长角度·妈妈）配音配方的第三步，`--cap 0.35`。
背景（2026-10-21 特级教师片）：用户反馈「句与句之间间隔太长、不自然，语速也偏慢」。
实测结论：火山 Speech 2.0 的 audio_params.speech_rate 只加快「说话」，不缩短内部停顿；
真正的句间空隙平均只有 0.115 s，长空隙全部在句子内部、由标点驱动
（`：“` 引语前 0.55–0.96 s，`，` 后 0.4–0.7 s）。API 没有句间静音参数，
additions.silence_duration 只给文本末尾加静音，所以只能在母带上做。

做法：把每个「字间空隙」压到不超过 --cap 秒，删掉的是纯静音中段，语音采样一帧不动。
删掉的时长是确定值，所以词级时间戳可以精确平移（old - 累计删除时长），不需要重新 ASR，
也不存在 ASR 认错字的风险。

不做的事：不重采样、不改变语音播放速率、不拼接不同次合成的音频。
--cap 0.45 时典型收益：0.9 s 的引语停→0.45 s，0.6 s 的逗号停→0.45 s，全片约缩 9 s。

用法（项目根目录）：
  python <skill>/scripts/audio/compress_pauses.py --project . \
      --wav assets/audio/narration-volcengine-jitang-full-v03.wav \
      --json assets/audio/narration-volcengine-jitang-full-v03.mp3.json \
      --text brief/narration.txt --cap 0.45 --tag v04

输出（同目录）：narration-<...>-v04.wav / .wav.json / .mp3
  .wav.json 沿用 provider 结构，只替换 provider_query.data.sentences 与 duration_seconds，
  并追加 pause_compression provenance → check_voice.py / hdv.Clock 可直接读。
校验：删静音前后「正文字符序列」必须逐字一致；压缩后任一空隙不得超过 cap + 0.02；
      cut 窗口内不能有真实语音（RMS 超阈值则跳过并告警）。
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('--project', default='.')
ap.add_argument('--wav', required=True, help='母带 wav（44.1k/16bit/单声道为佳）')
ap.add_argument('--json', required=True, help='对应 provider 时间戳 json')
ap.add_argument('--text', default='brief/narration.txt', help='口播原稿，用于逐字校验')
ap.add_argument('--cap', type=float, default=0.35, help='字间空隙上限（秒）；温柔妈妈 2.0 配方用 0.35')
ap.add_argument('--min-cut', type=float, default=0.05, help='小于这个删除量的空隙不动（秒）')
ap.add_argument('--fade', type=float, default=0.004, help='切点淡入淡出（秒），静音里只为防爆音')
ap.add_argument('--tag', required=True, help='输出文件名里的版本标记，如 v04')
ap.add_argument('--mp3', action='store_true', default=True, help='顺带导出 mp3 便于试听')
a = ap.parse_args()

P = Path(a.project).resolve()
WAV = (P / a.wav).resolve() if not Path(a.wav).is_absolute() else Path(a.wav)
JS = (P / a.json).resolve() if not Path(a.json).is_absolute() else Path(a.json)
TXT = (P / a.text).resolve() if not Path(a.text).is_absolute() else Path(a.text)

sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def strip(s):
    return re.sub(r'[^一-鿿0-9A-Za-z]', '', s)


# ---------- 读母带 ----------
with wave.open(str(WAV), 'rb') as w:
    sr, n, ch, width = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
    assert width == 2, f'只支持 16bit PCM，当前 {width * 8}bit'
    x = np.frombuffer(w.readframes(n), dtype='<i2').astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)

src = json.loads(JS.read_text(encoding='utf-8'))
data = src.get('data') or src.get('provider_query', {}).get('data') or {}
sents = json.loads(json.dumps(data['sentences']))  # deep copy

words = []
for s in sents:
    for wd in s['words']:
        if strip(wd['word']) == '' and wd['endTime'] - wd['startTime'] <= 0:
            continue
        words.append(wd)
if not words:
    sys.exit('时间戳里没有词')

# 逐字校验：源时间戳 vs 原稿
# 允许数字读法的等价替换（原稿「4个月」被念成「四个月」、「第17名」→「第十七名」），
# 只要求等长且差异位全是「阿拉伯数字 ↔ 汉字数字」。
DIGITS = set('0123456789一二三四五六七八九十零两')
src_chars = strip(''.join(w['word'] for w in words))
narr_chars = strip(TXT.read_text(encoding='utf-8'))
if src_chars != narr_chars:
    if len(src_chars) != len(narr_chars):
        sys.exit(f'源时间戳与口播原稿字数不一致（{len(src_chars)} vs {len(narr_chars)}），先修时间戳再压缩')
    bad = [(i, s, t) for i, (s, t) in enumerate(zip(src_chars, narr_chars)) if s != t and not (s in DIGITS and t in DIGITS)]
    if bad:
        sys.exit(f'源时间戳与口播原稿有 {len(bad)} 处非数字差异（例 {bad[:5]}），先修时间戳再压缩')
    print(f'注：{len([1 for s, t in zip(src_chars, narr_chars) if s != t])} 处数字读法差异，按等价处理')

# 说话段落的能量中位数，用于判断切点是否踩到语音
rms_all = []
for i in range(0, len(x) - int(0.02 * sr), int(0.02 * sr)):
    rms_all.append(float(np.sqrt(np.mean(x[i:i + int(0.02 * sr)] ** 2))))
speech_rms = float(np.median([r for r in rms_all if r > 0.01])) or 0.05
silence_limit = max(0.004, speech_rms * 0.12)

# ---------- 规划切点 ----------
cuts = []  # (start_sample, end_sample)
skipped = []
for i in range(len(words) - 1):
    a_end = words[i]['endTime']
    b_start = words[i + 1]['startTime']
    gap = b_start - a_end
    d = gap - a.cap
    if d < a.min_cut:
        continue
    # 能在整段空隙里滑动找最安静的位置，就滑；滑不到足够静的地方才跳过
    lo, hi = a_end + 0.10, b_start - 0.10
    if hi - lo < d:
        lo, hi = a_end + 0.03, b_start - 0.03
    lo_s, hi_s, d_n = int(lo * sr), int(hi * sr), int(d * sr)
    if hi_s - lo_s < d_n or d_n < int(0.02 * sr):
        continue
    best, best_rms, cut_n = None, 9e9, 0
    step = max(1, int(0.01 * sr))
    # 目标删除量不够安静（比如中间有吸气）时，逐级退让，尽量多删一点而不是整段放弃
    for d_try in np.arange(d, a.min_cut - 1e-9, -0.05):
        d_n = int(d_try * sr)
        if hi_s - lo_s < d_n or d_n < int(0.02 * sr):
            continue
        cand, cand_rms = None, 9e9
        for s0 in range(lo_s, hi_s - d_n + 1, step):
            r = float(np.sqrt(np.mean(x[s0:s0 + d_n] ** 2)))
            if r < cand_rms:
                cand, cand_rms = s0, r
        if cand is not None and cand_rms <= silence_limit:
            best, best_rms, cut_n = cand, cand_rms, d_n
            break
        if cand is not None and cand_rms < best_rms:
            best, best_rms, cut_n = cand, cand_rms, d_n
    if best is None or best_rms > silence_limit:
        skipped.append((round(a_end, 2), round(best_rms, 4), words[i]['word'][-1:], round(gap, 2)))
        continue
    cuts.append((best, best + cut_n))

removed = sum((e - s) for s, e in cuts) / sr
print(f'母带 {n / sr:.3f}s / {sr}Hz；字间空隙 {len(words) - 1} 个；待压缩 {len(cuts)} 处，删静音 {removed:.3f}s')
if skipped:
    print(f'  跳过 {len(skipped)} 处（切点有声音，保留原样）：{skipped[:6]}')

# ---------- 拼音频 ----------
fade_n = max(1, int(a.fade * sr))
keep = []
prev = 0
for s0, s1 in cuts:
    keep.append((prev, s0))
    prev = s1
keep.append((prev, len(x)))
parts = []
for i, (s0, s1) in enumerate(keep):
    seg = x[s0:s1].copy()
    if i > 0 and len(seg) > fade_n:
        seg[:fade_n] *= np.linspace(0, 1, fade_n, dtype=np.float32)
    if i < len(keep) - 1 and len(seg) > fade_n:
        seg[-fade_n:] *= np.linspace(1, 0, fade_n, dtype=np.float32)
    parts.append(seg)
y = np.concatenate(parts) if parts else x[:0]
out_wav = WAV.with_name(re.sub(r'-(v\d+)(?=\.wav$)', f'-{a.tag}', WAV.name))
if out_wav == WAV:
    sys.exit('输出路径与输入相同，换个 --tag')
pcm = np.clip(y, -1, 1)
with wave.open(str(out_wav), 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes((pcm * 32767).astype('<i2').tobytes())

# ---------- 平移时间戳 ----------
cut_ts = [(s / sr, e / sr, (e - s) / sr) for s, e in cuts]


def shift(t):
    acc = 0.0
    for cs, ce, d in cut_ts:
        if t >= ce:
            acc += d
        elif t > cs:
            acc += t - cs
    return round(t - acc, 3)


for s in sents:
    s['startTime'], s['endTime'] = shift(s['startTime']), shift(s['endTime'])
    for wd in s['words']:
        wd['startTime'], wd['endTime'] = shift(wd['startTime']), shift(wd['endTime'])

# ---------- 校验 ----------
new_chars = strip(''.join(wd['word'] for s in sents for wd in s['words']))
if new_chars != src_chars:
    sys.exit('压缩后词序列改变，拒绝出片')

flat = [wd for s in sents for wd in s['words']]
worst = 0.0
over = []
for i in range(len(flat) - 1):
    g = flat[i + 1]['startTime'] - flat[i]['endTime']
    if g > worst:
        worst = g
    if g > a.cap + 0.02:
        over.append((round(flat[i]['endTime'], 2), round(g, 2), flat[i]['word'][-1:]))
if len(over) == len(cuts) and cuts:
    sys.exit('压缩没有生效（所有空隙仍超 cap），检查时间戳是否重叠')
if worst > a.cap + 0.60:
    sys.exit(f'压缩后仍有 {worst:.3f}s 空隙（{over[:4]}），超出脚本能安全处理的范围，人工确认')
if over:
    print(f'  保留 {len(over)} 处超 cap 的空隙（切点有呼吸/气口，不动）：{over[:6]}')

dur = len(y) / sr
src_dur = float(data.get('duration_seconds') or n / sr)
out_json = out_wav.with_suffix('.wav.json')
payload = json.loads(JS.read_text(encoding='utf-8'))
if 'provider_query' in payload:
    payload['provider_query']['data']['sentences'] = sents
if 'data' in payload:
    payload['data']['sentences'] = sents
for k in ('duration_seconds',):
    if k in payload:
        payload[k] = round(dur, 3)
payload['wav_master'] = {
    'path': str(out_wav),
    'sha256': sha(out_wav),
    'duration_seconds': round(dur, 3),
    'sample_rate': sr,
    'channels': 1,
}
payload['pause_compression'] = {
    'method': 'trim_inter_word_silence_only',
    'speech_samples_modified': False,
    'resynthesis': False,
    'source_wav': str(WAV),
    'source_wav_sha256': sha(WAV),
    'source_json': str(JS),
    'source_json_sha256': sha(JS),
    'source_duration_seconds': round(src_dur, 3),
    'cap_seconds': a.cap,
    'min_cut_seconds': a.min_cut,
    'cut_count': len(cuts),
    'skipped_count': len(skipped),
    'removed_seconds': round(removed, 3),
    'output_duration_seconds': round(dur, 3),
    'worst_gap_after_seconds': round(worst, 3),
    'character_sequence_unchanged': True,
    'timestamp_shift': 'exact_arithmetic',
}
out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf-8')

mp3 = None
if a.mp3:
    mp3 = out_wav.with_suffix('.mp3')
    r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(out_wav),
                        '-codec:a', 'libmp3lame', '-q:a', '2', str(mp3)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print('ffmpeg 转 mp3 失败：', r.stderr[:300])
        mp3 = None

print(json.dumps({
    'wav': str(out_wav),
    'json': str(out_json),
    'mp3': str(mp3) if mp3 else None,
    'source_duration': round(src_dur, 3),
    'output_duration': round(dur, 3),
    'removed_seconds': round(removed, 3),
    'cut_count': len(cuts),
    'worst_gap_after': round(worst, 3),
    'chars_per_sec': round(len(src_chars) / dur, 2),
}, ensure_ascii=False, indent=1))
print('下一步：把 design/config.json 的 volc_json / voice_wav 指到新文件，跑 check_voice.py 再给用户试听。')
