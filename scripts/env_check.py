"""单包环境预检。--install 会自动安装缺失的运行依赖（官方来源、用户级、不需要管理员权限）；--production 另检查配音、独立转录与音乐；不调用付费服务。"""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from common import (SKILL, find_huashu, find_workspace, find_library,
                    companion_references, brand_logo, audio_config_status, playwright_browsers, which)
from verify_bundle import verify

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8')

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--project', default='.')
ap.add_argument('--production', action='store_true')
ap.add_argument('--install', action='store_true', help='自动安装缺失的 Python 库、uv、FFmpeg、Chromium 和独立转录模型（官方源，失败自动换国内镜像）')
a = ap.parse_args()
rows = []


PYPI_MIRROR = 'https://pypi.tuna.tsinghua.edu.cn/simple'
PLAYWRIGHT_MIRROR = 'https://cdn.npmmirror.com/binaries/playwright'
HF_MIRROR = 'https://hf-mirror.com'
ASR_REPO = 'Systran/faster-whisper-small'


def _run(cmd, env=None, timeout=3600):
    print('    $ ' + ' '.join(str(c) for c in cmd), flush=True)
    try:
        return subprocess.run(cmd, env=env, timeout=timeout).returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f'    ✗ 未完成：{type(exc).__name__}')
        return 1


def _py_ready():
    importlib.invalidate_caches()
    need = ['numpy', 'PIL', 'playwright', 'faster_whisper', 'requests', 'edge_tts', 'static_ffmpeg']
    if any(importlib.util.find_spec(m) is None for m in need):
        return False
    try:
        import edge_tts
        return tuple(int(x) for x in edge_tts.__version__.split('.')[:3]) >= (7, 3, 1)
    except Exception:
        return False


def _chromium_ready():
    pb = playwright_browsers()
    return bool(pb and sorted(pb.glob('chromium*')))


def _compiles(rel):
    """文件存在且语法可编译：换执行者时能真正跑起来，而不只是文件躺在包里。"""
    f = SKILL / rel
    if not f.is_file():
        return False
    try:
        compile(f.read_text(encoding='utf-8'), str(f), 'exec')
        return True
    except SyntaxError:
        return False


def _asr_ready():
    cache = Path.home() / '.cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots'
    local = os.environ.get('HDV_ASR_MODEL')
    return bool((local and (Path(local) / 'model.bin').is_file()) or list(cache.glob('*/model.bin')))


def install_missing():
    """逐项补齐；每一步先说明装什么、从哪来，官方源失败自动换国内镜像，仍失败就告诉你怎么手动装。"""
    print('== 自动安装缺失的运行依赖（官方来源、用户级安装、不需要管理员权限）==')
    if not _py_ready():
        print('· Python 依赖库（numpy、Pillow、playwright、faster-whisper、requests、edge-tts、uv、static-ffmpeg）来自 PyPI')
        req = str(SKILL / 'requirements.txt')
        base = [sys.executable, '-m', 'pip', 'install', '-r', req]
        if _run(base) != 0:
            print('  官方源失败，改用清华镜像重试')
            _run(base + ['-i', PYPI_MIRROR])
        print('  ' + ('✓ 完成' if _py_ready() else '✗ 仍有缺失：请手动运行 python -m pip install -r requirements.txt'))
    else:
        print('· Python 依赖库：已齐全')
    if not (which('ffmpeg') and which('ffprobe')):
        print('· FFmpeg / FFprobe：用 pip 装的 static-ffmpeg 下载对应系统的可执行文件（来自其 GitHub 发布页）')
        try:
            import static_ffmpeg
            static_ffmpeg.add_paths()
        except Exception as exc:
            print(f'  ✗ 下载失败（{type(exc).__name__}）：请手动安装 FFmpeg（Windows: winget install Gyan.FFmpeg；macOS: brew install ffmpeg；Linux: apt install ffmpeg）')
        print('  ' + ('✓ 完成' if (which('ffmpeg') and which('ffprobe')) else '✗ 仍未找到'))
    else:
        print('· FFmpeg / FFprobe：已有')
    if not _chromium_ready():
        print('· Chromium 浏览器（渲染用，约 150MB，来自 Playwright 官方下载源）')
        cmd = [sys.executable, '-m', 'playwright', 'install', 'chromium']
        if _run(cmd) != 0:
            print('  官方源失败，改用 npmmirror 镜像重试')
            _run(cmd, env={**os.environ, 'PLAYWRIGHT_DOWNLOAD_HOST': PLAYWRIGHT_MIRROR})
        print('  ' + ('✓ 完成' if _chromium_ready() else '✗ 仍未完成：请手动运行 python -m playwright install chromium'))
    else:
        print('· Chromium：已有')
    if not _asr_ready():
        print('· 独立转录模型（faster-whisper small，约 0.5GB，来自 Hugging Face；用来逐字核对配音有没有读错）')
        code = f"from huggingface_hub import snapshot_download; snapshot_download('{ASR_REPO}')"
        if _run([sys.executable, '-c', code], timeout=1800) != 0:
            print('  官方源失败，改用 hf-mirror 镜像重试')
            _run([sys.executable, '-c', code], env={**os.environ, 'HF_ENDPOINT': HF_MIRROR}, timeout=1800)
        print('  ' + ('✓ 完成' if _asr_ready() else '✗ 仍未完成：可设置 HDV_ASR_MODEL 指向已有模型目录（含 model.bin）'))
    else:
        print('· 独立转录模型：已有')
    print()


