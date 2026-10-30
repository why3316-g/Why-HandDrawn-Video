# 制作流程（13 步）

模式先行：默认 portrait；网站宽屏用 new_project.py --mode landscape，先读 LANDSCAPE_SPEC.md。原文章先留存并改编为待审讲解稿，用户确认后才进入下表第2–3步；宽屏坐标、主题封面和网站交付按该规范覆盖本页竖屏案例专属说明，审核闸门共用。

每步写明产物与闸门。第 0–1 步在工作区根目录运行；第 2 步起先 `cd projects/日期-短名-v01`，脚本默认处理当前目录（也可用 `--project` 指定）。`<skill>` = 本 Skill 目录。

| # | 步骤 | 做什么 | 产物 | 闸门 |
|---|---|---|---|---|
| 0 | 环境预检 | `python <skill>/scripts/env_check.py` | 终端报告 | 缺运行依赖先安装；包内快照损坏则重新解压完整包 |
| 1 | 立项 | `python <skill>/scripts/new_project.py <短名>` | `projects/日期-短名-v01/` | — |
| 2 | 锁定原稿与定位 | 逐字写入 `brief/narration.txt`、`title.txt`；`BRIEF.md` 写受众/平台/目标/口吻 | brief/ | 受众、平台、目标、口吻不清先问用户 |
| 3 | 配音 | 按 `references/workspace/AUDIO_STANDARD.md`：只用火山，先按 AUDIO_STANDARD 的音色选择规则定大壹（默认）、小何 2.0（男讲述者统一大壹，女讲述者统一小何 2.0；家长角度按家长性别，学生性别不明用小何），说明理由。用 `generate_candidate.py --voice dayi|xiaohe` 全文一次生成，一份完整试听；定音色后把 voice、narrator_is_protagonist、protagonist_cast 写进 design/config.json（主角性别随声音，生图前脚本会核对） | assets/audio/（mp3、44.1k 单声道 wav、词级时间戳 json） | **先跑 `check_voice.py`；试听消息逐项给出每个红/黄提示的秒数、对应原句和类型，并标注 ASR 可疑字词的时间段，不能只报汇总**；红色项必须人耳复核；确认有问题的，经用户同意后重新全文合成；再让用户锁定声音：**发完试听消息就结束本轮回复，不做第 4 步及之后任何事**；用户明确说通过后运行 `lock_voice.py --audio <mp3> --user-says "<原话>"`，没有锁定记录生图脚本会拒绝运行。词级时间戳对齐不代表实际读音已核实 |
| 4 | 表演表 | 把口播切成画板；通常 1–3 句一个语义单元，每块 3–7 秒，硬上限 8.0 秒、硬下限 2.5 秒（很短的一句并入相邻画板，合并后超 8 秒就换一个语义转折点重切）；较长段落按动作、情绪或信息转折拆开，不固定素材总数。`design/shots.json` 写口播原文、场景、角色表演、源图已有物件 `source_objects`、计划新增物件 `overlay_objects` 及原文依据；`design/cast.json` 写角色身份和 `wardrobe_role` | design/shots.json、cast.json | 用 `PROMPT_PACK.md` 模板；所有出镜人物都在 `roles[]` 绑定 `cast_id`；每个妈妈镜头在 `wardrobe_references` 中按 cast key 选择一张衣着图，老师镜头使用匹配性别的参考图。缺少服饰图选择即停止，不进入生图；新增物件须有原文依据且不能重复或遮挡源图对象；每个圈/叉/勾/箭头写明原文短语和语义；单板超过 8.0 秒须拆分；**第 1 块（开头）另写前 5 秒动作清单**，逐短语标明画什么，按 `OPENING_SPEC.md` |
| 5 | 生图 + 封面 | ①先概念图，再逐镜头：Claude/WorkBuddy 运行 `gen_sprites.py`（调用 Codex CLI）；Codex 运行 `gen_sprites.py --emit-only`，按 `qc/imagegen-run.json` 中的 `ref` 路径把所有参考图片真实附加到内置生图调用，按提示词生成并保存到指定路径；**Gemini Antigravity 同样先 `gen_sprites.py --emit-only --emit-tool "Antigravity image-generator 子代理"`，再把每条提示词连同该镜头的全部 `ref` 交给内置 `image-generator` 子代理生成，图存到提示词指定路径（默认走这个子代理，不调 Codex CLI、不换其他图像服务）**。使用了服饰参考扩展包时，缺参考图脚本会停止；不能只把路径写进提示词。看每张实图，记录已有物件及位置至 `source_objects`，与 `overlay_objects` 对照，删除重复或遮挡的新增画法；②**同时出封面**：先读 `references/COVER_SPEC.md` 和包内 `COVER_ART_DIRECTION.md`，写 `design/cover-philosophy-v01.md`、`design/cover.json`，`make_cover.py --text-only` 看文字底稿。Claude/WorkBuddy 用 `make_cover.py` 调 Codex CLI 生成并合成；Codex 先用 `make_cover.py --emit-image-prompt` 导出提示词，用内置生图工具生成到 `assets/images/cover-illus-v01.png`，再运行 `make_cover.py --skip-gen --imagegen-tool "Codex 内置生图工具" [--imagegen-version <版本>]` 合成；Antigravity 同样用 `--emit-image-prompt` 导出，交 `image-generator` 子代理生成后 `--skip-gen --imagegen-tool "Antigravity image-generator 子代理"` 合成 | assets/images/C-*-v01.png、qc/IMAGEGEN_LOG.md、renders/<名>-cover-v01.png、design/cover-record-v01.json | **一起给用户审核（人物图联系表 + 封面）**：每张人物图逐图验收，看实图写 observation，合格设 `reviewed:true`；封面看标题大且首尾橙色、人物小、画面是厌学在家躺平玩手机。不合格重生，不勉强；内置生图路径（Codex / Antigravity）结果须补记实际附件路径及 IMAGEGEN_LOG |
| 6 | 笔画提取 | `python <skill>/scripts/analyze_strokes.py` | design/sprite-strokes-v01.json | — |
| 7 | 写事件表 | 编辑 `design/film.py`（参考 `examples/xiaoyu/film.py` 与 `LAYOUT_LIBRARY.md`）+ `design/breaks.json`；运行 `design/film.py` 自动检查文字出界/重叠、线条穿字、圈字、单板时长、板内笔画空档与"画完再走镜头"（镜头在下一块起点前 0.5 s 开始离开，本板每一笔最晚在离开后 0.2 s 内画完），并生成 `qc/panel-rhythm.json`；圈字一律用 `ring()`，文字 y 是基线不是顶部 | design/spec-film.json、qc/panel-rhythm.json + 时间审查表 | 无"超出本块窗口"或节奏超限标记；每块 2.5–8.0 s，板内有效新笔画空档 ≤4 s；**开头自检同时拦截**：`hero` 起笔 > 0.5 s、0–5 s 静止 > 1.0 s；老项目的 `design/hdv/` 要先更新包内 `scripts/hdv/` |
| 8 | 资产检查 | `python <skill>/scripts/make_manifest.py` | design/performance-plan.json、brief/PERFORMANCE_TABLE.md、qc/asset-usage.json | 必须 pass，否则禁止渲染 |
| 9 | 预览 + 画板与节奏自检 + **独立审片** | ①渲染完整画面版 `render_film.py --out renders/<名>-visual-vNN.mp4`，跑 `panel_check.py` 看每块完成帧并写 `qc/panel-final-review.md`；逐板看 `qc/panel-rhythm.json` 并抽查板内中段及最长静止点，核对重复物件、遮挡、符号语义；预览版跑 `opening_check.py --ignore-start 0`。②自检全部合格、并先跑完第 10 步 `sync_report.py` 后，**在这一步派独立 agent 审画面预览版**（提示词见 `PROMPT_PACK.md` D，带上原稿、`qc/sync-report.md` 与锁定配音），报告写 `qc/independent-review-visual-vNN.md` | qc/panel-final/、qc/panel-final-review.md、qc/panel-rhythm.json、qc/independent-review-visual-vNN.md | **任一块有问题：改事件表 → 重渲染 visual-vNN+1 → 再检查**；完成帧检查不能替代过程节奏检查。审片只有"阻断"项必须改并复核（复核只看改动的画板）；"记录"项写进 STATUS，不触发重渲。画面审片通过之前不混音、不拼封面——成片返工都留在 visual 版本里消化，final 一次出 v01 |
| 10 | 音画对齐 | `python <skill>/scripts/sync_report.py` | qc/sync-report.md | "需检查"项逐条看 |
| 11 | 配乐 + 开头封面 | ①**直接用第 9 步独立审片通过的那一版 `renders/<名>-visual-vNN.mp4`，不再重渲画面**；②当前执行本工作流的 AI 工具按脚本自动选定已授权曲目，告知用户曲目与依据后继续，不等待挑选或审核；③`mix_audio.py --video … --out renders/<名>-bgm-v01.mp4 --bgm <曲目>`（响度查 `bgm-levels.json`，没有登记值时自动用 `-28 LUFS` 并记录；不用音效）；④**必须**用 `add_cover_intro.py` 把第 5 步用户已通过的封面图拼入最终视频开头 6 帧（≈0.2 s），输出 `renders/<名>-final-v01.mp4`。单独 PNG、试听版或平台端上传封面都不能替代成片内的封面帧 | renders/、qc/mix-report-*.json | 成片帧数 = 混音正片帧数 + 6；时长增加 0.2 s；第 0 帧须与已通过封面一致，第 6 帧开始正片，前 6 帧静音；混音响度 -16 LUFS；配乐过授权闸门。封面帧核验不通过不得交付；拼入封面后对 final 再跑 `opening_check.py --video <final>`（含封面 0.2 s 静止），必须通过 |
| 12 | 验收 | `python <skill>/scripts/qa_project.py`；ffprobe；成片再跑 `panel_check.py --offset 0.2` 和 `check_voice.py`；抽查第 0 帧与已通过封面、第 6 帧与混音正片首帧，并确认前 6 帧静音；关键帧目检；**独立 agent 成片复核**（提示词见 PROMPT_PACK D2：只核对第 9 步之后新增的封装——封面帧、静音片头、配乐压低与口播清晰度、成片开头检测、结尾渐隐；画面已在第 9 步审过，不重审） | qc/ | 复核发现的问题逐条处理；画面问题若在第 9 步审过的 visual 版里已存在且未判阻断，记录不返工；封面、帧数、静音片头任何一项不符都不得交付；**开头规范三项都要有记录**：事件表自检通过、`opening_check.py` 对成片通过（`qc/opening-check.md`）、开头抽帧目检（0.9/1.9/2.7/3.6/4.4/5.2 s）；任一项缺失不得交付。`qa_project.py` 会自动对最新 final 跑开头检测 |
| 13 | 交付 | landscape 先运行 `export_website.py --video <final> --cover <封面> --out renders/website-vNN` 生成网站MP4、poster、VTT；写 `STATUS.md`（成片路径、版本、已验证项、未验证项）；本地 git 提交文档变更 | STATUS.md | 用户最终确认 |

