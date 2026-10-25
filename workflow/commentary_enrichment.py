"""Vary live calls using only the event and past match context."""

from collections import defaultdict, deque

from workflow.match_context import build_match_context


ZH = {
    "pass_ok": {
        "neutral": ["{name} 把球送到 {recipient} 脚下，这次传递接上了。", "{recipient} 接到 {name} 的球，进攻还在推进。", "球从 {name} 交到 {recipient}，这一段配合继续。", "{name} 找到了 {recipient}，球权保持在这一边。"],
        "ours": ["{name} 找到 {recipient}，我们接着往前！", "传得好，{recipient} 已经接住了。", "球到 {recipient} 脚下，我们这次进攻还在继续。", "{name} 送出这一脚，{recipient} 接上了！"],
        "theirs": ["对手找到 {recipient}，我们得跟紧接球点。", "球到了 {recipient} 脚下，别让他轻松往前。", "{name} 这脚传成了，我们要跟着移动。", "对方传递连起来了，注意 {recipient} 的下一步。"],
    },
    "pass_lost": {
        "neutral": ["{name} 没能找到 {recipient}，传递在这里中断。", "{name} 的球没送到，{recipient} 没接上。", "传球线路被切断，{name} 这一脚丢了。"],
        "ours": ["哎，{name} 这脚没接上，球权丢了。", "可惜，{name} 想找 {recipient}，传球没成。", "这一下传丢了，得赶快回位。"],
        "theirs": ["对手这脚没送到，先把球控制住。", "传球没接上！我们准备转入进攻。", "{name} 的传递失误了，我们可以重新组织。"],
    },
    "carry": {
        "neutral": ["{name} 带球继续推进，下一步处理值得看。", "{name} 持球往前走，球来到更靠前的位置。", "这次由 {name} 带球，进攻再往前一步。", "{name} 没急着出球，选择自己带着球推进。"],
        "ours": ["{name} 继续带，我们还在往前走！", "往前走！{name} 这次推进没有停。", "{name} 把球带起来了，看看能不能接上下一脚。", "这次是 {name} 带球，我们保持进攻。"],
        "theirs": ["{name} 带球上来了，我们得压缩前面的空间。", "对手还在推进，盯住 {name} 的下一步。", "{name} 往前带，别让他轻松接近危险区域。", "这段带球让对方更靠前，我们要及时跟防。"],
    },
    "win": {
        "neutral": ["{name} 把球断下来，球权换边！", "防守到位，{name} 抢回球权。", "{name} 出手成功，这次推进在这里被终止。"],
        "ours": ["断得漂亮！{name} 帮我们拿回球权。", "好球，{name} 把这次进攻挡住了。", "{name} 抢下来了，现在轮到我们处理球！"],
        "theirs": ["球被 {name} 断了，我们得立刻回防。", "哎呀，球权丢了，先稳住防守位置。", "{name} 把球抢走了，这次推进没能继续。"],
    },
    "pressure": {
        "neutral": ["{name} 贴上去施压，持球者需要更快出球。", "{name} 开始逼抢，球还在对方脚下。", "{name} 这次上抢给了持球者压力。"],
        "ours": ["{name} 逼上去了！争取让对手仓促处理。", "继续压迫，{name} 已经贴近持球者。", "{name} 上去施压，看看能不能逼出失误。"],
        "theirs": ["{name} 逼过来了，我们得尽快把球送出去。", "对手压上来了，先把这一下处理干净。", "{name} 贴近持球者，别在这里丢球。"],
    },
    "saved": {
        "neutral": ["{name} 起脚——{keeper} 扑出来了！", "射门！{keeper} 做出扑救，比分没有变化。", "{name} 这脚奔向球门，{keeper} 把球挡住了！"],
        "ours": ["{name} 射了！哎，被 {keeper} 挡住了。", "起脚了！{name} 这一下还是被扑出去了。", "可惜，{name} 的射门被 {keeper} 守住。"],
        "theirs": ["扑出来了！我们的门将 {keeper} 守住了这次射门！", "好样的，{keeper} 把 {name} 的球挡了出去！", "{keeper} 没让这脚射门改写比分，守住了！"],
    },
    "wide": {
        "neutral": ["{name} 起脚，球偏出了！", "射门没能命中球门，{name} 这次机会结束。", "{name} 尝试攻门，球从门旁边过去了。"],
        "ours": ["{name} 这脚偏了，太可惜！", "哎呀，{name} 已经起脚，可惜没打在门框范围内。", "机会出来了，{name} 这一下却没能射正。"],
        "theirs": ["射偏了！这次我们没有丢球。", "呼，{name} 这脚偏了，比分没变。", "对手这脚没射正，我们先稳住局面。"],
    },
}

