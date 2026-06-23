from __future__ import annotations

import argparse
import sys
import time

import serial
from serial.tools import list_ports


PICO_KEYWORDS = ("pico", "rp2350", "rp2040", "usb serial", "cdc")

PRESET_COMMANDS = {
    "center": "CENTER",
    "stop": "STOP",
    "status": "STATUS",
    "forward": "MOVE FORWARD 40000",
    "backward": "MOVE BACKWARD 25536",
    "left": "MOVE LEFT 25536",
    "right": "MOVE RIGHT 40000",
    "up": "MOVE UP 40000",
    "down": "MOVE DOWN 25536",
    "yaw-cw": "MOVE CW 40000",
    "yaw-ccw": "MOVE CCW 25536",
}


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


def send_command(port: str, command: str, delay: float) -> None:
    with serial.Serial(port, 115200, timeout=0.5) as pico:
        time.sleep(1.0)
        if pico.in_waiting:
            sys.stdout.write(pico.read(pico.in_waiting).decode(errors="replace"))
        pico.write((command.strip() + "\n").encode("utf-8"))
        pico.flush()
        time.sleep(delay)
        response = pico.read(512).decode(errors="replace").strip()
        if response:
            print(response)


def interactive(port: str) -> None:
    with serial.Serial(port, 115200, timeout=0.1) as pico:
        time.sleep(1.0)
        print(f"[pico] connected on {port}. Type commands; K or STOP disarms.")
        while True:
            if pico.in_waiting:
                sys.stdout.write(pico.read(pico.in_waiting).decode(errors="replace"))
            line = input("> ").strip()
            if not line:
                continue
            pico.write((line + "\n").encode("utf-8"))
            pico.flush()
            if line.upper() in {"QUIT", "EXIT"}:
                break


def main() -> None:
    parser = argparse.ArgumentParser(description="Send USB serial control commands to the Pico drone controller.")
    parser.add_argument("--port", help="Pico serial port. Auto-detected if omitted.")
    parser.add_argument("--command", help="One command to send, for example: ARM or T:32768.")
    parser.add_argument(
        "--preset",
        choices=sorted(PRESET_COMMANDS),
        help="Named movement command to send after ARM, useful for quick axis checks.",
    )
    parser.add_argument("--delay", type=float, default=0.25, help="Seconds to wait for a response after one command.")
    args = parser.parse_args()

    port = args.port or detect_port()
    if not port:
        raise SystemExit("No serial port found. Plug in the Pico and try again.")

    if args.command and args.preset:
        raise SystemExit("Use --command or --preset, not both.")

    if args.preset:
        send_command(port, "ARM", args.delay)
        send_command(port, PRESET_COMMANDS[args.preset], args.delay)
    elif args.command:
        send_command(port, args.command, args.delay)
    else:
        interactive(port)


if __name__ == "__main__":
    main()
