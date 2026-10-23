# 第三方来源与许可

源子集、原始与当前 SHA-256 及改动理由见 upstream/SOURCES.json。仅有本包一个技能入口，内部参考不是另外安装的 Skill。

| 内容 | 来源与许可 |
|---|---|
| 手绘引擎与 QA 子集、方法整理 | alchaincyf/huashu-art-motion，MIT；保留 upstream/huashu-art-motion/LICENSE |
| 封面美术方法整理 | anthropics/skills 的 canvas-design（Apache 2.0），许可保留于 upstream/canvas-design/LICENSE.txt |
| 字体 | 霞鹜文楷与 Noto Sans SC，SIL OFL，见 assets/fonts/ 与引擎字体目录的许可文件 |
| 火山配音实现 | upstream/openmontage-audio 为源自 OpenMontage 项目的豆包语音调用代码子集，未单独附带许可证文件；使用或二次分发前请自行核实其上游许可 |
| 免费微软语音 | 依赖 PyPI 包 edge-tts（运行时安装，不随包分发），调用微软非官方接口，随时可能失效，请遵守微软服务条款 |
| 火山方舟生图 | 通过使用者自己的 API Key 调用，不随包提供密钥或额度 |

不打包私人凭证、依赖安装目录、缓存或历史视频；不提供配乐，使用者须自备可商用曲目并自行登记。保留许可不是转移服务账号、音乐授权或保证可用额度。

- `assets/marker-hand-landscape-v01.png`：以包内手部素材为参考，经Codex内置图片编辑生成并由用户审核的通用短袖口素材；仅landscape默认使用，无品牌和真实人物肖像。