EN = {
    "pass_ok": {
        "neutral": ["{name} finds {recipient}; the move keeps going.", "A clean pass from {name} into {recipient}'s feet.", "{recipient} takes the ball from {name}, with possession retained.", "{name} plays it to {recipient}; another step in the attack."],
        "ours": ["{name} finds {recipient} — we're moving forward!", "Good ball to {recipient}; keep this going.", "{recipient} takes it from {name}, and we're still building.", "{name} gets the pass away; {recipient} has it now."],
        "theirs": ["They find {recipient}; we need to stay close.", "{name} connects with {recipient}; watch the receiver.", "Their passing move continues through {recipient}.", "{recipient} has the ball now — stay with the play."],
    },
    "pass_lost": {
        "neutral": ["{name}'s pass does not reach {recipient}.", "That ball from {name} is cut out before {recipient} can collect.", "A misplaced pass from {name}; the move breaks down."],
        "ours": ["Oh, {name} gives it away there.", "Unlucky — {name} cannot find {recipient}.", "We've lost the ball; get back into shape."],
        "theirs": ["Their pass is off target — secure the loose ball.", "That move breaks down; we can take possession.", "{name} cannot find the pass, and we have a way back in."],
    },
    "carry": {
        "neutral": ["{name} drives forward with the ball.", "{name} carries into a more advanced position.", "The move keeps rolling as {name} advances.", "{name} takes the ball on; the next touch matters."],
        "ours": ["{name} is moving us closer to goal!", "Go on, {name} — keep carrying it forward.", "We're still building through {name}'s run.", "{name} brings the ball up; can we add the next pass?"],
        "theirs": ["{name} is coming forward; close the space.", "They're advancing with {name} on the ball.", "Stay with {name}; that carry moves them closer.", "{name} keeps coming — track the next touch."],
    },
    "win": {
        "neutral": ["{name} steps in; possession changes hands.", "Defensive work from {name}, and the attack stops there.", "{name} wins the ball back."],
        "ours": ["Yes! {name} wins it back for us.", "Good defending by {name}; we have the ball again.", "{name} gets there first — our turn to build."],
        "theirs": ["{name} wins it; we need to recover our positions.", "We've lost the ball — get back into shape.", "That move is broken up by {name}."],
    },
    "pressure": {
        "neutral": ["{name} closes down the ball carrier.", "Pressure from {name}; the ball is still with the opponent.", "{name} forces a quicker decision on the ball."],
        "ours": ["{name} presses in — force a mistake!", "Keep pressing; {name} is right on the ball.", "{name} closes the gap, looking to unsettle them."],
        "theirs": ["{name} is pressing us; move the ball quickly.", "They are closing down — play out of this cleanly.", "{name} is right on the carrier; do not lose it here."],
    },
    "saved": {
        "neutral": ["{name} shoots — saved by {keeper}!", "A shot from {name}, and {keeper} keeps it out.", "{name} goes for goal; {keeper} makes the save!"],
        "ours": ["{name} shoots! Ah, {keeper} stops it.", "So close — {keeper} denies {name}.", "{name} gets the shot away, but {keeper} is there."],
        "theirs": ["Saved! Our keeper {keeper} keeps it out!", "What a stop from {keeper} — {name} cannot score.", "{keeper} gets there; the score stays as it is!"],
    },
    "wide": {
        "neutral": ["{name} shoots — wide!", "{name} gets the shot away, but it misses the target.", "An effort from {name}; no change to the score."],
        "ours": ["{name} puts it wide — what a chance!", "Ah, {name} cannot get that one on target.", "We got the shot, but {name} sends it wide."],
        "theirs": ["Wide! We escape that one.", "{name} misses the target; the score holds.", "That shot stays out — settle down and reset."],
    },
}


