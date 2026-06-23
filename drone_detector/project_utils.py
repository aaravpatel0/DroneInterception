from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, UnidentifiedImageError


PROJECT_ROOT = Path(__file__).resolve().parent


def load_config(config_path: str | Path = "config.yaml") -> dict[str, Any]:
    path = Path(config_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: { path }")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    # Keep every script anchored to drone_detector/ even when it is launched
    # from VSCode tasks, Docker, or a different PowerShell working directory.
    return PROJECT_ROOT / path


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def image_extensions(config: dict[str, Any]) -> set[str]:
    return {str(ext).lower() for ext in config.get("image_extensions", [])}


def list_images(root: Path, extensions: set[str]) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in extensions
    )


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


def is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def drone_label_like(label: str | None) -> bool:
    if not label:
        return True
    normalized = label.strip().lower()
    if not normalized:
        return True
    keywords = ("drone", "uav", "uas", "aircraft", "quadcopter", "copter", "target")
    return any(keyword in normalized for keyword in keywords)


def resolve_device(requested: str = "auto", log_prefix: str = "device") -> str | int:
    requested = str(requested).strip().lower()
    if requested == "cpu":
        print(f"[{log_prefix}] Using CPU.")
        return "cpu"
    if requested == "auto":
        try:
            import torch

            if torch.cuda.is_available():
                print(f"[{log_prefix}] CUDA detected: {torch.cuda.get_device_name(0)}")
                return 0
        except Exception as exc:
            print(f"[{log_prefix}] Could not inspect CUDA with torch: {exc}")
        # Falling back to CPU keeps preflight/evaluation usable on laptops and
        # CI machines that do not have the training GPU attached.
        print(f"[{log_prefix}] CUDA not detected. Using CPU.")
        return "cpu"
    if requested.isdigit():
        print(f"[{log_prefix}] Using CUDA device {requested}.")
        return int(requested)
    print(f"[{log_prefix}] Using device value: {requested}")
    return requested
