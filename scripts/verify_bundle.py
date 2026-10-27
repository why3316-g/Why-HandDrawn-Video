"""校验单包文件及未改动的上游快照；不搜索个人 Skill 目录。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
IGNORE = {'__pycache__', '.pytest_cache', '.git', '.venv', 'node_modules', '.cache'}
ENGINE_FILES = {
    'render.py', 'clip.html', 'clip.js', 'lib/fonts.js', 'lib/util.js', 'lib/paint.js',
    'lib/kit.js', 'lib/motion.js', 'lib/diagram.js',
    'lib/fonts/LXGWWenKai-500.woff', 'lib/fonts/NotoSansSC-500.woff',
    'lib/fonts/LICENSES.md', 'lib/fonts/OFL.txt',
}
WARDROBE_FILES = {
    'assets/characters/wardrobe-reference-v01/README.md',
    'assets/characters/wardrobe-reference-v01/mother-dress-clothing-v01.png',
    'assets/characters/wardrobe-reference-v01/mother-qipao-clothing-v01.png',
    'assets/characters/wardrobe-reference-v01/mother-qipao-clothing-v02.png',
    'assets/characters/wardrobe-reference-v01/teacher-female-clothing-v01.png',
    'assets/characters/wardrobe-reference-v01/teacher-male-clothing-v01.png',
}


def bundle_files(root):
    for path in sorted(Path(root).rglob('*')):
        rel = path.relative_to(root)
        if any(part in IGNORE for part in rel.parts) or path.suffix == '.pyc':
            continue
        if path.is_file() and rel.as_posix() != 'BUNDLE_MANIFEST.json':
            yield rel.as_posix(), path


def hashes(root):
    return {rel: hashlib.sha256(path.read_bytes()).hexdigest() for rel, path in bundle_files(root)}


def verify(root=ROOT):
    root = Path(root).resolve()
    errors = []
    mf = root / 'BUNDLE_MANIFEST.json'
    if not mf.is_file():
        return {'pass': False, 'checked': 0, 'errors': ['缺少 BUNDLE_MANIFEST.json']}
    manifest = json.loads(mf.read_text(encoding='utf-8'))
    expected = manifest['files']
    actual = hashes(root)
    for name in ('references/RING_STYLE.md', 'scripts/hdv/ring_style.py',
                 'assets/ring-styles/ring-guides.json', 'assets/ring-styles/ring-02.svg', 'assets/ring-styles/ring-03.svg'):
        if name not in actual:
            errors.append('必要圈画资源缺失：' + name)
    if (root / 'assets/ring-styles/ring-01.svg').exists():
        errors.append('已淘汰的 01 圈画不得进入素材包')

    required = ('SKILL.md', 'scripts/new_project.py', 'scripts/render_film.py',
                'scripts/check_visual_manifest.py', 'scripts/audio/generate_candidate.py',
                'upstream/SOURCES.json', 'references/ENGINE_GUIDE.md',
                'upstream/huashu-art-motion/scripts/engine/render.py',
                'upstream/huashu-art-motion/scripts/qa.py', 'references/COVER_ART_DIRECTION.md',
                'upstream/openmontage-audio/tools/audio/doubao_tts.py',
                'references/workspace/AUDIO_STANDARD.md', 'references/workspace/CHARACTER_VISUAL_STANDARD.md',
                'assets/fonts/NotoSansSC-VF.ttf')
    if manifest.get('profile') != 'public':
        required = required + tuple(sorted(WARDROBE_FILES))
    for name in required:
        if name not in actual:
            errors.append('必要资源缺失：' + name)
    wardrobe_dir = root / 'assets/characters/wardrobe-reference-v01'
    if wardrobe_dir.is_dir():
        for path in wardrobe_dir.iterdir():
            if path.is_file() and path.suffix.lower() == '.png' and path.name not in {Path(x).name for x in WARDROBE_FILES}:
                errors.append('未登记的服饰参考文件：' + path.name)
    entries = sorted(p.relative_to(root).as_posix() for p in root.rglob('SKILL.md'))
    if entries != ['SKILL.md']:
        errors.append('只能有根 SKILL.md 一个可发现入口')
    prefix = 'upstream/huashu-art-motion/scripts/engine/'
    runtime = {name[len(prefix):] for name in actual if name.startswith(prefix)}
    if runtime != ENGINE_FILES:
        errors.append('手绘引擎依赖不完整或混入多余模块：' + str(sorted(runtime ^ ENGINE_FILES)))
    source_allow = {'upstream/huashu-art-motion/LICENSE', 'upstream/huashu-art-motion/scripts/qa.py',
                    'upstream/canvas-design/LICENSE.txt', 'upstream/SOURCES.json',
                    'upstream/openmontage-audio/voice-profile.json',
                    'upstream/openmontage-audio/tools/__init__.py',
                    'upstream/openmontage-audio/tools/base_tool.py',
                    'upstream/openmontage-audio/tools/audio/__init__.py',
                    'upstream/openmontage-audio/tools/audio/doubao_tts.py',
                    'upstream/openmontage-audio/tools/audio/doubao_voice_catalog.py'} | {prefix + name for name in ENGINE_FILES}
    for name in actual:
        if name.startswith('upstream/') and name not in source_allow:
            errors.append('不属于当前工作流的上游文件：' + name)
    for name, sha in expected.items():
        if name not in actual:
            errors.append('文件缺失：' + name)
        elif actual[name] != sha:
            errors.append('文件已变更：' + name)
    for extra in actual.keys() - expected.keys():
        errors.append('清单外文件：' + extra)
    sf = root / 'upstream/SOURCES.json'
    if sf.is_file():
        for source in json.loads(sf.read_text(encoding='utf-8'))['sources']:
            for name, sha in source['files'].items():
                full = f"upstream/{source['name']}/{name}"
                if actual.get(full) != sha:
                    errors.append('来源快照不符：' + full)
            for guidance in source.get('derived_guidance', []):
                if actual.get(guidance['path']) != guidance['sha256']:
                    errors.append('技术指导与来源记录不符：' + guidance['path'])
    for rel in actual:
        parts = Path(rel).parts
        if '.private' in parts or any(p == '.env' or p.lower().endswith('.env') or (p.startswith('.env.') and p != '.env.example') for p in parts):
            errors.append('禁止携带私人配置：' + rel)
        if (root / rel).is_symlink():
            errors.append('禁止外部软链接：' + rel)
    return {'pass': not errors, 'checked': len(expected), 'profile': manifest.get('profile'), 'errors': errors}


def write_manifest(root=ROOT, profile='migration'):
    root = Path(root)
    data = {'schema': 2, 'skill': 'Why-HandDrawn-Video', 'edition': 'lean', 'profile': profile,
            'snapshot_date': '2026-10-14', 'files': hashes(root)}
    (root / 'BUNDLE_MANIFEST.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', default=str(ROOT))
    ap.add_argument('--write', action='store_true', help='维护者变更源码后重建清单，不用于掩盖缺失文件')
    args = ap.parse_args()
    if args.write:
        write_manifest(args.root)
    result = verify(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result['pass'] else 1)
