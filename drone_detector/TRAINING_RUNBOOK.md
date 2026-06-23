# Home PC Training Runbook

Use this file on the home training PC. The goal is to pull the latest repo, verify Docker/GPU support, prepare the Roboflow datasets, run a smoke train, and only then start full YOLOv8 training.

## 1. Pull the latest code

Open PowerShell on the home PC.

```powershell
cd C:\Users\aptcs\Downloads

# If the repo is not already cloned:
git clone https://github.com/aaravpatel0/DroneDetection.git

# If the repo already exists:
cd C:\Users\aptcs\Downloads\DroneDetection
git pull origin main

cd C:\Users\aptcs\Downloads\DroneDetection\drone_detector
```

## 2. Confirm the dataset folders

Place the Roboflow YOLOv8 exports here:

```text
drone_detector/data/roboflow_raw/Drone1
drone_detector/data/roboflow_raw/Drone2
drone_detector/data/roboflow_raw/Drone3
```

Each folder should contain a Roboflow-style structure like:

```text
Drone1/
|-- train/images
|-- train/labels
|-- valid/images   # or val/images
|-- valid/labels   # or val/labels
|-- test/images
|-- test/labels
`-- data.yaml
```

It is okay if Roboflow placed most files in `train`; `merge_roboflow_datasets.py` pools all images from `train`, `valid`, `val`, and `test`, then creates a fresh 70/15/15 split.

## 3. Build Docker

```powershell
.\scripts\docker_build.ps1
```

## 4. Check Docker CPU and GPU support

Run both checks:

```powershell
.\scripts\docker_cpu_check.ps1
.\scripts\docker_gpu_check.ps1
```

The GPU check should show something like:

```text
torch.cuda.is_available(): True
GPU name: <your NVIDIA GPU>
```

If the GPU check fails, the repo can still run on CPU, but full training will be much slower. Do not run GPU training until Docker can see CUDA.

## 5. Run the safe GPU workflow

```powershell
.\scripts\docker_preflight_gpu.ps1
.\scripts\docker_merge.ps1
.\scripts\docker_clean.ps1
.\scripts\docker_preview.ps1
.\scripts\docker_smoke_train_gpu.ps1
```

Before full training, verify:

- `data/yolo/data.yaml` exists.
- `data/yolo/images/train`, `val`, and `test` are non-empty.
- `data/yolo/labels/train`, `val`, and `test` are non-empty.
- Preview images were generated in `data/processed/previews/`.
- The 1-epoch smoke train passed.

## 6. Start full GPU training only after smoke train passes

```powershell
.\scripts\docker_train_gpu.ps1
```

After training finishes, evaluate:

```powershell
.\scripts\docker_eval_gpu.ps1
```

The final model should be saved to:

```text
models/drone_roboflow_best.pt
```

## 7. CPU fallback

If GPU Docker does not work, use CPU commands:

```powershell
.\scripts\docker_preflight_cpu.ps1
.\scripts\docker_smoke_train_cpu.ps1
.\scripts\docker_train_cpu.ps1
.\scripts\docker_eval_cpu.ps1
```

CPU training is expected to be much slower.

## 8. Direct Docker commands

These are useful for training workflow debugging:

```powershell
docker compose run --rm cpu python docker_test.py
docker compose run --rm gpu python docker_test.py

docker compose run --rm cpu python preflight_check.py
docker compose run --rm gpu python preflight_check.py

docker compose run --rm cpu python merge_roboflow_datasets.py
docker compose run --rm cpu python clean_dataset.py
docker compose run --rm cpu python preview_labels.py --split train --count 20
docker compose run --rm cpu python preview_labels.py --split val --count 20
docker compose run --rm cpu python preview_labels.py --split test --count 20

docker compose run --rm gpu python preflight_check.py --smoke-train --device auto
docker compose run --rm gpu python train_yolov8.py --device auto
docker compose run --rm gpu python evaluate_model.py --device auto
```

## 9. What to check before training

Verify all of this before running full training:

```text
1. docker compose build succeeds.
2. docker_test.py runs in CPU mode.
3. docker_test.py runs in GPU mode and torch.cuda.is_available() is True.
4. Drone1, Drone2, and Drone3 exist under data/roboflow_raw.
5. merge_roboflow_datasets.py creates data/yolo/data.yaml.
6. train, val, and test splits have images and labels.
7. clean_dataset.py passes.
8. preview_labels.py generates previews for train, val, and test.
9. preflight_check.py --smoke-train passes.
10. Only then run docker_train_gpu.ps1.
```

## 10. Do not commit generated files

Do not commit:

```text
*.pt
runs/
models/
data/yolo/
data/processed/
data/roboflow_raw/
```

The repo should contain code and instructions only. Dataset exports, merged YOLO data, training runs, and model weights should stay local on the home PC.

## 11. Live Turret Tracking

The live tracking system is in `live_tracker/` and the Arduino firmware is in `arduino_turret_firmware/`. It is only for visual drone tracking and landing/signaling turret alignment. Do not build or attach anything intended to disable, damage, jam, or take down drones.

The production model path is:

```text
models/production_drone_model.pt
```

If Git LFS is unavailable in a fresh checkout, place the production model there manually before running live tracking.

Upload the Arduino firmware with the VSCode task:

```text
PlatformIO: Upload Turret Firmware
```

Or from PowerShell:

```powershell
cd C:\Users\aptcs\Downloads\DroneDetection\drone_detector\arduino_turret_firmware
platformio run --target upload
```

Wiring summary:

```text
Arduino D3  -> TMC2209 STEP
Arduino D4  -> TMC2209 DIR
Arduino D5  -> TMC2209 EN
Arduino D9  -> HiWonder servo signal
Arduino GND -> TMC2209 GND and servo power GND
```

Use external power for both the stepper driver VM rail and the HiWonder servo. Do not power the servo from Arduino 5V. Test first with motors mechanically disconnected.

Dry-run tracking:

```powershell
cd C:\Users\aptcs\Downloads\DroneDetection\drone_detector
python live_tracker\turret_tracker.py --source 0 --dry-run --show
```

Live serial tracking:

```powershell
python live_tracker\turret_tracker.py --source 0 --port COM3 --show
```

Tune with `--deadband-x`, `--deadband-y`, `--kp-pan`, `--kp-tilt`, `--max-pan-step`, and `--conf`.
