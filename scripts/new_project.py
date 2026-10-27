"""新建一个 Why-HandDrawn-Video 项目：目录骨架 + 复制花叔引擎并打补丁 + 渲染语法 + 项目内库 + 固定素材。
用法：python <skill>/scripts/new_project.py <英文短名> [--workspace 工作区根] [--date 20261010] [--mode portrait|landscape] [--hand 03]
结果：<工作区>/projects/<日期>-<短名>-v01/ ，里面自包含（design/hdv 是项目内库，之后不再依赖 Skill 目录）。
手与笔：竖屏与宽屏都从 assets/hands/hand-pool-v01/ 随机取一张装进 assets/images/，参数写入 hand-meta.json，
全片同一双，手臂统一归一到右下 45°；池缺失时竖屏退回 marker-hand-v02.png、宽屏退回 marker-hand-landscape-v01.png。"""
import argparse, datetime, json, re, shutil, sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import find_huashu, find_workspace, companion_references, brand_logo
import engine_fixes
from wardrobe import copy_wardrobe_assets
from hand_pool import pick as pick_hand, install as install_hand, record_use as record_hand_use
from hdv.layout import get_layout

SKILL = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument('name')
ap.add_argument('--workspace', default=None)
ap.add_argument('--mode', choices=('portrait', 'landscape'), default='portrait', help='portrait 竖屏（默认）；landscape 网站宽屏')
ap.add_argument('--content-type',choices=('general','institutional_promo'),default='general')
ap.add_argument('--hand', default=None, help='手部素材池内文件全名或前缀（如 03）；默认随机，一片一双手')
ap.add_argument('--date', default=datetime.date.today().strftime('%Y%m%d'))
a = ap.parse_args()
layout = get_layout(a.mode)
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
shutil.copytree(SKILL / 'assets/ring-styles', P / 'assets/images/ring-styles')
for f in ('config.json', 'film.py', 'shots.json', 'cast.json', 'breaks.json'):
    shutil.copy(SKILL / 'template/design' / f, P / 'design' / f)
for f in ('BRIEF.md', 'narration.txt', 'title.txt'):
    shutil.copy(SKILL / 'template/brief' / f, P / 'brief' / f)
# 只修改本次新项目的画幅；既有项目不迁移、不覆盖。
config_path = P / 'design/config.json'
config = json.loads(config_path.read_text(encoding='utf-8'))
config['mode'] = a.mode
config['content_type'] = a.content_type
if a.content_type == 'institutional_promo':
    config['voice'] = 'yichen'
    config['cover_style'] = 'institutional'
if a.mode == 'landscape':
    config['logic_plan'] = 'design/logic-plan.json'
    shutil.copy(SKILL / 'template/design/logic-plan.json', P / 'design/logic-plan.json')
    config['header_first'] = ['本片主题（锁稿后填写）', '本节要点（取自口播）']
    config['header_other'] = '本片主题'
# 手与笔：竖屏与宽屏同一套——随机取素材池一张，全片同一张，手臂归一到右下 45°（2026-10-26 用户定稿）。
hand_note = ''
entry = None
try:
    entry = pick_hand(SKILL, ws, a.hand)
except SystemExit as exc:
    print(f'手部素材池不可用，改用旧线稿手：{exc}')
if entry:
    hand_meta = install_hand(P, entry)
    config['hand'] = hand_meta['file']
    record_hand_use(ws, entry)
    if a.mode == 'landscape':
        config['hand_landscape'] = hand_meta['file']     # 老代码读这个字段，写同值保持兼容
        hand_note = (f"- 手与笔：{hand_meta['file']}（素材池随取，宽屏缩放 {hand_meta.get('scale_landscape')}，"
                     f"手臂 45°，全片同一双）\n")
    else:
        hand_note = f"- 手与笔：{hand_meta['file']}（素材池随取，笔尖 {hand_meta['tip']}，缩放 {hand_meta['scale']}，手臂 45°，全片同一双）\n"
elif a.mode == 'landscape':
    config['hand'] = 'marker-hand-landscape-v01.png'
    config['hand_landscape'] = 'marker-hand-landscape-v01.png'
    hand_note = '- 手与笔：marker-hand-landscape-v01.png（素材池缺失，退回已批准的宽屏短手）\n'
else:
    config['hand'] = 'marker-hand-v02.png'
    hand_note = '- 手与笔：marker-hand-v02.png（素材池缺失，退回旧线稿手）\n'
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
brief_path = P / 'brief/BRIEF.md'
brief = brief_path.read_text(encoding='utf-8').replace('1080×1920', f"{layout['width']}×{layout['height']}")
brief += f'\n- 模式：{a.mode}\n' + hand_note
if a.mode == 'landscape':
    brief = brief.replace('视频号竖屏；受众=厌学休学孩子的家长；目标=信任或种草；口吻=像人说话',
                          '客户网站宽屏；受众/内容目标/口吻据原文章与客户要求确认')
    brief += '- 文章转讲解：原文保存在 brief/；口播候选及原文对应表经用户确认后才锁定 narration.txt。版式与网站交付见 Skill references/LANDSCAPE_SPEC.md。\n'
brief_path.write_text(brief, encoding='utf-8')
shutil.copy(SKILL / 'template/STATUS.md', P / 'STATUS.md')
shutil.copy(SKILL / 'assets/style-ref-C.png', P / 'assets/images/style-ref-C.png')
if config['hand'] == 'marker-hand-v02.png':      # 素材池缺失时的退路，保留旧线稿手与其参数
    for f in ('marker-hand-v02.png', 'marker-hand-meta-v02.json'):
        shutil.copy(SKILL / 'assets' / f, P / 'assets/images' / f)
elif config['hand'] == 'marker-hand-landscape-v01.png':   # 宽屏退路
    shutil.copy(SKILL / 'assets/marker-hand-landscape-v01.png', P / 'assets/images/marker-hand-landscape-v01.png')
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
print(f'\n项目已建好：{P}\n下一步（见 references/PIPELINE_SOP.md）：\n 1. 填 brief/BRIEF.md、brief/narration.txt、brief/title.txt（原稿逐字锁定）\n 2. 生成配音 → assets/audio/，更新 design/config.json；发试听后停下等用户，用户明确通过后运行 lock_voice.py（不锁定不能生图）\n 3. 写 design/cast.json（妈妈/班主任标 wardrobe_role）和 design/shots.json（每镜选择 wardrobe_references），再运行 gen_sprites.py')
