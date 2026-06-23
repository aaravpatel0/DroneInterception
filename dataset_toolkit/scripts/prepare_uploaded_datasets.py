from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import cv2
from PIL import Image
from tqdm import tqdm

from common import PROJECT_ROOT, ensure_dir, load_config, setup_logging, write_data_yaml, write_text


LOGGER = setup_logging("prepare_uploaded")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def reset_dataset(dataset_id: str) -> Path:
    out_root = yolo_individual_root() / dataset_id
    if out_root.exists():
        shutil.rmtree(out_root)
    ensure_dir(out_root / "images")
    ensure_dir(out_root / "labels")
    return out_root


def hub_root() -> Path:
    if (PROJECT_ROOT / "dataset_toolkit").exists():
        return PROJECT_ROOT / "dataset_toolkit"
    return PROJECT_ROOT


def yolo_individual_root() -> Path:
    return hub_root() / "data" / "yolo_individual"


def reports_root() -> Path:
    return hub_root() / "reports"


def first_existing_path(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def yolo_box_from_xywh(x: float, y: float, w: float, h: float, image_w: int, image_h: int) -> str | None:
    if w <= 0 or h <= 0:
        return None
    x1 = max(0.0, min(float(image_w), x))
    y1 = max(0.0, min(float(image_h), y))
    x2 = max(0.0, min(float(image_w), x + w))
    y2 = max(0.0, min(float(image_h), y + h))
    if x2 <= x1 or y2 <= y1:
        return None
    bw = x2 - x1
    bh = y2 - y1
    xc = x1 + bw / 2
    yc = y1 + bh / 2
    return f"0 {xc / image_w:.6f} {yc / image_h:.6f} {bw / image_w:.6f} {bh / image_h:.6f}"


def yolo_line_to_box(line: str, class_override: int | None = None) -> str | None:
    parts = line.strip().split()
    if len(parts) < 5:
        return None
    try:
        class_id = int(float(parts[0])) if class_override is None else class_override
        coords = [float(v) for v in parts[1:]]
    except ValueError:
        return None
    if len(coords) == 4:
        xc, yc, bw, bh = coords
    else:
        xs = coords[0::2]
        ys = coords[1::2]
        if not xs or not ys:
            return None
        x1, x2 = max(0.0, min(xs)), min(1.0, max(xs))
        y1, y2 = max(0.0, min(ys)), min(1.0, max(ys))
        bw = x2 - x1
        bh = y2 - y1
        xc = x1 + bw / 2
        yc = y1 + bh / 2
    if class_id not in {0, 1, 2, 3, 4} or bw <= 0 or bh <= 0:
        return None
    return f"{class_id} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}"


def write_output_pair(out_root: Path, name: str, image_source: Path | None, image_data, label_lines: list[str]) -> None:
    image_out = out_root / "images" / f"{name}.jpg"
    label_out = out_root / "labels" / f"{name}.txt"
    if image_source is not None:
        shutil.copy2(image_source, image_out)
    else:
        cv2.imwrite(str(image_out), image_data)
    label_out.write_text("\n".join(label_lines) + ("\n" if label_lines else ""), encoding="utf-8")


def prepare_bird_vs_drone(source_root: Path, config: dict, max_items: int | None = None) -> str:
    dataset_root = source_root / "Dataset"
    if not dataset_root.exists():
        return "- `uploaded_bird_vs_drone` skipped: expected `Bird vs Drone/Dataset`."
    out_root = yolo_individual_root() / "uploaded_bird_vs_drone"
    if out_root.exists():
        shutil.rmtree(out_root)
    ensure_dir(out_root / "images")
    ensure_dir(out_root / "labels")

    copied = 0
    boxes = 0
    for split in ("train", "valid", "val", "test"):
        images_dir = dataset_root / split / "images"
        labels_dir = dataset_root / split / "labels"
        if not images_dir.exists() or not labels_dir.exists():
            continue
        for image in tqdm(sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS), desc=f"Bird vs Drone {split}"):
            if max_items is not None and copied >= max_items:
                break
            label = labels_dir / f"{image.stem}.txt"
            out_name = f"uploaded_bird_vs_drone_{split}_{image.stem}".replace(" ", "_")
            lines: list[str] = []
            if label.exists():
                for raw_line in label.read_text(encoding="utf-8", errors="ignore").splitlines():
                    converted = yolo_line_to_box(raw_line)
                    if converted:
                        lines.append(converted)
            boxes += len(lines)
            write_output_pair(out_root, out_name, image, None, lines)
            copied += 1
        if max_items is not None and copied >= max_items:
            break
    write_data_yaml(out_root / "data.yaml", out_root, config["class_names"])
    return f"- `uploaded_bird_vs_drone`: converted {copied} images and {boxes} boxes."


