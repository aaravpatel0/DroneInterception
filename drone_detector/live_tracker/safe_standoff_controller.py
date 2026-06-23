from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports


TRACKER_DIR = Path(__file__).resolve().parent
DEFAULT_POSITION_FILE = TRACKER_DIR / "latest_position.json"
NEUTRAL = 32768
PWM_MIN = 0
PWM_MAX = 65535
PICO_KEYWORDS = ("pico", "rp2350", "rp2040", "usb serial", "cdc")


def clamp(value: float, low: int, high: int) -> int:
    return max(low, min(high, int(round(value))))


def detect_port() -> str | None:
    ports = list(list_ports.comports())
    for port in ports:
        haystack = " ".join(
            str(value or "")
            for value in (port.device, port.description, port.manufacturer, port.hwid)
        ).lower()
        if any(keyword in haystack for keyword in PICO_KEYWORDS):
            return port.device
    return ports[0].device if ports else None


def load_position(path: Path) -> dict[str, float] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return {
        key: float(value)
        for key, value in data.items()
        if isinstance(value, (int, float))
    }


def make_commands(
    position: dict[str, float],
    standoff_inches: float,
    stop_band_inches: float,
    x_deadband_inches: float,
    y_deadband_inches: float,
    z_gain: float,
    x_gain: float,
    y_gain: float,
    max_delta: int,
) -> tuple[list[str], str]:
    x = position.get("x_inches", 0.0)
    y = position.get("y_inches", 0.0)
    z = position.get("z_inches", position.get("distance_inches", 0.0))
    distance = position.get("distance_inches", math.sqrt(x * x + y * y + z * z))

    pitch_delta = 0
    if distance > standoff_inches + stop_band_inches:
        pitch_delta = clamp((distance - standoff_inches) * z_gain, 0, max_delta)
    elif distance < standoff_inches - stop_band_inches:
        pitch_delta = -clamp((standoff_inches - distance) * z_gain, 0, max_delta)

    roll_delta = 0 if abs(x) < x_deadband_inches else clamp(x * x_gain, -max_delta, max_delta)
    throttle_delta = 0 if abs(y) < y_deadband_inches else clamp(y * y_gain, -max_delta, max_delta)

    pitch = clamp(NEUTRAL + pitch_delta, PWM_MIN, PWM_MAX)
    roll = clamp(NEUTRAL + roll_delta, PWM_MIN, PWM_MAX)
    throttle = clamp(NEUTRAL + throttle_delta, PWM_MIN, PWM_MAX)

    reason = (
        f"target x={x:.1f} y={y:.1f} z={z:.1f} distance={distance:.1f} "
        f"standoff={standoff_inches:.1f}"
    )
    return [f"PITCH {pitch}", f"ROLL {roll}", f"THROTTLE {throttle}"], reason


