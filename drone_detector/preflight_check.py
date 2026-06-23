from __future__ import annotations

import argparse
import importlib
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from merge_roboflow_datasets import SOURCE_SPLITS, SPLITS, collect_pairs, expected_structure, find_dataset_dir, parse_class_names
from project_utils import ensure_dir, image_extensions, load_config, project_path, resolve_device, write_text


PROJECT_ROOT = Path(__file__).resolve().parent
IMAGE_EXTENSIONS_DEFAULT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
REQUIRED_FILES = [
    "config.yaml",
    "requirements.txt",
    "merge_roboflow_datasets.py",
    "clean_dataset.py",
    "preview_labels.py",
    "train_yolov8.py",
    "evaluate_model.py",
    "run_inference.py",
]
REQUIRED_IMPORTS = {
    "ultralytics": "ultralytics",
    "cv2": "cv2",
    "numpy": "numpy",
    "pandas": "pandas",
    "yaml": "yaml",
    "PIL": "PIL",
    "tqdm": "tqdm",
    "torch": "torch",
}


@dataclass
class CheckReport:
    lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def line(self, text: str = "") -> None:
        self.lines.append(text)

    def ok(self, text: str) -> None:
        self.lines.append(f"[OK] {text}")

    def warn(self, text: str) -> None:
        self.warnings.append(text)
        self.lines.append(f"[WARN] {text}")

    def error(self, text: str) -> None:
        self.errors.append(text)
        self.lines.append(f"[ERROR] {text}")


def count_files(root: Path, extensions: set[str]) -> int:
    if not root.exists():
        return 0
    return sum(1 for p in root.rglob("*") if p.is_file() and p.suffix.lower() in extensions)


def list_files(root: Path, extensions: set[str]) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in extensions)


def validate_label_file(label_path: Path) -> tuple[int, int, int]:
    empty = 0
    invalid = 0
    boxes = 0
    if not label_path.exists():
        return empty, invalid, boxes
    text = label_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return 1, 0, 0
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            invalid += 1
            continue
        try:
            class_id = int(float(parts[0]))
            xc, yc, width, height = [float(value) for value in parts[1:]]
        except ValueError:
            invalid += 1
            continue
        if class_id != 0 or not (0 <= xc <= 1) or not (0 <= yc <= 1) or not (0 < width <= 1) or not (0 < height <= 1):
            invalid += 1
            continue
        boxes += 1
    return empty, invalid, boxes


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def create_missing_dirs(report: CheckReport) -> None:
    report.line("# Directory Setup")
    report.line("")
    dirs = [
        PROJECT_ROOT / "data" / "roboflow_raw",
        PROJECT_ROOT / "data" / "processed",
        PROJECT_ROOT / "data" / "yolo",
        PROJECT_ROOT / "runs",
        PROJECT_ROOT / "models",
    ]
    for directory in dirs:
        ensure_dir(directory)
        report.ok(f"Ensured directory exists: {directory}")


def check_environment(report: CheckReport) -> None:
    report.line("# Roboflow YOLOv8 Drone Pipeline Preflight Report")
    report.line("")
    report.line("## Environment")
    report.ok(f"Python executable: {sys.executable}")
    report.ok(f"Python version: {platform.python_version()}")
    report.ok(f"Project folder: {PROJECT_ROOT}")
    report.ok(f"Current working directory: {Path.cwd()}")
    if Path.cwd().resolve() != PROJECT_ROOT.resolve():
        report.warn(f"Run scripts from the project folder for best results: {PROJECT_ROOT}")


def check_required_files(report: CheckReport) -> None:
    report.line("")
    report.line("## Required Files")
    for relative in REQUIRED_FILES:
        path = PROJECT_ROOT / relative
        if path.exists():
            report.ok(f"Found {relative}")
        else:
            report.error(f"Missing {relative}")


def check_imports(report: CheckReport) -> dict[str, Any]:
    report.line("")
    report.line("## Python Package Imports")
    state: dict[str, Any] = {"imports_ok": True, "torch": None}
    for display_name, module_name in REQUIRED_IMPORTS.items():
        try:
            module = importlib.import_module(module_name)
            report.ok(f"Import works: {display_name}")
            if module_name == "torch":
                state["torch"] = module
        except Exception as exc:
            state["imports_ok"] = False
            report.error(f"Import failed: {display_name} ({exc})")
    return state


def check_cuda(report: CheckReport, torch_module: Any | None, requested_device: str = "auto") -> None:
    report.line("")
    report.line("## CUDA")
    if torch_module is None:
        report.warn("Cannot check CUDA because torch did not import")
        return
    try:
        cuda_available = bool(torch_module.cuda.is_available())
        report.line(f"torch version: {torch_module.__version__}")
        report.line(f"torch.cuda.is_available(): {cuda_available}")
        cuda_version = getattr(getattr(torch_module, "version", None), "cuda", None)
        report.line(f"torch.version.cuda: {cuda_version}")
        if cuda_available:
            report.ok(f"GPU: {torch_module.cuda.get_device_name(0)}")
        else:
            report.warn("CUDA is not available. Training can run on CPU, but it will be much slower.")
        selected = resolve_device(requested_device, "preflight")
        report.line(f"Requested device: {requested_device}")
        report.line(f"Current device used: {selected}")
    except Exception as exc:
        report.warn(f"CUDA check failed: {exc}")


