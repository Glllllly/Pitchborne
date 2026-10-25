"""Deterministic planning scaffold. No model calls or generated media."""

import argparse
import json
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[1]
RESULTS = {
    "Goal": ("the ball crosses the goal line inside the goal", "球进入球门", "The shot finds the net."),
    "Off T": ("the ball travels outside the goal mouth", "射门偏出球门", "The shot goes wide."),
    "Saved": ("the goalkeeper stops the shot before the goal line", "射门被门将扑出", "The goalkeeper saves the shot."),
}


class VideoProvider(Protocol):
    """Adapters return job status and optional media path/URL; never claim success early."""

    def submit(self, request: dict) -> dict: ...


class DryRunVideoProvider:
    def submit(self, request: dict) -> dict:
        return {
            "provider": "dry-run",
            "status": "not_submitted",
            "media_path": None,
            "reason": "No video model configured. Request prepared only.",
        }


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_context(data_dir, clip_id):
    match = read(data_dir / "match.json")
    events = read(data_dir / "events.json")
    clips = read(data_dir / "clips.json")
    clip = next((item for item in clips if item["id"] == clip_id), None)
    if clip is None:
        raise ValueError(f"Unknown clip: {clip_id}")
    by_id = {item["id"]: item for item in events}
    if len(by_id) != len(events):
        raise ValueError("Duplicate event IDs")
    if not match.get("synthetic") or not clip.get("synthetic"):
        raise ValueError("This workflow requires explicitly synthetic inputs")
    if clip["match_id"] != match["match_id"]:
        raise ValueError("Clip belongs to another match")
    chain = [by_id[event_id] for event_id in clip["event_ids"]]
    if not all(item.get("synthetic") for item in chain):
        raise ValueError("All source events must be synthetic")
    if clip["trigger_event_id"] not in clip["event_ids"]:
        raise ValueError("Trigger is not part of clip")
    shot = by_id[clip["trigger_event_id"]]
    if shot["type"]["name"] != "Shot":
        raise ValueError("Trigger must be a shot")
    outcome = shot["shot"]["outcome"]["name"]
    if outcome not in RESULTS or clip["generation_constraints"]["outcome"] != outcome:
        raise ValueError("Unsupported or conflicting shot outcome")
    if shot["shot"]["body_part"]["name"] != "Right Foot":
        raise ValueError("Initial prompt template supports right-footed shots only")
    if match["coordinate_system"]["attacking_direction"] != "positive_x for all supplied clips":
        raise ValueError("Initial template requires positive-x attacking direction")
    return {"match": match, "clip": clip, "events": chain, "shot": shot}


def plan_scene(context, pov):
    shot, clip = context["shot"], context["clip"]
    keeper = next(
        item for item in shot["shot"]["freeze_frame"]
        if item["position"]["name"] == "Goalkeeper" and not item["teammate"]
    )
    player = shot["player"] if pov == "striker" else keeper["player"]
    if player["id"] not in clip["available_pov_player_ids"]:
        raise ValueError("Selected player is not available for this clip")
    return {
        "schema": "pilot.scene.v1",
        "synthetic": True,
        "clip_id": clip["id"],
        "source_event_ids": clip["event_ids"],
        "pov": pov,
        "pov_player": player,
        "duration_seconds": clip["generation_constraints"]["target_duration_seconds"],
        "facts": {
            "shot_event_id": shot["id"],
            "shooter": shot["player"],
            "shot_location": shot["location"],
            "shot_end_location": shot["shot"]["end_location"],
            "outcome": shot["shot"]["outcome"]["name"],
            "body_part": shot["shot"]["body_part"]["name"],
            "freeze_frame": shot["shot"]["freeze_frame"],
            "score_before": clip["score_before"],
            "score_after": clip["score_after"],
        },
        "coordinate_system": context["match"]["coordinate_system"],
        "beats": [
            {"fraction": [0, 0.33], "action": "The striker receives the ground pass."},
            {"fraction": [0.33, 0.67], "action": "The striker carries the ball into the shooting position."},
            {"fraction": [0.67, 1], "action": RESULTS[shot["shot"]["outcome"]["name"]][0]},
        ],
        "creative_details": clip["generation_constraints"]["creative_details"],
        "limitations": [
            "Positions are a partial snapshot at shot time, not continuous tracking.",
            "Head orientation and motion interpolation are creative staging.",
            "Beat timing is editorial, not measured event timing.",
        ],
    }