if a.install:
    install_missing()


def add(name, ok, detail, fix='', required=True):
    rows.append((name, ok, detail, fix, required))


report = verify(SKILL)
add('单包文件与来源校验', report['pass'], f"{report['checked']} 个文件；" + ('完整' if report['pass'] else '；'.join(report['errors'][:6])),
    '重新解压完整 Why-HandDrawn-Video 包，不要另装花叔补洞')
add('Python 3.10+', sys.version_info >= (3, 10), sys.version.split()[0])
for mod, package in [('numpy', 'numpy'), ('PIL', 'Pillow')]:
    ok = importlib.util.find_spec(mod) is not None
    add(package, ok, '已安装' if ok else '缺失', f'python -m pip install {package}')
requests_ready = importlib.util.find_spec('requests') is not None
add('火山 HTTP 运行库 requests', requests_ready, '已安装' if requests_ready else '缺失',
    'python -m pip install requests', required=False)
edge_ready = False
try:
    import edge_tts
    edge_ready = tuple(int(x) for x in edge_tts.__version__.split('.')[:3]) >= (7, 3, 1)
except Exception:
    pass
add('免费微软语音 edge-tts（>=7.3.1）', edge_ready, '已安装' if edge_ready else '缺失或版本过旧',
    'python -m pip install -U edge-tts；或加 --install 自动安装', required=False)
uv = which('uv', 'uv.exe')
ff, fp = which('ffmpeg'), which('ffprobe')
add('uv', bool(uv), uv or '缺失', '加 --install 自动安装（pip install uv），或见 https://docs.astral.sh/uv/')
add('FFmpeg / FFprobe', bool(ff and fp), f'{ff} | {fp}', '加 --install 自动安装，或手动安装 FFmpeg 并加入 PATH')
hs = find_huashu()
add('包内手绘引擎、QA、规则', bool(hs), 'upstream/huashu-art-motion（无需另装）', '重新解压完整包')
# 配音链路三件套 + 停顿压缩工具都属于必需文件：换 AI 工具/换会话执行时，缺任何一个都不能开做
for rel in ('scripts/check_visual_manifest.py', 'references/COVER_ART_DIRECTION.md',
            'scripts/audio/generate_candidate.py', 'scripts/audio/directives.py',
            'scripts/audio/compress_pauses.py', 'assets/fonts/NotoSansSC-VF.ttf'):
    add(rel, (SKILL / rel).is_file(), '包内文件', '重新解压完整包')
# 配音配方：温柔妈妈 2.0 = 语速 19 + 重指令 + 本地压停顿。后两步要能真跑，不只看文件在不在。
numpy_ready = importlib.util.find_spec('numpy') is not None
comp_ok = _compiles('scripts/audio/compress_pauses.py')
add('配音停顿压缩工具（温柔妈妈配方第 3 步，必需）', comp_ok and numpy_ready,
    'compress_pauses.py 可执行' if comp_ok and numpy_ready else ('缺少 numpy' if comp_ok else '文件缺失或语法错误'),
    '重新解压完整包；numpy 缺失时 python -m pip install numpy')
