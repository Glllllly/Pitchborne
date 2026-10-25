"""Kick-off introductions and past-only interval summaries for timed tracks."""


INTERVAL_SECONDS = 600


def _lineup(match, side, language):
    team = match[f"{side}_team"]
    players = sorted((entry for entry in match["players"] if entry["team_id"] == team["id"]),
                     key=lambda entry: entry["shirt_number"])
    groups = [
        ("门将", "goalkeeper", {"GK"}),
        ("后卫", "defenders", {"LB", "CB", "RB"}),
        ("中场", "midfield", {"DM", "CM"}),
        ("前场", "front three", {"LW", "ST", "RW"}),
    ]
    parts = []
    for zh_label, en_label, positions in groups:
        names = [entry["player"]["name"] for entry in players if entry["position"] in positions]
        label = zh_label if language == "zh" else en_label
        parts.append(f"{label}：{'、'.join(names)}" if language == "zh" else f"{label}: {', '.join(names)}")
    return "；".join(parts) + "。" if language == "zh" else "; ".join(parts) + "."


def _intro(match, audience, language):
    home, away = match["home_team"]["name"], match["away_team"]["name"]
    if language == "zh":
        opening = (f"比赛开始！主队 {home} 对阵客队 {away}，双方都以 4-3-3 开场。" if audience == "neutral" else
                   f"比赛开始！我们支持的{'主队 ' + home if audience == 'home' else '客队 ' + away}，今天面对{'客队 ' + away if audience == 'home' else '主队 ' + home}。双方都以 4-3-3 开场。")
        return [opening, f"先看主队 {home} 的首发：{_lineup(match, 'home', language)}",
                f"客队 {away} 的首发：{_lineup(match, 'away', language)}"]
    opening = (f"Kick-off! {home} host {away}, with both sides starting in a 4-3-3." if audience == "neutral" else
               f"Kick-off! We're backing {'the hosts ' + home if audience == 'home' else 'the visitors ' + away} against {'the visitors ' + away if audience == 'home' else 'the hosts ' + home}. Both sides start in a 4-3-3.")
    return [opening, f"The home XI, {home}: {_lineup(match, 'home', language)}",
            f"The away XI, {away}: {_lineup(match, 'away', language)}"]


def _counts(match, events):
    result = {}
    for side in ("home", "away"):
        team_id = match[f"{side}_team"]["id"]
        own = [event for event in events if event["team"]["id"] == team_id]
        shots = [event for event in own if event["type"]["name"] == "Shot"]
        result[side] = {
            "shots": len(shots),
            "on_target": sum(event["shot"]["outcome"]["name"] in ("Goal", "Saved") for event in shots),
            "goals": sum(event["shot"]["outcome"]["name"] == "Goal" for event in shots),
            "pressures": sum(event["type"]["name"] == "Pressure" for event in own),
        }
    return result


