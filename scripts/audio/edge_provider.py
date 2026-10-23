"""免费微软语音（edge-tts）：不需要密钥，适合没有火山账号的用户；效果和稳定性不如火山。

edge-tts 调用微软 Edge 在线朗读接口，不是官方付费 API，微软随时可能改动接口：出现 403 先 `pip install -U edge-tts`。
输出与火山候选同一格式（mp3 + 回执 json，词级时间戳放 provider_query.data.sentences[].words[]），后续 Clock、check_voice、混音流程不用区分来源。"""
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path

EDGE_VOICES = {'dayi': 'zh-CN-YunxiNeural', 'xiaohe': 'zh-CN-XiaoxiaoNeural',
               'wenroumama': 'zh-CN-XiaoxiaoNeural'}   # 音色槽位：dayi=男声，xiaohe=女声，wenroumama=家长女声（微软无成熟妈妈音色，复用晓晓；正式成片必须走火山）
EDGE_RATE = '+10%'                                                              # 对应火山语速 1.1
MIN_EDGE_TTS = (7, 3, 1)                                                        # 7.2.x 实测被微软接口 403
_STRIP = lambda s: re.sub(r'[^一-鿿A-Za-z0-9]', '', s)
_END = '。！？!?…'


def edge_version():
    try:
        import edge_tts
        return tuple(int(x) for x in edge_tts.__version__.split('.')[:3])
    except Exception:
        return None


def proxy_from_env():
    return os.environ.get('HDV_PROXY') or os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy') or os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy') or None


async def _stream(text, voice, out_path, proxy):
    import edge_tts
    words = []
    comm = edge_tts.Communicate(text, voice, rate=EDGE_RATE, boundary='WordBoundary', proxy=proxy)
    with open(out_path, 'wb') as f:
        async for m in comm.stream():
            if m['type'] == 'audio':
                f.write(m['data'])
            elif m['type'] == 'WordBoundary':
                words.append({'text': m['text'], 'start': m['offset'] / 1e7, 'dur': m['duration'] / 1e7})
    return words


def build_sentences(narration, words):
    """把词边界对齐回带标点的原文：词后面的标点并入该词，句末标点处断句；对不上原文则报错。"""
    pos, tokens = 0, []
    for w in words:
        t = _STRIP(w['text'])
        if not t:
            continue
        while pos < len(narration) and not _STRIP(narration[pos]):
            pos += 1
        got = ''
        while pos < len(narration) and len(got) < len(t):
            if _STRIP(narration[pos]):
                got += narration[pos]
            pos += 1
        if got != t:
            raise ValueError(f'微软语音词边界与原文不一致：{t!r} ≠ {got!r}')
        tail = ''
        while pos < len(narration) and not _STRIP(narration[pos]):
            tail += narration[pos]
            pos += 1
        tokens.append({'word': t + tail.strip(), 'startTime': round(w['start'], 3), 'endTime': round(w['start'] + w['dur'], 3)})
    sentences, cur = [], []
    for tok in tokens:
        cur.append(tok)
        if tok['word'] and tok['word'][-1] in _END:
            sentences.append(cur); cur = []
    if cur:
        sentences.append(cur)
    return [{'text': ''.join(t['word'] for t in s), 'startTime': s[0]['startTime'], 'endTime': s[-1]['endTime'], 'words': s} for s in sentences]


def synthesize(text, voice_slot, target, proxy=None):
    """合成并写出 mp3，返回词级句子列表。失败抛异常，由调用方保留现场、不自动重复提交。"""
    sentences = None
    words = asyncio.run(_stream(text, EDGE_VOICES[voice_slot], str(target), proxy))
    if not words:
        raise RuntimeError('微软语音没有返回词级时间戳')
    sentences = build_sentences(text, words)
    return sentences
