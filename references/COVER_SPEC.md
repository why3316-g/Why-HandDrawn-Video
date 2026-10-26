# 封面规范（每条成片必须出封面）

封面是成片的一部分，不是可选项。**在流程第 5 步和人物图一起给用户审核**（不要等成片出完才想起来），审核通过的封面作为成片最开头的几帧。

网站 landscape 模式先读 LANDSCAPE_SPEC.md 第 4 节：使用1920×1080左题右图构图、按主题选场景和橙色重点，覆盖本页竖屏尺寸、居中与首尾结果要求；标题保真、美术指导、生图渠道、用户审核和首6帧规则共用。

## 1 规格
- 竖版 1080×1920 PNG，文件 `renders/<名>-cover-vNN.png`；不覆盖旧版，改了就升版本。
- 重要内容（标题 + 人物）放在中间 3:4 安全区 y≈240–1680 内；底部 200 px 留给平台界面。
- 白底；墨色 `#171717`；唯一强调色橙 `#ed7929`。

## 2 文字（2026-10-12 用户定稿的四条规则）
1. **标题要大、要粗**：用最粗字重黑体（包内 Noto Sans SC 可变字体 wght 900），基础字号约 108 px，居中，每行不超出左右 48 px 边距。标题逐字等于 `brief/title.txt`，脚本会校验。
2. **橙色只标两处：首和尾。**
   - 首 = 主角或话题当下的**状态词**（由标题决定，如"加班到凌晨""存不下钱""不想上学"）；
   - 尾 = **超预期的结果**（如"月入翻倍""再没加过班"）。
   - 中间的数字、时间不标橙。尾部结果行可以比其他行更大（约 150 px），像收尾的重音。
3. 标题拆行按语义断，不在词中间断；单行宽度超限脚本会报错，不要硬塞。

## 3 画面（人物）
1. **人物要小**：插画宽度约 760 px（画布 70%），周围留白充足；它是配角，标题才是主角。
2. **画面必须是目标受众一眼认得出、且与标题状态一致的场景**（由赛道和标题决定；赛道专属的封面场景要求写在视频工作区规则里）。不用与标题状态相反的画面做封面，也不用与标题无关的装饰。
3. 画风与成片一致：白纸黑线稿，衣服白色，只有袖口一点橙；人物用该片的概念图（`concept-<角色>-v01.png`）作参考，保持同一个孩子。
4. 未成年人着装：长袖长裤，自然躺姿，平静日常场景（脚本自动带上未成年人条款）。手机屏幕留白，不出现文字或图标。
5. 生图提示词里要写"纯白底、无光晕、无阴影"。生图偶尔会出黑色晕影底，那是废图，存入 `assets/images/rejected/` 重生，不放行。
6. 脚本把生图残留的近白底（≥238）归为纯白后合成，只处理背景，不改线条。

## 4 美术指导（必做）
每次先读包内 `references/COVER_ART_DIRECTION.md`，落实 canvas-design 的视觉理念、空间表达与精修方法；来源与许可见 SOURCES。再写本封面理念，不另装 Skill、不读取无关字体或海报路径。具体规格以本文件为准。

## 5 步骤
1. 写 `design/cover-philosophy-vNN.md` 和 `design/cover.json`（格式见 `scripts/make_cover.py` 顶部）。
2. `python <skill>/scripts/make_cover.py --text-only`：先看文字底稿（大小、断行、橙色位置）。
3. 按当前工具生成插画并合成：Claude / WorkBuddy 运行 `make_cover.py`，由 Codex CLI 生图；Codex 运行 `make_cover.py --emit-image-prompt` 导出提示词，用 Codex 内置生图工具生成并保存为 `assets/images/cover-illus-vNN.png`，然后运行 `make_cover.py --skip-gen --imagegen-tool "Codex 内置生图工具"`（可加 `--imagegen-version <版本>`）合成；**Gemini Antigravity 默认用内置 `image-generator` 子代理**——同样 `--emit-image-prompt` 导出后交子代理生成到 `assets/images/cover-illus-vNN.png`，再 `make_cover.py --skip-gen --imagegen-tool "Antigravity image-generator 子代理"` 合成（宽高比按插画要求传入，不传分辨率）。插画目检（躺平玩手机？白底？无字？衣服白色？）。
4. 只调字号/位置：`--skip-gen`，不再调生图；换版本 `--version v02`。
5. 记录 `design/cover-record-vNN.json`（标题、字体、提示词、实际生图工具及可获得的版本、插画与封面 SHA-256、canvas-design 来源与日期）；用 Codex / Antigravity 内置工具时通过 `--imagegen-tool` 和 `--imagegen-version` 登记（Antigravity 写 `Antigravity image-generator 子代理`），不要求本机安装 Codex CLI。

## 6 用户闸门（第 5 步）
封面和人物图联系表同一轮发给用户；通过后才能进入后面的笔画提取、事件表和渲染。封面有改动要重新审核。

## 7 开头封面帧（用户 2026-10-12 规定）
通过的封面放在成片**最开头 6 帧（30fps ≈ 0.2 s，约 0.19 s 的视觉停留）**：观众仍能看清封面，同时很多短视频平台默认抓取首帧当封面，这样抓到的就是设计好的封面。
- 用 `python <skill>/scripts/add_cover_intro.py --video <配乐版> --cover <封面> --out <成片>`；开头段静音，口播与画面整体后移 0.2 s，音画相对关系不变；脚本核对总帧数 = 正片帧数 + 6。
- 开头规范关系（`OPENING_SPEC.md`）：封面 0.2 s 是静止帧，计入"第一段静止"；因此第一块画板人物须在正片 0.5 s 内起笔，拼入封面后再对 final 跑 `opening_check.py`。
- 验收：用 ffmpeg 抽 0 s 帧与封面图比对（差异只应是压缩噪声），0.2 s 之后应是正片第一帧。

## G端机构宣传片（2026-10-22用户定稿）

学校、教育局、企业等官网宣传片设`content_type: institutional_promo`：默认儒雅逸辰2.0（`yichen`，`zh_male_ruyayichen_uranus_bigtts`），语速0和同一正式播音指令；封面为正式机构宣传片主视觉，正文保持原手绘。唯一细则见`references/INSTITUTIONAL_PROMO.md`，本节覆盖其他文件中的大壹默认及白板封面要求，仅限此内容类型。用户明确要求原文直接转视频时保留原文，不强制改写。用户明确要求先看静态效果时可先出封面与若干图，记录授权范围，不伪造全文声音锁定、不进入动画渲染。