## 开头规范（贯穿第 4、7、9、11、12 步）
唯一权威：`references/OPENING_SPEC.md`。三条硬指标：人物 0.5 s 内起笔；0–5 s 内除字幕外持续有新笔画、静止 ≤ 1.0 s；字幕/标题栏/小时钟/镜头平移不算动画。查法：事件表自检 + `opening_check.py` 检测成片 + 目检。

## 迭代规则
- 任何修改产出新版本号（v02…），不覆盖旧文件。
- `shots.json` 的可选 `image_file` 用于明确选用的版本图路径；笔画提取和资产清单均读取该字段，未填写时仍按 `C-<asset>-v01.png`。
- 重生某张图后：重跑 6→7→8→9（只复审改动画板）→11。
- 只改字幕断点或文字：重跑 7→9→11，不重跑生图。
- **版本号该停在哪**：画面返工只升 `visual-vNN`；`final` 只在第 9 步画面审片通过后出一次。正常情况下交付即 `final-v01`；final 升版只应来自封面、配乐、封装问题或用户成片意见，出现时在 STATUS 写明原因。
- 封面只调字号/位置：`make_cover.py --skip-gen`；换版本用 `--version v02`；换封面后重跑第 11 步的 ④。
- 音画不对齐先怀疑时间戳与原稿是否一致（`Clock` 会直接报错），不要手调时间。

