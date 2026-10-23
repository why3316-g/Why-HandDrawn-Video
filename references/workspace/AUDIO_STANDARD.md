# 全文火山配音规范

## 家长角度·妈妈：定稿配方（2026-10-22，任何执行者都必须照做）

**音色 = 温柔妈妈 2.0 `zh_female_wenroumama_uranus_bigtts`**（取代鸡汤女 2.0：鸡汤女偏慢、停顿多、不自然，已停用）。
**配方 = 语速 19（≈1.19 倍）+ 重指令 + 生成后本地压停顿**，三步缺一不可：

```bash
# 第 1 步：全文一次合成（脚本已内置语速 19 与该音色的重指令，不要手写 API 调用）
python <skill>/scripts/audio/generate_candidate.py \
    --project . --provider volcengine --voice wenroumama --version v01 --join-lines

# 第 2 步：压停顿（只删字间纯静音，语音采样一帧不动；时间戳精确平移）
python <skill>/scripts/audio/compress_pauses.py \
    --project . --wav assets/audio/narration-volcengine-wenroumama-full-v01.wav \
    --json assets/audio/narration-volcengine-wenroumama-full-v01.mp3.json \
    --text brief/narration.txt --cap 0.35 --tag v02
# 然后把 design/config.json 的 volc_json / voice_wav / voice_mp3 指到 v02 的三个文件

# 第 3 步：自检（含 ASR）→ 用户试听锁定
python <skill>/scripts/check_voice.py --project .
```

**重指令原文（`additions.context_texts`，逐字使用，不要改写）**：

> 你现在很着急，几乎不给喘气的机会，一口气把话说完，声音有点发紧。

这条指令写在 `scripts/audio/generate_candidate.py` 的 `VOICE_DIRECTIVES['wenroumama']`，`--voice wenroumama` 时自动带上并写进回执（`voice_directive` / `voice_directive_source: voice_recipe`）。`--no-directive` 只用于对照实验，正式成片禁用。

**为什么是这条、这些数（2026-10-22 实测，同段 116 字）**：

| 配置 | 时长 | 字/s | 最长静音 | ≥0.4 s 停顿 | 中位基频 |
|---|---|---|---|---|---|
| 语速 19，无指令 | 21.72 s | 5.34 | 0.64 s | 8 | 182 Hz |
| 语速 19 + 轻指令（「自然一点，别拖」） | 22.01 s | 5.27 | 0.62 s | 9 | 178 Hz |
| 语速 19 + 中指令（「又急又慌，停顿短一点」） | 20.83 s | 5.57 | 0.59 s | 7 | 186 Hz |
| **语速 19 + 重指令** | **19.85 s** | **5.84** | 0.53 s | 6 | **198 Hz** |
| 语速 19 + 重指令 + 压停顿 0.35 | **19.34 s** | **6.00** | **0.38 s** | **0** | 198 Hz |
| 语速 30 + 重指令 | 18.62 s | 6.23 | 0.49 s | 5 | 182 Hz |

- 轻指令无效甚至更慢：**指令必须把情绪说透**，不要写「自然一点」这种空话。
- 「快」和「紧」不是一回事：语速推到 30 后基频回落到 182 Hz，语速上去了、紧张感没了。所以靠指令定情绪、靠 19 定节奏。
- 停顿服务端治不了（`mute_cut_*` 不支持 2.0 音色），只能第 2 步本地压。
- 判断"够不够急"用中位基频 + 基频 IQR（升高 + 起伏变大 = 更激动），不要只凭一次试听。

**执行者无关条款**：以上步骤由 `scripts/` 里的脚本完成，**不使用**任何手写 curl / 手搓 API 调用 / 其它供应商的音色。换 AI 工具（Codex、Claude Code、WorkBuddy）、换会话、换模型执行本工作流时，一律按本节命令与参数执行；`scripts/env_check.py` 第 0 步会检查 `generate_candidate.py`、`directives.py`、`compress_pauses.py` 是否齐全且可编译，缺任一即不得开始配音。改音色或改指令前必须先跑 `audition_variants.py` 横评并得到用户确认。

## 配音通道（auto / 固定）

