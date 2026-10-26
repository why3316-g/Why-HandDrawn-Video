"""手与笔素材池：竖屏成片唯一的手/笔来源（2026-10-26 用户定稿）。

规则
- 池目录：<skill>/assets/hands/hand-pool-v01/；只取该目录**根下**的 PNG，不递归、不进任何子目录（备用图另存工作区归档）。
- 一片一双手：每个新项目随机取一张，全片从第一笔到最后一笔用同一张，不在片中换手。
- 尽量不连着重复：上一次用过的手记在 <工作区>/assets/hand-usage.json，随机时避开它（池里只剩一张时除外）。
- 新增图片：直接丢进池目录 → `python scripts/hand_pool.py --sync` 自动量笔尖、写清单 → 之后自动参与随机。
- 新图必须与现有 8 张同构图：透明底、笔尖朝左上、袖口朝右下、只有一只手一支笔、画布约 1100–1550 px。
  构图不同（笔尖不在左上角、多手多笔、白底不透明）时，要在清单里手写 tip/scale，或另开 pool。

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
BASELINE = 0.34 * math.hypot(1254, 1254)      # 样板 marker-hand-v02：1254² 对角、批准缩放 .34
USAGE = Path('assets/hand-usage.json')


def pool_dir(skill=None):
    return (Path(skill) if skill else SKILL) / POOL_REL


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(path):
    """量笔尖与建议缩放。笔尖取不透明像素里 x+y 最小的点：素材统一笔尖朝左上，极值点就是笔尖。"""
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
    diag = math.hypot(im.width, im.height)
    return {'size': [im.width, im.height], 'tip': [int(xs[i]), int(ys[i])],
            'scale': round(BASELINE / diag, 3), 'sleeve': None}


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
        e.setdefault('sleeve', None)
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
    """一片一双手：随机取一张，避开上一次用过的那张。forced 可用全名或前缀（如 03）。"""
    pool = entries(skill)
    if not pool:
        raise SystemExit(f'手部素材池为空：{pool_dir(skill)}。放 1 张以上透明底 PNG 再建项目。')
    if forced:
        hit = [e for e in pool if e['file'] == forced] or [e for e in pool if e['file'].startswith(forced)]
        if not hit:
            raise SystemExit(f'池里没有 {forced}；可选：' + '、'.join(e['file'] for e in pool))
        return hit[0]
    skip = last_used(workspace)
    candidates = [e for e in pool if e['file'] != skip] or pool
    return random.SystemRandom().choice(candidates)


def install(project, entry):
    """把选中的手装进项目：素材本体 + hand-meta.json（笔尖/缩放/袖管几何）。"""
    images = Path(project) / 'assets/images'
    images.mkdir(parents=True, exist_ok=True)
    shutil.copy(entry['path'], images / entry['file'])
    meta = {k: entry.get(k) for k in ('file', 'size', 'tip', 'scale', 'sleeve', 'sha256')}
    meta['pool'] = POOL_NAME
    meta['source'] = f'{POOL_REL.as_posix()}/{entry["file"]}'
    meta['note'] = '手与笔素材；tip 是笔尖像素坐标，scale 为竖屏缩放，sleeve=null 表示不画袖管延伸（彩色素材自带袖口）'
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
        images.append({'file': p.name, 'size': m['size'], 'tip': m['tip'],
                       'scale': prev.get('scale', m['scale']), 'sleeve': prev.get('sleeve'),
                       'sha256': sha256_of(p), 'source': prev.get('source', f'{POOL_REL.as_posix()}/{p.name}')})
    data = {'schema': 1, 'pool': POOL_NAME, 'updated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'rule': '只用本目录根下的 PNG；不递归、不用子目录；每片随机一张、全片同一张',
            'baseline': {'reference': 'assets/marker-hand-v02.png', 'scale': 0.34, 'diagonal': 1773},
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
    if a.sync:
        imgs = sync(a.skill)
        print(f'已同步 {len(imgs)} 张：' + '、'.join(i['file'] for i in imgs))
    if a.list or not (a.pick or a.sync):
        for e in entries(a.skill):
            print(f"{e['file']}  {e['size'][0]}×{e['size'][1]}  tip={e['tip']}  scale={e['scale']}")
    if a.pick:
        e = pick(a.skill, a.workspace, a.hand)
        print(json.dumps({k: e[k] for k in ('file', 'tip', 'scale', 'sleeve')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
