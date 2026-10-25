"""Grounded, timed play-by-play for each viewer allegiance."""


def build_tracks(match, events):
    home = match["home_team"]["id"]
    away = match["away_team"]["id"]
    score = {home: 0, away: 0}
    tracks = {audience: [] for audience in ("neutral", "home", "away")}

    for event in events:
        kind = event["type"]["name"]
        name = event["player"]["name"]
        actor_team = event["team"]["id"]
        if kind == "Shot" and event["shot"]["outcome"]["name"] == "Goal":
            score[actor_team] += 1
        for audience, lines in tracks.items():
            supported = None if audience == "neutral" else match[f"{audience}_team"]["id"]
            ours = supported == actor_team
            text = ""
            if kind == "Pass":
                complete = event["pass"]["outcome"]["name"] == "Complete"
                recipient = event["pass"]["recipient"]["name"]
                if not complete:
                    text = (f"{name} 这脚传球被拦下了！" if audience == "neutral" else
                            f"哎，{name} 传丢了！" if ours else "断下来了！对方这次传递没接上。")
                elif event["possession"] % 2 == 0 or event["location"][0] > 75:
                    text = (f"{name} 把球交给 {recipient}，进攻继续向前。" if audience == "neutral" else
                            f"{name} 找到 {recipient}，我们继续往前！" if ours else
                            f"对方把球送到 {recipient} 脚下，我们得跟紧。")
            elif kind == "Carry" and (event["possession"] % 3 == 0 or event["location"][0] > 80):
                text = (f"{name} 带球向前，正在寻找下一步空间。" if audience == "neutral" else
                        f"{name} 继续推进，我们看看能不能打出机会！" if ours else
                        f"对方还在推进，别让 {name} 轻松靠近球门。")
            elif kind == "Interception":
                text = (f"{name} 看准线路，拦下这脚传球！" if audience == "neutral" else
                        f"断得好！{name} 帮我们拿回球权。" if ours else
                        "哎，传球被对方拦截了。")
            elif kind == "Tackle":
                text = (f"{name} 抢断成功，球权换边！" if audience == "neutral" else
                        f"漂亮！{name} 把球抢回来了。" if ours else "这球被对手抢走了，赶紧回防。")
            elif kind == "Pressure" and event["possession"] % 3 == 0:
                text = (f"{name} 上前施压，持球者要尽快处理。" if audience == "neutral" else
                        f"{name} 逼上去了，我们争取断球！" if ours else
                        "对方压过来了，我们得把球处理出去。")
            elif kind == "Shot":
                outcome = event["shot"]["outcome"]["name"]
                if outcome == "Goal":
                    before = [score[home] - int(actor_team == home), score[away] - int(actor_team == away)]
                    after = [score[home], score[away]]
                    text = (f"{name} 起脚——球进了！比分从 {before[0]} 比 {before[1]} 变成 {after[0]} 比 {after[1]}！"
                            if audience == "neutral" else
                            f"进了！{name} 把球打进了！我们现在 {score[supported]} 比 {score[away if supported == home else home]}！"
                            if ours else f"哎呀，{name} 这脚打进了，我们丢球了。")
                elif outcome == "Saved":
                    text = (f"{name} 起脚——门将扑出来了！" if audience == "neutral" else
                            f"{name} 射了！哎，被门将挡住了。" if ours else
                            "扑出来了！我们的门将守住了这次射门！")
                else:
                    text = (f"{name} 起脚，球偏出了！" if audience == "neutral" else
                            f"{name} 这脚偏了，太可惜！" if ours else "射偏了！这次我们没有丢球。")
            elif kind == "Goal Keeper":
                text = (f"{name} 把球挡在门外，这次射门没能改写比分。" if audience == "neutral" else
                        f"好样的！{name} 这一下守住了。" if ours else "我们的射门还是被门将扑住了。")
            elif kind == "Full Time":
                text = (f"全场结束！比分 {score[home]} 比 {score[away]}。" if audience == "neutral" else
                        f"比赛结束！我们 {'赢了' if score[supported] > score[away if supported == home else home] else '输了' if score[supported] < score[away if supported == home else home] else '打平了'}，比分 {score[home]} 比 {score[away]}。")
            lines.append({"event_id": event["id"], "text": text,
                          "match_second": event["minute"] * 60 + event["second"]})
    return tracks


