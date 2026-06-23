from __future__ import annotations

import argparse
import csv
import json
import shutil
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from tqdm import tqdm

from common import (
    PROJECT_ROOT,
    YoloBox,
    alias_to_class_id,
    ensure_dir,
    get_image_size,
    image_extensions,
    list_files,
    load_config,
    pixels_to_yolo,
    read_manifest,
    safe_slug,
    setup_logging,
    write_data_yaml,
    write_text,
)


LOGGER = setup_logging("convert")


def image_keys(image: Path, root: Path) -> set[str]:
    keys = {image.name.lower(), image.stem.lower()}
    try:
        keys.add(image.relative_to(root).as_posix().lower())
    except ValueError:
        pass
    return keys


def image_index(images: list[Path], root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for image in images:
        for key in image_keys(image, root):
            index.setdefault(key, image)
    return index


def match_image(ref: str | None, index: dict[str, Path]) -> Path | None:
    if not ref:
        return None
    normalized = str(ref).replace("\\", "/").strip().lower()
    for candidate in (normalized, Path(normalized).name.lower(), Path(normalized).stem.lower()):
        if candidate in index:
            return index[candidate]
    return None


def parse_yolo_line(line: str, config: dict) -> YoloBox | None:
    parts = line.strip().split()
    if len(parts) < 5:
        return None
    class_id = alias_to_class_id(parts[0], config, default=0)
    if class_id is None:
        return None
    try:
        nums = [float(v) for v in parts[1:]]
    except ValueError:
        return None
    if len(nums) == 4:
        xc, yc, bw, bh = nums
    else:
        xs = nums[0::2]
        ys = nums[1::2]
        if not xs or not ys:
            return None
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        xc = (xmin + xmax) / 2
        yc = (ymin + ymax) / 2
        bw = xmax - xmin
        bh = ymax - ymin
    if bw <= 0 or bh <= 0:
        return None
    return YoloBox(class_id, xc, yc, bw, bh)


def parse_yolo_txt(raw_root: Path, images: list[Path], index: dict[str, Path], config: dict) -> dict[Path, list[YoloBox]]:
    annotations: dict[Path, list[YoloBox]] = defaultdict(list)
    for txt in list_files(raw_root, [".txt"]):
        image = match_image(txt.stem, index)
        if image is None:
            continue
        boxes = []
        for line in txt.read_text(encoding="utf-8", errors="ignore").splitlines():
            box = parse_yolo_line(line, config)
            if box:
                boxes.append(box)
        if boxes:
            annotations[image].extend(boxes)
    return annotations


def parse_voc(raw_root: Path, index: dict[str, Path], config: dict) -> dict[Path, list[YoloBox]]:
    annotations: dict[Path, list[YoloBox]] = defaultdict(list)
    for xml_path in list_files(raw_root, [".xml"]):
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError:
            continue
        image = match_image(root.findtext("filename") or xml_path.stem, index)
        if image is None:
            image = match_image(xml_path.stem, index)
        if image is None:
            continue
        size = get_image_size(image)
        if size is None:
            continue
        width, height = size
        for obj in root.findall(".//object"):
            class_id = alias_to_class_id(obj.findtext("name"), config, default=4)
            bndbox = obj.find("bndbox")
            if bndbox is None or class_id is None:
                continue
            try:
                xmin = float(bndbox.findtext("xmin", "0"))
                ymin = float(bndbox.findtext("ymin", "0"))
                xmax = float(bndbox.findtext("xmax", "0"))
                ymax = float(bndbox.findtext("ymax", "0"))
            except ValueError:
                continue
            box = pixels_to_yolo(class_id, xmin, ymin, xmax, ymax, width, height)
            if box:
                annotations[image].append(box)
    return annotations


def parse_coco(raw_root: Path, index: dict[str, Path], config: dict) -> dict[Path, list[YoloBox]]:
    annotations: dict[Path, list[YoloBox]] = defaultdict(list)
    for json_path in list_files(raw_root, [".json"]):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not {"images", "annotations"}.issubset(data):
            continue
        categories = {c.get("id"): c.get("name") for c in data.get("categories", []) if isinstance(c, dict)}
        images_by_id = {i.get("id"): i for i in data.get("images", []) if isinstance(i, dict)}
        for ann in data.get("annotations", []):
            if not isinstance(ann, dict):
                continue
            info = images_by_id.get(ann.get("image_id"))
            if not info:
                continue
            image = match_image(info.get("file_name"), index)
            if image is None:
                continue
            width = int(info.get("width") or 0)
            height = int(info.get("height") or 0)
            if not width or not height:
                size = get_image_size(image)
                if size is None:
                    continue
                width, height = size
            class_id = alias_to_class_id(categories.get(ann.get("category_id")), config, default=4)
            if class_id is None:
                continue
            if "bbox" in ann:
                try:
                    x, y, w, h = [float(v) for v in ann["bbox"][:4]]
                except (TypeError, ValueError):
                    continue
                box = pixels_to_yolo(class_id, x, y, x + w, y + h, width, height)
            elif "segmentation" in ann:
                points = ann["segmentation"][0] if ann["segmentation"] and isinstance(ann["segmentation"][0], list) else ann["segmentation"]
                xs = [float(v) for v in points[0::2]]
                ys = [float(v) for v in points[1::2]]
                box = pixels_to_yolo(class_id, min(xs), min(ys), max(xs), max(ys), width, height)
            else:
                box = None
            if box:
                annotations[image].append(box)
    return annotations


def first_existing(fields: Iterable[str], choices: Iterable[str]) -> str | None:
    by_lower = {field.lower().strip(): field for field in fields}
    for choice in choices:
        if choice in by_lower:
            return by_lower[choice]
    return None


def parse_csv_boxes(raw_root: Path, index: dict[str, Path], config: dict) -> dict[Path, list[YoloBox]]:
    annotations: dict[Path, list[YoloBox]] = defaultdict(list)
    for csv_path in list_files(raw_root, [".csv"]):
        try:
            with csv_path.open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
        except OSError:
            continue
        if not rows:
            continue
        fields = rows[0].keys()
        image_col = first_existing(fields, ["filename", "file", "image", "image_path", "path", "frame"])
        label_col = first_existing(fields, ["label", "class", "class_name", "category", "name"])
        xmin_col = first_existing(fields, ["xmin", "x_min", "left"])
        ymin_col = first_existing(fields, ["ymin", "y_min", "top"])
        xmax_col = first_existing(fields, ["xmax", "x_max", "right"])
        ymax_col = first_existing(fields, ["ymax", "y_max", "bottom"])
        x_col = first_existing(fields, ["x"])
        y_col = first_existing(fields, ["y"])
        w_col = first_existing(fields, ["w", "width"])
        h_col = first_existing(fields, ["h", "height"])
        if not image_col:
            continue
        for row in rows:
            image = match_image(row.get(image_col), index)
            if image is None:
                continue
            size = get_image_size(image)
            if size is None:
                continue
            width, height = size
            class_id = alias_to_class_id(row.get(label_col) if label_col else None, config, default=0)
            if class_id is None:
                continue
            try:
                if xmin_col and ymin_col and xmax_col and ymax_col:
                    xmin, ymin, xmax, ymax = float(row[xmin_col]), float(row[ymin_col]), float(row[xmax_col]), float(row[ymax_col])
                elif x_col and y_col and w_col and h_col:
                    x, y, w, h = float(row[x_col]), float(row[y_col]), float(row[w_col]), float(row[h_col])
                    xmin, ymin, xmax, ymax = x, y, x + w, y + h
                else:
                    continue
            except (TypeError, ValueError):
                continue
            box = pixels_to_yolo(class_id, xmin, ymin, xmax, ymax, width, height)
            if box:
                annotations[image].append(box)
    return annotations


def parse_mot(raw_root: Path, images: list[Path], config: dict) -> dict[Path, list[YoloBox]]:
    annotations: dict[Path, list[YoloBox]] = defaultdict(list)
    images_by_parent: dict[Path, list[Path]] = defaultdict(list)
    for image in images:
        images_by_parent[image.parent].append(image)
    for group in images_by_parent.values():
        group.sort()
    for txt in list_files(raw_root, [".txt"]):
        lines = [line.strip() for line in txt.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
        if not lines:
            continue
        parsed = []
        for line in lines[:2000]:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 6:
                parsed = []
                break
            try:
                frame, _track, x, y, w, h = [float(v) for v in parts[:6]]
            except ValueError:
                parsed = []
                break
            parsed.append((int(frame), x, y, w, h))
        if not parsed:
            continue
        candidates = images_by_parent.get(txt.parent) or images
        for frame, x, y, w, h in parsed:
            idx = frame - 1
            if idx < 0 or idx >= len(candidates):
                continue
            image = candidates[idx]
            size = get_image_size(image)
            if size is None:
                continue
            width, height = size
            box = pixels_to_yolo(0, x, y, x + w, y + h, width, height)
            if box:
                annotations[image].append(box)
    return annotations


def merge_sources(*sources: dict[Path, list[YoloBox]]) -> dict[Path, list[YoloBox]]:
    merged: dict[Path, list[YoloBox]] = defaultdict(list)
    seen: dict[Path, set[tuple[int, int, int, int, int]]] = defaultdict(set)
    for source in sources:
        for image, boxes in source.items():
            for box in boxes:
                key = (box.class_id, round(box.x_center, 6), round(box.y_center, 6), round(box.width, 6), round(box.height, 6))
                if key not in seen[image]:
                    seen[image].add(key)
                    merged[image].append(box)
    return merged


def is_negative_dataset(row: dict[str, str]) -> bool:
    text = " ".join([row.get("classes_available", ""), row.get("notes", ""), row.get("useful_for", "")]).lower()
    return any(word in text for word in ("negative", "background", "false positive", "invisible"))


def copy_converted(dataset_id: str, raw_root: Path, out_root: Path, images: list[Path], annotations: dict[Path, list[YoloBox]], allow_negatives: bool) -> tuple[int, int]:
    ensure_dir(out_root / "images")
    ensure_dir(out_root / "labels")
    copied = 0
    empty = 0
    for image in tqdm(images, desc=f"Converting {dataset_id}"):
        boxes = annotations.get(image, [])
        if not boxes and not allow_negatives:
            continue
        size = get_image_size(image)
        if size is None:
            continue
        try:
            rel = image.relative_to(raw_root)
        except ValueError:
            rel = Path(image.name)
        name = f"{dataset_id}_{safe_slug(str(rel.with_suffix('')))}{image.suffix.lower()}"
        dst_image = out_root / "images" / name
        dst_label = out_root / "labels" / f"{Path(name).stem}.txt"
        shutil.copy2(image, dst_image)
        if not boxes:
            empty += 1
        lines = [f"{b.class_id} {b.x_center:.6f} {b.y_center:.6f} {b.width:.6f} {b.height:.6f}" for b in boxes]
        dst_label.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        copied += 1
    return copied, empty


def convert_dataset(row: dict[str, str], config: dict) -> str:
    dataset_id = row["dataset_id"]
    raw_root = PROJECT_ROOT / row["raw_path"]
    out_root = PROJECT_ROOT / "data" / "yolo_individual" / dataset_id
    if not raw_root.exists() or not any(raw_root.iterdir()):
        return f"- `{dataset_id}` skipped: raw folder missing or empty."
    if out_root.exists():
        shutil.rmtree(out_root)
    ensure_dir(out_root)
    images = list_files(raw_root, image_extensions(config))
    valid_images = [p for p in images if get_image_size(p) is not None]
    if not valid_images:
        return f"- `{dataset_id}` skipped: no valid images found."
    index = image_index(valid_images, raw_root)
    annotations = merge_sources(
        parse_yolo_txt(raw_root, valid_images, index, config),
        parse_voc(raw_root, index, config),
        parse_coco(raw_root, index, config),
        parse_csv_boxes(raw_root, index, config),
        parse_mot(raw_root, valid_images, config),
    )
    if not annotations and not is_negative_dataset(row):
        return f"- `{dataset_id}` skipped: no compatible labels found."
    copied, empty = copy_converted(dataset_id, raw_root, out_root, valid_images, annotations, is_negative_dataset(row))
    if copied == 0:
        return f"- `{dataset_id}` skipped: conversion produced zero image/label pairs."
    write_data_yaml(out_root / "data.yaml", out_root, config["class_names"])
    return f"- `{dataset_id}` converted: {copied} images, {sum(len(v) for v in annotations.values())} boxes, {empty} empty labels."


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert raw datasets into individual YOLO datasets.")
    parser.add_argument("--dataset-id", help="Convert only one dataset id.")
    args = parser.parse_args()
    config = load_config()
    lines = ["# Conversion Report", ""]
    for row in read_manifest():
        if args.dataset_id and row["dataset_id"] != args.dataset_id:
            continue
        try:
            message = convert_dataset(row, config)
            LOGGER.info(message)
            lines.append(message)
        except Exception as exc:
            LOGGER.exception("Failed converting %s", row["dataset_id"])
            lines.append(f"- `{row['dataset_id']}` failed: {exc}")
    write_text(PROJECT_ROOT / "reports" / "conversion_report.md", "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
