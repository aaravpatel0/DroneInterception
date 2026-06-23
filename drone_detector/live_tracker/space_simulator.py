from __future__ import annotations

import argparse
import json
import socket
import time
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


DEFAULT_POSITION_FILE = Path(__file__).resolve().parent / "latest_position.json"
DEFAULT_IMU_PORT = 4210


def int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def fallback_position(fallback: tuple[float, float, float]) -> dict[str, float]:
    return {"x_inches": fallback[0], "y_inches": fallback[1], "z_inches": fallback[2]}


def load_position(path: Path, fallback: tuple[float, float, float]) -> dict[str, float]:
    if not path.exists():
        return fallback_position(fallback)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback_position(fallback)
    if not isinstance(data, dict):
        return fallback_position(fallback)
    return {key: float(value) for key, value in data.items() if isinstance(value, (int, float))}


def query_imu(host: str | None, port: int, timeout_sec: float) -> dict[str, Any] | None:
    if not host:
        return None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout_sec)
            sock.sendto(b"STATUS", (host, port))
            data, _ = sock.recvfrom(2048)
    except OSError:
        return {"ok": False, "error": "no UDP response"}
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"ok": False, "error": "bad UDP JSON"}
    imu = payload.get("imu")
    return imu if isinstance(imu, dict) else {"ok": False, "error": "missing imu"}


def set_equal_axes(ax, limit: float) -> None:
    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)
    ax.set_zlim(-limit, limit)
    ax.set_box_aspect((1, 1, 1))
    ax.grid(True, alpha=0.35)


def draw_imu_overlay(ax, imu: dict[str, Any] | None, limit: float) -> None:
    ax.scatter([0], [0], [0], c="teal", s=180, label="BMI160 / drone body (0,0,0)")

    if imu is None:
        return

    if not imu.get("ok"):
        ax.text(0, 0, limit * 0.08, f"BMI160: {imu.get('error', 'offline')}", color="crimson")
        return

    accel = imu.get("accel_raw", {})
    gyro = imu.get("gyro_raw", {})
    if not isinstance(accel, dict):
        accel = {}
    if not isinstance(gyro, dict):
        gyro = {}

    ax_value = int_or_none(accel.get("x")) or 0
    ay_value = int_or_none(accel.get("y")) or 0
    az_value = int_or_none(accel.get("z")) or 0
    scale = max(abs(ax_value), abs(ay_value), abs(az_value), 1)
    arrow_len = limit * 0.18
    dx = arrow_len * ax_value / scale
    dy = arrow_len * az_value / scale
    dz = arrow_len * ay_value / scale
    ax.quiver(0, 0, 0, dx, dy, dz, color="teal", linewidth=3, arrow_length_ratio=0.18, label="BMI160 accel vector")

    label = (
        "BMI160 accel raw "
        f"x={ax_value} y={ay_value} z={az_value}\n"
        "gyro raw "
        f"x={gyro.get('x', '-')} y={gyro.get('y', '-')} z={gyro.get('z', '-')}"
    )
    ax.text(limit * 0.04, limit * 0.04, limit * 0.1, label, color="teal")


def camera_position_relative_to_bmi(
    position: dict[str, float],
    mode: str,
    manual_offset: tuple[float, float, float],
) -> tuple[float, float, float]:
    x = position.get("x_inches", 0.0)
    y = position.get("y_inches", 0.0)
    z = position.get("z_inches", 0.0)
    if mode == "tracked-drone":
        return (-x, -y, -z)
    return manual_offset


def add_camera_relative_position(
    camera_position: tuple[float, float, float],
    x: float | None,
    y: float | None,
    z: float | None,
) -> tuple[float, float, float] | None:
    if x is None or y is None or z is None:
        return None
    return (camera_position[0] + x, camera_position[1] + y, camera_position[2] + z)


