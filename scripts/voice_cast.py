"""声音与主角性别一致：学生第一人称稿里，配音就是主角本人，男声=男学生，女声=女学生。

design/config.json 记录：voice（dayi 男声 / xiaohe 女声 / jitang 女声）、narrator_is_protagonist（学生第一人称为 true）、
protagonist_cast（cast.json 里主角的 key）。cast.json 里主角必须写 gender: male/female，且 identity 描述不能和性别冲突。
第三人称、家长或陪伴师口吻（narrator_is_protagonist 为 false）不受此约束。性别无法从稿子判断时按声音规则默认小何（女声），主角就画女生。"""
import re

VOICE_GENDER = {'yichen': 'male', 'dayi': 'male', 'xiaohe': 'female', 'jitang': 'female'}
_FEMALE_WORDS = re.compile(r'\b(girl|woman|female|she|her|daughter)\b', re.I)
_MALE_WORDS = re.compile(r'\b(boy|man|male|he|his|son)\b', re.I)


def _norm_gender(value):
    v = str(value or '').strip().lower()
    if v in ('male', 'man', 'boy', '男', '男性'): return 'male'
    if v in ('female', 'woman', 'girl', '女', '女性'): return 'female'
    return None


def check_voice_cast(config, cast):
    """返回错误列表；config 里没有 narrator_is_protagonist（旧项目）时不检查。"""
    if 'narrator_is_protagonist' not in config:
        return []
    if not config.get('narrator_is_protagonist'):
        return []
    voice = config.get('voice')
    if voice not in VOICE_GENDER:
        return [f'config.json 的 voice 必须是 {sorted(VOICE_GENDER)} 之一（当前 {voice!r}）']
    key = config.get('protagonist_cast')
    if key not in cast:
        return [f'config.json 的 protagonist_cast 必须是 cast.json 里的角色 key（当前 {key!r}）']
    want = VOICE_GENDER[voice]
    entry = cast[key]
    got = _norm_gender(entry.get('gender'))
    errors = []
    if got != want:
        errors.append(f'学生第一人称稿：声音 {voice} 是{"男" if want == "male" else "女"}声，主角 {key} 的 gender 必须是 {want}（当前 {entry.get("gender")!r}）')
    identity = str(entry.get('identity', ''))
    clash = (_FEMALE_WORDS if want == 'male' else _MALE_WORDS).search(identity)
    if clash:
        errors.append(f'主角 {key} 的 identity 里出现与{"男" if want == "male" else "女"}性主角冲突的词：{clash.group(0)}')
    return errors


def enforce(project):
    """读 design/config.json 与 cast.json；有错误则抛 ValueError（生图和清单前调用，避免白花生图额度）。"""
    import json
    from pathlib import Path
    p = Path(project)
    cfg_file, cast_file = p / 'design/config.json', p / 'design/cast.json'
    if not cfg_file.is_file() or not cast_file.is_file():
        return
    errors = check_voice_cast(json.loads(cfg_file.read_text(encoding='utf-8')), json.loads(cast_file.read_text(encoding='utf-8')))
    if errors:
        raise ValueError('声音与主角性别不一致：' + '；'.join(errors))
