from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


TRACKER_DIR = Path(__file__).resolve().parent
DEFAULT_POSITION_FILE = TRACKER_DIR / "latest_position.json"


def stop_process(process: subprocess.Popen, timeout_sec: float = 3.0) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    deadline = time.monotonic() + timeout_sec
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    if process.poll() is None:
        process.kill()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the 3D simulator and then run the tracker.")
    parser.add_argument("--position-output", default=str(DEFAULT_POSITION_FILE), help="JSON file shared by tracker and simulator.")
    parser.add_argument("tracker_args", nargs=argparse.REMAINDER, help="Arguments passed to turret_tracker.py after --.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    position_file = Path(args.position_output)
    simulator_cmd = [sys.executable, str(TRACKER_DIR / "space_simulator.py"), "--watch", str(position_file)]
    tracker_args = args.tracker_args[1:] if args.tracker_args[:1] == ["--"] else args.tracker_args
    tracker_cmd = [sys.executable, str(TRACKER_DIR / "turret_tracker.py"), "--position-output", str(position_file), *tracker_args]

    simulator = subprocess.Popen(simulator_cmd)
    try:
        subprocess.run(tracker_cmd, check=False)
    except KeyboardInterrupt:
        print("[launcher] Stopping tracker and simulator.")
    finally:
        stop_process(simulator)


if __name__ == "__main__":
    main()