def check_config(report: CheckReport, config: dict[str, Any]) -> None:
    report.line("")
    report.line("## Config")
    expected_values = {
        "roboflow_raw_dir": "data/roboflow_raw",
        "yolo_dir": "data/yolo",
        "model_size": "yolov8n.pt",
        "final_model_name": "drone_roboflow_best.pt",
    }
    for key, expected in expected_values.items():
        actual = config.get(key)
        if actual == expected:
            report.ok(f"{key}: {actual}")
        else:
            report.warn(f"{key}: {actual!r}; expected default {expected!r}")

    ratio_sum = float(config.get("train_ratio", 0)) + float(config.get("val_ratio", 0)) + float(config.get("test_ratio", 0))
    if abs(ratio_sum - 1.0) < 1e-6:
        report.ok(f"split ratios sum to 1.0: {ratio_sum:.2f}")
    else:
        report.error(f"split ratios must sum to 1.0; got {ratio_sum:.6f}")

    names = [str(name) for name in config.get("roboflow_dataset_names", [])]
    if names:
        report.ok(f"roboflow_dataset_names: {', '.join(names)}")
    else:
        report.error("roboflow_dataset_names must include at least one dataset")

    if config.get("class_names") == ["drone"]:
        report.ok("class_names normalized to: drone")
    else:
        report.error("class_names must be exactly ['drone']")


def check_roboflow_datasets(report: CheckReport, config: dict[str, Any]) -> dict[str, Any]:
    report.line("")
    report.line("## Roboflow Source Datasets")
    state: dict[str, Any] = {"datasets_found": {}, "source_images_ok": True}
    names = [str(name) for name in config.get("roboflow_dataset_names", ["Drone1", "Drone2", "Drone3"])]
    extensions = image_extensions(config) or IMAGE_EXTENSIONS_DEFAULT
    for name in names:
        dataset_dir = find_dataset_dir(name, config)
        if dataset_dir is None:
            report.error(f"{name} not found.\n{expected_structure()}")
            state["source_images_ok"] = False
            continue

        state["datasets_found"][name] = dataset_dir
        report.ok(f"{name} found: {dataset_dir}")
        data_yaml = dataset_dir / "data.yaml"
        if data_yaml.exists():
            classes = parse_class_names(load_yaml(data_yaml))
            report.ok(f"{name} data.yaml found; original class names: {classes or ['<none>']}")
        else:
            report.error(f"{name} is missing data.yaml")

        pairs = collect_pairs(name, dataset_dir, extensions)
        labels_found = sum(1 for pair in pairs if pair.label_path is not None)
        report.line(f"{name}: {len(pairs)} images discovered across train/valid/val/test folders, {labels_found} matching labels")
        source_counts = {}
        for split in SOURCE_SPLITS:
            split_dir = dataset_dir / split
            image_count = count_files(split_dir / "images", extensions)
            label_count = count_files(split_dir / "labels", {".txt"})
            source_counts[split] = image_count
            status = "exists" if split_dir.exists() else "missing"
            report.line(f"{name} {split}: {status}, {image_count} images, {label_count} labels")
        if source_counts.get("train", 0) > 0 and source_counts.get("valid", 0) == 0 and source_counts.get("val", 0) == 0 and source_counts.get("test", 0) == 0:
            report.warn(f"{name} appears to have all images only in train; merge will create a fresh split.")
        if not pairs:
            report.error(f"{name} has 0 images under {dataset_dir}")
            state["source_images_ok"] = False
    return state


def check_yolo_dataset(report: CheckReport, config: dict[str, Any]) -> dict[str, Any]:
    report.line("")
    report.line("## Merged YOLO Dataset")
    yolo_dir = project_path(config.get("yolo_dir", "data/yolo"))
    extensions = image_extensions(config) or IMAGE_EXTENSIONS_DEFAULT
    state: dict[str, Any] = {
        "data_yaml_exists": False,
        "split_images": {split: 0 for split in SPLITS},
        "split_labels": {split: 0 for split in SPLITS},
        "missing_label_files": 0,
        "empty_label_files": 0,
        "invalid_label_lines": 0,
    }

    data_yaml = yolo_dir / "data.yaml"
    state["data_yaml_exists"] = data_yaml.exists()
    if data_yaml.exists():
        report.ok(f"YOLO data.yaml exists: {data_yaml}")
    else:
        report.warn(f"YOLO data.yaml does not exist yet: {data_yaml}. Run merge_roboflow_datasets.py after source checks.")

    for split in SPLITS:
        image_dir = yolo_dir / "images" / split
        label_dir = yolo_dir / "labels" / split
        images = list_files(image_dir, extensions)
        labels = list_files(label_dir, {".txt"})
        state["split_images"][split] = len(images)
        state["split_labels"][split] = len(labels)
        report.line(f"{split}: {len(images)} images, {len(labels)} labels")
        if data_yaml.exists() and len(images) == 0:
            report.error(f"Merged {split} split has 0 images")

        for image_path in images:
            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.exists():
                state["missing_label_files"] += 1
        for label_path in labels:
            empty, invalid, _boxes = validate_label_file(label_path)
            state["empty_label_files"] += empty
            state["invalid_label_lines"] += invalid

    report.line(f"Missing label files: {state['missing_label_files']}")
    report.line(f"Empty label files: {state['empty_label_files']}")
    report.line(f"Invalid YOLO label lines: {state['invalid_label_lines']}")
    if state["missing_label_files"]:
        report.error("Some YOLO images are missing matching label files")
    if state["invalid_label_lines"]:
        report.error("Some YOLO labels have invalid format, class IDs, or coordinates")
    return state


