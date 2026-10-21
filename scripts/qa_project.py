"""运行花叔 qa.py（项目内补丁版 qc/huashu_qa.py，确定性、页面报错、动感、框景线索）。
用法（项目根目录）：python <skill>/scripts/qa_project.py [--spec design/spec-film.json] [--out qc/qa]
说明：框景里的"进字幕带"线索，是本片自己烧录的字幕进入字幕带，属预期；其余线索（裁切、叠字、近空白）要看对应帧再判断。"""
import argparse, json, os, subprocess, sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except Exception: pass
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import playwright_browsers, which, find_huashu
import engine_fixes

ap = argparse.ArgumentParser()
ap.add_argument('--project', default='.')
ap.add_argument('--spec', default=None)
ap.add_argument('--out', default='qc/qa')
ap.add_argument('--offline', action='store_true', help='仅用已缓存的运行依赖')
a = ap.parse_args()
P = Path(a.project).resolve()
cfg = json.loads((P / 'design/config.json').read_text(encoding='utf-8'))
spec = Path(a.spec) if a.spec else P / cfg.get('spec_out', 'design/spec-film.json')
if not spec.is_absolute():
    spec = P / spec
qa = P / 'qc/huashu_qa.py'
if not qa.is_file():
    engine_fixes.make_qa(find_huashu() / 'scripts/qa.py', qa)
env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
pb = playwright_browsers()
if pb:
    env.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(pb))
report_path = Path(a.out) / 'qa.json'
if not report_path.is_absolute():
    report_path = P / report_path
# 上游本就覆盖此技术报告；先移除旧报告，避免子进程没有写新结果却沿用旧通过记录。
report_path.unlink(missing_ok=True)
r = subprocess.run([which('uv', 'uv.exe'), 'run'] + (['--offline'] if a.offline else []) + ['--no-project', '--with', 'playwright', '--with', 'numpy', '--with', 'pillow', 'python', '-u', str(qa), '--project', 'engine', '--spec', str(spec), '--out', a.out],
                   cwd=P, env=env, capture_output=True, encoding='utf-8', errors='replace')
lines = [l for l in (r.stdout + r.stderr).splitlines() if 'willReadFrequently' not in l and '进字幕带' not in l]
print('\n'.join(lines[-8:]))
# 开头规范（references/OPENING_SPEC.md）：对最新的成片（renders/*-final-v*.mp4）自动跑开头检测
code = r.returncode
if not code:
    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
        segments = report.get('segments', [])
        if not segments or report.get('page_errors') or any(row.get('deterministic') is not True for row in segments):
            print('QA 未通过：缺少有效段落、页面报错或同帧重复渲染不一致；请检查 qa.json。')
            code = 1
    except (OSError, ValueError, TypeError):
        print('QA 未生成可读取的本轮 qa.json，不能标记通过。')
        code = 1
finals = sorted((P / 'renders').glob('*-final-v*.mp4'), key=lambda f: f.stat().st_mtime)
if finals:
    oc = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / 'opening_check.py'), '--project', str(P), '--video', str(finals[-1])],
                        capture_output=True, encoding='utf-8', errors='replace')
    print(oc.stdout.strip() or oc.stderr.strip())
    code = code or oc.returncode
else:
    print('开头检测：renders/ 里还没有 *-final-v*.mp4，成片出来后要补跑 opening_check.py（OPENING_SPEC.md）')
sys.exit(code)
