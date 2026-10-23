"""版面自检（事件表生成时自动运行，有错就拒绝输出 spec）。
背景：2026-10-12 小彬片里 "第一""小棋王" 的橙色圈圈整个落在字下面、没圈住字——手写坐标时把 text 的 y 当成了字的顶部，其实 y 是基线。
规则（文字包围盒：x..x+宽，y-0.82*size..y+0.12*size；CJK 字宽=字号，ASCII 字宽=0.55*字号）：
  错误：圈（ring）没有把它圈的字完整圈住；线条穿过任一文字内部（含擦过圈）；两段文字包围盒重叠；文字出界（左右 40px、上 285、下 1425）。
  警告：未标记的椭圆线与文字部分重叠（疑似手写坐标圈字没圈住）。
圈字一律用 Film.ring()，不要手写 ell 坐标去圈字。"""
import math


def text_w(s, size):
    return sum(size if ord(c) > 255 else size * .55 for c in s)


def tbox(e):
    w = text_w(e['str'], e['size'])
    return (e['x'], e['y'] - e['size'] * .82, e['x'] + w, e['y'] + e['size'] * .12)


def _inter(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0, w) * max(0, h)


def _area(a): return max(1e-9, (a[2] - a[0]) * (a[3] - a[1]))


def _pts(e, step=6):
    p = e['p']; out = []
    for (x0, y0), (x1, y1) in zip(p, p[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
        out += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n)]
    out.append(tuple(p[-1]))
    return out


def lint(events, panels=None, layout=None):
    from .layout import get_layout
    layout = layout or get_layout()
    left, top, right, bottom = layout['text_bounds']
    errs, warns = [], []
    by = {}
    for e in events: by.setdefault(e['index'], []).append(e)
    for i, evs in sorted(by.items()):
        texts = [e for e in evs if e['kind'] == 'text']
        lines = [e for e in evs if e['kind'] == 'line']
        tb = [(t, tbox(t)) for t in texts]
        for t, b in tb:
            if b[0] < left or b[2] > right or b[1] < top or b[3] > bottom:
                errs.append(f'板{i} 文字出界/压字幕带：「{t["str"]}」包围盒 x{b[0]:.0f}-{b[2]:.0f} y{b[1]:.0f}-{b[3]:.0f}')
        for a in range(len(tb)):
            for c in range(a + 1, len(tb)):
                A, B = tb[a][1], tb[c][1]
                if _inter(A, B) > 0:
                    errs.append(f'板{i} 文字重叠：「{tb[a][0]["str"]}」与「{tb[c][0]["str"]}」')
                elif min(A[2], B[2]) > max(A[0], B[0]) and 0 <= max(A[1], B[1]) - min(A[3], B[3]) < 6:
                    warns.append(f'板{i} 行距过紧：「{tb[a][0]["str"]}」与「{tb[c][0]["str"]}」上下只隔 {max(A[1], B[1]) - min(A[3], B[3]):.0f}px，读起来会黏在一起')
        for ln in lines:
            pts = _pts(ln)
            tag = ln.get('tag') or ''
            xs = [p[0] for p in ln['p']]; ys = [p[1] for p in ln['p']]
            lb = (min(xs), min(ys), max(xs), max(ys))
            if layout['mode'] == 'landscape' and (lb[0] < left or lb[2] > right or lb[1] < layout['content_top'] or lb[3] > layout['content_bottom']):
                errs.append(f'板{i} 线条越出宽屏画板，会被裁切')
            if tag.startswith('ring:'):
                s = tag[5:]
                tgt = [b for t, b in tb if t['str'] == s]
                if not tgt:
                    errs.append(f'板{i} 圈的文字「{s}」不在这块画板上'); continue
                b = tgt[0]
                if not (lb[0] <= b[0] and lb[1] <= b[1] and lb[2] >= b[2] and lb[3] >= b[3]):
                    errs.append(f'板{i} 圈没有圈住「{s}」：圈 x{lb[0]:.0f}-{lb[2]:.0f} y{lb[1]:.0f}-{lb[3]:.0f}，字 x{b[0]:.0f}-{b[2]:.0f} y{b[1]:.0f}-{b[3]:.0f}')
                pad = lambda q, d: (q[0] + d, q[1] + d, q[2] - d, q[3] - d)
                inner = pad(b, min(6, (b[3] - b[1]) * .05))
                if any(inner[0] <= x <= inner[2] and inner[1] <= y <= inner[3] for x, y in pts):
                    errs.append(f'板{i} 圈的线擦到了「{s}」')
                continue
            for t, b in tb:
                inner = (b[0] + (b[2] - b[0]) * .08, b[1] + (b[3] - b[1]) * .2, b[2] - (b[2] - b[0]) * .08, b[3] - (b[3] - b[1]) * .2)
                hit = sum(1 for x, y in pts if inner[0] <= x <= inner[2] and inner[1] <= y <= inner[3])
                if hit >= 2 and not (tag == 'pop' and lb[0] <= b[0] and lb[1] <= b[1] and lb[2] >= b[2] and lb[3] >= b[3]):
                    errs.append(f'板{i} 线条穿过文字「{t["str"]}」（线 x{lb[0]:.0f}-{lb[2]:.0f} y{lb[1]:.0f}-{lb[3]:.0f}）')
                elif len(ln['p']) >= 40 and tag != 'pop' and 0.03 < _inter(lb, b) / _area(b) < .97:
                    warns.append(f'板{i} 疑似圈字没圈住：椭圆线与「{t["str"]}」部分重叠，请改用 ring()')
    return errs, warns


