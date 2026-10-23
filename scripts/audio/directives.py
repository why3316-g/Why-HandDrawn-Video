"""给上游 DoubaoTTS 请求体补「2.0 音色可用的表达参数」，不改 upstream 代码。

火山 HTTP V3 文档（docs.volcengine.com/docs/6561/1598757）里，TTS 2.0 预设音色能调的只有：
  audio_params.speech_rate / loudness_rate / emotion / emotion_scale
  additions.context_texts（语音指令，仅第一个值生效、不计费）/ post_process.pitch / silence_duration
其中 mute_cut_*（服务端裁静音）明确不支持 2.0 音色，emotion 在多数 2.0 预设音色上被接受但无实际效果。

上游 tools/audio/doubao_tts.py 的 _submit_body 只写了 format/sample_rate/speech_rate/enable_timestamp，
这里用子类补字段，保持 upstream 原样可校验（见 references/PROVENANCE.md 的哈希登记要求）。
"""
import json

from tools.audio.doubao_tts import DoubaoTTS


class DoubaoTTSWithDirectives(DoubaoTTS):
    """支持 context_texts / post_process.pitch / emotion / loudness_rate 的子类。"""

    def _submit_body(self, inputs, *, voice_id, request_id):
        body = super()._submit_body(inputs, voice_id=voice_id, request_id=request_id)
        rp = body['req_params']
        ap = rp['audio_params']
        add = json.loads(rp['additions'])
        if inputs.get('loudness_rate') is not None:
            ap['loudness_rate'] = int(inputs['loudness_rate'])
        if inputs.get('emotion'):
            ap['emotion'] = inputs['emotion']
            ap['emotion_scale'] = int(inputs.get('emotion_scale') or 4)
        if inputs.get('pitch') is not None:
            add['post_process'] = {'pitch': int(inputs['pitch'])}
        ct = inputs.get('context_texts')
        if ct:
            # 官方说明：字符串列表只第一个值有效
            add['context_texts'] = [ct] if isinstance(ct, str) else list(ct)[:1]
        rp['additions'] = json.dumps(add, ensure_ascii=False)
        return body
