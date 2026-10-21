"""音频时钟：由配音的词级时间戳得到"每个字"的起止秒；T(短语) 返回该短语在口播里的 (起, 止) 秒。
时间戳来源：火山 Doubao Speech 2.0 submit/query 返回的 data.sentences[].words[]（startTime/endTime，单位秒）。
口播原文去掉标点后必须与时间戳逐字一致，否则直接报错——不一致说明配音文本被改动过，时间轴不可信。"""
import json, re
from pathlib import Path

_strip = lambda s: re.sub(r'[^一-鿿A-Za-z0-9]', '', s)
# 供应商识别文本把阿拉伯数字 0–9 写成汉字（3→三）。只做这一种归一，比较时两边同时归一；其他差异仍报错。
_DIG = str.maketrans('0123456789', '〇一二三四五六七八九')
# 供应商词文本同音变体归一（2026-10-19，shoebox211 项目实测）：火山把口播数字串里的 1 写成"幺"、"刹车"写成"杀"。
# 只做字音等价归一用于校验比对，不改口播原文；遇到新的变体请同步项目的 design/hdv/clock.py。
_VAR = str.maketrans({'幺': '一', '杀': '刹'})
# 供应商数字读法变体（2026-10-20，chuer-xiuxue-keyhigh 项目实测）：火山把"2个月"读成"两个月"、"12个小时"读成"十二个小时"；
# 源稿阿拉伯数字经 _DIG 按位归一为"二/一二"，与供应商按数词读法不一致。两侧同时归一，仅用于校验比对。
_NUM_FIX = ((re.compile('十二'), '一二'), (re.compile('两'), '二'))


def _num_norm(s):
    for _pat, _rep in _NUM_FIX:
        s = _pat.sub(_rep, s)
    return s


_norm = lambda s: _num_norm(_strip(s).translate(_DIG).translate(_VAR))


class Clock:
    def __init__(self, narration_txt, volc_json):
        d = json.loads(Path(volc_json).read_text(encoding='utf-8'))
        # generate_candidate.py 把火山 query 响应存在 provider_query.data 下；旧格式顶层 data 也兼容
        data = d.get('data') or d.get('provider_query', {}).get('data') or {}
        self.chars = []                      # (字, 起, 止)
        for s in data['sentences']:
            for w in s['words']:
                t = _strip(w['word'])
                for k, ch in enumerate(t):
                    n = len(t)
                    a = w['startTime'] + (w['endTime'] - w['startTime']) * k / n
                    b = w['startTime'] + (w['endTime'] - w['startTime']) * (k + 1) / n
                    self.chars.append((ch, a, b))
        # 供应商侧按整串归一：_norm 含多字变体规则（如"十二"→"一二"），逐字调用匹配不上；
        # 源侧 src 同样是整串归一，两侧规则一致。所有变体规则均保持字数不变，字符位置不错位。
        self.text = _norm(''.join(c[0] for c in self.chars))
        self.lines = [l for l in Path(narration_txt).read_text(encoding='utf-8').splitlines() if l.strip()]
        src = _norm(' '.join(self.lines))
        if self.text != src:
            raise SystemExit('词级时间戳与口播原文不一致：配音文本与 brief/narration.txt 不同，请重新核对。')
        self.end = self.chars[-1][2]

    @staticmethod
    def strip(s):
        return _norm(s)

    def T(self, phrase, nth=0, last=False):
        """短语（可含标点，会被去掉）在口播里的 (起, 止) 秒。nth=第几次出现；last=取最后一次。找不到直接报错。"""
        q = _norm(phrase)
        idx = [i for i in range(len(self.text)) if self.text.startswith(q, i)]
        if not idx:
            raise SystemExit(f'口播里找不到：{phrase}')
        i = idx[-1] if last else idx[nth]
        return round(self.chars[i][1], 3), round(self.chars[i + len(q) - 1][2], 3)

    def line_span(self, k):
        """第 k 行口播（从 0 起）的 (起, 止) 秒。"""
        pos = 0
        for j, l in enumerate(self.lines):
            n = len(_norm(l))
            if j == k:
                return round(self.chars[pos][1], 3), round(self.chars[pos + n - 1][2], 3)
            pos += n
        raise IndexError(k)
