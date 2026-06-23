from __future__ import annotations

import random
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from utils import ensure_dir, file_sha256, get_image_size, image_extensions, load_config, project_path, write_text


SPLITS = ("train", "val", "test")
SOURCE_SPLITS = ("train", "valid", "val", "test")


@dataclass(frozen=True)
class SourcePair:
    dataset_name: str
    image_path: Path
    label_path: Path | None
    image_hash: str


@dataclass
class DatasetStats:
    source: Path
    classes: list[str] = field(default_factory=list)
    images_found: int = 0
    labels_found: int = 0
    images_copied: dict[str, int] = field(default_factory=lambda: {split: 0 for split in SPLITS})
    labels_copied: int = 0
    missing_labels_fixed: int = 0
    invalid_labels_skipped: int = 0
    corrupted_images_skipped: int = 0
    duplicates_removed: int = 0


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "image"


def expected_structure() -> str:
    return (
        "Expected Roboflow YOLOv8 folders:\n"
        "data/roboflow_raw/<dataset-name>/\n"
        "or data/<dataset-name>/\n"
        "Each folder may contain train/, valid/, val/, or test/ images and labels.\n"
    )


def load_dataset_yaml(dataset_dir: Path) -> dict[str, Any]:
    data_yaml = dataset_dir / "data.yaml"
    if not data_yaml.exists():
        return {}
    with data_yaml.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def parse_class_names(data: dict[str, Any]) -> list[str]:
    names = data.get("names", [])
    if isinstance(names, dict):
        return [str(names[key]) for key in sorted(names, key=lambda item: int(item) if str(item).isdigit() else str(item))]
    if isinstance(names, list):
        return [str(name) for name in names]
    return []


def search_roots(config: dict[str, Any]) -> list[Path]:
    roots = [
        project_path(config.get("roboflow_raw_dir", "data/roboflow_raw")),
        project_path("data"),
        project_path("."),
    ]
    unique: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved.exists() and resolved not in unique:
            unique.append(resolved)
    return unique


def find_dataset_dir(name: str, config: dict[str, Any]) -> Path | None:
    raw_dir = project_path(config.get("roboflow_raw_dir", "data/roboflow_raw"))
    direct_names = (name, f"{name}.yolov8")
    for direct_name in direct_names:
        direct = raw_dir / direct_name
        if direct.exists() and direct.is_dir():
            return direct.resolve()

    for root in search_roots(config):
        try:
            matches = [
                p for p in root.rglob("*")
                if p.is_dir() and p.name.lower() in {candidate.lower() for candidate in direct_names}
            ]
        except OSError:
            matches = []
        if matches:
            return sorted(matches, key=lambda p: len(str(p)))[0].resolve()
    return None


def labels_by_stem(dataset_dir: Path) -> dict[str, list[Path]]:
    labels: dict[str, list[Path]] = {}
    for label_path in sorted(dataset_dir.rglob("*.txt")):
        if label_path.name.lower().startswith("readme"):
            continue
        labels.setdefault(label_path.stem, []).append(label_path)
    return labels


def matching_label_path(image_path: Path, label_index: dict[str, list[Path]]) -> Path | None:
    parts = list(image_path.parts)
    for index, part in enumerate(parts):
        if part.lower() == "images":
            candidate = Path(*parts[:index], "labels", *parts[index + 1 :]).with_suffix(".txt")
            if candidate.exists():
                return candidate
    matches = label_index.get(image_path.stem, [])
    return matches[0] if matches else None


def list_dataset_images(dataset_dir: Path, extensions: set[str]) -> list[Path]:
    return sorted(path for path in dataset_dir.rglob("*") if path.is_file() and path.suffix.lower() in extensions)


def collect_pairs(dataset_name: str, dataset_dir: Path, extensions: set[str]) -> list[SourcePair]:
    label_index = labels_by_stem(dataset_dir)
    return [
        SourcePair(dataset_name, image_path, matching_label_path(image_path, label_index), "")
        for image_path in list_dataset_images(dataset_dir, extensions)
    ]


def validate_label_line(line: str) -> tuple[bool, str]:
    parts = line.strip().split()
    if len(parts) != 5:
        return False, ""
    try:
        float(parts[0])
        xc, yc, width, height = [float(value) for value in parts[1:]]
    except ValueError:
        return False, ""
    if not (0 <= xc <= 1 and 0 <= yc <= 1 and 0 < width <= 1 and 0 < height <= 1):
        return False, ""
    return True, f"0 {xc:.6f} {yc:.6f} {width:.6f} {height:.6f}"


