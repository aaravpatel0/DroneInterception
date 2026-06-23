# Drone Dataset Hub

This project researches, downloads, inspects, converts, cleans, merges, previews, and smoke-tests public datasets for YOLOv8-based commercial drone detection/tracking.

The final training dataset is written to:

```text
data/yolo_merged/data.yaml
```

Classes:

```text
0 drone
1 bird
2 airplane
3 helicopter
4 unknown_flying_object
```

## Windows VSCode Setup

Open a VSCode terminal in this folder:

```powershell
cd C:\Users\aptcs\Downloads\DroneDetection\dataset_toolkit
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Kaggle Setup

Use one of these official Kaggle authentication methods:

```powershell
mkdir $env:USERPROFILE\.kaggle
copy path\to\kaggle.json $env:USERPROFILE\.kaggle\kaggle.json
```

Or set environment variables:

```powershell
$env:KAGGLE_USERNAME="your_username"
$env:KAGGLE_KEY="your_api_key"
```

Download Kaggle data only after you review and accept each dataset's Kaggle terms.

## Roboflow Setup

If you decide to use Roboflow Universe datasets, verify the project license and export terms, then set:

```powershell
$env:ROBOFLOW_API_KEY="your_api_key"
```

The downloader never stores API keys and never bypasses Roboflow's official export/API flow.

## Workflow

```powershell
python scripts/research_datasets.py
python scripts/download_datasets.py
python scripts/inspect_datasets.py
python scripts/convert_to_yolo.py
python scripts/clean_yolo_dataset.py
python scripts/merge_yolo_datasets.py
python scripts/preview_labels.py --split train --num 50
python scripts/dataset_stats.py
python scripts/train_smoke_test.py
```

Optional datasets are skipped by default. To attempt them:

```powershell
python scripts/download_datasets.py --include-optional
```

Force a redownload:

```powershell
python scripts/download_datasets.py --force --include-optional
```

## Uploaded Local Datasets

Place uploaded raw datasets under `dataset_toolkit/data/raw/`:

```text
dataset_toolkit/data/raw/anti_uav_dataset_300/
dataset_toolkit/data/raw/bird_vs_drone/
dataset_toolkit/data/raw/dut_anti_uav/
```

convert them into the hub with:

```powershell
python scripts\prepare_uploaded_datasets.py --frame-stride 10 --anti-modality visible
python scripts\merge_yolo_datasets.py
python scripts\preview_labels.py --split train --num 50
python scripts\dataset_stats.py
```

`prepare_uploaded_datasets.py` supports:

- `Bird vs Drone`: YOLOv7 boxes or segmentation polygons, preserving `0=drone` and `1=bird`.
- `DUT Anti-UAV`: frame folders plus `videoXX_gt.txt` tracking boxes, converted to class `0=drone`.
- `anti_uav_dataset_300`: `visible.mp4` or `infrared.mp4` plus Anti-UAV `exist` / `gt_rect` JSON annotations, converted to class `0=drone`.

The Anti-UAV video dataset can be large. Increase `--frame-stride` to extract fewer frames:

```powershell
python scripts\prepare_uploaded_datasets.py --frame-stride 30
```

For a quick code-path test, limit conversion:

```powershell
python scripts\prepare_uploaded_datasets.py --datasets bird_vs_drone dut anti_uav_300 --max-items 200 --frame-stride 100
```

To prepare only one uploaded dataset:

```powershell
python scripts\prepare_uploaded_datasets.py --datasets anti_uav_300 --frame-stride 100
```

## Full Training

After the smoke test passes, train normally:

```powershell
yolo detect train model=yolov8n.pt data=data/yolo_merged/data.yaml epochs=50 imgsz=640 batch=8
```

Or use the included Python training wrapper:

```powershell
python scripts\train_model.py --model yolov8n.pt --epochs 50 --imgsz 640 --batch 8
```

Validate a trained checkpoint:

```powershell
python scripts\validate_model.py --weights runs\train\drone_multidataset_yolov8\weights\best.pt --split test
```

Increase model size only after the dataset pipeline is stable:

```powershell
yolo detect train model=yolov8s.pt data=data/yolo_merged/data.yaml epochs=100 imgsz=640 batch=8
```

## Manual Download Folders

Some datasets require manual download or license review. Put extracted files exactly where the downloader/report says, for example:

```text
data/raw/anti_uav_zhao/
data/raw/maciullo_drone_detection/
data/raw/mendeley_drone_vs_bird_seg/
data/raw/incenda_aerospace_open/
```

After manual placement, rerun:

```powershell
python scripts/inspect_datasets.py
python scripts/convert_to_yolo.py
python scripts/clean_yolo_dataset.py
python scripts/merge_yolo_datasets.py
```

## Reports

- `datasets_manifest.csv`: source, license, citation, download method, annotation format, classes, status, and notes.
- `reports/dataset_research_report.md`: human-readable research summary.
- `reports/licenses_and_citations.md`: license and citation notes.
- `reports/download_report.md`: download/manual-skip results.
- `reports/inspection_*.md`: per-dataset inspection.
- `reports/conversion_report.md`: conversion successes and skips.
- `reports/cleaning_report.md`: corrupted/duplicate/invalid-label cleanup.
- `reports/merge_report.md`: final split counts.
- `reports/stats_report.md`: class and box statistics.
- `reports/previews/`: visual label previews.
- `reports/stats/`: plots.

## Troubleshooting

### Kaggle API Not Authenticated

Make sure `kaggle.json` is in:

```text
%USERPROFILE%\.kaggle\kaggle.json
```

Or set `KAGGLE_USERNAME` and `KAGGLE_KEY` in the terminal before running `download_datasets.py`.

### Roboflow API Key Missing

Set `ROBOFLOW_API_KEY`, then confirm the workspace/project/version identifiers and license on the Roboflow page. The included downloader intentionally does not guess private export versions.

### No Labels Found

Run:

```powershell
python scripts/inspect_datasets.py
```

Open `reports/inspection_<dataset_id>.md`. If the annotation format is custom, add a parser in `scripts/convert_to_yolo.py`.

### Class Mismatch

Edit label aliases in `config.yaml`. Drone-like labels are merged into class `0`.

### Corrupted Images

Run:

```powershell
python scripts/clean_yolo_dataset.py
```

Corrupted images and their label files are removed from individual YOLO datasets.

### Too Many Duplicate Frames

Near-duplicates are removed using perceptual image hashes. Increase or decrease:

```yaml
max_duplicate_hamming_distance: 2
```

Higher values remove more similar frames.

### CUDA Out Of Memory

Lower batch or image size:

```powershell
yolo detect train model=yolov8n.pt data=data/yolo_merged/data.yaml epochs=50 imgsz=512 batch=4
```

### Windows Path Issues

Run scripts from the project root and quote paths with spaces:

```powershell
cd C:\Users\aptcs\Downloads\DroneDetection\dataset_toolkit
python scripts\preview_labels.py --split train --num 50
```

## Safety Notes

This project only uses official download methods: Git, Kaggle API, Roboflow API/export, or direct official URLs. It does not scrape private, login-only, restricted, paywalled, or credential-protected data. Downloaded datasets, runs, and models are excluded by `.gitignore`.
