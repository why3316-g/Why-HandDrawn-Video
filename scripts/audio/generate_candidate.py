"""One full-body Volcengine synthesis per project; no sentence splitting or fallback."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SKILL=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL/'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import find_workspace

def workspace_for(project):
    project=Path(project).resolve()
    workspace=find_workspace(project)
    if workspace is None:
        workspace=next((p.parent for p in project.parents if p.name=='projects'), None)
    if workspace is None or not project.is_relative_to(workspace/'projects'):
        raise ValueError('Project must be inside the selected workspace projects directory.')
    return workspace

VOICES = {'dayi': 'zh_male_dayi_uranus_bigtts', 'xiaohe': 'zh_female_xiaohe_uranus_bigtts'}
# 音色槽位（2026-10-29 起只批准两个）：dayi=大壹（男讲述者，默认）；xiaohe=小何 2.0（女讲述者）。
# 温柔妈妈 2.0 与鸡汤女 2.0 均已停用（用户判定不满意）。
# 默认语速（火山 audio_params.speech_rate，[-50,100]，100=2.0 倍速、0=1.0 倍速）：大壹、小何 2.0 均为 10（≈1.1 倍）。
# 命令行 --speech-rate 只在用户明确要求时覆盖，且必须写进回执。
SPEECH_RATE = {'dayi': 10, 'xiaohe': 10}
from institutional_profile import PROFILE as INSTITUTIONAL, select_voice, broadcast_tts_class
VOICES['yichen'] = INSTITUTIONAL['voice_id']
SPEECH_RATE['yichen'] = INSTITUTIONAL['speech_rate']


# 每个音色的默认语音指令（additions.context_texts，仅 2.0 音色可用）。当前两个批准音色都不带默认指令；机制保留给将来经用户批准的配方。
VOICE_DIRECTIVES = {}



def speed_multiplier(rate):
    """火山语速 0=1.0 倍、100=2.0 倍、-50=0.5 倍，按线性换算，便于回执里写人话。"""
    return round(1 + rate / 100, 3)


def speech_rate_for(voice, profile, override=None):
    if override is not None:
        if not -50 <= override <= 100:
            raise ValueError('speech_rate 必须在 [-50, 100] 之间（100=2.0 倍速）')
        return int(override), 'cli_override'
    if voice in SPEECH_RATE:
        return SPEECH_RATE[voice], 'voice_default'
    return int(profile['speech_rate']), 'voice_profile'


def check_private_voice(values):
    if values.get('DOUBAO_SPEECH_VOICE_TYPE') not in VOICES.values():
        raise ValueError('Private voice is not an approved voice (dayi/xiaohe).')


def other_voice_receipt(project, text_hash, voice_id):
    """同一全文已用另一个音色合成过则返回其回执路径；换声要用户明确指令，不静默再付费。"""
    for f in sorted((project/'assets/audio').glob('narration-volcengine-*-full-*.mp3.json')):
        try: m=json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        if (m.get('input_text_sha256') or m.get('text_sha256'))==text_hash and m.get('voice_id') not in (None, voice_id): return f
    return None


def volc_ready(workspace):
    """工作区 .private/volcengine.env 是否已填真实密钥（不读取、不输出密钥内容）。"""
    f=workspace/'.private/volcengine.env'
    if not f.is_file(): return False
    try:
        for line in f.read_text(encoding='utf-8-sig').splitlines():
            if line.startswith('DOUBAO_SPEECH_API_KEY='):
                key=json.loads(line.split('=',1)[1])
                return bool(key.strip()) and not any(w in key.lower() for w in ('填写','your-key','placeholder','dummy','example'))
    except (ValueError, OSError): return False
    return False

def resolve_provider(workspace, explicit='auto'):
    """配音通道：命令行 > 环境变量 HDV_TTS_PROVIDER > 工作区 .hdv-workspace.json 的 tts_provider > auto。
    auto：配了火山密钥用火山，没配用免费微软语音。固定为 volcengine 时缺密钥直接报错，不会悄悄降级到微软。"""
    choice=explicit if explicit!='auto' else (os.environ.get('HDV_TTS_PROVIDER') or '')
    if not choice:
        mf=workspace/'.hdv-workspace.json'
        if mf.is_file():
            try: choice=json.loads(mf.read_text(encoding='utf-8')).get('tts_provider','')
            except (ValueError, OSError): choice=''
    if choice in ('volcengine','edge'): return choice
    return 'volcengine' if volc_ready(workspace) else 'edge'

def run_edge(project,workspace,text,text_hash,version,preflight,voice,confirm_voice_change):
    sys.path.insert(0,str(SKILL/'scripts/audio'))
    import edge_provider as ep
    voice_id=ep.EDGE_VOICES[voice]
    target=project/'assets/audio'/f'narration-edge-{voice}-full-{version}.mp3'
    summary={'provider':'edge_tts','voice':voice,'voice_id':voice_id,'text_sha256':text_hash,'text_characters':len(text),'output':str(target),
             'note':'免费微软语音，效果和稳定性不如火山；需要更好效果请配置火山密钥（见 README）'}
    ver=ep.edge_version()
    if ver is None or ver<ep.MIN_EDGE_TTS:
        raise ValueError('edge-tts 未安装或版本低于 7.3.1：运行 pip install -U edge-tts（或 env_check.py --install）。')
    if preflight:
        summary['credential_present']=False; print(json.dumps(summary,ensure_ascii=False)); return summary
    receipt=target.with_suffix('.mp3.json')
    if target.exists():
        metadata=json.loads(receipt.read_text(encoding='utf-8'))
        if metadata.get('input_text_sha256')!=text_hash or metadata.get('audio_sha256')!=sha_bytes(target.read_bytes()):
            raise ValueError('Existing candidate hash mismatch; no automatic resubmission.')
        duration,_=verify_audio(target); master=ensure_wav(target); metadata['wav_master']=master
        receipt.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        summary.update({'reused':True,'duration_seconds':duration,'wav_master':master['path']}); print(json.dumps(summary,ensure_ascii=False)); return summary
    if receipt.exists(): raise ValueError('Existing failure/receipt prevents duplicate submission; use explicit new version only when authorized.')
    if other_voice_receipt(project,text_hash,voice_id) and not confirm_voice_change:
        raise ValueError('Same narration already synthesized with another voice/provider; changing needs explicit user approval (--confirm-voice-change).')
    target.parent.mkdir(parents=True,exist_ok=True)
    print('Synthesizing with free Microsoft voice (edge-tts).',flush=True)
    try: sentences=ep.synthesize(text,voice,target,ep.proxy_from_env())
    except Exception as exc:
        receipt.write_text(json.dumps({'provider':'edge_tts','success':False,'error_type':type(exc).__name__,'error':str(exc)[:300],'input_text_sha256':text_hash},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if target.exists(): target.unlink()
        raise RuntimeError('edge-tts failed (403: pip install -U edge-tts; offline: check network/proxy).')
    duration,streams=verify_audio(target); master=ensure_wav(target)
    metadata={'provider':'edge_tts','input_text_sha256':text_hash,'voice_id':voice_id,'voice_slot':voice,'speech_rate':ep.EDGE_RATE,
        'full_body':True,'task_id':None,'source':'edge-tts '+'.'.join(map(str,ep.edge_version())),
        'provider_query':{'data':{'sentences':sentences}},'independent_asr_verified':False,'human_review':'pending',
        'audio_sha256':sha_bytes(target.read_bytes()),'duration_seconds':duration,'decode_passed':True,'streams':streams,'wav_master':master}
    receipt.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary.update({'duration_seconds':duration,'decode_passed':True,'reused':False,'wav_master':master['path']}); print(json.dumps(summary,ensure_ascii=False)); return summary


def utf16_length(text):
    return len(text.encode('utf-16-le'))//2

def scrub(value,secrets=()):
    if isinstance(value,dict):
        return {key:scrub(item,secrets) for key,item in value.items()
                if key.lower() not in {'audio_url','authorization','x-api-key','api_key','access_token','token'}}
    if isinstance(value,list):
        return [scrub(item,secrets) for item in value]
    if isinstance(value,str):
        for secret in secrets:
            if secret: value=value.replace(secret,'[redacted]')
        value=re.sub(r'https?://[^\s\"\']+\?[^\s\"\']+', '[redacted_signed_url]', value)
    return value

def sha_bytes(data): return hashlib.sha256(data).hexdigest()

def load_private(workspace):
    values={}
    for line in (workspace/'.private/volcengine.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' not in line or line.lstrip().startswith('#'): continue
        name,value=line.split('=',1)
        if name not in {'DOUBAO_SPEECH_API_KEY','DOUBAO_SPEECH_VOICE_TYPE'}: continue
        values[name]=json.loads(value)
        os.environ[name]=values[name]
    if not values.get('DOUBAO_SPEECH_API_KEY'): raise ValueError('Private speech credential missing.')
    return values

def verify_audio(path):
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)]))
    subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],check=True)
    return float(probe['format']['duration']),probe['streams']

def ensure_wav(path):
    wav=path.with_suffix('.wav')
    if not wav.exists():
        subprocess.run(['ffmpeg','-v','error','-i',str(path),'-ar','44100','-ac','1','-c:a','pcm_s16le',str(wav)],check=True)
    duration,streams=verify_audio(wav)
    if len(streams)!=1 or streams[0].get('sample_rate')!='44100' or streams[0].get('channels')!=1:
        raise ValueError('Invalid alignment WAV format.')
    return {'path':str(wav),'sha256':sha_bytes(wav.read_bytes()),'duration_seconds':duration,'sample_rate':44100,'channels':1}

def run(project,version='v01',preflight=False,voice=None,confirm_voice_change=False,provider='auto',speech_rate=None,join_lines=False,directive=None,no_directive=False):
    project=Path(project).resolve()
    workspace=workspace_for(project)
    voice=select_voice(project,voice)
    if voice not in VOICES: raise ValueError('Unknown voice; use dayi or xiaohe.')
    voice_id=VOICES[voice]
    if not re.fullmatch(r'v\d{2,}',version): raise ValueError('Invalid version.')
    text=(project/'brief/narration.txt').read_text(encoding='utf-8').strip()
    if not text: raise ValueError('Locked narration is empty.')
    text_hash=sha_bytes(text.encode('utf-8'))
    # 段间换行会被读成额外停顿：--join-lines 只把换行去掉，逐字内容必须完全不变（下面用去标点后的字符序列校验）。
    tts_text=text
    text_transform='as_is'
    if join_lines:
        tts_text=''.join(line.strip() for line in text.splitlines() if line.strip())
        keep=lambda v: re.sub(r'[^一-鿿A-Za-z0-9]','',v)
        if keep(tts_text)!=keep(text):
            raise ValueError('join-lines 改变了正文字符，拒绝提交')
        text_transform='paragraphs_joined'
    tts_hash=sha_bytes(tts_text.encode('utf-8'))
    provider=resolve_provider(workspace,provider)
    if voice=='yichen' and provider!='volcengine':
        raise ValueError('机构宣传片的儒雅逸辰只使用火山通道，请配置火山或指定 --provider volcengine。')
    if provider=='edge':
        return run_edge(project,workspace,text,text_hash,version,preflight,voice,confirm_voice_change)
    profile=json.loads((SKILL/'upstream/openmontage-audio/voice-profile.json').read_text(encoding='utf-8'))
    rate,rate_source=speech_rate_for(voice,profile,speech_rate)
    # 语音指令：命令行为准 > 音色默认配方 > 无。--no-directive 用于对照实验，正式成片不要用。
    if no_directive and directive: raise ValueError('--no-directive 与 --context-texts 不能同时使用。')
    if no_directive: directive,directive_source=None,'disabled'
    elif directive: directive_source='cli_override'
    elif voice in VOICE_DIRECTIVES: directive,directive_source=VOICE_DIRECTIVES[voice],'voice_recipe'
    else: directive,directive_source=None,'none'
    profile=dict(profile); profile['speech_rate']=rate
    target=project/'assets/audio'/f'narration-volcengine-{voice}-full-{version}.mp3'
    summary={'provider':'volcengine','voice':voice,'text_sha256':text_hash,'text_characters':len(text),
             'utf16_units':utf16_length(text),'full_body':True,'single_submission':True,
             'speech_rate':rate,'speed_multiplier':speed_multiplier(rate),'speech_rate_source':rate_source,
             'text_transform':text_transform,'tts_text_sha256':tts_hash,
             'voice_directive':directive,'voice_directive_source':directive_source,
             'output':str(target),'segmentation_allowed':False,
             'institutional_directive':INSTITUTIONAL['directive'] if voice=='yichen' else None}
    if preflight:
        values=load_private(workspace)
        check_private_voice(values)
        summary.update({'credential_present':True,'voice_id':voice_id,'speech_rate':profile['speech_rate'],
                        'speed_multiplier':speed_multiplier(profile['speech_rate']),'speech_rate_source':rate_source})
        print(json.dumps(summary,ensure_ascii=False)); return summary
    if target.exists():
        metadata=json.loads(target.with_suffix('.mp3.json').read_text(encoding='utf-8'))
        recorded=metadata.get('input_text_sha256') or metadata.get('text_sha256')
        if recorded!=text_hash or metadata.get('audio_sha256')!=sha_bytes(target.read_bytes()):
            raise ValueError('Existing candidate hash mismatch; no automatic resubmission.')
        if metadata.get('voice_id')!=voice_id or metadata.get('speech_rate')!=profile['speech_rate']:
            raise ValueError('Existing Volcengine parameters differ.')
        duration,_=verify_audio(target)
        master=ensure_wav(target)
        metadata['wav_master']=master
        target.with_suffix('.mp3.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        summary.update({'reused':True,'duration_seconds':duration,'wav_master':master['path']})
        print(json.dumps(summary,ensure_ascii=False)); return summary
    if target.with_suffix('.mp3.json').exists(): raise ValueError('Existing failure/receipt prevents duplicate submission; use explicit new version only when authorized.')
    if other_voice_receipt(project,text_hash,voice_id) and not confirm_voice_change:
        raise ValueError('Same narration already synthesized with another voice; changing voice needs explicit user approval (--confirm-voice-change).')
    target.parent.mkdir(parents=True,exist_ok=True)
    values=load_private(workspace)
    check_private_voice(values)
    sys.path.insert(0,str(SKILL/'upstream/openmontage-audio'))
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from directives import DoubaoTTSWithDirectives
    print('Submitting one full-body Volcengine task.',flush=True)
    tts_class=broadcast_tts_class() if voice=='yichen' else DoubaoTTSWithDirectives
    result=tts_class().execute({'text':tts_text,'voice_id':voice_id,
        'resource_id':profile['resource_id'],'speech_rate':profile['speech_rate'],
        'format':'mp3','sample_rate':profile['sample_rate'],'enable_timestamp':True,
        'context_texts':directive,
        'voice_validation':profile['voice_validation'],'output_path':str(target),
        'timeout_seconds':300,'poll_interval_seconds':2.0,'user_id':'huashu-art-motion'})
    receipt=target.with_suffix('.mp3.json')
    if receipt.exists():
        raw=json.loads(receipt.read_text(encoding='utf-8'))
        raw=scrub(raw,[values['DOUBAO_SPEECH_API_KEY']])
        receipt.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if not result.success:
        # Do not print arbitrary upstream exception text or auth context.
        safe=scrub({'stage':result.data.get('error_context',{}).get('stage','unknown'),
                    'error':result.error},[values['DOUBAO_SPEECH_API_KEY']])
        print(json.dumps(safe,ensure_ascii=False))
        raise RuntimeError('Volcengine task failed; preserve receipt and do not resubmit automatically.')
    provider_receipt=json.loads(receipt.read_text(encoding='utf-8'))
    metadata={'provider':'volcengine_doubao','input_text_sha256':text_hash,
        'voice_id':voice_id,'resource_id':profile['resource_id'],
        'institutional_directive':INSTITUTIONAL['directive'] if voice=='yichen' else None,
        'speech_rate':profile['speech_rate'],'speed_multiplier':speed_multiplier(profile['speech_rate']),
        'speech_rate_source':rate_source,
        'voice_directive':directive,'voice_directive_source':directive_source,
        'text_transform':text_transform,'tts_text_sha256':tts_hash,
        'request_count':1,'full_body':True,'synthesis_segmentation':False,
        'task_id':result.data.get('task_id'),'source':'Why-HandDrawn-Video/upstream/SOURCES.json',
        'voice_validation':'user_confirmed_source_profile',
        'provider_query':provider_receipt,'independent_asr_verified':False,
        'human_review':'pending'}
    duration,streams=verify_audio(target)
    metadata.update({'audio_sha256':sha_bytes(target.read_bytes()),'duration_seconds':duration,
                     'decode_passed':True,'streams':streams})
    master=ensure_wav(target)
    metadata['wav_master']=master
    target.with_suffix('.mp3.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary.update({'duration_seconds':duration,'decode_passed':True,'reused':False,'wav_master':master['path']})
    print(json.dumps(summary,ensure_ascii=False)); return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',required=True)
    parser.add_argument('--version',default='v01')
    parser.add_argument('--provider',default='auto',choices=('auto','volcengine','edge'),help='auto=配了火山密钥用火山、没配用免费微软语音；也可在工作区 .hdv-workspace.json 写 tts_provider 固定')
    parser.add_argument('--voice',default=None,choices=sorted(VOICES),help='dayi=大壹（男讲述者，默认）；xiaohe=小何 2.0（女讲述者，含女学生、妈妈）；性别不明的学生第一人称稿用 xiaohe。')
    parser.add_argument('--confirm-voice-change',action='store_true',help='同一全文已用另一音色合成过，用户明确同意换声再合成时才加')
    parser.add_argument('--speech-rate',type=int,default=None,help='火山 audio_params.speech_rate，[-50,100]，100=2.0 倍速。不填则按音色默认：大壹/小何 10。只在用户明确要求改语速时使用，值会写进回执')
    parser.add_argument('--context-texts',default=None,help='覆盖音色默认语音指令（additions.context_texts）。当前音色默认不带指令；改前先跑 audition_variants.py 横评')
    parser.add_argument('--no-directive',action='store_true',help='关闭音色默认语音指令，仅用于对照实验；正式成片不要用')
    parser.add_argument('--join-lines',action='store_true',help='只去掉 brief/narration.txt 的段间换行（逐字不变，脚本会校验），用于消除段末换行造成的额外停顿；口播原文不改')
    parser.add_argument('--preflight',action='store_true')
    args=parser.parse_args()
    try:
        run(args.project,args.version,args.preflight,args.voice,args.confirm_voice_change,args.provider,
            args.speech_rate,args.join_lines,args.context_texts,args.no_directive)
        if not args.preflight:
            print('下一步（顺序不能省）：')
            print('  1) 跑 check_voice.py（含 ASR），把试听消息发给用户后结束本轮回复，等用户试听。')
            print('  2) 用户明确说通过后才运行 lock_voice.py。没锁定前不写表演表、不生图。')
    except Exception as exc:
        # Credential-bearing transport errors are never echoed.
        print(json.dumps({'success':False,'error_type':type(exc).__name__,'resubmit_allowed':False}))
        raise SystemExit(1)
