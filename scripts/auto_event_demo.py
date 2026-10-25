"""Render a short synthetic feed, then infer ball events from its video pixels."""

import argparse
import json
from pathlib import Path

from scripts.generate_match import generate
from workflow.video_eventing import detect_video, render_synthetic_feed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output", type=Path, default=Path("outputs/auto-event-demo.avi"))
    parser.add_argument("--source", help="Read an existing synthetic marker video instead of rendering a demo")
    args = parser.parse_args()
    if args.source:
        source = args.source
    else:
        _, events, _ = generate(args.seed)
        sample = [next(event for event in events if event["type"]["name"] == kind)
                  for kind in ("Pass", "Shot")]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        render_synthetic_feed(sample, args.output)
        source = str(args.output)
    detections = detect_video(source)
    print(json.dumps({"video": source, "detections": detections}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
