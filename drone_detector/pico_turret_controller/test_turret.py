from __future__ import annotations

import argparse
import sys
import time

import serial
from serial.tools import list_ports


PICO_KEYWORDS = ("pico", "rp2350", "rp2040", "usb serial", "cdc")


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


def drain(board: serial.Serial) -> str:
    time.sleep(0.25)
    return board.read(512).decode(errors="replace").strip()


def send(board: serial.Serial, command: str, delay: float) -> None:
    board.write((command + "\n").encode("utf-8"))
    board.flush()
    time.sleep(delay)
    response = board.read(512).decode(errors="replace").strip()
    print(f"{command} => {response}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Pico turret serial commands.")
    parser.add_argument("--port", help="Pico serial port. Auto-detected if omitted.")
    parser.add_argument("--mode", choices=("stepper", "servo", "both", "interactive"), default="stepper")
    args = parser.parse_args()

    port = args.port or detect_port()
    if not port:
        raise SystemExit("No serial port found. Plug in the Pico and try again.")

    with serial.Serial(port, 115200, timeout=0.5) as board:
        time.sleep(1.0)
        ready = drain(board)
        if ready:
            print(ready)

        if args.mode == "interactive":
            print(f"[pico] connected on {port}. Type commands; K stops.")
            while True:
                command = input("> ").strip()
                if not command:
                    continue
                send(board, command, 0.2)
                if command.upper() in {"EXIT", "QUIT"}:
                    break
            return

        sequences = {
            "stepper": ["PANZERO", "MOTOR ON", "STATUS", "PAN 100", "PAN -100", "MOTOR OFF"],
            "servo": ["TILT 90", "TILT 100", "TILT 130", "TILT 85", "K"],
            "both": ["PANZERO", "TILT 90", "PAN 100", "TILT 100", "PAN -100", "TILT 85", "K"],
        }
        for command in sequences[args.mode]:
            send(board, command, 1.0)


if __name__ == "__main__":
    main()