def compile_video_request(scene):
    facts = scene["facts"]
    viewpoint = (
        "Camera at the striker's eye level, looking toward the goal in positive x."
        if scene["pov"] == "striker" else
        "Camera at the goalkeeper's eye level, looking out from the goal toward the approaching striker in negative x."
    )
    prompt = (
        f"A {scene['duration_seconds']}-second fictional football scene, one continuous "
        f"first-person shot through the eyes of {scene['pov_player']['name']}. {viewpoint} "
        "The striker receives a ground pass, carries forward, then shoots with the right foot. "
        f"Required ending: {RESULTS[facts['outcome']][0]}. "
        "Preserve the shot-time spatial layout described below. "
        "Use restrained head movement and natural stadium atmosphere. "
        "Do not switch to broadcast, third-person, or slow-motion camera. "
        "Use fictional unbranded kits. Do not add text to the image. "
        "Coordinates describe a normalized pitch, not camera pixels. "
        f"Scene facts: {json.dumps(facts, ensure_ascii=False)}. "
        f"Coordinate convention: {json.dumps(scene['coordinate_system'], ensure_ascii=False)}."
    )
    return {
        "schema": "pilot.video-request.v1",
        "prompt_version": "v1",
        "source_event_ids": scene["source_event_ids"],
        "pov": scene["pov"],
        "outcome": facts["outcome"],
        "duration_seconds": scene["duration_seconds"],
        "prompt": prompt,
        "negative_prompt": "camera cuts, broadcast view, changed outcome, duplicated ball, logos",
        "disclosure": "Synthetic match / AI scene interpretation",
    }


def audience_profile(context, audience, pov):
    if audience not in ("neutral", "home", "away"):
        raise ValueError("Unsupported audience")
    if audience == "neutral":
        return {"audience": audience, "pov": pov, "emotion": "neutral", "autoplay": False}
    team_id = context["match"][f"{audience}_team"]["id"]
    attacking = context["shot"]["team"]["id"] == team_id
    outcome = context["shot"]["shot"]["outcome"]["name"]
    emotion = ("joyful" if attacking else "disappointed") if outcome == "Goal" else (
        "disappointed" if attacking else "relieved"
    )
    return {"audience": audience, "supported_team_id": team_id,
            "pov": "striker" if attacking else "goalkeeper",
            "emotion": emotion, "autoplay": True}


def generate_commentary(context, scene, language, profile=None):
    """Template baseline; replace with grounded model generation behind this stage."""
    shot = context["shot"]
    outcome = scene["facts"]["outcome"]
    name = shot["player"]["name"]
    localized = {
        "zh": f"{name} 接球推进后右脚射门，{RESULTS[outcome][1]}。",
        "en": f"{name} receives the pass, carries forward and shoots with the right foot. {RESULTS[outcome][2]}",
        "es": f"{name} recibe el pase, avanza y remata con la derecha. " +
              {"Goal": "¡Gol!", "Saved": "El portero detiene el tiro.", "Off T": "El tiro se va fuera."}[outcome],
        "fr": f"{name} reçoit la passe, avance et frappe du pied droit. " +
              {"Goal": "But !", "Saved": "Le gardien repousse le tir.", "Off T": "Le tir passe à côté."}[outcome],
    }
    text = localized[language]
    profile = profile or audience_profile(context, "neutral", scene["pov"])
    if profile["audience"] != "neutral":
        attacking = profile["pov"] == "striker"
        phrases = {
            ("Goal", True): ("进了！我们的射手把球送进球门，一起庆祝这一刻！",
                             "It's in! Our striker finds the net. What a moment to celebrate!"),
            ("Goal", False): ("唉，还是丢球了。对方的射门越过了我们的门将。",
                              "A painful moment. Their shot beats our goalkeeper."),
            ("Saved", True): ("可惜！我们的射门被扑出了，这次没能破门。",
                              "So close! Our shot is saved. No goal this time."),
            ("Saved", False): ("扑得好！我们的门将挡住了射门，比分守住了！",
                               "What a save! Our goalkeeper stops the shot and keeps the score unchanged!"),
            ("Off T", True): ("可惜，射偏了。我们的这次进攻没能换来进球。",
                              "Oh, wide! Our attack ends without a goal."),
            ("Off T", False): ("松了一口气，对方射偏了，比分没有改变。",
                               "A sigh of relief. Their shot goes wide; the score stays unchanged."),
        }
        text = phrases[(outcome, attacking)][0 if language == "zh" else 1]
        if language in ("es", "fr"):
            reactions = {
                "es": {
                    ("Goal", True): "¡Gooool! ¡Nuestro delantero marca; a celebrarlo!",
                    ("Goal", False): "Nos marcan. Duele, pero hay que reaccionar.",
                    ("Saved", True): "¡Qué pena! El portero detiene nuestro remate.",
                    ("Saved", False): "¡Gran parada! Nuestro portero mantiene el resultado.",
                    ("Off T", True): "¡Qué pena! Nuestro tiro se va fuera.",
                    ("Off T", False): "Fallan el remate; respiramos.",
                },
                "fr": {
                    ("Goal", True): "Buuut ! Notre attaquant marque, on peut célébrer !",
                    ("Goal", False): "On encaisse un but. Il faut réagir.",
                    ("Saved", True): "Dommage ! Le gardien repousse notre frappe.",
                    ("Saved", False): "Quel arrêt ! Notre gardien préserve le score.",
                    ("Off T", True): "Dommage ! Notre tir passe à côté.",
                    ("Off T", False): "Leur tir passe à côté ; on peut souffler.",
                },
            }
            text = reactions[language][(outcome, attacking)]
    return {
        "language": language,
        "generator": "deterministic-template-v1",
        "text": text,
        "outcome": outcome,
        "source_event_ids": scene["source_event_ids"],
        "placement": "after_video",
        "audio_status": "not_generated",
        "audience": profile["audience"],
        "emotion": profile["emotion"],
    }


