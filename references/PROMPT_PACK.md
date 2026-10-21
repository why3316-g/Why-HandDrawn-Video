# 提示词包

## A 生图（由 gen_sprites.py 自动拼装，这里是原文，便于其他工具照用）
**STYLE 段（每张图都带）**
> Use case: illustration-story. The reference image defines the selected C clean ligne-claire ink drawing style. Clear elegant black contours with controlled line weights, accurate small expressive eyes, eyebrows and mouth, natural anatomy and hands, sparse carefully chosen clothing folds, white clothing interiors and very subtle flat skin tint. No hatching, realism, glamour, fashion poses, celebrity styling, glossy anime eyes, huge heads or crude stick figures. Ordinary Chinese family members, recognizable age differences. Isolated character acting illustration on pure white, entire requested bodies and hands inside generous margins. No text, lettering, borders, scenery or watermark.
> （另有颜色规则，紧接在 “Ordinary Chinese family members…” 之后：）Colour rule: black ink on white only. All clothing (tops, cardigans, sweaters, trousers, skirts) is plain white with black outlines and NO grey, black, cream or coloured fill; hair is solid black; shoes are white with black outlines; the only colour allowed is a tiny orange accent on the cuffs or collar edge and a very faint skin tint. Furniture and props are line drawings with no colour fill.

**MINOR（未成年人着装条款，自动加入）**：
> Clothing note for any character under 18: an ordinary everyday school or home outfit, a long-sleeved top and long trousers, fully covered, relaxed natural posture, calm everyday scene.
触发：cast 里写 `"minor": true`，或镜头 roles 里有年龄 <18，或镜头写 `"minor": true`（场景里出现未成年人但角色表没列时用）。写法只用正向描述（穿什么、什么姿态），不写 swimwear / sexualised / revealing 这类负面敏感词：这类词出现在提示词里本身就可能触发图像安全审核（实测 hook 曾被判 `safety_violations=[sexual]`）。

**HEAD**：Use your built-in image generation tool (do NOT draw with code, do NOT post-process with scripts) to create ONE image, landscape 3:2, pure white background. Describe the framing in the prompt; do not pass any size parameter. Do not read or edit any other file in the working directory: this task is only to generate the image described below and save it.
**FOOT**：生成后把 PNG 复制到指定相对路径，打印绝对路径和 SHA-256；工具不可用或失败就如实说明原因并停止，不用别的方法替代。

**概念图（先出，无身份/服饰参考的角色才生成）**：HEAD + "STYLE-ONLY reference attached: it shows a DIFFERENT person (this character is not him/her); copy only the drawing style." + STYLE + 角色 identity + concept_pose。参考图用 `assets/images/style-ref-C.png`。妈妈/班主任不能把概念图作为服饰参考的替代；每个镜头必须通过 `wardrobe_references` 附加批准的衣着图。

**镜头图**：参考图 = 该角色的概念图（保持同一个人）：
> The attached reference image shows {name} (and defines the clean ligne-claire ink style). Keep the SAME person: same face, hair, build and clothes. {identity} + STYLE + 镜头 scene

多人/新人物：参考图只给风格，STYLE + "defines ONLY the clean ligne-claire ink style (do not copy its person)" + scene。

**工具分流**：Claude 与 WorkBuddy 通过当前 Codex CLI 执行这套提示词；Codex 使用内置生图工具并运行 `gen_sprites.py --emit-only` 导出提示词。Codex 内置工具生成时保留同一提示词，并将该镜头 `qc/imagegen-run.json` 列出的全部 `ref` 文件实际作为图像输入；缺任一输入就不得调用生图。不要只复制提示词文本。不得改写角色、镜头或画风要求；输出仍为 3:2 纯白底、无字，放到指定项目路径。记录实际工具、可获得的版本、调用方式、提示词、参考图、对应原文和输出 SHA-256，逐图验收。

**角色 identity 写法**：衣服一律写成白色（white top / white trousers），不写灰、黑、米、蓝等颜色；发色黑；加一句 tiny orange cuffs。样板「小宇」的白卫衣 + 白长裤 + 橙袖口是标准。

**主角性别跟声音走**：学生第一人称稿里，男声主角画男学生、女声画女学生（性别判断不了时默认女声、女学生）；cast.json 主角写 `gender`（male/female），identity 开头直接写 boy/girl；config.json 记 voice、narrator_is_protagonist、protagonist_cast，脚本会核对。

