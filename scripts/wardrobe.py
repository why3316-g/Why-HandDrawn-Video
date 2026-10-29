"""Resolve and validate mandatory mother/teacher clothing-only references."""
from pathlib import Path
import json
import shutil

WARDROBE_DIR = Path('assets/characters/wardrobe-reference-v01')
MOTHER_FILES = {
    'mother-qipao-clothing-v01.png',
    'mother-qipao-clothing-v02.png',
    'mother-dress-clothing-v01.png',
}
TEACHER_FILES = {
    'teacher-male-clothing-v01.png',
    'teacher-female-clothing-v01.png',
}
ALL_FILES = MOTHER_FILES | TEACHER_FILES
SKILL_ROOT = Path(__file__).resolve().parents[1]


def pack_available(skill_root=None):
    """妈妈/班主任衣着参考属于可选的“家庭教育赛道扩展包”；公开版不带它，此时整套服饰强制规则不生效。"""
    root = Path(skill_root) if skill_root else SKILL_ROOT
    return all((root / WARDROBE_DIR / name).is_file() for name in ALL_FILES)


def copy_wardrobe_assets(skill_root, project_root):
    """Copy the approved reference set into the project-local relative path."""
    if not pack_available(skill_root):
        return None
    source = Path(skill_root) / WARDROBE_DIR
    target = Path(project_root) / WARDROBE_DIR
    missing = sorted(name for name in ALL_FILES if not (source / name).is_file())
    if missing:
        raise FileNotFoundError('Skill 服饰参考缺失：' + ', '.join(missing))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    return target


def wardrobe_role(cast_entry):
    if not pack_available():
        return None
    explicit = str(cast_entry.get('wardrobe_role', '')).strip().lower()
    aliases = {
        'mother': 'mother', 'mom': 'mother', '妈妈': 'mother', '母亲': 'mother',
        'teacher': 'teacher', '班主任': 'teacher', '老师': 'teacher', '教师': 'teacher',
    }
    haystack = ' '.join(str(cast_entry.get(k, '')) for k in ('name', 'identity')).lower()
    inferred = None
    if any(token in haystack for token in ('妈妈', '母亲', 'mother', 'mom')):
        inferred = 'mother'
    elif any(token in haystack for token in ('班主任', '老师', '教师', 'teacher')):
        inferred = 'teacher'
    if explicit in ('none', 'other', 'child'):
        if inferred:
            raise ValueError(f'{cast_entry.get("name", "角色")}: 描述识别为 {inferred}，不能将 wardrobe_role 设为 {explicit!r}')
        return None
    if explicit:
        if explicit not in aliases:
            raise ValueError(f'未知 wardrobe_role: {explicit!r}；只允许 mother/teacher/none')
        declared = aliases[explicit]
        if inferred and inferred != declared:
            raise ValueError(f'{cast_entry.get("name", "角色")}: wardrobe_role 与身份描述冲突')
        return declared
    return inferred


def cast_keys_for_shot(shot, cast):
    keys = []

    def add(value):
        if isinstance(value, str):
            key = value if value in cast else next((k for k, c in cast.items() if str(c.get('name', '')).strip() == value.strip()), None)
            if key and key not in keys:
                keys.append(key)
            elif not key and value.strip():
                raise ValueError(f'镜头引用了 cast key/角色名 {value!r}，但 design/cast.json 中不存在')
        elif isinstance(value, list):
            for item in value:
                add(item)

    add(shot.get('cast'))
    add(shot.get('cast_ids'))
    for role in shot.get('roles', []):
        key = role.get('cast_id') or role.get('cast')
        if not key:
            role_name = str(role.get('name', '')).strip()
            key = next((k for k, c in cast.items() if str(c.get('name', '')).strip() == role_name), None)
            if not key and any(token in role_name.lower() for token in ('妈妈', '母亲', 'mother', 'mom', '班主任', '老师', '教师', 'teacher')):
                raise ValueError(f"角色 {role_name!r} 必须在 roles[] 中填写 cast_id，才能绑定服饰参考")
        add(key)
    return keys


def _as_paths(value, label):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not value or not all(isinstance(x, str) for x in value):
        raise ValueError(f'{label} 必须是非空路径数组')
    return value


