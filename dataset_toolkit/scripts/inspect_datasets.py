from __future__ import annotations

import argparse
import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from common import PROJECT_ROOT, image_extensions, list_files, load_config, read_manifest, setup_logging, video_extensions, write_text


LOGGER = setup_logging("inspect")


def is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


def looks_like_yolo_txt(path: Path) -> bool:
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
    if not lines:
        return False
    for line in lines[:20]:
        parts = line.split()
        if len(parts) < 5 or not all(is_number(v) for v in parts[:5]):
            return False
        if len(parts) > 5:
            return True
        vals = [float(v) for v in parts[1:5]]
        if not all(-0.05 <= v <= 1.05 for v in vals):
            return False
    return True


def looks_like_mot_txt(path: Path) -> bool:
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
    if not lines:
        return False
    for line in lines[:20]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6 or not all(is_number(v) for v in parts[:6]):
            return False
    return True


def looks_like_voc(path: Path) -> bool:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return False
    return root.find(".//object") is not None and root.find(".//bndbox") is not None


def looks_like_coco(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and {"images", "annotations"}.issubset(data.keys())


def looks_like_csv_boxes(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            fields = {field.lower().strip() for field in (csv.DictReader(f).fieldnames or [])}
    except OSError:
        return False
    image_cols = {"filename", "file", "image", "image_path", "path", "frame"}
    bbox_cols = {"xmin", "ymin", "xmax", "ymax", "x_min", "y_min", "x_max", "y_max", "x", "y", "w", "h", "width", "height"}
    return bool(fields & image_cols) and len(fields & bbox_cols) >= 4


def inspect_dataset(dataset_id: str, raw_path: Path, config: dict) -> dict[str, object]:
    images = list_files(raw_path, image_extensions(config))
    videos = list_files(raw_path, video_extensions(config))
    txt_files = list_files(raw_path, [".txt"])
    xml_files = list_files(raw_path, [".xml"])
    json_files = list_files(raw_path, [".json"])
    csv_files = list_files(raw_path, [".csv"])

    yolo_txt = sum(1 for p in txt_files if looks_like_yolo_txt(p))
    yolo_polygons = sum(1 for p in txt_files if looks_like_yolo_txt(p) and any(len(line.split()) > 5 for line in p.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()))
    mot_txt = sum(1 for p in txt_files if looks_like_mot_txt(p))
    voc_xml = sum(1 for p in xml_files if looks_like_voc(p))
    coco_json = sum(1 for p in json_files if looks_like_coco(p))
    csv_boxes = sum(1 for p in csv_files if looks_like_csv_boxes(p))
    formats = []
    if yolo_txt:
        formats.append("YOLO txt")
    if yolo_polygons:
        formats.append("segmentation polygons")
    if mot_txt:
        formats.append("MOT tracking txt")
    if voc_xml:
        formats.append("Pascal VOC XML")
    if coco_json:
        formats.append("COCO JSON")
    if csv_boxes:
        formats.append("CSV boxes")
    if not formats:
        formats.append("unknown")

    return {
        "dataset_id": dataset_id,
        "raw_path": str(raw_path),
        "images": len(images),
        "videos": len(videos),
        "txt_files": len(txt_files),
        "xml_files": len(xml_files),
        "json_files": len(json_files),
        "csv_files": len(csv_files),
        "detected_formats": ", ".join(formats),
        "sample_images": [str(p) for p in images[:10]],
        "sample_labels": [str(p) for p in (txt_files + xml_files + json_files + csv_files)[:20]],
    }


def write_dataset_report(result: dict[str, object]) -> None:
    lines = [
        f"# Inspection Report: {result['dataset_id']}",
        "",
        f"- Raw path: `{result['raw_path']}`",
        f"- Images: {result['images']}",
        f"- Videos: {result['videos']}",
        f"- TXT files: {result['txt_files']}",
        f"- XML files: {result['xml_files']}",
        f"- JSON files: {result['json_files']}",
        f"- CSV files: {result['csv_files']}",
        f"- Detected formats: {result['detected_formats']}",
        "",
        "## Sample Images",
        "",
    ]
    lines.extend(f"- `{p}`" for p in result["sample_images"])
    lines.extend(["", "## Sample Annotation Files", ""])
    lines.extend(f"- `{p}`" for p in result["sample_labels"])
    write_text(PROJECT_ROOT / "reports" / f"inspection_{result['dataset_id']}.md", "\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect raw datasets and detect annotation formats.")
    parser.add_argument("--dataset-id", help="Inspect only one dataset id.")
    args = parser.parse_args()
    config = load_config()
    rows = read_manifest()
    if not rows:
        raise FileNotFoundError("datasets_manifest.csv not found. Run scripts/research_datasets.py first.")
    summary_lines = ["# Dataset Inspection Summary", ""]
    for row in rows:
        dataset_id = row["dataset_id"]
        if args.dataset_id and dataset_id != args.dataset_id:
            continue
        raw_path = PROJECT_ROOT / row["raw_path"]
        if not raw_path.exists() or not any(raw_path.iterdir()):
            LOGGER.info("Skipping %s: raw folder not present or empty", dataset_id)
            summary_lines.append(f"- `{dataset_id}`: skipped, raw folder missing or empty.")
            continue
        try:
            result = inspect_dataset(dataset_id, raw_path, config)
            write_dataset_report(result)
            summary_lines.append(f"- `{dataset_id}`: {result['images']} images, {result['videos']} videos, formats: {result['detected_formats']}.")
            LOGGER.info("Inspected %s", dataset_id)
        except Exception as exc:
            LOGGER.exception("Failed to inspect %s", dataset_id)
            summary_lines.append(f"- `{dataset_id}`: failed, {exc}.")
    write_text(PROJECT_ROOT / "reports" / "inspection_summary.md", "\n".join(summary_lines) + "\n")


if __name__ == "__main__":
    main()
