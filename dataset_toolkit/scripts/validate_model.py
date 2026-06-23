from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO

from common import PROJECT_ROOT, load_config, setup_logging, write_text
from train_model import detect_device


LOGGER = setup_logging("validate_model")


def hub_root() -> Path:
    if (PROJECT_ROOT / "dataset_toolkit").exists():
        return PROJECT_ROOT / "dataset_toolkit"
    return PROJECT_ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a trained YOLOv8 model on the merged dataset.")
    parser.add_argument("--weights", required=True, help="Path to best.pt or another YOLO checkpoint.")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--imgsz", type=int)
    args = parser.parse_args()
    config = load_config()
    root = hub_root()
    data_yaml = root / "data" / "yolo_merged" / "data.yaml"
    weights = Path(args.weights)
    if not weights.is_absolute():
        weights = root / weights
    if not data_yaml.exists():
        raise FileNotFoundError("Merged data.yaml not found. Run merge_yolo_datasets.py first.")
    if not weights.exists():
        raise FileNotFoundError(f"Weights file not found: {weights}")

    model = YOLO(str(weights))
    metrics = model.val(
        data=str(data_yaml),
        split=args.split,
        imgsz=args.imgsz or int(config["yolo_imgsz"]),
        batch=args.batch,
        project=str(root / "runs" / "validate"),
        name=f"{weights.stem}_{args.split}",
        device=detect_device(),
        exist_ok=True,
    )
    report = (
        "# Validation Report\n\n"
        f"- Weights: `{weights}`\n"
        f"- Split: `{args.split}`\n"
        f"- Precision: {float(metrics.box.mp):.6f}\n"
        f"- Recall: {float(metrics.box.mr):.6f}\n"
        f"- mAP50: {float(metrics.box.map50):.6f}\n"
        f"- mAP50-95: {float(metrics.box.map):.6f}\n"
    )
    out = root / "reports" / "validation_report.md"
    write_text(out, report)
    print(report)


if __name__ == "__main__":
    main()
