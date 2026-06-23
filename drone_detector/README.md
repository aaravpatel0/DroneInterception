# Drone YOLOv8 Training Pipeline

This project trains a YOLOv8 drone detector from three Roboflow YOLOv8 exports:

- `Drone1`
- `Drone2`
- `Drone3`

The default workflow merges those exports into a single YOLOv8 dataset, normalizes every class ID to `0: drone`, checks labels, runs a 1-epoch smoke train, and only then allows full training.

## Project Layout

```text
drone_detector/
|-- config.yaml
|-- TRAINING_RUNBOOK.md
|-- Dockerfile
|-- docker-compose.yml
|-- docker_test.py
|-- pico_drone_controller/
|-- pico_drone_platformio/
|-- esp32_drone_bridge/
|-- merge_roboflow_datasets.py
|-- preflight_check.py
|-- clean_dataset.py
|-- preview_labels.py
|-- train_yolov8.py
|-- evaluate_model.py
|-- run_inference.py
|-- scripts/
|-- data/
|   |-- roboflow_raw/
|   |-- processed/
|   `-- yolo/
|-- runs/
`-- models/
```

## Start Here on the Home Training PC

Use `TRAINING_RUNBOOK.md` as the step-by-step runbook for manual setup on the home PC. The quick version is:

```powershell
cd C:\Users\aptcs\Downloads
git clone https://github.com/aaravpatel0/DroneDetection.git
cd DroneDetection\drone_detector
```

Place the Roboflow exports here:

```text
data/roboflow_raw/Drone1
data/roboflow_raw/Drone2
data/roboflow_raw/Drone3
```

Then run the guarded Docker workflow:

```powershell
.\scripts\docker_build.ps1
.\scripts\docker_cpu_check.ps1
.\scripts\docker_gpu_check.ps1
.\scripts\docker_preflight_gpu.ps1
.\scripts\docker_merge.ps1
.\scripts\docker_clean.ps1
.\scripts\docker_preview.ps1
.\scripts\docker_smoke_train_gpu.ps1
```

Only after the smoke train passes, start full training:

```powershell
.\scripts\docker_train_gpu.ps1
.\scripts\docker_eval_gpu.ps1
```

If GPU Docker does not work, use the CPU fallback scripts instead. CPU training is much slower.

## Install

Run these commands from PowerShell if you want to use the non-Docker local Python workflow:

