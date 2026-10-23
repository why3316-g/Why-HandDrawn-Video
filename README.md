# AI一键生成手绘视频（Why-HandDrawn-Video）

支持默认竖屏 portrait（1080×1920）和网站宽屏 landscape（1920×1080）。对 AI 说“把这篇文章做成网站宽屏手绘讲解视频”；入口会读取 references/LANDSCAPE_SPEC.md，先改编并确认口播。新建命令加 `--mode landscape`；原有竖屏命令不变。宽屏验收用 `smoke_test.py --mode landscape --out <新目录>`，网站交付用 `export_website.py`。

给 AI（Claude Code / Codex / WorkBuddy）一个标题和一份口播稿，它帮你做出一条**白纸线稿 + 马克笔手绘 + 暗色字幕条**的竖屏（1080×1920）视频：配音、画人物、手绘动画、字幕、封面、混音、质检，一条龙。

> 画风固定、流程固定，所以出片稳定。适合讲故事、讲案例、讲观点的口播类短视频（视频号 / 抖音 / 小红书）。
> **赛道说明**：作者只在自己的赛道上完整跑过。其他赛道（职场、育儿、理财、知识科普……）理论上都能用，但没有逐一测试，效果请自己判断，欢迎提 issue 反馈。

---

## ⚠️ 开始前，必须先看这 5 件事

### 1. 运行软件：不用你手动装（但要联网）
对 AI 说"用 why-handdrawn-video 做视频"后，第一步环境检查会**自动下载安装**缺的东西，不需要你逐个确认：Python 依赖、FFmpeg、Chromium 浏览器（约 150MB）、独立转录模型（约 0.5GB）。官方源失败会自动换国内镜像。
你只需要提前有 **Python 3.10+**（装好并能在命令行输入 `python`）。想手动提前装，运行：

```bash
python scripts/env_check.py --install
```

### 2. 配音：默认免费微软语音，想要更好效果请配火山密钥
| 方案 | 效果 | 要不要配置 |
|---|---|---|
| 免费微软语音（edge-tts） | 一般，偶尔会读错、语气偏平 | 不用，自动用 |
| **火山引擎豆包语音 2.0（推荐）** | 明显更自然 | 要自己申请密钥 |

说明：免费微软语音走的是微软的非官方接口，可能随时失效；需要 `edge-tts` 7.3.1 以上（环境检查会自动装）。

**配置火山配音（约 5 分钟，新用户有免费额度，用完按量计费，以控制台为准）：**
1. 注册并实名认证火山引擎账号，打开豆包语音控制台：<https://console.volcengine.com/ark/region:cn-beijing/tts/tts2>
2. 开通「语音合成大模型 2.0」。
3. 在控制台的 **API Key 管理** 里创建一个 API Key，复制下来。
4. 在你的**视频工作区**（不是 Skill 文件夹）新建文件 `.private/volcengine.env`，内容（把引号里换成自己的 Key，保留双引号）：
   ```
   DOUBAO_SPEECH_API_KEY="你的Key"
   DOUBAO_SPEECH_VOICE_TYPE="zh_male_dayi_uranus_bigtts"
   ```
5. 完成。之后自动检测到 Key 就用火山；想强制只用某一种，在工作区 `.hdv-workspace.json` 里写 `"tts_provider": "volcengine"`（或 `"edge"`）。固定了火山但没配 Key 时会直接报错，不会偷偷降级成微软。

> 控制台界面会改版，菜单名以实际页面为准。**密钥只放 `.private/`，不要提交到 Git、不要发给别人。**

音色有三个：男声「大壹」（默认），女声「小何 2.0」（学生第一人称），女声「温柔妈妈 2.0」（家长角度且家长是妈妈，固定配方：语速 19 + 重指令 + 本地压停顿；家长是爸爸用大壹）。口播是学生第一人称时，**主角性别跟着声音走**：男声 = 男生主角，女声 = 女生主角；从稿子判断不出性别时用女声。

### 3. 生图：三条路，看你用什么 AI 工具
| 你用的工具 | 生图怎么办 |
|---|---|
| **Codex / WorkBuddy** | 直接用内置生图工具，不用配置 |
| **Claude Code**（首选） | 装 **Codex CLI** 并登录（需要 ChatGPT 付费会员账号）：`npm i -g @openai/codex`，然后运行 `codex` 按提示登录。工作流会调用它生图，且**只用 Codex 默认模型**，默认模型不是低消耗型号时会先问你，避免额度被烧光 |
| **Claude Code（没有 ChatGPT 会员）** | 用**火山方舟 Seedream 生图 API**：见下 |