class PicoLink:
    def __init__(self, port: str | None, live: bool):
        self.port = port
        self.live = live
        self.serial: serial.Serial | None = None

    def __enter__(self) -> "PicoLink":
        if self.live:
            if not self.port:
                raise RuntimeError("No Pico serial port found.")
            self.serial = serial.Serial(self.port, 115200, timeout=0.1)
            time.sleep(1.0)
            self.drain()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.send("CENTER")
        self.send("DISARM")
        if self.serial is not None:
            self.serial.close()

    def drain(self) -> None:
        if self.serial is not None and self.serial.in_waiting:
            sys.stdout.write(self.serial.read(self.serial.in_waiting).decode(errors="replace"))

    def send(self, command: str) -> None:
        if not self.live:
            print(f"[dry-run] {command}")
            return
        if self.serial is None:
            raise RuntimeError("Pico serial link is not open.")
        self.serial.write((command + "\n").encode("utf-8"))
        self.serial.flush()
        time.sleep(0.02)
        self.drain()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safe camera-guided standoff controller for the drone Pico. It will not command collision."
    )
    parser.add_argument("--position-file", type=Path, default=DEFAULT_POSITION_FILE)
    parser.add_argument("--port", help="Pico serial port. Auto-detected if omitted.")
    parser.add_argument("--live", action="store_true", help="Actually send commands to the Pico. Default is dry-run.")
    parser.add_argument(
        "--profile",
        choices=("normal", "fast"),
        default="normal",
        help="Control tuning preset. Fast follows more aggressively while preserving standoff behavior.",
    )
    parser.add_argument("--duration-sec", type=float, default=30.0)
    parser.add_argument("--rate-hz", type=float, help="Controller update rate. Defaults depend on --profile.")
    parser.add_argument("--standoff-inches", type=float, default=72.0, help="Minimum target distance to maintain.")
    parser.add_argument("--stop-band-inches", type=float, help="Distance band around standoff. Defaults depend on --profile.")
    parser.add_argument("--stale-after-sec", type=float, default=1.0)
    parser.add_argument("--x-deadband-inches", type=float, help="Left/right deadband. Defaults depend on --profile.")
    parser.add_argument("--y-deadband-inches", type=float, help="Up/down deadband. Defaults depend on --profile.")
    parser.add_argument("--z-gain", type=float, help="Forward/back distance gain. Defaults depend on --profile.")
    parser.add_argument("--x-gain", type=float, help="Left/right gain. Defaults depend on --profile.")
    parser.add_argument("--y-gain", type=float, help="Up/down gain. Defaults depend on --profile.")
    parser.add_argument("--max-delta", type=int, help="Max PWM delta from neutral per axis. Defaults depend on --profile.")
    return parser.parse_args()


def apply_profile_defaults(args: argparse.Namespace) -> argparse.Namespace:
    if args.profile == "fast":
        defaults = {
            "rate_hz": 12.0,
            "stop_band_inches": 4.0,
            "x_deadband_inches": 3.0,
            "y_deadband_inches": 3.0,
            "z_gain": 38.0,
            "x_gain": 135.0,
            "y_gain": 135.0,
            "max_delta": 4200,
        }
    else:
        defaults = {
            "rate_hz": 5.0,
            "stop_band_inches": 8.0,
            "x_deadband_inches": 6.0,
            "y_deadband_inches": 6.0,
            "z_gain": 18.0,
            "x_gain": 70.0,
            "y_gain": 70.0,
            "max_delta": 2500,
        }

    for name, value in defaults.items():
        if getattr(args, name) is None:
            setattr(args, name, value)
    return args


def main() -> None:
    args = apply_profile_defaults(parse_args())
    port = args.port or detect_port()
    interval = 1.0 / max(args.rate_hz, 0.1)
    deadline = time.monotonic() + args.duration_sec

    print("[controller] live mode" if args.live else "[controller] dry-run mode")
    print(
        f"[controller] profile={args.profile} rate={args.rate_hz:.1f}Hz "
        f"standoff={args.standoff_inches:.1f}in max_delta={args.max_delta}"
    )
    if args.live:
        print(f"[controller] Pico port: {port}")

    with PicoLink(port, args.live) as pico:
        pico.send("ARM")
        while time.monotonic() < deadline:
            position = load_position(args.position_file)
            if position is None:
                print("[controller] no position; centering")
                pico.send("CENTER")
                time.sleep(interval)
                continue

            updated_at = position.get("updated_at")
            if updated_at is not None and time.time() - updated_at > args.stale_after_sec:
                print("[controller] stale position; centering")
                pico.send("CENTER")
                time.sleep(interval)
                continue

            commands, reason = make_commands(
                position,
                args.standoff_inches,
                args.stop_band_inches,
                args.x_deadband_inches,
                args.y_deadband_inches,
                args.z_gain,
                args.x_gain,
                args.y_gain,
                args.max_delta,
            )
            print(f"[controller] {reason}")
            for command in commands:
                pico.send(command)
            time.sleep(interval)

        pico.send("CENTER")


if __name__ == "__main__":
    main()