`generate_candidate.py --provider auto|volcengine|edge`：优先级为命令行 > 环境变量 `HDV_TTS_PROVIDER` > 工作区 `.hdv-workspace.json` 的 `tts_provider` > auto。auto = 工作区配了真实火山密钥用火山，否则用免费微软语音（edge-tts，非官方接口，效果与稳定性不如火山，须 edge-tts ≥7.3.1）。**固定为 volcengine 时缺密钥直接报错，绝不静默降级到微软**；已有同稿候选换通道/音色等于新增一次合成，按下文规则需用户明确指令（`--confirm-voice-change`）。个人生产环境应在工作区固定 `volcengine`；下文“只用火山”指固定火山时的规则，微软通道沿用同一套全文一次、锁定、验收流程，输出文件名为 `narration-edge-<dayi|xiaohe|wenroumama>-full-vNN.mp3`（微软无成熟妈妈音色，wenroumama 槽位复用 zh-CN-XiaoxiaoNeural，仅作没配火山时的兜底）。

## 固定通道与配置

只用火山 Doubao Speech 2.0：批准音色三个——大壹 `zh_male_dayi_uranus_bigtts`（默认）、小何 2.0 `zh_female_xiaohe_uranus_bigtts`（女学生或性别不明的学生第一人称）、**温柔妈妈 2.0 `zh_female_wenroumama_uranus_bigtts`（家长角度且家长是妈妈，2026-10-22 起取代鸡汤女 2.0）**。音色选择（只批准三个）：默认用**大壹** `zh_male_dayi_uranus_bigtts`；口播稿是**学生以第一人称讲述自己的故事**时按性别选：男学生用大壹，女学生用**小何 2.0** `zh_female_xiaohe_uranus_bigtts`（火山豆包语音合成模型 2.0 通用场景女声）。依据是稿子本身：叙述者“我”是学生才算；性别无法从稿子判断时默认小何 2.0，不为选音色单独询问用户，但生成后照常停下等用户试听锁定（理由照常写进试听消息与 BRIEF）；**家长角度**脚本（脚本说明里标明是家长角度，口吻是家长讲述）：家长是妈妈用**温柔妈妈 2.0**，并按本节开头的三步配方执行（语速 19 + 重指令 + 压停顿），家长是爸爸仍用大壹；家长是妈妈还是爸爸以脚本说明为准，没写明时先问用户一次。陪伴师、第三人称叙述等其他口吻用大壹。选定的音色和理由写进试听消息与 BRIEF；脚本用 `generate_candidate.py --voice dayi|xiaohe|wenroumama`，其余参数（seed-tts-2.0、全文一次）不变，语速按下方「每音色语速」提交。同一全文已用一个音色合成后，改用另一个音色等于新增一次付费合成，须用户明确指令，脚本要加 `--confirm-voice-change`。 资源 `seed-tts-2.0`，默认音量，MP3 24kHz，请求词级时间戳。接口为 openspeech.bytedance.com/api/v3/tts/submit 与 query，X-Api-Key 鉴权。实现及公开参数在本包 upstream/openmontage-audio/；来源记录在 upstream/SOURCES.json。

**停用记录**：鸡汤女 2.0 `zh_female_jitangnv_uranus_bigtts` 于 2026-10-22 停用（用户判定"不够自然"），不再用于新片；历史项目里的产物保留，但不得作为新片音轨。


**TTS 2.0 预设音色可调的表达参数（2026-10-22 查官方文档实测，别再猜）**：