```powershell
cd C:\Users\aptcs\Downloads\DroneDetection\drone_detector
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Dataset Placement

Put the Roboflow YOLOv8 exports here:

```text
data/roboflow_raw/Drone1
data/roboflow_raw/Drone2
data/roboflow_raw/Drone3
```

Each dataset can use the normal Roboflow YOLOv8 layout:

```text
Drone1/
|-- train/
|   |-- images/
|   `-- labels/
|-- valid/        # or val/
|   |-- images/
|   `-- labels/
|-- test/
|   |-- images/
|   `-- labels/
`-- data.yaml
```

Roboflow exports may use `valid` instead of `val`, and some exports may place most files in `train`. The merge script pools every discovered image-label pair from `Drone1`, `Drone2`, and `Drone3`, removes duplicate images, shuffles with `random_seed: 42`, then creates a fresh 70/15/15 train/val/test split.

## Safe Local Python Workflow

Run this sequence before full training:

```powershell
python preflight_check.py --fix-dirs
python preflight_check.py
python merge_roboflow_datasets.py
python clean_dataset.py
python preview_labels.py --split train --count 20
python preview_labels.py --split val --count 20
python preview_labels.py --split test --count 20
python preflight_check.py --smoke-train
```

Only if the smoke train passes, run:

```powershell
python train_yolov8.py
python evaluate_model.py
python run_inference.py --source 0
```

For image or video inference:

```powershell
python run_inference.py --source path\to\image.jpg
python run_inference.py --source path\to\video.mp4
```

## Docker Training on Home PC

GPU training through Docker requires Docker Desktop with WSL2 enabled and NVIDIA GPU support installed. If the GPU check fails, use the CPU scripts; CPU training works but will be much slower.

From your home PC:

```powershell
git clone https://github.com/aaravpatel0/DroneDetection.git
cd DroneDetection\drone_detector
```

Place the Roboflow exports here:

```text
data/roboflow_raw/Drone1
data/roboflow_raw/Drone2
data/roboflow_raw/Drone3
```

Build and run the safe GPU workflow:

```powershell
.\scripts\docker_build.ps1
.\scripts\docker_gpu_check.ps1
.\scripts\docker_cpu_check.ps1
.\scripts\docker_preflight_gpu.ps1
.\scripts\docker_merge.ps1
.\scripts\docker_clean.ps1
.\scripts\docker_preview.ps1
.\scripts\docker_smoke_train_gpu.ps1
```

Only if preflight, merge, preview, and smoke training pass:

```powershell
.\scripts\docker_train_gpu.ps1
.\scripts\docker_eval_gpu.ps1
```

CPU fallback:

```powershell
.\scripts\docker_preflight_cpu.ps1
.\scripts\docker_smoke_train_cpu.ps1
.\scripts\docker_train_cpu.ps1
.\scripts\docker_eval_cpu.ps1
```

Direct Docker commands are also available:

```powershell
docker compose run --rm gpu python docker_test.py
docker compose run --rm gpu python preflight_check.py --smoke-train --device auto
docker compose run --rm gpu python train_yolov8.py --device auto
docker compose run --rm cpu python train_yolov8.py --device cpu
```

Do not run full training until preflight, merge, preview generation, and the 1-epoch smoke train pass.

## Ready-to-Train Checklist

Before running full training, confirm:

```text
[ ] Docker build passed.
[ ] CPU Docker test passed.
[ ] GPU Docker test shows torch.cuda.is_available(): True.
[ ] Drone1, Drone2, and Drone3 are present under data/roboflow_raw.
[ ] merge_roboflow_datasets.py created data/yolo/data.yaml.
[ ] train, val, and test splits have images and labels.
[ ] clean_dataset.py completed.
[ ] preview_labels.py generated previews for train, val, and test.
[ ] 1-epoch smoke training passed.
```

If any item fails, fix it before running full training.

## Outputs

- Merged YOLO dataset: `data/yolo/`
- Merge report: `data/processed/roboflow_merge_report.txt`
- Cleaning report: `data/processed/cleaning_report.txt`
- Preflight report: `data/processed/preflight_report.txt`
- Label previews: `data/processed/previews/`
- Smoke run: `runs/smoke_test/roboflow_preflight_yolov8n/`
- Full training run: `runs/train/drone_roboflow_yolov8/`
- Final best model: `models/drone_roboflow_best.pt`
- Latest model pointer: `models/latest_model_path.txt`
- Evaluation report: `data/processed/evaluation_report.txt`
- Inference outputs: `runs/inference/predict/`

## Configuration

The default `config.yaml` uses:

```yaml
roboflow_raw_dir: data/roboflow_raw
roboflow_dataset_names:
  - Drone1
  - Drone2
  - Drone3
