"""人物线稿生图：读 design/shots.json + design/cast.json，按 PROMPT_PACK 的固定骨架拼提示词。Claude 和 WorkBuddy 默认经当前 Codex CLI 并行生成；Codex 使用 --emit-only 导出提示词后改用内置生图工具。
--emit-only：只写提示词文件（design/prompts/*.txt）不调用任何工具——供 Codex 内置生图路径使用；按提示词指定的路径保存产物，并手动补齐生图日志中的工具、版本与输出 SHA-256。
顺序：先 concept（以 style_ref 为"仅风格"参考）→ 其余镜头以 concept 为参考，保持同一个人。记录写入 qc/imagegen-run.json 与 qc/IMAGEGEN_LOG.md（不含密钥）。
用法（项目根目录）：python <skill>/scripts/gen_sprites.py [--emit-only] [--only id,id] [--workers 6]"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass
from concurrent.futures import ThreadPoolExecutor
from wardrobe import cast_keys_for_shot, resolve_wardrobe_references, wardrobe_prompt_instructions, wardrobe_role

STYLE = ("Use case: illustration-story. The reference image defines the selected C clean ligne-claire ink drawing style. Clear elegant black contours with controlled line weights, "
         "accurate small expressive eyes, eyebrows and mouth, natural anatomy and hands (every person has exactly two arms and exactly two hands, one clearly a left hand and one clearly a right hand, five fingers each, no duplicated or extra limbs; avoid crossed arms or a hand resting on the person's own arm), sparse carefully chosen clothing folds, white clothing interiors and very subtle flat skin tint. "
         "No hatching, realism, glamour, fashion poses, celebrity styling, glossy anime eyes, huge heads or crude stick figures. Ordinary Chinese family members, recognizable age differences. "
         "Colour rule: black ink on white only. All clothing (tops, cardigans, sweaters, trousers, skirts) is plain white with black outlines and NO grey, black, cream or coloured fill; hair is solid black; shoes are white with black outlines; "
         "the only colour allowed is a tiny orange accent on the cuffs or collar edge and a very faint skin tint. Furniture and props are line drawings with no colour fill. "
         "Isolated character acting illustration on pure white, entire requested bodies and hands inside generous margins. No text, lettering, borders, scenery or watermark. "
         "Pure white background everywhere: no glow, no vignette, no drop shadow, no dark or night-time areas, no black-filled regions or silhouettes; black is only for thin outlines and solid black hair. ")
MINOR = ("Clothing note for any character under 18: an ordinary everyday school or home outfit, a long-sleeved top and long trousers, fully covered, "
         "relaxed natural posture, calm everyday scene. ")
COMPANION_STYLE = ("COMPANION COLOR OVERRIDE: solid black hair; white fill on face, skin, all clothing and all other regions; crisp black outlines; orange ONLY on sleeve cuffs. "
                   "No skin tint, gray shading, colored clothing, orange collar, or other accent colors. The exact source logo is a small chest badge and may retain its original brand colors. "
                   "SCENE OVERRIDE: this is a scene illustration, not an isolated cutout. Include the requested phone/video-call framing and sparse relevant environment as simple black line art with white fills; no text or unrelated props.")
HEAD = ("Use your built-in image generation tool (do NOT draw with code, do NOT post-process with scripts) to create ONE image, landscape 3:2, pure white background. Describe the framing in the prompt; do not pass any size parameter. Do not read or edit any other file in the working directory: this task is only to generate the image described below and save it.\n\n")
FOOT = ("\n\nAfter generating, copy the final PNG to {out} (relative to the current working directory) and print its absolute path and SHA-256. "
        "If the image tool is unavailable or fails, say exactly why and stop; do not substitute another method.\n")


def _minor(shot, c):
    """角色或镜头里有 18 岁以下的人，就带上未成年人着装条款。"""
    if (c and c.get('minor')) or (shot or {}).get('minor'):
        return True
    for r in (shot or {}).get('roles', []):
        try:
            if int(r.get('age', 99)) < 18:
                return True
        except (TypeError, ValueError):
            pass
    return False


def compose(shot, cast, concept_mode=False, wardrobe_map=None):
    if concept_mode:
        c = cast
        return (HEAD + (MINOR if _minor(None, c) else '') + "STYLE-ONLY reference attached: it shows a DIFFERENT person (this character is not him/her); copy only the drawing style. " + STYLE + c['identity'] + ' ' +
                c.get('concept_pose', 'Full body standing, three-quarter view, arms hanging naturally, calm neutral expression. Neutral model-sheet-like pose.'))
    if wardrobe_map is None:
        wardrobe_map = {}
        per_role = shot.get('wardrobe_references', {}) or {}
        keys = cast_keys_for_shot(shot, cast)
        for key in keys:
            refs = per_role.get(key, per_role.get(cast[key].get('name', key)))
            if refs is None and shot.get('wardrobe_reference_images') is not None and len(keys) == 1:
                refs = shot['wardrobe_reference_images']
            if refs is None:
                refs = cast[key].get('wardrobe_reference_images')
            if refs:
                wardrobe_map[key] = [refs] if isinstance(refs, str) else refs
    clothing_ref = wardrobe_prompt_instructions(wardrobe_map, cast)
    if shot.get('layout_reference_images'):
        ref = ("The attached layout images are COMPOSITION-ONLY references for a single whiteboard containing multiple distinct household scenes. Borrow only spatial hierarchy, spacing, relative scale and whitespace. Do NOT copy any reference people, family facts, text, props, furniture, room background or exact vignette content. Rebuild each vignette only from the approved script and this shot description; keep each household visually separate. "
               + clothing_ref + "The final attached image defines ONLY the clean ligne-claire drawing style. ")
        identities = ' '.join(cast[k].get('identity', '') for k in cast_keys_for_shot(shot, cast))
        return HEAD + ref + STYLE + (MINOR if _minor(shot, None) else '') + identities + ' ' + shot['scene']
    if wardrobe_map and not shot.get('cast'):
        identities = ' '.join(cast[k].get('identity', '') for k in wardrobe_map if k in cast)
        return HEAD + clothing_ref + "The final attached image defines ONLY the clean ligne-claire drawing style. " + STYLE + (MINOR if _minor(shot, None) else '') + identities + ' ' + shot['scene']
    if shot.get('cast'):
        c = cast[shot['cast']]
        companion = c.get('brand_role') == 'companion'
        refs = c.get('reference_images', [])
        if isinstance(refs, str): refs = [refs]
        if companion:
            logo_ref = c.get('logo_reference')
            if logo_ref: refs = refs + [logo_ref]
            ref = ("The first five attached images are approved scene references for the SAME companion woman. The last attached image, if present, is the exact brand logo source for her chest badge. Preserve her recognizable identity and design while creating a NEW shot; do not reuse or recreate any reference composition. Prefer an online video-call scene with her visibly inside a phone screen unless the script explicitly requires in-person support. Hair black; all other fills white; black outlines; orange only on sleeve cuffs; use the exact logo source for the badge. ")
            body = ref + STYLE + COMPANION_STYLE + (MINOR if _minor(shot, c) else '') + shot['scene']
        elif c.get('wardrobe_reference_images') or c.get('wardrobe_role') or wardrobe_map:
            ref = (clothing_ref + "The final attached image defines ONLY the clean ligne-claire drawing style. Follow the textual character description for age, face and appearance, and follow this shot for expression, shoes, pose, glasses and props; vary these details naturally between shots as the script requires. " + c['identity'] + ' ')
            body = ref + STYLE + (MINOR if _minor(shot, c) else '') + shot['scene']
        else:
            ref = (f"The attached reference image shows {c['name']} (and defines the clean ligne-claire ink style). Keep the SAME person: same face, hair, build and clothes. {c['identity']} ")
            body = ref + STYLE + (MINOR if _minor(shot, c) else '') + shot['scene']
    else:                                                                # 多人/新人物：参考图只给风格
        body = STYLE + (MINOR if _minor(shot, None) else '') + "The attached reference image defines ONLY the clean ligne-claire ink style (do not copy its person). " + shot['scene']
    return HEAD + body


def run(job):
    P, name, text, ref, out_rel, tool = job
    pf = P / f'design/prompts/{name}.txt'
    pf.parent.mkdir(parents=True, exist_ok=True)
    full = (text + '\n\nREFERENCE IMAGE FILES — each listed file must be attached as an image input to the generation call:\n' +
            ''.join(f'- {Path(x).as_posix()}\n' for x in (ref if isinstance(ref, list) else [ref])) + FOOT.format(out=out_rel))
    pf.write_text(full, encoding='utf-8')
    out = P / out_rel
    refs = ref if isinstance(ref, list) else [ref]
    ref_rel = [str(x.relative_to(P)) for x in refs]
    rec = {'name': name, 'prompt_file': str(pf.relative_to(P)), 'prompt_sha256': hashlib.sha256(full.encode()).hexdigest(),
           'ref': ref_rel, 'attached_ref': [], 'attempts': []}
    if tool == 'emit':
        print('emit', name); return rec
    attached = False
    for attempt in (1, 2):
        if out.exists():
            break
        t0 = time.time()
        if tool == 'volcano':
            import imagegen_volcano as iv
            from common import find_workspace
            try:
                iv.generate(text + '\n\n(The reference images are attached to this request in the order described above.)', refs, out, iv.load_key(find_workspace(P)))
                code = 0
                attached = out.is_file()
            except RuntimeError as exc:
                code = str(exc)[:160]
        else:
            cmd = [shutil.which('codex.cmd') or shutil.which('codex') or 'codex', 'exec', '-s', 'workspace-write', '-C', str(P), '--skip-git-repo-check', '-o', str(P / f'qc/codex-last-{name}.txt')]
            for image in refs:
                cmd += ['-i', str(image)]
            cmd += ['-']
            try:
                r = subprocess.run(cmd, input=full.encode('utf-8'), capture_output=True, timeout=1200)
                code = r.returncode
                attached = code == 0 and out.is_file()
                (P / f'qc/codex-run-{name}-try{attempt}.log').write_bytes(r.stdout[-6000:] + b'\n---stderr---\n' + r.stderr[-3000:])
            except subprocess.TimeoutExpired:
                code = 'timeout-1200s'
            except FileNotFoundError:
                code = 'codex-not-found'
        rec['attempts'].append({'exit': code, 'seconds': round(time.time() - t0, 1), 'output_exists': out.exists()})
    rec['output_sha256'] = hashlib.sha256(out.read_bytes()).hexdigest() if out.exists() else None
    if attached:
        rec['attached_ref'] = ref_rel
    print(json.dumps({k: rec[k] for k in ('name', 'attempts', 'output_sha256')}, ensure_ascii=False), flush=True)
    return rec


def write_log(P, recs, tool):
    """把本次运行写入 qc/imagegen-run.json 与 qc/IMAGEGEN_LOG.md（累积追加，不覆盖旧记录）。"""
    if not recs:
        return
    ver = (subprocess.run([shutil.which('codex.cmd') or 'codex', '--version'], capture_output=True, text=True).stdout.strip() if tool == 'codex'
           else 'volcano-ark ' + (os.environ.get('ARK_IMAGE_MODEL') or 'doubao-seedream-4-5-251128') if tool == 'volcano' else 'emit-only')
    runf = P / 'qc/imagegen-run.json'
    runs = json.loads(runf.read_text(encoding='utf-8')).get('runs', []) if runf.exists() else []
    runs.append({'time': time.strftime('%Y-%m-%d %H:%M'), 'codex': ver, 'records': recs})
    runf.write_text(json.dumps({'runs': runs}, ensure_ascii=False, indent=1), encoding='utf-8')
    rows = ['| 图 | 提示词 | 计划参考图 | 实际附图 | 过程 | 输出 SHA-256（前 16 位） |', '|---|---|---|---|---|---|']
    for r in recs:
        proc = '; '.join(f"第{i + 1}次 退出码{x['exit']} {x['seconds']}s {'出图' if x['output_exists'] else '未出图'}" for i, x in enumerate(r['attempts'])) or '仅写提示词'
        rows.append(f"| {r['name']} | {r['prompt_file']} | {r['ref']} | {r.get('attached_ref', [])} | {proc} | {(r.get('output_sha256') or '')[:16]} |")
    log = P / 'qc/IMAGEGEN_LOG.md'
    nl = chr(10)
    prev = log.read_text(encoding='utf-8').rstrip(nl) + nl + nl if log.exists() else '# 生图记录（密钥与令牌不入档）' + nl + nl
    section = f'## {time.strftime("%Y-%m-%d %H:%M")} 运行（{ver}）' + nl + nl + nl.join(rows) + nl + nl + 'Codex 内置生图为 emit-only：生成后须把实际传给图像工具的参考路径写入 imagegen-run.json 对应记录 attached_ref；未填写会被渲染前清单拦截。失败的尝试如实保留；没有用别的办法替代。逐图验收见 design/performance-plan.json。' + nl
    log.write_text(prev + section, encoding='utf-8')


def reference_images_for_shot(project, shot, cast, wardrobe_map, style_ref):
    """Return image inputs in the same order described by the generated prompt."""
    P = Path(project)
    clothing = [P / rel for paths in wardrobe_map.values() for rel in paths]
    layout = shot.get('layout_reference_images')
    if layout:
        if isinstance(layout, str):
            layout = [layout]
        return [P / x for x in layout] + clothing + [Path(style_ref)]
    if clothing:
        return clothing + [Path(style_ref)]
    key = shot.get('cast')
    if key and key in cast and cast[key].get('reference_images'):
        refs = cast[key]['reference_images']
        if isinstance(refs, str):
            refs = [refs]
        result = [P / x for x in refs]
        if cast[key].get('logo_reference'):
            result.append(P / cast[key]['logo_reference'])
        return result
    return [P / f"assets/images/concept-{key}-v01.png"] if key else [Path(style_ref)]


EXPECTED_MODEL = 'gpt-6-luna'


def codex_default_model():
    """读 config.toml 顶层 model（第一个 [段] 之前）；读不到返回 None。只读取，不修改配置，也不向 codex 传 --model。"""
    cfg = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex') / 'config.toml'
    try:
        for line in cfg.read_text(encoding='utf-8-sig').splitlines():
            if line.lstrip().startswith('['):
                break
            m = re.match(r'\s*model\s*=\s*"([^"]+)"', line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', default='.'); ap.add_argument('--emit-only', action='store_true'); ap.add_argument('--only', default=''); ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--image-backend', default='codex', choices=('codex', 'volcano'), help='codex=Codex CLI（默认，需 ChatGPT 账号登录）；volcano=火山方舟 Seedream（需 ARK_API_KEY，见 README）')
    ap.add_argument('--confirm-model', default='', help='用户已同意用非 gpt-6-luna 的默认模型生图时，填该模型名')
    a = ap.parse_args()
    P = Path(a.project).resolve()
    shots = json.loads((P / 'design/shots.json').read_text(encoding='utf-8'))
    cast = json.loads((P / 'design/cast.json').read_text(encoding='utf-8'))
    from voice_cast import enforce
    try: enforce(P)
    except ValueError as e: print('停止：' + str(e)); sys.exit(3)
    tool = 'emit' if a.emit_only else a.image_backend
    if tool == 'volcano':
        import imagegen_volcano as iv
        from common import find_workspace
        if not iv.key_ready(find_workspace(P)):
            print('停止：没找到火山方舟密钥。把 ARK_API_KEY 写进视频工作区 .private/ark.env（格式见 template/ark.env.example），教程见 README 开头；不会自动改用其他生图工具。')
            sys.exit(4)
    if tool == 'codex':
        model = codex_default_model()
        if model != EXPECTED_MODEL and a.confirm_model != (model or ''):
            print(f'停止：Codex 默认模型是 {model or "读不到 config.toml 的 model"}，不是 {EXPECTED_MODEL}（非 luna 可能很快耗尽额度）。'
                  f'请先问用户；用户明确同意后加 --confirm-model {model or "<模型名>"} 再运行。本脚本从不传 --model，也不改 config.toml。')
            sys.exit(2)
    style_ref = P / shots.get('style_ref', 'assets/images/style-ref-C.png')
    (P / 'qc').mkdir(exist_ok=True)
    only = set(x for x in a.only.split(',') if x)
    wardrobe_by_shot = {}
    for s in shots['shots']:
        if not s.get('generate', True) or (only and s.get('asset', s['id']) not in only and s['id'] not in only):
            continue
        try:
            wardrobe_map = resolve_wardrobe_references(s, cast, P)
        except (ValueError, OSError) as e:
            sys.exit(f"服饰参考预检失败（{s['id']}）：{e}")
        if s.get('fixed') and wardrobe_map:
            sys.exit(f"服饰参考预检失败（{s['id']}）：出镜妈妈/班主任不能使用固定旧图，须按本镜服饰参考重新生图。")
        wardrobe_by_shot[s['id']] = wardrobe_map
    recs = []
    # 1) concept（每个 cast 一张形象基准图）
    gen_cast = {k: v for k, v in cast.items() if not v.get('reference_images') and not v.get('wardrobe_reference_images') and not wardrobe_role(v)}
    for key, c in gen_cast.items():
        out_rel = f'assets/images/concept-{key}-v01.png'
        if (P / out_rel).exists() or (only and f'concept-{key}' not in only and only != {'concept'}):
            continue
        recs.append(run((P, f'concept-{key}-v01', compose(None, c, True), style_ref, out_rel, tool)))
    for key in gen_cast:
        if not (P / f'assets/images/concept-{key}-v01.png').exists() and tool != 'emit':
            write_log(P, recs, tool)
            print(f'concept-{key} 未生成，停止（需要先通过形象基准图，再出各镜头）'); sys.exit(1)
    # 2) 各镜头
    jobs = []
    for s in shots['shots']:
        if not s.get('generate', True) or s.get('fixed') or (only and s.get('asset', s['id']) not in only and s['id'] not in only):
            continue
        aid = s.get('asset', s['id'])
        out_rel = s.get('image_file') or f"assets/images/C-{aid}-v01.png"
        if (P / out_rel).exists():
            continue
        wardrobe_map = wardrobe_by_shot.get(s['id'], {})
        ref = reference_images_for_shot(P, s, cast, wardrobe_map, style_ref)
        jobs.append((P, Path(out_rel).stem, compose(s, cast, wardrobe_map=wardrobe_map), ref, out_rel, tool))
    with ThreadPoolExecutor(a.workers) as ex:
        recs += list(ex.map(run, jobs))
    write_log(P, recs, tool)
    print('ALL DONE')


if __name__ == '__main__':
    main()
