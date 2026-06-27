# DroneDetection

Vision-guided drone tracking, 3D position estimation, turret control, and custom PCB prototypes for a small drone-frame build.

I am Aarav Patel, and I built DroneDetection as a computer-vision turret project: detect a drone in a live camera feed, estimate where it is in 3D space, predict where it is moving, and drive a physical pan/tilt turret to keep it centered. During the build, I pivoted the drone-control side from hacking joystick signals into a commercial controller to designing custom PCBs that reuse a Snaptain SP350-style frame, motors, and propellers with cleaner electronics.

I organized the code, demos, and board files so the project can be presented, reproduced, and continued once the fabricated PCBs arrive.

## Current Status

- YOLOv8 drone detection pipeline is working.
- Live camera tracking is working.
- Camera-relative 3D position estimation is working.
- Short-term motion prediction and preview arrows are working.
- Pico 2 turret firmware controls pan with a stepper and tilt with a servo.
- Stepper acceleration ramping is implemented to reduce stalls.
- Turret tracking and depth-perception tests have been run successfully.
- Custom PCB layouts are ready for fabrication review and ordering.
- Final hardware milestone: assemble and test the manufactured PCBs.

## Demo Links

| Demo | What it shows | Repo file | Drive link |
| --- | --- | --- | --- |
| YouTube project demo | Main public demo video for the full project | - | [Watch on YouTube](https://youtu.be/fUEFKIeKq6E?si=KoJLhP0QhyuUc3A9) |
| Live turret tracking | Physical turret tracking a detected drone | - | [Drone Tracking Turret.mp4](https://drive.google.com/file/d/1UBQOuaAiReNZodWpAV6A1nRXlFVHGqKZ/view?usp=drivesdk) |
| Detection proof of concept | Drone detected and tracked in camera view | - | [Proof of Concept - Drone Tracked.mp4](https://drive.google.com/file/d/1Y8ixHSbWaxlFa2D4qZv8LF1yn2z77p-x/view?usp=drivesdk) |
| Fast follow simulation | Simulated drone rapidly following a target | [MP4](assets/demo_simulations/follow_tracking_demo.mp4) / [GIF](assets/demo_simulations/follow_tracking_demo.gif) | [Drive MP4](https://drive.google.com/file/d/1x22EfQROl3rcCMJz3o-rANU-yGck9Fjs/view?usp=drivesdk) / [Drive GIF](https://drive.google.com/file/d/1ceiqXWkpfdoIr6vI1aE4kro-Gwh2Y9jS/view?usp=drivesdk) |
| Orbit simulation | Simulated drone orbiting around a tracked target | [MP4](assets/demo_simulations/orbit_tracking_demo.mp4) / [GIF](assets/demo_simulations/orbit_tracking_demo.gif) | [Drive MP4](https://drive.google.com/file/d/1vTIU1h2euXmmVWb8Ut7vwJZywcUVn1Vr/view?usp=drivesdk) / [Drive GIF](https://drive.google.com/file/d/1toew0ILT582uKQxMksciPWsyv_LBWJpW/view?usp=drivesdk) |
| Safe standoff simulation | Simulated controlled follow behavior with spacing | [MP4](assets/demo_simulations/standoff_tracking_demo.mp4) / [GIF](assets/demo_simulations/standoff_tracking_demo.gif) | [Drive MP4](https://drive.google.com/file/d/1BEXhN5-Scd0X3nanZK4e2Cr_hdrNLuV4/view?usp=drivesdk) / [Drive GIF](https://drive.google.com/file/d/1r3fI6IdqFA_aWafnw3gRHlx3CpV9DbdE/view?usp=drivesdk) |
| Full ship folder | Videos, previews, and supporting project files | - | [Google Drive folder](https://drive.google.com/drive/folders/1Nn7UfG2TgwVNnhRaEpTsOkTEUmSowxKg) |

The notebook and script used to generate the simulation videos are:

- [drone_detector/live_tracker/demo_flight_simulations.ipynb](drone_detector/live_tracker/demo_flight_simulations.ipynb)
- [drone_detector/live_tracker/demo_flight_simulations.py](drone_detector/live_tracker/demo_flight_simulations.py)

Regenerate all simulation clips:

```powershell
cd C:\Users\aptcs\Downloads\Projects\DroneDetection
.\drone_detector\.venv\Scripts\python.exe .\drone_detector\live_tracker\demo_flight_simulations.py --scenario all
```

## CAD

I designed the turret CAD in Onshape:

[Open the turret CAD in Onshape](https://cad.onshape.com/documents/1e954f2e6fb0afe0e50c1e47/w/2cc3740a39c70e9d1274ecfc/e/ad41d11dd19aaeac7b789fd0?renderMode=0&uiState=6a3ad88aa638e38f0ba9bea5)

## Project Layout

```text
DroneDetection/
|-- README.md
|-- assets/
|   `-- demo_simulations/          # Rendered tracking demo MP4s and GIFs
|-- Drone PCB/                     # SP350-frame drone board KiCad files and Gerbers
|-- Turret Control PCB/            # Turret controller KiCad files and Gerbers
|-- drone_detector/
|   |-- live_tracker/              # Live camera tracking, 3D position, prediction, turret control
|   |-- pico_turret_platformio/    # Active Pico 2 turret firmware
|   |-- pico_drone_platformio/     # Pico 2 drone remote-control firmware
|   |-- pico_drone_controller/     # MicroPython drone-control prototype
|   |-- esp32_drone_bridge/        # ESP32-C3 telemetry bridge and BMI160 IMU work
|   |-- scripts/                   # Docker and workflow helpers
|   |-- train_yolov8.py
|   |-- evaluate_model.py
|   `-- run_tracker_sim.ps1
|-- dataset_toolkit/               # Dataset research, conversion, cleaning, and reports
`-- archived/                      # Legacy firmware and old artifacts
```

## Hardware Overview

### Tracking Turret

| Part | Role |
| --- | --- |
| USB camera | Live video input for YOLO detection and 3D position estimation |
| Raspberry Pi Pico 2 | USB serial turret controller |
| Stepper driver | Drives the pan axis |
| NEMA 17 stepper | Rotates the turret left/right |
| Servo | Tilts the camera up/down |
| 12V input | Main turret power input |
| 12V-to-8.4V buck/BEC | Servo power rail on the turret PCB |
| Custom turret controller PCB | Cleaner replacement for prototype wiring |

### Drone-Frame Electronics

I started the drone-control work by injecting filtered voltage signals into a commercial drone controller. That proved my computer could affect the drone, but it was fragile and hard to reproduce. I then pivoted to a custom PCB for the small SP350-style frame.

I designed the drone-frame PCB around:

- Compact board outline for the reused frame.
- Four brushed motor outputs.
- Solder pads for motor and battery wiring.
- Shared ground and clean power routing.
- Room to continue integrating offboard control electronics.

## How The System Works

### 1. Dataset And Training

The training pipeline merges multiple YOLO-format drone datasets into a single `drone` class dataset, cleans labels, previews annotations, and trains/evaluates a YOLOv8 model.

Main scripts:

- `drone_detector/merge_roboflow_datasets.py`
- `drone_detector/clean_dataset.py`
- `drone_detector/preview_labels.py`
- `drone_detector/train_yolov8.py`
- `drone_detector/evaluate_model.py`

The live tracker expects:

```text
drone_detector/models/production_drone_model.pt
```

If that model is missing, it falls back to:

```text
drone_detector/models/drone_roboflow_best.pt
```

### 2. Detection

`drone_detector/live_tracker/turret_tracker.py` reads frames from a camera and runs YOLOv8 inference. It chooses the best drone bounding box, compares its center to the camera center, and uses that error to command the turret.

```text
error_x = box_center_x - frame_center_x
error_y = box_center_y - frame_center_y
```

### 3. Camera-Origin 3D Position

The tracker treats the camera as the origin:

```text
camera = (0.0, 0.0, 0.0) inches
```

The estimated drone position is logged as:

```text
x = left/right distance from camera center
y = up/down distance from camera center
z = forward distance away from the camera
```

Depth is estimated from the visible drone width, camera focal length, and bounding-box width. Yaw/pitch angles from the camera center convert that distance into camera-relative `x`, `y`, and `z`.

### 4. Prediction

The prediction system filters measured 3D position and velocity so one noisy frame does not make the turret jump. It:

- Smooths measured camera-space position.
- Smooths velocity.
- Softens unrealistic position jumps.
- Predicts a short distance into the future.
- Clamps the prediction arrow length.

Current launcher defaults:

```text
prediction horizon: 0.18 seconds
max prediction step: 14 inches
position smoothing alpha: 0.55
velocity smoothing alpha: 0.30
lost target hold: 0.15 seconds
```

### 5. Pan/Tilt Control

The Python tracker sends simple USB serial commands to the Pico 2 turret controller:

```text
PAN <steps>
TILT <angle>
PANZERO
STATUS
STOP
```

Pan uses horizontal pixel error. Tilt uses the vertical camera-relative estimate and stays inside configured servo limits. When the target leaves the frame, the turret briefly holds the last filtered target instead of snapping to a random angle.

### 6. Stepper Ramp

The Pico firmware ramps the stepper pulse delay at the beginning and end of each pan command:

```text
slow start pulse delay -> fast cruise pulse delay -> slow ending pulse delay
```

This helps reduce stepper stalls during fast tracking movements.

## Quick Start

Create or activate the Python environment, then run the tracker:

```powershell
cd C:\Users\aptcs\Downloads\Projects\DroneDetection\drone_detector
.\.venv\Scripts\Activate.ps1
.\run_tracker_sim.ps1 -Port COM6 -Source 0
```

Use a calmer pan gain if the turret overshoots:

```powershell
.\run_tracker_sim.ps1 -Port COM6 -Source 0 -KpPan 0.40
```

Emergency stop:

```powershell
.\.venv\Scripts\python.exe -c "import serial,time; s=serial.Serial('COM6',115200,timeout=1); time.sleep(1); s.write(b'K\n'); s.flush(); time.sleep(.3); print(s.read(200).decode(errors='ignore').strip()); s.close()"
```

Check Pico status:

```powershell
.\.venv\Scripts\python.exe -c "import serial,time; s=serial.Serial('COM6',115200,timeout=1); time.sleep(1); s.write(b'STATUS\n'); s.flush(); time.sleep(.3); print(s.read(300).decode(errors='ignore').strip()); s.close()"
```

## Upload Pico Turret Firmware

```powershell
cd C:\Users\aptcs\Downloads\Projects\DroneDetection\drone_detector\pico_turret_platformio
..\.venv\Scripts\python.exe -m platformio run -e rpipico2 --target upload
```

## Training Workflow

Place Roboflow YOLOv8 exports here:

```text
drone_detector/data/roboflow_raw/Drone1
drone_detector/data/roboflow_raw/Drone2
drone_detector/data/roboflow_raw/Drone3
```

Run the local workflow:

```powershell
cd C:\Users\aptcs\Downloads\Projects\DroneDetection\drone_detector
python preflight_check.py --fix-dirs
python preflight_check.py
python merge_roboflow_datasets.py
python clean_dataset.py
python preview_labels.py --split train --count 20
python preflight_check.py --smoke-train
```

Train and evaluate:

```powershell
python train_yolov8.py --device auto
python evaluate_model.py --device auto
```

## PCB Fabrication Files

Both PCB projects include KiCad files, Gerbers/drill files, previews, and fabrication ZIPs.

| Board | Local fabrication package | Local preview | Drive links |
| --- | --- | --- | --- |
| SP350 drone-frame PCB | [SP350_PCB_fabrication.zip](Drone%20PCB/SP350_PCB_fabrication.zip) | [sp350_fc_compact.svg](Drone%20PCB/preview/sp350_fc_compact.svg) | [Gerbers](https://drive.google.com/file/d/1_clK4amSKWlXcbOoY3qKn666rn6Dt4GA/view?usp=drivesdk) / [Preview](https://drive.google.com/file/d/1AM0e_IHqhc1ucxpBFDUrG8czhq44fBtK/view?usp=drivesdk) |
| Turret controller PCB | [Turret_Control_PCB_fabrication.zip](Turret%20Control%20PCB/Turret_Control_PCB_fabrication.zip) | [turret_control.svg](Turret%20Control%20PCB/preview/turret_control.svg) | [Gerbers](https://drive.google.com/file/d/1bgDib1TZAem1N0iuNZMGmwHZ0CROYYnE/view?usp=drivesdk) / [Preview](https://drive.google.com/file/d/17CKoOh3Z418mv7G7dEkDwoyh0OWlZMZ4/view?usp=drivesdk) |

KiCad DRC reports currently show `0 DRC violations` and `0 unconnected pads` for both boards.

## Debugging And Tuning

The tracker prints readable status lines:

```text
[track] DETECT conf=0.82 err=(+74,-12) x=+8.4in y=+1.2in z=42.0in target_x=+8.4in target_y=+1.2in -> pico2 PAN +37 TILT 86
```

Useful tuning notes:

- Increase `KpPan` if pan is too slow.
- Decrease `KpPan` if the turret overshoots.
- Increase `deadband-x` if it jitters near center.
- Decrease `imgsz` for lower latency.
- Increase `imgsz` if detections get unreliable.
- Increase stepper current carefully if the motor stalls under load.
- Increase the slow pulse delay in firmware if the stepper needs a gentler ramp start.

## Credits

I am Aarav Patel, and I designed, assembled, tested, and debugged this project. I also designed the turret CAD.

My drone-frame prototype reuses the original Snaptain SP350-style frame, brushed motors, and propellers as the mechanical base for custom electronics work. Snaptain is credited for those original commercial drone hardware parts.

Thanks to AI tools for helping me understand drone controls and PCB design, and for helping turn my drone tracking and orbiting code into simulations for the project demo.

The project concept, physical testing, wiring, debugging decisions, dataset work, CAD design, and final integration choices are my work.

## Safety

I built this for controlled visual tracking, turret experimentation, and drone-control research. Test with propellers removed or in a restrained setup whenever electronics, firmware, or control logic changes.

## More Documentation

- [drone_detector/README.md](drone_detector/README.md): training and detector details.
- [drone_detector/live_tracker/README.md](drone_detector/live_tracker/README.md): live tracker notes.
- [drone_detector/pico_turret_platformio/README.md](drone_detector/pico_turret_platformio/README.md): Pico turret firmware.
- [drone_detector/pico_drone_platformio/README.md](drone_detector/pico_drone_platformio/README.md): Pico drone controller firmware.
- [dataset_toolkit/README.md](dataset_toolkit/README.md): dataset tooling.
