"""手与笔素材池：竖屏成片唯一的手/笔来源（2026-10-26 用户定稿）。

规则
- 池目录：<skill>/assets/hands/hand-pool-v01/；只取该目录**根下**的 PNG，不递归、不进任何子目录（备用图另存工作区归档）。
- 一片一双手：每个新项目随机取一张，全片从第一笔到最后一笔用同一张，不在片中换手。
- 轮着用：最近用过的顺序记在 <工作区>/assets/hand-usage.json，取图时把"本轮还没用过的之外的"排除，
  当前池内 3 张为 3 支片一轮、顺序随机（数量按池内有效 PNG 自动计算）；池里只剩一张时直接用那张。
- 新增图片：直接丢进池目录 → `python scripts/hand_pool.py --sync` 自动量笔尖、写清单 → 之后自动参与随机。
- 新图必须与当前已通过的素材同构图：透明底、笔尖朝左上、袖口朝右下（前臂与水平线 45°±12°）、
  只有一只手一支笔、画布约 1100–1550 px。
  构图不同（笔尖不在左上角、多手多笔、白底不透明）时，要在清单里手写 tip/scale，或另开 pool。
- 角度口径（2026-10-26 用户定 A 方案）：**固定 45°，不按素材原角**。渲染时把每张图绕笔尖旋到 45°，
  转幅 = |45° − 实测手臂轴|；>12° 报警、>15° 拒绝入片（此时袖口会被甩离画面，应重生成）。
- 竖屏与宽屏同一套（同日定稿）：宽屏也用本池，缩放走 `scale_landscape`（等效原 .18@1254²，视觉大小不变）。
- 袖口不延伸（用户定稿）：图片什么样就什么样，`sleeve` 恒为 null，不画袖管延伸到右下角；
  只有旧线稿手 `marker-hand-v02.png` 保留它的袖口遮挡线。

用法
  python scripts/hand_pool.py --list                 列出池内图片与参数
  python scripts/hand_pool.py --pick --workspace <ws> 按规则随机挑一张（只打印，不安装）
  python scripts/hand_pool.py --sync                 量尺寸/重算哈希并重写 hand-pool-v01.json
"""
import argparse
import hashlib
import json
import math
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

SKILL = Path(__file__).resolve().parents[1]
POOL_REL = Path('assets/hands/hand-pool-v01')
POOL_NAME = 'hand-pool-v01'
MANIFEST = 'hand-pool-v01.json'
BASELINE = 0.34 * math.hypot(1254, 1254)      # 样板 marker-hand-v02：1254² 对角、批准缩放 .34（竖屏）
LANDSCAPE_BASELINE = 0.18 * math.hypot(1254, 1254)   # 宽屏基准：批准缩放 .18@1254²，换成任意素材的等效缩放
ARM_TARGET = 45.0                            # 手臂（袖口方向）统一归一到右下 45°，见 HAND_POOL.md
ROT_WARN = 12.0                              # 转幅超过 12°：可用但报警，建议重生成
ROT_MAX = 15.0                               # 转幅超过 15°：拒绝入池（袖口会被甩出画面或压住人物）
USAGE = Path('assets/hand-usage.json')


def rotation_check(entry):
    """转幅质检门（2026-10-26 用户定 A 方案：固定 45°，不按素材原角）。
    返回 (level, msg)，level ∈ ok / warn / reject。转幅 = |45° − 素材实测手臂轴|。"""
    r = abs(float(entry.get('rotation') or 0.0))
    arm = entry.get('arm_angle')
    tail = f'（素材原角 {arm}°）' if arm is not None else ''
    if r > ROT_MAX:
        return 'reject', f'转幅 {r:.1f}° 超过 {ROT_MAX:.0f}° 上限{tail}：硬转会把手/袖口甩离画面，建议重生成'
    if r > ROT_WARN:
        return 'warn', f'转幅 {r:.1f}° 超过 {ROT_WARN:.0f}° 建议值{tail}：可用，但建议重生成以减小变形'
    return 'ok', ''


def pool_dir(skill=None):
    return (Path(skill) if skill else SKILL) / POOL_REL


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(path):
    """量笔尖、手臂轴向与建议缩放。
    笔尖：不透明像素里 x+y 最小的点（素材统一笔尖朝左上，极值点就是笔尖）。
    手臂轴向：离笔尖最远那 40% 不透明像素的重心方向，即袖口朝哪边。
    旋转：把手臂轴向掰到右下 45° 需要转的角度（正数=顺时针，canvas 约定）。"""
    try:
        import numpy as np
        from PIL import Image
    except ImportError as e:      # 依赖由 env_check.py --install 补齐
        raise SystemExit(f'量手部素材需要 Pillow 与 numpy（{e}）。先运行 scripts/env_check.py --install。')
    im = Image.open(path).convert('RGBA')
    alpha = np.array(im)[:, :, 3]
    ys, xs = np.nonzero(alpha > 128)
    if not len(xs):
        raise ValueError(f'{Path(path).name} 没有不透明像素，不是可用的手部素材')
    i = int((xs + ys).argmin())
    tip = (int(xs[i]), int(ys[i]))
    dist = np.hypot(xs - tip[0], ys - tip[1])
    far = dist > .6 * dist.max()
    cx, cy = float(xs[far].mean()), float(ys[far].mean())
    arm = math.degrees(math.atan2(cy - tip[1], cx - tip[0]))
    return {'size': [im.width, im.height], 'tip': [tip[0], tip[1]],
            'arm_angle': round(arm, 1), 'rotation': round(ARM_TARGET - arm, 1),
            'scale': round(BASELINE / math.hypot(im.width, im.height), 3),
            'scale_landscape': round(LANDSCAPE_BASELINE / math.hypot(im.width, im.height), 3),
            'sleeve': None}


