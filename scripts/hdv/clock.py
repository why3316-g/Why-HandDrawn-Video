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
_VAR = str.maketrans({'幺': '一', '杀': '刹', '启': '企'})   # 启→企：kandekai-mama 实测，火山把"企鹅加油"写作"启鹅加油"
# 供应商数字读法变体（2026-10-20，chuer-xiuxue-keyhigh 项目实测）：火山把"2个月"读成"两个月"、"12个小时"读成"十二个小时"；
# 源稿阿拉伯数字经 _DIG 按位归一为"二/一二"，与供应商按数词读法不一致。两侧同时归一，仅用于校验比对。
# 2026-10-21（kandekai-mama 项目实测）新增：15岁→十五岁、16岁→十六岁、800米→八百米、10分钟→十分钟、20分钟→二十分钟。
# 注意顺序：'二十分钟' 必须先于 '十分钟'，否则 '二十分钟' 会被 '十分钟' 规则误改写成 '二一零分钟'。
# 2026-10-21（teji-3buhui 项目实测）新增：源稿"第17名"经 _DIG 按位归一为"第一七名"，火山按数词读法写作"第十七名"。
# 规则保持等长（第十七 → 第一七，三字换三字），字符与时间位置不错开；放在末尾，兼容前面已把"十二"改写掉的情况。
_NUM_FIX = ((re.compile('二十分钟'), '二〇分钟'), (re.compile('十分钟'), '一〇分钟'), (re.compile('十二'), '一二'),
            (re.compile('十五'), '一五'), (re.compile('十六'), '一六'), (re.compile('八百'), '八〇〇'), (re.compile('两'), '二'),
            (re.compile('第十([一二三四五六七八九])'), r'第一\1'))


def _num_norm(s):
    for _pat, _rep in _NUM_FIX:
        s = _pat.sub(_rep, s)
    return s


_norm = lambda s: _num_norm(_strip(s).translate(_DIG).translate(_VAR))


def _apply_variants(chars):
    """对 (字, 起, 止) 序列应用 _DIG/_VAR 与 _NUM_FIX 变体，并把被改写片段的时间窗均分给新字列。
    2026-10-21（kandekai-mama）：火山把"15岁"读成"十五岁"、"800米"读成"八百米"，这类读法变体会改变字数，
    逐字/等长归一都对不上；改为在字序列上整体归一，被替换的 k 个字的时间窗 [首字起, 末字止] 均分给 m 个新字。"""
    cs = [[ch.translate(_DIG).translate(_VAR), a, b] for ch, a, b in chars]
    for pat, rep in _NUM_FIX:
        i = 0
        while i < len(cs):
            seg = ''.join(c[0] for c in cs[i:])
            mobj = pat.search(seg)
            if not mobj:
                break
            j = i + mobj.start()                     # 被替换片段 [j, j+k)
            k = mobj.end() - mobj.start()
            # 规则可能带反向引用（如 '第十([一二三四五六七八九])' → r'第一\1'），必须走 expand 才能取到实际替换串
            rep_s = mobj.expand(rep)
            m = len(rep_s)
            a, b = cs[j][1], cs[j + k - 1][2]
            new = [[rep_s[p], a + (b - a) * p / m, a + (b - a) * (p + 1) / m] for p in range(m)]
            cs = cs[:j] + new + cs[j + k:]
            i = j + m
    return [(c[0], c[1], c[2]) for c in cs]


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
        # 供应商侧按整串归一（2026-10-21 起用 _apply_variants 在字序列上做，含会改变字数的读法变体，
        # 时间窗均分重映射；源侧 src 仍用 _norm 整串归一，两侧结果一致）。
        self.chars = _apply_variants(self.chars)
        self.text = ''.join(c[0] for c in self.chars)
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