| 参数 | 位置 | 作用 | 2.0 预设音色实测结论 |
|---|---|---|---|
| `speech_rate` | `audio_params` | 语速 [-50,100]，100=2.0 倍 | 可用，但**只加快说话**，停顿时长基本不变 |
| `context_texts` | `additions` | 自然语言语音指令（情绪/语气/语速/停顿感），仅第一个值生效、不计费 | **最有效**：重指令可让 116 字从 21.72 s 缩到 19.85 s（5.34→5.84 字/s），中位基频 182→198 Hz |
| `post_process.pitch` | `additions` | 音调 [-12,12] | 可用，+2 约 +2 半音（中位基频 186→203 Hz） |
| `loudness_rate` | `audio_params` | 音量 [-50,100] | 可用 |
| `emotion` / `emotion_scale` | `audio_params` | 固定情绪枚举 + 强度 1–5 | **接口接受、但该音色无实际效果**：fearful/4 与无情绪版同为 182 Hz、时长 22.51 vs 21.72 s。文档也写明"仅部分音色支持" |
| `silence_duration` | `additions` | 只在**文本末尾**补静音 | 可用但对句间无用 |
| `mute_cut_threshold` / `mute_cut_remain_ms` | `additions` | 服务端裁静音 | **明确不支持 2.0 音色** |
| `use_tag_parser`（cot 标签） | `additions` | 逐句情感标签 | 仅限声音复刻 2.0 表现力增强版，预设音色不可用 |

结论：想同时要"更自然 + 少停顿 + 更急"，只能 **`context_texts` 定情绪 + `speech_rate` 定速度 + `compress_pauses.py` 压停顿**，三者叠加；`emotion` 这条路径对 2.0 预设音色不要指望。
- 变体横评脚本：`scripts/audio/audition_variants.py`（用子类给上游请求体补 `context_texts`/`post_process`/`emotion`，不改 upstream）。spec 是 JSON 数组，每项 `{key, speech_rate, loudness_rate, pitch, emotion, emotion_scale, context_texts}`。
- 客观评估"急不急"：算中位基频与基频 IQR（升高 + 起伏变大 = 更激动），比只听一遍可靠；停顿用最长静音 + ≥0.4 s 段数。
- 踩坑：试听目录必须传 `allow_overwrite=True`，否则失败残留的 `.mp3.json` / `.lock` 会把后续重跑全挡在 artifact_lock；失败回执（`{"success": false, ...}`）也要先清掉。
- 踩坑：`emotion` 探测那次全部变体因 `SSLError(... UNEXPECTED_EOF_WHILE_READING)` 失败——这是本机到 openspeech 的临时网络故障，**不是参数被拒**。脚本已加网络层重试（只在 SSL/连接类错误时重试，参数错误不重试，避免隐性重复计费）。

**音色试听流程（2026-10-22 起）**：用户对已批准音色不满意、要求在火山 2.0 音色表里重选时，用 `scripts/audio/audition_voices.py`（`FEMALE_ADULT` 已登记成熟女声候选及官方出处 https://www.volcengine.com/docs/6561/1257544）在同一段原稿开头文字上横评：每音色一次提交整段试听文本（不拆句、不拼接），输出到 `assets/audio/audition/<tag>/`。试听文本必须是原稿开头的**连续段落**，不改字、约 20 秒。选定音色并写入下方批准清单后，才可用 `generate_candidate.py` 做全文一次合成；试听样音不得当成品音轨。
- 踩坑：`DoubaoTTS` 返回的 `duration_seconds` **不是音频时长**（实测偏短 30% 以上），一律用 `ffprobe` 实测，回执写 `duration_source: ffprobe`。
- 2026-10-22 实测（116 字，语速 14）：温柔妈妈 22.85 s / 5.08 字/s / 最长停顿 0.64 s；知性女声 18.29 / 6.34 / 0.41；亲切女声 17.21 / 6.74 / 0.24；知性灿灿 19.30 / 6.01 / 0.59；暖阳女声 20.06 / 5.78 / 0.42。

**每音色语速（2026-10-21 定值，2026-10-22 更新）**：语速走 API `audio_params.speech_rate`，取值区间 **[-50, 100]**，100 = 2.0 倍速、0 = 1.0 倍速、-50 = 0.5 倍速（线性换算，倍速 = 1 + speech_rate/100）。默认值按音色分：**大壹 10（≈1.1 倍）、小何 2.0 10（≈1.1 倍）、温柔妈妈 2.0 19（≈1.19 倍，2026-10-22 用户定稿）**。温柔妈妈底速偏慢（同 1.14 倍时比大壹长 20%），19 是本工作流定值；控制台默认显示 0 只是接口缺省，不改变本工作流默认。实现见 `scripts/audio/generate_candidate.py` 的 `SPEECH_RATE` 与 `--speech-rate`（覆盖值必须写进回执；只在用户明确要求改语速时使用）。

