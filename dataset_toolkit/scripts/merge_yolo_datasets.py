from __future__ import annotations

import random
import re
import shutil
from collections import defaultdict
from pathlib import Path

from common import PROJECT_ROOT, ensure_dir, image_extensions, list_files, load_config, setup_logging, write_data_yaml, write_text


LOGGER = setup_logging("merge")


def group_key(image: Path) -> str:
    stem = image.stem
    no_frame = re.sub(r"([_-]?(frame|img|image)?[_-]?\d{3,})$", "", stem, flags=re.IGNORECASE)
    parent = image.parent.name
    dataset = image.parents[1].name if len(image.parents) > 1 else "unknown"
    return f"{dataset}/{parent}/{no_frame or stem}"


def split_groups(images: list[Path], config: dict) -> dict[str, list[Path]]:
    rng = random.Random(int(config["random_seed"]))
    groups: dict[str, list[Path]] = defaultdict(list)
    for image in images:
        groups[group_key(image)].append(image)
    group_items = list(groups.items())
    rng.shuffle(group_items)
    total = len(group_items)
    train_end = int(total * float(config["train_ratio"]))
    val_end = train_end + int(total * float(config["val_ratio"]))
    splits = {"train": [], "val": [], "test": []}
    for idx, (_key, members) in enumerate(group_items):
        split = "train" if idx < train_end else "val" if idx < val_end else "test"
        splits[split].extend(members)
    return splits


def label_for(image: Path) -> Path:
    return image.parents[1] / "labels" / f"{image.stem}.txt"


def merge() -> None:
    config = load_config()
    individual_root = PROJECT_ROOT / "data" / "yolo_individual"
    merged_root = PROJECT_ROOT / "data" / "yolo_merged"
    if merged_root.exists():
        shutil.rmtree(merged_root)
    for split in ("train", "val", "test"):
        ensure_dir(merged_root / "images" / split)
        ensure_dir(merged_root / "labels" / split)

    all_images: list[Path] = []
    for dataset_root in sorted(p for p in individual_root.iterdir() if p.is_dir()):
        all_images.extend(list_files(dataset_root / "images", image_extensions(config)))
    if not all_images:
        message = "# Merge Report\n\n- Skipped: no converted YOLO images found. Run `python scripts/convert_to_yolo.py` after downloading or manually placing datasets.\n"
        write_text(PROJECT_ROOT / "reports" / "merge_report.md", message)
        LOGGER.warning("No converted YOLO images found; merge skipped.")
        return

    split_map = split_groups(all_images, config)
    lines = ["# Merge Report", ""]
    for split, images in split_map.items():
        for image in images:
            label = label_for(image)
            dst_image = merged_root / "images" / split / image.name
            dst_label = merged_root / "labels" / split / f"{image.stem}.txt"
            shutil.copy2(image, dst_image)
            if label.exists():
                shutil.copy2(label, dst_label)
            else:
                dst_label.write_text("", encoding="utf-8")
        lines.append(f"- `{split}`: {len(images)} images")
    write_data_yaml(merged_root / "data.yaml", merged_root, config["class_names"])
    write_text(PROJECT_ROOT / "reports" / "merge_report.md", "\n".join(lines) + "\n")
    LOGGER.info("Merged dataset written to %s", merged_root)


if __name__ == "__main__":
    merge()
