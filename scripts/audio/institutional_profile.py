"""机构宣传片默认声音；仅显式内容类型启用，普通项目兼容。"""
import json
from pathlib import Path

PROFILE = {
    'voice': 'yichen', 'voice_id': 'zh_male_ruyayichen_uranus_bigtts', 'speech_rate': 0,
    'directive': '请用学校、教育局官网宣传片的正式播音风格朗读：普通话标准、吐字清晰、沉稳端正，采用新闻播报式的停连和重音，语气客观克制，不用聊天口吻，不夸张煽情。引号内的内容按引用陈述处理，不模仿角色。',
}

def select_voice(project, explicit=None):
    if explicit:
        return explicit
    cfg = Path(project) / 'design/config.json'
    data = json.loads(cfg.read_text(encoding='utf-8')) if cfg.is_file() else {}
    return 'yichen' if data.get('content_type') == 'institutional_promo' else 'dayi'

def broadcast_tts_class():
    from tools.audio.doubao_tts import DoubaoTTS
    class BroadcastTTS(DoubaoTTS):
        def _submit_body(self, inputs, *, voice_id, request_id):
            body = super()._submit_body(inputs, voice_id=voice_id, request_id=request_id)
            additions = json.loads(body['req_params']['additions'])
            additions['context_texts'] = [PROFILE['directive']]
            body['req_params']['additions'] = json.dumps(additions, ensure_ascii=False)
            return body
    return BroadcastTTS
