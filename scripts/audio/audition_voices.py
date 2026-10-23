"""音色横向试听（不产生成片音轨）。

用途：用户对已批准音色不满意、要求在火山 2.0 音色表里找更合适的声音时，
用**同一段口播原文**给多个候选音色各合成一次，导出成短样音横向对比。
这一步只服务于「选音色」，不是成片音轨——成片仍必须全文一次 submit。

边界：
- 只用火山 Doubao Speech 2.0（`seed-tts-2.0`），凭证仍从工作区 `.private/volcengine.env` 读；
- 每个音色**一次提交整段试听文本**（不按句拆、不拼接、不注入静音），回执记录 task_id 与时长；
- 试听文本必须是原稿开头的连续段落（不改字、不许改写），默认取开头约 20 秒；
- 选定的音色要写进 AUDIO_STANDARD 的批准清单后，才能用 generate_candidate.py 做全文合成。

用法（项目根目录）：
  python <skill>/scripts/audio/audition_voices.py --project . --text-file audition.txt \
      --voices wenroumama,zhixingnv,qinqienv,cancan,kefunvsheng --speech-rate 14 --tag mom-search-01

输出：`assets/audio/audition/<tag>/<key>-<voice_id>.mp3` + 同名 `.json` 回执，终端打印对照表。
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / 'scripts'))
from common import find_workspace  # noqa: E402

# 2026-10-22 取自火山官方音色列表 https://www.volcengine.com/docs/6561/1257544
# （「豆包语音合成模型 2.0」表，均为 seed-tts-2.0 资源，中文，通用场景/视频配音）。
# 只收「成熟女性、能当 30–45 岁妈妈/老师」的候选；少女音、御姐音、奶奶音不入表。
FEMALE_ADULT = {
    # key                      voice_type                                    官方场景      定位
    'wenroumama':  ('zh_female_wenroumama_uranus_bigtts',      '通用场景', '温柔妈妈：名字最贴妈妈，声线偏柔'),
    'zhixingnv':   ('zh_female_zhixingnv_uranus_bigtts',       '通用场景', '知性女声：像老师/讲者，克制可信'),
    'qinqienv':    ('zh_female_qinqienv_uranus_bigtts',        '通用场景', '亲切女声：口语近人，豆包同款'),
    'cancan':      ('zh_female_cancan_uranus_bigtts',          '角色扮演', '知性灿灿：知性偏暖，叙述感强'),
    'kefunvsheng': ('zh_female_kefunvsheng_uranus_bigtts',     '客服场景', '暖阳女声：客服底子最不端着，稳'),
    'tiexinnvsheng': ('zh_female_tiexinnvsheng_uranus_bigtts', '通用场景', '贴心女声：体贴、耐力久听不累'),
    'liuchangnv':  ('zh_female_liuchangnv_uranus_bigtts',      '视频配音', '流畅女声：配音底子，断句利落'),
    'sophie':      ('zh_female_sophie_uranus_bigtts',          '通用场景', '魅力苏菲：成熟有质感，略带气声'),
    'vv':          ('zh_female_vv_uranus_bigtts',              '通用场景', 'Vivi 2.0：S2S 主打，多语种最强'),
}
# 明确排除（供复核用）：tianmeixiaoyuan/tianmeitaozi 等少女音、gaolengyujie 御姐、popo/heainainai 长辈、
# jitangnv（已否决）、xiaohe（偏年轻）、jiachunv/chanmeinv 等角色扮演音。

ap = argparse.ArgumentParser()
ap.add_argument('--project', default='.')
ap.add_argument('--text-file', required=True, help='试听文本（原稿开头的连续段落，相对项目根）')
ap.add_argument('--voices', required=True, help='逗号分隔的 key，取自 FEMALE_ADULT')
ap.add_argument('--speech-rate', type=int, default=14, help='与对照版一致的语速，默认 14（1.14 倍）')
ap.add_argument('--tag', required=True, help='本次试听的输出子目录名，如 mom-search-01')
ap.add_argument('--dry-run', action='store_true', help='只打印将要提交的内容，不调用接口')
a = ap.parse_args()

P = Path(a.project).resolve()
ws = find_workspace(P) or next(p.parent for p in P.parents if p.name == 'projects')
if ws is None:
    sys.exit('找不到工作区根目录')

txt_path = P / a.text_file if not Path(a.text_file).is_absolute() else Path(a.text_file)
text = txt_path.read_text(encoding='utf-8').strip()
if not text:
    sys.exit('试听文本为空')
spkn = text.replace('\n', '').replace(' ', '')      # 实际朗读字数（不含换行），用于字/s 统计
text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()

keys = [k.strip() for k in a.voices.split(',') if k.strip()]
unknown = [k for k in keys if k not in FEMALE_ADULT]
if unknown:
    sys.exit(f'未知候选 {unknown}；可选：{", ".join(FEMALE_ADULT)}')

outdir = P / 'assets/audio/audition' / a.tag
outdir.mkdir(parents=True, exist_ok=True)
(outdir / 'audition-text.txt').write_text(text + '\n', encoding='utf-8')

# 凭证（不打印值）
env_path = ws / '.private/volcengine.env'
env = {}
for line in env_path.read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    env[k.strip()] = v.strip().strip('"').strip("'")
import os  # noqa: E402
for k, v in env.items():
    os.environ.setdefault(k, v)
if not os.environ.get('DOUBAO_SPEECH_API_KEY'):
    sys.exit('缺少 DOUBAO_SPEECH_API_KEY（.private/volcengine.env）')

sys.path.insert(0, str(SKILL / 'upstream/openmontage-audio'))
from tools.audio.doubao_tts import DoubaoTTS  # noqa: E402

print(f'试听文本 {len(spkn)} 字（sha256 {text_hash[:12]}…）：{text[:34]}…')
print(f'候选 {len(keys)} 个，语速 {a.speech_rate}（{1 + a.speech_rate / 100:.2f} 倍），输出 {outdir}')
if a.dry_run:
    for k in keys:
        vid, scene, note = FEMALE_ADULT[k]
        print(f'  {k:14s} {vid:42s} {scene}  {note}')
    sys.exit(0)

def probe_duration(path):
    """实测音频时长。DoubaoTTS 返回的 duration_seconds 不是音频时长（实测偏短 30%+），一律以 ffprobe 为准。"""
    try:
        out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                              '-of', 'csv=p=0', str(path)], capture_output=True, text=True, check=True)
        return round(float(out.stdout.strip()), 3)
    except Exception:
        return None


rows = []
for k in keys:
    vid, scene, note = FEMALE_ADULT[k]
    target = outdir / f'{k}-{vid}.mp3'
    receipt_path = target.with_suffix('.mp3.json')
    if target.exists() and receipt_path.exists():
        r = json.loads(receipt_path.read_text(encoding='utf-8'))
        if r.get('input_text_sha256') == text_hash and r.get('speech_rate') == a.speech_rate:
            print(f'[reuse] {k} 已存在同文本同参数产物，跳过')
            rows.append((k, vid, note, probe_duration(target), r.get('task_id'), 'reused'))
            continue
    print(f'[submit] {k} → {vid}', flush=True)
    res = DoubaoTTS().execute({
        'text': text, 'voice_id': vid, 'resource_id': 'seed-tts-2.0',
        'speech_rate': a.speech_rate, 'format': 'mp3', 'sample_rate': 24000,
        'enable_timestamp': False, 'voice_validation': 'user_requested_audition',
        'output_path': str(target), 'timeout_seconds': 300, 'poll_interval_seconds': 2.0,
        'user_id': 'huashu-art-motion',
    })
    if not res.success:
        print(f'[fail] {k}: {str(res.error)[:200]}')
        rows.append((k, vid, note, None, None, f'failed: {str(res.error)[:80]}'))
        continue
    dur = probe_duration(target)
    task = (res.data or {}).get('task_id')
    data = {'provider': 'volcengine', 'purpose': 'voice_audition', 'voice_id': vid,
            'resource_id': 'seed-tts-2.0', 'speech_rate': a.speech_rate,
            'speed_multiplier': round(1 + a.speech_rate / 100, 3),
            'input_text_sha256': text_hash, 'text_characters': len(spkn),
            'task_id': task, 'duration_seconds': dur, 'output': str(target),
            'full_body': True, 'synthesis_segmentation': False,
            'note': 'audition sample only; final track must be one full-body submit'}
    receipt_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    rows.append((k, vid, note, dur, task, 'ok'))

print('\n| key | 音色 | 说明 | 时长 | 字/s |')
print('|---|---|---|---|---|')
for k, vid, note, dur, task, status in rows:
    rate = f'{len(spkn) / dur:.2f}' if dur else '-'
    print(f'| {k} | {vid} | {note} | {dur or "-"} | {rate} |')
print('\n下一步：把候选样音逐个试听；选中的音色先写进 AUDIO_STANDARD 的批准清单，再用 generate_candidate.py 做全文一次合成。')
