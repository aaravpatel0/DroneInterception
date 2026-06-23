from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2

from project_utils import ensure_dir, image_extensions, load_config, project_path


def find_yolo_images(yolo_dir: Path, split: str, extensions: set[str]) -> list[Path]:
    root = yolo_dir / "images" / split
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in extensions)


def label_path_for_image(yolo_dir: Path, image_path: Path) -> Path:
    split = image_path.parent.name
    return yolo_dir / "labels" / split / f"{ image_path.stem }.txt"


def draw_labels(image_path: Path, label_path: Path) -> object:
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"Could not read image: { image_path }")
    height, width = image.shape[:2]
    if label_path.exists():
        for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            try:
                _, xc, yc, bw, bh = [float(value) for value in parts]
            except ValueError:
                continue
            x1 = int((xc - bw / 2) * width)
            y1 = int((yc - bh / 2) * height)
            x2 = int((xc + bw / 2) * width)
            y2 = int((yc + bh / 2) * height)
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 220, 255), 2)
            cv2.putText(image, "drone", (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 2)
    return image


def preview(config: dict, split: str, count: int, show: bool) -> None:
    yolo_dir = project_path(config["yolo_dir"])
    data_yaml = yolo_dir / "data.yaml"
    if not data_yaml.exists():
        raise FileNotFoundError(f"YOLO data.yaml not found at { data_yaml }. Run merge_roboflow_datasets.py first.")
    images = find_yolo_images(yolo_dir, split, image_extensions(config))
    if not images:
        raise FileNotFoundError(f"No YOLO images found for split '{ split }' under { yolo_dir / 'images' / split }")

    output_dir = ensure_dir(project_path(config["processed_dir"]) / "previews")
    sample = random.sample(images, min(count, len(images)))
    for image_path in sample:
        label_path = label_path_for_image(yolo_dir, image_path)
        drawn = draw_labels(image_path, label_path)
        output_path = output_dir / f"{ split }_{ image_path.stem }_preview.jpg"
        cv2.imwrite(str(output_path), drawn)
        print(f"[preview] Saved: { output_path }")
        if show:
            cv2.imshow("YOLO label preview", drawn)
            cv2.waitKey(0)
    if show:
        cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create random visual previews of YOLO labels.")
    parser.add_argument("--split", default="train", choices=["train", "val", "test"], help="YOLO split to preview.")
    parser.add_argument("--count", type=int, default=12, help="Number of preview images to create.")
    parser.add_argument("--show", action="store_true", help="Open each preview window as it is generated.")
    args = parser.parse_args()
    preview(load_config(), args.split, args.count, args.show)


if __name__ == "__main__":
    main()
