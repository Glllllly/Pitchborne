"""Timed Spanish and French match calls from synthetic event facts."""

from workflow.broadcast_beats import INTERVAL_SECONDS, _counts


PHRASES = {
    "es": {
        "pass_ok": ("{name} encuentra a {recipient}; sigue la jugada.", "¡{name} conecta con {recipient}, seguimos avanzando!", "El rival encuentra a {recipient}; toca cerrar espacios."),
        "pass_lost": ("El pase de {name} no llega a {recipient}.", "¡Ay, {name} pierde el balón!", "¡Recuperamos! El pase de {name} no llega."),
        "carry": ("{name} conduce hacia delante, buscando espacio.", "¡{name} avanza con el balón, vamos!", "{name} progresa; tenemos que cerrar el camino."),
        "win": ("{name} recupera el balón y cambia la posesión.", "¡Bien, {name} recupera para los nuestros!", "Perdemos el balón ante {name}; hay que replegarse."),
        "pressure": ("{name} presiona al jugador con balón.", "¡{name} aprieta arriba, a forzar el error!", "Nos presiona {name}; hay que soltar el balón."),
        "goal": ("¡Gol de {name}! El marcador queda {home}-{away}.", "¡Gooool de {name}! ¡Lo celebramos, vamos {ours}-{theirs}!", "Nos marca {name}. Duele; vamos {ours}-{theirs}."),
        "saved": ("¡Dispara {name} y {keeper} detiene el balón!", "¡Remata {name}, pero {keeper} lo para!", "¡Qué parada de {keeper} ante {name}!"),
        "wide": ("{name} dispara, pero el balón se va fuera.", "¡Qué pena! {name} remata desviado.", "{name} falla el tiro; respiramos."),
        "opening": ("¡Comienza el partido! {name} pone el balón en juego.", "¡Arrancamos! {name} mueve el balón para los nuestros.", "¡Arranca el partido! Saca el rival; mantenemos la forma."),
        "restart": ("Vuelta al centro: {name} saca tras el gol.", "{name} reanuda desde el centro; ¡a reaccionar!", "El rival saca de centro; seguimos atentos."),
        "fulltime": ("¡Final del partido! {home}-{away}.", "¡Final! Terminamos {ours}-{theirs}.", "¡Final! Terminamos {ours}-{theirs}."),
        "keeper": ("{name} asegura el balón.", "¡Bien, {name} protege la portería!", "El portero rival se queda con el balón."),
        "intro": "¡Comienza el partido! {home} recibe a {away}; ambos salen con un 4-3-3.",
        "intro_fan": "¡Comienza el partido! Apoyamos a {ours} ante {theirs}; ambos salen con un 4-3-3.",
        "lineup": "Once inicial de {team}: portero {gk}; defensa {defenders}; centro del campo {midfield}; ataque {attack}.",
        "summary": "Balance de este tramo: {home_shots} tiros locales ({home_target} a puerta) y {away_shots} visitantes ({away_target} a puerta). Goles: {home_goals}-{away_goals}.",
        "final_summary": "Balance final: {home_shots} tiros locales ({home_target} a puerta) y {away_shots} visitantes ({away_target} a puerta). Goles: {home_goals}-{away_goals}.",
    },
    "fr": {
        "pass_ok": ("{name} trouve {recipient} ; l'action continue.", "{name} sert {recipient}, on continue d'avancer !", "L'adversaire trouve {recipient} ; il faut resserrer."),
        "pass_lost": ("La passe de {name} n'atteint pas {recipient}.", "Oh non, {name} perd le ballon !", "On récupère ! La passe de {name} est coupée."),
        "carry": ("{name} progresse balle au pied et cherche de l'espace.", "{name} avance avec le ballon, allez !", "{name} progresse ; fermons les espaces."),
        "win": ("{name} récupère le ballon ; la possession change de camp.", "Bien joué, {name} récupère pour nous !", "{name} nous prend le ballon ; il faut se replacer."),
        "pressure": ("{name} presse le porteur du ballon.", "{name} monte au pressing ; provoquons l'erreur !", "{name} nous presse ; il faut faire circuler le ballon."),
        "goal": ("But de {name} ! Le score est de {home}-{away}.", "Buuut de {name} ! On mène le score à {ours}-{theirs} !", "{name} marque contre nous. C'est dur : {ours}-{theirs}."),
        "saved": ("{name} frappe, mais {keeper} repousse !", "{name} tente sa chance ; {keeper} arrête le tir !", "Quel arrêt de {keeper} face à {name} !"),
        "wide": ("{name} frappe, mais le ballon passe à côté.", "Dommage, {name} ne cadre pas !", "{name} manque le cadre ; on peut souffler."),
        "opening": ("C'est parti ! {name} donne le coup d'envoi.", "C'est parti ! {name} lance notre match.", "C'est parti ; l'adversaire engage, restons bien placés."),
        "restart": ("Retour au rond central : {name} engage après le but.", "{name} remet le ballon en jeu ; réagissons !", "L'adversaire engage au centre ; restons vigilants."),
        "fulltime": ("Coup de sifflet final ! {home}-{away}.", "C'est fini ! Score final pour nous : {ours}-{theirs}.", "C'est fini ! Score final pour nous : {ours}-{theirs}."),
        "keeper": ("{name} capte le ballon.", "Bien joué, {name} protège notre but !", "Le gardien adverse garde le ballon."),
        "intro": "Coup d'envoi ! {home} reçoit {away} ; les deux équipes évoluent en 4-3-3.",
        "intro_fan": "Coup d'envoi ! On soutient {ours} face à {theirs} ; les deux équipes évoluent en 4-3-3.",
        "lineup": "Onze de départ de {team} : gardien {gk} ; défense {defenders} ; milieu {midfield} ; attaque {attack}.",
        "summary": "Bilan de cette période : {home_shots} tirs à domicile ({home_target} cadrés), {away_shots} à l'extérieur ({away_target} cadrés). Buts : {home_goals}-{away_goals}.",
        "final_summary": "Bilan final : {home_shots} tirs à domicile ({home_target} cadrés), {away_shots} à l'extérieur ({away_target} cadrés). Buts : {home_goals}-{away_goals}.",
    },
}

