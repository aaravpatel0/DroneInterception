from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
import imageio_ffmpeg


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "assets" / "demo_simulations"


@dataclass(frozen=True)
class DemoScenario:
    name: str
    title: str
    description: str
    duration_sec: float
    fps: int
    mode: str
    orbit_radius_inches: float = 38.0
    standoff_inches: float = 48.0


SCENARIOS = {
    "follow": DemoScenario(
        name="follow",
        title="Fast Follow Tracking",
        description="The controlled drone follows a moving target while smoothing camera/depth estimates.",
        duration_sec=18.0,
        fps=24,
        mode="follow",
    ),
    "orbit": DemoScenario(
        name="orbit",
        title="Orbit Tracking",
        description="The controlled drone circles the target while keeping it centered in the camera frame.",
        duration_sec=20.0,
        fps=24,
        mode="orbit",
        orbit_radius_inches=42.0,
    ),
    "standoff": DemoScenario(
        name="standoff",
        title="Safe Standoff Follow",
        description="The controlled drone follows the target but holds a minimum separation distance.",
        duration_sec=18.0,
        fps=24,
        mode="standoff",
        standoff_inches=54.0,
    ),
}


def target_path(t: np.ndarray) -> np.ndarray:
    x = 52.0 * np.sin(0.48 * t) + 14.0 * np.sin(1.18 * t + 0.7)
    y = 34.0 + 13.0 * np.sin(0.62 * t + 0.9)
    z = 118.0 + 38.0 * np.cos(0.34 * t)
    return np.column_stack((x, y, z))


def smooth_measurements(target: np.ndarray, t: np.ndarray) -> np.ndarray:
    noise = np.column_stack(
        (
            2.0 * np.sin(2.7 * t),
            1.5 * np.cos(2.1 * t + 0.4),
            3.0 * np.sin(1.9 * t + 1.2),
        )
    )
    measured = target + noise
    filtered = np.empty_like(measured)
    filtered[0] = measured[0]
    alpha = 0.28
    for idx in range(1, len(measured)):
        filtered[idx] = (1.0 - alpha) * filtered[idx - 1] + alpha * measured[idx]
    return filtered


def desired_position(
    mode: str,
    target: np.ndarray,
    filtered: np.ndarray,
    t_value: float,
    orbit_radius_inches: float,
    standoff_inches: float,
) -> np.ndarray:
    if mode == "orbit":
        angle = 0.85 * t_value
        return filtered + np.array(
            [
                orbit_radius_inches * math.cos(angle),
                0.45 * orbit_radius_inches * math.sin(0.55 * angle),
                orbit_radius_inches * math.sin(angle),
            ]
        )

    offset = target - filtered
    distance = max(float(np.linalg.norm(offset)), 1.0)
    direction = offset / distance
    if mode == "standoff":
        return target - direction * standoff_inches

    # Follow mode stays slightly behind and below the target for a stable camera view.
    return filtered + np.array([0.0, -8.0, -26.0])


def simulate_scenario(scenario: DemoScenario) -> dict[str, np.ndarray]:
    frames = int(scenario.duration_sec * scenario.fps)
    t = np.linspace(0.0, scenario.duration_sec, frames)
    target = target_path(t)
    filtered = smooth_measurements(target, t)
    controlled = np.empty_like(target)
    controlled[0] = np.array([-70.0, 16.0, 30.0])
    velocity = np.zeros(3)
    dt = 1.0 / scenario.fps

    for idx in range(1, frames):
        desired = desired_position(
            scenario.mode,
            target[idx],
            filtered[idx],
            float(t[idx]),
            scenario.orbit_radius_inches,
            scenario.standoff_inches,
        )
        error = desired - controlled[idx - 1]
        acceleration = 2.35 * error - 1.25 * velocity
        acceleration = np.clip(acceleration, -95.0, 95.0)
        velocity = np.clip(velocity + acceleration * dt, -72.0, 72.0)
        controlled[idx] = controlled[idx - 1] + velocity * dt

    line_of_sight = filtered - controlled
    distance = np.linalg.norm(target - controlled, axis=1)
    return {
        "t": t,
        "target": target,
        "filtered": filtered,
        "controlled": controlled,
        "line_of_sight": line_of_sight,
        "distance": distance,
    }


