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
from common import find_workspace

def workspace_for(project):
    project=Path(project).resolve()
    workspace=find_workspace(project)
    if workspace is None:
        workspace=next((p.parent for p in project.parents if p.name=='projects'), None)
    if workspace is None or not project.is_relative_to(workspace/'projects'):
        raise ValueError('Project must be inside the selected workspace projects directory.')
    return workspace

VOICES = {'dayi': 'zh_male_dayi_uranus_bigtts', 'xiaohe': 'zh_female_xiaohe_uranus_bigtts',
          'jitang': 'zh_female_jitangnv_uranus_bigtts'}   # 大壹（默认）；小何 2.0（女学生第一人称口吻）；鸡汤女 2.0（家长角度且家长是妈妈）


def check_private_voice(values):
    if values.get('DOUBAO_SPEECH_VOICE_TYPE') not in VOICES.values():
        raise ValueError('Private voice is not an approved voice (dayi/xiaohe/jitang).')


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

def run(project,version='v01',preflight=False,voice='dayi',confirm_voice_change=False,provider='auto'):
    project=Path(project).resolve()
    workspace=workspace_for(project)
    if voice not in VOICES: raise ValueError('Unknown voice; use dayi, xiaohe or jitang.')
    voice_id=VOICES[voice]
    if not re.fullmatch(r'v\d{2,}',version): raise ValueError('Invalid version.')
    text=(project/'brief/narration.txt').read_text(encoding='utf-8').strip()
    if not text: raise ValueError('Locked narration is empty.')
    text_hash=sha_bytes(text.encode('utf-8'))
    provider=resolve_provider(workspace,provider)
    if provider=='edge':
        return run_edge(project,workspace,text,text_hash,version,preflight,voice,confirm_voice_change)
    profile=json.loads((SKILL/'upstream/openmontage-audio/voice-profile.json').read_text(encoding='utf-8'))
    target=project/'assets/audio'/f'narration-volcengine-{voice}-full-{version}.mp3'
    summary={'provider':'volcengine','voice':voice,'text_sha256':text_hash,'text_characters':len(text),
             'utf16_units':utf16_length(text),'full_body':True,'single_submission':True,
             'output':str(target),'segmentation_allowed':False}
    if preflight:
        values=load_private(workspace)
        check_private_voice(values)
        summary.update({'credential_present':True,'voice_id':voice_id,'speech_rate':profile['speech_rate']})
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
    from tools.audio.doubao_tts import DoubaoTTS
    print('Submitting one full-body Volcengine task.',flush=True)
    result=DoubaoTTS().execute({'text':text,'voice_id':voice_id,
        'resource_id':profile['resource_id'],'speech_rate':profile['speech_rate'],
        'format':'mp3','sample_rate':profile['sample_rate'],'enable_timestamp':True,
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
        'speech_rate':profile['speech_rate'],'speed_multiplier':1.1,
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
    parser.add_argument('--voice',default='dayi',choices=sorted(VOICES),help='dayi=大壹（默认）；xiaohe=小何 2.0，仅学生第一人称且为女生或性别不明的稿子；jitang=鸡汤女 2.0，仅家长角度且家长是妈妈的稿子（家长是爸爸用 dayi）')
    parser.add_argument('--confirm-voice-change',action='store_true',help='同一全文已用另一音色合成过，用户明确同意换声再合成时才加')
    parser.add_argument('--preflight',action='store_true')
    args=parser.parse_args()
    try: run(args.project,args.version,args.preflight,args.voice,args.confirm_voice_change,args.provider)
    except Exception as exc:
        # Credential-bearing transport errors are never echoed.
        print(json.dumps({'success':False,'error_type':type(exc).__name__,'resubmit_allowed':False}))
        raise SystemExit(1)