**母亲角色造型**：按项目人物标准，把母亲设计为漂亮、有成熟气质、修长匀称、打理得体、穿着简洁有品味的中年女性。提示词用正向细节描述整洁发型、优雅比例、利落剪裁、精致五官和从容亲和的气质；衣服仍遵守本 Skill 的白色填充、黑色轮廓和橙袖口规则，不加色彩或浓妆来表达品味。真实情绪由镜头表决定，不得把忧伤、克制画成邋遢、衰老或不修边幅。详细标准见 `references/workspace/CHARACTER_VISUAL_STANDARD.md`。

**服饰参考资产（强制）**：妈妈当前有 3 张可选服饰参考（两款旗袍、一款连衣裙），男女班主任各有一张，文件均在 `assets/characters/wardrobe-reference-v01/`。新建项目会自动复制整个目录到项目内同路径。`design/cast.json` 给妈妈/班主任标记 `wardrobe_role`，每个实际出镜镜头在 `design/shots.json` 的 `wardrobe_references` 中按 cast key 选出服饰参考。妈妈必须逐镜按脚本选择一张，不把固定衣服套用全片；教师按角色性别使用对应图。任何新生成人物镜头只要出现妈妈/班主任，就必须将对应图作为图像输入实际附加到生图调用，不能只在文字提示词中提路径。

`gen_sprites.py` 会检查参考是否存在、角色类别是否匹配，并在 CLI 调用中真实附加；`--emit-only` 后用于 Codex 内置生图时，必须把该镜头 `qc/imagegen-run.json` 中的 `ref` 路径逐一传入 `referenced_image_paths`，再把实际传入的路径写回同一记录的 `attached_ref`。模板/清单校验会拦截缺失引用，不能跳过。服饰图只作衣服剪裁与廓形参考，不复制参考人物的身份、脸、发型、表情、鞋子、姿势、体型细节、眼镜或道具。旧字段 `reference_images` 代表同一角色身份参考，不要与服饰参考混用。

**多人白板版式**：这里的“多人”指同一块白板呈现多个不同家庭/个案，不是同户成员数量。A 主次错落、B 纵向三段、C 三点均衡三张版式图都已审核通过并保存在 `assets/layouts/multi-household-v01/`，按每块白板的脚本节奏选用；同一视频不同板可混用。整板镜头可在 `shots.json` 使用 `layout_reference_images` 数组列出对应资产；提示词必须说明附件只参考空间层级、留白与疏密，不复制人物、案例事实、文字、道具或背景。每格只画原稿出现的家庭情况，格与格留白分开、不共用房间/家具/视线；正式镜头仍要逐格对应原稿和表演表。

## B 表演表模板（shots.json 每个镜头）
```
id / asset（与事件表 hero 的 id 对应）/ cast / narration（该画板口播原文）
第 1 块另加 opening_plan：前 5 秒动作清单（口播短语 → 画什么，时间点），见 OPENING_SPEC.md
source_objects[]：验收后逐张登记源图里已经存在的物件及位置；overlay_objects[]：列出代码新增的物件、对应的口播短语及其含义。符号（圈/叉/勾/箭头）也逐项登记；不得重复画源图对象或遮挡它们，符号没有语义锚点就删除。不得从“听到/看到某物”推导叉号或其他相反语义。
scene（英文：全身或半身、朝向、手和脚在做什么、眉眼嘴、视线；写"安静的忍耐/克制"等具体情绪，禁止 "sad""emotional" 这类空词）
roles[]: cast_id / name / age / emotion / face（眉眼嘴）/ body（肩背手脚）/ gaze / action / avoid
wardrobe_references: { cast_id: ["assets/characters/wardrobe-reference-v01/具体服饰文件.png"] }，逐镜指定每位妈妈/班主任实际要附加的服饰参考
observation: 生成后实际看图写（读得出什么情绪、什么动作），不是复述提示词
reviewed: 验收通过才设 true
```
情绪要对应口播的那一句，不是对应整篇；同一人物不同画板的姿态和表情不同；一画板一图，同图全片 ≤2 次。

## C 逐图验收（看联系表，逐张答）
1. 是同一个人吗（脸、发型、衣服）？2. 年龄、体态对吗？3. 手、脚、五官正常吗？**手要放大逐只数**：每人是否恰好两只手、一左一右（不是两个右手）、各五指、没有多出的手或手臂、没有长在身体里或手搭手的错位？把结论写进 hands_check（例：“妈妈：右手捂嘴、左手握裙摆，两只手，一左一右”）。4. 表情和动作读得出口播这一句的情绪吗？5. 线稿干净、纯白底、无文字？任一否 → 重生，不放行。