def draw_scene(
    ax,
    position: dict[str, float],
    imu: dict[str, Any] | None,
    limit: float,
    stale_after_sec: float,
    origin_mode: str,
    manual_camera_offset: tuple[float, float, float],
) -> None:
    x = position.get("x_inches", 0.0)
    y = position.get("y_inches", 0.0)
    z = position.get("z_inches", 0.0)
    px = position.get("predicted_x_inches")
    py = position.get("predicted_y_inches")
    pz = position.get("predicted_z_inches")
    camera = camera_position_relative_to_bmi(position, origin_mode, manual_camera_offset)
    drone = add_camera_relative_position(camera, x, y, z)
    predicted = add_camera_relative_position(camera, px, py, pz)
    ax.clear()
    set_equal_axes(ax, limit)
    updated_at = position.get("updated_at")
    age = time.time() - updated_at if updated_at is not None else None
    stale_label = " (stale)" if age is not None and age > stale_after_sec else ""
    ax.set_title(f"BMI-Origin 3D Map{stale_label}")
    ax.set_xlabel("X left/right from BMI inches")
    ax.set_ylabel("Z forward from BMI inches")
    ax.set_zlabel("Y up/down from BMI inches")

    draw_imu_overlay(ax, imu, limit)

    cx, cy, cz = camera
    ax.scatter([cx], [cz], [cy], c="black", s=140, label=f"Camera ({cx:.1f}, {cy:.1f}, {cz:.1f})")
    if drone is not None:
        dx, dy, dz = drone
        ax.scatter([dx], [dz], [dy], c="orange", s=170, label=f"Tracked drone ({dx:.1f}, {dy:.1f}, {dz:.1f})")
        ax.plot([cx, dx], [cz, dz], [cy, dy], color="gray", linewidth=2.5, label="Camera line of sight")
    if predicted is not None and drone is not None:
        tx, ty, tz = drone
        qx, qy, qz = predicted
        ax.scatter([qx], [qz], [qy], c="purple", s=130, label=f"Predicted ({qx:.1f}, {qy:.1f}, {qz:.1f})")
        ax.quiver(tx, tz, ty, qx - tx, qz - tz, qy - ty, color="purple", linewidth=3, arrow_length_ratio=0.2, label="Predicted motion")

    ax.quiver(0, 0, 0, limit * 0.7, 0, 0, color="red", arrow_length_ratio=0.06)
    ax.quiver(0, 0, 0, 0, limit * 0.7, 0, color="blue", arrow_length_ratio=0.06)
    ax.quiver(0, 0, 0, 0, 0, limit * 0.7, color="green", arrow_length_ratio=0.06)
    ax.text(limit * 0.74, 0, 0, "X", color="red", fontsize=12)
    ax.text(0, limit * 0.74, 0, "Z", color="blue", fontsize=12)
    ax.text(0, 0, limit * 0.74, "Y", color="green", fontsize=12)
    ax.legend(loc="upper left")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show a 3D camera/drone position view.")
    parser.add_argument("--x", type=float, default=0.0, help="Drone X position in inches.")
    parser.add_argument("--y", type=float, default=0.0, help="Drone Y position in inches.")
    parser.add_argument("--z", type=float, default=40.0, help="Drone Z/forward position in inches.")
    parser.add_argument("--limit", type=float, default=240.0, help="Axis limit in inches.")
    parser.add_argument("--figure-size", type=float, nargs=2, default=(12.0, 9.0), metavar=("WIDTH", "HEIGHT"), help="Matplotlib figure size in inches.")
    parser.add_argument("--view-elev", type=float, default=24.0, help="3D camera elevation angle.")
    parser.add_argument("--view-azim", type=float, default=-58.0, help="3D camera azimuth angle.")
    parser.add_argument("--refresh-sec", type=float, default=0.35, help="Graph refresh interval.")
    parser.add_argument("--watch", type=Path, default=DEFAULT_POSITION_FILE, help="Position JSON file to watch.")
    parser.add_argument("--stale-after-sec", type=float, default=2.0, help="Mark the plot stale after this many seconds without tracker updates.")
    parser.add_argument("--imu-host", help="ESP32-C3 IP address for BMI160 UDP STATUS telemetry.")
    parser.add_argument("--imu-port", type=int, default=DEFAULT_IMU_PORT, help="ESP32-C3 UDP telemetry port.")
    parser.add_argument("--imu-timeout-sec", type=float, default=0.1, help="UDP timeout for IMU STATUS polls.")
    parser.add_argument(
        "--origin-mode",
        choices=("tracked-drone", "manual-camera-offset"),
        default="tracked-drone",
        help="Use BMI/drone body as origin. tracked-drone places the camera at the inverse of the visual drone estimate.",
    )
    parser.add_argument("--camera-x-from-bmi", type=float, default=0.0, help="Manual camera X offset from BMI in inches.")
    parser.add_argument("--camera-y-from-bmi", type=float, default=0.0, help="Manual camera Y offset from BMI in inches.")
    parser.add_argument("--camera-z-from-bmi", type=float, default=0.0, help="Manual camera Z offset from BMI in inches.")
    parser.add_argument("--no-watch", action="store_true", help="Show one static position instead of watching a file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fallback = (args.x, args.y, args.z)
    plt.ion()
    fig = plt.figure(figsize=tuple(args.figure_size))
    ax = fig.add_subplot(111, projection="3d")

    while plt.fignum_exists(fig.number):
        position = fallback_position(fallback) if args.no_watch else load_position(args.watch, fallback)
        imu = query_imu(args.imu_host, args.imu_port, args.imu_timeout_sec)
        draw_scene(
            ax,
            position,
            imu,
            args.limit,
            args.stale_after_sec,
            args.origin_mode,
            (args.camera_x_from_bmi, args.camera_y_from_bmi, args.camera_z_from_bmi),
        )
        ax.view_init(elev=args.view_elev, azim=args.view_azim)
        plt.tight_layout()
        plt.pause(args.refresh_sec)
        if args.no_watch:
            plt.ioff()
            plt.show()
            break
        time.sleep(args.refresh_sec)


if __name__ == "__main__":
    main()