def build_english_tracks(match, events):
    """Timed English calls from the same event stream, with allegiance-aware reactions."""
    home, away = match["home_team"]["id"], match["away_team"]["id"]
    score = {home: 0, away: 0}
    tracks = {audience: [] for audience in ("neutral", "home", "away")}
    for event in events:
        kind, name = event["type"]["name"], event["player"]["name"]
        actor = event["team"]["id"]
        if kind == "Shot" and event["shot"]["outcome"]["name"] == "Goal":
            score[actor] += 1
        for audience, lines in tracks.items():
            supported = None if audience == "neutral" else match[f"{audience}_team"]["id"]
            ours = supported == actor
            text = ""
            if kind == "Pass":
                recipient = event["pass"]["recipient"]["name"]
                if event["pass"]["outcome"]["name"] != "Complete":
                    text = (f"{name}'s pass is cut out!" if audience == "neutral" else
                            "Oh, we've given it away!" if ours else "We've intercepted that pass!")
                elif event["possession"] % 2 == 0 or event["location"][0] > 75:
                    text = (f"{name} finds {recipient}; the move keeps going." if audience == "neutral" else
                            f"{name} finds {recipient} — we're moving forward!" if ours else
                            f"They find {recipient}; we need to stay close.")
            elif kind == "Carry" and (event["possession"] % 3 == 0 or event["location"][0] > 80):
                text = (f"{name} drives forward, looking for space." if audience == "neutral" else
                        f"{name} carries it forward — can we make this count?" if ours else
                        f"{name} is coming forward; don't give them space.")
            elif kind in ("Interception", "Tackle"):
                action = "reads the pass and intercepts" if kind == "Interception" else "wins the tackle"
                text = (f"{name} {action}! Possession changes hands." if audience == "neutral" else
                        f"Yes! {name} wins it back for us." if ours else "We've lost the ball — get back into shape!")
            elif kind == "Pressure" and event["possession"] % 3 == 0:
                text = (f"{name} closes down the ball carrier." if audience == "neutral" else
                        f"{name} presses high — force a mistake!" if ours else "They're pressing us; move the ball quickly!")
            elif kind == "Shot":
                outcome = event["shot"]["outcome"]["name"]
                if outcome == "Goal":
                    text = (f"{name} shoots — it's in! {score[home]}–{score[away]}!" if audience == "neutral" else
                            f"Goal! {name} scores for us! We're {score[supported]}–{score[away if supported == home else home]}!" if ours else
                            f"Oh no, {name} scores against us.")
                elif outcome == "Saved":
                    text = (f"{name} shoots — saved by the keeper!" if audience == "neutral" else
                            f"{name} shoots! Ah, the keeper stops it." if ours else "Saved! Our keeper keeps it out!")
                else:
                    text = (f"{name} shoots — wide!" if audience == "neutral" else
                            f"{name} puts it wide — what a chance!" if ours else "Wide! We escape that one.")
            elif kind == "Goal Keeper":
                text = (f"{name} holds the shot; the score stays the same." if audience == "neutral" else
                        f"Brilliant save by {name}!" if ours else "Their keeper denies our shot.")
            elif kind == "Full Time":
                text = (f"Full time! {score[home]}–{score[away]}." if audience == "neutral" else
                        f"Full time! {'We win' if score[supported] > score[away if supported == home else home] else 'We lose' if score[supported] < score[away if supported == home else home] else 'It ends level'}, {score[home]}–{score[away]}.")
            lines.append({"event_id": event["id"], "text": text,
                          "match_second": event["minute"] * 60 + event["second"]})
    return tracks
