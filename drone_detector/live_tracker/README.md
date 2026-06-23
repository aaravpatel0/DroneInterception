# Live Drone Tracking

This folder runs live visual drone tracking with the trained YOLOv8 model and estimates the drone position relative to the camera.

## Archived Turret Hardware

The old Arduino pan/tilt turret firmware has been archived at:

```text
archived/arduino_turret_firmware_legacy.zip
```

## Find The COM Port On Windows

Open Device Manager and check **Ports (COM & LPT)**, or run:

```powershell
python -m serial.tools.list_ports
```

Common Arduino ports look like `COM3`, `COM4`, or `COM5`.

## Run Tracking

Dry-run does not open the serial port. It prints intended commands and still shows the detection preview.

```powershell
cd C:\Users\aptcs\Downloads\DroneDetection\drone_detector
python live_tracker\turret_tracker.py --source 0 --dry-run --show
```

## Run Live Serial Output

```powershell
python live_tracker\turret_tracker.py --source 0 --port COM3 --show
```

If you omit `--port`, the script tries to auto-detect a likely Arduino port.

## Safe Drone Standoff Controller

The safe standoff controller reads `latest_position.json` from the camera tracker and sends cautious commands to the drone-control Pico. It is designed to approach only until a configured safe distance, then hold or back away; it does not command collision.

Start the tracker so it writes position estimates:

```powershell
python live_tracker\turret_tracker.py --source 0 --dry-run --show --position-output live_tracker\latest_position.json
```

In another terminal, dry-run the controller first:

```powershell
python live_tracker\safe_standoff_controller.py --duration-sec 30 --standoff-inches 72
```

Only after dry-run output looks correct, send live commands to the drone-control Pico:

```powershell
python live_tracker\safe_standoff_controller.py --port COM7 --live --duration-sec 10 --standoff-inches 72 --max-delta 1200
```

Use a large `--standoff-inches` and small `--max-delta` for early tests.

For faster following while still holding a safe standoff distance, use the fast profile:

```powershell
python live_tracker\safe_standoff_controller.py --profile fast --duration-sec 30 --standoff-inches 72
```

Live fast test:

```powershell
python live_tracker\safe_standoff_controller.py --port COM7 --live --profile fast --duration-sec 10 --standoff-inches 72
```

## Keyboard Controls

```text
q  quit
h  home
s  stop
+  increase confidence threshold
-  decrease confidence threshold
```

## Position Estimate

The tracker estimates the drone position from the YOLO bounding box when the drone size is known. The current defaults are:

```yaml
drone_visible_width_inches: 10.5
drone_height_inches: 2.5
focal_length_px: 588.0
camera_horizontal_fov_deg: 57.2
```

The estimate appears in the preview as:

```text
camera origin: (0.0, 0.0, 0.0) in
red x distance: left-right from camera in
green y distance: up-down from camera in
blue z distance: forward distance from camera in
angle yaw/pitch: horizontal-angle / vertical-angle deg
```

This follows the same triangle-similarity idea as the PyImageSearch marker-distance method: `z_distance = known_visible_width * focal_length_px / pixel_width`.
If the distance looks consistently too high or too low, tune `focal_length_px` after measuring the drone at a known distance:

```powershell
python live_tracker\turret_tracker.py --source 0 --dry-run --show --focal-length-px 588
```

If you calibrate the Logitech camera with a checkerboard, add `camera_matrix` and `dist_coeffs` to `camera_config.yaml`; the tracker will call `cv2.undistort` before detection and distance estimation.

## 3D Position Simulator

Run the tracker and write live positions to JSON:

```powershell
python live_tracker\turret_tracker.py --source 0 --dry-run --show --position-output live_tracker\latest_position.json
```

In another terminal, open the 3D simulator:

```powershell
python live_tracker\space_simulator.py
```

The simulator treats the BMI160 on the drone as `(0, 0, 0)` and draws the camera plus the tracked drone estimate relative to that BMI origin. Because the camera tracker measures the drone relative to the camera, the default `tracked-drone` mode places the camera at the inverse of that estimate and keeps the BMI/drone body at the origin.

To overlay the ESP32-C3 BMI160 IMU telemetry in the same 3D view, pass the ESP32-C3 IP address:

```powershell
python live_tracker\space_simulator.py --imu-host 192.168.1.123 --limit 240
```

The simulator sends `STATUS` to UDP port `4210` and draws a teal BMI160 marker with raw accelerometer and gyroscope readings. Replace `192.168.1.123` with the IP printed by the ESP32-C3 when it joins WiFi.

If the BMI is not mounted on the tracked drone body, use a manual camera offset from the BMI origin:

```powershell
python live_tracker\space_simulator.py --imu-host 192.168.1.123 --limit 240 --origin-mode manual-camera-offset --camera-x-from-bmi 0 --camera-y-from-bmi 0 --camera-z-from-bmi -36
```

If the points still look crowded, increase `--limit` to `360` or `480`.

## ESP32-C3 BMI160 Over WiFi

The ESP32-C3 bridge code is here:

```text
drone_detector/esp32_drone_bridge/main.py
```

Before running it wirelessly, edit:

```python
WIFI_SSID = "CHANGE_ME"
WIFI_PASSWORD = "CHANGE_ME"
```

Then upload over USB while the ESP32-C3 is still connected:

```powershell
cd C:\Users\aptcs\Downloads\Projects\DroneDetection
python -m mpremote connect COM8 fs cp drone_detector\esp32_drone_bridge\main.py :main.py
python -m mpremote connect COM8 reset
```

Open the serial output once to get the IP address:

```powershell
python -m mpremote connect COM8
```

Look for:

```text
wifi connected 192.168.1.123
BMI160 ready at 0x68
```

Your board may report `0x69` if SDO is tied high. After you know the IP address, you can unplug the ESP32-C3 from the computer and power it from the drone battery/regulator. Keep the ESP32-C3 and your computer on the same WiFi network.

## Calibrate The Logitech Camera

Your printed board has `8 x 10` squares, so OpenCV should use `7 x 9` inside corners. Each square is `20 mm`.

For best distance accuracy, capture calibration images through the same OpenCV path the tracker uses:

```powershell
python live_tracker\capture_calibration_images.py --source 0
```

Press `SPACE` to save each image and `q` to quit. Save 15-30 images, then run:

```powershell
python live_tracker\calibrate_camera.py --image-dir calibration_images_opencv --corners-x 7 --corners-y 9 --square-size-mm 20 --update-config
```

If no corners are found, rotate the pattern orientation:

```powershell
python live_tracker\calibrate_camera.py --image-dir calibration_images_opencv --corners-x 9 --corners-y 7 --square-size-mm 20 --update-config
```

## Tuning

- Increase `--deadband-x` or `--deadband-y` to reduce jitter.
- Decrease `--kp-pan` or `--kp-tilt` if tracking oscillates.
- Increase `--kp-pan` or `--kp-tilt` if tracking is too slow.
- Lower `--conf` if drones are missed.
- Raise `--conf` if false positives affect the tracker/controller.
- Lower `--max-pan-step` while testing a new mechanism.

Example cautious start:

```powershell
python live_tracker\turret_tracker.py --source 0 --port COM3 --show --max-pan-step 10 --kp-pan 0.015 --kp-tilt 0.01
```