def load_manifest(skill=None):
    f = pool_dir(skill) / MANIFEST
    if f.is_file():
        data = json.loads(f.read_text(encoding='utf-8'))
        if isinstance(data, dict) and isinstance(data.get('images'), list):
            return data
    return {'schema': 1, 'pool': POOL_NAME, 'images': []}


def entries(skill=None):
    """池内可用图片：只取根目录 PNG，跳过 `_` 前缀与子目录。清单里没有的现场量尺。"""
    d = pool_dir(skill)
    known = {e.get('file'): e for e in load_manifest(skill)['images']}
    out = []
    for p in sorted(d.glob('*.png')):
        if p.name.startswith('_') or not p.is_file():
            continue
        e = dict(known.get(p.name) or {})
        if not e.get('tip') or not e.get('size'):
            e.update(measure(p))
        e['file'] = p.name
        e['path'] = str(p)
        e.setdefault('scale', round(BASELINE / math.hypot(*e['size']), 3))
        e.setdefault('scale_landscape', round(LANDSCAPE_BASELINE / math.hypot(*e['size']), 3))
        e.setdefault('rotation', 0.0)      # 缺参数时按素材原姿态（多为 45° 右下），不硬旋 -45°
        e.setdefault('sleeve', None)
        e['gate'], e['gate_msg'] = rotation_check(e)
        e['sha256'] = sha256_of(p)
        out.append(e)
    return out


def last_used(workspace):
    if not workspace:
        return None
    f = Path(workspace) / USAGE
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text(encoding='utf-8')).get('last')
    except Exception:
        return None


def recent_used(workspace, n):
    """最近用过的前 n 张（新的在前）。取图时把这一批排除，保证一轮内不重复——池有 N 张就按 N 张轮用。"""
    if not workspace or n <= 0:
        return []
    f = Path(workspace) / USAGE
    if not f.is_file():
        return []
    try:
        return list(json.loads(f.read_text(encoding='utf-8')).get('history', []))[:n]
    except Exception:
        return []