def enrich_tracks(match, events, tracks, language):
    templates = ZH if language == "zh" else EN
    turns = defaultdict(int)
    recent_lines = {audience: deque(maxlen=24) for audience in tracks}
    prefix = []
    home, away = match["home_team"]["id"], match["away_team"]["id"]
    score = {home: 0, away: 0}
    for index, event in enumerate(events):
        prefix.append(event)
        kind = event["type"]["name"]
        before = score.copy()
        if kind == "Shot" and event["shot"]["outcome"]["name"] == "Goal":
            score[event["team"]["id"]] += 1
        if kind == "Pass":
            category = "pass_ok" if event["pass"]["outcome"]["name"] == "Complete" else "pass_lost"
        elif kind == "Carry":
            category = "carry"
        elif kind in ("Interception", "Tackle"):
            category = "win"
        elif kind == "Pressure":
            category = "pressure"
        elif kind == "Shot":
            category = {"Saved": "saved", "Off T": "wide"}.get(event["shot"]["outcome"]["name"])
        else:
            category = None
        if kind == "Goal Keeper":
            for lines in tracks.values():
                lines[index]["text"] = ""  # The preceding shot has already called the save.
            continue
        if category is None:
            if kind == "Shot":
                scorer = event["team"]["id"]
                other = away if scorer == home else home
                if before[scorer] <= before[other] and score[scorer] > score[other]:
                    zh_note, en_note = "这一球让他们取得领先。", "That goal puts them in front."
                elif before[scorer] < before[other] and score[scorer] == score[other]:
                    zh_note, en_note = "这一球把比分扳平。", "That goal brings the scores level."
                elif score[scorer] < score[other]:
                    zh_note, en_note = "这一球缩小了分差。", "That goal cuts the deficit."
                else:
                    zh_note, en_note = "这一球扩大了领先优势。", "That goal extends their lead."
                for audience, lines in tracks.items():
                    if audience == "neutral":
                        lines[index]["text"] += " " + (zh_note if language == "zh" else en_note)
                    elif match[f"{audience}_team"]["id"] == scorer:
                        lines[index]["text"] += " " + ((zh_note.replace("他们", "我们")) if language == "zh" else en_note.replace("them", "us").replace("their", "our"))
                    recent_lines[audience].append(lines[index]["text"])
            continue
        context = build_match_context(match, prefix, event) if kind in ("Shot", "Interception", "Tackle", "Pressure") else None
        keeper = ""
        if kind == "Shot":
            keeper = next((player["player"]["name"] for player in event["shot"]["freeze_frame"]
                           if player["position"]["name"] == "Goalkeeper"), "门将" if language == "zh" else "the keeper")
        values = {"name": event["player"]["name"],
                  "recipient": event.get("pass", {}).get("recipient", {}).get("name", ""), "keeper": keeper}
        for audience, lines in tracks.items():
            if not lines[index]["text"]:
                continue
            supported = None if audience == "neutral" else match[f"{audience}_team"]["id"]
            stance = "neutral" if supported is None else "ours" if supported == event["team"]["id"] else "theirs"
            options = templates[category][stance]
            key = (audience, category)
            text = options[turns[key] % len(options)].format(**values)
            for offset in range(1, len(options)):
                if text not in recent_lines[audience]:
                    break
                text = options[(turns[key] + offset) % len(options)].format(**values)
                turns[key] += 1
            turns[key] += 1
            if kind == "Shot":
                passes = context["possession_completed_passes"]
                if passes >= 2 and event["index"] % 2 == 0:
                    text += (f" 这次球权先完成了 {passes} 脚传球。" if language == "zh" else
                             f" That possession included {passes} completed passes.")
                elif context["recent_shots"] >= 2 and event["index"] % 2:
                    number = context["recent_shots"]
                    text += (f" 这是这一边近五分钟第 {number} 次射门。" if language == "zh" else
                             f" It's this team's shot number {number} in five minutes.")
            elif kind in ("Interception", "Tackle") and context["recent_ball_wins"] >= 3 and event["index"] % 3 == 0:
                text += (" 这段时间同一边已经多次夺回球权。" if language == "zh" else
                         " This side has won the ball back repeatedly in the last five minutes.")
            lines[index]["text"] = text
            recent_lines[audience].append(text)
    return tracks
