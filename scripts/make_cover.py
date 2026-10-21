"""封面：代码排字（标题逐字、首尾橙色重点）+ 按工具分流生成小尺寸人物插画 + 合成 1080×1920 竖版封面。规则见 references/COVER_SPEC.md。
流程（项目根目录）：
  1) 写 design/cover.json（标题分行、橙色词、插画场景）——先写 design/cover-philosophy-vNN.md（canvas-design 视觉理念）
  2) python <skill>/scripts/make_cover.py --text-only      只出文字底稿 renders/<名>-cover-text-vNN.png，供检查
  3) Claude / WorkBuddy：运行本脚本，由当前 Codex CLI 生图并合成。
     Codex：先运行 --emit-image-prompt 导出提示词，使用 Codex 内置生图工具生成指定插画，再运行 --skip-gen --imagegen-tool "Codex 内置生图工具" 合成。
  --emit-image-prompt 只导出封面插画提示词；--skip-gen 复用已有插画只合成；--imagegen-tool / --imagegen-version 登记外部内置工具；--version v02 出新版本，不覆盖旧文件。
design/cover.json 例：
{"lines": [[["初一男孩开学一个月", 0]], [["就", 0], ["不想上学", 1], ["了，", 0]], [["指导3周后", 0]], [["爱上了上学", 1, 150]]],
 "scene": "English scene ...", "cast": "xiaobin", "illus_width": 760, "illus_center_y": 1260}
每个片段 [文字, 是否橙色, 可选字号]；所有片段拼起来必须与 brief/title.txt 逐字相同。"""
import argparse, hashlib, json, shutil, subprocess, sys, time
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image, ImageDraw, ImageFont, ImageChops
import gen_sprites as G
from common import SKILL

W, H = 1080, 1920
INK, OR = (23, 23, 23), (237, 121, 41)
FONT_CANDIDATES = [str(SKILL / 'assets/fonts/NotoSansSC-VF.ttf')]


def load_font(size):
    for f in FONT_CANDIDATES:
        if Path(f).is_file():
            ft = ImageFont.truetype(f, size)
            try: ft.set_variation_by_axes([900])                    # 可变字体取最粗字重
            except Exception: pass
            return ft, f
    raise SystemExit('包内中文字体缺失，请重新解压完整 Skill 包')


def render_text(cfg, title):
    flat = ''.join(seg[0] for line in cfg['lines'] for seg in line)
    if flat != title:
        raise SystemExit(f'封面标题与 brief/title.txt 不一致：\n  封面 {flat}\n  原稿 {title}')
    im = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(im)
    base = cfg.get('size', 108); gap = cfg.get('line_gap', 1.3)
    y = cfg.get('title_top', 290); used = None
    for line in cfg['lines']:
        parts = []
        for seg in line:
            ft, used = load_font(seg[2] if len(seg) > 2 else base)
            parts.append((seg[0], seg[1], ft))
        wid = sum(d.textlength(t, font=f) for t, _, f in parts)
        if wid > W - 2 * cfg.get('margin', 48):
            raise SystemExit(f'封面这一行太宽（{wid:.0f}px）：{"".join(p[0] for p in parts)}，请减小字号或换行')
        x = (W - wid) / 2
        hmax = max(f.size for _, _, f in parts)
        for t, o, f in parts:
            d.text((x, y + hmax - f.size), t, font=f, fill=OR if o else INK)
            x += d.textlength(t, font=f)
        y += int(hmax * gap)
    return im, y, used