**配置火山方舟生图（Seedream）：**
1. 登录火山引擎控制台，进入「火山方舟」：<https://console.volcengine.com/ark>
2. 在「开通管理」里开通图片生成模型 **Seedream 4.5**（模型 ID `doubao-seedream-4-5-251128`）。有免费额度，用完是否自动转按量计费以控制台说明为准，请自己留意。
3. 在「API Key 管理」创建 API Key。
4. 在视频工作区新建 `.private/ark.env`：
   ```
   ARK_API_KEY="你的方舟Key"
   ```
5. 生图时加参数 `--image-backend volcano`（告诉 AI"用火山生图"即可）。尺寸不被接受时设置环境变量 `ARK_IMAGE_SIZE=2K`；换模型设 `ARK_IMAGE_MODEL`。

> 诚实说明：火山生图后端已有离线测试，但作者尚未用真实账号长期验证；遇到报错（401 密钥无效 / 404 模型没开通 / 400 参数不合法）按提示处理或提 issue。

### 4. 三个必须你亲自点头的环节（AI 不会替你跳过）
1. **声音锁定**：先生成整条口播的试听音频，你听完确认，才锁定为成片音轨。
2. **人物 + 封面审核**：人物图和封面一起给你看，你点头才继续渲染。
3. **成片最终确认**：渲染、质检、独立审片之后，你确认才算定稿。

### 5. 配乐：不随包提供
背景音乐没有再分发授权，所以仓库里没有。请自己准备**可商用**的曲目，放到视频工作区 `assets/audio-library/bgm/`，并按 `assets/audio-library/LICENSES.md` 的表格登记（"可商用=是"才会被选用）。没有曲目时，生产前检查会明确提示缺项，不会偷偷出一条没配乐的片。

---

## 怎么用

1. **安装**：把整个 `Why-HandDrawn-Video` 文件夹放到你的 AI 工具的 Skills 目录：
   - Claude Code：`~/.claude/skills/Why-HandDrawn-Video/`
   - Codex：`~/.codex/skills/Why-HandDrawn-Video/`
   - 其他工具按其 Skills 导入方式。只复制 `SKILL.md` 不行，要整个文件夹。
2. **对 AI 说**：
   > 用 why-handdrawn-video 做一条视频。受众：……；平台：视频号；目标：……；口吻：像人说话。标题：……  口播稿：……
3. 跟着 AI 走：环境检查 → 建项目 → 配音试听（你确认）→ 设计人物 → 封面（你确认）→ 手绘动画渲染 → 质检 → 混音 → 成片确认。
4. 成片和过程文件都在你的视频工作区 `projects/日期-主题-v01/` 里；AI 会告诉你成片的完整路径。

标题和口播稿**逐字保留**，不会被改写；你提供的稿子视为已确认的事实输入。

## 名词解释：独立转录是什么
配音生成后，要有一个**独立**的语音识别（faster-whisper small 模型，本地运行）把成片声音重新听写一遍，和你的原稿逐字对照，防止配音读错字、漏句。模型约 0.5GB，环境检查会自动下载，不用你管。

## 可选扩展：自己的人物 / 服饰 / 版式参考图
公开版不带任何品牌 Logo、固定人物或服饰参考图。如果你想让某个角色（比如你的 IP 形象）全片保持一致，把参考图放进视频工作区 `assets/` 并在项目 `design/cast.json` 的 `reference_images` 里登记即可（见 `template/design/cast.json`）。

## 常见问题
- **检查提示"文件已变更"**：你改过包内文件。重新下载原包，或运行 `python scripts/verify_bundle.py` 看具体哪个文件。
- **免费微软语音报 403**：`pip install -U edge-tts`（需 7.3.1 以上）；仍失败说明微软接口变了，请配火山。
- **没有 ChatGPT 会员也没有火山账号**：目前没有第三条免费生图路径；Codex/WorkBuddy 内置生图是最省事的。

## 开发与测试
```bash
python scripts/verify_bundle.py            # 校验完整性清单
python -m unittest discover -s tests       # 回归测试（不调用任何付费服务）
python scripts/smoke_test.py --out <空目录> # 真实渲染一条离线测试视频
```
来源与许可见 `THIRD_PARTY_NOTICES.md` 和 `upstream/SOURCES.json`。

## G端机构宣传片

学校、教育局、企业等官网宣传片用content_type=institutional_promo；默认儒雅逸辰2.0（yichen）、语速0与正式播音指令，封面用正式机构宣传片风格，正文仍手绘。唯一细则见references/INSTITUTIONAL_PROMO.md；本节覆盖其他段落旧默认，仅限机构宣传片。用户明确要求原文直接做视频时不得强制改写；明确要求先看静态图可先出美术预览，不伪造全文锁音、不进入动画渲染。
