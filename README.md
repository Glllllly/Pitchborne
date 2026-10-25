# Inside the Moment — 工作流原型

Python 依赖：`pip install -r requirements.txt`。

### 生成 90 分钟合成比赛

页面默认加载 seed 7 的完整比赛。需要换比赛时，重启服务并指定种子：

```powershell
python -m workflow.server --seed 42
```

也可以用 `python -m scripts.generate_match --seed 42` 单独生成数据文件。
同一个 seed 始终生成相同的虚构比赛；文件写入忽略提交的 `data/matches/seed-<seed>/`。
其中 `commentary.json` 保存中立、主队和客队三套逐事件文字解说，可供后续配音。
事件覆盖 0–90 分钟，包括成功和失败传球、接球、带球、拦截、施压、抢断、
射门、扑救及全场结束。双方各 11 人；每个事件带 22 人的示意起终关键帧。
比分只由进球事件累计，页面和洞察都从已发生事件计算。仅射正的进球和被扑救
射门会生成第一视角视频任务；射偏仍保留在比赛动画、解说与数据统计中。
这是演示用受约束随机模拟：位置在每次事件内插值，并非连续追踪；没有越位、
犯规、换人、体力或真实联赛统计分布的完整模型。全场普通事件只用规则解读，
仅射门事件会请求 AI 场边解读，避免快进时发出数百次模型调用。

从合成足球事件生成球员第一视角的场景规划、视频生成请求和解说。
Python 本地框架负责合成事件、场景规划和展示；场边洞察现支持
OpenRouter AI 解读与视频生成，未配置时使用规则基线和视频 dry-run。语音仍待接入。
场景规划和右侧视频解说仍使用确定性模板。

```text
合成事件 → 读取与检查 → 场景规划 ┬→ 视频提示词 ─┐
                              └→ 解说文本 ───┤
                                      一致性检查
                                           ↓
                                 OpenRouter 视频任务（无 Key 时 dry-run）
                                           ↓
                                      本地结果文件
```

## 运行

在仓库根目录使用 Python 3.10+：

```powershell
python scripts/generate_synthetic.py
python -m workflow.pipeline --clip saved --pov striker --language zh
python -m workflow.pipeline --clip saved --pov goalkeeper --language en
```

支持片段：`goal`、`off_target`、`saved`。
支持视角：`striker`、`goalkeeper`。支持语言：`zh`、`en`。
使用 `--output 路径` 指定输出位置；默认在 `outputs/<片段>-<视角>-<语言>/`。
相同配置再次运行会覆盖该目录中的工作流结果文件。

## 产物

| 文件 | 内容 |
| --- | --- |
| `scene.json` | 事实、视角球员、位置快照、分段动作、创作边界 |
| `video_request.json` | 英文视频提示词、负向提示词、时长及事件引用 |
| `commentary.json` | 中文或英文解说文本；语音尚未生成 |
| `validation.json` | 结构化结果、证据引用与视角一致性检查 |
| `video_job.json` | 视频任务状态：`queued`、`running`、`succeeded`、`failed`；无 Key 时为 `not_submitted` |
| `run.json` | 本次运行参数及阶段 |

## 后续接入点

`workflow/pipeline.py` 中各阶段独立为函数：

- `plan_scene`：未来可接 LLM，但应保留事实字段与输入证据引用。
- `compile_video_request`：替换或优化供应商专用提示词模板。
- `generate_commentary`：接入基于事实的 AI 解说，再对接 TTS。
- `VideoProvider.submit`：接入选定的视频服务，返回任务状态及资源引用。
  真正服务还需补充任务轮询、超时、重试与幂等控制。
- `validate_outputs`：当前只检查结构化元数据，未来扩展文本语义、
  视频结果、视角、空间及音画同步检查。

单次工作流按顺序执行，尚无后台生成队列。
本地结果的 `prepared` 仅表示请求准备完成，不代表模型生成成功。
命令行工作流的默认片段是局部合成样例，具体数据约定见 `data/synthetic/README.md`。

## 本地观赛界面

```powershell
python -m workflow.server
```

打开 http://127.0.0.1:8000 ，使用 Ctrl+C 停止。
Python 标准库服务仅监听本机，面向开发预览，不用于生产部署。