ALTERNATES = {
    "es": {
        "pass_ok": ("{recipient} recibe el pase de {name}; el ataque sigue vivo.", "Buen pase de {name} para {recipient}; ¡sigamos!", "{name} conecta con {recipient}; hay que seguirles de cerca."),
        "pass_lost": ("{name} buscó a {recipient}, pero cortaron la línea.", "No llega el pase de {name}; toca recuperar.", "El pase rival queda corto; podemos salir."),
        "carry": ("{name} gana metros con el balón.", "{name} conduce y nos acerca al área.", "{name} lleva el balón hacia nuestra defensa."),
        "win": ("Interviene {name}; termina la posesión rival.", "¡{name} corta la jugada y recuperamos!", "{name} nos roba; reorganizamos la defensa."),
        "pressure": ("{name} cierra el espacio del poseedor.", "{name} mete presión; ¡que no jueguen cómodos!", "{name} aprieta; necesitamos una salida rápida."),
        "saved": ("{keeper} salva el disparo de {name}.", "¡{keeper} frena el tiro de {name}!", "¡{keeper} salva nuestra portería ante {name}!"),
        "wide": ("El intento de {name} no encuentra portería.", "{name} remata, pero no acierta a puerta.", "El tiro de {name} sale desviado; seguimos vivos."),
    },
    "fr": {
        "pass_ok": ("{recipient} reçoit la passe de {name} ; l'attaque se poursuit.", "Belle passe de {name} pour {recipient} ; continuons !", "{name} trouve {recipient} ; suivons le mouvement."),
        "pass_lost": ("{name} cherchait {recipient}, mais la passe est coupée.", "La passe de {name} échoue ; récupérons vite.", "La passe adverse n'arrive pas ; à nous de jouer."),
        "carry": ("{name} gagne du terrain avec le ballon.", "{name} avance et nous rapproche de la surface.", "{name} porte le ballon vers notre défense."),
        "win": ("{name} intervient ; l'attaque adverse s'arrête.", "{name} coupe la trajectoire ; on récupère !", "{name} nous dépossède ; replaçons-nous."),
        "pressure": ("{name} réduit l'espace du porteur.", "{name} met la pression ; ne les laissons pas jouer !", "{name} nous presse ; trouvons vite une sortie."),
        "saved": ("{keeper} repousse la frappe de {name}.", "{keeper} arrête la tentative de {name} !", "{keeper} sauve notre but face à {name} !"),
        "wide": ("La tentative de {name} manque le cadre.", "{name} tire, mais ne cadre pas.", "La frappe de {name} passe à côté ; on respire."),
    },
}


