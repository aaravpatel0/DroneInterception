# ESP32-C3 Drone WiFi + BMI160 Bridge

This MicroPython module is the drone-side ESP32-C3 WiFi bridge. It listens for UDP control packets, keeps a short failsafe, and reports Bosch BMI160 IMU telemetry.

## Hardware Role

This is separate from the two Raspberry Pi Pico 2 boards:

| Board | Role |
| --- | --- |
| Pico 2 #1 | Drone remote/control PWM outputs for throttle, yaw, pitch, and roll |
| Pico 2 #2 | Servo/aiming controller used by the tracker hardware |
| ESP32-C3 | WiFi link and onboard BMI160 IMU telemetry for drone position/state tracking |

## BMI160 Wiring

| BMI160 Signal | ESP32-C3 GPIO |
| --- | ---: |
| SDA | GPIO 8 |
| SCL | GPIO 9 |
| VCC | 3.3V |
| GND | GND |

The default BMI160 I2C address is `0x68`. If the SDO pin is tied high, use `0x69`; the firmware checks both. The chip ID register `0x00` must return `0xD1`.

During startup, the bridge wakes the BMI160 sensors by writing:

```text
0x11 -> command register 0x7E  # accelerometer normal mode
0x15 -> command register 0x7E  # gyroscope normal mode
```

## Control Packet

UDP port: `4210`

Send either JSON:

```json
{"throttle":32768,"yaw":32768,"pitch":32768,"roll":32768}
```

or CSV:

```text
32768,32768,32768,32768
```

Axis meaning:

| Axis | Value below 32768 | Value above 32768 |
| --- | --- | --- |
| Throttle | Hold/lower altitude | Increase altitude |
| Yaw | Rotate counter-clockwise | Rotate clockwise |
| Pitch | Move backward | Move forward |
| Roll | Move left | Move right |

The bridge starts disarmed. Send `ARM` before controls, and send `STOP`, `K`, or `DISARM` to center and disarm. If no valid control packet arrives for `500 ms`, it centers and disarms.

## Setup

1. Install MicroPython on the ESP32-C3.
2. Edit `WIFI_SSID` and `WIFI_PASSWORD` in `main.py`.
3. Upload `main.py` to the ESP32.
4. Watch the serial console for the assigned IP address.

`STATUS` replies include `controls` plus BMI160 `accel_raw` and `gyro_raw` readings.
