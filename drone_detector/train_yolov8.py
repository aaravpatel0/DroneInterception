from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

from project_utils import ensure_dir, load_config, project_path, resolve_device, write_text


def resolve_model_path(model_size: str) -> str:
    configured = project_path(model_size)
    if configured.exists():
        return str(configured)
    local_model = project_path("models") / Path(model_size).name
    if local_model.exists():
        return str(local_model)
    # Ultralytics accepts names like yolov8n.pt and downloads/caches them when
    # they are not already present in the repo.
    return model_size


def parse_cache(value: str | bool) -> str | bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"false", "0", "off", "no", "none"}:
        return False
    if normalized in {"true", "1", "on", "yes"}:
        return True
    if normalized in {"ram", "disk"}:
        return normalized
    raise ValueError("cache must be one of: false, true, ram, disk")


def train(
    config: dict,
    device: str = "auto",
    epochs: int | None = None,
    imgsz: int | None = None,
    batch: int | None = None,
    workers: int | None = None,
    cache: str | bool | None = None,
) -> Path:
    yolo_dir = project_path(config["yolo_dir"])
    data_yaml = yolo_dir / "data.yaml"
    if not data_yaml.exists():
        raise FileNotFoundError(f"Missing YOLO data file: { data_yaml }. Run merge_roboflow_datasets.py first.")

    train_epochs = int(epochs if epochs is not None else config["epochs"])
    train_imgsz = int(imgsz if imgsz is not None else config["imgsz"])
    train_batch = int(batch if batch is not None else config["batch"])
    train_workers = int(workers if workers is not None else config.get("workers", 8))
    train_cache = parse_cache(cache if cache is not None else config.get("cache", False))

    model = YOLO(resolve_model_path(str(config["model_size"])))
    runs_dir = ensure_dir(project_path("runs") / "train")
    print("[train] Starting YOLOv8 training")
    results = model.train(
        data=str(data_yaml),
        epochs=train_epochs,
        imgsz=train_imgsz,
        batch=train_batch,
        workers=train_workers,
        cache=train_cache,
        project=str(runs_dir),
        name="drone_roboflow_yolov8",
        device=resolve_device(device, "train"),
        exist_ok=True,
    )

    save_dir = Path(getattr(results, "save_dir", runs_dir / "drone_roboflow_yolov8"))
    best_path = save_dir / "weights" / "best.pt"
    if not best_path.exists():
        raise FileNotFoundError(f"Training finished, but best.pt was not found at { best_path }")

    models_dir = ensure_dir(project_path("models"))
    final_model = models_dir / str(config.get("final_model_name", "drone_roboflow_best.pt"))
    # Copy the best run checkpoint to a stable filename so inference and live
    # tracking do not need to know the latest Ultralytics run directory.
    shutil.copy2(best_path, final_model)
    write_text(models_dir / "latest_model_path.txt", str(final_model.resolve()) + "\n")
    print(f"[train] Best checkpoint: { best_path }")
    print(f"[train] Copied final model to: { final_model }")
    return final_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train YOLOv8 on the merged Roboflow drone dataset.")
    parser.add_argument("--device", default="auto", help="Device to use: auto, cpu, or a CUDA index such as 0.")
    parser.add_argument("--epochs", type=int, help="Override config.yaml epochs.")
    parser.add_argument("--imgsz", type=int, help="Override config.yaml image size.")
    parser.add_argument("--batch", type=int, help="Override config.yaml batch size.")
    parser.add_argument("--workers", type=int, help="Override dataloader worker count.")
    parser.add_argument("--cache", help="Cache images for faster training: false, true, ram, or disk.")
    return parser.parse_args()


def apply_overrides(config: dict, args: argparse.Namespace) -> dict:
    updated = dict(config)
    for key in ("epochs", "imgsz", "batch", "workers", "cache"):
        value = getattr(args, key)
        if value is not None:
            updated[key] = value
    return updated


def main() -> None:
    args = parse_args()
    train(
        load_config(),
        device=args.device,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        cache=args.cache,
    )


if __name__ == "__main__":
    main()