def _lineup(match, side, words):
    team = match[f"{side}_team"]
    players = [entry for entry in match["players"] if entry["team_id"] == team["id"]]
    def names(positions):
        return ", ".join(entry["player"]["name"] for entry in players if entry["position"] in positions)
    return words["lineup"].format(team=team["name"], gk=names({"GK"}),
                                  defenders=names({"LB", "CB", "RB"}),
                                  midfield=names({"DM", "CM"}), attack=names({"LW", "ST", "RW"}))


def build_romance_tracks(match, events, language):
    if language not in PHRASES:
        raise ValueError("Unsupported commentary language")
    words = PHRASES[language]
    home, away = match["home_team"]["id"], match["away_team"]["id"]
    score = {home: 0, away: 0}
    tracks = {audience: [] for audience in ("neutral", "home", "away")}
    turns = {}
    for index, event in enumerate(events):
        kind, name = event["type"]["name"], event["player"]["name"]
        actor = event["team"]["id"]
        if kind == "Shot" and event["shot"]["outcome"]["name"] == "Goal":
            score[actor] += 1
        category = None
        if kind == "Pass":
            if event["pass"]["outcome"]["name"] != "Complete": category = "pass_lost"
            elif event["possession"] % 2 == 0 or event["location"][0] > 75: category = "pass_ok"
        elif kind == "Carry" and (event["possession"] % 3 == 0 or event["location"][0] > 80): category = "carry"
        elif kind in ("Interception", "Tackle"): category = "win"
        elif kind == "Pressure" and event["possession"] % 3 == 0: category = "pressure"
        elif kind == "Shot": category = {"Goal": "goal", "Saved": "saved", "Off T": "wide"}[event["shot"]["outcome"]["name"]]
        elif kind == "Kick Off": category = "opening" if event["kick_off"].get("opening") else "restart"
        elif kind == "Full Time": category = "fulltime"
        for audience, lines in tracks.items():
            supported = None if audience == "neutral" else match[f"{audience}_team"]["id"]
            stance = 0 if supported is None else 1 if supported == actor else 2
            opponent = away if supported == home else home
            values = {"name": name, "recipient": event.get("pass", {}).get("recipient", {}).get("name", ""),
                      "keeper": next((p["player"]["name"] for p in event.get("shot", {}).get("freeze_frame", [])
                                      if p["position"]["name"] == "Goalkeeper"), "the keeper"),
                      "home": score[home], "away": score[away],
                      "ours": score.get(supported, 0), "theirs": score[opponent]}
            text = ""
            if category:
                key = (audience, category)
                turn = turns.get(key, 0)
                turns[key] = turn + 1
                choices = [words[category][stance]]
                if category in ALTERNATES[language]:
                    choices.append(ALTERNATES[language][category][stance])
                text = choices[turn % len(choices)].format(**values)
            lines.append({"event_id": event["id"], "text": text,
                          "match_second": event["minute"] * 60 + event["second"]})
    if not events:
        return tracks
    for audience, lines in tracks.items():
        home_name, away_name = match["home_team"]["name"], match["away_team"]["name"]
        opening = words["intro"].format(home=home_name, away=away_name) if audience == "neutral" else words["intro_fan"].format(
            ours=home_name if audience == "home" else away_name,
            theirs=away_name if audience == "home" else home_name)
        lines[0]["intro"] = [opening, _lineup(match, "home", words), _lineup(match, "away", words)]
    next_mark, previous_end = INTERVAL_SECONDS, -1
    for index, event in enumerate(events):
        second = event["minute"] * 60 + event["second"]
        if second < next_mark: continue
        final = event["type"]["name"] == "Full Time"
        window = (events[:index + 1] if final else
                  [item for item in events[:index + 1]
                   if previous_end < item["minute"] * 60 + item["second"] <= second])
        counts = _counts(match, window)
        home_count, away_count = counts["home"], counts["away"]
        values = {"home_shots": home_count["shots"], "home_target": home_count["on_target"],
                  "away_shots": away_count["shots"], "away_target": away_count["on_target"],
                  "home_goals": home_count["goals"], "away_goals": away_count["goals"]}
        for lines in tracks.values():
            lines[index]["summary"] = {
                "text": words["final_summary" if final else "summary"].format(**values),
                "period_start_second": 0 if final else max(0, previous_end),
                "period_end_second": second, "facts": counts,
            }
        previous_end, next_mark = second, next_mark + INTERVAL_SECONDS
    return tracks