def record_use(workspace, entry):
    if not workspace:
        return None
    f = Path(workspace) / USAGE
    f.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if f.is_file():
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            data = {}
    history = [h for h in data.get('history', []) if h != entry['file']]
    history.insert(0, entry['file'])
    data.update({'last': entry['file'], 'pool': POOL_NAME, 'updated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                 'history': history[:20], 'history_note': '最近用过的顺序，新的在前'})
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return f


def pick(skill=None, workspace=None, forced=None):
    """一片一双手：在"本轮还没用过"的图里随机取一张。按池内当前有效数量轮用，顺序随机。
    转幅超 15° 的图不参与（硬转会把手甩离画面）；forced 可用全名或前缀（如 03）强制指定。"""
    everything = entries(skill)
    if not everything:
        raise SystemExit(f'手部素材池为空：{pool_dir(skill)}。放 1 张以上透明底 PNG 再建项目。')
    pool = [e for e in everything if e.get('gate') != 'reject']
    if not pool:
        detail = '；'.join(f"{e['file']} {e['gate_msg']}" for e in everything)
        raise SystemExit(f'池内图片转幅全部超限，没有可用的手：{detail}。重生成后再跑 --sync。')
    if forced:
        hit = [e for e in pool if e['file'] == forced] or [e for e in pool if e['file'].startswith(forced)]
        if not hit:
            bad = [e for e in everything if e['file'] == forced or e['file'].startswith(forced)]
            if bad:
                raise SystemExit(f'{forced} 转幅超限，不能入片：{bad[0]["gate_msg"]}')
            raise SystemExit(f'池里没有 {forced}；可选：' + '、'.join(e['file'] for e in pool))
        return hit[0]
    skip = set(recent_used(workspace, len(pool) - 1))
    candidates = [e for e in pool if e['file'] not in skip] or pool
    return random.SystemRandom().choice(candidates)


def install(project, entry):
    """把选中的手装进项目：素材本体 + hand-meta.json（笔尖/缩放/旋转/袖管几何）。"""
    level, msg = rotation_check(entry)
    if level == 'reject':
        raise SystemExit(f'{entry.get("file")} 转幅超限，不能装进项目：{msg}')
    images = Path(project) / 'assets/images'
    images.mkdir(parents=True, exist_ok=True)
    shutil.copy(entry['path'], images / entry['file'])
    meta = {k: entry.get(k) for k in ('file', 'size', 'tip', 'rotation', 'scale', 'scale_landscape', 'sleeve', 'sha256')}
    meta['pool'] = POOL_NAME
    meta['source'] = f'{POOL_REL.as_posix()}/{entry["file"]}'
    meta['note'] = ('手与笔素材；tip=笔尖像素坐标，rotation=把手臂掰到右下 45° 的旋转角（度，顺时针为正），'
                    'scale=竖屏缩放，scale_landscape=宽屏缩放，sleeve=null 表示不画袖管延伸（图片原样）')
    (images / 'hand-meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return meta


def sync(skill=None, bundle=True):
    """量尺寸、重算哈希、重写池清单；池在包内时顺手刷新 BUNDLE_MANIFEST，避免完整性校验误报。"""
    d = pool_dir(skill)
    old = {e.get('file'): e for e in load_manifest(skill)['images']}
    images = []
    for p in sorted(d.glob('*.png')):
        if p.name.startswith('_'):
            continue
        m = measure(p)
        prev = old.get(p.name, {})
        level, _ = rotation_check(m)
        images.append({'file': p.name, 'size': m['size'], 'tip': m['tip'], 'arm_angle': m['arm_angle'],
                       'rotation': m['rotation'], 'gate': level,
                       'scale': prev.get('scale', m['scale']),
                       'scale_landscape': m['scale_landscape'],
                       'sleeve': prev.get('sleeve'),
                       'sha256': sha256_of(p), 'source': prev.get('source', f'{POOL_REL.as_posix()}/{p.name}')})
    data = {'schema': 1, 'pool': POOL_NAME, 'updated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'rule': '只用本目录根下的 PNG；不递归、不用子目录；每片随机一张、全片同一张',
            'baseline': {'reference': 'assets/marker-hand-v02.png', 'scale': 0.34, 'diagonal': 1773,
                         'arm_angle': ARM_TARGET,
                         'gate': {'warn_over': ROT_WARN, 'reject_over': ROT_MAX},
                         'note': f'手臂（袖口）轴向统一归一到右下 {ARM_TARGET:.0f}°，按图实测 rotation；'
                                 f'转幅 >{ROT_WARN:.0f}° 报警、>{ROT_MAX:.0f}° 不入片（见 HAND_POOL.md）'},
            'images': images}
    (d / MANIFEST).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    if bundle and (d.parents[2] / 'BUNDLE_MANIFEST.json').is_file():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import verify_bundle
        verify_bundle.write_manifest(skill or SKILL)
    return images


def main():
    ap = argparse.ArgumentParser(description='手与笔素材池：随机取图、装进项目、维护清单')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--pick', action='store_true')
    ap.add_argument('--sync', action='store_true')
    ap.add_argument('--skill', default=None, help='默认用本脚本所在的包')
    ap.add_argument('--workspace', default=None, help='视频工作区根（读写 hand-usage.json）')
    ap.add_argument('--hand', default=None, help='指定池内文件全名或前缀，跳过随机')
    a = ap.parse_args()
    rc = 0
    if a.sync:
        imgs = sync(a.skill)
        ok = [i for i in imgs if i.get('gate') == 'ok']
        warn = [i for i in imgs if i.get('gate') == 'warn']
        bad = [i for i in imgs if i.get('gate') == 'reject']
        print(f'已同步 {len(imgs)} 张：合格 {len(ok)}、警告 {len(warn)}、不可入片 {len(bad)}')
        for i in warn:
            print('  ! ' + i['file'] + '：' + rotation_check(i)[1])
        for i in bad:
            print('  × ' + i['file'] + '：' + rotation_check(i)[1])
        if bad:
            print(f'有 {len(bad)} 张转幅超过 {ROT_MAX:.0f}°，已拒绝入片；重生成后再 sync。', file=sys.stderr)
            rc = 1
    if a.list or not (a.pick or a.sync):
        for e in entries(a.skill):
            mark = {'ok': ' ', 'warn': '!', 'reject': '×'}[e['gate']]
            print(f"{mark} {e['file']}  {e['size'][0]}×{e['size'][1]}  tip={e['tip']}  "
                  f"手臂={e.get('arm_angle')}°  转={e['rotation']:+.1f}°  scale={e['scale']}")
    if a.pick:
        e = pick(a.skill, a.workspace, a.hand)
        print(json.dumps({k: e[k] for k in ('file', 'tip', 'scale', 'rotation', 'sleeve')}, ensure_ascii=False))
    return rc


if __name__ == '__main__':
    sys.exit(main())
