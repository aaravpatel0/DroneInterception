# Pico 2 W Turret Controller

MicroPython controller for the second Raspberry Pi Pico 2. This board is separate from the drone remote-control Pico and handles the servo/aiming hardware used by `live_tracker/turret_tracker.py`.

The first Pico 2 runs `../pico_drone_controller/` for throttle, yaw, pitch, and roll PWM outputs. The ESP32-C3 runs `../esp32_drone_bridge/` for WiFi and BMI160 IMU telemetry.

## Wiring

| Function | Pico GPIO |
| --- | ---: |
| Stepper STEP | GP3 |
| Stepper DIR | GP16 |
| Stepper EN | GP5 |
| Tilt servo signal | GP9 |

Use a shared ground between the Pico, stepper driver, servo power, and motor supply. Do not power the NEMA stepper from the Pico.

`EN` is active-low:

```text
GP5 low  = stepper driver enabled
GP5 high = stepper driver disabled
```

## Safety Limits

```text
Servo tilt: 85 to 130 degrees
Servo test ending angle: 85 degrees
Pan travel: -250 to +250 motor steps
```

With a 200-step motor and a 1:5 motor-to-turret gear ratio, `250` motor steps equals 90 turret degrees in full-step mode.

## Upload Without Thonny

Install MicroPython on the Pico 2 W first. Then:

```powershell
cd C:\Users\aptcs\Downloads\Projects\DroneDetection\drone_detector\pico_turret_controller
.\upload_main.ps1
```

If auto-detect fails:

```powershell
.\upload_main.ps1 -Port COM7
```

## Test Commands

Stepper only:

```powershell
python test_turret.py --port COM7 --mode stepper
```

Servo only, ending at 85:

```powershell
python test_turret.py --port COM7 --mode servo
```

Interactive:

```powershell
python test_turret.py --port COM7 --mode interactive
```

Manual serial commands:

```text
PANZERO
MOTOR ON
PAN 100
PAN -100
MOTOR OFF
TILT 90
TILT 85
STATUS
K
```

`K` and `STOP` disable the stepper and detach the servo PWM.