**句间停顿**：API 没有句间静音参数。`additions.silence_duration` 只给**文本末尾**追加静音（0–30000 ms），管不到句与句之间；段末停顿只能靠语速与标点自然产生。所以「句子之间太长」先用语音指令 + 语速解决（温柔妈妈 2.0 用 19 + 重指令）；仍不够就按开头配方第 2 步用 `compress_pauses.py` 压：保留原轨、另存版本、记录参数并**精确平移时间轴**，不得静默删停顿，也不得用变速修补代替。

**停顿到底长在哪（2026-10-21 特级教师片实测，三版对照，别再凭感觉调语速）**：
- `speech_rate` 只加快**说话**，不缩短**内部停顿**。实测 10→14 倍速，时长 165.264→160.608 s（-2.8%），但 ≥0.3 s 静音总时长 23.66→26.55 s 反而变多，静音占比 14.3%→17.0%。指望调语速解决「停顿长」是无效的。
- **真正的句间空隙很短**：provider 的 41 个句间空隙平均 **0.115 s**，最长 0.35 s。用户听到的「句与句之间太长」，实际是**句子内部、标点驱动的停顿**：`：“` 引语前 0.55–0.96 s（7 处，是全片空感最强的部分），`，` 后 0.4–0.7 s。
- 段间换行不是主因：加 `--join-lines` 去掉段间换行后，时长 160.608→160.512 s、最长停顿 0.91→0.96 s，基本无变化（但它顺带修好了 v01 的头部时间戳截断：42 句、从 0 s 起，不用再补头部）。
- 处置结论：**停顿只能在母带上做静音压缩**，见下条。

**静音压缩（`scripts/audio/compress_pauses.py`，母带后处理，不重新合成）**：把每个「字间空隙」压到 `--cap` 秒以内，删掉的是纯静音中段，**语音采样一帧不动**，不重采样、不改播放速率、不拼接不同次合成。因为删除量是确定值，词级时间戳按累计删除时长**精确平移**，不需要重新 ASR，也就没有 ASR 认错字的风险。
- 切点用滑动窗口找该空隙里最安静的 `d` 秒，`d` 不够安静（中间有吸气）时逐级退让而不是硬切；实在找不到安静窗口就跳过并记录下来，不硬删。
- 出厂校验：压缩前后「正文字符序列」逐字一致（只允许「阿拉伯数字 ↔ 汉字数字」等价差异）、任一残余空隙 ≤ cap+0.02、爆音检查（采样跳变数不增）。
- 实测（cap 0.45）：160.512→**151.793 s**，删 8.719 s / 38 处，≥0.3 s 静音 27.28→18.79 s（17.0%→12.4%），最长停顿 0.96→0.50 s，字速 5.48→5.80 字/s；保留 5 处切口有气口的空隙（0.47–0.50 s）。
- 用法：`compress_pauses.py --project . --wav <母带> --json <时间戳 json> --text brief/narration.txt --cap 0.45 --tag v04`，输出 `-v04.wav/.wav.json/.mp3`；之后把 `design/config.json` 的 `volc_json`/`voice_wav`/`voice_mp3` 指过去，再跑 `check_voice.py`。原始母带一律保留，不覆盖。

**声音决定主角性别（学生第一人称稿）：**配音就是主角本人。男声（大壹）→ 主角画成男学生；女声（小何 2.0）→ 主角画成女学生（温柔妈妈 2.0 只用于家长角度，叙述者是家长，不适用本条）；稿子判断不了性别时按音色规则默认小何，主角就画女生。生图前把 `voice`（dayi/xiaohe）、`narrator_is_protagonist`（学生第一人称为 true）、`protagonist_cast`（主角在 cast.json 的 key）写进 `design/config.json`，cast.json 主角 `gender` 写 male/female 且与声音一致；`gen_sprites.py` 与 `make_manifest.py` 会检查，不一致拒绝运行。第三人称、家长（含鸡汤女 2.0 的家长角度稿）、陪伴师口吻不受此限，主角性别按稿子。逐图验收要核对图里主角性别与声音一致。

