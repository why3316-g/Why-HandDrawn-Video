"""用户审核图的相对轮廓和笔压；生成可随文字伸缩的逐笔圈线。"""
import math

# 从右侧开始、顺时针 32 个采样。保留审核图的倾斜、不对称轮廓和笔压变化。
_SHAPES = {
    'key': ([.930,.888,.849,.818,.803,.804,.823,.855,.908,.975,1.037,1.083,1.096,1.067,1.024,.971,.922,.880,.854,.821,.814,.798,.804,.795,.828,.875,.928,.978,1.016,1.028,1.009,.972],
            [16.2,13.5,11,9.1,7.9,7.8,8.1,9.1,11.2,13.5,19.8,24.1,22.9,13.3,9.6,11.3,14,14.7,13.7,12.7,12.6,11.9,11.2,6.9,7.8,8.8,10.1,11.6,12.7,12.1,12.3,14]),
    'normal': ([.934,.895,.863,.840,.829,.835,.857,.897,.953,1.027,1.103,1.150,1.135,1.062,1.019,.975,.926,.888,.860,.844,.842,.853,.879,.919,.969,1.025,1.080,1.110,1.144,1.097,1.037,.982],
               [3.9,3.7,3.1,2.6,2.4,2.4,2.5,2.8,3.4,4.3,5.2,7,8.5,7.9,7.9,5.7,5.9,5.1,4.1,3.5,3,3,3,3.2,3.4,4,3.3,1.9,2.3,3,3.4,3.8]),
    'special': ([.912,.869,.835,.797,.773,.774,.791,.826,.870,.913,.953,.960,.954,.952,.939,.940,.941,.949,.961,.971,1.031,.870,.884,.904,.961,.984,1.023,1.048,1.053,1.012,.988,.950],
                [16,14,8.1,5.6,4.2,5.9,8,10.9,13.7,18.6,23.7,23.9,21.3,23.3,20.7,17.8,20.4,19.7,12.9,2.7,1,1,1,1.6,2.1,2.5,1.8,1.1,1.2,2,5.2,10.2]),
}


def _sample(values, angle):
    n = len(values)
    pos = (angle % (2 * math.pi)) * n / (2 * math.pi) - .5
    k = math.floor(pos)
    f = pos - k
    return values[k % n] * (1 - f) + values[(k + 1) % n] * f


def ring_geometry(width, size, style='normal'):
    """返回文字左端/基线坐标系下的 (中心轨迹, 逐点笔宽, 细回笔, 干刷标记)。"""
    if style not in _SHAPES:
        raise ValueError('圈画 style 只能是 normal、key 或 special')
    shape, pressure = _SHAPES[style]
    start = {'key': 4.05, 'normal': 5.35, 'special': 4.34}[style]
    sweep = {'key': 2 * math.pi * 1.02, 'normal': 2 * math.pi * .98,
             'special': 2 * math.pi * .965}[style]
    count = 201
    angles = [start + sweep * i / (count - 1) for i in range(count)]
    # 02 原图的左下回笔是两条细线，采样面积不应被误当成一根粗线。
    multiplier = .72 if style == 'normal' else 1
    widths = [max(.45, size * _sample(pressure, a) / 85 * multiplier) for a in angles]
    if style == 'key':
        for i in range(count - 12, count):
            widths[i] *= .2 + .8 * (count - 1 - i) / 11
    rx, ry = width / 2 + size * 1.05, size * 1.06

    def generate():
        return [(width / 2 + rx * _sample(shape, a) * math.cos(a),
                 -size * .35 + ry * _sample(shape, a) * math.sin(a)) for a in angles]

    for _ in range(120):
        points = generate()
        unsafe = False
        for i in range(count - 1):
            for f in (0, .5, 1):
                x = points[i][0] * (1 - f) + points[i + 1][0] * f
                y = points[i][1] * (1 - f) + points[i + 1][1] * f
                pad = max(widths[i], widths[i + 1]) / 2 + size * .025
                if -pad < x < width + pad and -size * .82 - pad < y < size * .12 + pad:
                    unsafe = True
                    break
            if unsafe:
                break
        if not unsafe:
            break
        rx *= 1.025
        ry *= 1.025
    else:
        raise ValueError('圈线无法安全避开文字，请调整版面')

    details = []
    if style == 'key':
        # 审核图左上角的两条细长甩笔：与主轨迹同步，向右上方逐渐抬笔。
        last = 24
        lengths = [0.0]
        for p, q in zip(points, points[1:]):
            lengths.append(lengths[-1] + math.hypot(q[0] - p[0], q[1] - p[1]))
        for extra in (.04, .085):
            detail = []
            for i in range(last + 1):
                f = i / last
                detail.append((points[i][0] + size * .22 * f,
                               points[i][1] - size * (.20 + extra) * f))
            details.append((detail, max(.6, size * .018), 0, lengths[last] / lengths[-1]))
    elif style == 'normal':
        chosen = [i for i, a in enumerate(angles) if 1.95 <= a % (2 * math.pi) <= 2.85]
        if len(chosen) > 1:
            first, last = chosen[0], chosen[-1]
            lengths = [0.0]
            for p, q in zip(points, points[1:]):
                lengths.append(lengths[-1] + math.hypot(q[0] - p[0], q[1] - p[1]))
            detail = []
            for i in range(first, last + 1):
                dx, dy = points[i][0] - width / 2, points[i][1] + size * .35
                norm = max(math.hypot(dx, dy), 1)
                detail.append((points[i][0] + dx / norm * size * .04,
                               points[i][1] + dy / norm * size * .04))
            details.append((detail, max(.7, size * .022), lengths[first] / lengths[-1], lengths[last] / lengths[-1]))
    return points, widths, details, style == 'special'
