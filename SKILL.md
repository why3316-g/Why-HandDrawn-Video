---
name: why-handdrawn-video
description: 把标题和口播稿做成固定画风（白纸线稿 + 橙色强调 + 马克笔手绘 + 暗色字幕条）的竖屏故事/讲解视频；给定标题和口播稿时使用。单包含制作、自检和审核所需资源，不用于其他画风或横屏。
---

# Why-HandDrawn-Video

只用本包完成现有固定手绘工作流；保持已批准的画风、剪辑和声音。标题正文逐字锁定，受众/平台/目标/口吻不清时先确认。运行软件由 `env_check.py --install` 自动补齐；配音密钥、生图渠道与账号按 README.md 配置。

用户提供的稿件视为已确认的事实输入，不另审真实性、不索要证明。预检只报告制作环境与配置；“已验证/未验证”仅指制作质量与验收。保留原稿保真检查，不增编情节、效果或证据。

## 开始

读取 `references/PIPELINE_SOP.md`，运行 `python <skill>/scripts/env_check.py --install`（自动安装缺失的运行依赖、不需要逐项征求同意）并告诉用户结果；正式制作再用 `--production` 检查服务配置。缺项先处理，检查失败不能继续冒充完成。

按 SOP 执行，声音锁定、人物逐图与封面审核、最终成片确认处必须等待用户；已明确的决定沿用。配乐由执行工具从已授权库自动选择，不设挑曲闸门。独立审片不得省略。

**声音闸门（强制）**：第 3 步生成全文配音并跑完 `check_voice.py` 后，向用户发试听消息（音频绝对路径、音色与选择理由、时长、红/黄项逐条），然后**结束本轮回复，等用户试听**；等待期间不做第 4 步及之后的任何事（不写表演表、不出封面底稿、不生图）。用户在对话里明确说通过/锁定后，运行 `python <skill>/scripts/lock_voice.py --audio <mp3> --user-says "<用户原话>"` 记录；没有这份记录，`gen_sprites.py` 和封面生图拒绝运行。用户没明确说通过时，不得自行运行 lock_voice.py。

**制作中不改工作流**：做视频时，原则上不得修改本 Skill 的任何内容（SKILL.md、references、scripts、template、assets），也不得改写项目里复制来的 `design/hdv/`、`engine/` 代码，或另写脚本绕过、替代包内检查。确需修改时立即停下，向用户说清：为什么要改（遇到什么问题、证据）、改什么（哪些文件、具体内容）、具体方案、对其他视频的影响和风险、不改的话有什么替代做法；用户明确回复同意修改后才能动手。批准前该视频停在当前步骤。

可选扩展：用户若在视频工作区放了自己的人物/服饰/版式参考图，并在 `design/cast.json`、`design/shots.json` 登记，则生图时必须真实附加并记录；参考图只定身份或服饰，不直接入镜，脸/发型/表情每镜头重设。没有扩展包时按 `references/workspace/CHARACTER_VISUAL_STANDARD.md` 的通用人物规范设计，references 里提到的品牌人物、妈妈/老师服饰、固定版式等条款仅在对应素材存在时适用。

每块画板 3–7 秒为目标，2.5 秒为硬下限、8.0 秒为硬上限；拆分必须跟随口播里的动作、情绪或信息转折。每张分镜图都登记源图已有物件和代码新增物件，圈/叉/勾/箭头必须写明对应原文短语及具体含义。渲染验收逐板检查过程节奏、源图重复物件、遮挡和符号误义；只看完成帧或开头自动检测通过不能放行。

`<skill>` 为本文件夹；`new_project.py <短名> --workspace <视频工作区>` 可初始化空目录。项目内记录 BRIEF、STATUS、来源与版本，不覆盖旧产物。

## 按环节读取唯一规范

| 环节 | 必读 |
|---|---|
| 动画方法、引擎与事件表 | `references/ENGINE_GUIDE.md`、`STYLE_SPEC.md`、`LAYOUT_LIBRARY.md`；节奏手感与易错点见 `WHITEBOARD_GRAMMAR_Y3.md`、`CRAFT_LESSONS.md`（公开版不带样板案例，事件表写法见这些文件与 `template/design/film.py`） |
| 开头与画板安全 | `references/OPENING_SPEC.md` |
| 全文配音（火山或免费微软）与私密配置 | `references/workspace/AUDIO_STANDARD.md` |
| 人物表演、用色与复用 | `references/workspace/CHARACTER_VISUAL_STANDARD.md`、`PROMPT_PACK.md`；有自己的参考图扩展包时按其说明使用 |
| 封面 | `references/COVER_SPEC.md`、`COVER_ART_DIRECTION.md` |
| 音乐与混音 | `references/AUDIO_MIX.md` |
| 逐项验收与独立审片 | `references/CHECKLISTS.md`、`PROMPT_PACK.md` 的审片任务 |
| 环境、工具分流与迁移 | `references/TOOL_CONTRACT.md`、`README.md` |

所有参考路径从本包根解析，同目录短名从 references/ 解析。不加载另一个 Skill；来源子集只作技术实现，不能覆盖本包专用规则。超出固定能力时按 ENGINE_GUIDE 的改编规则沟通，不静默换供应商或画风。

完成须具备全部自动检查、实际画面/声音核验、独立审片和用户确认。交付给成片绝对路径、版本、已验证与未验证项。技术测试音调/参考图不算真实作品审核。