凭证只存**视频工作区** `.private/volcengine.env`，格式见 template/volcengine.env.example；不复制整份其他项目 .env、不存进 Skill，不进 Git/打包/截图/日志。配置检查只报状态，不输出值；固定音色由用户指定，未查账户目录时不得虚称目录验证通过。

## 一份正文，一次提交

1. 标题与正文逐字锁定，标题不朗读；正文不改写、不加 SSML、不注入静音。全文原样 submit 一次，得到连续完整试听；不先做短样音，不拆句/分段/拼接。用户提出制作视频或试听，即授权本稿一次合成，不另设外发审批。
2. 同一全文哈希与音色/参数完全一致时可复用已有候选，说明来源。异步只轮询原 task ID；查询或下载的网络重试不算新合成，但绝不能重新 submit。失败、超时、结果不确定或运行环境拒绝调用时，保留回执并停止；不自动创建新付费任务或换供应商。
3. 用户试听前运行 check_voice.py：逐句查语速突变、局部压缩、整句偏小、独立 ASR 对照原稿。红色项必须人耳复核；误报写明依据，确有问题须经用户同意后重新全文合成一次，不用拼接、变速或静音修补。
4. 向用户展示一份完整音轨，说明供应商、音色、语速、时长和实际检查范围，等待用户锁定声音：发完试听消息即结束本轮回复，不继续后续步骤；用户明确说通过后运行 `lock_voice.py --audio <mp3> --user-says "<原话>"`，生图脚本凭 `qc/voice-lock.json` 放行。不得把默认参数或沉默当作批准。试听提示必须逐条列出 `qc/voice-check.md` 中全部红/黄项的时间点、对应原句和问题类型；同时列出独立 ASR 标记的可疑字词及所在时间段，明确它只是机器提示，需人耳确认。不能只概括“有几处偏快/音量偏低”，也不能把词级时间戳与稿件对齐说成实际读音已核实。独立转录与专名/语气试听不能由哈希或供应商时间戳代替。
5. 声音锁定后建立真实时间轴，字幕、分镜和动作按词级时间戳对齐。只转换为 44.1kHz 单声道 PCM WAV 母带，不删停顿、不变速。用户另有明确处理要求时保留原轨、另存版本、记录参数并重算时间轴。

## 执行与证据

- 入口：`python <skill>/scripts/audio/generate_candidate.py --project <项目>`；`--preflight` 只核配置、不联网、不计费。已有同稿同参候选复用；已有失败回执时禁止自动重提。额外合成、换声或新版付费任务必须有用户明确指令。
- 输出 assets/audio/narration-volcengine-<dayi|xiaohe|wenroumama>-full-vNN.mp3、相邻回执和 WAV 母带；温柔妈妈还要再做一步 compress_pauses（见开头配方），产出 vNN 后缀的压缩版并让 config.json 指向它；config.json 绑定音频与词级时间戳，Clock 检查正文一致。拒绝的候选保留并标 rejected，不进入成片；批准记 approved。
- 元数据保留正文/音频 SHA-256、接口/音色/参数、task ID、时间戳、时长/解码、复用状态和人工确认。签名下载 URL 仅内存使用，不能进交付回执。
- 交付前再跑 check_voice.py，完成解码、时长、全文与逐句独立转录、人耳及音画核验；只做电平或 --no-asr 检查不能称内容验收通过。结果与复核记录放 qc/，接续以本项目 BRIEF/STATUS 为准，不从别片推断已批准声音。

## G端宣传片默认声音（2026-10-22用户定稿）

G端学校、教育局、企业等机构官网宣传片，content_type=institutional_promo，默认儒雅逸辰2.0，voice=yichen，voice_type=zh_male_ruyayichen_uranus_bigtts，seed-tts-2.0，speech_rate=0。正式播音指令与执行方法统一见Skill references/INSTITUTIONAL_PROMO.md。用户已从真实短试听选定音色；新全文仍按一次提交、独立核验与试听锁定。其他内容原有声音规则不变。明确要求先看静态图可记录授权后出静态预览，不冒充全文音轨已锁定。
