from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import yaml


DEFAULT_IMAGE_DIR = Path(__file__).resolve().parents[1] / "calibration_images"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "camera_calibration.yaml"
DEFAULT_TRACKER_CONFIG = Path(__file__).resolve().parent / "camera_config.yaml"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def list_images(image_dir: Path) -> list[Path]:
    return sorted(path for path in image_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)


def make_object_points(corners_x: int, corners_y: int, square_size: float) -> np.ndarray:
    points = np.zeros((corners_x * corners_y, 3), np.float32)
    points[:, :2] = np.mgrid[0:corners_x, 0:corners_y].T.reshape(-1, 2)
    points *= float(square_size)
    return points


def find_corners(gray, corners_x: int, corners_y: int):
    pattern_size = (corners_x, corners_y)
    flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_FAST_CHECK
    found, corners = cv2.findChessboardCorners(gray, pattern_size, flags)
    if not found:
        return False, None
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
    return True, refined


def calibrate(image_paths: list[Path], corners_x: int, corners_y: int, square_size: float):
    object_template = make_object_points(corners_x, corners_y, square_size)
    object_points = []
    image_points = []
    image_size = None
    used_images = []

    for path in image_paths:
        image = cv2.imread(str(path))
        if image is None:
            print(f"[skip] Could not read {path}")
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        image_size = gray.shape[::-1]
        found, corners = find_corners(gray, corners_x, corners_y)
        if not found:
            print(f"[skip] Checkerboard not found: {path.name}")
            continue
        object_points.append(object_template)
        image_points.append(corners)
        used_images.append(path.name)
        print(f"[ok] {path.name}")

    if len(object_points) < 5:
        raise RuntimeError(f"Only found corners in {len(object_points)} images. Use at least 5, ideally 15-30.")

    rms, camera_matrix, dist_coeffs, _rvecs, _tvecs = cv2.calibrateCamera(
        object_points,
        image_points,
        image_size,
        None,
        None,
    )
    return rms, camera_matrix, dist_coeffs.reshape(-1), image_size, used_images


def write_outputs(output_path: Path, payload: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    output_path.with_suffix(".json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def update_tracker_config(config_path: Path, payload: dict) -> None:
    config = {}
    if config_path.exists():
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config["focal_length_px"] = float(payload["camera_matrix"][0][0])
    config["calibration_image_size"] = payload["image_size"]
    config["camera_matrix"] = payload["camera_matrix"]
    config["dist_coeffs"] = payload["dist_coeffs"]
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate a webcam from checkerboard photos.")
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR, help="Folder containing checkerboard photos.")
    parser.add_argument("--corners-x", type=int, default=7, help="Inner checkerboard corners across the short side.")
    parser.add_argument("--corners-y", type=int, default=9, help="Inner checkerboard corners across the long side.")
    parser.add_argument("--square-size-mm", type=float, default=20.0, help="Printed checkerboard square size in millimeters.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="YAML output path.")
    parser.add_argument("--update-config", action="store_true", help="Write calibration into live_tracker/camera_config.yaml.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.image_dir.exists():
        raise FileNotFoundError(f"Image folder not found: {args.image_dir}")
    image_paths = list_images(args.image_dir)
    if not image_paths:
        raise FileNotFoundError(f"No calibration images found in {args.image_dir}")

    rms, camera_matrix, dist_coeffs, image_size, used_images = calibrate(
        image_paths,
        args.corners_x,
        args.corners_y,
        args.square_size_mm,
    )
    payload = {
        "image_size": [int(image_size[0]), int(image_size[1])],
        "rms_reprojection_error": float(rms),
        "camera_matrix": camera_matrix.tolist(),
        "dist_coeffs": dist_coeffs.tolist(),
        "used_images": used_images,
    }
    write_outputs(args.output, payload)
    if args.update_config:
        update_tracker_config(DEFAULT_TRACKER_CONFIG, payload)
    print("\nCalibration complete.")
    print(f"RMS reprojection error: {rms:.4f}")
    print(f"Wrote: {args.output}")
    print("\nPaste these into live_tracker/camera_config.yaml:")
    print(yaml.safe_dump({"camera_matrix": payload["camera_matrix"], "dist_coeffs": payload["dist_coeffs"]}, sort_keys=False))


if __name__ == "__main__":
    main()
