from __future__ import annotations

import argparse
from types import SimpleNamespace

from safe_standoff_controller import NEUTRAL, apply_profile_defaults, make_commands


def pwm_to_delta(command: str) -> int:
    return int(command.split()[1]) - NEUTRAL


def simulation_args(profile: str, standoff_inches: float, max_delta: int | None) -> argparse.Namespace:
    args = SimpleNamespace(
        profile=profile,
        standoff_inches=standoff_inches,
        rate_hz=None,
        stop_band_inches=None,
        stale_after_sec=None,
        x_deadband_inches=None,
        y_deadband_inches=None,
        z_gain=None,
        x_gain=None,
        y_gain=None,
        max_delta=max_delta,
    )
    return apply_profile_defaults(args)


def run_simulation(args: argparse.Namespace) -> None:
    x = args.start_x
    y = args.start_y
    z = args.start_z

    tuning = simulation_args(args.profile, args.standoff_inches, args.max_delta)
    print(
        f"Sim profile={tuning.profile} standoff={tuning.standoff_inches:.1f}in "
        f"rate={tuning.rate_hz:.1f}Hz max_delta={tuning.max_delta}"
    )
    print("time    x      y      z    dist   pitch  roll  throttle")

    dt = 1.0 / tuning.rate_hz
    steps = int(args.duration_sec * tuning.rate_hz)
    for step in range(steps + 1):
        distance = (x * x + y * y + z * z) ** 0.5
        position = {
            "x_inches": x,
            "y_inches": y,
            "z_inches": z,
            "distance_inches": distance,
        }
        commands, _ = make_commands(
            position,
            tuning.standoff_inches,
            tuning.stop_band_inches,
            tuning.x_deadband_inches,
            tuning.y_deadband_inches,
            tuning.z_gain,
            tuning.x_gain,
            tuning.y_gain,
            tuning.max_delta,
        )
        pitch_delta = pwm_to_delta(commands[0])
        roll_delta = pwm_to_delta(commands[1])
        throttle_delta = pwm_to_delta(commands[2])

        if step % max(1, int(tuning.rate_hz * args.print_every_sec)) == 0:
            print(
                f"{step * dt:4.1f} {x:6.1f} {y:6.1f} {z:6.1f} {distance:6.1f} "
                f"{commands[0].split()[1]:>6} {commands[1].split()[1]:>6} {commands[2].split()[1]:>8}"
            )

        # Crude response model: positive pitch reduces forward distance, positive roll reduces right offset,
        # and positive throttle reduces low/negative vertical offset. This is only for command-shape intuition.
        z -= pitch_delta * args.forward_inches_per_sec_per_pwm * dt
        x -= roll_delta * args.lateral_inches_per_sec_per_pwm * dt
        y -= throttle_delta * args.vertical_inches_per_sec_per_pwm * dt


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate safe standoff controller command behavior.")
    parser.add_argument("--profile", choices=("normal", "fast"), default="fast")
    parser.add_argument("--duration-sec", type=float, default=12.0)
    parser.add_argument("--print-every-sec", type=float, default=0.5)
    parser.add_argument("--standoff-inches", type=float, default=72.0)
    parser.add_argument("--max-delta", type=int)
    parser.add_argument("--start-x", type=float, default=30.0)
    parser.add_argument("--start-y", type=float, default=-18.0)
    parser.add_argument("--start-z", type=float, default=150.0)
    parser.add_argument("--forward-inches-per-sec-per-pwm", type=float, default=0.0018)
    parser.add_argument("--lateral-inches-per-sec-per-pwm", type=float, default=0.0012)
    parser.add_argument("--vertical-inches-per-sec-per-pwm", type=float, default=0.0012)
    run_simulation(parser.parse_args())


if __name__ == "__main__":
    main()
