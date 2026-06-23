from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO

from project_utils import ensure_dir, load_config, project_path, resolve_device


def parse_source(source: str) -> str | int:
    source = source.strip()
    if source.isdigit():
        return int(source)
    path = Path(source)
    if path.exists():
        return str(path)
    return source


def run_inference(source: str, config: dict, device: str = "auto") -> None:
    model_path = project_path("models") / str(config.get("final_model_name", "drone_roboflow_best.pt"))
    if not model_path.exists():
        raise FileNotFoundError(f"Trained model not found: { model_path }. Run train_yolov8.py first.")

    output_dir = ensure_dir(project_path("runs") / "inference")
    model = YOLO(str(model_path))
    parsed_source = parse_source(source)
    webcam_mode = isinstance(parsed_source, int)
    print(f"[infer] Running inference with source: { parsed_source }")
    print(f"[infer] Outputs will be saved under: { output_dir }")

    model.predict(
        source=parsed_source,
        conf=float(config["confidence_threshold"]),
        project=str(output_dir),
        name="predict",
        save=True,
        show=webcam_mode,
        device=resolve_device(device, "infer"),
        exist_ok=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run YOLOv8 drone inference on an image, video, or webcam.")
    parser.add_argument("--source", required=True, help="Image path, video path, URL, or webcam index such as 0.")
    parser.add_argument("--device", default="auto", help="Inference device: auto, cpu, 0, 1, etc.")
    args = parser.parse_args()
    run_inference(args.source, load_config(), device=args.device)


if __name__ == "__main__":
    main()
