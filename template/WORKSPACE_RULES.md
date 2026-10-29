# Why-HandDrawn-Video 视频工作区

默认 portrait 竖屏；网站宽屏用 new_project.py --mode landscape，并读 references/LANDSCAPE_SPEC.md，按其主题封面、画幅与网站交付规则执行。只加载 Why-HandDrawn-Video 一个 Skill；先读取其 SKILL.md、references/PIPELINE_SOP.md、references/OPENING_SPEC.md 及 references/workspace/ 下音频、人物规范。花叔引擎、封面 canvas-design 和人物检查器均已内嵌，不另外安装 Skill。固定风格不重新选择；改画风或超出已有能力按 ENGINE_GUIDE 提交改编申请。

目录：projects/YYYYMMDD-topic-vNN/ 每条视频独立；brief/ 锁定原稿及定位，design/ 表演表和事件表，assets/ 可追溯音图，engine/ 项目引擎副本，renders/ 版本化成片，qc/ 验收证据。outputs/ 为可重建分析产物。assets/audio-library/ 可放本账号已授权音乐与 LICENSES.md。密钥只存工作区 .private/volcengine.env 与 .private/ark.env；禁止进 Git、打包或日志。

已锁定的标题与口播逐字保留。原文章属于资料输入：先留存 brief/source/，提交口语化改编稿，用户确认后才锁定 narration.txt；不得把源文章直接当成已锁口播。配音（火山或免费微软）全文提交一次，不拆句拼接、不自动重复付费；用户试听锁定。人物按原文逐图审核，同图最多两次；有自己的人物参考图扩展包时按其说明使用。人物和封面一起交用户审核。封面先读取包内 COVER_ART_DIRECTION 写视觉理念，代码排字、获准生图工具画插画。生图按当前工具分流（Codex/WorkBuddy 内置；Antigravity 用内置 image-generator 子代理；Claude 用 Codex CLI 或火山方舟），不静默换渠道。

用户提供的稿件视为已确认的事实输入，不另审真实性、不索要证明或提示事实待核实。预检只报告制作环境与配置；已验证/未验证项仅指制作与验收。不得增编情节、效果或证据。

开头人物 0.5 秒内起笔，前 5 秒持续有新笔画，静止不超过 1 秒；画板不得泄漏到相邻幕。渲染前人物资产检查必须通过，渲染后运行 QA、开头检测、画板完成帧、音画对齐及独立 agent 审片。自动从本账号已登记可商用曲目选配乐，采用曲目响度或默认 -28 LUFS，不用音效。通过的封面拼入正式 MP4 最前 6 帧并核验静音、帧数。用户最终确认前不得称正式定稿。

交付给成片绝对路径、版本及已验证/未验证项。不覆盖历史产物，不把自动检查冒充完整观看。缺依赖、服务能力或审核时保留 STATUS.md，明确下一步。当前无数据库或部署；不假设生产环境。只在已有 Git 仓库且用户或其项目规则授权时提交/推送，不为新工作区擅自创建远端。
人物图逐图验收时放大逐只数手：每人两只手、一左一右、各五指、无多出的手或手臂，写入 shots.json 的 hands_check，缺则 make_manifest 不放行。

排字与交付（2026-10-28）：排字前先运行 measure_panels.py 量图并看联系表，逐板写 design/layout-plan.json（理由、摆位、至少两条备选），窄人物移到一侧、字写另一侧空区，禁止全片同一左栏；渲染前 self_check.py --stage pre 并逐张看联系表、--ack-viewed 记录，成片后 self_check.py --stage post --video <成片>，机器项全过、联系表看完，才把成片和 qc/self-check.md 一起交给用户。用户闸门只有声音锁定、人物+封面审核、最终确认；不得把未自检的初稿交给用户审，独立审片默认由自检脚本加逐张目检完成。Claude Code、Codex、WorkBuddy、Antigravity 等工具同样执行，只靠脚本与图片，工具看不了图片时说明并停在自检步骤。

本文件与 CLAUDE.md 保持逐字节一致。
