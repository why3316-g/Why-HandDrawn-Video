"""将已审核成片封装为网站 MP4、poster 和偏移正确的 WebVTT；不上传网站。"""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

from common import ensure_media_tools
from hdv.layout import project_layout, validate_spec_layout


def stamp(seconds):
    millis = round(seconds * 1000)
    hours, rest = divmod(millis, 3600000)
    minutes, rest = divmod(rest, 60000)
    secs, millis = divmod(rest, 1000)
    return f'{hours:02}:{minutes:02}:{secs:02}.{millis:03}'


def captions_vtt(captions, offset=.2):
    if not math.isfinite(offset) or offset < 0:
        raise ValueError('字幕偏移必须为非负秒数')
    rows = ['WEBVTT', '']
    previous_end = 0
    for i, cap in enumerate(captions, 1):
        start, end = float(cap['start']), float(cap['end'])
        if not all(math.isfinite(v) for v in (start, end)) or start < previous_end - 1e-6 or end <= start:
            raise ValueError('字幕时间必须非负、递增且不重叠')
        text = str(cap['text']).strip()
        if not text:
            raise ValueError('字幕文字不能为空')
        rows += [str(i), f'{stamp(start + offset)} --> {stamp(end + offset)}',
                 html.escape(text, quote=False), '']
        previous_end = end
    if not captions:
        raise ValueError('缺少字幕，不能生成网站字幕文件')
    return '\n'.join(rows) + '\n'


def probe(path):
    return json.loads(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
        encoding='utf-8'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project', default='.')
    ap.add_argument('--video', required=True, help='含审核通过封面首6帧的 final MP4')
    ap.add_argument('--cover', required=True, help='用户通过的同尺寸 PNG 封面')
    ap.add_argument('--out', required=True, help='不存在的新交付目录，例如 renders/website-v01')
    args = ap.parse_args()
    ensure_media_tools()
    project = Path(args.project).resolve()
    resolve = lambda name: (project / name).resolve()
    video, cover, output = resolve(args.video), resolve(args.cover), resolve(args.out)
    if output.exists():
        raise FileExistsError('交付目录已存在，请换新版本，不覆盖旧产物')
    cfg = json.loads((project / 'design/config.json').read_text(encoding='utf-8'))
    spec = json.loads((project / cfg.get('spec_out', 'design/spec-film.json')).read_text(encoding='utf-8'))
    layout = project_layout(project)
    validate_spec_layout(spec, layout)
    media = probe(video)
    v = next(s for s in media['streams'] if s['codec_type'] == 'video')
    a = next((s for s in media['streams'] if s['codec_type'] == 'audio'), None)
    if (v['width'], v['height']) != (layout['width'], layout['height']):
        raise ValueError('成片尺寸与项目 mode 不一致')
    if v['codec_name'] != 'h264' or v.get('pix_fmt') != 'yuv420p' or not a or a['codec_name'] != 'aac':
        raise ValueError('网站交付需要 H.264/yuv420p 与 AAC 音轨，请先完成标准成片封装')
    fps_n, fps_d = map(int, v['r_frame_rate'].split('/'))
    fps = fps_n / fps_d
    if abs(fps - spec['fps']) > 1e-6 or fps != 30:
        raise ValueError('成片与事件表帧率不一致或不是30fps')
    frames = int(v['nb_frames'])
    if frames != round(spec['duration'] * fps) + 6:
        raise ValueError('成片帧数不等于正片加首6帧，不能推断字幕偏移')
    from PIL import Image
    with Image.open(cover) as poster:
        if poster.size != (layout['width'], layout['height']) or poster.format != 'PNG':
            raise ValueError('poster 必须为与成片同尺寸的 PNG 封面')
    offset = 6 / fps
    captions = spec['data']['captions']
    vtt = captions_vtt(captions, offset)
    if any(float(c['end']) + offset > frames / fps + 1e-6 for c in captions):
        raise ValueError('字幕超出最终视频时长')
    output.mkdir(parents=True)
    target = output / 'video.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-n', '-i', str(video), '-map', '0:v:0', '-map', '0:a:0',
                    '-c', 'copy', '-map_metadata', '-1', '-movflags', '+faststart', str(target)], check=True)
    exported = probe(target)
    ev = next(s for s in exported['streams'] if s['codec_type'] == 'video')
    if int(ev['nb_frames']) != frames:
        raise ValueError('网站封装改变了帧数，禁止交付')
    shutil.copyfile(cover, output / 'poster.png')
    (output / 'captions.vtt').write_text(vtt, encoding='utf-8')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = {'pass': True, 'mode': layout['mode'], 'size': [v['width'], v['height']],
              'fps': fps, 'frames': frames, 'caption_offset_seconds': offset, 'faststart': True,
              'source_video_sha256': sha(video), 'source_cover_sha256': sha(cover),
              'files': {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()},
              'review_scope': '仅封装和时序校验，不代替用户声音、人物、封面、成片确认或网站实测'}
    (output / 'delivery.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'网站交付 → {output}（MP4 / poster / WebVTT；未上传网站）')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
