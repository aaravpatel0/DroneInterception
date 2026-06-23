from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

from common import ensure_dir, image_extensions, list_files, load_config, setup_logging, write_data_yaml


LOGGER = setup_logging("split")


def split_flat_yolo(source: Path, output: Path, config: dict) -> None:
    images = list_files(source / "images", image_extensions(config))
    rng = random.Random(int(config["random_seed"]))
    rng.shuffle(images)
    train_end = int(len(images) * float(config["train_ratio"]))
    val_end = train_end + int(len(images) * float(config["val_ratio"]))
    splits = {"train": images[:train_end], "val": images[train_end:val_end], "test": images[val_end:]}
    if output.exists():
        shutil.rmtree(output)
    for split, split_images in splits.items():
        ensure_dir(output / "images" / split)
        ensure_dir(output / "labels" / split)
        for image in split_images:
            label = source / "labels" / f"{image.stem}.txt"
            shutil.copy2(image, output / "images" / split / image.name)
            if label.exists():
                shutil.copy2(label, output / "labels" / split / label.name)
            else:
                (output / "labels" / split / label.name).write_text("", encoding="utf-8")
    write_data_yaml(output / "data.yaml", output, config["class_names"])
    LOGGER.info("Split %s into %s", source, output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Split a flat YOLO dataset into train/val/test.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    split_flat_yolo(args.source, args.output, load_config())


if __name__ == "__main__":
    main()
