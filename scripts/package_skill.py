"""构建单文件夹安装包。share=不含三首自用配乐；public=面向互联网公开：另外剔除品牌 Logo/陪伴师/服饰/版式参考图、样板案例，并换上 public/ 里的通用文档，且做隐私扫描。"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
from verify_bundle import ROOT, bundle_files, verify


PUBLIC_EXCLUDE = ('assets/brand/', 'assets/characters/', 'assets/layouts/', 'assets/hands/', 'examples/', 'public/')   # assets/hands/ 是个人手部素材池，公开版不带图，new_project 自动退回 marker-hand-v02.png
PUBLIC_REPLACED = ('README.md', 'AGENTS.md', 'CLAUDE.md')          # 个人版文档，公开版用 public/ 里的同名通用版
TEXT_SUFFIX = {'.md', '.py', '.json', '.txt', '.yaml', '.yml', '.js', '.html', '.css', '.env', '.example', '.toml', '.cfg'}


def privacy_scan(root, files):
    """公开版隐私闸门：public/privacy_denylist.txt 每行一个正则（该文件本身不进公开包）；命中任何一条即拒绝打包。"""
    deny = Path(root) / 'public/privacy_denylist.txt'
    if not deny.is_file():
        raise ValueError('缺少 public/privacy_denylist.txt，公开版不能在没有隐私扫描时打包。')
    lines = [line.strip() for line in deny.read_text(encoding='utf-8').splitlines() if line.strip() and not line.startswith('#')]
    patterns = [re.compile(x) for x in lines if not x.startswith('warn:')]
    warns = [re.compile(x[5:]) for x in lines if x.startswith('warn:')]
    hits, warned = [], {}
    for rel, content in files:
        if Path(rel).suffix.lower() in TEXT_SUFFIX or Path(rel).name in ('.gitignore', '.gitattributes'):
            text = content.decode('utf-8', errors='ignore')
            hits += [f'{rel}: 命中 {p.pattern}' for p in patterns if p.search(text)]
            for p in warns:
                if p.search(text):
                    warned.setdefault(rel, []).append(p.pattern)
        hits += [f'{rel}: 文件名命中 {p.pattern}' for p in patterns if p.search(rel)]
    for rel, words in sorted(warned.items()):
        print(f'提示（赛道/品牌用词，未拦截）：{rel} 含 {", ".join(words)}', file=sys.stderr)
    if hits:
        raise ValueError('隐私扫描未通过，不打包：' + '; '.join(hits[:12]))


def package(root, output, profile):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.is_relative_to(root):
        raise ValueError('压缩包必须保存到 Skill 目录外。')
    if output.exists():
        raise FileExistsError(f'不覆盖已有交付包：{output}')
    report = verify(root)
    if not report['pass']:
        raise ValueError('原包完整性未通过：' + '; '.join(report['errors'][:8]))
    selected = []
    for rel, path in bundle_files(root):
        if profile in ('share', 'public') and rel.startswith('assets/audio-library/bgm/') and path.suffix.lower() in ('.mp3', '.wav', '.flac', '.m4a'):
            continue
        if profile == 'public':
            if rel.startswith(PUBLIC_EXCLUDE) or rel in PUBLIC_REPLACED:
                continue
        selected.append((rel, path.read_bytes()))
    if profile == 'public':
        overlay = {rel[len('public/'):].removesuffix('.tpl'): path.read_bytes() for rel, path in bundle_files(root)   # .tpl 后缀避免被当成第二个 SKILL.md
                   if rel.startswith('public/') and rel != 'public/privacy_denylist.txt'}
        if 'AGENTS.md' not in overlay:
            raise ValueError('public/AGENTS.md 缺失')
        overlay['CLAUDE.md'] = overlay['AGENTS.md']                    # 两份必须逐字节一致
        selected = [(r, c) for r, c in selected if r not in overlay] + sorted(overlay.items())
        privacy_scan(root, selected)
    selected.sort()
    manifest = {'schema': 2, 'skill': 'Why-HandDrawn-Video', 'edition': 'lean', 'profile': profile,
                'snapshot_date': '2026-10-14',
                'files': {rel: hashlib.sha256(content).hexdigest() for rel, content in selected}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for rel, content in selected:
            archive.writestr('Why-HandDrawn-Video/' + rel, content)
        archive.writestr('Why-HandDrawn-Video/BUNDLE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    result = {'path': str(output), 'profile': profile, 'files': len(selected) + 1,
              'bytes': output.stat().st_size, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    output.with_suffix(output.suffix + '.sha256').write_text(result['sha256'] + '  ' + output.name + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', default=str(ROOT))
    ap.add_argument('--out', required=True)
    ap.add_argument('--profile', choices=('migration', 'share', 'public'), default='share')
    args = ap.parse_args()
    print(json.dumps(package(args.root, args.out, args.profile), ensure_ascii=False, indent=2))
