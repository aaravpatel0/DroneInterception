from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from tqdm import tqdm

from common import PROJECT_ROOT, append_text, ensure_dir, read_manifest, setup_logging


LOGGER = setup_logging("download")
REPORT_PATH = PROJECT_ROOT / "reports" / "download_report.md"


def is_truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def has_existing_files(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def reset_target(path: Path, force: bool) -> None:
    if force and path.exists():
        shutil.rmtree(path)
    ensure_dir(path)


def log_report(message: str) -> None:
    append_text(REPORT_PATH, message.rstrip() + "\n")


def git_clone(row: dict[str, str], force: bool) -> bool:
    target = PROJECT_ROOT / row["raw_path"]
    if has_existing_files(target) and not force:
        LOGGER.info("%s already exists; skipping", row["dataset_id"])
        return True
    reset_target(target, force)
    if force and target.exists():
        shutil.rmtree(target)
    cmd = ["git", "clone", row["source_url"], str(target)]
    LOGGER.info("Cloning %s", row["dataset_id"])
    subprocess.run(cmd, check=True)
    return True


def kaggle_download(row: dict[str, str], force: bool) -> bool:
    target = PROJECT_ROOT / row["raw_path"]
    if has_existing_files(target) and not force:
        LOGGER.info("%s already exists; skipping", row["dataset_id"])
        return True
    if not (os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY")):
        kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
        if not kaggle_json.exists():
            LOGGER.warning("Kaggle credentials missing; skipping %s", row["dataset_id"])
            log_report(f"- `{row['dataset_id']}` skipped: Kaggle credentials missing. Put `kaggle.json` in `%USERPROFILE%\\.kaggle\\` or set `KAGGLE_USERNAME` and `KAGGLE_KEY`.")
            return False
    reset_target(target, force)
    dataset_slug = row["source_url"].rstrip("/").split("/datasets/")[-1]
    cmd = ["kaggle", "datasets", "download", "-d", dataset_slug, "-p", str(target), "--unzip"]
    LOGGER.info("Downloading Kaggle dataset %s", dataset_slug)
    subprocess.run(cmd, check=True)
    return True


def roboflow_download(row: dict[str, str], force: bool) -> bool:
    target = PROJECT_ROOT / row["raw_path"]
    if has_existing_files(target) and not force:
        LOGGER.info("%s already exists; skipping", row["dataset_id"])
        return True
    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if not api_key:
        LOGGER.warning("ROBOFLOW_API_KEY missing; skipping %s", row["dataset_id"])
        log_report(f"- `{row['dataset_id']}` skipped: set `ROBOFLOW_API_KEY` and verify the Roboflow project/version license before downloading.")
        return False
    LOGGER.warning("Roboflow project/version must be confirmed manually for %s", row["dataset_id"])
    log_report(f"- `{row['dataset_id']}` skipped: Roboflow URL needs workspace/project/version confirmation. Use official export API and place output in `{row['raw_path']}`.")
    return False


def direct_download(row: dict[str, str], force: bool) -> bool:
    target = PROJECT_ROOT / row["raw_path"]
    if has_existing_files(target) and not force:
        LOGGER.info("%s already exists; skipping", row["dataset_id"])
        return True
    url = row["download_command_or_function"].strip()
    if not url.startswith(("http://", "https://")):
        LOGGER.warning("No direct URL for %s", row["dataset_id"])
        return False
    reset_target(target, force)
    filename = Path(urlparse(url).path).name or f"{row['dataset_id']}.download"
    out_path = target / filename
    LOGGER.info("Downloading %s", url)
    existing = out_path.stat().st_size if out_path.exists() else 0
    headers = {"Range": f"bytes={existing}-"} if existing else {}
    with requests.get(url, stream=True, timeout=60, headers=headers) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        mode = "ab" if out_path.exists() else "wb"
        with out_path.open(mode) as f, tqdm(total=total, unit="B", unit_scale=True, desc=filename) as bar:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))
    if zipfile.is_zipfile(out_path):
        with zipfile.ZipFile(out_path) as zf:
            zf.extractall(target)
    return True


def manual_instructions(row: dict[str, str]) -> None:
    message = (
        f"- `{row['dataset_id']}` requires manual download.\n"
        f"  Source: {row['source_url']}\n"
        f"  Instructions: {row['download_command_or_function']}\n"
        f"  Expected folder: `{row['raw_path']}`\n"
    )
    print(message)
    log_report(message)


def download_all(force: bool, include_optional: bool) -> None:
    ensure_dir(REPORT_PATH.parent)
    REPORT_PATH.write_text("# Download Report\n\n", encoding="utf-8")
    rows = read_manifest()
    if not rows:
        raise FileNotFoundError("datasets_manifest.csv not found. Run scripts/research_datasets.py first.")

    for row in rows:
        dataset_id = row["dataset_id"]
        status = row.get("status", "")
        if status == "skip":
            LOGGER.info("Skipping %s because status=skip", dataset_id)
            log_report(f"- `{dataset_id}` skipped: manifest status is `skip`.")
            continue
        if status == "optional" and not include_optional:
            LOGGER.info("Skipping optional dataset %s", dataset_id)
            log_report(f"- `{dataset_id}` skipped: optional dataset. Re-run with `--include-optional`.")
            continue
        if is_truthy(row.get("needs_manual_download", "")):
            manual_instructions(row)
            continue
        try:
            method = row.get("download_method", "").lower()
            if method == "git":
                ok = git_clone(row, force)
            elif method == "kaggle":
                ok = kaggle_download(row, force)
            elif method == "roboflow":
                ok = roboflow_download(row, force)
            elif method in {"direct", "requests"}:
                ok = direct_download(row, force)
            else:
                LOGGER.warning("Unknown download method for %s: %s", dataset_id, method)
                ok = False
            log_report(f"- `{dataset_id}` {'downloaded or already present' if ok else 'not downloaded'}.")
        except Exception as exc:
            LOGGER.exception("Failed to download %s", dataset_id)
            log_report(f"- `{dataset_id}` failed: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public datasets using official methods only.")
    parser.add_argument("--force", action="store_true", help="Redownload datasets even when target folders already contain files.")
    parser.add_argument("--include-optional", action="store_true", help="Also attempt datasets marked optional.")
    args = parser.parse_args()
    download_all(force=args.force, include_optional=args.include_optional)


if __name__ == "__main__":
    main()
