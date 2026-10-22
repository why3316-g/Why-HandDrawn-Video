"""新电脑离线技术验收：隔离复制本包，真实渲染及验收；不付费、不生图、不冒充内容审片。"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave
from verify_bundle import ROOT, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, help='全新可写目录；拒绝覆盖')
    parser.add_argument('--mode', choices=('portrait', 'landscape'), default='portrait', help='分别验收两种画幅')
    parser.add_argument('--online-runtime', action='store_true', help='仅允许 uv 补齐运行依赖；不调用付费服务')
    args = parser.parse_args()
    output = Path(args.out).resolve()
    if output.exists():
        raise FileExistsError(f'验收目录已存在，不覆盖：{output}')
    result = verify(ROOT)
    if not result['pass']:
        raise ValueError('先修复整包完整性：' + '; '.join(result['errors'][:8]))
    output.mkdir(parents=True)
    # 在含空格的新路径中执行；只复制本包，不传原工作区或其他 Skill。
    skill = output / 'isolated installation/Why-HandDrawn-Video'
    shutil.copytree(ROOT, skill, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
    workspace = output / 'new computer workspace'
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
               HUASHU_SKILL=str(output / 'absent external skill'))
    env.pop('HDV_LIBRARY', None)
    commands = []

    def run(command, cwd=None):
        proc = subprocess.run([str(v) for v in command], cwd=cwd or output, env=env,
                              capture_output=True, encoding='utf-8', errors='replace')
        commands.append({'command': [str(v) for v in command], 'exit_code': proc.returncode})
        (output / f'step-{len(commands):02d}.log').write_text(proc.stdout + proc.stderr, encoding='utf-8')
        print(f'[{len(commands)}] {Path(str(command[1])).name if len(command) > 1 else command[0]} → {proc.returncode}', flush=True)
        if proc.returncode:
            raise RuntimeError(f'步骤失败，见 step-{len(commands):02d}.log\n' + (proc.stdout + proc.stderr)[-1800:])
        return proc

    def script(name, *arguments):
        return run([sys.executable, skill / 'scripts' / name, '--project', project, *arguments], project)

    run([sys.executable, skill / 'scripts/verify_bundle.py'])
    # 明确模拟没有其他 Skill 的新 home；保留本机浏览器缓存作为运行软件。
    probe = ("import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); import common; "
             "common.HOME=Path(sys.argv[2]); assert common.find_huashu()==common.SKILL/'upstream/huashu-art-motion'; "
             "assert common.find_story_visuals()==common.SKILL")
    run([sys.executable, '-c', probe, skill / 'scripts', output / 'empty user home'])
    run([sys.executable, skill / 'scripts/new_project.py', 'smoke', '--workspace', workspace, '--date', '20261014', '--mode', args.mode])
    project = workspace / 'projects/20261014-smoke-v01'
    narration = ['孩子躺在家里玩手机。', '妈妈坐在旁边看着他。']
    (project / 'brief/narration.txt').write_text('\n'.join(narration), encoding='utf-8')
    title = '手绘工作流迁移测试'
    (project / 'brief/title.txt').write_text(title, encoding='utf-8')
    sentences, offset = [], .1
    for text in narration:
        clean = text.rstrip('。')
        words = [{'word': c, 'startTime': round(offset + k * .37, 3),
                  'endTime': round(offset + (k + 1) * .37, 3)} for k, c in enumerate(clean)]
        sentences.append({'text': text, 'startTime': words[0]['startTime'],
                          'endTime': words[-1]['endTime'], 'words': words})
        offset = words[-1]['endTime'] + .2
    timestamps = project / 'assets/audio/fixture-timestamps.json'
    timestamps.write_text(json.dumps({'fixture_only': True, 'data': {'sentences': sentences}}, ensure_ascii=False), encoding='utf-8')
    # 正弦音仅用于检查声轨和混音，不是配音，也不能用来验证 ASR/人耳通过。
    voice = project / 'assets/audio/fixture-tone.wav'
    import numpy as np
    sr = 44100
    times = np.arange(round(offset * sr)) / sr
    tone = (.13 * np.sin(2 * math.pi * 173 * times) + .04 * np.sin(2 * math.pi * 311 * times))
    with wave.open(str(voice), 'wb') as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(sr)
        stream.writeframes((tone * 32767).astype('<i2').tobytes())
    cfg_path = project / 'design/config.json'
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    cfg.update(volc_json='assets/audio/fixture-timestamps.json', voice_wav='assets/audio/fixture-tone.wav',
               voice_mp3='assets/audio/fixture-tone.wav', header_first=['手绘工作流', '迁移技术测试'], header_other='迁移技术测试')
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8')
    roles = [{'cast_id': 'fixture', 'name': '测试人物', 'age': 30, 'emotion': '技术夹具', 'face': '包内参考图', 'body': '包内参考图',
              'gaze': '包内参考图', 'action': '技术测试', 'avoid': '不可作正式人物/内容验收'}]
    (project / 'design/cast.json').write_text(json.dumps({'fixture': {
        'name': '测试人物', 'identity': '仅用于离线技术烟测的虚构角色', 'wardrobe_role': 'none',
        'gender': 'unspecified'}}, ensure_ascii=False), encoding='utf-8')
    shots = {'shots': []}
    for k, sid in enumerate(('hook', 'next')):
        # 同图两次验证复用检查器；不新造正式人物图。
        shutil.copyfile(skill / 'assets/style-ref-C.png', project / f'assets/images/C-{sid}-v01.png')
        shots['shots'].append({'id': sid, 'asset': sid, 'cast': 'fixture', 'narration': narration[k],
                               'roles': roles, 'reviewed': True,
                               'hands_check': '技术夹具字段：复用参考图，仅测试检查记录流转；不代表正式人物双手已验收。',
                               'observation': '技术测试夹具：复用包内画风参考；只测试记录流转，不是新人物或内容审核。'})
    (project / 'design/shots.json').write_text(json.dumps(shots, ensure_ascii=False), encoding='utf-8')
    script('analyze_strokes.py')
    film = '''import json,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'design'))
from hdv import Clock,Film,INK,OR
cfg=json.loads((P/'design/config.json').read_text(encoding='utf-8'))
c=Clock(P/cfg['narration'],P/cfg['volc_json'])
F=Film(P,c,header_first=cfg['header_first'],header_other=cfg['header_other'])
wide=cfg.get('mode')=='landscape'
cx,top,h=(1380,300,550) if wide else (540,700,550)
F.panel(0,'hook',0)
F.hero(0,'hook',cx,top,h,c.T('孩子')[0],c.T('玩手机')[0]-c.T('孩子')[0])
F.text(0,'玩手机',145,480,72,c.T('玩手机')[0],.85,OR)
F.line(0,[(145,530),(560,530)],c.T('手机')[0],.45,INK,6,False)
F.panel(1,'next',c.T('妈妈')[0]-.1)
F.hero(1,'next',cx,top,h,c.T('妈妈')[0],c.T('看着他')[0]-c.T('妈妈')[0])
F.text(1,'看着他',145,480,72,c.T('看着他')[0],.85,OR)
F.line(1,[(145,530),(560,530)],c.T('他')[0],.35,INK,6,False)
caps=[{'start':c.line_span(i)[0],'end':c.line_span(i)[1],'text':t} for i,t in enumerate(c.lines)]
F.build(caps,out='design/spec-film.json')
'''
    (project / 'design/film.py').write_text(film, encoding='utf-8')
    run([sys.executable, project / 'design/film.py'], project)
    script('make_manifest.py')
    render_args = [] if args.online_runtime else ['--offline']
    script('render_film.py', '--out', 'renders/smoke-visual-v01.mp4', *render_args)
    # 中文封面走真实现有合成脚本，插画仅取随包画风参考；没有付费生图。
    cover_cfg = {'name': 'smoke', 'size': 100, 'title_top': 180,
                 'lines': [[[title[:5], 0]], [[title[5:], 1]]], 'illus_width': 520, 'illus_center_y': 1280}
    if args.mode == 'landscape':
        cover_cfg.update(size=76, title_top=220, illus_width=400, illus_center_x=1440, illus_center_y=570)
    (project / 'design/cover.json').write_text(json.dumps(cover_cfg, ensure_ascii=False), encoding='utf-8')
    (project / 'design/cover-philosophy-v01.md').write_text('仅为迁移技术夹具：白底、中文标题、橙色强调与包内参考。不是用户审核过的正式封面。', encoding='utf-8')
    shutil.copyfile(skill / 'assets/style-ref-C.png', project / 'assets/images/cover-illus-v01.png')
    script('make_cover.py', '--skip-gen', '--imagegen-tool', '随包测试夹具（无新生图）')
    # 公开分享包也能验证混音：本次测试创建短暂的合成双声道音调作为 BGM。
    library = workspace / 'assets/audio-library'
    (library / 'bgm').mkdir(parents=True)
    bgm = library / 'bgm/fixture.wav'
    with wave.open(str(bgm), 'wb') as stream:
        stream.setnchannels(2); stream.setsampwidth(2); stream.setframerate(sr)
        stereo = np.repeat((tone * .25)[:, None], 2, axis=1)
        stream.writeframes((stereo * 32767).astype('<i2').tobytes())
    (library / 'LICENSES.md').write_text('| 文件 | 来源 | 授权类型 | 可商用 |\n|---|---|---|---|\n| fixture.wav | 本测试合成音调 | 仅作测试夹具 | 是 |\n', encoding='utf-8')
    script('mix_audio.py', '--video', 'renders/smoke-visual-v01.mp4', '--out', 'renders/smoke-bgm-v01.mp4', '--bgm', 'fixture.wav')
    script('add_cover_intro.py', '--video', 'renders/smoke-bgm-v01.mp4', '--cover', 'renders/smoke-cover-v01.png', '--out', 'renders/smoke-final-v01.mp4')
    script('export_website.py', '--video', 'renders/smoke-final-v01.mp4', '--cover', 'renders/smoke-cover-v01.png', '--out', 'renders/website-v01')
    script('opening_check.py', '--video', 'renders/smoke-final-v01.mp4')
    script('panel_check.py', '--video', 'renders/smoke-final-v01.mp4', '--offset', '.2')
    script('sync_report.py')
    script('check_voice.py', '--no-asr')
    script('qa_project.py', *render_args)
    qa = json.loads((project / 'qc/qa/qa.json').read_text(encoding='utf-8'))
    assert not qa['page_errors'], qa['page_errors']
    assert qa['segments'] and all(row['deterministic'] for row in qa['segments'])
    def probe(path):
        return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]).stdout)
    before = probe(project / 'renders/smoke-bgm-v01.mp4')
    final = project / 'renders/smoke-final-v01.mp4'
    after = probe(final)
    video = lambda data: next(s for s in data['streams'] if s['codec_type'] == 'video')
    assert int(video(after)['nb_frames']) == int(video(before)['nb_frames']) + 6
    dimensions = (1920, 1080) if args.mode == 'landscape' else (1080, 1920)
    assert (video(after)['width'], video(after)['height'], video(after)['r_frame_rate']) == (*dimensions, '30/1')
    assert any(s['codec_type'] == 'audio' for s in after['streams'])
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(final), '-t', '0.16', '-vn', '-ac', '1', '-ar', '44100', '-f', 's16le', '-'])
    assert np.max(np.abs(np.frombuffer(raw, dtype='<i2').astype(np.int32))) <= 8, '封面片头非静音'
    def frame(path, seconds):
        thumb = '480:270' if args.mode == 'landscape' else '270:480'
        return np.frombuffer(subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(seconds), '-i', str(path), '-frames:v', '1', '-vf', 'scale=' + thumb, '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-']), np.uint8).astype(float)
    from PIL import Image
    thumb = (480, 270) if args.mode == 'landscape' else (270, 480)
    cover = np.array(Image.open(project / 'renders/smoke-cover-v01.png').convert('RGB').resize(thumb)).ravel()
    assert float(np.mean(np.abs(frame(final, 0) - cover))) < 6, '第0帧不是封面'
    assert float(np.mean(np.abs(frame(final, .2) - frame(project / 'renders/smoke-bgm-v01.mp4', 0)))) < 6, '第6帧未回到正片'
    delivery = json.loads((project / 'renders/website-v01/delivery.json').read_text(encoding='utf-8'))
    assert delivery['pass'] and delivery['caption_offset_seconds'] == .2
    web = probe(project / 'renders/website-v01/video.mp4')
    assert int(video(web)['nb_frames']) == int(video(after)['nb_frames'])
    assert (video(web)['width'], video(web)['height']) == dimensions
    # faststart 实际 atom 顺序；不能只相信命令参数或回执字段。
    payload = (project / 'renders/website-v01/video.mp4').read_bytes()
    assert payload.index(b'moov') < payload.index(b'mdat')
    vtt = (project / 'renders/website-v01/captions.vtt').read_text(encoding='utf-8')
    assert '00:00:00.300 --> ' in vtt, 'VTT未计首6帧偏移'
    report = {'pass': True, 'fixture_only': True, 'mode': args.mode, 'isolated_skill': str(skill), 'project': str(project),
              'video': str(final), 'video_sha256': hashlib.sha256(final.read_bytes()).hexdigest(),
              'commands': commands, 'frame_count': int(video(after)['nb_frames']),
              'qa_deterministic': True, 'paid_calls': 0,
              'not_verified': ['真实火山配音与接口', '真实生图', '独立ASR内容', '人物表演和封面人工审核', '完整成片人耳/独立审片', '其他操作系统']}
    (output / 'SMOKE_RESULT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'pass': True, 'report': str(output / 'SMOKE_RESULT.json'), 'video': str(final)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    main()
