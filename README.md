# Pitchborne

**Feel the match from the pitch.** Pitchborne turns a synthetic 90-minute football match into a live animated broadcast. It combines event-driven commentary, explainable match insights, and AI-generated player-POV replays of shots on target.

The pitch and text start as soon as the match loads. Video jobs run in the background, so a slow generation request does not hold up the live experience.

## What you can see

- An animated 11-v-11 match with moving players, a ball, score, clock, and starting lineups.
- A live commentary feed with kick-off introductions, event calls, periodic match summaries, and a full-time recap.
- Neutral, home-fan, and away-fan perspectives, plus casual and analyst viewing modes.
- Commentary in English, Chinese, Spanish, and French. The interface itself is in English.
- A live data board with shots, shots on target, estimated xG and possession, passing, and other standard match statistics.
- First-person striker or goalkeeper video for **shots on target** (goals and saves), generated through OpenRouter when configured.

## Run locally

Requires **Python 3.10+** and **Node.js 22+**. Run these commands from the repository root:

```powershell
python -m pip install -r requirements.txt
npm ci
python -m workflow.server
```

Open <http://127.0.0.1:8000>. The default match uses seed `7` and starts automatically. Python serves the local preview on `127.0.0.1:8000`; stop it with `Ctrl+C`.

The match animation, statistics, and rule-based commentary work without an API key. To enable OpenRouter insights and video generation, copy `.env.example` to `.env` and add your own key:

```powershell
Copy-Item .env.example .env
```

Set `OPENROUTER_API_KEY` in `.env`. The example file also contains the text model (`deepseek/deepseek-v4.1-flash-1017`), video model (`bytedance/seedance-2.0-mini`), and text timeout. Keep `.env` private; it is git-ignored. Video generation makes paid provider requests and may take longer than the match event that triggered it.

To replay a different deterministic match, restart the server with a different seed:

```powershell
python -m workflow.server --seed 42
```

To generate only the data files:

```powershell
python -m scripts.generate_match --seed 42
```

Generated files live under `data/matches/seed-<seed>/` and include `match.json`, `events.json`, `clips.json`, and language-specific commentary tracks. They are ignored by git and rebuilt when needed.

## How it works

| Stage | Pitchborne implementation |
| --- | --- |
| Ingest | Generate and stream deterministic synthetic events: passes, carries, pressure, tackles, possession changes, shots, saves, and match metadata. |
| Interpret | Update the score, possession and passing estimates, shot counts, xG estimate, and recent patterns using only events that have occurred. |
| Explain | Turn events and short-term trends into commentary and evidence-backed insights about pressure, chances, and match rhythm. |
| Render | Synchronize the pitch animation, live text feed, insight cards, and data board with the match clock. |
| Personalize | Adapt commentary and POV choice to the viewer's team allegiance; offer casual and analyst modes and four commentary languages. |

The server prepares the full synthetic event stream and localized commentary at launch. The browser then plays it on a compressed timeline. The video queue prepares up to two upcoming shots on target at a time. A ready clip pauses the pitch, plays inline, and then resumes the match. If a clip is still generating when the shot happens, the match continues and a watch button appears when the clip is ready.

The implementation is split across `scripts/generate_match.py` (match data), `workflow/match_commentary.py` and `workflow/broadcast_beats.py` (commentary), `workflow/insights.py` (interpretation), `workflow/openrouter_video.py` (video provider), `workflow/server.py` (local API), and `web/` (broadcast UI). The local API exposes `GET /api/match`, `POST /api/insights`, `POST /api/highlights/prepare`, and highlight job status/video endpoints.

## Data and scope

All teams, players, and match events are fictional. The event structure is inspired by [StatsBomb Open Data](https://github.com/hudl/open-data), but this is a smaller custom schema, not a drop-in StatsBomb export. [pl-insights-engine](https://github.com/timmytrace/pl-insights-engine) was a reference for the type of football context worth showing; Pitchborne uses its own generated data and implementation.

Player positions are synthetic event keyframes interpolated for display, not optical tracking. Possession, xG, ball speed, and shot speed are simulator estimates rather than measured match statistics. Events the simulator does not model, such as offsides and disciplinary cards, display zero. The optional auto-event demo detects the ball in this project's rendered synthetic footage; it does not identify players or events in real broadcast video. Text commentary is displayed on screen; spoken commentary and text-to-speech are not implemented.

## Verify

```powershell
npm test
python -m unittest discover -s tests -p 'test_*.py'
```

For the optional synthetic-video event detection demo, install `requirements-video.txt` and run `python -m scripts.auto_event_demo`.
