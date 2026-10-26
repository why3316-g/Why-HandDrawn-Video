# 工具与环境约定

## 必备
| 项 | 要求 | 检查 |
|---|---|---|
| 单包来源 | 手绘引擎必要子集与人物检查器；花叔/封面方法已整理为包内参考，只有一个 Skill 入口 | verify_bundle / env_check |
| Python | 3.10+，numpy、Pillow（骨架提取自带实现） | env_check |
| uv + playwright + Chromium | 渲染引擎用 `uv run --no-project --with playwright` | env_check |
| ffmpeg / ffprobe | 混音、抽帧、探测 | env_check |
| 字体 | 引擎自带 LXGWWenKai-500.woff、NotoSansSC-500.woff；封面优先使用包内 `assets/fonts/NotoSansSC-VF.ttf`，无需预装系统字体 | env_check / smoke_test |
| 生图 | 按执行工具分流：Claude 与 WorkBuddy 调用当前安装并已登录的 Codex CLI（`codex`，Windows 用 `codex.cmd`）；Codex 使用自身内置生图工具；**Gemini Antigravity 默认使用自身内置的 `image-generator` 子代理生图**；三条路径都不换渠道 | Claude/WorkBuddy 走 CLI 检查；Codex 与 Antigravity 使用各自内置能力 |
| 火山配音凭证 | `.private/volcengine.env`，只按名读取 | — |
| 全文配音 | `scripts/audio/generate_candidate.py` + `upstream/openmontage-audio/`；requests 运行库 | env_check --production |
| 独立转录 | faster-whisper + small 模型或 `HDV_ASR_MODEL` 指定本机模型 | env_check --production |

空工作区由 new_project.py 先建同步规则再建项目，不要求携带原来的项目仓库。音乐先读本工作区覆盖库，否则使用随包库；公开分享版不含原三首歌，需要接收者登记自己的授权音乐。默认预检仅检查包与渲染依赖；正式制作另跑 `--production`，△ 不是全流程就绪。

## 能力分级
- **Codex CLI 生图模型**：只用 `config.toml` 的默认模型，不传 `--model`、不改配置。默认是 `gpt-6-luna` 才直接生成；不是则先问用户，同意后 `gen_sprites.py --confirm-model <模型名>`。脚本已强制检查。
- **Claude / WorkBuddy**：必须能从当前环境调用已安装的 Codex CLI；有 Python 等运行依赖后跑完整 SOP。不得切换到 Claude 或 WorkBuddy 自带的生图工具。
- **Codex**：用 Codex 内置生图工具；先运行 `gen_sprites.py --emit-only` 生成提示词，再逐张通过内置工具生图并保存到提示词指定路径。不得为了生图改走 Codex CLI。
- **Gemini Antigravity（2026-10-26 新增）**：生图默认用 Antigravity 内置的 **`image-generator` 子代理**（基于 Antigravity 自带的图像生成服务），不调用 Codex CLI，也不换用 Antigravity 之外的图像服务。做法与 Codex 内置路径一致：先 `gen_sprites.py --emit-only --emit-tool "Antigravity image-generator 子代理"` 导出提示词，再逐张把该镜头 `qc/imagegen-run.json` 的 `ref` 全部作为参考图交给子代理，图存到提示词指定路径。只把这个子代理当生图执行者：提示词、参考图、画风与验收一律按本 Skill，不让它改写角色、镜头或画风要求。宽高比按提示词里的 landscape 3:2 传入（子代理只接受宽高比，不接受像素尺寸），不传分辨率参数。
- **指定生图渠道不可用**：Claude / WorkBuddy 无法调用当前 Codex CLI，Codex 内置生图工具不可用，或 Antigravity 的 `image-generator` 子代理不可用（未配置、额度耗尽、调用失败）时，停止生图并报告缺失项；不得静默改用其他渠道。只有用户明确要求更换生图渠道时才调整路径。
- **制作环境不可用**：没有 Python 或浏览器渲染环境时，停下并报告具体缺项，不假装完成。

Codex 与 Antigravity 的内置生图路径下，图像必须保存到提示词中指定的项目相对路径。生成后登记实际工具/可获得的版本信息、提示词、参考图、调用方式、对应原文与输出 SHA-256，并按本 Skill 逐图验收。不得把仅导出的提示词记作已完成生图。

## Windows 注意
- Python 路径用 `E:/...`，不用 `/e/...`；每个脚本（尤其 `mix_audio.py`、`make_cover.py`）都先设置 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`；`PLAYWRIGHT_BROWSERS_PATH` 指向本机浏览器目录（脚本会自动设置）。
- 大文件用写文件工具，不用超长 heredoc。
- 渲染前 `new_project.py` 会给项目内引擎副本打补丁（UTF-8 读取、本地服务队列、失败请求日志）；补丁断言上游代码模式，上游变了会报错而不是静默跳过。
