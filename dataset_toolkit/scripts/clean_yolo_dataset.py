from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from common import PROJECT_ROOT, clamp, file_sha256, get_image_size, image_extensions, list_files, load_config, setup_logging, write_text

try:
    import imagehash
except ImportError:
    imagehash = None


LOGGER = setup_logging("clean")


def label_for(image: Path, dataset_root: Path) -> Path:
    return dataset_root / "labels" / f"{image.stem}.txt"


def remove_pair(image: Path, dataset_root: Path) -> None:
    label = label_for(image, dataset_root)
    if image.exists():
        image.unlink()
    if label.exists():
        label.unlink()


def clean_label(label: Path, image_size: tuple[int, int], min_box_area_px: int) -> tuple[int, int]:
    if not label.exists():
        label.write_text("", encoding="utf-8")
        return 0, 0
    width, height = image_size
    fixed = 0
    removed = 0
    lines_out: list[str] = []
    for line in label.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            removed += 1
            continue
        try:
            class_id = int(float(parts[0]))
            xc, yc, bw, bh = [float(v) for v in parts[1:]]
        except ValueError:
            removed += 1
            continue
        if class_id < 0 or class_id > 4 or bw <= 0 or bh <= 0:
            removed += 1
            continue
        x1, y1 = xc - bw / 2, yc - bh / 2
        x2, y2 = xc + bw / 2, yc + bh / 2
        if x2 <= 0 or y2 <= 0 or x1 >= 1 or y1 >= 1:
            removed += 1
            continue
        tolerance = 0.02
        if x1 < -tolerance or y1 < -tolerance or x2 > 1 + tolerance or y2 > 1 + tolerance:
            removed += 1
            continue
        clamped = (clamp(x1), clamp(y1), clamp(x2), clamp(y2))
        if clamped != (x1, y1, x2, y2):
            fixed += 1
        x1, y1, x2, y2 = clamped
        bw, bh = x2 - x1, y2 - y1
        if bw * width * bh * height < min_box_area_px:
            removed += 1
            continue
        xc, yc = x1 + bw / 2, y1 + bh / 2
        lines_out.append(f"{class_id} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
    label.write_text("\n".join(lines_out) + ("\n" if lines_out else ""), encoding="utf-8")
    return fixed, removed


def clean_dataset(dataset_root: Path, config: dict) -> dict[str, int]:
    stats = {"images": 0, "corrupted": 0, "duplicates": 0, "fixed_boxes": 0, "removed_boxes": 0}
    images = list_files(dataset_root / "images", image_extensions(config))
    stats["images"] = len(images)
    seen_hashes: list[tuple[object, Path]] = []
    seen_exact: dict[str, Path] = {}
    max_distance = int(config["max_duplicate_hamming_distance"])
    if imagehash is None:
        LOGGER.warning("imagehash is not installed; falling back to exact duplicate detection. Run `pip install -r requirements.txt` for near-duplicate removal.")
    for image in images:
        size = get_image_size(image)
        if size is None:
            remove_pair(image, dataset_root)
            stats["corrupted"] += 1
            continue
        if imagehash is None:
            exact = file_sha256(image)
            duplicate_of = seen_exact.get(exact)
            if duplicate_of is None:
                seen_exact[exact] = image
        else:
            try:
                with Image.open(image) as img:
                    digest = imagehash.phash(img)
            except OSError:
                remove_pair(image, dataset_root)
                stats["corrupted"] += 1
                continue
            duplicate_of = next((old for old_hash, old in seen_hashes if digest - old_hash <= max_distance), None)
            if duplicate_of is None:
                seen_hashes.append((digest, image))
        if duplicate_of:
            LOGGER.info("Removing near duplicate %s (similar to %s)", image, duplicate_of)
            remove_pair(image, dataset_root)
            stats["duplicates"] += 1
            continue
        fixed, removed = clean_label(label_for(image, dataset_root), size, int(config["min_box_area_px"]))
        stats["fixed_boxes"] += fixed
        stats["removed_boxes"] += removed
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean individual YOLO datasets.")
    parser.add_argument("--dataset-id", help="Clean only one individual YOLO dataset.")
    args = parser.parse_args()
    config = load_config()
    base = PROJECT_ROOT / "data" / "yolo_individual"
    lines = ["# Cleaning Report", ""]
    roots = [base / args.dataset_id] if args.dataset_id else sorted(p for p in base.iterdir() if p.is_dir())
    for root in roots:
        if not (root / "images").exists():
            lines.append(f"- `{root.name}` skipped: no images folder.")
            continue
        try:
            stats = clean_dataset(root, config)
            lines.append(f"- `{root.name}`: {stats}")
        except Exception as exc:
            LOGGER.exception("Failed cleaning %s", root.name)
            lines.append(f"- `{root.name}` failed: {exc}")
    write_text(PROJECT_ROOT / "reports" / "cleaning_report.md", "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
