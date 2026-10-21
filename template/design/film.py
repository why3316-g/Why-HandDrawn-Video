"""本视频的事件表。每块画板 = 口播的一个意思单元；时间全部来自配音词级时间戳。
运行：在项目根目录执行  python design/film.py   → 写出 design/spec-film.json 并打印"时间审查"。
参照 examples/xiaoyu/film.py 与 references/LAYOUT_LIBRARY.md 写画板；外壳（Clock / Film / 别名 / 字幕 / build）不改。"""
import json, os, sys
from pathlib import Path
P = Path(os.environ.get('HDV_PROJECT') or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(P / 'design'))
if os.environ.get('HDV_SCRIPTS'): sys.path.insert(0, os.environ['HDV_SCRIPTS'])
from hdv import Clock, Film, INK, OR, captions_from_breaks
cfg = json.loads((P / 'design/config.json').read_text(encoding='utf-8'))
clock = Clock(P / cfg['narration'], P / cfg['volc_json'])
F = Film(P, clock, header_first=cfg['header_first'], header_other=cfg['header_other'])
S, E = F.S, F.E
panel, text, line, hero, box, arrow, cross, check, bubble, phone, ell = F.panel, F.text, F.line, F.hero, F.box, F.arrow, F.cross, F.check, F.bubble, F.phone, F.ell

# ======================= 画板定义（本视频专属）=======================
# 【开头规范，必须遵守：references/OPENING_SPEC.md】第 1 块画板：人物 hero 起笔 ≤ 0.5 s；0–5 s 内除字幕外持续有新笔画（画元素、写关键词、圈/叉/勾/箭头），静止 ≤ 1.0 s；
#   画的东西只来自口播，屏幕文字取口播原文，勾/叉等非重点标记用墨色（INK），橙色每块 ≤ 3–4 个。自检不通过会拒绝输出 spec。
# 画板坐标：宽 1080，可见区 y 285–1455。每块画板：panel(序号, 'id', 起始秒)，起始 = 该意思单元第一句口播起点 - 0.1。
# 文字起笔 = S('口播里的原词')；人物 hero(序号, 'id', 中心x, 顶y, 高, 起笔, 时长)；id 必须与 design/shots.json 的镜头 id 对应。
# 下面是占位示例，换成本视频的画板：
# panel(0, 'hook', 0.0)
# hero(0, 'hook', 330, 600, 640, .55, 1.3)
# text(0, '关键词', 100, 495, 80, S('关键词'), .7, OR)
raise SystemExit('design/film.py 还是模板：请按本视频口播写画板（参照 examples/xiaoyu/film.py）。')

# ======================= 字幕 + 输出（通用）=======================
breaks = json.loads((P / 'design/breaks.json').read_text(encoding='utf-8'))
F.build(captions_from_breaks(clock, breaks), out=cfg.get('spec_out', 'design/spec-film.json'))
