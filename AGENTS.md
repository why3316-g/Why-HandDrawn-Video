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