def prepare_dut(source_root: Path, config: dict, max_items: int | None = None) -> str:
    images_base = source_root / "Anti-UAV-Tracking-V0" / "Anti-UAV-Tracking-V0"
    labels_base = source_root / "Anti-UAV-Tracking-V0GT" / "Anti-UAV-Tracking-V0GT"
    if not images_base.exists() or not labels_base.exists():
        return "- `uploaded_dut_anti_uav`: skipped: expected DUT image and GT folders."
    out_root = yolo_individual_root() / "uploaded_dut_anti_uav"
    if out_root.exists():
        shutil.rmtree(out_root)
    ensure_dir(out_root / "images")
    ensure_dir(out_root / "labels")

    copied = 0
    boxes = 0
    for video_dir in tqdm(sorted(p for p in images_base.iterdir() if p.is_dir()), desc="DUT videos"):
        gt_path = labels_base / f"{video_dir.name}_gt.txt"
        if not gt_path.exists():
            continue
        gt_lines = [line.strip() for line in gt_path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
        frame_paths = sorted(p for p in video_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
        for idx, image in enumerate(frame_paths):
            if max_items is not None and copied >= max_items:
                break
            if idx >= len(gt_lines):
                break
            try:
                x, y, w, h = [float(v) for v in gt_lines[idx].replace(",", " ").split()[:4]]
            except ValueError:
                continue
            with Image.open(image) as im:
                image_w, image_h = im.size
            label = yolo_box_from_xywh(x, y, w, h, image_w, image_h)
            out_name = f"uploaded_dut_anti_uav_{video_dir.name}_{image.stem}"
            write_output_pair(out_root, out_name, image, None, [label] if label else [])
            copied += 1
            boxes += 1 if label else 0
        if max_items is not None and copied >= max_items:
            break
    write_data_yaml(out_root / "data.yaml", out_root, config["class_names"])
    return f"- `uploaded_dut_anti_uav`: converted {copied} frames and {boxes} boxes."


def prepare_anti_uav_300(source_root: Path, config: dict, frame_stride: int, modality: str, max_items: int | None = None) -> str:
    if not source_root.exists():
        return "- `uploaded_anti_uav_300`: skipped: folder not found."
    out_root = yolo_individual_root() / "uploaded_anti_uav_300"
    if out_root.exists():
        shutil.rmtree(out_root)
    ensure_dir(out_root / "images")
    ensure_dir(out_root / "labels")

    copied = 0
    boxes = 0
    json_files = sorted(source_root.rglob(f"{modality}.json"))
    for ann_path in tqdm(json_files, desc=f"Anti-UAV {modality} sequences"):
        video_path = ann_path.with_suffix(".mp4")
        if not video_path.exists():
            continue
        data = json.loads(ann_path.read_text(encoding="utf-8"))
        exists = data.get("exist", [])
        rects = data.get("gt_rect", [])
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            LOGGER.warning("Could not open video %s", video_path)
            continue
        frame_idx = 0
        sequence_id = ann_path.parent.name
        while True:
            if max_items is not None and copied >= max_items:
                break
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx < len(exists) and frame_idx < len(rects) and frame_idx % frame_stride == 0:
                image_h, image_w = frame.shape[:2]
                label = None
                if int(exists[frame_idx]) == 1:
                    try:
                        x, y, w, h = [float(v) for v in rects[frame_idx][:4]]
                        label = yolo_box_from_xywh(x, y, w, h, image_w, image_h)
                    except (TypeError, ValueError):
                        label = None
                out_name = f"uploaded_anti_uav_300_{modality}_{sequence_id}_{frame_idx + 1:06d}"
                write_output_pair(out_root, out_name, None, frame, [label] if label else [])
                copied += 1
                boxes += 1 if label else 0
            frame_idx += 1
        cap.release()
        if max_items is not None and copied >= max_items:
            break
    write_data_yaml(out_root / "data.yaml", out_root, config["class_names"])
    return f"- `uploaded_anti_uav_300`: extracted {copied} {modality} frames at stride {frame_stride} and {boxes} boxes."


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert uploaded root-level datasets into YOLO individual datasets.")
    parser.add_argument("--frame-stride", type=int, default=10, help="Extract every Nth Anti-UAV video frame.")
    parser.add_argument("--anti-modality", choices=["visible", "infrared"], default="visible", help="Video stream to use for anti_uav_dataset_300.")
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=["bird_vs_drone", "dut", "anti_uav_300"],
        default=["bird_vs_drone", "dut", "anti_uav_300"],
        help="Subset of uploaded datasets to prepare.",
    )
    parser.add_argument("--max-items", type=int, help="Optional per-dataset item limit for quick pipeline tests.")
    args = parser.parse_args()
    config = load_config()
    root = hub_root().parent
    raw_root = hub_root() / "data" / "raw"
    lines = ["# Uploaded Dataset Preparation Report", ""]
    report_path = reports_root() / "uploaded_dataset_preparation_report.md"
    write_text(report_path, "\n".join(lines) + "\n")
    if "bird_vs_drone" in args.datasets:
        lines.append(prepare_bird_vs_drone(first_existing_path(raw_root / "bird_vs_drone", root / "Bird vs Drone"), config, args.max_items))
        write_text(report_path, "\n".join(lines) + "\n")
    if "dut" in args.datasets:
        lines.append(prepare_dut(first_existing_path(raw_root / "dut_anti_uav", root / "DUT Anti-UAV"), config, args.max_items))
        write_text(report_path, "\n".join(lines) + "\n")
    if "anti_uav_300" in args.datasets:
        lines.append(prepare_anti_uav_300(first_existing_path(raw_root / "anti_uav_dataset_300", root / "anti_uav_dataset_300"), config, max(1, args.frame_stride), args.anti_modality, args.max_items))
        write_text(report_path, "\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
