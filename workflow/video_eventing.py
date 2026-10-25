"""Colour-marker vision baseline for the synthetic pitch video feed.

The detector receives pixels and frame rate, not source event labels. It is
deliberately limited to the repo's rendered feed, not broadcast footage.
"""

import math


def _cv2():
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("Install requirements-video.txt for video eventing") from error
    return cv2


WIDTH, HEIGHT = 320, 220
FPS = 12


def to_pixel(location):
    return round(20 + location[0] * 280 / 120), round(20 + location[1] * 180 / 80)


def from_pixel(pixel):
    return ((pixel[0] - 20) * 120 / 280, (pixel[1] - 20) * 80 / 180)


def render_synthetic_feed(events, output, fps=FPS):
    """Render unlabelled ball paths; events supply only positions and duration."""
    cv2 = _cv2()
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"MJPG"), fps, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError("Could not create synthetic video feed")
    import numpy as np
    blank = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    try:
        for event in events:
            if not event.get("kinematics"):
                continue
            start, end = event["tracking"]["ball_start"], event["tracking"]["ball_end"]
            frames = max(4, round(event["kinematics"]["ball_flight_seconds"] * fps) + 1)
            for index in range(frames):
                t = index / (frames - 1)
                frame = np.full((HEIGHT, WIDTH, 3), (38, 105, 53), dtype=np.uint8)
                cv2.rectangle(frame, (20, 20), (300, 200), (120, 155, 120), 1)
                point = to_pixel((start[0] + (end[0] - start[0]) * t,
                                  start[1] + (end[1] - start[1]) * t))
                cv2.circle(frame, point, 5, (255, 255, 255), -1)
                writer.write(frame)
            writer.write(blank)
            writer.write(blank)
    finally:
        writer.release()


def detect_video(source):
    """Detect pass/shot-like ball movements from rendered video pixels only."""
    cv2 = _cv2()
    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        raise RuntimeError(f"Could not read video source: {source}")
    fps = capture.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        raise RuntimeError("Video has no usable frame rate")
    found, segment, frame_index = [], [], 0

    def finish():
        if len(segment) < 4:
            return
        start, end = from_pixel(segment[0][1]), from_pixel(segment[-1][1])
        distance = math.hypot((end[0] - start[0]) * 105 / 120,
                              (end[1] - start[1]) * 68 / 80)
        if distance < 1.5:
            return
        duration = (segment[-1][0] - segment[0][0]) / fps
        kind = "Shot" if start[0] >= 75 and end[0] >= 114 else "Pass"
        found.append({"type": kind, "start": [round(v, 1) for v in start],
                      "end": [round(v, 1) for v in end],
                      "ball_speed_kmh": round(distance / duration * 3.6, 1),
                      "video_second": round(segment[0][0] / fps, 2),
                      "source": "synthetic_video_pixels_v1"})

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            mask = cv2.inRange(frame, (220, 220, 220), (255, 255, 255))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            ball = max(contours, key=cv2.contourArea) if contours else None
            if ball is not None and cv2.contourArea(ball) >= 12:
                moments = cv2.moments(ball)
                if moments["m00"]:
                    segment.append((frame_index, (moments["m10"] / moments["m00"],
                                                  moments["m01"] / moments["m00"])))
            elif segment:
                finish()
                segment = []
            frame_index += 1
        finish()
    finally:
        capture.release()
    return found
