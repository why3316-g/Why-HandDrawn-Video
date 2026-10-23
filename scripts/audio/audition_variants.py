"""同一音色的「表达变体」横评（语速 / 语音指令 / 音调 / 情绪），用于调参试听。

背景（2026-10-22 特级教师片）：温柔妈妈 2.0 年龄与声线合适，但停顿多、偏慢、不够焦虑。
火山文档确认，TTS 2.0 预设音色可调的表达项只有这些（`mute_cut_*` 对 2.0 音色明确不支持，
`emotion/emotion_scale` 仅部分音色支持，`use_tag_parser` 仅限声音复刻 2.0 表现力增强版）：

| 参数 | 位置 | 作用 | 2.0 音色可用 |
|---|---|---|---|
| speech_rate | audio_params | 语速 [-50,100]，100=2.0 倍 | 是 |
| loudness_rate | audio_params | 音量 [-50,100] | 是 |
| emotion / emotion_scale | audio_params | 固定情绪枚举 + 强度 1–5 | 部分音色，需实测 |
| context_texts | additions | 自然语言语音指令（情绪/语速/语气/停顿感） | 是（仅第一个值有效，不计费） |
| post_process.pitch | additions | 音调 [-12,12]，合成后处理 | 是 |
| silence_duration | additions | 仅在**文本末尾**补静音，管不到句间 | 是（对本用途无用） |
| mute_cut_threshold / mute_cut_remain_ms | additions | 服务端裁句首静音 | **2.0 音色不支持** |

句间停顿要真正变短，只能「语音指令 + 语速」影响生成，再用 compress_pauses.py 兜底压。

用法（项目根目录）：
  python <skill>/scripts/audio/audition_variants.py --project . \
      --text-file assets/audio/audition/head3.txt --voice zh_female_wenroumama_uranus_bigtts \
      --spec assets/audio/audition/variants-mom-02.json --tag mom-search-02

spec 是一个数组，每项：{"key","speech_rate","loudness_rate","pitch","emotion","emotion_scale","context_texts"}
输出：`assets/audio/audition/<tag>/<key>.mp3` + `.json`，终端打印实测时长、字/s、最长静音。
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
import numpy as np

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / 'scripts'))
from common import find_workspace  # noqa: E402
sys.path.insert(0, str(SKILL / 'upstream/openmontage-audio'))
from tools.audio.doubao_tts import DoubaoTTS  # noqa: E402


class DoubaoTTSWithDirectives(DoubaoTTS):
    """不改上游代码，只给请求体补上 2.0 音色可用的表达参数。"""

    def _submit_body(self, inputs, *, voice_id, request_id):
        body = super()._submit_body(inputs, voice_id=voice_id, request_id=request_id)
        rp = body['req_params']
        ap = rp['audio_params']
        add = json.loads(rp['additions'])
        if inputs.get('loudness_rate') is not None:
            ap['loudness_rate'] = int(inputs['loudness_rate'])
        if inputs.get('emotion'):
            ap['emotion'] = inputs['emotion']
            ap['emotion_scale'] = int(inputs.get('emotion_scale') or 4)
        if inputs.get('pitch') is not None:
            add['post_process'] = {'pitch': int(inputs['pitch'])}
        ct = inputs.get('context_texts')
        if ct:
            add['context_texts'] = [ct] if isinstance(ct, str) else list(ct)[:1]
        rp['additions'] = json.dumps(add, ensure_ascii=False)
        return body


def probe_all(path):
    try:
        out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                              '-of', 'csv=p=0', str(path)], capture_output=True, text=True, check=True)
        return round(float(out.stdout.strip()), 3)
    except Exception:
        return None


def pause_report(mp3, tmp):
    """最长静音与 ≥0.4 s 停顿数：判断「拖不拖」比听感更客观。"""
    wav = tmp / (mp3.stem + '.wav')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(mp3), '-ac', '1', '-ar', '16000', str(wav)],
                   check=True)
    with wave.open(str(wav), 'rb') as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.float32) / 32768
    fr, hop = int(0.03 * sr), int(0.01 * sr)
    n = (len(x) - fr) // hop + 1
    r = np.array([np.sqrt(np.mean(x[i * hop:i * hop + fr] ** 2)) for i in range(n)])
    sil = r < 0.006
    runs, i = [], 0
    while i < len(sil):
        if sil[i]:
            j = i
            while j < len(sil) and sil[j]:
                j += 1
            if i > 0 and j < len(sil):
                runs.append((j - i) * 0.01)
            i = j
        else:
            i += 1
    wav.unlink(missing_ok=True)
    return (round(max(runs), 2) if runs else 0.0), sum(1 for d in runs if d >= 0.4)


ap = argparse.ArgumentParser()
ap.add_argument('--project', default='.')
ap.add_argument('--text-file', required=True)
ap.add_argument('--voice', required=True)
ap.add_argument('--spec', required=True, help='变体 JSON 数组')
ap.add_argument('--tag', required=True)
ap.add_argument('--probe-emotion', default='', help='额外探测一个 emotion 枚举是否受支持（如 fearful）')
a = ap.parse_args()

P = Path(a.project).resolve()
ws = find_workspace(P) or next(p.parent for p in P.parents if p.name == 'projects')
text = (P / a.text_file).read_text(encoding='utf-8').strip()
spkn = text.replace('\n', '').replace(' ', '')
text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
variants = json.loads((P / a.spec).read_text(encoding='utf-8'))
outdir = P / 'assets/audio/audition' / a.tag
outdir.mkdir(parents=True, exist_ok=True)
tmp = outdir / '_tmp'
tmp.mkdir(exist_ok=True)

env_path = ws / '.private/volcengine.env'
for line in env_path.read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
if not os.environ.get('DOUBAO_SPEECH_API_KEY'):
    sys.exit('缺少 DOUBAO_SPEECH_API_KEY')

print(f'音色 {a.voice}；试听文本 {len(spkn)} 字（{text_hash[:12]}…）；变体 {len(variants)} 个')

# 可选：先探测 emotion 枚举是否被这个音色接受（用同样短文本，代价很小）
if a.probe_emotion:
    probe = outdir / f'_probe-emotion-{a.probe_emotion}.mp3'
    res = DoubaoTTSWithDirectives().execute({
        'text': text, 'voice_id': a.voice, 'resource_id': 'seed-tts-2.0',
        'speech_rate': 19, 'format': 'mp3', 'sample_rate': 24000, 'enable_timestamp': False,
        'emotion': a.probe_emotion, 'emotion_scale': 4,
        'voice_validation': 'param_probe', 'output_path': str(probe), 'allow_overwrite': True,
        'timeout_seconds': 300, 'poll_interval_seconds': 2.0, 'user_id': 'huashu-art-motion',
    })
    print(f'[probe] emotion={a.probe_emotion} → success={res.success}'
          + ('' if res.success else f'  错误：{str(res.error)[:220]}'))
    if res.success:
        print(f'        探测产物 {probe.name}，时长 {probe_all(probe)}s（未列入正式变体，仅证明参数被接受）')

rows = []
for v in variants:
    key = v['key']
    target = outdir / f'{key}.mp3'
    rec = target.with_suffix('.mp3.json')
    if target.exists() and rec.exists():
        r = json.loads(rec.read_text(encoding='utf-8'))
        if r.get('input_text_sha256') == text_hash:
            print(f'[reuse] {key}')
            rows.append((key, r.get('duration_seconds'), r.get('speech_rate') or (r.get('request_params') or {}).get('speech_rate'), r.get('context_texts') or (r.get('request_params') or {}).get('context_texts')))
            continue
    print(f'[submit] {key}', flush=True)
    res = None
    for attempt in range(3):
        res = DoubaoTTSWithDirectives().execute({
            'text': text, 'voice_id': a.voice, 'resource_id': 'seed-tts-2.0',
            'speech_rate': v.get('speech_rate', 19), 'format': 'mp3', 'sample_rate': 24000,
            'enable_timestamp': False, 'voice_validation': 'param_variant',
            'loudness_rate': v.get('loudness_rate'), 'pitch': v.get('pitch'),
            'emotion': v.get('emotion'), 'emotion_scale': v.get('emotion_scale'),
            'context_texts': v.get('context_texts'),
            'output_path': str(target), 'timeout_seconds': 300, 'poll_interval_seconds': 2.0,
            'user_id': 'huashu-art-motion', 'allow_overwrite': True,
        })
        if res.success:
            break
        err = str(res.error)
        # 只在网络层失败时重试；供应商明确拒绝参数时不重试，避免隐性重复计费
        transient = any(s in err for s in ('SSLError', 'Max retries exceeded', 'Connection', 'Timeout',
                                           'timed out', 'RemoteDisconnected', 'EOF occurred'))
        print(f'  attempt {attempt + 1} 失败（{"网络" if transient else "非网络"}）：{err[:150]}')
        if not transient or attempt == 2:
            break
        time.sleep(4 * (attempt + 1))
    if not res.success:
        print(f'[fail] {key}: {str(res.error)[:220]}')
        rows.append((key, None, v.get('speech_rate'), v.get('context_texts')))
        continue
    dur = probe_all(target)
    payload = {'provider': 'volcengine', 'purpose': 'expression_variant', 'voice_id': a.voice,
               'resource_id': 'seed-tts-2.0', 'input_text_sha256': text_hash,
               'text_characters': len(spkn), 'duration_seconds': dur, 'duration_source': 'ffprobe',
               'speech_rate': v.get('speech_rate'), 'context_texts': v.get('context_texts'),
               'output': str(target), 'request_params': v, 'full_body': True,
               'synthesis_segmentation': False}
    rec.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    rows.append((key, dur, v.get('speech_rate'), v.get('context_texts')))

print('\n| 变体 | 语速 | 指令 | 时长 | 字/s | 最长静音 | ≥0.4s停 |')
print('|---|---|---|---|---|---|---|')
for key, dur, rate, ctx in rows:
    if not dur:
        print(f'| {key} | {rate} | {ctx or "—"} | 失败 | - | - | - |')
        continue
    mp3 = outdir / f'{key}.mp3'
    mx, cnt = pause_report(mp3, tmp)
    ceil = (ctx[:26] + '…') if ctx and len(ctx) > 26 else (ctx or '—')
    print(f'| {key} | {rate} | {ceil} | {dur:.2f}s | {len(spkn) / dur:.2f} | {mx:.2f}s | {cnt} |')
tmp.rmdir()
print('\n下一步：试听后按中选变体的参数做全文一次合成（generate_candidate.py 需支持同参数）。')