def _teacher_gender(cast_entry):
    gender = str(cast_entry.get('gender', '')).strip().lower()
    if gender in ('male', 'man', '男', '男性', '男教师'):
        return 'male'
    if gender in ('female', 'woman', '女', '女性', '女教师'):
        return 'female'
    identity = str(cast_entry.get('identity', '')).lower()
    name = str(cast_entry.get('name', '')).lower()
    text = identity + ' ' + name
    if any(token in text for token in ('男教师', '男老师', 'male teacher', 'man teacher')):
        return 'male'
    if any(token in text for token in ('女教师', '女老师', 'female teacher', 'woman teacher')):
        return 'female'
    return None


def resolve_wardrobe_references(shot, cast, project_root):
    """Return {cast_key: [project-relative paths]} or fail closed for required roles."""
    project_root = Path(project_root).resolve()
    per_role = shot.get('wardrobe_references', {}) or {}
    if not isinstance(per_role, dict):
        raise ValueError('wardrobe_references 必须是按 cast key 映射路径数组的对象')
    active = cast_keys_for_shot(shot, cast)
    result = {}
    for key in active:
        entry = cast[key]
        kind = wardrobe_role(entry)
        name = str(entry.get('name', key))
        refs = per_role.get(key, per_role.get(name))
        if refs is None and shot.get('wardrobe_reference_images') is not None and len(active) == 1:
            refs = shot['wardrobe_reference_images']
        if refs is None and kind == 'teacher':
            refs = entry.get('wardrobe_reference_images')
            if refs is None:
                gender = _teacher_gender(entry)
                if gender is None:
                    raise ValueError(f'{name}: 老师角色请填写 gender 或 wardrobe_reference_images')
                filename = f'teacher-{gender}-clothing-v01.png'
                refs = [(WARDROBE_DIR / filename).as_posix()]
        if refs is None and kind == 'mother':
            raise ValueError(f'{name}: 妈妈必须在本镜头 wardrobe_references 中逐镜选择一张衣着图')
        if refs is None:
            refs = entry.get('wardrobe_reference_images')
        if refs is None:
            continue
        refs = _as_paths(refs, f'{name} 的服饰参考')
        allowed = MOTHER_FILES if kind == 'mother' else TEACHER_FILES if kind == 'teacher' else ALL_FILES
        normalized = []
        for raw in refs:
            rel = Path(raw)
            if rel.is_absolute() or '..' in rel.parts:
                raise ValueError(f'{name}: 服饰参考必须使用项目内相对路径：{raw}')
            rel_posix = rel.as_posix()
            if rel.parent.as_posix() != WARDROBE_DIR.as_posix() or rel.name not in allowed:
                raise ValueError(f'{name}: 服饰参考类别/路径不匹配：{raw}')
            resolved = (project_root / rel).resolve()
            if not resolved.is_relative_to(project_root) or not resolved.is_file():
                raise ValueError(f'{name}: 服饰参考文件不存在或越界：{raw}')
            normalized.append(rel_posix)
        if kind == 'teacher':
            gender = _teacher_gender(entry)
            if gender and any(Path(p).name not in (f'teacher-{gender}-clothing-v01.png',) for p in normalized):
                raise ValueError(f'{name}: 教师服饰参考必须与性别匹配（{gender}）')
        result[key] = normalized
    return result


def wardrobe_prompt_instructions(wardrobe_map, cast):
    if not wardrobe_map:
        return ''
    rows = []
    for key, paths in wardrobe_map.items():
        name = cast.get(key, {}).get('name', key)
        rows.append(f"{name}: {', '.join(paths)}")
    return (
        'MANDATORY CLOTHING-ONLY IMAGE INPUTS are attached for these on-screen characters: '
        + '; '.join(rows)
        + '. Copy only garment cut, seams and silhouette. Do NOT copy any reference person identity, face, hair, expression, shoes, pose, body shape, glasses or props. '
    )


def logged_attachments(project_root, image_name):
    """Return the latest recorded actual image inputs for an output name, or None."""
    path = Path(project_root) / 'qc/imagegen-run.json'
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    found = None
    for run in data.get('runs', []):
        for record in run.get('records', []):
            if record.get('name') == image_name:
                found = record
    if found is None or 'attached_ref' not in found:
        return None
    return [str(x).replace(chr(92), '/') for x in found['attached_ref']]


def validate_logged_attachments(project_root, image_name, required_paths):
    actual = logged_attachments(project_root, image_name)
    if actual is None:
        raise ValueError(f'{image_name}: 缺少实际生图附图记录；Codex 内置生图须填写 imagegen-run.json 的 attached_ref')
    missing = {str(x).replace(chr(92), '/') for x in required_paths} - set(actual)
    if missing:
        raise ValueError(f'{image_name}: 妈妈/班主任服饰参考未实际附加：{sorted(missing)}')
    return actual
