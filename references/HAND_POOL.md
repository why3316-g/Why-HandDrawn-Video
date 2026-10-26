# 手与笔素材规范（2026-10-26 用户定稿）

竖屏成片里那只握笔的手**只有一个来源**：本包 `assets/hands/hand-pool-v01/` 素材池。不再每片临时找手，也不在片中途换手。

> 公开版（`package_skill.py --profile public`）不带素材池图片：池目录为空时 `new_project.py` 自动退回旧线稿手 `marker-hand-v02.png`，其余规则不变。

## 规则

1. **一片一双手**：新建竖屏项目时从池里随机取一张，装进项目的 `assets/images/`，全片从第一笔到最后一笔都是这双手。中途换手视为画面错误。
2. **只取池目录根下的 PNG**：不递归、不进任何子目录。`_` 开头的文件与子目录一律不参与（备用图放工作区归档，不放进池）。
3. **轮着用、顺序随机**：最近用过的顺序记在工作区 `assets/hand-usage.json`，取图时只在「本轮还没用过」的图里随机——池里 8 张就是 8 支片一轮不重复；新增图片自动进入下一轮。池里只剩一张时直接用那张。
4. **不手写几何参数**：笔尖坐标 `tip`、竖屏缩放 `scale`、袖管几何 `sleeve` 由 `scripts/hand_pool.py` 量出来写进项目 `assets/images/hand-meta.json`，渲染时由 `design/hdv/dsl.py` 带进 spec。禁止在 `film.py` 里手写 `hand_tip` 去凑位置。
5. **宽屏不受影响**：1920×1080 继续用已批准的短手素材 `assets/marker-hand-landscape-v01.png`（scale .18），不套用素材池。
6. **这是唯一允许的彩色写实元素**：手与笔是实拍级彩色素材，其余画面仍按 `STYLE_SPEC.md` 走白底墨线 + 橙色强调。不得因为手是彩色，就给人物、家具、道具上色、加阴影或渐变。

## 新增图片

直接把透明底 PNG 丢进 `assets/hands/hand-pool-v01/`，然后：

```bash
python <skill>/scripts/hand_pool.py --sync        # 量笔尖、写清单、顺手刷新 BUNDLE_MANIFEST
python <skill>/scripts/verify_bundle.py           # 确认包完整
```

之后它自动参与随机，不需要改代码、不需要改文档。

新图必须与现有 8 张**同构图**，否则量出来的参数会让手画歪：

- 透明底 RGBA，只有一只手、一支笔，没有第二只手、没有背景、没有文字水印；
- 笔尖朝左上、袖口朝右下（现在的渲染统一按 −45° 旋转，让笔变水平）；
- 画布长边约 1100–1550 px，手在画面里占比与现有图相当；
- 笔尖是整张图 `x+y` 最小的不透明点（脚本按这个量）。

构图不同（笔尖不在左上、多手多笔、白底不透明）时不要硬塞进这个池：另开 `hand-pool-v02/`，并在清单里手写 `tip`/`scale`，改 `hand_pool.py` 的 `POOL_REL` 前先按 `ENGINE_GUIDE.md` 的改编规则沟通。

## 命名

`序号-笔-腕饰-袖口.png`，全 ASCII、小写、中划线，例如：

| 文件 | 内容 |
|---|---|
| `01-porcelain-butterfly-blue-sleeve.png` | 青花瓷笔 + 蝴蝶戒指 + 蓝花袖 |
| `02-jade-bangle-leaf-cuff.png` | 玉笔 + 玉镯 + 叶纹白袖 |
| `03-porcelain-gem-ring-blue-cuff.png` | 青花瓷笔 + 蓝宝石戒指 + 蓝花袖 |
| `04-jade-bangle-floral-hanging-cuff.png` | 玉笔 + 玉镯 + 垂坠花袖 |
| `05-jade-bangle-ivory-silk-sleeve.png` | 玉笔 + 玉镯 + 象牙色软纱袖 |
| `06-porcelain-chain-layered-sleeve.png` | 青花瓷笔 + 蓝花银链 + 层叠纱袖 |
| `07-porcelain-chain-pearl-lilac-sleeve.png` | 青花瓷笔 + 珠花银链 + 淡紫边袖 |
| `08-porcelain-mountain-print-sleeve.png` | 青花瓷笔 + 蓝花银链 + 山水纹袖 |

## 怎么用

```bash
python <skill>/scripts/hand_pool.py --list                 # 看池里有什么、笔尖与缩放
python <skill>/scripts/new_project.py <短名> --workspace <工作区>          # 随机取一张
python <skill>/scripts/new_project.py <短名> --workspace <工作区> --hand 03 # 指定序号（复现旧片的手）
```

项目里会留下痕迹：`design/config.json` 的 `hand`、`assets/images/hand-meta.json`、`brief/BRIEF.md` 的「手与笔」一行。

## 回退

要回到旧的线稿手：把项目 `design/config.json` 的 `hand` 改成 `marker-hand-v02.png`，并把 `assets/images/marker-hand-v02.png` 放回项目（旧包自带）。`hand-meta.json` 不匹配时会自动忽略，渲染回到 tip `[147,119]`、scale `.34`、袖管几何 `[[1253,885],[1052,1253]]`。