def whiten(img):
    """把生图残留的近白底（如 252,252,252 的浅灰块）归为纯白，只处理浅色背景，不改线条。"""
    return img.convert('RGB').point(lambda v: 255 if v >= 238 else int(v * 255 / 238))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', default='.'); ap.add_argument('--version', default='v01')
    ap.add_argument('--text-only', action='store_true'); ap.add_argument('--skip-gen', action='store_true')
    ap.add_argument('--emit-image-prompt', action='store_true'); ap.add_argument('--imagegen-tool', default=''); ap.add_argument('--imagegen-version', default='')
    a = ap.parse_args()
    P = Path(a.project).resolve(); ver = a.version
    cfg = json.loads((P / 'design/cover.json').read_text(encoding='utf-8'))
    title = (P / 'brief/title.txt').read_text(encoding='utf-8').strip()
    name = cfg.get('name') or P.name.split('-', 1)[1].rsplit('-v', 1)[0]
    (P / 'renders').mkdir(exist_ok=True)
    text_im, text_end, font_used = render_text(cfg, title)
    tpath = P / f'renders/{name}-cover-text-{ver}.png'
    text_im.save(tpath)
    print('文字底稿 →', tpath.relative_to(P), '| 标题块底边 y =', text_end)
    if a.text_only:
        return
    illus_rel = f'assets/images/cover-illus-{ver}.png'
    if a.emit_image_prompt or not (a.skip_gen or (P / illus_rel).exists()):
        from lock_voice import enforce_voice_locked
        try: enforce_voice_locked(P)
        except ValueError as e: raise SystemExit('停止：' + str(e))
    if a.emit_image_prompt:
        shots = json.loads((P / 'design/shots.json').read_text(encoding='utf-8'))
        cast = json.loads((P / 'design/cast.json').read_text(encoding='utf-8'))
        shot = {'cast': cfg['cast'], 'scene': cfg['scene'], 'minor': True}
        text = G.compose(shot, cast) + G.FOOT.format(out=illus_rel)
        prompt_file = P / f'design/prompts/cover-illus-{ver}.txt'
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(text, encoding='utf-8')
        print('封面插画提示词 →', prompt_file.relative_to(P))
        print('参考图 →', P / f"assets/images/concept-{cfg['cast']}-v01.png")
        print('生成后保存到 →', P / illus_rel)
        return
    # ---- 插画（Claude/WorkBuddy 用 Codex CLI；Codex 用 --emit-image-prompt）----
    illus = P / illus_rel
    rec = None
    if not illus.exists() and not a.skip_gen:
        shots = json.loads((P / 'design/shots.json').read_text(encoding='utf-8'))
        cast = json.loads((P / 'design/cast.json').read_text(encoding='utf-8'))
        shot = {'cast': cfg['cast'], 'scene': cfg['scene'], 'minor': True}
        text = G.compose(shot, cast)
        ref = [P / f"assets/images/concept-{cfg['cast']}-v01.png"]
        (P / 'qc').mkdir(exist_ok=True)
        rec = G.run((P, f'cover-illus-{ver}', text, ref, illus_rel, 'codex'))
        G.write_log(P, [rec], 'codex')
    if not illus.exists():
        raise SystemExit('封面插画不存在（生成失败或 --skip-gen 时没有旧图）；如实报告，不用其他工具替代。')
    # ---- 合成 ----
    il = whiten(Image.open(illus))
    bbox = ImageChops.invert(il.convert('L')).point(lambda v: 255 if v > 12 else 0).getbbox()
    il = il.crop(bbox)
    iw = cfg.get('illus_width', 760)
    il = il.resize((iw, int(il.height * iw / il.width)), Image.LANCZOS)
    cy = cfg.get('illus_center_y', 1260)
    x, y = (W - il.width) // 2, int(cy - il.height / 2)
    if y < text_end + cfg.get('min_gap', 90):
        raise SystemExit(f'插画顶 y={y} 离标题底边 {text_end} 太近，请调 illus_center_y 或 illus_width')
    if y + il.height > H - 200:
        raise SystemExit(f'插画底 y={y + il.height} 太靠下（需留出底部界面区）')
    canvas = text_im.copy()
    region = canvas.crop((x, y, x + il.width, y + il.height))
    canvas.paste(ImageChops.darker(region, il), (x, y))
    out = P / f'renders/{name}-cover-{ver}.png'
    canvas.save(out)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    ver_codex = ''
    if rec:
        codex_bin = shutil.which('codex.cmd') or shutil.which('codex')
        if codex_bin:
            try:
                ver_codex = subprocess.run([codex_bin, '--version'], capture_output=True, text=True, timeout=30).stdout.strip()
            except (OSError, subprocess.TimeoutExpired):
                ver_codex = '版本查询失败'
    imagegen_tool = 'Codex CLI' if rec else (a.imagegen_tool or '已有插画（工具未登记）')
    imagegen_version = ver_codex if rec else a.imagegen_version
    prompt_file = P / f'design/prompts/cover-illus-{ver}.txt'
    prompt_sha256 = hashlib.sha256(prompt_file.read_bytes()).hexdigest() if prompt_file.is_file() else None
    imagegen_method = 'Codex CLI 调用' if rec else ('Codex 内置生图工具' if a.imagegen_tool else '复用已有插画')
    record = {'time': time.strftime('%Y-%m-%d %H:%M'), 'version': ver, 'title': title, 'size': [W, H], 'font': font_used,
              'lines': cfg['lines'], 'illus_width': iw, 'illus_center_y': cy, 'illus_file': illus_rel, 'illus_sha256': sha(illus),
              'cover_sha256': sha(out), 'codex': ver_codex, 'imagegen_tool': imagegen_tool,
              'imagegen_version': imagegen_version, 'imagegen_method': imagegen_method, 'imagegen_prompt': str(prompt_file.relative_to(P)) if prompt_file.is_file() else None, 'imagegen_prompt_sha256': prompt_sha256, 'imagegen': rec or '复用已有插画', 'philosophy': f'design/cover-philosophy-{ver}.md',
              'canvas_design': {'source': 'https://github.com/anthropics/skills/blob/b9e19e6f44773509fbdd7001d77ff41a49a486c1/skills/canvas-design/SKILL.md', 'bundled_path': 'references/COVER_ART_DIRECTION.md', 'guidance_sha256': sha(SKILL / 'references/COVER_ART_DIRECTION.md'), 'commit': 'b9e19e6f44773509fbdd7001d77ff41a49a486c1', 'read_on': time.strftime('%Y-%m-%d')}}
    (P / f'design/cover-record-{ver}.json').write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
    print('封面 →', out.relative_to(P))


if __name__ == '__main__':
    main()
