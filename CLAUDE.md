# Why-HandDrawn-Video 维护规则

## 目标与目录
- 本仓库根目录就是一个可独立安装的 Skill；入口 SKILL.md，使用方式见 README.md。
- scripts/ 运行与维护脚本；references/ 唯一规范；assets/ 获准素材与许可；template/ 项目模板；tests/ 回归测试；upstream/ 当前流程需要的来源子集和许可。
- 视频项目放仓库外的视频工作区；不得提交缓存、依赖目录、私人凭证（`.private/`、`*.env`）或未获再分发授权的音乐、品牌素材、他人肖像。

## 修改与验证
- 先改规则再改实现；本文件与 CLAUDE.md 必须逐字节一致。标题原文、声音锁定、人物和封面审核、最终确认及独立审片规则按 SKILL.md 执行。
- 修改后：`python scripts/verify_bundle.py --write` 重建清单，再 `python -m unittest discover -s tests -v`；运行链有改动再跑 `python scripts/smoke_test.py --out <仓库外全新目录>`。更新上游文件须按 upstream/SOURCES.json 登记来源与改动依据。
- 本仓库为公开版：清单 profile 为 public；不含品牌素材、人物参考图和配乐。提交前确认没有个人信息、密钥、本机绝对路径。

## 双模式维护
- portrait 是旧项目默认模式；landscape 是1920×1080网站手绘讲解，唯一区别规范见 references/LANDSCAPE_SPEC.md。原文章先改编并锁口播，用户素材不进入公开包。
- 模式运行链变化必须分别跑 `smoke_test.py --mode portrait --out <新目录>` 与 `--mode landscape --out <另一新目录>`，两种模式都通过才能发布。

## G端机构宣传片

学校、教育局、企业等官网宣传片用content_type=institutional_promo；默认儒雅逸辰2.0（yichen）、语速0与正式播音指令，封面用正式机构宣传片风格，正文仍手绘。唯一细则见references/INSTITUTIONAL_PROMO.md；本节覆盖其他段落旧默认，仅限机构宣传片。用户明确要求原文直接做视频时不得强制改写；明确要求先看静态图可先出美术预览，不伪造全文锁音、不进入动画渲染。

## 宽屏风格定稿
landscape与portrait是两种独立风格。宽屏手部按 references/HAND_POOL.md：公开版不带素材池图片，退回到 assets/marker-hand-landscape-v01.png 短手（scale .18、袖口原样收口、后方留白）；自用版则与竖屏同一素材池、同一 45°。无装饰竖色条；按内容穿插居中人物、居中文字/逻辑和左右讲解。唯一标准references/LANDSCAPE_LOGIC.md。竖屏原实现保留；用户明确原文直转时不强制改写。

## 排字测量与一次成片交付（2026-10-28）
- 排字前先运行 measure_panels.py 量图并看联系表，逐板写 design/layout-plan.json（理由、摆位、至少两条备选），窄人物移到一侧、字写另一侧空区，禁止全片同一左栏；渲染前 self_check.py --stage pre 并逐张看联系表、--ack-viewed 记录，成片后 self_check.py --stage post --video <成片>，机器项全过、联系表看完，才把成片和 qc/self-check.md 一起交给用户。用户闸门只有声音锁定、人物+封面审核、最终确认；不得把未自检的初稿交给用户审，独立审片默认由自检脚本加逐张目检完成。Claude Code、Codex、WorkBuddy、Antigravity 等工具同样执行，只靠脚本与图片，工具看不了图片时说明并停在自检步骤。
