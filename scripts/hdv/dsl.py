"""事件表 DSL：把"画板上的文字、线条道具、人物描绘"写成带绝对时间的事件，输出渲染配置 spec。
画板坐标：宽 1080，可见区 y 285–1455，板内 x 从 0 起（渲染时再加 index*1120）。时间全部来自 Clock（配音词级时间戳）。
每个事件可带 tag（cross/check/pop/frame/ring），供版面自检识别语义；渲染器忽略 tag，混音不使用音效。"""
import json, math, sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')   # Windows 重定向到文件时默认 GBK，自检错误里的 ✗ 会让脚本崩溃、吞掉真正的错误原因
except Exception: pass

INK, OR = '#171717', '#ed7929'
PANEL = 1120


class Film:
    def __init__(self, project, clock, lib_json='design/sprite-strokes-v01.json', hand='../assets/images/marker-hand-v02.png',
                 hand_tip=(147, 119), header_first=('', ''), header_other='', tail=1.6, fps=30, grammar='hand_drawn_marker'):
        self.P, self.clock = Path(project), clock
        self.lib = json.loads((self.P / lib_json).read_text(encoding='utf-8'))
        self.EV, self.PANELS = [], []
        self.hand, self.hand_tip = hand, list(hand_tip)
        self.header_first, self.header_other = list(header_first), header_other
        self.tail, self.fps, self.grammar = tail, fps, grammar
        self.aspect = {k: v['rect'][2] / v['rect'][3] for k, v in self.lib['sprites'].items()}

    # ---- 时间 ----
    def S(self, phrase, nth=0, last=False): return self.clock.T(phrase, nth, last)[0]
    def E(self, phrase, nth=0, last=False): return self.clock.T(phrase, nth, last)[1]

    # ---- 画板 ----
    def panel(self, i, pid, start): self.PANELS.append((i, pid, start))

    # ---- 基础事件 ----
    def text(self, i, s, x, y, size, at, dur=None, color=INK, fade=False):
        d = dur if dur else max(.35, min(len(s) * .11, .9))
        self.EV.append({'kind': 'text', 'index': i, 'str': s, 'x': x, 'y': y, 'size': size, 'at': round(at, 3), 'dur': round(d, 3), 'color': color, **({'fade': True} if fade else {})})

    def line(self, i, pts, at, dur, color=INK, width=6, curved=True, tag=None):
        e = {'kind': 'line', 'index': i, 'p': [[round(a, 1), round(b, 1)] for a, b in pts], 'at': round(at, 3), 'dur': round(dur, 3), 'color': color, 'width': width, 'curved': curved}
        if tag: e['tag'] = tag
        self.EV.append(e)

    def hero(self, i, sid, cx, top, h, at, dur):
        self.EV.append({'kind': 'hero', 'index': i, 'id': sid, 'cx': cx, 'top': top, 'h': h, 'at': round(at, 3), 'dur': round(dur, 3)})

    # ---- 组合道具 ----
    @staticmethod
    def ell(x, y, rx, ry, n=60):
        return [(x + rx * math.cos(-math.pi / 2 + t * (math.pi * 1.52) / (n - 1)), y + ry * math.sin(-math.pi / 2 + t * (math.pi * 1.52) / (n - 1))) for t in range(n)]

    @staticmethod
    def squircle(x, y, rx, ry, n=60, p=4):
        """与 ell 同起点、同弧度（约 273° 开口环）的超椭圆点列，供 ring 使用。"""
        pts = []
        for t in range(n):
            a = -math.pi / 2 + t * (math.pi * 1.52) / (n - 1); c, sn = math.cos(a), math.sin(a)
            pts.append((x + rx * math.copysign(abs(c) ** (2 / p), c), y + ry * math.copysign(abs(sn) ** (2 / p), sn)))
        return pts

    def box(self, i, x, y, w, h, at, dur=.4, color=INK, tag='frame'):
        self.line(i, [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], at, dur, color, 6, False, tag)

    def arrow(self, i, x, y, x2, y2, at, color=OR):
        self.line(i, [(x, y), (x2, y2)], at, .35, color, 7, False)
        a = math.atan2(y2 - y, x2 - x); r = 25
        self.line(i, [(x2 - math.cos(a - .5) * r, y2 - math.sin(a - .5) * r), (x2, y2), (x2 - math.cos(a + .5) * r, y2 - math.sin(a + .5) * r)], at + .35, .15, color, 7, False)

    def cross(self, i, x, y, w, h, at, color=OR):
        """否定的叉。默认橙（STYLE_SPEC 已批准的画法）；开头块或本块橙色元素已满 3–4 个时显式传 INK，见 OPENING_SPEC。"""
        self.line(i, [(x, y), (x + w, y + h)], at, .12, color, 6, False, 'cross'); self.line(i, [(x + w, y), (x, y + h)], at + .12, .12, color, 6, False)

    def check(self, i, x, y, at, color=OR): self.line(i, [(x, y), (x + 22, y + 30), (x + 60, y - 28)], at, .25, color, 7, False, 'check')

    def bubble(self, i, cx, cy, rx, ry, s, size, at, color=INK):
        self.line(i, self.ell(cx, cy, rx, ry), at, .35, color, 5, True, 'pop'); self.text(i, s, cx - len(s) * size / 2, cy + size * .3, size, at + .3, .3, color)

    def ring(self, i, s, x, y, size, at, dur=.4, color=OR):
        """圈住 text(i, s, x, y, size, …) 写的字。y 是文字基线（不是顶部）；圈的位置按字的真实包围盒算，不要手写 ell 坐标去圈字。"""
        from .lint import text_w
        w = text_w(s, size)
        # 四次超椭圆：普通椭圆在字多时两端变窄，会从首尾字的上下角穿过去；超椭圆两端仍留够高度，1–8 字都圈在字外。
        self.line(i, self.squircle(x + w / 2, y - size * .34, w / 2 + size * .5, size * .66), at, dur, color, 6, True, 'ring:' + s)

    def phone(self, i, x, y, w, h, at):
        self.box(i, x, y, w, h, at, .4); self.line(i, [(x + 15, y + 45), (x + w - 15, y + 45)], at + .43, .14)
        self.line(i, self.ell(x + w / 2, y + h - 24, 8, 8), at + .6, .12)

    # ---- 输出 ----
    def build(self, captions, out='design/spec.json'):
        scenes = []
        for k, (i, pid, st) in enumerate(self.PANELS):
            en = self.PANELS[k + 1][2] if k + 1 < len(self.PANELS) else self.clock.end + 1.4
            scenes.append({'index': i, 'id': pid, 'start': round(max(0, st), 3), 'end': round(en, 3)})
        dur = round((self.clock.end + self.tail) * self.fps) / self.fps
        spec = {'grammar': self.grammar, 'duration': dur, 'fps': self.fps, 'width': 1080, 'height': 1920,
                'data': {'image': self.hand, 'handTip': self.hand_tip, 'header': {'first': self.header_first, 'other': self.header_other},
                         'scenes': scenes, 'events': self.EV, 'captions': captions, 'spriteLibrary': self.lib},
                'cues': [{'at': 0, 'kind': 'asset', 'image': '../assets/images/' + v['file'], 'data': {'group': k}} for k, v in self.lib['source_images'].items()]}
        from .lint import lint, panel_rhythm_issues, panel_rhythm_report, panel_exit_issues
        errs, warns = lint(self.EV)
        errs.extend(panel_rhythm_issues(self.EV, scenes))
        errs.extend(panel_exit_issues(self.EV, scenes))
        # 越界与开头自检（2026-10-13 修复：人物图越出画板会泄漏到相邻画板；开头必须先画人）
        from .lint import text_w as _tw
        for e in self.EV:
            if e['kind'] == 'hero':
                w = e['h'] * self.aspect[e['id']]; x0, x1 = e['cx'] - w / 2, e['cx'] + w / 2
                if x0 < 40 or x1 > 1040:
                    errs.append(f"板{e['index']} 人物 {e['id']} 水平范围 {x0:.0f}–{x1:.0f} 越出画板 40–1040，会泄漏到相邻画板；缩小 h 或移动 cx")
            if e['kind'] == 'text':
                x1 = e['x'] + _tw(e['str'], e['size'])
                if x1 > 1040:
                    errs.append(f"板{e['index']} 文字「{e['str'][:12]}」右边界 {x1:.0f} 超出 1040；缩小字号或换行")
        if self.PANELS:
            i0 = self.PANELS[0][0]
            heroes0 = [e['at'] for e in self.EV if e['kind'] == 'hero' and e['index'] == i0]
            if not heroes0 or min(heroes0) > .5:
                errs.append(f"开头第 1 块画板（板{i0}）须在 0.5 s 内开始画人（当前 {min(heroes0) if heroes0 else '无人物'}）：短视频前 3 秒是留人时间")
            from .lint import opening_still_gaps
            for a, b in opening_still_gaps(self.EV):
                errs.append(f"开头 0–5 s 内 {a}–{b} s 画面静止 {b - a:.2f} s（上限 1.0 s）：这段时间要画元素、写关键词或圈/标记（见 references/OPENING_SPEC.md）")
        for w in warns: print('版面警告：', w)
        if errs:
            print('版面自检未通过（下面每一条都是会出现在成片里的错误，改完再生成）：')
            for e in errs: print('  ✗', e)
            raise SystemExit(1)
        (self.P / out).write_text(json.dumps(spec, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        rhythm = panel_rhythm_report(self.EV, scenes)
        rhythm_path = self.P / 'qc' / 'panel-rhythm.json'
        rhythm_path.parent.mkdir(parents=True, exist_ok=True)
        rhythm_path.write_text(json.dumps(rhythm, ensure_ascii=False, indent=2), encoding='utf-8')
        report = [f'events {len(self.EV)}  duration {dur}  panels {len(scenes)}']
        for sc in scenes:
            evs = [e for e in self.EV if e['index'] == sc['index']]
            last = max(e['at'] + e['dur'] for e in evs); first = min(e['at'] for e in evs)
            flag = '  <<< 超出本块窗口' if last > sc['end'] - .3 and sc is not scenes[-1] else ''
            metrics = next(row for row in rhythm if row['index'] == sc['index'])
            report.append(f"{sc['index']:>2} {sc['id']:<12} 窗口 {sc['start']:6.2f}–{sc['end']:6.2f}  事件 {first:6.2f}–{last:6.2f}  板长 {metrics['duration']:.2f}s  最长无笔画 {metrics['longest_still_gap']:.2f}s{flag}")
        print('\n'.join(report))
        return spec
