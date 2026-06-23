from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from project_utils import ensure_dir, image_extensions, is_number, list_images, load_config, project_path, write_text


ANNOTATION_EXTENSIONS = {".txt", ".json", ".xml", ".csv"}


def looks_like_yolo_txt(path: Path) -> bool:
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()]
    except OSError:
        return False
    nonempty = [line for line in lines if line and not line.startswith("#")]
    if not nonempty:
        return False
    checked = 0
    for line in nonempty[:10]:
        parts = line.split()
        if len(parts) != 5:
            return False
        if not parts[0].lstrip("-").isdigit() or not all(is_number(v) for v in parts[1:]):
            return False
        coords = [float(v) for v in parts[1:]]
        if not all(-0.05 <= v <= 1.05 for v in coords):
            return False
        checked += 1
    return checked > 0


def looks_like_coco_json(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and {"images", "annotations", "categories"}.issubset(data.keys())


def looks_like_voc_xml(path: Path) -> bool:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return False
    return root.find(".//object") is not None and root.find(".//bndbox") is not None


def looks_like_bbox_csv(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fields = {field.lower().strip() for field in (reader.fieldnames or [])}
    except OSError:
        return False
    filename_cols = {"filename", "file", "image", "image_path", "path"}
    bbox_cols = {"xmin", "ymin", "xmax", "ymax"} | {"x_min", "y_min", "x_max", "y_max"} | {"x", "y", "w", "h"} | {"x", "y", "width", "height"}
    return bool(fields & filename_cols) and len(fields & bbox_cols) >= 4


def detect_formats(annotation_files: list[Path]) -> dict[str, int]:
    counts = {"YOLO txt": 0, "COCO JSON": 0, "Pascal VOC XML": 0, "CSV bbox": 0, "unknown": 0}
    for path in annotation_files:
        detected = False
        if path.suffix.lower() == ".txt" and looks_like_yolo_txt(path):
            counts["YOLO txt"] += 1
            detected = True
        elif path.suffix.lower() == ".json" and looks_like_coco_json(path):
            counts["COCO JSON"] += 1
            detected = True
        elif path.suffix.lower() == ".xml" and looks_like_voc_xml(path):
            counts["Pascal VOC XML"] += 1
            detected = True
        elif path.suffix.lower() == ".csv" and looks_like_bbox_csv(path):
            counts["CSV bbox"] += 1
            detected = True
        if not detected:
            counts["unknown"] += 1
    return counts


def build_report(raw_dir: Path, processed_dir: Path, extensions: set[str]) -> str:
    images = list_images(raw_dir, extensions)
    annotation_files = sorted(
        p for p in raw_dir.rglob("*") if p.is_file() and p.suffix.lower() in ANNOTATION_EXTENSIONS
    ) if raw_dir.exists() else []
    formats = detect_formats(annotation_files)

    lines = [
        "UETT4K-Anti-UAV Dataset Inspection",
        "=" * 36,
        f"Raw directory: { raw_dir }",
        f"Images found: { len(images) }",
        f"Annotation-like files found: { len(annotation_files) }",
        "",
        "Detected annotation formats:",
    ]
    lines.extend(f"- { name }: { count }" for name, count in formats.items())
    lines.append("")
    lines.append("Sample image paths:")
    lines.extend(f"- { path }" for path in images[:10])
    lines.append("")
    lines.append("Sample annotation paths:")
    lines.extend(f"- { path }" for path in annotation_files[:20])
    report = "\n".join(lines) + "\n"

    write_text(processed_dir / "dataset_report.txt", report)
    return report


def main() -> None:
    config = load_config()
    raw_dir = project_path(config.get("full_dataset_dir", config["raw_dir"]))
    processed_dir = ensure_dir(project_path(config["processed_dir"]))
    if not raw_dir.exists() or not any(raw_dir.iterdir()):
        print(f"[inspect] Full dataset folder is missing or empty: { raw_dir }")
        print("[inspect] Run setup_dataset.py, then manually place the SharePoint dataset in that folder.")
        print("[inspect] Conversion is intentionally blocked until the actual downloaded folders are present.")
    report = build_report(raw_dir, processed_dir, image_extensions(config))
    print(report)
    print(f"[inspect] Report saved to: { processed_dir / 'dataset_report.txt' }")


if __name__ == "__main__":
    main()
