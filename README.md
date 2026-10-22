# Inside the Moment — 工作流原型

从合成足球事件生成球员第一视角的场景规划、视频生成请求和解说。
Python 本地框架负责合成事件、场景规划和展示；场边洞察现支持
OpenRouter AI 解读，未配置时使用规则基线。视频与语音仍待接入。
场景规划和右侧视频解说仍使用确定性模板。

```text
合成事件 → 读取与检查 → 场景规划 ┬→ 视频提示词 ─┐
                              └→ 解说文本 ───┤
                                      一致性检查
                                           ↓
                                 视频供应商接口（dry-run）
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
| `video_job.json` | 视频任务状态；目前为 `not_submitted` |
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
比赛片段是局部合成样例，具体数据约定见 `data/synthetic/README.md`。

## 本地观赛界面

```powershell
python -m workflow.server
```

打开 http://127.0.0.1:8000 ，使用 Ctrl+C 停止。
Python 标准库服务仅监听本机，面向开发预览，不用于生产部署。

基础版包含片段播放/暂停/重置/倍速、比分、事件位置示意、样例统计、
关键事件时间轴、简短事件解释、轻松/数据模式、球迷立场及自动片段回顾。
第一视角面板可选择射手/门将、中英文解说，并真实调用已有准备工作流。
阵容现为双方各 11 人。“关注球员”已移除，所有观众都能看到完整片段列表。
主队/客队球迷优先进入支持球队的球员视角，在片段结束后自动准备请求；
中立观众手动选择射手或门将视角。解说根据进攻/防守一方与事件结果调整语气。
切换立场或语言会清除旧结果并重新准备，重置不会触发自动准备。
所有统计只计入已播放的样例事件；不提供全场控球率、xG 等无依据指标。

### API 交接

- `GET /api/match`：返回 `match`、`events`、`clips`。
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
- 当前 prepare 是同步 dry-run。接真实视频服务时应新增独立提交/轮询接口，
  包括 `queued / running / succeeded / failed` 状态与视频 URL；
  前端已经支持 `video_job.json` 返回 `status: succeeded` 和 `media_url` 时展示播放器，
  有立场的自动请求会尝试播放；浏览器禁止自动播放时提示手动点击。
  当前没有视频资源，不能验证真实成片播放；尚未实现异步任务轮询。
- API Key 放在后端环境变量中，不写进浏览器代码或提交到 Git。

功能范围参考了 [Virtual Studio Crew](https://github.com/timmytrace/pl-insights-engine)
的公开项目说明；本实现没有复制其代码或素材。重点保留第一视角体验，
不实现多 Agent 导播、复杂战术指标或多语言解说系统。

球场现支持 22 人移动关键帧和足球插值动画，当前动作参与者高亮、其他球员调暗。
每次只播放一个片段，结束自动暂停。数据生成说明见
`data/synthetic/README.md` 的“22 人移动样例”。

### 场边洞察（Interpret / Explain）

动画每前进一步，球场下方会更新该动作的意义：传球的向前推进、接球后的
进攻选择、带球缩短的射门距离、射门位置与防守距离，以及进球/扑救对比分的影响。
主队与客队球迷有不同的关注点和情绪，中立观众使用客观表达；
轻松模式突出意义，数据模式补充计算指标。“查看分析依据”展开数值与事件链。

- `POST /api/insights`：`{"event_id":"事件 ID","audience":"home","mode":"casual"}`。
- 只传入当前事件及此前证据，不包含后续事件或尚未发生的射门结果。
- `workflow/insights.py` 计算 `facts`，返回 `title/text/evidence/render/ai_request`。
- `ai_request` 是可交给语言模型的事实、观众立场及写作指令。
  partner 实现 `InsightWriter.generate(request)`，在服务端设置 `INSIGHT_WRITER` 即可接入。
  模型应返回 `{"title":"...","text":"...","evidence_event_ids":["当前事件 ID"]}`。
- 未配置模型时，页面明确显示“规则解读 · AI 接口待接入”。这是中文文字解读，
  尚未接语音；右侧视频解说的语言选择不改变这里的语言。
- 配置模型后会检查输出长度及事件引用；失败时回退规则解读。
  引用检查不代表已验证模型的全部语义事实，后续接 API 时仍需评估。
- 前端丢弃过期请求，缓存同一事件/立场/模式的结果；下一事件立即替换当前洞察。

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
