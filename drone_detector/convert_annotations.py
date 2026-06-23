from __future__ import annotations

import csv
import json
import random
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml
from tqdm import tqdm

from inspect_dataset import looks_like_yolo_txt
from project_utils import (
    drone_label_like,
    ensure_dir,
    get_image_size,
    image_extensions,
    list_images,
    load_config,
    project_path,
)


@dataclass(frozen=True)
class YoloBox:
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float


def image_reference_keys(path: Path, raw_dir: Path) -> set[str]:
    keys = {path.name.lower(), path.stem.lower()}
    try:
        keys.add(path.relative_to(raw_dir).as_posix().lower())
    except ValueError:
        pass
    return keys


def build_image_index(images: list[Path], raw_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for image in images:
        for key in image_reference_keys(image, raw_dir):
            index.setdefault(key, image)
    return index


def match_image(ref: str | None, image_index: dict[str, Path]) -> Path | None:
    if not ref:
        return None
    normalized = ref.replace("\\", "/").lower().strip()
    candidates = [normalized, Path(normalized).name.lower(), Path(normalized).stem.lower()]
    for candidate in candidates:
        if candidate in image_index:
            return image_index[candidate]
    return None


def bbox_pixels_to_yolo(
    xmin: float, ymin: float, xmax: float, ymax: float, image_width: int, image_height: int
) -> YoloBox | None:
    xmin = max(0.0, min(float(image_width), xmin))
    ymin = max(0.0, min(float(image_height), ymin))
    xmax = max(0.0, min(float(image_width), xmax))
    ymax = max(0.0, min(float(image_height), ymax))
    if xmax <= xmin or ymax <= ymin:
        return None
    box_width = xmax - xmin
    box_height = ymax - ymin
    return YoloBox(
        class_id=0,
        x_center=(xmin + box_width / 2) / image_width,
        y_center=(ymin + box_height / 2) / image_height,
        width=box_width / image_width,
        height=box_height / image_height,
    )


def parse_yolo_txt(path: Path) -> list[YoloBox]:
    boxes: list[YoloBox] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 5:
            print(f"[convert] Skipping malformed YOLO line { path }:{ line_no }")
            continue
        try:
            _, xc, yc, bw, bh = [float(value) for value in parts]
        except ValueError:
            print(f"[convert] Skipping non-numeric YOLO line { path }:{ line_no }")
            continue
        if bw <= 0 or bh <= 0:
            continue
        boxes.append(YoloBox(0, xc, yc, bw, bh))
    return boxes


def parse_yolo_annotations(raw_dir: Path, image_index: dict[str, Path]) -> dict[Path, list[YoloBox]]:
    annotations: dict[Path, list[YoloBox]] = defaultdict(list)
    txt_files = sorted(p for p in raw_dir.rglob("*.txt") if p.is_file())
    for txt in txt_files:
        if not looks_like_yolo_txt(txt):
            continue
        image = match_image(txt.stem, image_index)
        if image is None:
            continue
        annotations[image].extend(parse_yolo_txt(txt))
    return annotations


def parse_voc_annotations(raw_dir: Path, image_index: dict[str, Path]) -> dict[Path, list[YoloBox]]:
    annotations: dict[Path, list[YoloBox]] = defaultdict(list)
    for xml_path in sorted(raw_dir.rglob("*.xml")):
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError:
            continue
        filename = root.findtext("filename") or xml_path.stem
        image = match_image(filename, image_index) or match_image(xml_path.stem, image_index)
        if image is None:
            continue
        size = get_image_size(image)
        if size is None:
            continue
        image_width, image_height = size
        for obj in root.findall(".//object"):
            label = obj.findtext("name")
            if not drone_label_like(label):
                continue
            bndbox = obj.find("bndbox")
            if bndbox is None:
                continue
            try:
                xmin = float(bndbox.findtext("xmin", "0"))
                ymin = float(bndbox.findtext("ymin", "0"))
                xmax = float(bndbox.findtext("xmax", "0"))
                ymax = float(bndbox.findtext("ymax", "0"))
            except ValueError:
                continue
            box = bbox_pixels_to_yolo(xmin, ymin, xmax, ymax, image_width, image_height)
            if box:
                annotations[image].append(box)
    return annotations


def parse_coco_annotations(raw_dir: Path, image_index: dict[str, Path]) -> dict[Path, list[YoloBox]]:
    annotations: dict[Path, list[YoloBox]] = defaultdict(list)
    for json_path in sorted(raw_dir.rglob("*.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not {"images", "annotations"}.issubset(data.keys()):
            continue
        categories = {
            item.get("id"): str(item.get("name", ""))
            for item in data.get("categories", [])
            if isinstance(item, dict)
        }
        images_by_id = {
            item.get("id"): item
            for item in data.get("images", [])
            if isinstance(item, dict) and item.get("id") is not None
        }
        for ann in data.get("annotations", []):
            if not isinstance(ann, dict) or "bbox" not in ann:
                continue
            label = categories.get(ann.get("category_id"), "")
            if categories and not drone_label_like(label):
                continue
            image_info = images_by_id.get(ann.get("image_id"))
            if not image_info:
                continue
            image = match_image(str(image_info.get("file_name", "")), image_index)
            if image is None:
                continue
            width = int(image_info.get("width") or 0)
            height = int(image_info.get("height") or 0)
            if not width or not height:
                size = get_image_size(image)
                if size is None:
                    continue
                width, height = size
            try:
                x, y, w, h = [float(v) for v in ann["bbox"][:4]]
            except (TypeError, ValueError):
                continue
            box = bbox_pixels_to_yolo(x, y, x + w, y + h, width, height)
            if box:
                annotations[image].append(box)
    return annotations


def first_existing(fields: Iterable[str], choices: Iterable[str]) -> str | None:
    lowered = {field.lower().strip(): field for field in fields}
    for choice in choices:
        if choice in lowered:
            return lowered[choice]
    return None


def parse_csv_annotations(raw_dir: Path, image_index: dict[str, Path]) -> dict[Path, list[YoloBox]]:
    annotations: dict[Path, list[YoloBox]] = defaultdict(list)
    for csv_path in sorted(raw_dir.rglob("*.csv")):
        try:
            rows = list(csv.DictReader(csv_path.open("r", encoding="utf-8", newline="")))
        except OSError:
            continue
        if not rows:
            continue
        fields = rows[0].keys()
        image_col = first_existing(fields, ["filename", "file", "image", "image_path", "path"])
        label_col = first_existing(fields, ["label", "class", "class_name", "category", "name"])
        xmin_col = first_existing(fields, ["xmin", "x_min", "left"])
        ymin_col = first_existing(fields, ["ymin", "y_min", "top"])
        xmax_col = first_existing(fields, ["xmax", "x_max", "right"])
        ymax_col = first_existing(fields, ["ymax", "y_max", "bottom"])
        x_col = first_existing(fields, ["x"])
        y_col = first_existing(fields, ["y"])
        w_col = first_existing(fields, ["w", "width"])
        h_col = first_existing(fields, ["h", "height"])
        if image_col is None:
            continue
        for row in rows:
            if label_col and not drone_label_like(row.get(label_col)):
                continue
            image = match_image(row.get(image_col), image_index)
            if image is None:
                continue
            size = get_image_size(image)
            if size is None:
                continue
            image_width, image_height = size
            try:
                if xmin_col and ymin_col and xmax_col and ymax_col:
                    xmin = float(row[xmin_col])
                    ymin = float(row[ymin_col])
                    xmax = float(row[xmax_col])
                    ymax = float(row[ymax_col])
                elif x_col and y_col and w_col and h_col:
                    x = float(row[x_col])
                    y = float(row[y_col])
                    w = float(row[w_col])
                    h = float(row[h_col])
                    xmin, ymin, xmax, ymax = x, y, x + w, y + h
                else:
                    continue
            except (TypeError, ValueError):
                continue
            box = bbox_pixels_to_yolo(xmin, ymin, xmax, ymax, image_width, image_height)
            if box:
                annotations[image].append(box)
    return annotations


def merge_annotations(*sources: dict[Path, list[YoloBox]]) -> dict[Path, list[YoloBox]]:
    merged: dict[Path, list[YoloBox]] = defaultdict(list)
    seen: dict[Path, set[tuple[int, int, int, int, int]]] = defaultdict(set)
    for source in sources:
        for image, boxes in source.items():
            for box in boxes:
                signature = (
                    box.class_id,
                    round(box.x_center, 6),
                    round(box.y_center, 6),
                    round(box.width, 6),
                    round(box.height, 6),
                )
                if signature not in seen[image]:
                    merged[image].append(box)
                    seen[image].add(signature)
    return merged


def split_images(images: list[Path], train_ratio: float, val_ratio: float, test_ratio: float, seed: int) -> dict[str, list[Path]]:
    total = train_ratio + val_ratio + test_ratio
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Split ratios must sum to 1.0, got { total }")
    shuffled = images[:]
    random.Random(seed).shuffle(shuffled)
    train_end = int(len(shuffled) * train_ratio)
    val_end = train_end + int(len(shuffled) * val_ratio)
    return {
        "train": shuffled[:train_end],
        "val": shuffled[train_end:val_end],
        "test": shuffled[val_end:],
    }


def reset_yolo_dir(yolo_dir: Path) -> None:
    if yolo_dir.exists():
        shutil.rmtree(yolo_dir)
    for split in ("train", "val", "test"):
        ensure_dir(yolo_dir / "images" / split)
        ensure_dir(yolo_dir / "labels" / split)


def write_label_file(path: Path, boxes: list[YoloBox]) -> None:
    lines = [
        f"{ box.class_id } { box.x_center:.6f } { box.y_center:.6f } { box.width:.6f } { box.height:.6f }"
        for box in boxes
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def convert_dataset(config: dict) -> None:
    raw_dir = project_path(config.get("full_dataset_dir", config["raw_dir"]))
    yolo_dir = project_path(config["yolo_dir"])
    if not raw_dir.exists():
        raise FileNotFoundError(f"Full dataset folder not found: { raw_dir }. Run setup_dataset.py first.")
    if not any(raw_dir.iterdir()):
        raise RuntimeError(
            f"Full dataset folder is empty: { raw_dir }. "
            "Download the SharePoint dataset manually and place/extract it there before conversion."
        )

    images = list_images(raw_dir, image_extensions(config))
    valid_images = [image for image in images if get_image_size(image) is not None]
    skipped_corrupted = len(images) - len(valid_images)
    if not valid_images:
        raise RuntimeError(f"No valid images found under { raw_dir }")

    image_index = build_image_index(valid_images, raw_dir)
    yolo = parse_yolo_annotations(raw_dir, image_index)
    voc = parse_voc_annotations(raw_dir, image_index)
    coco = parse_coco_annotations(raw_dir, image_index)
    csv_boxes = parse_csv_annotations(raw_dir, image_index)
    annotations = merge_annotations(yolo, voc, coco, csv_boxes)

    format_counts = {
        "YOLO txt images": len(yolo),
        "Pascal VOC images": len(voc),
        "COCO images": len(coco),
        "CSV images": len(csv_boxes),
    }
    print("[convert] Annotation sources detected:")
    for name, count in format_counts.items():
        print(f"[convert]   { name }: { count }")

    if not annotations:
        found = sorted(p.suffix.lower() for p in raw_dir.rglob("*") if p.is_file())
        unique_suffixes = ", ".join(sorted(set(found))[:30])
        raise RuntimeError(
            "No supported annotations could be matched to images. "
            f"Found file suffixes include: { unique_suffixes or 'none' }. "
            "Run inspect_dataset.py and check whether annotations use a custom format."
        )

    reset_yolo_dir(yolo_dir)
    splits = split_images(
        valid_images,
        float(config["train_ratio"]),
        float(config["val_ratio"]),
        float(config["test_ratio"]),
        int(config.get("random_seed", 42)),
    )

    copied = 0
    empty_labels = 0
    for split, split_images_list in splits.items():
        for image in tqdm(split_images_list, desc=f"Writing { split } split"):
            destination_image = yolo_dir / "images" / split / image.name
            destination_label = yolo_dir / "labels" / split / f"{ image.stem }.txt"
            shutil.copy2(image, destination_image)
            boxes = annotations.get(image, [])
            if not boxes:
                empty_labels += 1
            write_label_file(destination_label, boxes)
            copied += 1

    data_yaml = {
        "path": str(yolo_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {0: "drone"},
    }
    with (yolo_dir / "data.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(data_yaml, f, sort_keys=False)

    print(f"[convert] Valid images copied: { copied }")
    print(f"[convert] Corrupted images skipped: { skipped_corrupted }")
    print(f"[convert] Empty label files created: { empty_labels }")
    print(f"[convert] YOLO dataset ready: { yolo_dir }")
    print(f"[convert] data.yaml written: { yolo_dir / 'data.yaml' }")


def main() -> None:
    try:
        convert_dataset(load_config())
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"[convert] { exc }")
        sys.exit(1)


if __name__ == "__main__":
    main()
