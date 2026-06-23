# Pico 2 W Drone Remote PWM Controller

This MicroPython controller runs on the first Raspberry Pi Pico 2. It drives four filtered PWM outputs into a 3.3V drone remote for throttle, yaw, pitch, and roll.

The second Pico 2 is separate and runs the servo/aiming controller in `../pico_turret_controller/`. The ESP32-C3 WiFi + BMI160 bridge lives in `../esp32_drone_bridge/`.

## Pins

| Axis | Pico GPIO | Wire color | PWM duty neutral |
| --- | ---: | --- | ---: |
| Throttle | GP16 | Green | 32768 |
| Yaw | GP17 | Blue | 32768 |
| Pitch | GP18 | Yellow | 32768 |
| Roll | GP19 | Orange | 32768 |

PWM frequency is `20000 Hz`. Each output expects a `10k` resistor and `0.1uF` capacitor low-pass filter before the remote signal line.

## Axis Direction Mapping

The ground Pico 2 W outputs use 16-bit values from `0` to `65535`, with `32768` as neutral.

| Axis | GPIO | Wire color | Motion | Below 32768 | Above 32768 |
| --- | ---: | --- | --- | --- | --- |
| Throttle | GP16 | Green | Up/down altitude | Hold/lower altitude | Increase altitude |
| Yaw | GP17 | Blue | Drone turning/rotation | Counter-clockwise | Clockwise |
| Pitch | GP18 | Yellow | Forward/backward | Backward | Forward |
| Roll | GP19 | Orange | Left/right lateral | Left | Right |

Yaw is available for turning, but the main movement tests usually focus on throttle, pitch, and roll.

## Upload Without Thonny

Install MicroPython on the Pico 2 W once, then copy `main.py` over USB:

```powershell
cd C:\Users\aptcs\Downloads\Projects\DroneDetection\drone_detector\pico_drone_controller
.\upload_main.ps1
```

If auto-detect fails:

```powershell
.\upload_main.ps1 -Port COM7
```

## Command Protocol

The Pico starts disarmed and centers all outputs at `32768`.

```text
ARM
THROTTLE 32768
YAW 32768
PITCH 32768
ROLL 32768
T:32768
Y:32768
P:32768
R:32768
MOVE FORWARD 40000
MOVE BACKWARD 25536
MOVE LEFT 25536
MOVE RIGHT 40000
MOVE UP 40000
MOVE DOWN 25536
MOVE CW 40000
MOVE CCW 25536
STATUS
CENTER
K
STOP
DISARM
```

`K`, `STOP`, and `DISARM` immediately center all channels and disarm.

You can remap an axis at runtime:

```text
MAP THROTTLE 16
MAP YAW 17
MAP PITCH 18
MAP ROLL 19
```

## PC Test Sender

Interactive mode:

```powershell
python send_controls.py --port COM7
```

One command:

```powershell
python send_controls.py --port COM7 --command "ARM"
python send_controls.py --port COM7 --command "T:40000"
python send_controls.py --port COM7 --command "MOVE FORWARD 40000"
python send_controls.py --port COM7 --command "K"
```

Named preset:

```powershell
python send_controls.py --port COM7 --preset forward
python send_controls.py --port COM7 --preset right
python send_controls.py --port COM7 --preset yaw-cw
python send_controls.py --port COM7 --preset stop
```

The failsafe recenters and disarms if the Pico is armed and receives no serial command for `1000 ms`.

## ESP32 + IMU WiFi Bridge

The drone-side WiFi bridge starter lives in:

```text
drone_detector/esp32_drone_bridge/
```

It receives `throttle`, `yaw`, `pitch`, and `roll` values over UDP, replies with telemetry JSON, and has a `read_imu()` hook for the IMU driver once the exact sensor is selected.