def normalized_label_text(pair: SourcePair, stats: DatasetStats) -> str:
    if pair.label_path is None or not pair.label_path.exists():
        stats.missing_labels_fixed += 1
        return ""

    valid_lines: list[str] = []
    for raw_line in pair.label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not raw_line.strip():
            continue
        ok, normalized = validate_label_line(raw_line)
        if ok:
            valid_lines.append(normalized)
        else:
            stats.invalid_labels_skipped += 1
    stats.labels_copied += 1
    return "\n".join(valid_lines) + ("\n" if valid_lines else "")


def clear_yolo_dir(yolo_dir: Path) -> None:
    ensure_dir(yolo_dir)
    project_root = project_path(".").resolve()
    resolved = yolo_dir.resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise RuntimeError(f"Refusing to clear YOLO directory outside project: {resolved}") from exc
    for child in yolo_dir.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def prepare_yolo_dirs(yolo_dir: Path) -> None:
    clear_yolo_dir(yolo_dir)
    for split in SPLITS:
        ensure_dir(yolo_dir / "images" / split)
        ensure_dir(yolo_dir / "labels" / split)


def collect_unique_pairs(dataset_dirs: dict[str, Path], config: dict[str, Any], stats_by_name: dict[str, DatasetStats]) -> list[SourcePair]:
    extensions = image_extensions(config) or {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    seen_hashes: set[str] = set()
    pairs: list[SourcePair] = []

    for dataset_name, dataset_dir in dataset_dirs.items():
        data_yaml = load_dataset_yaml(dataset_dir)
        label_index = labels_by_stem(dataset_dir)
        images = list_dataset_images(dataset_dir, extensions)
        stats = DatasetStats(
            source=dataset_dir,
            classes=parse_class_names(data_yaml),
            images_found=len(images),
            labels_found=sum(len(paths) for paths in label_index.values()),
        )
        stats_by_name[dataset_name] = stats

        for image_path in images:
            if get_image_size(image_path) is None:
                stats.corrupted_images_skipped += 1
                continue
            image_hash = file_sha256(image_path)
            if image_hash in seen_hashes:
                stats.duplicates_removed += 1
                continue
            seen_hashes.add(image_hash)
            pairs.append(SourcePair(dataset_name, image_path, matching_label_path(image_path, label_index), image_hash))

    return pairs


def split_pairs(pairs: list[SourcePair], config: dict[str, Any]) -> dict[str, list[SourcePair]]:
    shuffled = list(pairs)
    random.Random(int(config.get("random_seed", 42))).shuffle(shuffled)
    train_ratio = float(config.get("train_ratio", 0.70))
    val_ratio = float(config.get("val_ratio", 0.15))
    train_count = int(len(shuffled) * train_ratio)
    val_count = int(len(shuffled) * val_ratio)
    return {
        "train": shuffled[:train_count],
        "val": shuffled[train_count : train_count + val_count],
        "test": shuffled[train_count + val_count :],
    }


def unique_output_stem(pair: SourcePair, used_stems: set[str]) -> str:
    base = safe_name(f"{pair.dataset_name}_{pair.image_path.stem}")
    stem = base
    if stem in used_stems:
        stem = f"{base}_{pair.image_hash[:8]}"
    counter = 2
    while stem in used_stems:
        stem = f"{base}_{pair.image_hash[:8]}_{counter}"
        counter += 1
    used_stems.add(stem)
    return stem


def copy_pair(pair: SourcePair, split: str, yolo_dir: Path, stats: DatasetStats, used_stems: set[str]) -> None:
    new_stem = unique_output_stem(pair, used_stems)
    new_image = yolo_dir / "images" / split / f"{new_stem}{pair.image_path.suffix.lower()}"
    new_label = yolo_dir / "labels" / split / f"{new_stem}.txt"
    shutil.copy2(pair.image_path, new_image)
    write_text(new_label, normalized_label_text(pair, stats))
    stats.images_copied[split] += 1


def write_data_yaml(yolo_dir: Path) -> None:
    try:
        yolo_path = yolo_dir.resolve().relative_to(project_path(".").resolve()).as_posix()
    except ValueError:
        yolo_path = str(yolo_dir.resolve())
    data = {
        "path": yolo_path,
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {0: "drone"},
    }
    with (yolo_dir / "data.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def build_report(stats_by_name: dict[str, DatasetStats], yolo_dir: Path, config: dict[str, Any]) -> str:
    totals = {
        "images_found": 0,
        "labels_found": 0,
        "duplicates_removed": 0,
        "corrupted_images_skipped": 0,
        "missing_labels_fixed": 0,
        "invalid_labels_skipped": 0,
    }
    split_counts = {split: 0 for split in SPLITS}
    lines = [
        "Roboflow YOLOv8 Merge Report",
        "============================",
        "",
        "Split strategy: pooled all valid, non-duplicate images and split 70/15/15",
        f"Random seed: {int(config.get('random_seed', 42))}",
        "",
        "Datasets found:",
    ]
    for name, stats in stats_by_name.items():
        lines.append(f"- {name}: {stats.source}")
        lines.append(f"  Original class names: {stats.classes or ['<none>']}")
        lines.append(f"  Images found: {stats.images_found}")
        lines.append(f"  Label txt files found: {stats.labels_found}")
        lines.append(f"  Duplicates removed: {stats.duplicates_removed}")
        lines.append(f"  Corrupted images skipped: {stats.corrupted_images_skipped}")
        lines.append(f"  Missing labels converted to empty labels: {stats.missing_labels_fixed}")
        lines.append(f"  Invalid label lines skipped: {stats.invalid_labels_skipped}")
        for split in SPLITS:
            lines.append(f"  {split} images copied: {stats.images_copied[split]}")
            split_counts[split] += stats.images_copied[split]
        totals["images_found"] += stats.images_found
        totals["labels_found"] += stats.labels_found
        totals["duplicates_removed"] += stats.duplicates_removed
        totals["corrupted_images_skipped"] += stats.corrupted_images_skipped
        totals["missing_labels_fixed"] += stats.missing_labels_fixed
        totals["invalid_labels_skipped"] += stats.invalid_labels_skipped

    lines.extend(
        [
            "",
            "Totals:",
            f"- images found before merging: {totals['images_found']}",
            f"- labels found before merging: {totals['labels_found']}",
            f"- duplicates removed: {totals['duplicates_removed']}",
            f"- corrupted images skipped: {totals['corrupted_images_skipped']}",
            f"- missing labels converted to empty labels: {totals['missing_labels_fixed']}",
            f"- invalid label lines skipped: {totals['invalid_labels_skipped']}",
            f"- final train images: {split_counts['train']}",
            f"- final val images: {split_counts['val']}",
            f"- final test images: {split_counts['test']}",
            f"- final data.yaml path: {(yolo_dir / 'data.yaml').resolve()}",
            f"- final merged dataset location: {yolo_dir.resolve()}",
        ]
    )
    return "\n".join(lines) + "\n"


def merge(config: dict[str, Any]) -> dict[str, DatasetStats]:
    names = [str(name) for name in config.get("roboflow_dataset_names", ["Drone1", "Drone2", "Drone3"])]
    dataset_dirs: dict[str, Path] = {}
    missing: list[str] = []
    for name in names:
        dataset_dir = find_dataset_dir(name, config)
        if dataset_dir is None:
            missing.append(name)
        else:
            dataset_dirs[name] = dataset_dir
    if missing:
        print("Missing Roboflow dataset folders: " + ", ".join(missing))
        print(expected_structure())
        raise SystemExit(1)

    yolo_dir = project_path(config.get("yolo_dir", "data/yolo"))
    prepare_yolo_dirs(yolo_dir)
    stats_by_name: dict[str, DatasetStats] = {}
    pairs = collect_unique_pairs(dataset_dirs, config, stats_by_name)
    if not pairs:
        raise RuntimeError("No valid, non-duplicate images found to merge.")

    used_stems: set[str] = set()
    for split, split_items in split_pairs(pairs, config).items():
        for pair in split_items:
            copy_pair(pair, split, yolo_dir, stats_by_name[pair.dataset_name], used_stems)

    write_data_yaml(yolo_dir)
    processed_dir = ensure_dir(project_path(config.get("processed_dir", "data/processed")))
    report = build_report(stats_by_name, yolo_dir, config)
    write_text(processed_dir / "roboflow_merge_report.txt", report)
    print(report)
    print(f"[merge] Report saved to: {processed_dir / 'roboflow_merge_report.txt'}")
    return stats_by_name


def main() -> None:
    merge(load_config())


if __name__ == "__main__":
    main()