def _summary_text(counts, audience, language, final=False):
    home, away = counts["home"], counts["away"]
    ours = counts[audience] if audience in ("home", "away") else None
    theirs = counts["away" if audience == "home" else "home"] if ours else None
    if language == "zh":
        lead = "全场回顾：" if final else "回头看刚才这段时间，"
        if audience == "neutral":
            if home["shots"] >= 3 and home["shots"] >= away["shots"] + 2:
                body = f"主队连续形成机会，{home['shots']} 次射门、{home['on_target']} 次射正；客队 {away['shots']} 次射门。"
            elif away["shots"] >= 3 and away["shots"] >= home["shots"] + 2:
                body = f"客队这段时间起脚更频繁，{away['shots']} 次射门、{away['on_target']} 次射正；主队 {home['shots']} 次射门。"
            elif home["shots"] >= 2 and away["shots"] >= 2:
                body = f"双方互有攻门：主队 {home['shots']} 次射门，客队 {away['shots']} 次。"
            elif home["shots"] + away["shots"]:
                body = f"射门机会不算密集，主队 {home['shots']} 次、客队 {away['shots']} 次。"
            else:
                body = "双方都还没有完成射门，进攻更多停留在组织和争夺阶段。"
        elif ours["shots"] >= 3 and ours["shots"] >= theirs["shots"] + 2:
            body = f"我们已经起脚 {ours['shots']} 次，其中 {ours['on_target']} 次射正；对手只有 {theirs['shots']} 次。机会正在累积。"
        elif theirs["shots"] >= 3 and theirs["shots"] >= ours["shots"] + 2:
            body = f"对手完成 {theirs['shots']} 次射门，我们只有 {ours['shots']} 次；门前压力需要认真应对。"
        elif ours["shots"] + theirs["shots"]:
            body = f"我们 {ours['shots']} 次射门，对手 {theirs['shots']} 次，双方都在寻找更好的最后一脚。"
        else:
            body = "两边暂时都没有射门，先看谁能把推进变成真正的机会。"
        if home["goals"] + away["goals"]:
            body += f" 这一段主队进 {home['goals']} 球、客队进 {away['goals']} 球。"
        elif home["shots"] + away["shots"] == 0 and home["pressures"] + away["pressures"] >= 3:
            body += f" 已记录主队 {home['pressures']} 次、客队 {away['pressures']} 次施压。"
        return lead + body
    lead = "Full-time review: " if final else "Looking back over this spell, "
    if audience == "neutral":
        if home["shots"] >= 3 and home["shots"] >= away["shots"] + 2:
            body = f"the hosts have had the busier shooting spell: {home['shots']} shots, {home['on_target']} on target, against {away['shots']} for the visitors."
        elif away["shots"] >= 3 and away["shots"] >= home["shots"] + 2:
            body = f"the visitors have been shooting more often: {away['shots']} shots, {away['on_target']} on target, against {home['shots']} for the hosts."
        elif home["shots"] >= 2 and away["shots"] >= 2:
            body = f"both sides have had chances: {home['shots']} home shots and {away['shots']} away shots."
        elif home["shots"] + away["shots"]:
            body = f"chances have been limited: {home['shots']} home shots and {away['shots']} away shots."
        else:
            body = "neither side has taken a shot yet; the play has been about building and winning the ball."
    elif ours["shots"] >= 3 and ours["shots"] >= theirs["shots"] + 2:
        body = f"we have taken {ours['shots']} shots, {ours['on_target']} on target, while they have only {theirs['shots']}."
    elif theirs["shots"] >= 3 and theirs["shots"] >= ours["shots"] + 2:
        body = f"they have taken {theirs['shots']} shots to our {ours['shots']}; we need to deal with that pressure."
    elif ours["shots"] + theirs["shots"]:
        body = f"we have {ours['shots']} shots and they have {theirs['shots']}; both sides are still looking for a cleaner finish."
    else:
        body = "neither side has taken a shot yet; the next good move could change that."
    if home["goals"] + away["goals"]:
        body += f" Goals in this spell: {home['goals']} for the hosts and {away['goals']} for the visitors."
    return lead + body


def add_broadcast_beats(match, events, tracks, language):
    if not events:
        return tracks
    for audience, lines in tracks.items():
        lines[0]["intro"] = _intro(match, audience, language)
    next_mark = INTERVAL_SECONDS
    previous_end = -1
    for index, event in enumerate(events):
        second = event["minute"] * 60 + event["second"]
        if second < next_mark:
            continue
        final = event["type"]["name"] == "Full Time"
        window = (events[:index + 1] if final else
                  [item for item in events[:index + 1]
                   if previous_end < item["minute"] * 60 + item["second"] <= second])
        counts = _counts(match, window)
        for audience, lines in tracks.items():
            lines[index]["summary"] = {
                "text": _summary_text(counts, audience, language, final=final),
                "period_start_second": 0 if final else max(0, previous_end),
                "period_end_second": second,
                "facts": counts,
            }
        previous_end = second
        next_mark += INTERVAL_SECONDS
    return tracks