yolo_dir: data/yolo
image_extensions: [.jpg, .jpeg, .png, .bmp, .webp]
train_ratio: 0.70
val_ratio: 0.15
test_ratio: 0.15
class_names: ["drone"]
model_size: yolov8n.pt
epochs: 50
imgsz: 640
batch: 8
confidence_threshold: 0.35
random_seed: 42
final_model_name: drone_roboflow_best.pt
```

Lower `batch` or `imgsz` if you run out of GPU memory.

Training and evaluation also accept command-line overrides:

```powershell
python train_yolov8.py --device auto --epochs 50 --imgsz 640 --batch 8
python train_yolov8.py --device cpu
python evaluate_model.py --device auto --imgsz 640 --batch 8
python preflight_check.py --smoke-train --device cpu
```

## Script Summary

- `TRAINING_RUNBOOK.md`: home-PC runbook for manual training.
- `preflight_check.py`: checks source Roboflow folders, merged dataset counts, labels, CUDA, imports, and optionally runs a 1-epoch smoke train with `--device auto`, `--device cpu`, or a GPU index such as `--device 0`.
- `merge_roboflow_datasets.py`: pools all images from `Drone1`, `Drone2`, and `Drone3`, removes duplicate images, creates a deterministic 70/15/15 split, renames files to avoid collisions, normalizes labels to `0 drone`, and writes `data/yolo/data.yaml`.
- `clean_dataset.py`: verifies `data/yolo/data.yaml`, removes corrupted generated images, validates labels, clamps slightly out-of-range boxes, and writes a cleaning report.
- `preview_labels.py`: draws YOLO boxes and saves previews under `data/processed/previews/`.
- `train_yolov8.py`: trains YOLOv8 from `data/yolo/data.yaml` and copies `best.pt` to `models/drone_roboflow_best.pt`. CLI overrides include `--device`, `--epochs`, `--imgsz`, and `--batch`.
- `evaluate_model.py`: evaluates `models/drone_roboflow_best.pt` on the test split and writes metrics. CLI overrides include `--device`, `--imgsz`, and `--batch`.
- `run_inference.py`: runs trained-model inference on webcam, image, video, or URL sources.

## Live Drone Tracking

The live turret tracker uses the production model at:

```text
models/production_drone_model.pt
```

If that file is missing, the tracker falls back to `models/drone_roboflow_best.pt`. The system visually tracks drones and estimates their position relative to the camera.

### Arduino Control Direction

The turret firmware has been archived at `archived/arduino_turret_firmware_legacy.zip`.

Active drone-control starter code now lives in:

```text
pico_drone_controller/
pico_turret_controller/
esp32_drone_bridge/
```

Hardware roles:

| Board | Folder | Role |
| --- | --- | --- |
| Raspberry Pi Pico 2 #1 | `pico_drone_controller/` or `pico_drone_platformio/` | Drone remote PWM for throttle, yaw, pitch, and roll |
| Raspberry Pi Pico 2 #2 | `pico_turret_controller/` | Servo/aiming controller for tracker hardware |
| ESP32-C3 | `esp32_drone_bridge/` | WiFi bridge and Bosch BMI160 IMU telemetry |

The ground drone-control Pico 2 axis mapping is:

| Axis | GPIO | Wire color | Below 32768 | Above 32768 |
| --- | ---: | --- | --- | --- |
| Throttle | GP16 | Green | Hold/lower altitude | Increase altitude |
| Yaw | GP17 | Blue | Counter-clockwise rotation | Clockwise rotation |
| Pitch | GP18 | Yellow | Backward | Forward |
| Roll | GP19 | Orange | Left | Right |

Yaw is wired for turning, but the main movement tests usually focus on throttle, pitch, and roll.

The onboard IMU is a Bosch BMI160 wired to the ESP32-C3 with SDA on GPIO 8 and SCL on GPIO 9. The firmware checks chip ID `0xD1` at register `0x00` and wakes the accelerometer/gyroscope through command register `0x7E`.

### Run Tracking

Dry-run mode prints intended serial commands without opening the Arduino port:

```powershell
cd C:\Users\aptcs\Downloads\DroneDetection\drone_detector
python live_tracker\turret_tracker.py --source 0 --dry-run --show
```

Live serial tracking:

```powershell
python live_tracker\turret_tracker.py --source 0 --port COM3 --show
```

Find the COM port in Device Manager under **Ports (COM & LPT)** or with:

```powershell
python -m serial.tools.list_ports
```

Tuning tips:

- Increase deadband to reduce jitter.
- Decrease `Kp` if tracking oscillates.
- Increase `Kp` if tracking is too slow.
- Lower confidence threshold if detections are missed.
- Raise confidence threshold if false positives move the tracker/controller.

## Troubleshooting

### Missing Merged Splits

If preflight reports an empty merged split, rerun `python merge_roboflow_datasets.py`. Source exports do not need original valid/test folders, but the merged dataset must have non-empty train, val, and test splits before smoke training.

### Bad Labels

Run:

```powershell
python clean_dataset.py
python preview_labels.py --split train --count 20
```

The cleaner removes invalid boxes, clamps boxes that are only slightly outside image bounds, and writes `data/processed/cleaning_report.txt`.

### CUDA Not Found

For local Python:

```powershell
python -c "import torch; print(torch.cuda.is_available())"
```

For Docker:

```powershell
.\scripts\docker_gpu_check.ps1
```

If GPU Docker fails, verify Docker Desktop is using WSL2 and that the NVIDIA driver supports containers. Use CPU scripts as a fallback.
