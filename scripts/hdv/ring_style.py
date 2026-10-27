"""用户定稿的两款原笔迹：02 常规、03 关键结论；项目内自包含。"""
import hashlib
import json
import math
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[2] / 'assets/ring-styles'
if not ASSETS.is_dir():
    ASSETS = Path(__file__).resolve().parents[2] / 'assets/images/ring-styles'


def ring_reference(width, size, style='normal', assets=None):
    """返回相对文字左端/基线的原图框及笔尖；special 仅兼容为 03。"""
    style = 'key' if style == 'special' else style
    if style not in ('normal', 'key'):
        raise ValueError('圈画仅支持 normal（02 常规）与 key（03 关键结论）；01 已停用')
    if not all(math.isfinite(v) and v > 0 for v in (width, size)):
        raise ValueError('圈画文字宽度与字号必须为正数')
    assets = Path(assets) if assets is not None else ASSETS
    guide_file = assets / 'ring-guides.json'
    if not guide_file.is_file():
        raise FileNotFoundError('缺少已审核圈画轨迹，请恢复完整随包 assets/ring-styles')
    data = json.loads(guide_file.read_text(encoding='utf-8'))[style]
    filename = 'ring-02.svg' if style == 'normal' else 'ring-03.svg'
    source = assets / filename
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != data['sha256']:
        raise ValueError('已审核圈画素材缺失或被替换：' + filename)
    sy = size / 80
    sx = max((width + (data['width'] - 320) * sy) / data['width'], width / 320)
    # 长词保持参考图的相对留白，避免横向拉长后圈线从两侧压进字框。
    asymmetry = data['text_left'] - (data['width'] - 320) / 2
    x, y = (width - data['width'] * sx) / 2 - asymmetry * sy, -data['baseline'] * sy
    points = [(x + px * sx, y + py * sy) for px, py in data['points']]
    return {'style': style, 'file': filename, 'start': data['start'],
            'box': [x, y, data['width'] * sx, data['height'] * sy], 'points': points}


def ring_asset_cues(events, project):
    """输出实际预加载入口；缺项目素材则拒绝构建，不引用安装目录或临时文件。"""
    cues = []
    for style in sorted({e['ringAsset'] for e in events if e.get('ringAsset')}):
        asset = ring_reference(320, 80, style, Path(project) / 'assets/images/ring-styles')
        cues.append({'at': 0, 'kind': 'ring_reference',
                     'image': '../assets/images/ring-styles/' + asset['file'],
                     'data': {'style': style}})
    return cues
