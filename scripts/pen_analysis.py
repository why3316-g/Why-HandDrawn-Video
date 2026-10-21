"""骨架 → 笔画路径。函数原样取自 Codex 在小凯项目写的 analyze_A_strokes.py（本工作区自有实现，不是花叔 Skill；见 references/PROVENANCE.md）。
skeleton：Zhang-Suen 细化（最多 80 轮）；simplify：Douglas-Peucker；paths_from：沿骨架连成路径；order：按上中下四个竖向分区、就近接笔排序。
只做数值分析，不修改任何图片像素。"""
import math
import numpy as np


def skeleton(a):
    a = np.pad(a.astype(bool), 1)
    for iteration in range(80):
        count = 0
        for step in (0, 1):
            v = [a[:-2, 1:-1], a[:-2, 2:], a[1:-1, 2:], a[2:, 2:], a[2:, 1:-1], a[2:, :-2], a[1:-1, :-2], a[:-2, :-2]]
            n = np.stack(v).sum(axis=0)
            crossings = np.stack([(~v[i]) & v[(i + 1) % 8] for i in range(8)]).sum(axis=0)
            remove = a[1:-1, 1:-1] & (n >= 2) & (n <= 6) & (crossings == 1)
            if step == 0:
                remove &= ~(v[0] & v[2] & v[4]) & ~(v[2] & v[4] & v[6])
            else:
                remove &= ~(v[0] & v[2] & v[6]) & ~(v[0] & v[4] & v[6])
            count += int(remove.sum())
            a[1:-1, 1:-1][remove] = False
        if not count:
            break
    return a[1:-1, 1:-1]


def simplify(points, tolerance=1.0):
    if len(points) <= 2:
        return points
    a, b = np.array(points[0]), np.array(points[-1])
    vec = b - a
    q = np.array(points)
    length = float(vec @ vec)
    t = np.clip((q - a) @ vec / max(length, 1e-9), 0, 1)
    distances = np.linalg.norm(q - (a + t[:, None] * vec), axis=1)
    at = int(distances.argmax())
    if distances[at] <= tolerance:
        return [points[0], points[-1]]
    return simplify(points[:at + 1], tolerance)[:-1] + simplify(points[at:], tolerance)


def paths_from(skel):
    yy, xx = np.nonzero(skel)
    pixels = set(zip(xx.tolist(), yy.tolist()))
    dirs = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
    neighbors = {pt: [(pt[0] + dx, pt[1] + dy) for dx, dy in dirs if (pt[0] + dx, pt[1] + dy) in pixels] for pt in pixels}
    used = set()
    paths = []
    starts = sorted(pixels, key=lambda pt: (len(neighbors[pt]) == 2, pt[1], pt[0]))

    def key(a, b):
        return tuple(sorted((a, b)))
    for a in starts:
        for b in neighbors[a]:
            if key(a, b) in used:
                continue
            points = [a, b]
            used.add(key(a, b))
            previous, current = a, b
            while len(neighbors[current]) == 2:
                nxt = next(q for q in neighbors[current] if q != previous)
                if key(current, nxt) in used:
                    break
                used.add(key(current, nxt))
                points.append(nxt)
                previous, current = current, nxt
            length = sum(math.dist(points[i - 1], points[i]) for i in range(1, len(points)))
            if length >= 3:
                paths.append(simplify(points))
    return paths


def order(paths, height):
    remaining = list(paths)
    out = []
    last = (height * .25, 0)
    for zone in range(4):
        band = [q for q in remaining if min(3, int(np.mean([pt[1] for pt in q]) / height * 4)) == zone]
        while band:
            best = min(range(len(band)), key=lambda i: min(math.dist(last, band[i][0]), math.dist(last, band[i][-1])))
            q = band.pop(best)
            if math.dist(last, q[-1]) < math.dist(last, q[0]):
                q = q[::-1]
            out.append(q)
            last = q[-1]
    return out
