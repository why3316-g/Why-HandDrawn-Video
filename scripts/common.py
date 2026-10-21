"""只从本包定位制作资源；工作区允许覆盖音频库，浏览器仍是本机运行依赖。"""
import json, os, shutil, sys
from pathlib import Path

HOME = Path.home()
SKILL = Path(__file__).resolve().parents[1]


def find_huashu():
    """兼容旧函数名，只返回内嵌快照；从不回退到其他 Skill 或环境变量。"""
    bundled = SKILL / 'upstream/huashu-art-motion'
    return bundled if (bundled / 'scripts/engine/render.py').is_file() else None


def find_story_visuals(workspace=None):
    return SKILL if (SKILL / 'scripts/check_visual_manifest.py').is_file() else None


def find_workspace(start):
    """识别单包初始化的工作区，也兼容原工作区。"""
    p = Path(start).resolve()
    for q in [p] + list(p.parents):
        if (q / '.hdv-workspace.json').is_file():
            return q
        if (q / 'CLAUDE.md').is_file() and ((q / 'assets').is_dir() or (q / '固定素材').is_dir()):
            return q
    return None


def find_library(start):
    if os.environ.get('HDV_LIBRARY'):
        return Path(os.environ['HDV_LIBRARY'])
    ws = find_workspace(start)
    local = ws / 'assets/audio-library' if ws else None
    if local and (local / 'bgm').is_dir() and any((local / 'bgm').glob('*')):
        return local
    return SKILL / 'assets/audio-library'


def companion_references(workspace=None):
    local = Path(workspace) / 'assets/characters/companion-references-v01' if workspace else None
    expected = ['01-线上-书桌手机通话.png', '02-线上-床边手机通话.png', '03-线上-家庭共看手机.png',
                '04-线下-倾听青少年.png', '05-线下-倾听家长.png']
    if local and all((local / name).is_file() for name in expected):
        return local
    return SKILL / 'assets/characters/companion-references-v01'


def brand_logo(workspace=None):
    local = Path(workspace) / 'assets/brand/companion-logo-reference-v01.png' if workspace else None
    return local if local and local.is_file() else SKILL / 'assets/brand/companion-logo-reference-v01.png'


def audio_config_status(path):
    """仅返回配置结论，不回传或输出私人值；与全文入口使用同一 JSON 字符串格式。"""
    if not path or not Path(path).is_file():
        return False, '未配置本机火山凭证文件'
    values = {}
    try:
        for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
            if '=' not in line or line.lstrip().startswith('#'):
                continue
            key, value = line.split('=', 1)
            if key.strip() in ('DOUBAO_SPEECH_API_KEY', 'DOUBAO_SPEECH_VOICE_TYPE'):
                values[key.strip()] = json.loads(value.strip())
    except (ValueError, OSError):
        return False, '配置不可读取或不是示例要求的 JSON 双引号格式'
    key = values.get('DOUBAO_SPEECH_API_KEY')
    if not isinstance(key, str) or not key.strip() or any(word in key.lower() for word in ('填写', 'your-key', 'placeholder', 'dummy', 'example')):
        return False, '密钥缺失、为空或仍是示例占位符'
    if values.get('DOUBAO_SPEECH_VOICE_TYPE') not in ('zh_male_dayi_uranus_bigtts', 'zh_female_xiaohe_uranus_bigtts'):
        return False, '音色不是本工作流批准的大壹或小何 2.0'
    return True, '非空配置与批准音色已核对；实际用哪个音色由 generate_candidate.py --voice 决定；未联网验证账户权限或额度'


def playwright_browsers():
    env = os.environ.get('PLAYWRIGHT_BROWSERS_PATH')
    for c in ([env] if env else []) + [HOME / 'AppData/Local/ms-playwright', HOME / '.cache/ms-playwright', HOME / 'Library/Caches/ms-playwright']:
        if c and Path(c).is_dir():
            return Path(c)
    return None


def _extra_bin_dirs():
    """pip 装的命令行工具（uv 等）落在 Python 的 Scripts 目录，不一定在 PATH 里。"""
    import sysconfig
    dirs = [Path(sys.executable).parent / 'Scripts', Path(sys.executable).parent]
    for scheme in (None, 'posix_user', 'nt_user'):
        try:
            dirs.append(Path(sysconfig.get_path('scripts', scheme) if scheme else sysconfig.get_path('scripts')))
        except Exception:
            pass
    return [d for d in dirs if d.is_dir()]


def ensure_media_tools():
    """PATH 里没有 ffmpeg/ffprobe 时，用 pip 装的 static-ffmpeg 补进本进程 PATH（子进程继承）；没装就什么也不做。"""
    if shutil.which('ffmpeg') and shutil.which('ffprobe'):
        return True
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths(weak=True)
    except Exception:
        return False
    return bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))


def which(*names):
    for n in names:
        w = shutil.which(n)
        if w:
            return w
    for d in _extra_bin_dirs():
        for n in names:
            for cand in (d / n, d / (n + '.exe')):
                if cand.is_file():
                    return str(cand)
    return None


ensure_media_tools()
