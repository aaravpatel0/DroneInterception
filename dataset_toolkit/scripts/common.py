from __future__ import annotations

import csv
import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
from PIL import Image, UnidentifiedImageError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "datasets_manifest.csv"
REPORTS_DIR = PROJECT_ROOT / "reports"


@dataclass(frozen=True)
class YoloBox:
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float


def setup_logging(name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
    )
    return logging.getLogger(name)


def load_config(path: Path | str = "config.yaml") -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def project_path(path: Path | str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def ensure_dir(path: Path | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_manifest(path: Path = MANIFEST_PATH) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_manifest(rows: list[dict[str, Any]], path: Path = MANIFEST_PATH) -> None:
    ensure_dir(path.parent)
    columns = [
        "dataset_id",
        "dataset_name",
        "source_url",
        "license",
        "citation",
        "download_method",
        "download_command_or_function",
        "needs_manual_download",
        "needs_api_key",
        "raw_path",
        "annotation_format",
        "classes_available",
        "useful_for",
        "status",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def image_extensions(config: dict[str, Any]) -> set[str]:
    return {str(ext).lower() for ext in config.get("image_extensions", [])}


def video_extensions(config: dict[str, Any]) -> set[str]:
    return {str(ext).lower() for ext in config.get("video_extensions", [])}


def list_files(root: Path, extensions: Iterable[str]) -> list[Path]:
    ext_set = {ext.lower() for ext in extensions}
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in ext_set)


def get_image_size(path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            return img.size
    except (OSError, UnidentifiedImageError):
        return None


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def append_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(content)


def safe_slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", text).strip("_").lower()


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def alias_to_class_id(label: str | int | None, config: dict[str, Any], default: int | None = None) -> int | None:
    if label is None:
        return default
    text = str(label).strip().lower().replace(" ", "-").replace("_", "-")
    if text.isdigit():
        numeric = int(text)
        return numeric if numeric in config.get("class_names", {}) else default

    alias_groups = [
        (0, config.get("drone_label_aliases", [])),
        (1, config.get("bird_label_aliases", [])),
        (2, config.get("airplane_label_aliases", [])),
        (3, config.get("helicopter_label_aliases", [])),
    ]
    for class_id, aliases in alias_groups:
        normalized = {str(alias).strip().lower().replace(" ", "-").replace("_", "-") for alias in aliases}
        if text in normalized or any(alias and alias in text for alias in normalized):
            return class_id
    if "unknown" in text or "flying" in text or "object" in text:
        return 4
    return default


def pixels_to_yolo(
    class_id: int,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    image_width: int,
    image_height: int,
) -> YoloBox | None:
    xmin = max(0.0, min(float(image_width), float(xmin)))
    ymin = max(0.0, min(float(image_height), float(ymin)))
    xmax = max(0.0, min(float(image_width), float(xmax)))
    ymax = max(0.0, min(float(image_height), float(ymax)))
    if xmax <= xmin or ymax <= ymin:
        return None
    box_w = xmax - xmin
    box_h = ymax - ymin
    return YoloBox(
        class_id=class_id,
        x_center=(xmin + box_w / 2) / image_width,
        y_center=(ymin + box_h / 2) / image_height,
        width=box_w / image_width,
        height=box_h / image_height,
    )


def write_data_yaml(path: Path, dataset_root: Path, class_names: dict[int, str]) -> None:
    names = {int(k): v for k, v in class_names.items()}
    data = {
        "path": str(dataset_root.resolve()),
        "train": "images/train" if (dataset_root / "images" / "train").exists() else "images",
        "val": "images/val" if (dataset_root / "images" / "val").exists() else "images",
        "test": "images/test" if (dataset_root / "images" / "test").exists() else "images",
        "names": names,
    }
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)
