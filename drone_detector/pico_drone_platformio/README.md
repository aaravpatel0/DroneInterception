# Pico 2 Ground-Station Drone PWM Driver

PlatformIO firmware for the Raspberry Pi Pico 2 ground-station bridge. The Pico connects to the computer over USB Serial and drives four 20 kHz PWM outputs through RC low-pass filters into a modified 3.3V drone remote.

## Pinout

| Pico GPIO | Physical pin | Wire color | Axis | Motion |
| ---: | ---: | --- | --- | --- |
| GP16 | 21 | Green | Throttle | Up/down altitude |
| GP17 | 22 | Blue | Yaw | Drone turning/rotation |
| GP18 | 24 | Yellow | Pitch | Forward/backward |
| GP19 | 25 | Orange | Roll | Left/right |
| GND | 23 | Ground | Common ground to remote |

## RC Filter Per Channel

Use the same two-row layout for each axis:

| Breadboard row | Connections |
| --- | --- |
| Row 1 input | Pico GPIO jumper and 1k resistor leg A |
| Row 2 junction | 1k resistor leg B, 1uF capacitor positive leg, remote PCB signal wire |
| Ground rail | 1uF capacitor negative leg to common ground |

## Serial Commands

The firmware accepts newline-terminated commands at `115200` baud:

```text
throttle:32768
yaw:32768
pitch:40000
roll:25536
center
status
```

Values are clamped to `0..65535`. Startup and `center` set all channels to neutral `32768`, roughly `1.65V` after the low-pass filter.

## Test

```powershell
pio run -t upload
pio device monitor
```

Try `pitch:65535`, `pitch:0`, and `pitch:32768`, then measure the pitch junction row with a multimeter. You should see roughly `3.3V`, `0V`, and `1.65V`.
