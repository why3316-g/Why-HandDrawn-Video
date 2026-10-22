"""同一手绘语法的画幅配置；事件表、封面和像素检查共用，旧项目默认竖屏。"""
from copy import deepcopy
import json
from pathlib import Path

_LAYOUTS = {
    'portrait': {
        'mode': 'portrait', 'width': 1080, 'height': 1920, 'panel_width': 1120,
        'content_top': 285, 'content_bottom': 1455, 'text_bounds': [40, 285, 1040, 1425],
        'separator_y': 1430, 'separator_x': [120, 925], 'clock': [932, 322, 24],
        'opening_bottom': 1430, 'opening_clock_mask': [870, 285, 1005, 370],
        'caption_top': 1438, 'caption_height': 80, 'caption_baseline': 1494,
        'caption_size': 52, 'caption_small_size': 48,
        'header_x': 85, 'header_first_y': [245, 308], 'header_other_y': 250,
        'pen_enter_x': 1280, 'pen_enter_bottom': 1350,
    },
    'landscape': {
        'mode': 'landscape', 'width': 1920, 'height': 1080, 'panel_width': 1960,
        'content_top': 190, 'content_bottom': 900, 'text_bounds': [80, 190, 1840, 890],
        'separator_y': 920, 'separator_x': [120, 1800], 'clock': [1772, 162, 24],
        'opening_bottom': 900, 'opening_clock_mask': [1710, 125, 1845, 190],
        'caption_top': 930, 'caption_height': 80, 'caption_baseline': 986,
        'caption_size': 52, 'caption_small_size': 48,
        'header_x': 85, 'header_first_y': [105, 162], 'header_other_y': 110,
        'pen_enter_x': 2120, 'pen_enter_bottom': 860,
    },
}


def get_layout(mode='portrait'):
    if mode not in _LAYOUTS:
        raise ValueError(f'未知画幅模式 {mode!r}；请选择 portrait 或 landscape。')
    return deepcopy(_LAYOUTS[mode])


def project_layout(project):
    path = Path(project) / 'design/config.json'
    cfg = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    return get_layout(cfg.get('mode', 'portrait'))


def validate_spec_layout(spec, layout):
    """旧 spec 只允许无 layout 的竖屏；宽屏必须携带实际布局。"""
    if (spec.get('width'), spec.get('height')) != (layout['width'], layout['height']):
        raise ValueError('spec 尺寸与项目 mode 不一致，请重建事件表，不要拉伸画面。')
    declared = spec.get('data', {}).get('layout')
    if declared is None:
        if layout['mode'] != 'portrait':
            raise ValueError('宽屏 spec 缺少 data.layout，请重建事件表。')
    elif declared != layout:
        raise ValueError('spec 的布局与项目模式不一致，请重建事件表。')
