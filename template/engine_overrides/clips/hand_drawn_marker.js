// Why-HandDrawn-Video · 白板手绘渲染语法（C 线稿 + 握笔手逐笔画出）。结构取自 Codex 为小凯项目写的 xiaokai_C_whiteboard_v08.js：
// 一条连续横向白板，每个镜头一块画板（画幅布局由 spec.data.layout 决定），相机在板间平移；人物线稿由骨架提取出的笔画路径逐笔描出；文字逐字手写；道具由线条画出；深色字幕条。
// 与 v08 的区别：①不含小凯的场景脚本、品牌徽标合成、旧时间重映射；②所有事件时间直接用音轨绝对时间（spec.data.events，由 design/film.py 依词级时间戳生成）。
// 竖屏视觉常量见 references/STYLE_SPEC.md，宽屏见 references/LANDSCAPE_SPEC.md；改动本文件 = 改动风格，须走改编申请。
// 依赖 Skill 库：DG（drawPartial/zigzag/revealMask/hand/cum/pointAt/arcPts）、U。
CLIPS.hand_drawn_marker = (() => {
  const INK = '#171717', OR = '#ed7929', BG = '#ffffff';
  // 旧项目没有 data.layout 时保留原竖屏视觉；新项目由 Python 的唯一布局配置传入。
  let L = null, PANEL = 1120;
  const LEGACY = {mode:'portrait',width:1080,height:1920,panel_width:1120,content_top:285,content_bottom:1455,
    separator_y:1430,separator_x:[120,925],clock:[932,322,24],caption_top:1438,caption_height:80,caption_baseline:1494,
    caption_size:52,caption_small_size:48,header_x:85,header_first_y:[245,308],header_other_y:250,pen_enter_x:1280,pen_enter_bottom:1350};
  let ringImages = {}, ringTints = {}, strokes = [], hand, tip = [147, 119], scenes = [], spriteMeta = {}, spriteSources = {}, spriteBuffers = {};
  const smooth = (a, b, t) => { const p = U.clamp((t - a) / (b - a)); return p * p * (3 - 2 * p); };
  function handPose(pen, layout) {
    // 手臂轴向：竖屏与宽屏同一套（2026-10-26 用户定稿）——从右下斜向上约 45°，不再按画幅分两套。
    // 具体旋转角按素材实测写在 spec.data.handRotation（度，顺时针为正）；缺省 0 = 保持素材原姿态。
    // armAngle 只用于自检/测试，汇报"这条手臂被摆到多少度"，已确定是 45°。
    return { rotation: 0, scale: layout.mode === 'landscape' ? .18 : .34, armAngle: Math.PI / 4 };
  }
  function addLine(e, off) {
    const pts = e.p.map(([x, y]) => [x + off, y]), p = e.curved === false ? pts : DG.hand(pts, { amp: .65, seed: e.seed, per: 7 }), cum = DG.cum(p);
    const pressure = Array.isArray(e.pressure) && e.pressure.length === p.length ? e.pressure : null;
    const accents = (e.accents || []).map(a => { const ap = a.p.map(([x,y]) => [x + off,y]); const ac = DG.cum(ap); return {...a,p:ap,cum:ac,len:ac.at(-1)}; });
    strokes.push({ kind: 'line', p, cum, len: cum.at(-1), at: e.at, dur: e.dur, color: e.color || INK, width: e.width || 6, pressure, dryBrush: !!e.dryBrush, accents, ringAsset: e.ringAsset, ringBox: e.ringBox ? [e.ringBox[0]+off,e.ringBox[1],e.ringBox[2],e.ringBox[3]] : null, ringStart: e.ringStart, index: e.index });
  }
  function drawPressureLine(g, s, q) {
    const amount = s.len * q, tip = DG.pointAt(s.p, s.cum, amount);
    for (let i = 1; i < s.p.length && s.cum[i - 1] < amount; i++) {
      const a = s.p[i - 1], b = s.p[i], seg = s.cum[i] - s.cum[i - 1];
      if (!seg) continue;
      const f = Math.min(1, (amount - s.cum[i - 1]) / seg), end = [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
      const w = Math.max(.35, (s.pressure[i - 1] + s.pressure[i]) / 2);
      if (s.dryBrush && w > 1.5) {
        const nx = -(b[1] - a[1]) / seg, ny = (b[0] - a[0]) / seg;
        // 核心笔墨叠上细丝：保留有力的下沿与真实飞白的间隙。
        g.lineWidth = Math.max(.5, w * .55); g.beginPath(); g.moveTo(...a); g.lineTo(...end); g.stroke();
        for (let j = 0; j < 9; j++) {
          // 以固定相位画稀疏笔丝，逐帧确定；保留白纸飞白，不覆盖别的内容。
          if (Math.sin(i * .17 + j * 2.31) < -.77) continue;
          const shift = (j - 4) * w * .105;
          g.lineWidth = Math.max(.4, w * (.075 + .018 * Math.sin(j * 2.4 + i * .045)));
          g.beginPath(); g.moveTo(a[0] + nx * shift, a[1] + ny * shift); g.lineTo(end[0] + nx * shift, end[1] + ny * shift); g.stroke();
        }
      } else {
        g.lineWidth = w; g.beginPath(); g.moveTo(...a); g.lineTo(...end); g.stroke();
      }
    }
    for (const a of s.accents) {
      const aq = U.clamp((q - a.start) / Math.max(.0001, a.end - a.start));
      if (aq > 0) { g.lineWidth = a.width; DG.drawPartial(g, a.p, a.cum, a.len * aq); }
    }
    return tip;
  }
  // 原笔迹与笔尖共享同一角度进度，完成时显示完整原图；旧事件仍走原线条逻辑。
  function ringTip(s, q) {
    const t = U.clamp(q) * (s.p.length - 1), i = Math.min(s.p.length - 2, Math.floor(t)), f = t - i;
    return [s.p[i][0] + (s.p[i+1][0] - s.p[i][0]) * f, s.p[i][1] + (s.p[i+1][1] - s.p[i][1]) * f];
  }
  function drawOriginalRing(g, s, q) {
    let image = ringImages[s.ringAsset];
    if (!image) throw new Error('缺少已审核圈画原稿 ' + s.ringAsset);
    if (q <= 0) return;
    // 橙色保留原稿 RGB；历史显式墨色调用按原笔迹透明度着色，不退回规则椭圆。
    if (s.color !== OR) {
      const key = s.ringAsset + ':' + s.color;
      if (!ringTints[key]) {
        const cv = document.createElement('canvas'); cv.width = image.width; cv.height = image.height;
        const c = cv.getContext('2d'); c.drawImage(image, 0, 0);
        const im = c.getImageData(0, 0, cv.width, cv.height), a = im.data;
        for (let k=0;k<a.length;k+=4) a[k+3] *= (255 - Math.min(a[k],a[k+1],a[k+2])) / 255;
        c.putImageData(im,0,0); c.globalCompositeOperation='source-in'; c.fillStyle=s.color; c.fillRect(0,0,cv.width,cv.height);
        ringTints[key] = cv;
      }
      image = ringTints[key];
    }
    const [x,y,w,h] = s.ringBox, cx=x+w/2, cy=y+h/2;
    g.save();
    if (q < 1) {
      g.beginPath(); g.moveTo(cx,cy);
      g.ellipse(cx,cy,w*2,h*2,0,s.ringStart,s.ringStart+q*Math.PI*2,false);
      g.closePath(); g.clip();
    }
    g.globalCompositeOperation='multiply'; g.drawImage(image,x,y,w,h); g.restore();
  }
  function isolateForComposite(image, rect) {            // 取 rect 区域，把与边缘相连的近白色背景去掉（衣服里面的白色保留）
    const cv = document.createElement('canvas'); cv.width = rect[2]; cv.height = rect[3]; const c = cv.getContext('2d'); c.drawImage(image, ...rect, 0, 0, cv.width, cv.height);
    const im = c.getImageData(0, 0, cv.width, cv.height), a = im.data, w = cv.width, h = cv.height, n = w * h, seen = new Uint8Array(n), queue = new Int32Array(n); let first = 0, last = 0;
    const nearWhite = i => a[i * 4] > 235 && a[i * 4 + 1] > 235 && a[i * 4 + 2] > 235;
    const add = i => { if (!seen[i] && nearWhite(i)) { seen[i] = 1; queue[last++] = i; } };
    for (let x = 0; x < w; x++) { add(x); add((h - 1) * w + x); } for (let y = 0; y < h; y++) { add(y * w); add(y * w + w - 1); }
    while (first < last) { const i = queue[first++], x = i % w, y = Math.floor(i / w); if (x) add(i - 1); if (x < w - 1) add(i + 1); if (y) add(i - w); if (y < h - 1) add(i + w); }
    for (let i = 0; i < n; i++) if (seen[i]) a[i * 4 + 3] = 0;
    c.putImageData(im, 0, 0); return cv;
  }
  function addSprite(id, x, y, h, at, dur, index) {
    const meta = spriteMeta[id]; if (!meta) throw new Error('缺少人物笔画 ' + id);
    const scale = h / meta.rect[3], w = meta.rect[2] * scale, parts = []; let total = 0, last = null;
    for (const points of meta.paths) {
      if (last) { const distance = Math.hypot(points[0][0] - last[0], points[0][1] - last[1]);
        if (distance > 1) { const p = [last, points[0]], cum = DG.cum(p), len = distance * .24; parts.push({ ink: false, p, cum, distance, len, from: total }); total += len; } }
      const cum = DG.cum(points), distance = cum.at(-1); parts.push({ ink: true, p: points, cum, distance, len: distance, from: total }); total += distance; last = points.at(-1);
    }
    // 分区补满：meta.split（可选）把人物分成左(0)右(1)两组；每组各自"已画完的行补满"，先画完的一侧（如先画孩子再画妈妈）不会留白，也不会等到整张画完才突然补色
    const split = meta.split || 0, H0 = meta.rect[3], rt = [H0, H0];
    for (const part of parts) part.grp = !split || !part.ink ? 0 : (part.p.reduce((a, p) => a + p[0], 0) / part.p.length < split ? 0 : 1);
    for (let i = parts.length - 1; i >= 0; i--) { if (parts[i].ink) rt[parts[i].grp] = Math.min(rt[parts[i].grp], ...parts[i].p.map(p => p[1])); parts[i].rt = [rt[0], rt[1]]; }
    strokes.push({ kind: 'sprite', id, x, y, w, h, scale, at, dur, parts, total, index, first: meta.paths[0]?.[0] || [0, 0], last: meta.paths.at(-1)?.at(-1) || [0, 0] });
  }
  const spriteEnds = (s, first) => { const p = first ? s.first : s.last; return [s.x + p[0] * s.scale, s.y + p[1] * s.scale]; };
  function drawSprite(g, s, q) {
    const meta = spriteMeta[s.id], b = spriteBuffers[s.id], image = b.source;
    if (q >= 1) { g.drawImage(image, s.x, s.y, s.w, s.h); return { tip: spriteEnds(s, false) }; }
    const m = b.mask.getContext('2d'), c = b.tile.getContext('2d'), amount = q * s.total;
    m.clearRect(0, 0, b.mask.width, b.mask.height); m.strokeStyle = '#fff'; m.lineWidth = meta.brush; m.lineCap = 'round'; m.lineJoin = 'round';
    let tipP = s.first, seals = null;
    for (const part of s.parts) {
      if (amount < part.from) { seals = part.rt; break; }
      const fraction = U.clamp((amount - part.from) / part.len), distance = fraction * part.distance;
      tipP = DG.pointAt(part.p, part.cum, distance);
      if (part.ink) { m.beginPath(); m.moveTo(...part.p[0]); for (let i = 1; i < part.p.length; i++) { if (part.cum[i] <= distance) m.lineTo(...part.p[i]); else { m.lineTo(...tipP); break; } } m.stroke(); }
      if (fraction < 1) { seals = part.rt; break; }
    }
    if (seals) { m.fillStyle = '#fff'; const W = b.mask.width, sp = meta.split || 0;      // 已画完的行补满，保证头部细节完整
      for (let g = 0; g < 2; g++) { const top = Math.max(0, seals[g] - meta.brush / 2); if (top > 0) { const x0 = sp ? (g ? sp : 0) : 0, x1 = sp ? (g ? W : sp) : W; if (sp || g === 0) m.fillRect(x0, 0, x1 - x0, top); } } }
    c.clearRect(0, 0, b.tile.width, b.tile.height); c.globalCompositeOperation = 'source-over'; c.drawImage(image, 0, 0);
    c.globalCompositeOperation = 'destination-in'; c.drawImage(b.mask, 0, 0); c.globalCompositeOperation = 'source-over';
    g.drawImage(b.tile, s.x, s.y, s.w, s.h);
    // 填色层：线条画过的地方周围 FILLW 范围内的肤色/阴影一并显出，避免脸上出现没填上的白斑（线条仍按笔画逐笔出现）
    const m2 = b.mask2.getContext('2d'), c2 = b.tile2.getContext('2d');
    m2.clearRect(0, 0, b.mask2.width, b.mask2.height); m2.strokeStyle = '#fff'; m2.lineWidth = 150; m2.lineCap = 'round'; m2.lineJoin = 'round';
    for (const part of s.parts) {
      if (amount < part.from) break;
      const fraction = U.clamp((amount - part.from) / part.len), distance = fraction * part.distance;
      if (part.ink) { const tp = DG.pointAt(part.p, part.cum, distance); m2.beginPath(); m2.moveTo(...part.p[0]); for (let i = 1; i < part.p.length; i++) { if (part.cum[i] <= distance) m2.lineTo(...part.p[i]); else { m2.lineTo(...tp); break; } } m2.stroke(); }
      if (fraction < 1) break;
    }
    c2.clearRect(0, 0, b.tile2.width, b.tile2.height); c2.globalCompositeOperation = 'source-over'; c2.drawImage(b.fill, 0, 0);
    c2.globalCompositeOperation = 'destination-in'; c2.drawImage(b.mask2, 0, 0); c2.globalCompositeOperation = 'source-over';
    g.drawImage(b.tile2, s.x, s.y, s.w, s.h);
    return { tip: [s.x + tipP[0] * s.scale, s.y + tipP[1] * s.scale] };
  }
  function init(ctx) {
    ringImages = {}; ringTints = {};
    for (const cue of ctx.cues) if (cue.kind === 'ring_reference') {
      const image=ctx.IMG[cue.image]; if (!image) throw new Error('圈画原稿加载失败 '+cue.image);
      ringImages[cue.data.style] = image;
    }
    L = ctx.data.layout || LEGACY; PANEL = L.panel_width;
    if (ctx.W !== L.width || ctx.H !== L.height) throw new Error('画幅与布局不一致，请重建事件表');
    spriteMeta = ctx.data.spriteLibrary.sprites; spriteSources = {}; spriteBuffers = {};
    for (const cue of ctx.cues) if (cue.kind === 'asset') spriteSources[cue.data.group] = ctx.IMG[cue.image];
    for (const [id, meta] of Object.entries(spriteMeta)) {
      const make = () => { const cv = document.createElement('canvas'); cv.width = meta.rect[2]; cv.height = meta.rect[3]; return cv; };
      const src = isolateForComposite(spriteSources[meta.group], meta.rect), fill = make(), fg = fill.getContext('2d'); fg.drawImage(src, 0, 0);
      const fd = fg.getImageData(0, 0, fill.width, fill.height), fa = fd.data;      // 填色层：去掉黑色线条和近白色，只留肤色/阴影/橙色等填色
      const FW = fill.width, FH = fill.height, dk = new Uint8Array(FW * FH);
      for (let i = 0; i < FW * FH; i++) dk[i] = fa[i * 4 + 3] > 0 && (fa[i * 4] + fa[i * 4 + 1] + fa[i * 4 + 2]) / 3 < 90 ? 1 : 0;
      const thick = i => { const x = i % FW, y = (i / FW) | 0; return x > 5 && y > 5 && x < FW - 5 && y < FH - 5 && dk[i - 5] && dk[i + 5] && dk[i - 5 * FW] && dk[i + 5 * FW]; };   // 粗黑块（头发）算填色，细黑线不算
      for (let i = 0; i < FW * FH; i++) { const k = i * 4, white = fa[k] > 235 && fa[k + 1] > 235 && fa[k + 2] > 235; if (white || (dk[i] && !thick(i))) fa[k + 3] = 0; }
      fg.putImageData(fd, 0, 0);
      spriteBuffers[id] = { mask: make(), tile: make(), mask2: make(), tile2: make(), fill, source: src };
    }
    hand = ctx.IMG[ctx.data.image]; tip = ctx.data.handTip || tip; scenes = ctx.data.scenes; strokes = [];
    ctx.data.events.forEach((e, k) => {
      const off = e.index * PANEL; e.seed = k + 22;
      if (e.kind === 'line') addLine(e, off);
      else if (e.kind === 'media') {
        const cue=ctx.cues.find(q=>q.kind==='document'&&q.data?.original_image===e.image);
        const image=ctx.IMG[cue?.image||e.image];
        if (!image) throw new Error('官方原件加载失败 '+e.image);
        strokes.push({kind:'media',image,x:e.x+off,y:e.y,w:e.w,h:e.h,at:e.at,dur:e.dur,index:e.index,fade:true});
      }
      else if (e.kind === 'text') strokes.push({ fade: !!e.fade, kind: 'text', str: e.str, x: e.x + off, y: e.y, size: e.size, at: e.at, dur: e.dur, color: e.color || INK, index: e.index });
      else if (e.kind === 'hero') { const m = spriteMeta[e.id], w = m.rect[2] / m.rect[3] * e.h; addSprite(e.id, e.cx - w / 2 + off, e.top, e.h, e.at, e.dur, e.index); }
    });
    strokes.sort((a, b) => a.at - b.at);
  }
  function drawText(g, s, q) {
    const chars = [...s.str], step = q * chars.length, n = Math.floor(step); g.font = `${s.size}px "LXGWWenKai-500"`; g.fillStyle = s.color; let x = s.x, p = null;
    for (let i = 0; i < chars.length; i++) { const w = g.measureText(chars[i]).width;
      if (i < n) g.fillText(chars[i], x, s.y);
      else if (i === n && q < 1) { const z = DG.zigzag(x, s.y - s.size * .85, w, s.size, 4), c = DG.cum(z), d = c.at(-1) * (step - n);
        g.save(); g.clip(DG.revealMask(z, c, d, s.size * .27)); g.fillText(chars[i], x, s.y); g.restore(); p = DG.pointAt(z, c, d); }
      x += w; }
    return p;
  }
  function camera(t) {
    let x = 0; for (const sc of scenes) { if (sc.index === 0) continue;
      if (t < sc.start - .5) break; x = U.lerp((sc.index - 1) * PANEL, sc.index * PANEL, smooth(sc.start - .5, sc.start + .4, t)); if (t < sc.start + .4) break; } return x;
  }
  function ambient(g, t, sc) {       // 点线随时间走、右上角小钟：表示故事时间在流动
    const x = sc.index * PANEL, lt = t - sc.start;
    g.strokeStyle = OR; g.lineWidth = 3; g.lineCap = 'round'; g.save(); g.setLineDash([3, 15]); g.lineDashOffset = -t * 17; g.beginPath(); g.moveTo(x + L.separator_x[0], L.separator_y); g.lineTo(x + L.separator_x[1], L.separator_y); g.stroke(); g.restore();
    const [clockX, clockY, clockR] = L.clock;
    g.strokeStyle = '#ccc'; g.lineWidth = 3; g.beginPath(); g.arc(x + clockX, clockY, clockR, 0, Math.PI * 2); g.stroke();
    for (let j = 0; j < 2; j++) { const a = lt * (j ? .16 : .65) - Math.PI / 2, r = j ? 12 : 19; g.beginPath(); g.moveTo(x + clockX, clockY); g.lineTo(x + clockX + Math.cos(a) * r, clockY + Math.sin(a) * r); g.stroke(); }
  }
  function caption(g, t, ctx) {
    const cap = ctx.data.captions.find(c => t >= c.start && t < c.end); if (!cap || ctx.data.captioned === false) return;
    let size = [...cap.text].length > 17 ? L.caption_small_size : L.caption_size; g.font = `${size}px "PuHui-Medium"`; g.textAlign = 'center';
    let width = g.measureText(cap.text).width;
    if (L.mode === 'landscape' && width > L.width - 100) { size *= (L.width - 100) / width; g.font = `${size}px \"PuHui-Medium\"`; width = g.measureText(cap.text).width; }
    g.fillStyle = 'rgba(28,28,28,.90)'; g.beginPath(); g.roundRect(L.width / 2 - width / 2 - 25, L.caption_top, width + 50, L.caption_height, 14); g.fill(); g.fillStyle = '#fff'; g.fillText(cap.text, L.width / 2, L.caption_baseline); g.textAlign = 'left';
  }
  function draw(g, t, ctx) {
    g.scale(ctx.W / L.width, ctx.W / L.width); g.fillStyle = BG; g.fillRect(0, 0, L.width, L.height);
    const cam = camera(t), sc = scenes.filter(s => s.start <= t).at(-1) || scenes[0];
    g.save(); g.beginPath(); g.rect(0, L.content_top, L.width, L.content_bottom - L.content_top); g.clip(); g.translate(-cam, 0); let activeTip = null;
    // 圈画位于文字下层；每块画板独立裁切，不能覆盖新文字或泄漏到相邻板。
    for (const s of strokes) {
      if (!s.ringAsset || t < s.at || s.index * PANEL - cam > L.width || (s.index + 1) * PANEL - cam < 0) continue;
      g.save(); g.beginPath(); g.rect(s.index*PANEL,L.content_top,L.width,L.content_bottom-L.content_top); g.clip();
      drawOriginalRing(g,s,U.clamp((t-s.at)/s.dur)); g.restore();
    }
    for (const s of strokes) { if (t < s.at || s.index * PANEL - cam > L.width || (s.index + 1) * PANEL - cam < 0) continue;
      g.save(); g.beginPath(); g.rect(s.index * PANEL, L.content_top, L.width, L.content_bottom - L.content_top); g.clip();   // 每笔只画在自己的画板内，越界部分不泄漏到相邻画板
      const q = U.clamp((t - s.at) / s.dur); g.strokeStyle = s.color; g.lineWidth = s.width || 6; g.lineCap = 'round'; g.lineJoin = 'round';
      if (s.kind === 'media') { g.globalAlpha=q; g.drawImage(s.image,s.x,s.y,s.w,s.h); g.restore(); continue; }
      if (s.fade) { g.globalAlpha = q; g.font = `${s.size}px "LXGWWenKai-500"`; g.fillStyle = s.color; g.fillText(s.str, s.x, s.y); g.restore(); continue; }   // 渐显文字：不用笔写，不进笔的轨迹
      const sr = s.kind === 'sprite' ? drawSprite(g, s, q) : null; const p = sr ? sr.tip : s.kind === 'text' ? drawText(g, s, q) : s.ringAsset ? ringTip(s, q) : s.pressure ? drawPressureLine(g, s, q) : DG.drawPartial(g, s.p, s.cum, s.len * q); if (q < 1) activeTip = p; g.restore(); }
    if (L.mode === 'portrait') for (const s of scenes) { if (t >= s.start && t < s.end && Math.abs(s.index * PANEL - cam) < L.width + 220) ambient(g, t, s); }
    g.restore();
    if (L.mode === 'landscape') { g.save(); g.beginPath(); g.rect(0, 0, L.width, L.height); g.clip(); g.translate(-cam, 0); ambient(g, t, sc); g.restore(); }
    let pen = activeTip ? [activeTip[0] - cam, activeTip[1]] : null, opacity = 1;
    if (!pen) {   // 没有正在画的笔：短空档沿弧线滑过去；长空档手退出画外再进来
      const pens = strokes.filter(s => !s.fade), prev = pens.filter(s => s.at + s.dur <= t).at(-1), next = pens.find(s => s.at > t);
      const end = prev ? (prev.kind === 'sprite' ? spriteEnds(prev, false) : prev.p ? prev.p.at(-1) : [prev.x + [...prev.str].length * prev.size, prev.y]) : null;
      const start = next ? (next.kind === 'sprite' ? spriteEnds(next, true) : next.p ? next.p[0] : [next.x, next.y - next.size * .85]) : null;
      const gap = prev && next ? next.at - prev.at - prev.dur : Infinity;
      if (gap < .3) { const q = smooth(prev.at + prev.dur, next.at, t); pen = [U.lerp(end[0], start[0], q) - cam, U.lerp(end[1], start[1], q) - Math.sin(q * Math.PI) * 20]; }
      else if (next && next.at - t < .3) { const q = smooth(next.at - .3, next.at, t); pen = [U.lerp(L.pen_enter_x, start[0] - cam, q), U.lerp(Math.min(L.pen_enter_bottom, start[1] + 160), start[1], q)]; opacity = q; }
      else if (prev && t - prev.at - prev.dur < .28) { const q = (t - prev.at - prev.dur) / .28; pen = [end[0] - cam + q * 360, end[1] + q * 100]; opacity = 1 - q; } }
    if (pen && hand && pen[0] > -180 && pen[0] < L.width) {
      g.save(); g.beginPath(); g.rect(0, L.content_top, L.width, L.content_bottom - L.content_top); g.clip(); g.globalAlpha = opacity;
      const pose=handPose(pen,L), hs=ctx.data.handScale; if (hs) pose.scale=hs;
      const hr=ctx.data.handRotation; if (hr !== undefined) pose.rotation = hr * Math.PI / 180;
      g.translate(...pen); g.rotate(pose.rotation); g.scale(pose.scale, pose.scale); g.translate(-tip[0], -tip[1]);
      // 竖屏/宽屏都用素材池的彩色手：素材自带袖口，sleeve=null 就原样贴，不叠加袖管延伸（2026-10-26 用户定稿）。
      // 只有旧线稿手 marker-hand-v02.png 带袖口遮挡线（白底+墨线盖住先画的内容），且只在竖屏用。
      const sl = ctx.data.sleeve === undefined ? [[1253, 885], [1052, 1253]] : ctx.data.sleeve;
      if (L.mode !== 'landscape' && sl) {
        const a = sl[0], b = sl[1], far = 5000;
        g.fillStyle = BG; g.strokeStyle = INK; g.lineWidth = 3; g.beginPath(); g.moveTo(...a); g.lineTo(a[0] + far, a[1] + far); g.lineTo(b[0] + far, b[1] + far); g.lineTo(...b); g.closePath(); g.fill();
        g.beginPath(); g.moveTo(...a); g.lineTo(a[0] + far, a[1] + far); g.moveTo(...b); g.lineTo(b[0] + far, b[1] + far); g.stroke();
      }
      g.drawImage(hand, 0, 0);
      g.restore(); }
    // Persistent titles removed by user decision, 2026-10-28.
    caption(g, t, ctx);
    const fade = U.clamp((t - (ctx.dur - .7)) / .6); if (fade > 0) { g.fillStyle = `rgba(255,255,255,${fade})`; g.fillRect(0, 0, L.width, L.height); }   // 结尾 0.6s 淡出到白板，不突然定格
  }
  return { inspectHand: handPose, inspect: () => strokes.filter(s => s.kind === 'sprite').map(s => ({ id: s.id, at: s.at, end: s.at + s.dur, index: s.index })), safe: true, fonts: ['LXGWWenKai-500', 'PuHui-Medium'], init, draw };
})();