观赛界面默认加载 seed 7 并自动开球。正常比赛按动作类型分配屏幕时长，
seed 7 约 12 分钟；第一视角视频的等待和播放时间另计。支持暂停/重播/倍速、
比分、事件位置示意、已发生事件统计、关键事件时间轴及自动片段回顾。
服务端从整场事件预生成中英双语、各含中立/主队/客队三套同步文字解说，切换语言或球迷立场即时换稿。
普通事件采用轮换句式，并结合接球者、球场位置、本次球权和截至当前的近五分钟节奏改写；
同一扑救只播报一次。规则解说先随事件即时出现，中文射门解说可在 AI 洞察返回后原位更新，
生成失败时保留规则文案，不耽误比赛播放。所有上下文均取自已发生事件。
开球时另有双方 4-3-3 首发介绍；每约十个比赛分钟插入一次阶段回顾，按该时段的射门、射正、进球和施压事件写局势，
终场附全场回顾。回顾与逐事件解说使用同一时间轴，支持中英双语和三种球迷立场。
第一视角面板可选择射手/门将、中英文解说，并真实调用已有准备工作流。
阵容现为双方各 11 人，位置按球员职责组成随球移动的合成 4-3-3 事件快照；
主队向右、客队向左进攻。“关注球员”已移除，所有观众都能看到完整片段列表。
浏览器会在连续事件的关键帧之间使用缓入缓出插值，球员和足球共用进场与动作阶段；
传球及射门的足球先到位，接应与跟进动作随后收束。跨越较大的无追踪空白时，足球直接进入下一事件位置。
这仍是合成动画，不代表真实光学追踪。
主队/客队球迷优先进入支持球队的球员视角；中立观众可预先选择射手或门将视角。
开球后先预热最近两次射正，比赛推进时再逐步提交其余射正的视频任务；
同时最多处理两个视频任务，并持续查询进度。
highlight 发生时，若成片已经就绪则暂停比赛并播放，播完自动继续；
若仍在生成，动画与文字解说继续按比赛时间推进，完成后显示观看入口，由观众决定何时暂停观看。片段播放完毕后，该片段的观看按钮隐藏。
浏览器拒绝自动播放时可手动点视频，或点击「跳过视频，继续比赛」。
无 Key、生成失败或播放失败时会自动继续。下方比赛数据看板显示双方首发阵容、
进球、射门、射正、关键传球、成功传球、传球成功率、平均传球/射门球速及 xG 合成估算；统计只计入已播放的事件。
xG 用射门位置、角度与受压状态的启发式公式计算，未经真实数据校准，不能当作真实比赛 xG。
每次传球和射门的 `kinematics` 包含球路距离、独立于动画的合成飞行时长与球速；
传球另含依据距离、向前推进及接球点附近防守者计算的 0–100 难度分级。
分析模式的解说卡展示这些数值，洞察接口也返回相同事实。它们是可复现的模拟指标，并非摄像机测速。
全场控球率等尚无可靠事件依据的指标暂不展示。

可用 `pip install -r requirements-video.txt` 后运行 `python -m scripts.auto_event_demo`。
脚本先渲染一段没有事件文字标签的合成画面，再由 OpenCV 读取视频像素，
根据白色足球轨迹自动识别传球/射门并估算球速；`--source <视频路径>` 可读取同格式视频。
这是针对本项目合成画面的自动事件识别基线，尚不能识别真实转播视频中的球员或遮挡球。

### API 交接

- `GET /api/match`：返回 `match`、`events`、`clips`，以及中文 `commentary` 和英文 `commentary_en`，每种语言均含三种立场。
- `POST /api/highlights/prepare`：
  `{"clip_id":"saved","pov":"striker","language":"zh","audience":"home"}`。
  返回 `job_id` 和 `artifacts`；每次结果保存在 `outputs/<job_id>/`。
- partner 可实现 `VideoProvider.submit(request)`，在服务调用 `run` 时注入。
  `request` 提供 `prompt`、`negative_prompt`、`duration_seconds`、
  `pov`、`outcome`、`source_event_ids`，供应商不支持的参数应在适配器中转换。
- `audience` 接受 `neutral`（默认）、`home`、`away`。
  有球队偏好时，后端按射门球队归属决定 `pov`，不直接相信前端传入的视角。
  `scene.viewer`、`video_request.viewer` 提供 `audience`、`pov`、`emotion`、`autoplay`；
  `commentary.json` 提供相应语气的解说文本与情绪标签，可供后续 TTS 使用。
- 配置 `OPENROUTER_API_KEY` 后，prepare 会提交 OpenRouter 视频任务，前端轮询
  `GET /api/highlights/<job_id>`，并在生成完成后播放；浏览器禁止自动播放时可手动点击。
  后端把成片下载至
  `outputs/<job_id>/video.mp4`，通过本地 `/api/highlights/<job_id>/video` 播放。
  可用 `OPENROUTER_VIDEO_MODEL` 更换模型；无 Key 时仍为 dry-run。
