from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

try:
    import serial
    from serial.tools import list_ports
except ImportError as exc:  # pragma: no cover - exercised by users without pyserial
    raise SystemExit(
        "pyserial is required for turret serial control. Install it with: pip install pyserial"
    ) from exc


PICO_KEYWORDS = ("pico", "rp2040", "rp2350", "raspberry", "2e8a", "usb serial", "ttyacm")


@dataclass
class SerialResponse:
    command: str
    response: str | None


def list_serial_ports() -> list[str]:
    return [port.device for port in list_ports.comports()]


def autodetect_pico_port() -> str | None:
    ports = list(list_ports.comports())
    for port in ports:
        haystack = " ".join(
            str(value or "")
            for value in (port.device, port.description, port.manufacturer, port.hwid)
        ).lower()
        if any(keyword in haystack for keyword in PICO_KEYWORDS):
            return port.device
    return ports[0].device if ports else None


class PicoSerialController:
    def __init__(
        self,
        port: str | None = None,
        baud: int = 115200,
        timeout: float = 0.5,
        reconnect_interval: float = 2.0,
    ) -> None:
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.reconnect_interval = reconnect_interval
        self._serial: serial.Serial | None = None
        self._last_connect_attempt = 0.0

    @property
    def connected(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    def connect(self) -> None:
        selected_port = self.port or autodetect_pico_port()
        if not selected_port:
            available = ", ".join(list_serial_ports()) or "<none>"
            raise RuntimeError(
                "Could not auto-detect a Pico 2 serial port. "
                f"Available ports: {available}. Pass --port COMx explicitly."
            )

        self.port = selected_port
        self.close()
        try:
            self._serial = serial.Serial(selected_port, self.baud, timeout=self.timeout)
            time.sleep(1.0)
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
        except serial.SerialException as exc:
            self._serial = None
            raise RuntimeError(f"Failed to open serial port {selected_port}: {exc}") from exc

    def reconnect_if_needed(self) -> None:
        if self.connected:
            return
        now = time.monotonic()
        if now - self._last_connect_attempt < self.reconnect_interval:
            return
        self._last_connect_attempt = now
        self.connect()

    def close(self) -> None:
        if self._serial:
            try:
                self._serial.close()
            finally:
                self._serial = None

    def read_response(self) -> str | None:
        if not self.connected or not self._serial:
            return None
        try:
            line = self._serial.readline()
        except serial.SerialException as exc:
            self.close()
            raise RuntimeError(f"Serial read failed: {exc}") from exc
        if not line:
            return None
        return line.decode("utf-8", errors="replace").strip()

    def send_command(self, command: str, expect_response: bool = True) -> SerialResponse:
        self.reconnect_if_needed()
        if not self.connected or not self._serial:
            raise RuntimeError("Serial port is not connected.")

        clean = command.strip()
        if not clean:
            raise ValueError("Refusing to send an empty serial command.")

        try:
            self._serial.write((clean + "\n").encode("utf-8"))
            self._serial.flush()
        except serial.SerialException as exc:
            self.close()
            raise RuntimeError(f"Serial write failed for {clean!r}: {exc}") from exc

        response = self.read_response() if expect_response else None
        return SerialResponse(command=clean, response=response)

    def pan(self, steps: int) -> SerialResponse:
        return self.send_command(f"PAN {int(steps)}")

    def tilt(self, angle: int) -> SerialResponse:
        return self.send_command(f"TILT {int(angle)}")

    def home(self) -> SerialResponse:
        return self.send_command("HOME")

    def stop(self) -> SerialResponse:
        return self.send_command("STOP")

    def status(self) -> SerialResponse:
        return self.send_command("STATUS")

    def drain_responses(self, max_lines: int = 10) -> Iterable[str]:
        for _ in range(max_lines):
            response = self.read_response()
            if response is None:
                return
            yield response

    def __enter__(self) -> "PicoSerialController":
        self.connect()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()


ArduinoSerialController = PicoSerialController
autodetect_arduino_port = autodetect_pico_port