def smoke_ready(imports_ok: bool, yolo_state: dict[str, Any]) -> bool:
    return (
        imports_ok
        and yolo_state["data_yaml_exists"]
        and all(yolo_state["split_images"][split] > 0 for split in SPLITS)
        and yolo_state["missing_label_files"] == 0
        and yolo_state["invalid_label_lines"] == 0
    )


def readiness_report(report: CheckReport, imports_ok: bool, source_state: dict[str, Any], yolo_state: dict[str, Any]) -> dict[str, bool]:
    report.line("")
    report.line("## Readiness")
    ready = {
        "source_datasets": bool(source_state.get("datasets_found")) and source_state.get("source_images_ok", False),
        "merged_dataset": yolo_state["data_yaml_exists"] and all(yolo_state["split_images"][split] > 0 for split in SPLITS),
        "labels_valid": yolo_state["missing_label_files"] == 0 and yolo_state["invalid_label_lines"] == 0,
        "smoke_training": smoke_ready(imports_ok, yolo_state),
    }
    ready["full_training"] = ready["smoke_training"]
    for label, value in ready.items():
        report.line(f"{label.replace('_', ' ').title()}: {'YES' if value else 'NO'}")
    return ready


def run_smoke_train(report: CheckReport, ready: dict[str, bool], device: str) -> None:
    report.line("")
    report.line("## Smoke Training")
    data_yaml = PROJECT_ROOT / "data" / "yolo" / "data.yaml"
    if not data_yaml.exists():
        report.error(f"Smoke training skipped because data.yaml is missing: {data_yaml}")
        return
    if not ready.get("smoke_training", False):
        report.error("Smoke training skipped because the merged dataset is not ready.")
        return
    try:
        from ultralytics import YOLO

        model = YOLO("yolov8n.pt")
        results = model.train(
            data=str(data_yaml),
            epochs=1,
            imgsz=320,
            batch=2,
            project=str(PROJECT_ROOT / "runs" / "smoke_test"),
            name="roboflow_preflight_yolov8n",
            device=resolve_device(device, "smoke"),
            exist_ok=True,
        )
        report.ok(f"Smoke training completed. Results: {getattr(results, 'save_dir', PROJECT_ROOT / 'runs' / 'smoke_test' / 'roboflow_preflight_yolov8n')}")
    except Exception as exc:
        report.error(f"Smoke training failed: {exc}")


def save_report(report: CheckReport) -> Path:
    report.line("")
    report.line("## Summary")
    report.line(f"Warnings: {len(report.warnings)}")
    report.line(f"Errors: {len(report.errors)}")
    output_path = PROJECT_ROOT / "data" / "processed" / "preflight_report.txt"
    write_text(output_path, "\n".join(report.lines) + "\n")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Roboflow YOLOv8 pre-training checks.")
    parser.add_argument("--smoke-train", action="store_true", help="Run a guarded 1-epoch YOLOv8n smoke train.")
    parser.add_argument("--fix-dirs", action="store_true", help="Create missing project directories and exit without dataset checks.")
    parser.add_argument("--device", default="auto", help="Smoke training device: auto, cpu, 0, 1, etc.")
    args = parser.parse_args()

    report = CheckReport()
    if args.fix_dirs:
        create_missing_dirs(report)
        report_path = save_report(report)
        print("\n".join(report.lines))
        print(f"\n[preflight] Directory setup report saved to: {report_path}")
        return

    check_environment(report)
    check_required_files(report)
    import_state = check_imports(report)
    check_cuda(report, import_state.get("torch"), args.device)
    config = load_config()
    check_config(report, config)
    source_state = check_roboflow_datasets(report, config)
    yolo_state = check_yolo_dataset(report, config)
    ready = readiness_report(report, bool(import_state.get("imports_ok")), source_state, yolo_state)
    if args.smoke_train:
        run_smoke_train(report, ready, args.device)

    report_path = save_report(report)
    print("\n".join(report.lines))
    print(f"\n[preflight] Report saved to: {report_path}")

    if report.errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