## D 独立审片提示词（第 9 步，审画面预览版；派独立 agent，不给它看你的结论）
> 你是独立审片员。画面预览版：<renders/名-visual-vNN.mp4>（无封面、无配乐；时间轴与成片正片一致）；原稿：brief/narration.txt；对齐表：qc/sync-report.md；锁定配音：<assets/audio/…wav>；节奏表：qc/panel-rhythm.json；表演表：design/shots.json。请先跑 `panel_check.py --video <预览版>` 取每块画板写完的那一帧并逐块看（圈/箭头是否指对、文字是否互压），再另外抽帧（至少每块画板 2 帧，含镜头离开前 0.3 s 的一帧）并逐项核对：①文字出现是否与口播对齐 ②字幕与口播是否一致、断点是否合理 ③人物表情动作与该句口播是否相符，同一人物身份/性别是否一致 ④是否有裁切、压字幕带、压标题区、压人物脸 ⑤每个圈/叉/勾/箭头是否对应原文短语与含义（对照 shots.json 的 overlay_objects），有无重复画源图已有物件 ⑥每块画板的字和符号在镜头离开前是否有可读的瞬间 ⑦结尾 1.5 s 留白与渐隐 ⑧开头规范（`OPENING_SPEC.md`）：先跑 `opening_check.py --ignore-start 0 --video <预览版>` 并附结果；再抽 0.7/1.7/2.5/3.4/4.2/5.0 s 帧（预览版无 0.2 s 封面），逐帧回答：人物是否 0.5 s 内起笔？0–5 s 内除字幕外是否每一秒都有新笔画？新元素是否和当时的口播对应、有没有压在人物上、屏幕文字是不是口播原文、橙色是否过多。
>
> **每条发现必须分级**，并写帧号/时间 + 现象 + 违反的规则出处（文件名）：
> - **阻断**（必须改）：违反 SKILL/STYLE_SPEC/OPENING_SPEC/CHECKLISTS 的硬规则，或观众会看错、看不到——文字/符号没有可读瞬间、压人物脸或字幕带、裁切、屏幕文字与原稿不符、符号语义错或指错对象、人物身份/性别跳变或多手、字幕与口播错位、开头规范不过。
> - **记录**（不改，写进 STATUS）：审美偏好、"可以更好"，以及下列固定版式本来就有的现象。
>
> 以下是本画风固有机制，**不算缺陷、不报阻断**：口播停顿时字幕条暂时消失；镜头平移时露出相邻画板边缘、握笔手停在画面右缘；画到一半时手和笔经过人物（过程态，不是完成态）；写字比对应口播晚 0.2–0.8 s；字幕去标点；画板最后一笔在镜头开始离开后 0.2 s 内画完（事件表自检已卡上限）。锁定配音里 ASR 同音字误识不算画面问题。
>
> 只报你实际看到的问题，不要夸奖；没看到就写"未核对"。最后一行写结论：`阻断 N 条` / `可进入混音`。

## D2 成片复核提示词（第 12 步，只核对封装；派独立 agent）
> 你是成片复核员。成片：<renders/名-final-v01.mp4>；第 9 步已审过的画面版：<renders/名-visual-vNN.mp4> 及其审片报告；已通过封面：<renders/名-cover-vNN.png>；混音报告：qc/mix-report-*.json。画面内容已经审过，**不重审画板**；只核对第 9 步之后新增的部分：①第 0 帧与已通过封面一致、第 6 帧进入正片、前 6 帧静音、总帧数 = 画面版 + 6 ②`opening_check.py --video <成片>` 通过（含 0.2 s 封面） ③口播清晰、无音效、配乐在口播处压低、无爆音（看混音报告峰值） ④结尾 1.5 s 留白与渐隐 ⑤抽 3 帧（开头、中段、结尾）与画面版同时刻比对，确认没有拼错版本或错位。分级同 D；画面版里已经存在且第 9 步未判阻断的现象，只记录不返工。最后一行写结论：`阻断 N 条` / `可交付用户确认`。

## E 最简开场提示词

流程、画风、预检和审核由 Skill 负责；提示词只提供本次任务变量。

```text
用 $why-handdrawn-video 制作视频。
平台/受众：【平台】，【目标受众】。
目标：【种草 / 信任 / 转化】。
口吻：【口吻，例如亲切口语、像人说话】。
标题：【标题】
正文：【完整口播稿】
```