## G端机构宣传片（2026-10-22用户定稿）

学校、教育局、企业等官网宣传片设`content_type: institutional_promo`：默认儒雅逸辰2.0（`yichen`，`zh_male_ruyayichen_uranus_bigtts`），语速0和同一正式播音指令；封面为正式机构宣传片主视觉，正文保持原手绘。唯一细则见`references/INSTITUTIONAL_PROMO.md`，本节覆盖其他文件中的大壹默认及白板封面要求，仅限此内容类型。用户明确要求原文直接转视频时保留原文，不强制改写。用户明确要求先看静态效果时可先出封面与若干图，记录授权范围，不伪造全文声音锁定、不进入动画渲染。

## 宽屏第4步前置：逻辑策划

landscape在第4步写表演分镜前，按LANDSCAPE_LOGIC.md逐段分析完整锁稿（含样片以外部分），写design/logic-plan.json、逻辑策划表和官方材料来源清单。第7步Film.build与第9步正式render_film均检查；检查失败先补真实分析或调整分镜，不关开关、不跳检查。第9步独立审片逐一核对关系与布局、人物覆盖和原件真实性。

## 宽屏风格定稿（仅landscape）
第4步按LANDSCAPE_LOGIC.md标记逐板构图与关系，穿插居中人物、居中逻辑/文字说明和左右讲解；不机械定比例。第5步场景随原文，不能一张人物换文字无限复用。第7步用素材池随机一张手、无装饰竖色条；原件原样呈现。第9/12步逐板过程与完成态复查居中、阅读顺序、变化、袖口原样收口和真实原件；portrait继续原风格。


