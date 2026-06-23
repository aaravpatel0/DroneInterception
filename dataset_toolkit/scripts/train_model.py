from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO

from common import PROJECT_ROOT, load_config, setup_logging


LOGGER = setup_logging("train_model")


def hub_root() -> Path:
    if (PROJECT_ROOT / "dataset_toolkit").exists():
        return PROJECT_ROOT / "dataset_toolkit"
    return PROJECT_ROOT


def detect_device() -> str | int:
    try:
        import torch

        if torch.cuda.is_available():
            LOGGER.info("CUDA detected: %s", torch.cuda.get_device_name(0))
            return 0
    except Exception as exc:
        LOGGER.info("Could not inspect CUDA: %s", exc)
    LOGGER.info("CUDA unavailable; using CPU")
    return "cpu"


def main() -> None:
    parser = argparse.ArgumentParser(description="Train YOLOv8 on the merged drone dataset.")
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--name", default="drone_multidataset_yolov8")
    args = parser.parse_args()
    config = load_config()
    root = hub_root()
    data_yaml = root / "data" / "yolo_merged" / "data.yaml"
    if not data_yaml.exists():
        raise FileNotFoundError("Merged data.yaml not found. Run prepare_uploaded_datasets.py and merge_yolo_datasets.py first.")
    model = YOLO(args.model)
    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz or int(config["yolo_imgsz"]),
        batch=args.batch,
        project=str(root / "runs" / "train"),
        name=args.name,
        device=detect_device(),
        exist_ok=True,
    )


if __name__ == "__main__":
    main()
