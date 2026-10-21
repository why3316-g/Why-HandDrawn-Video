"""由 design/shots.json 生成人物资产清单 design/performance-plan.json + brief/PERFORMANCE_TABLE.md，并运行 why-story-visuals 的检查器。
shots.json 里每个镜头必须由"实际看过图片的人/AI"写好 observation，并把 reviewed 设为 true；脚本不替你签验收。
旧项目的 fixed_assets 结构仅为兼容历史镜头；新陪伴师镜头须使用新生成的场景图并按人物规范逐图验收。检查结果写入 qc/asset-usage.json。
用法（项目根目录）：python <skill>/scripts/make_manifest.py"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import find_story_visuals, find_workspace
from wardrobe import resolve_wardrobe_references, validate_logged_attachments

ap = argparse.ArgumentParser()
ap.add_argument('--project', default='.')
a = ap.parse_args()
P = Path(a.project).resolve()
shots = json.loads((P / 'design/shots.json').read_text(encoding='utf-8'))
cast = json.loads((P / 'design/cast.json').read_text(encoding='utf-8'))
cfg = json.loads((P / 'design/config.json').read_text(encoding='utf-8'))
from voice_cast import check_voice_cast
_vc = check_voice_cast(cfg, cast)
if _vc:
    print('声音与主角性别不一致：' + '；'.join(_vc)); sys.exit(1)
spec = json.loads((P / cfg.get('spec_out', 'design/spec-film.json')).read_text(encoding='utf-8'))
win = {s['id']: (s['start'], s['end']) for s in spec['data']['scenes']}
sha = lambda rel: hashlib.sha256((P / rel).read_bytes()).hexdigest()
fixed = shots.get('fixed_assets', {})
assets, out_shots, md, problems = {}, [], ['# 表演镜头表', '', '时间 = 该画板的语音窗口；原文取自锁定口播。', ''], []
for s in shots['shots']:
    aid = s.get('asset', s['id'])
    if s['id'] not in win:
        problems.append(f"{s['id']}: 事件表里没有同名画板"); continue
    rel = fixed[s['fixed']]['file'] if s.get('fixed') else (s.get('image_file') or f'assets/images/C-{aid}-v01.png')
    if not (P / rel).is_file():
        problems.append(f'{aid}: 图片不存在 {rel}'); continue
    try:
        wardrobe_map = resolve_wardrobe_references(s, cast, P)
        if s.get('fixed') and wardrobe_map:
            problems.append(f"{s['id']}: 妈妈/班主任镜头不能使用固定旧图，须按本镜服饰参考重新生图")
        for cast_id, ref_paths in wardrobe_map.items():
            try:
                validate_logged_attachments(P, Path(rel).stem, ref_paths)
            except ValueError as e:
                problems.append(f"{s['id']}: {e}")
    except (ValueError, OSError) as e:
        problems.append(f"{s['id']}: 服饰参考校验失败：{e}")
    if aid not in assets:
        assets[aid] = {'file': '../' + rel, 'origin_id': fixed[s['fixed']]['origin_id'] if s.get('fixed') else Path(rel).stem, 'sha256': sha(rel)}
        if s.get('reviewed') is True or s.get('fixed'):
            assets[aid]['quality_review'] = {k: 'pass' for k in ('identity', 'anatomy', 'finish')}
    if not str(s.get('hands_check', '')).strip():
        problems.append(f"{s['id']}: 缺 hands_check（放大逐只数手：每人两只手、一左一右、各五指、无多出的手或手臂，写清每只手在哪、做什么）")
    obs = s.get('observation') or (fixed[s['fixed']]['observation'] if s.get('fixed') else '')
    if not (s.get('reviewed') is True or s.get('fixed')) or not obs:
        problems.append(f"{s['id']}: 未经逐图验收（需要 reviewed=true 和基于实际图片的 observation）")
    ok = {k: 'pass' for k in ('identity', 'emotion', 'action', 'relation')}
    shot = {'id': s['id'], 'start': win[s['id']][0], 'end': win[s['id']][1], 'narration': s['narration'], 'roles': s['roles'], 'assets': [aid],
            'assessments': {aid: {**ok, 'observation': obs}}}
    if s.get('fixed'):
        # 旧项目兼容：fixed_assets 仅服务于历史镜头，新陪伴师镜头应使用逐图生成的新场景图。
        fx = fixed[s['fixed']]
        logo = (P / 'design' / fx['logo_source']).resolve()
        shot['companion_review'] = {'identity': 'pass', 'listening': 'pass', 'logo': 'pass', 'logo_side': 'wearer_left', 'logo_source': fx['logo_source'],
                                    'logo_sha256': hashlib.sha256(logo.read_bytes()).hexdigest() if logo.is_file() else '', 'observation': fx['observation']}
    elif any(r.get('name') == '陪伴师' or r.get('brand_role') == 'companion' for r in s['roles']):
        review = s.get('companion_review', {})
        required = ('identity', 'listening', 'logo', 'logo_side', 'logo_source', 'observation')
        missing = [k for k in required if not review.get(k)]
        if missing:
            problems.append(f"{s['id']}: 陪伴师新图缺少逐图审核字段 {missing}")
        else:
            logo_rel = review['logo_source']
            logo = (P / logo_rel).resolve()
            if not logo.is_file():
                problems.append(f"{s['id']}: 品牌 Logo 原图不存在 {logo_rel}")
            shot['companion_review'] = {**review, 'logo_source': '../' + logo_rel, 'logo_sha256': hashlib.sha256(logo.read_bytes()).hexdigest() if logo.is_file() else ''}
    out_shots.append(shot)
    md.append(f"## {s['id']}（{shot['start']:.2f}–{shot['end']:.2f}s）")
    md.append(f"- 原文：{s['narration']}")
    for r in s['roles']:
        md.append(f"- {r['name']}（{r['age']}岁）：情绪={r['emotion']}；眉眼嘴={r['face']}；肩背手脚={r['body']}；视线={r['gaze']}；动作={r['action']}；禁止={r['avoid']}")
    md += [f'- 实图验收：{obs}', '']
if problems:
    print('清单不完整：'); [print(' -', x) for x in problems]; sys.exit(1)
(P / 'design/performance-plan.json').write_text(json.dumps({'style': 'Why-HandDrawn-Video C 线稿白板', 'reuse_limit': 2, 'assets': assets, 'shots': out_shots}, ensure_ascii=False, indent=2), encoding='utf-8')
(P / 'brief/PERFORMANCE_TABLE.md').write_text('\n'.join(md), encoding='utf-8')
sv = find_story_visuals(find_workspace(P))
if not sv:
    sys.exit('找不到 why-story-visuals 检查器')
r = subprocess.run([sys.executable, str(sv / 'scripts/check_visual_manifest.py'), str(P / 'design/performance-plan.json'), '--out', str(P / 'qc/asset-usage.json')], capture_output=True, text=True)
print(r.stdout.strip())
sys.exit(r.returncode)
