from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from project_utils import clamp, ensure_dir, file_sha256, get_image_size, image_extensions, load_config, project_path, write_text


@dataclass
class CleaningSummary:
    total_images: int = 0
    removed_corrupted: int = 0
    removed_duplicates: int = 0
    fixed_labels: int = 0
    skipped_labels: int = 0
    missing_labels_created: int = 0


def yolo_image_paths(yolo_dir: Path, extensions: set[str]) -> list[Path]:
    image_root = yolo_dir / "images"
    return sorted(
        p for p in image_root.rglob("*") if p.is_file() and p.suffix.lower() in extensions
    )


def label_path_for_image(yolo_dir: Path, image_path: Path) -> Path:
    split = image_path.parent.name
    return yolo_dir / "labels" / split / f"{ image_path.stem }.txt"


def remove_pair(yolo_dir: Path, image_path: Path) -> None:
    label_path = label_path_for_image(yolo_dir, image_path)
    if image_path.exists():
        image_path.unlink()
    if label_path.exists():
        label_path.unlink()


def clean_label_file(label_path: Path) -> tuple[int, int]:
    if not label_path.exists():
        label_path.parent.mkdir(parents=True, exist_ok=True)
        label_path.write_text("", encoding="utf-8")
        return 0, 0

    fixed = 0
    skipped = 0
    cleaned_lines: list[str] = []
    for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            skipped += 1
            continue
        try:
            _, xc, yc, bw, bh = [float(value) for value in parts]
        except ValueError:
            skipped += 1
            continue
        if bw <= 0 or bh <= 0:
            skipped += 1
            continue

        x1 = xc - bw / 2
        y1 = yc - bh / 2
        x2 = xc + bw / 2
        y2 = yc + bh / 2
        if x2 <= 0 or y2 <= 0 or x1 >= 1 or y1 >= 1:
            skipped += 1
            continue

        tolerance = 0.02
        if x1 < -tolerance or y1 < -tolerance or x2 > 1 + tolerance or y2 > 1 + tolerance:
            skipped += 1
            continue

        clamped = (clamp(x1), clamp(y1), clamp(x2), clamp(y2))
        if clamped != (x1, y1, x2, y2):
            fixed += 1
        x1, y1, x2, y2 = clamped
        bw = x2 - x1
        bh = y2 - y1
        if bw <= 0 or bh <= 0:
            skipped += 1
            continue
        xc = x1 + bw / 2
        yc = y1 + bh / 2
        cleaned_lines.append(f"0 {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")

    label_path.write_text("\n".join(cleaned_lines) + ("\n" if cleaned_lines else ""), encoding="utf-8")
    return fixed, skipped


def clean_dataset(config: dict) -> CleaningSummary:
    yolo_dir = project_path(config["yolo_dir"])
    if not (yolo_dir / "data.yaml").exists():
        raise FileNotFoundError(f"YOLO data.yaml not found at { yolo_dir / 'data.yaml' }. Run merge_roboflow_datasets.py first.")

    for split in ("train", "val", "test"):
        ensure_dir(yolo_dir / "images" / split)
        ensure_dir(yolo_dir / "labels" / split)

    summary = CleaningSummary()
    seen_hashes: dict[str, Path] = {}
    images = yolo_image_paths(yolo_dir, image_extensions(config))
    summary.total_images = len(images)

    for image_path in images:
        if get_image_size(image_path) is None:
            remove_pair(yolo_dir, image_path)
            summary.removed_corrupted += 1
            continue

        digest = file_sha256(image_path)
        if digest in seen_hashes:
            print(f"[clean] Removing duplicate image: { image_path } (same as { seen_hashes[digest] })")
            remove_pair(yolo_dir, image_path)
            summary.removed_duplicates += 1
            continue
        seen_hashes[digest] = image_path

        label_path = label_path_for_image(yolo_dir, image_path)
        if not label_path.exists():
            summary.missing_labels_created += 1
        fixed, skipped = clean_label_file(label_path)
        summary.fixed_labels += fixed
        summary.skipped_labels += skipped

    processed_dir = ensure_dir(project_path(config["processed_dir"]))
    report = (
        "YOLO Dataset Cleaning Summary\n"
        "=============================\n"
        f"Total images scanned: { summary.total_images }\n"
        f"Removed corrupted images: { summary.removed_corrupted }\n"
        f"Removed duplicate images: { summary.removed_duplicates }\n"
        f"Missing label files created: { summary.missing_labels_created }\n"
        f"Fixed label boxes: { summary.fixed_labels }\n"
        f"Skipped invalid label lines: { summary.skipped_labels }\n"
    )
    write_text(processed_dir / "cleaning_report.txt", report)
    print(report)
    print(f"[clean] Report saved to: { processed_dir / 'cleaning_report.txt' }")
    return summary


def main() -> None:
    clean_dataset(load_config())


if __name__ == "__main__":
    main()
