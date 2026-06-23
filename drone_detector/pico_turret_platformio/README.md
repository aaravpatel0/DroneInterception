# Pico 2 W Turret Controller - PlatformIO

This is the PlatformIO C++/Arduino-Pico version of the turret controller. It replaces the Arduino Uno firmware while keeping the same USB serial commands used by the Python tracker.

## Pins

| Function | Pico 2 W GPIO |
| --- | ---: |
| Stepper STEP | GP3 |
| Stepper DIR | GP16 |
| Stepper EN | GP5 |
| Tilt servo signal | GP9 |

Use a shared ground between Pico, stepper driver, servo supply, and motor supply.

`EN` is active-low:

```text
GP5 LOW  = driver enabled
GP5 HIGH = driver disabled
```

## Limits

```text
Servo tilt: 85 to 130 degrees
Pan travel: -900 to +900 driver steps
Max pan command: 80 driver steps
```

Tune this range after confirming the real microstepping and gear ratio on the assembled turret.

## Build

```powershell
cd C:\Users\aptcs\Downloads\Projects\DroneDetection\drone_detector\pico_turret_platformio
python -m platformio run
```

## Upload

Hold `BOOTSEL`, plug in the Pico 2 W, then release `BOOTSEL`.

```powershell
python -m platformio run --target upload
```

If PlatformIO cannot upload directly, build first and copy the UF2 manually:

```powershell
python -m platformio run
```

Then drag this file onto the `RPI-RP2` drive:

```text
.pio\build\rpipico2w\firmware.uf2
```

## Commands

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
STOP
```

`K` and `STOP` disable the stepper and detach the servo.