def opening_still_gaps(events, window=5.0, max_still=1.0, min_dur=.2):
    """开头静止检查（2026-10-14 新增，规范见 references/OPENING_SPEC.md）：
    返回 [(起, 止)]：0–window 秒内"没有任何有效绘制事件"且长度 > max_still 的静止段。
    有效绘制事件 = 人物笔画、文字、圈/叉/勾/箭头、道具线条等 dur ≥ min_dur 的事件。
    字幕、标题栏、小时钟、镜头平移不算动画（它们不在事件表里，也不应被当作画面在动）。"""
    iv = sorted((max(0.0, e['at']), min(window, e['at'] + e['dur'])) for e in events if e['at'] < window and e['dur'] >= min_dur and e['kind']!='media')
    gaps, cur = [], 0.0
    for a, b in iv:
        if a - cur > max_still + 1e-9:
            gaps.append((round(cur, 2), round(a, 2)))
        cur = max(cur, b)
    if window - cur > max_still + 1e-9:
        gaps.append((round(cur, 2), window))
    return gaps


def panel_rhythm_report(events, scenes, min_dur=.2):
    """逐板时长、有效绘制区间和最长无新笔画空档。"""
    report = []
    for scene in scenes:
        start, end, index = float(scene['start']), float(scene['end']), scene['index']
        intervals = sorted(
            (max(start, float(e['at'])), min(end, float(e['at']) + float(e['dur'])))
            for e in events
            if e.get('index') == index and float(e.get('dur', 0)) >= min_dur
            and e.get('kind') != 'media'
            and float(e['at']) < end and float(e['at']) + float(e['dur']) > start
        )
        cur = start
        gaps = []
        for a, b in intervals:
            if a - cur > 1e-9:
                gaps.append((cur, a))
            cur = max(cur, b)
        if end - cur > 1e-9:
            gaps.append((cur, end))
        longest = max(gaps, key=lambda gap: gap[1] - gap[0], default=(start, start))
        report.append({
            'index': index, 'id': scene.get('id', ''),
            'start': round(start, 3), 'end': round(end, 3), 'duration': round(end - start, 3),
            'longest_still_gap': round(longest[1] - longest[0], 3),
            'gap_start': round(longest[0], 3), 'gap_end': round(longest[1], 3),
        })
    return report


def panel_exit_issues(events, scenes, pan_lead=.5, tolerance=.2):
    """画完再走镜头（2026-10-21 新增）：渲染器在下一块画板起点前 pan_lead 秒开始平移离开本板，
    本板最后一笔最晚在平移开始后 tolerance 秒内画完，否则观众看不到写完的字/符号。
    最后一块画板没有离场平移，不检查。旧版只在时间审查表里提示"超出本块窗口"（容许拖到平移后 0.7 s），
    导致独立审片在成片阶段反复挑出"写完时已在平移"而返工。"""
    issues = []
    for scene in scenes[:-1]:
        index, name = scene['index'], scene.get('id', '')
        pan = float(scene['end']) - pan_lead
        late = [e for e in events if e.get('index') == index and float(e['at']) + float(e['dur']) > pan + tolerance + 1e-9]
        if late:
            worst = max(late, key=lambda e: float(e['at']) + float(e['dur']))
            end = float(worst['at']) + float(worst['dur'])
            what = worst.get('str') or worst.get('id') or worst.get('tag') or worst['kind']
            issues.append(f"板{index} {name} 「{str(what)[:12]}」{end:.2f}s 才画完，镜头 {pan:.2f}s 已开始离开本板（最晚 {pan + tolerance:.2f}s）：提前起笔、缩短 dur 或删掉这笔")
    return issues


def panel_rhythm_issues(events, scenes, max_duration=8.0, max_still=4.0, min_dur=.2, min_duration=2.5):
    """逐板节奏硬检查：画板最短 2.5 秒（2026-10-21 新增：去掉镜头进出 0.9 秒后只剩约 1.6 秒可看）、最长 8 秒，板内无有效新笔画的空档最多 4 秒。"""
    issues = []
    for row in panel_rhythm_report(events, scenes, min_dur):
        index, name = row['index'], row['id']
        if row['duration'] < min_duration - 1e-9:
            issues.append(f"板{index} {name} 时长 {row['duration']:.2f}s，短于 {min_duration:.1f}s：并入前后相邻画板（合并后超 8 秒就换个语义转折点重切）")
        if row['duration'] > max_duration + 1e-9:
            issues.append(f"板{index} {name} 时长 {row['duration']:.2f}s，超过 {max_duration:.1f}s")
        if row['longest_still_gap'] > max_still + 1e-9:
            issues.append(f"板{index} {name} 在 {row['gap_start']:.2f}–{row['gap_end']:.2f}s 无有效新笔画，空档 {row['longest_still_gap']:.2f}s")
    return issues
