"""Rolling, past-only match context for grounded on-screen interpretation."""


def build_match_context(match, prefix, event):
    second = event["minute"] * 60 + event["second"]
    team_id = event["team"]["id"]
    home_id = match["home_team"]["id"]
    away_id = match["away_team"]["id"]

    def in_period(item, start, end):
        time = item["minute"] * 60 + item["second"]
        return start < time <= end

    recent = [item for item in prefix if in_period(item, second - 300, second)]
    previous = [item for item in prefix if in_period(item, second - 600, second - 300)]
    possession = [item for item in prefix if item["possession"] == event["possession"]]

    def count(items, kind, side=None):
        return sum(item["type"]["name"] == kind and (side is None or item["team"]["id"] == side)
                   for item in items)

    own_shots = count(recent, "Shot", team_id)
    prior_shots = count(previous, "Shot", team_id)
    opponent_id = away_id if team_id == home_id else home_id
    opponent_shots = count(recent, "Shot", opponent_id)
    own_pressure = count(recent, "Pressure", team_id)
    own_turnovers = count(recent, "Interception", team_id) + count(recent, "Tackle", team_id)
    passes = sum(item["type"]["name"] == "Pass" and item["pass"]["outcome"]["name"] == "Complete"
                 for item in possession)
    carries = count(possession, "Carry")
    window_available = second >= 600
    if window_available and own_shots >= prior_shots + 2 and own_shots >= 2:
        rhythm = "rising_shot_volume"
    elif own_shots >= 2:
        rhythm = "repeat_shots"
    elif own_pressure >= 3:
        rhythm = "pressure_cluster"
    else:
        rhythm = "insufficient_signal"
    return {
        "window_seconds": min(300, second),
        "team_id": team_id,
        "team_name": event["team"]["name"],
        "recent_shots": own_shots,
        "opponent_recent_shots": opponent_shots,
        "previous_shots": prior_shots if window_available else None,
        "recent_pressures": own_pressure,
        "recent_ball_wins": own_turnovers,
        "possession_completed_passes": passes,
        "possession_carries": carries,
        "rhythm": rhythm,
        "supporting_event_ids": [item["id"] for item in recent
                                 if item["team"]["id"] == team_id and
                                 item["type"]["name"] in ("Shot", "Pressure", "Interception", "Tackle")][-8:],
    }


def build_analysis(event, facts, context):
    """A factual judgment, implication and watchpoint; never predicts an outcome."""
    kind = event["type"]["name"]
    signals = []
    if kind == "Shot":
        outcome = facts["outcome"]
        if outcome == "Goal":
            verdict = "这次机会改变了比分"
            why = "射门直接转化为进球，进攻产出已经体现在比分上。"
            watch = "重新开球后，观察双方能否延续此前的进攻节奏。"
        elif outcome == "Saved":
            verdict = "射门形成威胁，扑救保住比分"
            why = "进攻已经推进到射门，但门将的处理阻止了这次得分。"
            watch = "留意下一次推进能否再次进入类似的射门区域。"
        else:
            verdict = "进攻抵达射门区，终结未成功"
            why = "这次推进获得了射门机会，但射偏意味着比分没有变化。"
            watch = "观察后续机会能否改善射门位置或终结选择。"
        signals.extend([
            {"label": "射门距离", "value": f"{facts['goal_distance_m']} m"},
            {"label": "本方近五分钟射门", "value": str(context["recent_shots"])},
        ])
        if facts.get("nearest_defender_m") is not None:
            signals.append({"label": "最近防守者", "value": f"{facts['nearest_defender_m']} m"})
        if context["possession_completed_passes"]:
            signals.append({"label": "本次球权成功传球", "value": str(context["possession_completed_passes"])})
    elif kind == "Pressure":
        verdict = "一次防守施压，尚未形成夺回球权"
        why = "施压事件说明防守者正在限制持球空间；单次施压不能证明对手已经失误。"
        watch = "观察随后是否出现传球失误、拦截或抢断。"
        signals.append({"label": "本方近五分钟施压", "value": str(context["recent_pressures"])})
    elif kind in ("Interception", "Tackle"):
        verdict = "防守赢回球权，进攻方向切换"
        why = "这次拦截或抢断终止了对手当前的持球推进，提供了新的进攻起点。"
        watch = "观察夺回球权后能否完成第一脚有效传递。"
        signals.append({"label": "本方近五分钟夺回球权", "value": str(context["recent_ball_wins"])})
    elif kind == "Pass":
        complete = facts["pass_complete"]
        verdict = "传球推进成功" if complete else "传球链条中断"
        why = ("这次传递让下一名球员在更靠前的位置接球。" if facts["forward_progress_m"] > 0 else
               "这次传递维持球权并重新组织站位。") if complete else "传球没有找到接应者，原进攻链条停止。"
        watch = "观察接球者下一步能否继续推进。" if complete else "观察对手夺球后的第一步处理。"
        signals.append({"label": "向前推进", "value": f"{facts['forward_progress_m']} m"})
        if "pass_difficulty" in facts:
            signals.append({"label": "合成传球难度", "value": f"{facts['pass_difficulty']}/100"})
    else:
        verdict = "比赛继续"
        why = "当前事件不足以单独判断局势变化。"
        watch = "等待下一段事件链。"
    rhythm = context["rhythm"]
    if rhythm == "rising_shot_volume":
        pattern = (f"截至此刻，本方近五分钟 {context['recent_shots']} 次射门，"
                   f"高于此前五分钟的 {context['previous_shots']} 次；只能说明近期射门更密集。")
    elif rhythm == "repeat_shots":
        pattern = f"截至此刻，本方近五分钟已有 {context['recent_shots']} 次射门，机会正在重复出现。"
    elif rhythm == "pressure_cluster":
        pattern = f"截至此刻，本方近五分钟记录 {context['recent_pressures']} 次施压，但不能据此断定控球优势。"
    else:
        pattern = "目前没有足够的连续事件，不能判断一方已持续掌控局面。"
    return {"verdict": verdict, "why": why, "pattern": pattern,
            "watch": watch, "signals": signals,
            "scope": "只使用已发生的合成事件；局部事件不等于完整战术追踪。"}
