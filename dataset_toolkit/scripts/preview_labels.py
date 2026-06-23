from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2

from common import PROJECT_ROOT, ensure_dir, image_extensions, list_files, load_config, setup_logging


LOGGER = setup_logging("preview")


COLORS = {
    0: (0, 220, 255),
    1: (80, 220, 80),
    2: (255, 160, 0),
    3: (255, 80, 180),
    4: (190, 190, 190),
}


def label_for(image: Path, merged_root: Path, split: str) -> Path:
    return merged_root / "labels" / split / f"{image.stem}.txt"


def draw(image_path: Path, label_path: Path, names: dict[int, str]):
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"Could not read image {image_path}")
    h, w = image.shape[:2]
    if label_path.exists():
        for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            try:
                cid = int(float(parts[0]))
                xc, yc, bw, bh = [float(v) for v in parts[1:]]
            except ValueError:
                continue
            x1, y1 = int((xc - bw / 2) * w), int((yc - bh / 2) * h)
            x2, y2 = int((xc + bw / 2) * w), int((yc + bh / 2) * h)
            color = COLORS.get(cid, (255, 255, 255))
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            cv2.putText(image, names.get(cid, str(cid)), (x1, max(16, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview merged YOLO labels.")
    parser.add_argument("--split", default="train", choices=["train", "val", "test"])
    parser.add_argument("--num", type=int, default=50)
    args = parser.parse_args()
    config = load_config()
    names = {int(k): v for k, v in config["class_names"].items()}
    merged_root = PROJECT_ROOT / "data" / "yolo_merged"
    images = list_files(merged_root / "images" / args.split, image_extensions(config))
    if not images:
        raise FileNotFoundError(f"No images found in {merged_root / 'images' / args.split}")
    output_dir = ensure_dir(PROJECT_ROOT / "reports" / "previews")
    sample = random.sample(images, min(args.num, len(images)))
    for image in sample:
        output = output_dir / f"{args.split}_{image.stem}.jpg"
        cv2.imwrite(str(output), draw(image, label_for(image, merged_root, args.split), names))
        LOGGER.info("Saved %s", output)


if __name__ == "__main__":
    main()
