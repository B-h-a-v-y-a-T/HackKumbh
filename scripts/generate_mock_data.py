"""
Generate synthetic mock examination frames and video for testing.

Creates exam-hall-like images using OpenCV for mock/demo testing
without requiring real examination footage.
"""

import argparse
import random
from pathlib import Path

import cv2
import numpy as np


def generate_exam_frame(
    width: int = 1920, height: int = 1080, num_desks: int = 12, seed: int = 42
) -> np.ndarray:
    """Generate a synthetic examination hall frame."""
    rng = random.Random(seed)
    frame = np.full((height, width, 3), (220, 215, 210), dtype=np.uint8)

    # Floor gradient
    for y in range(height):
        shade = int(200 + (y / height) * 30)
        frame[y, :] = (shade, shade - 5, shade - 10)

    # Draw desk rows
    rows = 3
    cols = num_desks // rows
    desk_w, desk_h = 140, 100
    margin_x, margin_y = 120, 150

    for row in range(rows):
        for col in range(cols):
            x = margin_x + col * (desk_w + 60)
            y = margin_y + row * (desk_h + 180)

            # Desk surface
            cv2.rectangle(frame, (x, y), (x + desk_w, y + desk_h), (160, 140, 120), -1)
            cv2.rectangle(frame, (x, y), (x + desk_w, y + desk_h), (120, 100, 80), 2)

            # Paper on desk
            px, py = x + 15, y + 10
            cv2.rectangle(frame, (px, py), (px + 80, py + 60), (250, 250, 250), -1)
            cv2.rectangle(frame, (px, py), (px + 80, py + 60), (200, 200, 200), 1)
            # Text lines on paper
            for line_y in range(py + 10, py + 55, 8):
                lw = rng.randint(30, 70)
                cv2.line(frame, (px + 5, line_y), (px + 5 + lw, line_y), (180, 180, 180), 1)

            # Student silhouette (upper body)
            head_x = x + desk_w // 2
            head_y = y - 40
            cv2.circle(frame, (head_x, head_y), 20, (100, 90, 80), -1)
            # Shoulders
            cv2.ellipse(frame, (head_x, head_y + 45), (35, 25), 0, 0, 180, (90, 80, 70), -1)

            # Pen
            pen_x = x + rng.randint(50, 100)
            pen_y = y + rng.randint(20, 60)
            cv2.line(frame, (pen_x, pen_y), (pen_x + 8, pen_y - 30), (50, 50, 150), 2)

    # Add a simulated phone on one desk (for detection testing)
    phone_desk_col = 2
    phone_desk_row = 1
    px = margin_x + phone_desk_col * (desk_w + 60) + 100
    py = margin_y + phone_desk_row * (desk_h + 180) + 30
    # Phone shape
    cv2.rectangle(frame, (px, py), (px + 25, py + 50), (30, 30, 30), -1)
    cv2.rectangle(frame, (px + 2, py + 5), (px + 23, py + 42), (60, 80, 100), -1)
    cv2.rectangle(frame, (px, py), (px + 25, py + 50), (20, 20, 20), 1)

    # Add a small chit near another desk
    chit_x = margin_x + 3 * (desk_w + 60) + 30
    chit_y = margin_y + 0 * (desk_h + 180) + 70
    pts = np.array([
        [chit_x, chit_y], [chit_x + 35, chit_y + 5],
        [chit_x + 30, chit_y + 25], [chit_x - 3, chit_y + 20]
    ], np.int32)
    cv2.fillPoly(frame, [pts], (240, 240, 230))
    cv2.polylines(frame, [pts], True, (200, 200, 190), 1)

    # Lighting variation
    noise = np.random.RandomState(seed).randint(-5, 6, frame.shape, dtype=np.int16)
    frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return frame


def generate_mock_video(
    output_path: str,
    duration_seconds: float = 30.0,
    fps: float = 15.0,
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Generate a short synthetic exam video."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = int(duration_seconds * fps)
    for i in range(total_frames):
        frame = generate_exam_frame(width, height, seed=42 + (i // 30))
        # Add subtle motion
        shift = int(2 * np.sin(i * 0.05))
        M = np.float32([[1, 0, shift], [0, 1, 0]])
        frame = cv2.warpAffine(frame, M, (width, height), borderValue=(210, 210, 210))
        # Timestamp overlay
        ts = f"CAM_01 | {i / fps:.1f}s"
        cv2.putText(frame, ts, (10, height - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        writer.write(frame)

    writer.release()
    print(f"Generated mock video: {output_path} ({total_frames} frames, {duration_seconds}s)")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Generate mock examination data")
    parser.add_argument("--output-dir", default="data/mock", help="Output directory")
    parser.add_argument("--video-duration", type=float, default=30.0, help="Video duration in seconds")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Generate frame
    frame = generate_exam_frame()
    frame_path = str(out / "exam_frame.jpg")
    cv2.imwrite(frame_path, frame)
    print(f"Generated mock frame: {frame_path} ({frame.shape[1]}x{frame.shape[0]})")

    # Generate video
    video_path = str(out / "sample_video.mp4")
    generate_mock_video(video_path, duration_seconds=args.video_duration)


if __name__ == "__main__":
    main()