def validate_outputs(context, scene, request, commentary):
    expected = context["shot"]["shot"]["outcome"]["name"]
    if not (scene["facts"]["outcome"] == request["outcome"] == commentary["outcome"] == expected):
        raise ValueError("Outcome changed between workflow stages")
    expected_ids = context["clip"]["event_ids"]
    for value in (scene, request, commentary):
        if value["source_event_ids"] != expected_ids:
            raise ValueError("Evidence references changed between workflow stages")
    if request["pov"] != scene["pov"]:
        raise ValueError("Viewpoint changed")
    return {
        "status": "passed",
        "checks": ["outcome consistency", "source event references", "viewpoint consistency"],
        "scope": "Structured metadata only; not semantic prompt or generated-media verification.",
        "media_validation": "not_performed",
    }


def run(clip_id, pov, language, data_dir, output_dir, provider=None, audience="neutral"):
    if pov not in ("striker", "goalkeeper") or language not in ("zh", "en", "es", "fr"):
        raise ValueError("Unsupported POV or language")
    context = load_context(data_dir, clip_id)
    profile = audience_profile(context, audience, pov)
    pov = profile["pov"]
    scene = plan_scene(context, pov)
    scene["viewer"] = profile
    request = compile_video_request(scene)
    request["viewer"] = profile
    commentary = generate_commentary(context, scene, language, profile)
    validation = validate_outputs(context, scene, request, commentary)
    # Validate before any future paid provider submission.
    job = (provider or DryRunVideoProvider()).submit(request)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "scene.json": scene,
        "video_request.json": request,
        "commentary.json": commentary,
        "validation.json": validation,
        "video_job.json": job,
        "run.json": {
            "clip_id": clip_id, "pov": pov, "language": language, "viewer": profile,
            "status": "prepared" if job["status"] == "not_submitted" else "submitted",
            "stages": ["load", "plan", "compile_prompt", "commentary", "validate", "video_submit"],
        },
    }
    for name, value in artifacts.items():
        (output_dir / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clip", default="saved")
    parser.add_argument("--pov", choices=["striker", "goalkeeper"], default="striker")
    parser.add_argument("--language", choices=["zh", "en", "es", "fr"], default="zh")
    parser.add_argument("--audience", choices=["neutral", "home", "away"], default="neutral")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "synthetic")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "outputs" / f"{args.clip}-{args.pov}-{args.language}-{args.audience}"
    try:
        run(args.clip, args.pov, args.language, args.data_dir, output, audience=args.audience)
    except (ValueError, KeyError, StopIteration, OSError) as error:
        parser.exit(1, f"Workflow failed: {type(error).__name__}: {error}\n")
    print(f"Prepared workflow artifacts: {output}\nDry run: no video or audio generated.")


if __name__ == "__main__":
    main()
