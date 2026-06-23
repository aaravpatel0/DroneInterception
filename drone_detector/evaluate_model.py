from __future__ import annotations

import argparse

from ultralytics import YOLO

from project_utils import ensure_dir, load_config, project_path, resolve_device, write_text


def evaluate(config: dict, device: str = "auto", imgsz: int | None = None, batch: int | None = None) -> None:
    model_path = project_path("models") / str(config.get("final_model_name", "drone_roboflow_best.pt"))
    data_yaml = project_path(config["yolo_dir"]) / "data.yaml"
    if not model_path.exists():
        raise FileNotFoundError(f"Trained model not found: { model_path }. Run train_yolov8.py first.")
    if not data_yaml.exists():
        raise FileNotFoundError(f"YOLO data file not found: { data_yaml }. Run merge_roboflow_datasets.py first.")

    eval_imgsz = int(imgsz if imgsz is not None else config["imgsz"])
    eval_batch = int(batch if batch is not None else config["batch"])

    model = YOLO(str(model_path))
    print("[eval] Running validation on the test split")
    metrics = model.val(
        data=str(data_yaml),
        split="test",
        imgsz=eval_imgsz,
        batch=eval_batch,
        project=str(project_path("runs") / "evaluate"),
        name="roboflow_drone_test",
        device=resolve_device(device, "eval"),
        exist_ok=True,
    )

    box = metrics.box
    report = (
        "YOLOv8 Test Evaluation\n"
        "======================\n"
        f"Model: { model_path.resolve() }\n"
        f"Data: { data_yaml.resolve() }\n"
        f"Precision: {float(box.mp):.6f}\n"
        f"Recall: {float(box.mr):.6f}\n"
        f"mAP50: {float(box.map50):.6f}\n"
        f"mAP50-95: {float(box.map):.6f}\n"
    )
    processed_dir = ensure_dir(project_path(config["processed_dir"]))
    write_text(processed_dir / "evaluation_report.txt", report)
    print(report)
    print(f"[eval] Report saved to: { processed_dir / 'evaluation_report.txt' }")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a trained YOLOv8 drone model on the test split.")
    parser.add_argument("--device", default="auto", help="Device to use: auto, cpu, or a CUDA index such as 0.")
    parser.add_argument("--imgsz", type=int, help="Override config.yaml image size.")
    parser.add_argument("--batch", type=int, help="Override config.yaml batch size.")
    return parser.parse_args()


def apply_overrides(config: dict, args: argparse.Namespace) -> dict:
    updated = dict(config)
    for key in ("imgsz", "batch"):
        value = getattr(args, key)
        if value is not None:
            updated[key] = value
    return updated


def main() -> None:
    args = parse_args()
    evaluate(load_config(), device=args.device, imgsz=args.imgsz, batch=args.batch)


if __name__ == "__main__":
    main()
