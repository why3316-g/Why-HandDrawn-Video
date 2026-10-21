# 全文火山配音规范

## 配音通道（auto / 固定）

`generate_candidate.py --provider auto|volcengine|edge`：优先级为命令行 > 环境变量 `HDV_TTS_PROVIDER` > 工作区 `.hdv-workspace.json` 的 `tts_provider` > auto。auto = 工作区配了真实火山密钥用火山，否则用免费微软语音（edge-tts，非官方接口，效果与稳定性不如火山，须 edge-tts ≥7.3.1）。**固定为 volcengine 时缺密钥直接报错，绝不静默降级到微软**；已有同稿候选换通道/音色等于新增一次合成，按下文规则需用户明确指令（`--confirm-voice-change`）。个人生产环境应在工作区固定 `volcengine`；下文“只用火山”指固定火山时的规则，微软通道沿用同一套全文一次、锁定、验收流程，输出文件名为 `narration-edge-<dayi|xiaohe>-full-vNN.mp3`（音色对应 zh-CN-YunxiNeural / zh-CN-XiaoxiaoNeural，语速 +10%）。

## 固定通道与配置

只用火山 Doubao Speech 2.0：批准音色两个——大壹 `zh_male_dayi_uranus_bigtts`（默认）、小何 2.0 `zh_female_xiaohe_uranus_bigtts`（女学生或性别不明的学生第一人称）。音色选择（只批准两个）：默认用**大壹** `zh_male_dayi_uranus_bigtts`；口播稿是**学生以第一人称讲述自己的故事**时按性别选：男学生用大壹，女学生用**小何 2.0** `zh_female_xiaohe_uranus_bigtts`（火山豆包语音合成模型 2.0 通用场景女声）。依据是稿子本身：叙述者“我”是学生才算；性别无法从稿子判断时默认小何 2.0，不停下来问用户（理由照常写进试听消息与 BRIEF）；家长、陪伴师、第三人称叙述等其他口吻用大壹。选定的音色和理由写进试听消息与 BRIEF；脚本用 `generate_candidate.py --voice dayi|xiaohe`，其余参数（seed-tts-2.0、语速 1.1、全文一次）不变。同一全文已用一个音色合成后，改用另一个音色等于新增一次付费合成，须用户明确指令，脚本要加 `--confirm-voice-change`。 资源 `seed-tts-2.0`，语速 1.1（speech_rate=10），默认音量，MP3 24kHz，请求词级时间戳。接口为 openspeech.bytedance.com/api/v3/tts/submit 与 query，X-Api-Key 鉴权。实现及公开参数在本包 upstream/openmontage-audio/；来源记录在 upstream/SOURCES.json。

**声音决定主角性别（学生第一人称稿）：**配音就是主角本人。男声（大壹）→ 主角画成男学生；女声（小何 2.0）→ 主角画成女学生；稿子判断不了性别时按音色规则默认小何，主角就画女生。生图前把 `voice`（dayi/xiaohe）、`narrator_is_protagonist`（学生第一人称为 true）、`protagonist_cast`（主角在 cast.json 的 key）写进 `design/config.json`，cast.json 主角 `gender` 写 male/female 且与声音一致；`gen_sprites.py` 与 `make_manifest.py` 会检查，不一致拒绝运行。第三人称、家长、陪伴师口吻不受此限，主角性别按稿子。逐图验收要核对图里主角性别与声音一致。

凭证只存**视频工作区** `.private/volcengine.env`，格式见 template/volcengine.env.example；不复制整份其他项目 .env、不存进 Skill，不进 Git/打包/截图/日志。配置检查只报状态，不输出值；固定音色由用户指定，未查账户目录时不得虚称目录验证通过。

## 一份正文，一次提交

1. 标题与正文逐字锁定，标题不朗读；正文不改写、不加 SSML、不注入静音。全文原样 submit 一次，得到连续完整试听；不先做短样音，不拆句/分段/拼接。用户提出制作视频或试听，即授权本稿一次合成，不另设外发审批。
2. 同一全文哈希与音色/参数完全一致时可复用已有候选，说明来源。异步只轮询原 task ID；查询或下载的网络重试不算新合成，但绝不能重新 submit。失败、超时、结果不确定或运行环境拒绝调用时，保留回执并停止；不自动创建新付费任务或换供应商。
3. 用户试听前运行 check_voice.py：逐句查语速突变、局部压缩、整句偏小、独立 ASR 对照原稿。红色项必须人耳复核；误报写明依据，确有问题须经用户同意后重新全文合成一次，不用拼接、变速或静音修补。
4. 向用户展示一份完整音轨，说明供应商、音色、语速、时长和实际检查范围，等待用户锁定声音；不得把默认参数当作批准。试听提示必须逐条列出 `qc/voice-check.md` 中全部红/黄项的时间点、对应原句和问题类型；同时列出独立 ASR 标记的可疑字词及所在时间段，明确它只是机器提示，需人耳确认。不能只概括“有几处偏快/音量偏低”，也不能把词级时间戳与稿件对齐说成实际读音已核实。独立转录与专名/语气试听不能由哈希或供应商时间戳代替。
5. 声音锁定后建立真实时间轴，字幕、分镜和动作按词级时间戳对齐。只转换为 44.1kHz 单声道 PCM WAV 母带，不删停顿、不变速。用户另有明确处理要求时保留原轨、另存版本、记录参数并重算时间轴。

## 执行与证据

- 入口：`python <skill>/scripts/audio/generate_candidate.py --project <项目>`；`--preflight` 只核配置、不联网、不计费。已有同稿同参候选复用；已有失败回执时禁止自动重提。额外合成、换声或新版付费任务必须有用户明确指令。
- 输出 assets/audio/narration-volcengine-<dayi|xiaohe>-full-vNN.mp3、相邻回执和 WAV 母带；config.json 绑定音频与词级时间戳，Clock 检查正文一致。拒绝的候选保留并标 rejected，不进入成片；批准记 approved。
- 元数据保留正文/音频 SHA-256、接口/音色/参数、task ID、时间戳、时长/解码、复用状态和人工确认。签名下载 URL 仅内存使用，不能进交付回执。
- 交付前再跑 check_voice.py，完成解码、时长、全文与逐句独立转录、人耳及音画核验；只做电平或 --no-asr 检查不能称内容验收通过。结果与复核记录放 qc/，接续以本项目 BRIEF/STATUS 为准，不从别片推断已批准声音。
