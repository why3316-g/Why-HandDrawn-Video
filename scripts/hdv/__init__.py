"""Why-HandDrawn-Video 项目内库：音频时钟 + 事件表 DSL + 字幕断句。new_project.py 会把本包整份复制到项目的 design/hdv/，项目从此自包含。"""
from .clock import Clock
from .dsl import Film, INK, OR
from .captions import captions_from_breaks

__all__ = ['Clock', 'Film', 'INK', 'OR', 'captions_from_breaks']
