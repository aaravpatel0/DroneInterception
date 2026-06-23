from __future__ import annotations

from ultralytics import YOLO

from common import PROJECT_ROOT, load_config, setup_logging


LOGGER = setup_logging("smoke")


def detect_device() -> str | int:
    try:
        import torch

        if torch.cuda.is_available():
            LOGGER.info("CUDA detected: %s", torch.cuda.get_device_name(0))
            return 0
    except Exception as exc:
        LOGGER.info("Could not inspect CUDA: %s", exc)
    LOGGER.info("Using CPU")
    return "cpu"


def main() -> None:
    config = load_config()
    data_yaml = PROJECT_ROOT / "data" / "yolo_merged" / "data.yaml"
    if not data_yaml.exists():
        raise FileNotFoundError("Merged data.yaml not found. Run scripts/merge_yolo_datasets.py first.")
    model = YOLO("yolov8n.pt")
    model.train(
        data=str(data_yaml),
        epochs=1,
        imgsz=int(config["yolo_imgsz"]),
        batch=4,
        project=str(PROJECT_ROOT / "runs" / "smoke_test"),
        name="yolov8n_dataset_check",
        device=detect_device(),
        exist_ok=True,
    )
    LOGGER.info("Smoke test finished.")


if __name__ == "__main__":
    main()
