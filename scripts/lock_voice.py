"""声音锁定闸门（2026-10-21 新增）：用户试听并明确说通过后，记录用户原话与音频 SHA-256 到 qc/voice-lock.json。
背景：执行工具生成配音后没停下等试听，直接进了生图。规则写在文字里会被跳过，所以改成脚本强制：
新项目（design/config.json 有 voice_lock_required: true）没有锁定记录时，gen_sprites.py 与封面生图拒绝运行。
用法（项目根目录，只能在用户明确说"通过/锁定"之后运行）：
  python <skill>/scripts/lock_voice.py --audio assets/audio/narration-...-full-v01.mp3 --user-says "用户原话"
换成新版本音频（用户已明确同意重合成并通过新版）时加 --relock。"""
import argparse, hashlib, json, sys, time
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass

LOCK = 'qc/voice-lock.json'


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def voice_lock_errors(project):
    """返回错误列表；旧项目（config 没有 voice_lock_required）不检查。"""
    p = Path(project)
    cfg_file = p / 'design/config.json'
    if not cfg_file.is_file():
        return []
    cfg = json.loads(cfg_file.read_text(encoding='utf-8'))
    if not cfg.get('voice_lock_required'):
        return []
    lock_file = p / LOCK
    if not lock_file.is_file():
        return ['声音还没锁定：第 3 步发完试听消息后要结束本轮回复、等用户试听；用户明确说通过后运行 lock_voice.py 记录原话，才能生图']
    lock = json.loads(lock_file.read_text(encoding='utf-8'))
    audio = p / lock.get('audio', '')
    if not audio.is_file():
        return [f'锁定记录里的音频不存在：{lock.get("audio")}']
    if _sha(audio) != lock.get('audio_sha256'):
        return [f'音频 {lock.get("audio")} 与锁定时的 SHA-256 不一致（文件被改动过），须让用户重新试听确认']
    mp3 = str(cfg.get('voice_mp3', ''))
    if mp3 and not mp3.startswith('assets/audio/<') and Path(mp3).as_posix() != Path(lock['audio']).as_posix():
        return [f'design/config.json 的 voice_mp3（{mp3}）不是用户锁定的那份音频（{lock["audio"]}）']
    return []


def enforce_voice_locked(project):
    errors = voice_lock_errors(project)
    if errors:
        raise ValueError('；'.join(errors))


def main():
    ap = argparse.ArgumentParser(description='用户明确说通过后，记录声音锁定')
    ap.add_argument('--project', default='.')
    ap.add_argument('--audio', required=True, help='用户试听并通过的那份 mp3（项目内相对路径）')
    ap.add_argument('--user-says', required=True, help='用户在对话里说"通过/锁定"的原话，逐字照抄')
    ap.add_argument('--relock', action='store_true', help='用户已明确通过新版本音频时才加')
    a = ap.parse_args()
    P = Path(a.project).resolve()
    audio = (P / a.audio).resolve()
    if not audio.is_file():
        sys.exit(f'音频不存在：{a.audio}')
    quote = a.user_says.strip()
    if len(quote) < 2:
        sys.exit('--user-says 要逐字照抄用户说通过的原话；用户没说通过就不要运行本脚本')
    lock_file = P / LOCK
    if lock_file.is_file() and not a.relock:
        sys.exit(f'已有锁定记录 {LOCK}；用户明确通过了新版本音频时才加 --relock')
    rel = audio.relative_to(P).as_posix()
    rec = {'audio': rel, 'audio_sha256': _sha(audio), 'user_says': quote,
           'locked_at': time.strftime('%Y-%m-%d %H:%M:%S')}
    if lock_file.is_file():
        rec['previous'] = json.loads(lock_file.read_text(encoding='utf-8'))
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'声音已锁定：{rel}（SHA-256 {rec["audio_sha256"][:12]}…），记录 {LOCK}')


if __name__ == '__main__':
    main()
