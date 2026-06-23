from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests

from project_utils import ensure_dir, load_config, project_path, write_text


def clone_metadata_repo(repo_url: str, metadata_dir: Path) -> None:
    parent = metadata_dir.parent
    ensure_dir(parent)

    if metadata_dir.exists():
        print(f"[setup] Metadata/sample repo already exists at: { metadata_dir }")
        print("[setup] Skipping clone. Delete the folder if you want a fresh clone.")
        return

    print(f"[setup] Cloning dataset from { repo_url }")
    cmd = ["git", "clone", repo_url, str(metadata_dir)]
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Git was not found. Install Git for Windows and make sure it is on PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"git clone failed with exit code { exc.returncode }") from exc

    if not metadata_dir.exists():
        raise RuntimeError(f"Clone finished, but metadata folder was not created: { metadata_dir }")

    print(f"[setup] Metadata/sample repo ready: { metadata_dir }")


def extract_dataset_links(readme_path: Path) -> list[str]:
    if not readme_path.exists():
        raise FileNotFoundError(f"README.md not found in metadata repo: { readme_path }")
    text = readme_path.read_text(encoding="utf-8", errors="ignore")
    urls = re.findall(r"https?://[^\s)>\"]+", text)
    return [url.rstrip(".,") for url in urls if "sharepoint.com" in url.lower()]


def looks_like_download_response(content_type: str, url: str) -> bool:
    content_type = content_type.lower()
    suffix = Path(urlparse(url).path).suffix.lower()
    downloadable_types = ("application/zip", "application/octet-stream", "application/x-zip-compressed")
    return suffix in {".zip", ".rar", ".7z"} or any(item in content_type for item in downloadable_types)


def try_sharepoint_download(url: str, full_dataset_dir: Path) -> bool:
    print("[setup] Attempting a safe automatic SharePoint download check...")
    print("[setup] This only works if the SharePoint URL resolves to a direct downloadable archive.")
    try:
        response = requests.get(url, stream=True, allow_redirects=True, timeout=30)
    except requests.RequestException as exc:
        print(f"[setup] SharePoint request failed: { exc }")
        return False

    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400:
        print(f"[setup] SharePoint returned HTTP { response.status_code }.")
        return False
    if not looks_like_download_response(content_type, response.url):
        print(f"[setup] SharePoint returned an interactive page, not a direct archive. Content-Type: { content_type or 'unknown' }")
        return False

    filename = Path(urlparse(response.url).path).name or "uett4k_anti_uav_download.zip"
    download_path = full_dataset_dir.parent / filename
    ensure_dir(full_dataset_dir.parent)
    print(f"[setup] Direct archive detected. Downloading to: { download_path }")
    with download_path.open("wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    print("[setup] Download finished. Extract the archive into the full dataset folder if needed:")
    print(f"[setup]   { full_dataset_dir }")
    return True


def print_manual_instructions(sharepoint_links: list[str], full_dataset_dir: Path) -> None:
    print("")
    print("[setup] Manual download required.")
    print("[setup] The README points to a SharePoint folder, which usually requires browser interaction.")
    print("[setup] Please download the full dataset manually from:")
    for link in sharepoint_links:
        print(f"[setup]   { link }")
    print("")
    print("[setup] Extract/place the downloaded full dataset here:")
    print(f"[setup]   { full_dataset_dir }")
    print("")
    print("[setup] After the folder contains the real images and labels, run:")
    print("[setup]   python inspect_dataset.py")
    print("[setup]   python convert_annotations.py")


def main() -> None:
    config = load_config()
    metadata_dir = project_path(config.get("metadata_dir", "data/raw/UETT4K-Anti-UAV"))
    full_dataset_dir = project_path(config.get("full_dataset_dir", config["raw_dir"]))
    clone_metadata_repo(config["repo_url"], metadata_dir)

    sharepoint_links = extract_dataset_links(metadata_dir / "README.md")
    if not sharepoint_links:
        raise RuntimeError(
            f"No SharePoint dataset link was found in { metadata_dir / 'README.md' }. "
            "Open the README manually and update config.yaml if the dataset URL changed."
        )

    report = "UETT4K full dataset links found in README.md\n" + "\n".join(sharepoint_links) + "\n"
    write_text(project_path(config["processed_dir"]) / "uett4k_sharepoint_link.txt", report)
    print("[setup] SharePoint dataset link(s) extracted:")
    for link in sharepoint_links:
        print(f"[setup]   { link }")

    if full_dataset_dir.exists() and any(full_dataset_dir.iterdir()):
        print(f"[setup] Full dataset folder already contains files: { full_dataset_dir }")
        print("[setup] Skipping download. Run inspect_dataset.py to detect images and annotation format.")
        return

    ensure_dir(full_dataset_dir)
    downloaded = try_sharepoint_download(sharepoint_links[0], full_dataset_dir)
    if not downloaded:
        print_manual_instructions(sharepoint_links, full_dataset_dir)
        return


if __name__ == "__main__":
    main()
