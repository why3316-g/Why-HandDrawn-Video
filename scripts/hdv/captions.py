"""字幕：由"手工断句"和词级时间戳得到每条字幕的起止秒。
断句由 AI 或人工按语义写在 design/breaks.json（每行口播一个列表，每条 3–13 字，不在词中间断开）；
本函数校验"断句拼起来去掉标点 = 口播去掉标点"，再按字取时间。标点在显示时换成空格。"""
import re


def captions_from_breaks(clock, breaks):
    lines = clock.lines
    if len(breaks) != len(lines):
        raise SystemExit(f'断句行数 {len(breaks)} 与口播行数 {len(lines)} 不一致')
    pos, out = 0, []
    for i, (line, chunks) in enumerate(zip(lines, breaks)):
        if clock.strip(''.join(chunks)) != clock.strip(line):
            raise SystemExit(f'第 {i + 1} 行断句拼接后与口播不一致')
        for c in chunks:
            n = len(clock.strip(c))
            seg = clock.chars[pos:pos + n]
            text = re.sub(r'\s+', ' ', re.sub(r'[，。；：？！"“”]', ' ', c)).strip()
            out.append({'start': round(seg[0][1], 3), 'end': round(seg[-1][2], 3), 'text': text})
            pos += n
    for a, b in zip(out, out[1:]):                     # 相邻字幕间隙很小时，前一条顺延到下一条起点（避免闪烁）
        gap = b['start'] - a['end']
        if gap < .12:
            a['end'] = b['start']
    return out
