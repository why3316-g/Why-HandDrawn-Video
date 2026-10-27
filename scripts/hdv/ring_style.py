"""用户选定的三种手写圈线；只生成普通逐笔线事件所需的坐标。"""
import math


def ring_strokes(width, size, style='normal'):
    """返回相对文字左端和基线的 (点列, 笔宽, 时间占比)。"""
    if style not in ('normal', 'key', 'special'):
        raise ValueError("圈画 style 只能是 normal、key 或 special")
    cx, cy = width / 2, -size * .35
    rx, ry = width / 2 + size * 1.20, size * 1.12

    def arc(start, end, count, offset=0):
        result = []
        for i in range(count):
            a = start + (end - start) * i / (count - 1)
            c, s = math.cos(a), math.sin(a)
            # 真实椭圆而非圆角方框；加宽两端为长词留下字角安全余量。
            dx = (rx + offset) * c
            dy = (ry + offset) * s
            result.append((cx + dx, cy + dy - size * .10 * dx / (rx + offset)))
        return result

    # 上右角留出微小开口；所有样式都沿同一个安全外轮廓逐笔画出。
    loop = arc(-1.20, -1.20 + 2 * math.pi * .98, 160)
    if style == 'key':
        return [(loop, max(4, size * .085), .72),
                (arc(.38, 2.82, 65, size * .012), max(5, size * .13), .18),
                (arc(3.65, 4.40, 30, size * .13), max(2, size * .045), .10)]
    if style == 'special':
        return [(loop, max(3, size * .075), .70),
                (arc(.30, 2.92, 65, size * .02), max(3, size * .095), .12),
                (arc(.22, 2.58, 58, size * .075), max(1.0, size * .020), .06),
                (arc(.42, 2.92, 60, size * .13), max(1.0, size * .018), .06),
                (arc(.57, 2.74, 54, size * .19), max(1.0, size * .014), .06)]
    return [(loop, max(2, size * .05), .84),
            (arc(1.82, 2.80, 32, size * .045), max(1.5, size * .028), .16)]
