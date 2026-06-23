from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

from common import PROJECT_ROOT, ensure_dir, get_image_size, image_extensions, list_files, load_config, setup_logging, write_text


LOGGER = setup_logging("stats")


def main() -> None:
    config = load_config()
    names = {int(k): v for k, v in config["class_names"].items()}
    root = PROJECT_ROOT / "data" / "yolo_merged"
    stats_dir = ensure_dir(PROJECT_ROOT / "reports" / "stats")
    split_counts: dict[str, int] = {}
    class_boxes: Counter[int] = Counter()
    source_counts: Counter[str] = Counter()
    box_areas: list[float] = []
    small_count = 0
    negative_images = 0

    for split in ("train", "val", "test"):
        images = list_files(root / "images" / split, image_extensions(config))
        split_counts[split] = len(images)
        for image in images:
            source_counts[image.name.split("_", 1)[0]] += 1
            size = get_image_size(image)
            if size is None:
                continue
            w, h = size
            label = root / "labels" / split / f"{image.stem}.txt"
            lines = label.read_text(encoding="utf-8", errors="ignore").splitlines() if label.exists() else []
            if not [line for line in lines if line.strip()]:
                negative_images += 1
            for line in lines:
                parts = line.split()
                if len(parts) != 5:
                    continue
                try:
                    cid = int(float(parts[0]))
                    bw, bh = float(parts[3]), float(parts[4])
                except ValueError:
                    continue
                area_px = bw * w * bh * h
                box_areas.append(area_px)
                class_boxes[cid] += 1
                if area_px / max(1, w * h) < 0.01:
                    small_count += 1

    if box_areas:
        plt.figure(figsize=(8, 5))
        plt.hist(box_areas, bins=50)
        plt.xlabel("Box area (pixels)")
        plt.ylabel("Count")
        plt.title("YOLO Box Area Distribution")
        plt.tight_layout()
        plt.savefig(stats_dir / "box_area_distribution.png", dpi=150)
        plt.close()

    if class_boxes:
        plt.figure(figsize=(8, 5))
        labels = [names.get(k, str(k)) for k in class_boxes.keys()]
        values = [class_boxes[k] for k in class_boxes.keys()]
        plt.bar(labels, values)
        plt.ylabel("Boxes")
        plt.title("Boxes per Class")
        plt.tight_layout()
        plt.savefig(stats_dir / "boxes_per_class.png", dpi=150)
        plt.close()

    total_boxes = sum(class_boxes.values())
    lines = [
        "# Dataset Stats Report",
        "",
        "## Images Per Split",
        "",
    ]
    lines.extend(f"- `{split}`: {count}" for split, count in split_counts.items())
    lines.extend(["", "## Boxes Per Class", ""])
    lines.extend(f"- `{names.get(cid, cid)}`: {count}" for cid, count in sorted(class_boxes.items()))
    lines.extend(
        [
            "",
            "## Other Metrics",
            "",
            f"- Total boxes: {total_boxes}",
            f"- Negative images: {negative_images}",
            f"- Approximate small-object percentage: {(small_count / total_boxes * 100) if total_boxes else 0:.2f}%",
            "",
            "## Source Dataset Contribution",
            "",
        ]
    )
    lines.extend(f"- `{source}`: {count}" for source, count in source_counts.most_common())
    write_text(PROJECT_ROOT / "reports" / "stats_report.md", "\n".join(lines) + "\n")
    LOGGER.info("Stats written to reports/stats_report.md and reports/stats/")


if __name__ == "__main__":
    main()