add('音色试听/变体横评工具（换音色或调参时才用）',
    _compiles('scripts/audio/audition_voices.py') and _compiles('scripts/audio/audition_variants.py'),
    'audition_voices.py / audition_variants.py 可执行', '重新解压完整包', required=False)
pb = playwright_browsers()
chromium = sorted(pb.glob('chromium*')) if pb else []
add('Chromium 缓存目录', bool(chromium), str(pb) if chromium else '未发现',
    '加 --install 自动安装，或 python -m playwright install chromium；实际启动用 smoke_test.py 验证')
ws = find_workspace(a.project)
add('工作区', bool(ws), str(ws) if ws else '空目录：new_project.py 会先创建同步规则和目录标识', required=False)
comp = companion_references(ws)
add('品牌扩展包：陪伴师五张审核参考（可选）', len(list(comp.glob('*.png'))) == 5, str(comp) if comp.is_dir() else '未安装（公开版默认不带，不影响其他赛道）', '', required=False)
logo = brand_logo(ws)
add('品牌扩展包：品牌原 Logo（可选）', logo.is_file(), str(logo) if logo.is_file() else '未安装（公开版默认不带）', '', required=False)
envf = ws / '.private/volcengine.env' if ws else None
creds, credential_detail = audio_config_status(envf)
add('火山配音配置（更好的效果；不输出值）', creds, credential_detail,
    '想要更好的配音：按 README 开头教程配置火山密钥，写入视频工作区 .private/volcengine.env', required=False)
add('配音通道（火山或免费微软至少一个）', bool(creds or edge_ready), '火山' if creds else '免费微软语音（效果一般，建议配火山）' if edge_ready else '都不可用',
    '加 --install 装好免费微软语音，或配置火山密钥', required=a.production)
asr = importlib.util.find_spec('faster_whisper') is not None
add('独立 ASR 运行库', asr, '已安装' if asr else '缺失',
    '加 --install 自动安装；完整配音验收不可用 --no-asr 替代', required=a.production)
model = os.environ.get('HDV_ASR_MODEL')
cache = Path.home() / '.cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots'
ready_model = bool((model and (Path(model) / 'model.bin').is_file()) or list(cache.glob('*/model.bin')))
add('独立 ASR 模型', ready_model, str(model) if model else 'small 模型缓存' if ready_model else '未发现本机模型',
    '加 --install 自动下载（官方源失败自动换镜像），或设置 HDV_ASR_MODEL 为已有模型目录（含 model.bin）', required=a.production)
lib = find_library(a.project)
tracks = list((lib / 'bgm').glob('*')) if (lib / 'bgm').is_dir() else []
tracks = [p for p in tracks if p.suffix.lower() in ('.mp3', '.wav', '.flac', '.m4a')]
add('可用配乐文件（仍须按账号核实授权登记）', bool(tracks), f'{lib}：{len(tracks)} 首',
    '公开分享包不附原三首曲目；在工作区 assets/audio-library/bgm 放入本账号可商用曲目，并登记 LICENSES.md', required=a.production)
codex = which('codex.cmd', 'codex')
add('Claude/WorkBuddy 的 Codex CLI', bool(codex), codex or '未发现；Codex 用内置生图工具、Antigravity 用内置 image-generator 子代理',
    'Claude/WorkBuddy 生图前需配置已登录的 Codex CLI；Codex 与 Antigravity 会话不需要', required=False)
bad = 0
for name, ok, detail, fix, req in rows:
    print(f"{'✓' if ok else '✗' if req else '△'} {name}: {detail}")
    if not ok:
        if fix:
            print('    → ' + fix)
        bad += bool(req)
print(f'\n结论：{bad} 项必需条件未满足。' if bad else '\n结论：所选预检通过。渲染实际启动用 smoke_test.py 验证；△ 不代表服务或人工审核已完成。')
sys.exit(1 if bad else 0)
