from __future__ import annotations

import argparse
from pathlib import Path

import cv2


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "calibration_images_opencv"


def parse_source(source: str) -> int | str:
    clean = str(source).strip()
    return int(clean) if clean.isdigit() else clean


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture checkerboard calibration images through OpenCV.")
    parser.add_argument("--source", default="0", help="Camera index, video path, or stream URL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Folder for captured images.")
    parser.add_argument("--prefix", default="opencv_calib", help="Captured image filename prefix.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(parse_source(args.source))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera source: {args.source}")

    saved = 0
    print("Press SPACE to save a calibration image. Press q to quit.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("Camera opened but failed to read a frame.")
            height, width = frame.shape[:2]
            cv2.putText(frame, f"{width}x{height} saved={saved}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.imshow("Calibration Capture", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == 32:
                saved += 1
                output = args.output_dir / f"{args.prefix}_{saved:03d}.jpg"
                cv2.imwrite(str(output), frame)
                print(f"[saved] {output}")
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