> 2026-10-28 更新：构图与绘制顺序先按 `EDITING_COMPOSITION.md` 第1—4节执行。本文固定坐标仅为示例，不是默认排版；完整语义单元优先于凑事件数。情绪与物件已获审核；取消全部常驻标题，正式渲染执行构图检测。

> 2026-10-28最终决定：所有固定标题/歌名取消，旧标题坐标不再执行；封面和叙事关键词保留。正式渲染须通过 EDITING_COMPOSITION 第7节检查。

## 自检优先与一次成片（2026-10-28，覆盖本页第 7、9、12 步中与之冲突的做法）
- **第 7 步前**：`python <skill>/scripts/measure_panels.py` 量图并看联系表；写 `design/layout-plan.json` 逐板构图计划；写完事件表后 `build_composition.py` 生成 composition.json。窄人物移到一侧、字写另一侧空区，禁止全片同一左栏（EDITING_COMPOSITION 第 9 节）。
- **第 8 步后、整片渲染前**：`self_check.py --stage pre`，逐张看它生成的联系表（写到一半/写完），改到全部通过，再 `--ack-viewed` 记录。
- **第 9 步**：整片画面版渲染一次；独立审片由自检脚本加逐张联系表目检完成，子智能体仅在用户要求或自检无法判定时使用。画面返工先用静帧验证再重渲，不拿整片渲染试错。
- **第 12 步**：`self_check.py --stage post --video <成片>` 全部通过并看完联系表，才把成片和 `qc/self-check.md` 给用户。用户闸门只有声音锁定、人物+封面审核、最终确认（EDITING_COMPOSITION 第 10 节）。
