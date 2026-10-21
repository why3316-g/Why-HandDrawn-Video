"""新建一个 Why-HandDrawn-Video 项目：目录骨架 + 复制花叔引擎并打补丁 + 渲染语法 + 项目内库 + 固定素材。
用法：python <skill>/scripts/new_project.py <英文短名> [--workspace 工作区根] [--date 20261010]
结果：<工作区>/projects/<日期>-<短名>-v01/ ，里面自包含（design/hdv 是项目内库，之后不再依赖 Skill 目录）。"""
import argparse, datetime, json, re, shutil, sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import find_huashu, find_workspace, companion_references, brand_logo
import engine_fixes
from wardrobe import copy_wardrobe_assets

SKILL = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument('name')
ap.add_argument('--workspace', default=None)
ap.add_argument('--date', default=datetime.date.today().strftime('%Y%m%d'))
a = ap.parse_args()
if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', a.name):
    sys.exit('短名只用英文小写字母、数字和中划线，例如 xiaoyu-return。')
if not re.fullmatch(r'\d{8}', a.date):
    sys.exit('日期格式必须为 YYYYMMDD。')
datetime.datetime.strptime(a.date, '%Y%m%d')
ws = Path(a.workspace).resolve() if a.workspace else (find_workspace('.') or Path.cwd())
hs = find_huashu()
if not hs:
    sys.exit('本 Skill 内嵌引擎缺失，请重新解压完整 Why-HandDrawn-Video 包；不需要另装花叔。')
P = ws / 'projects' / f'{a.date}-{a.name}-v01'
if P.exists():
    sys.exit(f'已存在，不覆盖：{P}')
# 空工作区先建立规则；已有规则原样保留，不覆盖用户约定。
ws.mkdir(parents=True, exist_ok=True)
agents, claude = ws / 'AGENTS.md', ws / 'CLAUDE.md'
if not agents.exists() and not claude.exists():
    rules = (SKILL / 'template/WORKSPACE_RULES.md').read_bytes()
    agents.write_bytes(rules); claude.write_bytes(rules)
elif agents.exists() and not claude.exists():
    claude.write_bytes(agents.read_bytes())
elif claude.exists() and not agents.exists():
    agents.write_bytes(claude.read_bytes())
elif agents.read_bytes() != claude.read_bytes():
    sys.exit('工作区 AGENTS.md 与 CLAUDE.md 不一致，请先核对现有规则；脚本不会覆盖。')
ignore = ws / '.gitignore'
old = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
needed = [p for p in ('.private/', '.env', '.env.*', '!.env.example', 'projects/', 'outputs/',
                      'node_modules/', '.venv/', '__pycache__/', '*.pyc') if p not in old.splitlines()]
if needed:
    ignore.write_text(old.rstrip() + '\n' + '\n'.join(needed) + '\n', encoding='utf-8')
marker = ws / '.hdv-workspace.json'
if not marker.exists():
    marker.write_text(json.dumps({'skill': 'Why-HandDrawn-Video', 'schema': 1}), encoding='utf-8')
for d in ('brief', 'design/prompts', 'assets/images', 'assets/audio', 'assets/references/companion', 'renders', 'qc'):
    (P / d).mkdir(parents=True, exist_ok=True)
shutil.copytree(hs / 'scripts/engine', P / 'engine', ignore=shutil.ignore_patterns('__pycache__'))
print('render.py 补丁：', engine_fixes.patch_render(P / 'engine/render.py'))
(P / 'engine/clips').mkdir(exist_ok=True)
shutil.copy(SKILL / 'template/engine_overrides/clips/hand_drawn_marker.js', P / 'engine/clips/hand_drawn_marker.js')
shutil.copytree(SKILL / 'scripts/hdv', P / 'design/hdv', ignore=shutil.ignore_patterns('__pycache__'))
for f in ('config.json', 'film.py', 'shots.json', 'cast.json', 'breaks.json'):
    shutil.copy(SKILL / 'template/design' / f, P / 'design' / f)
for f in ('BRIEF.md', 'narration.txt', 'title.txt'):
    shutil.copy(SKILL / 'template/brief' / f, P / 'brief' / f)
shutil.copy(SKILL / 'template/STATUS.md', P / 'STATUS.md')
for f in ('marker-hand-v02.png', 'marker-hand-meta-v02.json', 'style-ref-C.png'):
    shutil.copy(SKILL / 'assets' / f, P / 'assets/images' / f)
wardrobe_dir = copy_wardrobe_assets(SKILL, P)
if wardrobe_dir:
    print(f'已复制妈妈与班主任服饰参考到项目：{wardrobe_dir}')
comp_refs = companion_references(ws)
if comp_refs.is_dir():
    shutil.copytree(comp_refs, P / 'assets/references/companion', dirs_exist_ok=True)
    logo = brand_logo(ws)
    if logo.is_file():
        shutil.copy(logo, P / 'assets/references/companion-logo-reference-v01.png')
        print('已复制陪伴师5张场景参考图及品牌 Logo 参考。')
    else:
        print('已复制陪伴师5张场景参考图；缺少品牌 Logo 原图，陪伴师生图前请补齐。')
else:
    print('未安装品牌扩展包（陪伴师参考图与 Logo，可选）；使用通用人物规范即可。')
engine_fixes.make_qa(hs / 'scripts/qa.py', P / 'qc/huashu_qa.py')
(P / 'design/_env.json').write_text(json.dumps({'embedded_source': 'upstream/huashu-art-motion', 'skill': str(SKILL), 'workspace': str(ws)}, ensure_ascii=False, indent=1), encoding='utf-8')
print(f'\n项目已建好：{P}\n下一步（见 references/PIPELINE_SOP.md）：\n 1. 填 brief/BRIEF.md、brief/narration.txt、brief/title.txt（原稿逐字锁定）\n 2. 生成配音 → assets/audio/，更新 design/config.json\n 3. 写 design/cast.json（妈妈/班主任标 wardrobe_role）和 design/shots.json（每镜选择 wardrobe_references），再运行 gen_sprites.py')