- API Key 放在后端环境变量中，不写进浏览器代码或提交到 Git。

功能范围参考了 [Virtual Studio Crew](https://github.com/timmytrace/pl-insights-engine)
的公开项目说明；本实现没有复制其代码或素材。重点保留第一视角体验，
不实现多 Agent 导播或复杂战术指标；双语直播文案采用事件规则模板，片段解说另由工作流生成。

球场现支持 22 人移动关键帧和足球插值动画，当前动作参与者高亮、其他球员调暗。
关键片段发生时暂停正常比赛，视频结束后续播。数据生成说明见
`data/synthetic/README.md` 的“22 人移动样例”。

### 场边洞察（Interpret / Explain）

直播解说栏会在射门、拦截、抢断和施压时更新“为什么重要”的场边洞察，
同时保留事件时间戳。洞察分为直播解说与局面判断：后者给出动作意义、
截至当前的近五分钟射门/施压节奏、下一步观察点和分析边界。
传球推进距离、射门位置与防守距离等解释依据由接口提供。
主队与客队球迷有不同的关注点和情绪，中立观众使用客观表达；
轻松模式突出意义，数据模式补充计算指标。“查看分析依据”展开数值与事件链。

- `POST /api/insights`：`{"event_id":"事件 ID","audience":"home","mode":"casual"}`。
- 只传入当前事件及此前证据，不包含后续事件或尚未发生的射门结果。
- `workflow/insights.py` 计算 `facts`，并由 `workflow/match_context.py` 生成只看已发生事件的
  `context` 与 `analysis`，返回 `title/text/evidence/render/ai_request`。
- `ai_request` 是可交给语言模型的事实、观众立场及写作指令。
  partner 实现 `InsightWriter.generate(request)`，在服务端设置 `INSIGHT_WRITER` 即可接入。
  模型应返回 `{"title":"...","text":"...","evidence_event_ids":["当前事件 ID"]}`。
- 未配置模型时，页面使用规则解读；英文洞察由同一事实字段生成简短解释。
  尚未接语音，模型生成的中文洞察不会被当作英文翻译显示。
- 配置模型后会检查输出长度及事件引用；失败时回退规则解读。
  引用检查不代表已验证模型的全部语义事实，后续接 API 时仍需评估。
- 前端缓存同一事件/立场/模式的结果；一般传递不会刷掉最近一次关键洞察。

检查：`python -m unittest discover -s tests -v`。

### 接入 OpenRouter 场边洞察

使用官方 `@openrouter/sdk`（锁定版本见 `package-lock.json`），默认模型：
`deepseek/deepseek-v4.1-flash-1017`。需要 Node.js 22+。

```powershell
npm ci
Copy-Item .env.example .env
# 在本机编辑 .env，填入 OPENROUTER_API_KEY；已有环境变量时无需创建 .env。
npm run check:openrouter
python -m workflow.server
```

已有 `.env` 时直接编辑，不要覆盖。环境变量优先于 `.env`。
`check:openrouter` 只显示是否配置、模型及超时，不输出密钥，也不发付费请求。
可用 `OPENROUTER_MODEL` 更换模型，`OPENROUTER_TIMEOUT_MS` 设置超时（默认 45000）。
修改配置后重启 Python 服务。

调用链：浏览器 → Python `InsightWriter` → Node SDK → OpenRouter。
API Key 仅在后端读取，既不写入前端，也不通过命令行参数传递。
SDK 使用 `stream: true`，收集 `delta.content` 和末尾的 usage，
其中 reasoning token 数写入响应的 `generation.usage.reasoning_tokens`。
不存储或展示模型的推理正文。流结束后解析 JSON、检查长度及引用，再更新洞察卡；
浏览器收到的是检查后的完整文字，不是逐 token 流。

页面先显示规则洞察，再请求 AI 更新。超时、服务错误、截断或错误引用会保留规则结果。
过期浏览器请求会取消，后端检测断开后终止 SDK 子进程；实际计费取消由上游处理。
最多同时执行两条模型请求，成功输出有内存缓存。进程重启后缓存清空。

`POST /api/insights` 增加 `use_ai`（默认 `true`）；`false` 仅返回规则基线。
响应的 `ai_available` 表示已配置，不代表该次请求一定成功。
`generation` 包含供应商、模型与 token usage；错误日志仅记录经过清理的错误码/状态。

离线验证：`npm test`（模拟 SDK SSE 响应，不消耗 API 额度）和
`python -m unittest discover -s tests -v`。
