"""Evidence-first live insights. Rule baseline plus a model-ready writing request."""

import math
from typing import Protocol


class InsightWriter(Protocol):
    """Implement with the chosen server-side model SDK; use a bounded timeout."""

    def generate(self, request: dict) -> dict: ...


def build_insight(match, events, event_id, audience="neutral", mode="casual", writer=None):
    if audience not in ("neutral", "home", "away") or mode not in ("casual", "analyst"):
        raise ValueError("Unsupported insight audience or mode")
    index = next((i for i, event in enumerate(events) if event["id"] == event_id), None)
    if index is None:
        raise ValueError("Unknown event")
    # Do not expose future events, final scores or the future shot outcome to writers.
    prefix = events[:index + 1]
    event = prefix[-1]
    chain = [item for item in prefix if item["possession"] == event["possession"]]
    home, away = match["home_team"]["id"], match["away_team"]["id"]
    supported = None if audience == "neutral" else match[f"{audience}_team"]["id"]
    attack_team = event["possession_team"]["id"]
    favor_attack = supported == attack_team
    coord = match["coordinate_system"]
    physical = match.get("tracking", {}).get("physical_pitch_metres", [105, 68])
    scale = [physical[0] / coord["length"], physical[1] / coord["width"]]

    def distance(a, b):
        return math.hypot((a[0]-b[0])*scale[0], (a[1]-b[1])*scale[1])

    facts = {
        "actor": event["player"]["name"],
        "event_type": event["type"]["name"],
        "minute": event["minute"],
        "synthetic": True,
    }
    score = {home: 0, away: 0}
    for item in prefix:
        if item.get("shot", {}).get("outcome", {}).get("name") == "Goal":
            score[item["team"]["id"]] += 1
    facts["score_after"] = [score[home], score[away]]
    kind = event["type"]["name"]
    # Templates carry interpretation grounded in a small explicit fact sheet.
    if kind == "Pass":
        target = event["pass"]["end_location"]
        progress = (target[0]-event["location"][0])*scale[0]
        facts.update(pass_distance_m=round(distance(event["location"], target), 1),
                     forward_progress_m=round(progress, 1),
                     recipient=event["pass"]["recipient"]["name"])
        title = "把进攻向前送"
        detail = f"这脚传球向球门方向推进约 {progress:.1f} 米，找到 {facts['recipient']}。"
        why = "它让接球者在更靠近球门的位置处理下一步进攻。"
        if progress <= 0:
            title, why = "重新组织进攻", "这脚传球没有直接向球门推进，球权交给队友重新组织。"
        home_voice, away_voice = "我们的推进接上了，看看接球后怎么处理。", "对手又向前推进了一步，我们需要留意接球者。"
    elif kind == "Ball Receipt*":
        prior_pass = next((item for item in reversed(chain[:-1]) if item.get("pass")), None)
        title = "传球变成接球机会"
        detail = f"{facts['actor']} 已经接到球。"
        why = "球权从传球者转到接球者，接下来的持球选择值得关注。"
        if prior_pass:
            facts["passer"] = prior_pass["player"]["name"]
            detail = f"{facts['passer']} 的传球找到了 {facts['actor']}。"
        home_voice, away_voice = "球到我们脚下了，下一步能否继续向前？", "对方已经接住传球，注意他的下一步动作。"
    elif kind == "Carry":
        target = event["carry"]["end_location"]
        goal = [coord["goal_line_x"], sum(coord["goal_mouth_y"])/2]
        facts.update(carry_distance_m=round(distance(event["location"], target), 1),
                     goal_distance_reduction_m=round(distance(event["location"], goal)-distance(target, goal), 1))
        title = "持球缩短与球门的距离"
        detail = f"{facts['actor']} 带球移动约 {facts['carry_distance_m']} 米，距球门中心缩短约 {facts['goal_distance_reduction_m']} 米。"
        why = "更近的位置提供了不同的处理空间，但能否射门还要看接下来的防守。"
        home_voice, away_voice = "我们又靠近球门了一点，期待这次处理。", "对手正靠近我们的球门，这一步推进需要警惕。"
    elif kind in ("Shot", "Goal Keeper"):
        shot = event if kind == "Shot" else next(item for item in reversed(chain) if item.get("shot"))
        goal = [coord["goal_line_x"], sum(coord["goal_mouth_y"])/2]
        opponents = [
            p for p in shot.get("tracking", {}).get("start", [])
            if p["team_id"] != shot["team"]["id"]
            and next(entry for entry in match["players"] if entry["player"]["id"] == p["player_id"])["role"] != "goalkeeper"
        ]
        if not opponents:
            opponents = [p for p in shot["shot"]["freeze_frame"] if not p["teammate"] and p["position"]["name"] != "Goalkeeper"]
        nearest = min((distance(p["location"], shot["location"]) for p in opponents), default=None)
        posts = [[coord["goal_line_x"], y] for y in coord["goal_mouth_y"]]
        vectors = [[(p[0]-shot["location"][0])*scale[0], (p[1]-shot["location"][1])*scale[1]] for p in posts]
        angle = math.degrees(math.atan2(abs(vectors[0][0]*vectors[1][1]-vectors[0][1]*vectors[1][0]),
                                       sum(a*b for a, b in zip(*vectors))))
        outcome = shot["shot"]["outcome"]["name"]
        facts.update(goal_distance_m=round(distance(shot["location"], goal), 1),
                     nearest_defender_m=round(nearest, 1) if nearest is not None else None,
                     goal_opening_angle_degrees=round(angle, 1),
                     under_pressure=shot.get("under_pressure", False), outcome=outcome)
        detail = f"这脚射门距球门中心约 {facts['goal_distance_m']} 米"
        if nearest is not None:
            detail += f"，最近防守球员约 {nearest:.1f} 米"
        detail += "。"
        if outcome == "Goal":
            before = dict(score)
            before[shot["team"]["id"]] -= 1
            other = away if shot["team"]["id"] == home else home
            facts["score_before"] = [before[home], before[away]]
            facts["scoring_team_goal_margin"] = score[shot["team"]["id"]] - score[other]
            leads = score[shot["team"]["id"]] > score[other] and before[shot["team"]["id"]] <= before[other]
            title = "在防守附近完成破门" if nearest is not None and nearest < 3 else "把机会变成进球"
            why = "这次进攻被转化成进球，打破了此前的平衡。" if leads and before[home] == before[away] else "这次进攻被转化成进球，改变了比分。"
            home_voice, away_voice = "进了！我们把这次机会把握住了！", "唉，还是没能守住这次射门。"
        elif outcome == "Saved":
            title = "射门机会止步于扑救"
            why = "门将挡住了这次射门，让这次进攻没有改变比分。"
            home_voice, away_voice = "可惜，被扑出了！我们的这次进攻没能得分。", "扑得好！我们的门将守住了这次射门！"
        else:
            title = "推进到位，射门未能得分"
            why = "推进创造了射门机会，但球偏出球门，比分没有改变。"
            home_voice, away_voice = "可惜偏了，这次进攻还差最后一下。", "松了一口气，对手这脚没有打进。"
    else:
        title, detail, why = "比赛继续", f"{facts['actor']} 完成了当前动作。", "等待更多事件再判断这次进攻的发展。"
        home_voice = away_voice = ""
    tone = "" if audience == "neutral" else home_voice if favor_attack else away_voice
    if audience != "neutral":
        if kind == "Pass":
            why = ("重点看接球后的处理：我们的球已经向前转移，接下来能否继续推进？" if favor_attack
                   else "重点看对方接球者：这次向前传递后，他会成为我们防守需要关注的人。") if facts["forward_progress_m"] > 0 else why
        elif kind == "Carry" and facts["goal_distance_reduction_m"] > 0:
            why = ("对我们而言，这次带球让持球者更接近球门；能否完成下一步，还要看防守。" if favor_attack
                   else "从我们的防守视角看，对手正在缩短与球门的距离，下一步处理值得警惕。")
        elif kind in ("Shot", "Goal Keeper") and facts.get("outcome") == "Saved":
            why = ("我们已经把进攻推进到射门这一步，但门将的扑救让机会没能变成进球。" if favor_attack
                   else "对手已经完成射门，我们的门将通过扑救保持了比分。")
    if mode == "casual":
        if kind in ("Shot", "Goal Keeper"):
            detail = f"这脚射门距离球门中心约 {round(facts['goal_distance_m'])} 米。"
        elif kind == "Carry":
            detail = f"{facts['actor']} 持球向球门靠近。" if facts["goal_distance_reduction_m"] > 0 else f"{facts['actor']} 调整了持球位置。"
    text = " ".join(part for part in (tone, detail, why) if part)
    if mode == "analyst" and "goal_opening_angle_degrees" in facts:
        text += f" 从射门点看，两门柱夹角约 {facts['goal_opening_angle_degrees']}°。"
    event_names = {"Pass": "传球", "Ball Receipt*": "接球", "Carry": "带球推进", "Shot": "射门", "Goal Keeper": "扑救"}
    evidence = [{"event_id": item["id"], "label": f"{item['minute']}′ {item['player']['name']} · {event_names.get(item['type']['name'], item['type']['name'])}"} for item in chain]
    result = {
        "schema": "pilot.live-insight.v1", "event_id": event_id,
        "audience": audience, "mode": mode, "title": title, "text": text,
        "generator": "rules-v1", "generator_label": "规则解读 · AI 接口待接入",
        "facts": facts, "evidence": evidence,
        "measurement_note": f"距离与角度按 {physical[0]} × {physical[1]} 米模拟球场计算；依据为合成事件与位置。",
        "render": {"slot": "pitch_commentary", "match_minute": event["minute"], "match_second": event["second"], "expires_on_next_event": True},
        "ai_request": {
            "instructions": (
                "Write a short Chinese football insight for the current event, explaining its significance. "
                "Use only the supplied facts and evidence. Never predict or reveal later events. "
                "Audience preference changes emphasis and emotion, never facts. "
                "Do not invent intent, causation, xG, historical records, tactical patterns or unseen runs. "
                "Nearby defenders alone do not prove a shot was blocked or forced wide. "
                "Return JSON {title, text, evidence_event_ids}. Cite only supplied IDs. "
                "For casual mode use plain language and at most one numeric metric; for analyst mode explain selected computed metrics. "
                "For home/away fans speak as a supporter using 我们, with joy, disappointment or relief appropriate to the actual outcome. "
                "Choose a viewpoint: attacking fans care about creating/converting chances; defending fans care about threats and stopping shots. "
                "For neutral viewers explain both sides without partisan emotion. Do not merely repeat the event: explain its supported significance."
                " A one-goal lead is narrow, never a huge advantage. Do not invent crowd reactions or call a result decisive. "
                "Prioritize a concrete observation from the supplied facts over generic celebration."
            ),
            "audience": audience, "supported_team_id": supported, "attacking_team_id": attack_team,
            "mode": mode, "facts": facts, "evidence": evidence,
        },
    }
    if writer is not None:
        try:
            response = writer.generate(result["ai_request"])
            allowed = {item["event_id"] for item in evidence}
            if not isinstance(response, dict):
                raise ValueError("Expected a JSON object")
            refs = response.get("evidence_event_ids")
            if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref in allowed for ref in refs) or event_id not in refs:
                raise ValueError("Missing current-event evidence or unsupported references")
            if not all(isinstance(response.get(key), str) and 0 < len(response[key].strip()) <= limit
                       for key, limit in (("title", 60), ("text", 320))):
                raise ValueError("Invalid insight title or text")
            result.update(title=response["title"], text=response["text"], generator="ai",
                          generator_label="AI 解读 · 基于当前合成事件",
                          cited_event_ids=refs, validation_scope="Schema and evidence references only; semantic accuracy is not automatically verified.")
            if "generation" in response:
                result["generation"] = response["generation"]
        except Exception:
            # A slow/failed/invalid model must not remove the rule-based explanation.
            result["generator_label"] = "规则解读 · AI 暂不可用"
            result["ai_status"] = "fallback"
    return result