def set_axes(ax, limit: float = 180.0) -> None:
    ax.set_xlim(-limit, limit)
    ax.set_ylim(0, limit * 1.2)
    ax.set_zlim(-20, limit)
    ax.set_box_aspect((2.0, 1.25, 1.25))
    ax.set_xlabel("X left/right (in)")
    ax.set_ylabel("Z forward (in)")
    ax.set_zlabel("Y height (in)")
    ax.grid(True, alpha=0.25)


def create_animation(scenario: DemoScenario, save_path: Path | str | None = None):
    data = simulate_scenario(scenario)
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")
    fig.patch.set_facecolor("#f7f7f3")
    ax.set_facecolor("#fbfbf8")

    skip = max(1, scenario.fps // 12)
    total = len(data["t"])

    def update(frame: int):
        ax.clear()
        set_axes(ax)
        ax.view_init(elev=24, azim=-58)
        ax.set_title(f"{scenario.title}  |  t={data['t'][frame]:.1f}s", pad=18)

        start = max(0, frame - 90)
        target = data["target"]
        filtered = data["filtered"]
        controlled = data["controlled"]
        distance = data["distance"][frame]

        ax.plot(target[start : frame + 1, 0], target[start : frame + 1, 2], target[start : frame + 1, 1], color="#ff8c1a", linewidth=2.5, label="target drone path")
        ax.plot(controlled[start : frame + 1, 0], controlled[start : frame + 1, 2], controlled[start : frame + 1, 1], color="#1f77b4", linewidth=2.5, label="controlled drone path")
        ax.plot(filtered[start : frame + 1 : skip, 0], filtered[start : frame + 1 : skip, 2], filtered[start : frame + 1 : skip, 1], color="#7a3db8", linewidth=1.4, alpha=0.8, label="filtered camera/depth estimate")

        tx, ty, tz = target[frame]
        cx, cy, cz = controlled[frame]
        fx, fy, fz = filtered[frame]
        ax.scatter([tx], [tz], [ty], s=140, color="#ff8c1a", edgecolor="black", linewidth=0.8)
        ax.scatter([cx], [cz], [cy], s=150, color="#1f77b4", edgecolor="black", linewidth=0.8)
        ax.scatter([fx], [fz], [fy], s=90, color="#7a3db8", edgecolor="black", linewidth=0.6)
        ax.plot([cx, fx], [cz, fz], [cy, fy], color="#444444", linewidth=1.6, alpha=0.7, label="camera line of sight")

        ax.text2D(
            0.02,
            0.93,
            f"{scenario.description}\nSeparation: {distance:5.1f} in",
            transform=ax.transAxes,
            fontsize=10,
            color="#222222",
        )
        ax.legend(loc="upper right")
        return []

    anim = animation.FuncAnimation(fig, update, frames=range(0, total, 2), interval=1000 / scenario.fps, blit=False)
    if save_path is not None:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        if save_path.suffix.lower() == ".mp4":
            plt.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
            writer = animation.FFMpegWriter(fps=scenario.fps // 2, bitrate=2200)
        elif save_path.suffix.lower() == ".gif":
            writer = animation.PillowWriter(fps=scenario.fps // 2)
        else:
            raise ValueError(f"Unsupported animation output format: {save_path.suffix}")
        anim.save(save_path, writer=writer)
    return fig, anim


def main() -> None:
    parser = argparse.ArgumentParser(description="Create 3D demo simulations for the drone tracking project.")
    parser.add_argument("--scenario", choices=tuple(SCENARIOS) + ("all",), default="all")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--format", choices=("gif", "mp4", "all"), default="all")
    args = parser.parse_args()

    selected = SCENARIOS.values() if args.scenario == "all" else [SCENARIOS[args.scenario]]
    suffixes = (".gif", ".mp4") if args.format == "all" else (f".{args.format}",)
    for scenario in selected:
        for suffix in suffixes:
            output = args.output_dir / f"{scenario.name}_tracking_demo{suffix}"
            print(f"[demo] saving {output}")
            _, anim = create_animation(scenario, output)
            plt.close(anim._fig)


if __name__ == "__main__":
    main()
